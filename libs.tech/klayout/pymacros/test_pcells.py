#!/usr/bin/env python3
"""Self-test for the OR1 KLayout PCell library.

    klayout -b -r test_pcells.py

Builds one instance of every PCell (plus parameter variants) into
/tmp/or1_pcells_test.gds and prints the cell names.  Run the OR1 DRC deck on
each cell afterwards (see README.md).
"""
import os
import sys
import pya

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "."
sys.path.insert(0, HERE)
import or1_pcells  # noqa: F401  (registers the "or1_pcells" library)

ly = pya.Layout()
ly.dbu = 0.001
top = ly.create_cell("pcell_top")

CASES = [
    ("T_CNT_DIFF",  "OR1_CONTACT", {"on": "diff", "cols": 3, "rows": 2}),
    ("T_CNT_POLY",  "OR1_CONTACT", {"on": "poly", "cols": 2, "rows": 2}),
    ("T_VIA1",      "OR1_VIA",     {"cut": "via1", "cols": 2, "rows": 2}),
    ("T_VIA2",      "OR1_VIA",     {"cut": "via2", "cols": 3, "rows": 3}),
    ("T_PAD",       "OR1_PAD",     {"size": 12.0}),
    ("T_MOSN1",     "OR1_MOS",     {"type": "n", "w": 4.0, "l": 1.0, "nf": 1}),
    ("T_MOSN4",     "OR1_MOS",     {"type": "n", "w": 4.0, "l": 1.0, "nf": 4}),
    ("T_MOSP2",     "OR1_MOS",     {"type": "p", "w": 6.0, "l": 1.0, "nf": 2}),
    ("T_MOSNTIE0",  "OR1_MOS",     {"type": "n", "w": 2.0, "l": 2.0, "nf": 1,
                                    "body_tie": "none", "gate_contact": False}),
    ("T_MOSVIA",    "OR1_MOS",     {"type": "n", "w": 4.0, "l": 1.0, "nf": 2,
                                    "with_via": True}),
    ("T_GUARDN",    "OR1_MOSGUARD", {"type": "n", "w": 4.0, "l": 1.0, "nf": 1}),
    ("T_GUARDP",    "OR1_MOSGUARD", {"type": "p", "w": 4.0, "l": 1.0, "nf": 2}),
    ("T_RES",       "OR1_RES",     {"w": 2.0, "l": 10.0}),
    ("T_HRES",      "OR1_RES",     {"w": 2.0, "l": 30.0, "hr": True}),
    ("T_DRESN",     "OR1_DIFFRES", {"type": "n", "w": 2.0, "l": 10.0}),
    ("T_DRESP",     "OR1_DIFFRES", {"type": "p", "w": 2.0, "l": 10.0}),
    ("T_DIODE",     "OR1_DIODE", {"w": 6.0, "h": 4.0}),
    ("T_MOSCAP",    "OR1_MOSCAP", {"w": 6.0, "h": 4.0, "l": 2.0}),
    ("T_MATCH",     "OR1_MOSMATCH", {"type": "n", "w": 4.0, "l": 1.0, "nf": 1, "gap": 1.5}),
    ("T_RESARR",    "OR1_RESARRAY", {"w": 2.0, "l": 8.0, "count": 3}),
    ("T_CAPARR",    "OR1_CAPARRAY", {"w": 6.0, "h": 4.0, "l": 2.0, "cols": 2, "rows": 2}),
    ("T_ESD",       "OR1_ESD",      {"w": 4.0, "l": 1.0, "fingers": 4}),
    ("T_RINGP",     "OR1_RING",    {"type": "p", "w": 20.0, "h": 20.0, "t": 2.0}),
    ("T_RINGN",     "OR1_RING",    {"type": "n", "w": 20.0, "h": 20.0, "t": 2.0}),
    ("T_LINEP",     "OR1_TAPLINE", {"type": "p", "length": 20.0, "width": 2.0}),
    ("T_LINEN",     "OR1_TAPLINE", {"type": "n", "length": 20.0, "width": 2.0}),
]

names = []
for name, pc, params in CASES:
    c = ly.create_cell(pc, "or1_pcells", params)
    c.name = name
    names.append(name)
    top.insert(pya.CellInstArray(c.cell_index(), pya.Trans()))

# Parameter sweep (OR1_PCELL_SWEEP=1): every numeric parameter is also drawn at
# its clamping bound (a tiny value) and at 3x the nominal value (a large one),
# so the DRC gate covers the coerce_parameters_impl limits, not just one point.
if os.environ.get("OR1_PCELL_SWEEP"):
    for name, pc, params in CASES:
        for key, value in params.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            for tag, probe in (("lo", 0.1), ("hi", max(value * 3.0, 3.0))):
                variant = dict(params)
                variant[key] = int(probe) if isinstance(value, int) else probe
                cname = "%s__%s_%s" % (name, key, tag)
                try:
                    c = ly.create_cell(pc, "or1_pcells", variant)
                except Exception:
                    continue
                c.name = cname
                names.append(cname)
                top.insert(pya.CellInstArray(c.cell_index(), pya.Trans()))

out = os.environ.get("OR1_PCELL_TEST_GDS", "/tmp/or1_pcells_test.gds")
ly.write(out)
print("wrote %s" % out)
print("cells: " + " ".join(names))
