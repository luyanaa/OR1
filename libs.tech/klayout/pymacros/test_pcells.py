#!/usr/bin/env python3
"""Self-test for the OR1 KLayout PCell library.

    klayout -b -r test_pcells.py

Builds one instance of every PCell into /tmp/or1_pcells_test.gds.
Run the OR1 DRC deck on each cell afterwards (see README.md).
"""
import os
import pya

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "."
import sys
sys.path.insert(0, HERE)
import or1_pcells  # noqa: F401  (registers the "or1_pcells" library)

ly = pya.Layout()
ly.dbu = 0.001
top = ly.create_cell("pcell_top")

CASES = [
    ("T_VIA1", "OR1_VIA", {"cut": "via1", "cols": 2, "rows": 2}),
    ("T_VIA2", "OR1_VIA", {"cut": "via2", "cols": 3, "rows": 3}),
    ("T_PAD",  "OR1_PAD", {"size": 12.0, "via_pitch": 2.0}),
    ("T_MOSN", "OR1_MOS", {"type": "n", "w": 4.0, "l": 1.0, "sd": 2.0}),
    ("T_MOSP", "OR1_MOS", {"type": "p", "w": 4.0, "l": 1.0, "sd": 2.0}),
    ("T_RES",  "OR1_RES", {"w": 2.0, "l": 10.0}),
]

for name, pc, params in CASES:
    c = ly.create_cell(pc, "or1_pcells", params)
    c.name = name
    top.insert(pya.CellInstArray(c.cell_index(), pya.Trans()))

out = os.environ.get("OR1_PCELL_TEST_GDS", "/tmp/or1_pcells_test.gds")
ly.write(out)
print("wrote %s: %s" % (out, [c.name for c in ly.each_cell()]))
