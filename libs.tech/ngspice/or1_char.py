#!/usr/bin/env python3
"""Re-characterise the OR1 standard cells from their layouts.

For every cell the device netlist is taken from magic (`extract` of the cell
GDS, so W/L/ad/as come from the drawn layout, not from the hand-kept CDL),
simulated with the OR1 ngspice models, and written out as a Liberty file.

Usage:
    python3 or1_char.py <cell-device.spice dir> <out.lib>

Delays/transitions are reported with 50 % / 20-80 % thresholds on a 5.0 V
supply at 25 C (the process is used at 5 V - see
docs/measure/2026-11-01-round9-supply-determination.md), over a 4 x 4 grid of
input transitions and output loads.  `--vdd` selects another supply.
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# Model set: "virtual" (LEVEL=1, tentative) is the default and the only set
# the shipped library is built with.  "bsim3" selects the upstream BSIM3V3
# cards in upstream_bsim3/ and is EXPERIMENTAL - it never changes the default.
# Select with --models bsim3 or with the OR1_CHAR_MODELS environment variable.
MODEL_SET = "virtual"
MODELS = []
MODEL_MAP = {}


def select_models(name):
    """Set the module-level model table; call before characterising."""
    global MODEL_SET, MODELS, MODEL_MAP
    MODEL_SET = (name or "virtual").lower()
    if MODEL_SET == "virtual":
        MODELS = [os.path.join(HERE, "OR1_models.spice")]
        MODEL_MAP = {}
    elif MODEL_SET == "bsim3":
        MODELS = [os.path.join(HERE, "upstream_bsim3", "BSIM3V3N.mod"),
                  os.path.join(HERE, "upstream_bsim3", "BSIM3V3P.mod")]
        MODEL_MAP = {"NMOS": "nch", "PMOS": "pch"}  # load_cell() normalises names
    else:
        raise SystemExit("unknown model set %r (use virtual or bsim3)" % MODEL_SET)


select_models(os.environ.get("OR1_CHAR_MODELS", "virtual"))

# Operating point: the OR1 process is used at 5 V on silicon (both shuttles,
# see OR1PDK/docs/measure/2026-11-01-round9-supply-determination.md).  The
# shipped upstream Liberty is labelled 3.3 V; 5.0 V is the determined value.
# Override with --vdd.
VDD = 5.0
CORNERS = ["tt"]

# 20-80 % input transitions (ns) and output loads (pF)
SLEWS = [0.2, 0.5, 1.0, 2.0]
LOADS = [0.01, 0.03, 0.06, 0.12]

# cell -> (inputs, output, arcs[(related_pin, other_inputs{})], function)
CELLS = {
    "INVX1":    dict(inputs=["A"], output="Y",
                     arcs=[("A", {})], function="!A", area=6.5),
    "BUFX2":    dict(inputs=["A"], output="Y",
                     arcs=[("A", {})], function="A", area=12.5),
    "NAND2X1":  dict(inputs=["A", "B"], output="Y",
                     arcs=[("A", {"B": 1}), ("B", {"A": 1})],
                     function="!(A*B)", area=9.5),
    "NOR2X1":   dict(inputs=["A", "B"], output="Y",
                     arcs=[("A", {"B": 0}), ("B", {"A": 0})],
                     function="!(A+B)", area=9.5),
    # clock-to-Q only: the rise table is taken with D=1 and the fall table
    # with D=0, which is the standard way to fill a DFF arc.
    "CLKBUFX2": dict(inputs=["A"], output="Y",
                     arcs=[("A", {})], function="A", area=12.5 * 30),
    # static-master DFFR: same core as DFFRX1 plus the keeper inverter
    # (net104 -> net114).  RESET is held low during characterisation.
    "DFFRX2": dict(inputs=["D", "CLK", "RESET"], output="Q",
                   arcs=[("CLK", {"D": 1}), ("CLK", {"D": 0})],
                   function="IQ", area=3000, kind="dff"),
    # plain resettable DFF (same core as DFFRX2 without the keeper inverter)
    "DFFRX1": dict(inputs=["D", "CLK", "RESET"], output="Q",
                   arcs=[("CLK", {"D": 1}), ("CLK", {"D": 0})],
                   function="IQ", area=384, kind="dff"),
    "DFFPOSX1": dict(inputs=["D", "CLK"], output="Q",
                     arcs=[("CLK", {"D": 1}), ("CLK", {"D": 0})],
                     function="IQ", area=384, kind="dff"),
}

# extracted with magic; bulk pins VDD/VSS are rewritten to vdd/0
def load_cell(path):
    lines = []
    for raw in open(path):
        s = raw.strip()
        if s.startswith("M"):
            lines.append(s)
        elif s.startswith("+"):
            lines[-1] += " " + s[1:].strip()
    devices = []
    for ln in lines:
        p = ln.split()
        d, g, s, b = p[1:5]
        model = p[5].lower()
        w = l = None
        for tok in p[6:]:
            t = tok.strip(",").lower()
            if t.startswith("w="):
                w = float(t[2:].replace("u", ""))
            elif t.startswith("l="):
                l = float(t[2:].replace("u", ""))
        if model == "pfet":
            b = "vdd"
            model = "PMOS"
        else:
            b = "0"
            model = "NMOS"
        s = "vdd" if s.upper() == "VDD" else ("0" if s.upper() == "VSS" else s)
        d = "vdd" if d.upper() == "VDD" else ("0" if d.upper() == "VSS" else d)
        devices.append((d, g, s, b, model, w, l))
    return devices


# Multi-stage cells: magic's per-cell extraction can leave an internal net
# split at a contact (the two halves keep different names).  Alias the halves
# back together before characterising.
NODE_ALIAS = {
    "BUFX2": {"a_8_21#": "a_1_5#"},
}


def pin_map(devices, inputs, output):
    """Map Liberty pin names to the nodes used by the extracted netlist.

    The extracted netlist only keeps labels on the output (Y).  Input pins are
    the nodes that appear as a gate but are never driven by a drain/source;
    they are assigned to the cell's inputs in sorted order.
    """
    alias = NODE_ALIAS.get(_CURRENT_CELL[0], {})
    driven = set()
    gates = set()
    for d, g, s, b, model, w, l in devices:
        d, g, s = alias.get(d, d), alias.get(g, g), alias.get(s, s)
        driven.add(d)
        driven.add(s)
        gates.add(g)
    nodes = set()
    for d, g, s, b, model, w, l in devices:
        nodes |= {d, g, s}
    if all(p in nodes for p in inputs) and output in nodes:
        return {p: p for p in inputs} | {output: output}
    ports = sorted(gates - driven)
    if len(ports) != len(inputs):
        raise RuntimeError(f"pin detection failed: {ports} vs {inputs}")
    return dict(zip(inputs, ports)) | {output: output}


_CURRENT_CELL = [""]


def netlist(devices, mapping):
    alias = NODE_ALIAS.get(_CURRENT_CELL[0], {})
    rev = {v: k for k, v in mapping.items()}
    out = []
    for i, (d, g, s, b, model, w, l) in enumerate(devices):
        d = alias.get(d, d)
        g = alias.get(g, g)
        s = alias.get(s, s)
        d = rev.get(d, d)
        g = rev.get(g, g)
        s = rev.get(s, s)
        model = MODEL_MAP.get(model, model)
        out.append(f"M{i} {d} {g} {s} {b} {model} W={w}u L={l}u")
    return "\n".join(out)


_TRIPS = []


def trip_point(cell, devices, in_pin, other, out_pin):
    """Input voltage at which the output crosses VDD/2 in a DC sweep.

    At 5 V the OR1 cells switch at ~1.8 V, not at VDD/2 = 2.5 V.  Measuring a
    50 %->50 % delay against a 2.5 V input reference then gives *negative*
    delays for slow input edges (the output crosses 2.5 V before the input
    does).  The delay is therefore referenced to the cell's own switching
    point, and the Liberty input threshold is set to the measured average.
    """
    spec = CELLS[cell]
    ports = spec["inputs"] + [out_pin]
    src = [f"V{name} {name} 0 {VDD if val else 0}" for name, val in other.items()]
    outfile = tempfile.mktemp(suffix=".txt")
    deck = f"""OR1 trip {cell} {in_pin}
{chr(10).join('.include "%s"' % m for m in MODELS)}
Vdd vdd 0 {VDD}
V{in_pin} {in_pin} 0 0
{chr(10).join(src)}
.subckt {cell} {" ".join(ports)} vdd
{netlist(devices, pin_map(devices, spec["inputs"], out_pin))}
.ends
X1 {" ".join(ports)} vdd {cell}
.control
dc V{in_pin} 0 {VDD} {VDD/500}
wrdata {outfile} v({out_pin})
.endc
.end
"""
    path = tempfile.mktemp(suffix=".sp")
    with open(path, "w") as fh:
        fh.write(deck)
    subprocess.run(["ngspice", "-b", path], capture_output=True, text=True)
    pts = []
    try:
        for line in open(outfile):
            f = line.split()
            if len(f) >= 2:
                try:
                    pts.append((float(f[0]), float(f[1])))
                except ValueError:
                    pass
    except OSError:
        pass
    vref = VDD / 2.0
    for i in range(1, len(pts)):
        a, b = pts[i - 1][1], pts[i][1]
        if (a - VDD / 2.0) * (b - VDD / 2.0) <= 0 and a != b:
            t = (VDD / 2.0 - a) / (b - a)
            vref = pts[i - 1][0] + t * (pts[i][0] - pts[i - 1][0])
            break
    for f in (outfile, path):
        try:
            os.unlink(f)
        except OSError:
            pass
    return vref


def run_point(cell, devices, in_pin, other, out_pin, slew, load, vref,
              require=("tphl", "tplh", "tfall", "trise")):
    """One rise+fall transient; returns dict with the four measurements."""
    spec = CELLS[cell]
    # tphl = the input edge that makes the output fall, tplh = the one that
    # makes it rise.  For an inverting cell that is input rise / input fall;
    # for a non-inverting cell (BUFX2) it is the opposite.  Measuring a fixed
    # polarity (rise->fall) on a buffer finds no edge and yields garbage.
    inverting = spec["function"].lstrip().startswith("!")
    trig_phl = "rise" if inverting else "fall"
    trig_plh = "fall" if inverting else "rise"
    vmid = VDD / 2.0
    meas_tphl = (".meas tran tphl trig v(%s) val=%.6g %s=1 "
                 "targ v(%s) val=%.6g fall=1" % (in_pin, vref, trig_phl, out_pin, vmid))
    meas_tplh = (".meas tran tplh trig v(%s) val=%.6g %s=1 "
                 "targ v(%s) val=%.6g rise=1" % (in_pin, vref, trig_plh, out_pin, vmid))
    ports = spec["inputs"] + [out_pin]
    sources = [f"Vdd vdd 0 {VDD}",
               f"V{in_pin} {in_pin} 0 PULSE(0 {VDD} 2n {slew}n {slew}n 40n 80n)"]
    for name, val in other.items():
        sources.append(f"V{name} {name} 0 {VDD if val else 0}")
    deck = f"""OR1 characterisation {cell} {in_pin}
{chr(10).join('.include "%s"' % m for m in MODELS)}
Vdd vdd 0 {VDD}
V{in_pin} {in_pin} 0 PULSE(0 {VDD} 2n {slew}n {slew}n 40n 80n)
{chr(10).join(s for s in sources if not s.startswith('Vdd') and not s.startswith('V' + in_pin + ' '))}
Cout {out_pin} 0 {load}p
.subckt {cell} {" ".join(ports)} vdd
{netlist(devices, pin_map(devices, spec["inputs"], out_pin))}
.ends
X1 {" ".join(ports)} vdd {cell}
.tran 2p 80n
{meas_tphl}
{meas_tplh}
.meas tran tfall trig v({out_pin}) val={0.8*VDD:.6g} fall=1 targ v({out_pin}) val={0.2*VDD:.6g} fall=1
.meas tran trise trig v({out_pin}) val={0.2*VDD:.6g} rise=1 targ v({out_pin}) val={0.8*VDD:.6g} rise=1
.end
"""
    with tempfile.NamedTemporaryFile("w", suffix=".sp", delete=False) as fh:
        fh.write(deck)
        path = fh.name
    try:
        r = subprocess.run(["ngspice", "-b", path], capture_output=True, text=True)
        txt = r.stdout + r.stderr
        vals = {}
        for key in ("tphl", "tplh", "tfall", "trise"):
            m = re.search(rf"{key}\s*=\s*([-\d.eE+]+)", txt)
            vals[key] = float(m.group(1)) * 1e9 if m else float("nan")
        vals["_log"] = txt
        bad = [k for k in require if not (vals[k] == vals[k])]  # NaN check
        if bad:
            raise RuntimeError("measurement failed for %s (%s): %s"
                               % (cell, in_pin, ", ".join(bad)))
        return vals
    finally:
        os.unlink(path)


_NEG = []


def _dff_sim(cell, devices, slew, load, d0, d_events, tstop=34.0, step=2.0):
    """Run the 3-edge DFF stimulus and return (times, v(q)).

    Edges at 5/15/25 ns: the first two establish a known state (Q=1 after
    edge 1 with D=1, Q=0 after edge 2 with D=0), the third is the edge under
    test.  `d_events` is a list of (time_ns, value) transitions of D, each
    with the same `slew` as the clock, so the 50 % crossing is at `time_ns`.
    """
    spec = CELLS[cell]
    ports = spec["inputs"] + [spec["output"]]
    tr = slew / 2.0
    clk_pts = ["(0 0)"]
    for te in (5.0, 15.0, 25.0):
        clk_pts.append(f"({te - tr:.4f}n 0)")
        clk_pts.append(f"({te + tr:.4f}n {VDD})")
        if te < 25.0:
            clk_pts.append(f"({te + 5 - tr:.4f}n {VDD})")
            clk_pts.append(f"({te + 5 + tr:.4f}n 0)")
    clk_pts.append(f"({tstop}n {VDD})")
    d_pts = [f"(0 {d0})"]
    prev = d0
    for td, val in d_events:
        lo = max(td - tr, 0.0)
        d_pts.append(f"({lo:.4f}n {prev})")
        d_pts.append(f"({td + tr:.4f}n {val})")
        prev = val
    d_pts.append(f"({tstop}n {prev})")
    vmid = VDD / 2.0
    outfile = tempfile.mktemp(suffix=".txt")
    reset = "VRESET RESET 0 0\n" if "RESET" in spec["inputs"] else ""
    deck = f"""OR1 dff {cell}
{chr(10).join('.include "%s"' % m for m in MODELS)}
Vdd vdd 0 {VDD}
VCLK CLK 0 PWL {" ".join(clk_pts)}
VD D 0 PWL {" ".join(d_pts)}
{reset}Cout {spec["output"]} 0 {load}p
.subckt {cell} {" ".join(ports)} vdd
{netlist(devices, pin_map(devices, spec["inputs"], spec["output"]))}
.ends
X1 {" ".join(ports)} vdd {cell}
.options gmin=1e-12 itl1=500 reltol=1e-4
.tran {step}p {tstop}n
.control
run
wrdata {outfile} v(CLK) v({spec["output"]})
.endc
.end
"""
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".sp", delete=False) as fh:
            fh.write(deck)
            path = fh.name
        subprocess.run(["ngspice", "-b", path], capture_output=True, text=True)
        os.unlink(path)
        rows = [list(map(float, ln.split())) for ln in open(outfile) if ln.strip()]
        os.unlink(outfile)
        t = [r[0] * 1e9 for r in rows]   # ns
        q = [r[3] for r in rows]
        return t, q
    finally:
        pass


def _cross(t, sig, level, t0=0.0, t1=1e9):
    """First upward-or-downward 50 % crossing of `sig` in [t0, t1] (ns)."""
    for i in range(1, len(sig)):
        if t[i - 1] < t0 or t[i - 1] > t1:
            continue
        if (sig[i - 1] - level) * (sig[i] - level) < 0:
            f = (level - sig[i - 1]) / (sig[i] - sig[i - 1])
            return t[i - 1] + f * (t[i] - t[i - 1])
    return None


def run_dff_point(cell, devices, slew, load, vref):
    """Clock-to-Q fall and rise of a positive-edge DFF (ns).

    Fall: D=1 before edge 2 (15 ns).  Rise: D=0 before edge 3 (25 ns) and
    raised while the clock is low before it.  Both are measured against the
    clock edge's 50 % crossing.
    """
    vmid = VDD / 2.0
    t, q = _dff_sim(cell, devices, slew, load, VDD, [(10.0, 0)], tstop=34.0)
    tf = _cross(t, q, vmid, 15.0, 22.0)
    tfall = _transition(t, q, 15.0, 22.0)
    t, q = _dff_sim(cell, devices, slew, load, 0, [(20.0, VDD)], tstop=34.0)
    tr = _cross(t, q, vmid, 25.0, 32.0)
    trise = _transition(t, q, 25.0, 32.0)
    if tf is None or tr is None:
        raise RuntimeError("dff measurement failed for %s (no Q transition)" % cell)
    return {"tphl": tf - 15.0, "tplh": tr - 25.0,
            "trise": trise, "tfall": tfall}


def _transition(t, q, t0, t1):
    lo = 0.2 * VDD
    hi = 0.8 * VDD
    ta = _cross(t, q, lo, t0, t1)
    tb = _cross(t, q, hi, t0, t1)
    if ta is None or tb is None:
        return float("nan")
    return abs(tb - ta)


def run_dff_constraint(cell, devices, slew, load, mode, iters=10, span=3.0):
    """Setup or hold time of the D pin against the CLK rising edge (ns).

    Bisection: the smallest data-to-clock separation at which the third clock
    edge still captures D=1 (setup) / does not disturb the captured 1 (hold).
    """
    vmid = VDD / 2.0

    def captures(off):
        if mode == "setup":
            # D=0 through edges 1-2, raised (25-off) before edge 3.
            t, q = _dff_sim(cell, devices, slew, load, 0,
                            [(25.0 - off, VDD)], tstop=36.0, step=5.0)
        else:
            # D=1 through edges 1-3, falls (25+off) after edge 3.
            t, q = _dff_sim(cell, devices, slew, load, VDD,
                            [(25.0 + off, 0)], tstop=36.0, step=5.0)
        if not t:
            return False
        return q[-1] > vmid

    lo, hi = 0.0, span
    if not captures(hi):
        raise RuntimeError("dff %s %s: no passing point within %.1f ns"
                           % (cell, mode, span))
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if captures(mid):
            hi = mid
        else:
            lo = mid
    return hi


def char_cell(cell, devices, spec):
    out_pin = spec["output"]
    arcs = {}
    is_dff = spec.get("kind") == "dff"
    for related, other in spec["arcs"]:
        if is_dff:
            vref = VDD / 2.0
        else:
            vref = trip_point(cell, devices, related, other, out_pin)
        _TRIPS.append(vref / VDD * 100.0)
        print(f"  {cell} arc {related}: trip {vref:.3f} V "
              f"({vref / VDD * 100:.1f} % of VDD)", file=sys.stderr)
        rise = []
        fall = []
        rt = []
        ft = []
        for slew in SLEWS:
            row_r, row_f, row_rt, row_ft = [], [], [], []
            for load in LOADS:
                if is_dff:
                    v = run_dff_point(cell, devices, slew, load, vref)
                else:
                    v = run_point(cell, devices, related, other, out_pin, slew, load, vref)
                row_r.append(v["tplh"])
                row_f.append(v["tphl"])
                if v["tplh"] < 0 or v["tphl"] < 0:
                    _NEG.append((cell, related, slew, load, v["tplh"], v["tphl"]))
                row_rt.append(v["trise"])
                row_ft.append(v["tfall"])
            rise.append(row_r)
            fall.append(row_f)
            rt.append(row_rt)
            ft.append(row_ft)
        arcs[related] = dict(rise=rise, fall=fall, rtr=rt, ftf=ft)
    if is_dff and os.environ.get("OR1_CHAR_SH", "1") != "0":
        sh = {}
        for mode in ("setup", "hold"):
            worst = 0.0
            for slew in SLEWS:
                for load in (LOADS[0], LOADS[-1]):
                    value = run_dff_constraint(cell, devices, slew, load, mode)
                    worst = max(worst, value)
                    print(f"  {cell} {mode}: slew {slew} ns load {load} pF"
                          f" -> {value:.3f} ns", file=sys.stderr)
            sh[mode] = worst
        arcs["__constraints__"] = sh
        print(f"  {cell} worst-case {sh}", file=sys.stderr)
    return arcs


def table(vals):
    return '"' + ", ".join(f"{v:.4f}" for v in vals) + '"'


def main():
    global VDD
    args = sys.argv[1:]
    if "--vdd" in args:
        i = args.index("--vdd")
        if i + 1 >= len(args):
            raise SystemExit("--vdd needs a value in volts")
        VDD = float(args[i + 1])
        del args[i:i + 2]
    if "--models" in args:
        i = args.index("--models")
        if i + 1 >= len(args):
            raise SystemExit("--models needs an argument (virtual|bsim3)")
        select_models(args[i + 1])
        del args[i:i + 2]
    args = [a[len("--models="):] if a.startswith("--models=") else a for a in args]
    if len(args) != 2:
        raise SystemExit(
            "usage: or1_char.py [--models virtual|bsim3] [--vdd V] <cell-spice-dir> <out.lib>")
    src, out_lib = args
    only = os.environ.get("OR1_CHAR_CELLS", "").split()
    # DFFPOSX1 is opt-in only: its clock polarity is still unresolved
    # (round16 note), so a default run must not emit a bogus table.
    selected = [c for c in CELLS if not only or c in only]
    cells = {}
    for cell in selected:
        cells[cell] = load_cell(os.path.join(src, cell + ".spice"))
    results = {}
    for cell in selected:
        spec = CELLS[cell]
        _CURRENT_CELL[0] = cell
        print(f"characterising {cell} …", file=sys.stderr)
        results[cell] = char_cell(cell, cells[cell], spec)

    with open(out_lib, "w") as f:
        f.write('library(or1_fd_sc) {\n')
        f.write('  delay_model : table_lookup ;\n  time_unit : "1ns" ;\n')
        f.write('  voltage_unit : "1V" ;\n  current_unit : "1uA" ;\n')
        f.write('  capacitive_load_unit (1,pf) ;\n  leakage_power_unit : "1nW" ;\n')
        f.write('  slew_upper_threshold_pct_rise : 80 ;\n  slew_lower_threshold_pct_rise : 20 ;\n')
        f.write('  slew_upper_threshold_pct_fall : 80 ;\n  slew_lower_threshold_pct_fall : 20 ;\n')
        _ith = (sum(_TRIPS) / len(_TRIPS)) if _TRIPS else 50.0
        f.write(f'  input_threshold_pct_rise : {_ith:.1f} ;\n')
        f.write(f'  input_threshold_pct_fall : {_ith:.1f} ;\n')
        f.write('  output_threshold_pct_rise : 50 ;\n  output_threshold_pct_fall : 50 ;\n')
        f.write(f'  nom_voltage : {VDD:g} ;\n  nom_temperature : 25 ;\n')
        f.write('  lu_table_template(char_4x4) {\n')
        f.write('    variable_1 : input_net_transition ;\n')
        f.write('    variable_2 : total_output_net_capacitance ;\n')
        f.write(f'    index_1 ({table(SLEWS)}) ;\n')
        f.write(f'    index_2 ({table(LOADS)}) ;\n  }}\n')
        for cell in selected:
            spec = CELLS[cell]
            r = results[cell]
            f.write(f'  cell ({cell}) {{\n    area : {spec["area"]} ;\n')
            for pin in spec["inputs"]:
                f.write(f'    pin ({pin}) {{\n      direction : input ;\n      capacitance : 0.004 ;\n    }}\n')
            f.write(f'    pin ({spec["output"]}) {{\n      direction : output ;\n')
            f.write(f'      function : "{spec["function"]}" ;\n')
            f.write('      max_capacitance : 0.25 ;\n')
            sh = r.get("__constraints__")
            if sh:
                for timing_type, key in (("setup_rising", "setup"),
                                         ("hold_rising", "hold")):
                    f.write('      timing () {\n')
                    f.write('        related_pin : "CLK" ;\n')
                    f.write(f'        timing_type : {timing_type} ;\n')
                    f.write(f'        rise_constraint ({sh[key]:.4f}) ;\n')
                    f.write(f'        fall_constraint ({sh[key]:.4f}) ;\n')
                    f.write('      }\n')
            for related, a in r.items():
                if related.startswith("__"):
                    continue
                f.write('      timing () {\n')
                f.write(f'        related_pin : "{related}" ;\n')
                sense = "negative_unate" if cell in ("INVX1", "NAND2X1", "NOR2X1") else "positive_unate"
                f.write(f'        timing_sense : {sense} ;\n')
                for name, key in (("cell_rise", "rise"), ("cell_fall", "fall"),
                                  ("rise_transition", "rtr"), ("fall_transition", "ftf")):
                    f.write(f'        {name}(char_4x4) {{\n          values ( \\\n')
                    rows = a[key]
                    for i, row in enumerate(rows):
                        sep = "," if i < len(rows) - 1 else ""
                        f.write(f'            {table(row)}{sep} \\\n')
                    f.write('          ) ;\n        }\n')
                f.write('      }\n')
            f.write('    }\n  }\n')
        f.write('}\n')
    if _NEG:
        print("WARNING: %d negative delay entries - the input 50%% crossing is "
              "later than the output crossing, which happens when the cell's "
              "switching threshold is far from VDD/2 (at 5 V the OR1 inverter "
              "trips at ~1.8 V).  Such tables are not usable for STA; see "
              "docs/measure/2026-11-01-round9-supply-determination.md." % len(_NEG),
              file=sys.stderr)
        for cell, rel, slew, load, tp, tf in _NEG[:5]:
            print("  %s arc %s slew %.1f ns load %.2f pF: tplh=%.3f tphl=%.3f"
                  % (cell, rel, slew, load, tp, tf), file=sys.stderr)
    print(f"wrote {out_lib}", file=sys.stderr)


if __name__ == "__main__":
    main()
