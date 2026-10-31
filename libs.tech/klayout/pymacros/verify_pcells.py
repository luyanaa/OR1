#!/usr/bin/env python3
"""Round-trip and rule-conformance check for the OR1 PCell library.

    klayout -b -r verify_pcells.py

1. builds every PCell test case (same list as test_pcells.py),
2. writes the GDS,
3. re-reads it and compares per-cell shape counts and bounding boxes,
4. reports PASS/FAIL.

A cell that displays correctly in the GUI but loses geometry on export is a
failure here.
"""
import os
import sys
import tempfile

import pya

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "."
sys.path.insert(0, HERE)
import or1_pcells  # noqa: F401

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


def build():
    ly = pya.Layout()
    ly.dbu = 0.001
    top = ly.create_cell("pcell_top")
    for name, pc, params in CASES:
        c = ly.create_cell(pc, "or1_pcells", params)
        c.name = name
        top.insert(pya.CellInstArray(c.cell_index(), pya.Trans()))
    return ly


def signature(ly, name):
    c = ly.cell(name)
    b = c.dbbox()
    n = sum(c.shapes(li).size() for li in range(ly.layers()))
    return (round(b.left, 3), round(b.bottom, 3), round(b.right, 3),
            round(b.top, 3), n)


def main():
    sys.setrecursionlimit(10000)
    ly = build()
    fd, path = tempfile.mkstemp(suffix=".gds")
    os.close(fd)
    try:
        ly.write(path)
        back = pya.Layout()
        back.read(path)
        ok = True
        for name, _, _ in CASES:
            a = signature(ly, name)
            b = signature(back, name)
            if a != b:
                ok = False
                print("FAIL %-12s before=%s after=%s" % (name, a, b))
            else:
                print("ok   %-12s bbox=%s shapes=%d" % (name, a[:4], a[4]))
        print("ROUND-TRIP:", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        os.unlink(path)


if __name__ == "__main__":
    sys.exit(main())
