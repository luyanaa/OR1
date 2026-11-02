#!/bin/sh
# Device-level LVS check for the OR1 passive PCells.
#
#   libs.tech/klayout/lvs/test_lvs_devices.sh [report-dir]
#
# Builds a labeled copy of the PCell test layout, writes the reference
# netlists for the passive devices and runs the KLayout LVS deck + netgen on
# each one.  Also runs negative controls (missing device, wrong polarity) that
# MUST fail - if any of them "matches", the comparison is not doing its job.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
PDK=$(cd "$HERE/../../.." && pwd)
OUT=${1:-/tmp/or1_lvs_devices}
GDS=${OR1_PCELL_TEST_GDS:-/tmp/or1_pcells_test.gds}
SETUP="$PDK/libs.tech/netgen/OR1_setup.tcl"
mkdir -p "$OUT"

if [ ! -f "$GDS" ]; then
    echo "missing $GDS - run libs.tech/klayout/pymacros/test_pcells.py first"
    exit 1
fi

# --- labeled copy: LVS needs named nets on the device terminals -------------
cat > "$OUT/label_devices.py" <<'PY'
import pya
ly = pya.Layout()
ly.read("/tmp/or1_pcells_test.gds")
m1 = ly.layer(8, 0)
def lbl(cell, s, x, y):
    ly.cell(cell).shapes(m1).insert(
        pya.Text(s, pya.Trans(pya.Point(int(x * 1000), int(y * 1000)))))
lbl("T_RES",    "A", 1.0, 1.0); lbl("T_RES",    "B", 9.0, 1.0)
lbl("T_DRESN",  "A", 1.0, 1.0); lbl("T_DRESN",  "B", 9.0, 1.0)
lbl("T_DRESP",  "A", 1.0, 1.0); lbl("T_DRESP",  "B", 9.0, 1.0)
lbl("T_DIODE",  "A", 3.0, 2.0); lbl("T_DIODE",  "C", 3.0, -2.5)
lbl("T_MOSCAP", "A", 3.0, 6.0); lbl("T_MOSCAP", "B", 1.0, 2.0)

# broken variants of the resistor: the deck must flag both
def variant(name, short=False, open_=False):
    dst = ly.create_cell(name)
    dst.copy_tree(ly.cell("T_RES"))
    if open_:
        # remove the right-hand contact: the resistor loses one terminal
        # (removing only the metal pad is not an open - the label and the
        # device terminal still sit on the contact)
        cs = dst.shapes(ly.layer(7, 0))
        for sh in list(cs.each()):
            if not sh.is_text() and sh.bbox() == pya.Box(8500, 500, 9500, 1500):
                cs.erase(sh)
    shapes = dst.shapes(m1)
    if short:
        shapes.insert(pya.Box(0, 0, 10000, 2000))
variant("NEG_OPEN", open_=True)
variant("NEG_SHORT", short=True)
ly.write("/tmp/or1_lvs_devices.gds")
PY
klayout -b -r "$OUT/label_devices.py" > /dev/null 2>&1
LGDS=/tmp/or1_lvs_devices.gds

# --- reference netlists -----------------------------------------------------
# The resistance follows from the drawn geometry (see the sheet resistance of
# each extractor in OR1.lvs); the values below are the ones the PCell defaults
# (2 x 10 um body, 2 um metal heads) produce - 3 squares.
cat > "$OUT/reference.cdl" <<'EOF'
* OR1 passive device reference (device-level LVS)
.subckt T_RES A B
R1 A B 60 POLYRES
.ends

.subckt T_DRESN A B
R1 A B 126 NDIFFRES
.ends

.subckt T_DRESP A B
R1 A B 126 PDIFFRES
.ends

.subckt T_DIODE A C
D1 A C PDIO
.ends

.subckt T_MOSCAP A B
C1 A B 8e-15 MOSCAP
.ends
EOF

run() {  # run <cell> <reference> -> echoes match/mismatch
    klayout -b -zz -r "$HERE/OR1.lvs" -rd input="$LGDS" -rd topcell="$1" \
            -rd schematic="$2" -rd report="$OUT/$3.lvsdb" \
            > "$OUT/$3.log" 2>&1 || true
    if grep -q "Congratulations" "$OUT/$3.log"; then echo match; else echo MISMATCH; fi
}

printf '%-12s %-10s\n' device klayout
bad=0
for c in T_RES T_DRESN T_DRESP T_MOSCAP; do
    r=$(run "$c" "$OUT/reference.cdl" "pos_$c")
    printf '%-12s %-10s\n' "$c" "$r"
    [ "$r" = match ] || bad=1
done

# diode: not extracted by this deck (see OR1.lvs / STATUS section 24)
r=$(run T_DIODE "$OUT/reference.cdl" "pos_T_DIODE")
printf '%-12s %-10s (not extracted, not gating)\n' T_DIODE "$r"

# --- negative controls ------------------------------------------------------
# 1) reference misses a device
cat > "$OUT/neg_missing.cdl" <<'EOF'
.subckt T_MOSCAP A B
.ends
EOF
# 2) reference uses a wrong device type (a wrong device *count* is not usable:
#    combine_devices merges series/parallel resistors of the same class)
cat > "$OUT/neg_extra.cdl" <<'EOF'
.subckt T_RES A B
R1 A B 60 POLYRES
C1 A B 1e-15 MOSCAP
.ends
EOF
# 3+4) broken *layouts*: one metal head removed (open), pads shorted
cat > "$OUT/neg_layout.cdl" <<'EOF'
.subckt NEG_OPEN A B
R1 A B 60 POLYRES
.ends
.subckt NEG_SHORT A B
R1 A B 60 POLYRES
.ends
EOF
for spec in "T_MOSCAP $OUT/neg_missing.cdl neg_missing" \
            "T_RES $OUT/neg_extra.cdl neg_extra" \
            "NEG_OPEN $OUT/neg_layout.cdl neg_open" \
            "NEG_SHORT $OUT/neg_layout.cdl neg_short"; do
    set -- $spec
    r=$(run "$1" "$2" "$3")
    printf '%-12s %-10s (negative control, must MISMATCH)\n' "$1" "$r"
    [ "$r" = MISMATCH ] || bad=1
done

echo "DEVICE LVS: $([ $bad -eq 0 ] && echo PASS || echo FAIL)  reports in $OUT"
exit $bad
