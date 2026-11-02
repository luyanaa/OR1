"""Fail if any PCell test cell is empty (catches silent produce_impl errors)."""
import os
import sys
import pya

GDS = None
for arg in sys.argv[1:]:
    if arg.startswith("gds="):
        GDS = arg[4:]
GDS = GDS or os.environ.get("OR1_PCELL_TEST_GDS", "/tmp/or1_pcells_test.gds")

ly = pya.Layout()
ly.read(GDS)
bad = 0
for c in sorted(ly.each_cell(), key=lambda x: x.name):
    if c.name.startswith("pcell_"):
        continue
    n = sum(c.shapes(li).size() for li in range(ly.layers()))
    if n == 0:
        print("EMPTY %s" % c.name)
        bad = 1
print("GEOMETRY:", "PASS" if not bad else "FAIL")
sys.exit(bad)
