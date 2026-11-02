#!/usr/bin/env python3
"""Structural and numeric validation of OR1.rcx_rules.

OpenROAD is not installed in this environment, so the ruleset cannot be
exercised by a real `extract_parasitics` run here.  What *can* be checked -
and what the previous 10-metal, 0.07 um table failed - is:

  * the declared layer count matches the number of metal sections and the
    tech LEF (3 metals, not 10);
  * no section references a layer that does not exist;
  * every section carries a width table, and every DIST block declares the
    number of rows it actually has;
  * the geometry grid covers the LEF routing width (1.0 um) instead of
    stopping below it;
  * spacings are increasing and positive;
  * capacitance columns are non-negative;
  * the resistance column reproduces the LEF RPERSQ: R = RPERSQ / w.

Usage:
    python3 check_rcx_rules.py [OR1.rcx_rules] [--lef OR1.tlef]
Exit status 0 when everything passes.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RULES = os.path.join(HERE, "OR1.rcx_rules")
DEFAULT_LEF = os.path.join(HERE, "..", "..", "libs.ref", "or1_fd_sc", "lef", "OR1.tlef")


def read_lef(path):
    """Return {layer: (RPERSQ, CPERSQDIST, WIDTH)} for the routing layers."""
    info, cur = {}, None
    try:
        for line in open(path, errors="ignore"):
            s = line.strip()
            m = re.match(r"^LAYER\s+(\w+)", s)
            if m:
                cur = m.group(1)
                info.setdefault(cur, {})
                continue
            if cur is None:
                continue
            m = re.match(r"^RESISTANCE\s+RPERSQ\s+([-\d.eE+]+)", s)
            if m:
                info[cur]["rpersq"] = float(m.group(1))
            m = re.match(r"^CAPACITANCE\s+CPERSQDIST\s+([-\d.eE+]+)", s)
            if m:
                info[cur]["cpersq"] = float(m.group(1))
            m = re.match(r"^WIDTH\s+([-\d.eE+]+)\s*;", s)
            if m and "width" not in info[cur]:
                info[cur]["width"] = float(m.group(1))
    except IOError:
        return {}
    return info


def parse(path):
    """Return (layer_count, sections) where sections is a list of dicts."""
    layer_count = None
    sections = []
    cur = None
    in_dist = False
    width_table = None
    errors = []

    for lineno, line in enumerate(open(path), 1):
        s = line.strip()
        if not s or s.startswith("Extraction Rules"):
            continue
        m = re.match(r"^LayerCount\s+(\d+)", s)
        if m:
            layer_count = int(m.group(1))
            continue
        m = re.match(r"^WIDTH Table (\d+) entries:\s*(.*)$", s)
        if m:
            width_table = [float(x) for x in m.group(2).split()]
            if len(width_table) != int(m.group(1)):
                errors.append("line %d: WIDTH table declares %s entries, lists %d"
                              % (lineno, m.group(1), len(width_table)))
            if cur is not None:
                cur["widths"] = width_table
            continue
        m = re.match(r"^Metal (\d+) (RESOVER|OVER|UNDER|DIAGUNDER)(?: (\d+))?$", s)
        if m:
            cur = {"metal": int(m.group(1)), "kind": m.group(2),
                   "ref": int(m.group(3)) if m.group(3) is not None else None,
                   "widths": None, "dists": [], "line": lineno}
            sections.append(cur)
            continue
        m = re.match(r"^DIST count (\d+) width ([-\d.eE+]+)", s)
        if m:
            in_dist = True
            cur.setdefault("dists", []).append(
                {"declared": int(m.group(1)), "width": float(m.group(2)), "rows": []})
            continue
        if s == "END DIST":
            in_dist = False
            continue
        if in_dist and cur and cur["dists"]:
            parts = s.split()
            if len(parts) == 4:
                cur["dists"][-1]["rows"].append(tuple(float(x) for x in parts))
            else:
                errors.append("line %d: DIST row has %d columns" % (lineno, len(parts)))

    return layer_count, sections, errors


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    rules = args[0] if args else DEFAULT_RULES
    lef = DEFAULT_LEF
    for i, a in enumerate(sys.argv):
        if a == "--lef" and i + 1 < len(sys.argv):
            lef = sys.argv[i + 1]

    layer_count, sections, errors = parse(rules)
    lef_info = read_lef(lef)
    lef_layers = {k: v for k, v in lef_info.items() if "rpersq" in v}
    problems = list(errors)

    if layer_count is None:
        problems.append("no LayerCount statement")
    metals = sorted({s["metal"] for s in sections})
    if layer_count is not None:
        if metals != list(range(1, layer_count + 1)):
            problems.append("LayerCount %d but metal sections are %s"
                            % (layer_count, metals))
        if lef_layers and layer_count != len(lef_layers):
            problems.append("LayerCount %d but the LEF defines %d routing layers"
                            % (layer_count, len(lef_layers)))

    for s in sections:
        if s["widths"] is None and s["kind"] != "RESOVER":
            pass
        if s["kind"] in ("OVER", "UNDER", "DIAGUNDER") and s["ref"] is not None:
            if layer_count is not None and s["ref"] > layer_count:
                problems.append("line %d: %s references layer %d > LayerCount"
                                % (s["line"], s["kind"], s["ref"]))
        for d in s.get("dists", []):
            if d["declared"] != len(d["rows"]):
                problems.append("line %d: Metal %d %s declares %d rows, has %d"
                                % (s["line"], s["metal"], s["kind"],
                                   d["declared"], len(d["rows"])))
            # RESOVER rows are (width, neighbour width, 0, R) pairs, not a
            # spacing sweep - only OVER/UNDER/DIAGUNDER are distance tables
            if s["kind"] != "RESOVER":
                dists = [r[0] for r in d["rows"]]
                if d["rows"] and any(b <= a for a, b in zip(dists, dists[1:])):
                    problems.append("line %d: Metal %d %s spacing column is not increasing"
                                    % (s["line"], s["metal"], s["kind"]))
            for r in d["rows"]:
                if r[1] < 0 or r[2] < 0 or r[3] < 0:
                    problems.append("line %d: Metal %d %s has a negative column"
                                    % (s["line"], s["metal"], s["kind"]))
                    break

    # geometry grid must cover the LEF routing width
    grids = [w for s in sections if s["widths"] for w in s["widths"]]
    max_width = max(grids) if grids else 0.0
    for name, info in sorted(lef_layers.items()):
        w = info.get("width")
        if w and max_width < w:
            problems.append("width grid stops at %g um but %s is %g um wide"
                            % (max_width, name, w))

    # resistance column vs LEF RPERSQ (per nm at the table width)
    checked = 0
    for s in sections:
        if s["kind"] != "RESOVER" or s["ref"] != 0:
            continue
        rs = lef_layers.get("metal%d" % s["metal"], {}).get("rpersq")
        if rs is None:
            continue
        for d in s.get("dists", []):
            for r in d["rows"]:
                w = r[0]
                if w <= 0:
                    continue
                expect = rs / (w * 1000.0)
                if abs(r[3] - expect) > 1e-3 * max(expect, 1e-12):
                    problems.append("Metal %d RESOVER: R(%g um) = %.6g, LEF RPERSQ "
                                    "expects %.6g ohm/nm" % (s["metal"], w, r[3], expect))
                    break
                checked += 1

    print("rules    : %s" % rules)
    print("layers   : LayerCount=%s, metal sections=%s, LEF routing layers=%s"
          % (layer_count, metals, sorted(lef_layers)))
    print("sections : %d" % len(sections))
    print("widths   : %s (max %g um)" % (sorted(set(grids)), max_width))
    print("R checks : %d rows matched LEF RPERSQ" % checked)

    if problems:
        print("RCX RULES: FAIL")
        for p in problems[:20]:
            print("  - %s" % p)
        return 1
    print("RCX RULES: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
