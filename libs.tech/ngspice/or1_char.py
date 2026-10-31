#!/usr/bin/env python3
"""Re-characterise the OR1 standard cells from their layouts.

For every cell the device netlist is taken from magic (`extract` of the cell
GDS, so W/L/ad/as come from the drawn layout, not from the hand-kept CDL),
simulated with the OR1 ngspice models, and written out as a Liberty file.

Usage:
    python3 or1_char.py <cell-device.spice dir> <out.lib>

Delays/transitions are reported with 50 % / 20-80 % thresholds on a 3.3 V
supply at 25 C, over a 5 x 5 grid of input transitions and output loads.
"""
import os
import re
import subprocess
import sys
import tempfile

MODELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "OR1_models.spice")

VDD = 3.3
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
            if tok.startswith("w="):
                w = float(tok[2:].replace("u", ""))
            elif tok.startswith("l="):
                l = float(tok[2:].replace("u", ""))
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
        out.append(f"M{i} {d} {g} {s} {b} {model} W={w}u L={l}u")
    return "\n".join(out)


def run_point(cell, devices, in_pin, other, out_pin, slew, load):
    """One rise+fall transient; returns dict with the four measurements."""
    spec = CELLS[cell]
    ports = spec["inputs"] + [out_pin]
    sources = [f"Vdd vdd 0 {VDD}",
               f"V{in_pin} {in_pin} 0 PULSE(0 {VDD} 2n {slew}n {slew}n 40n 80n)"]
    for name, val in other.items():
        sources.append(f"V{name} {name} 0 {VDD if val else 0}")
    deck = f"""OR1 characterisation {cell} {in_pin}
.include "{MODELS}"
Vdd vdd 0 {VDD}
V{in_pin} {in_pin} 0 PULSE(0 {VDD} 2n {slew}n {slew}n 40n 80n)
{chr(10).join(s for s in sources if not s.startswith('Vdd') and not s.startswith('V' + in_pin + ' '))}
Cout {out_pin} 0 {load}p
.subckt {cell} {" ".join(ports)} vdd
{netlist(devices, pin_map(devices, spec["inputs"], out_pin))}
.ends
X1 {" ".join(ports)} vdd {cell}
.tran 2p 80n
.meas tran tphl trig v({in_pin}) val=1.65 rise=1 targ v({out_pin}) val=1.65 fall=1
.meas tran tplh trig v({in_pin}) val=1.65 fall=1 targ v({out_pin}) val=1.65 rise=1
.meas tran tfall trig v({out_pin}) val=2.64 fall=1 targ v({out_pin}) val=0.66 fall=1
.meas tran trise trig v({out_pin}) val=0.66 rise=1 targ v({out_pin}) val=2.64 rise=1
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
        return vals
    finally:
        os.unlink(path)


def char_cell(cell, devices, spec):
    out_pin = spec["output"]
    arcs = {}
    for related, other in spec["arcs"]:
        rise = []
        fall = []
        rt = []
        ft = []
        for slew in SLEWS:
            row_r, row_f, row_rt, row_ft = [], [], [], []
            for load in LOADS:
                v = run_point(cell, devices, related, other, out_pin, slew, load)
                row_r.append(v["tplh"])
                row_f.append(v["tphl"])
                row_rt.append(v["trise"])
                row_ft.append(v["tfall"])
            rise.append(row_r)
            fall.append(row_f)
            rt.append(row_rt)
            ft.append(row_ft)
        arcs[related] = dict(rise=rise, fall=fall, rtr=rt, ftf=ft)
    return arcs


def table(vals):
    return '"' + ", ".join(f"{v:.4f}" for v in vals) + '"'


def main():
    src, out_lib = sys.argv[1], sys.argv[2]
    cells = {}
    for cell in CELLS:
        cells[cell] = load_cell(os.path.join(src, cell + ".spice"))
    results = {}
    for cell, spec in CELLS.items():
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
        f.write('  input_threshold_pct_rise : 50 ;\n  input_threshold_pct_fall : 50 ;\n')
        f.write('  output_threshold_pct_rise : 50 ;\n  output_threshold_pct_fall : 50 ;\n')
        f.write('  nom_voltage : 3.3 ;\n  nom_temperature : 25 ;\n')
        f.write('  lu_table_template(char_4x4) {\n')
        f.write('    variable_1 : input_net_transition ;\n')
        f.write('    variable_2 : total_output_net_capacitance ;\n')
        f.write(f'    index_1 ({table(SLEWS)}) ;\n')
        f.write(f'    index_2 ({table(LOADS)}) ;\n  }}\n')
        for cell, spec in CELLS.items():
            r = results[cell]
            f.write(f'  cell ({cell}) {{\n    area : {spec["area"]} ;\n')
            for pin in spec["inputs"]:
                f.write(f'    pin ({pin}) {{\n      direction : input ;\n      capacitance : 0.004 ;\n    }}\n')
            f.write(f'    pin ({spec["output"]}) {{\n      direction : output ;\n')
            f.write(f'      function : "{spec["function"]}" ;\n')
            f.write('      max_capacitance : 0.25 ;\n')
            for related, a in r.items():
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
    print(f"wrote {out_lib}", file=sys.stderr)


if __name__ == "__main__":
    main()
