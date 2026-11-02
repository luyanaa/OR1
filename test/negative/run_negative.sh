#!/bin/sh
# Negative regression: the checks must FAIL on bad input.
#   1) DRC must report the 0.5 um metal1 space
#   2) netgen must reject a reference with the wrong device W
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
PDK=$(cd "$HERE/../.." && pwd)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/or1neg.XXXXXX"); trap 'rm -rf "$TMP"' EXIT

klayout -b -r "$HERE/gen_negative.py" > /dev/null
klayout -b -r "$PDK/libs.tech/klayout/drc/OR1.drc" -rd input=/tmp/neg_ml1.gds \
        -rd topcell=NEG_ML1_SPACE -rd report="$TMP/neg.lyrdb" > /dev/null 2>&1 || true
n=$(grep -c '<item>' "$TMP/neg.lyrdb" || true)
[ "$n" -gt 0 ] || { echo "FAIL: DRC did not flag the metal1 space violation"; exit 1; }
echo "ok: DRC rejected the metal1 space violation ($n items)"

GDS="$PDK/libs.ref/or1_fd_sc/gds/or1_fd_sc.gds"
CDL="$PDK/libs.ref/or1_fd_sc/cdl/or1_fd_sc.cdl"
klayout -b -zz -r "$PDK/libs.tech/klayout/lvs/OR1.lvs" -rd input="$GDS" \
        -rd topcell=INVX1 -rd target_netlist="$TMP/ext.spice" > /dev/null 2>&1
sed 's/w=6u l=1u/w=5u l=1u/' "$CDL" > "$TMP/bad.cdl"
if netgen -batch lvs "$TMP/ext.spice INVX1" "$TMP/bad.cdl INVX1" \
        "$PDK/libs.tech/netgen/OR1_setup.tcl" "$TMP/ng.log" > /dev/null 2>&1; then
    :
fi
if grep -q "property errors\|do not match" "$TMP/ng.log"; then
    echo "ok: netgen rejected the wrong device width"
else
    echo "FAIL: netgen accepted a reference with w=5u instead of 6u"
    exit 1
fi
echo "NEGATIVE TESTS: PASS"
