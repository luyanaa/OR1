#!/bin/sh
# PCell acceptance check: geometry presence + official DRC per cell.
#   libs.tech/klayout/pymacros/check_pcells.sh [report-dir]
# Exits non-zero if any cell is empty or has DRC violations.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
KLAYOUT_DIR=$(cd "$HERE/.." && pwd)
OUT=${1:-/tmp/or1_pcell_reports}
GDS=${OR1_PCELL_TEST_GDS:-/tmp/or1_pcells_test.gds}
mkdir -p "$OUT"

klayout -b -r "$HERE/test_pcells.py" > "$OUT/build.log" 2>&1
CELLS=$(sed -n 's/^cells: //p' "$OUT/build.log")

klayout -b -r "$HERE/geometry_check.py" -rd gds="$GDS" > "$OUT/geometry.txt" 2>&1
if ! grep -q "GEOMETRY: PASS" "$OUT/geometry.txt"; then
    echo "PCell geometry check FAILED"; cat "$OUT/geometry.txt"; exit 1
fi

bad=0
for c in $CELLS; do
    klayout -b -r "$KLAYOUT_DIR/drc/OR1.drc" -rd input="$GDS" -rd topcell="$c" \
            -rd report="$OUT/$c.lyrdb" > /dev/null 2>&1 || true
    if [ -f "$OUT/$c.lyrdb" ]; then
        n=$(grep -c '<item>' "$OUT/$c.lyrdb" 2>/dev/null) || n=0
    else
        n=missing
    fi
    printf '%-14s drc=%s\n' "$c" "$n"
    [ "$n" = "0" ] || bad=1
done
echo "DRC: $([ $bad -eq 0 ] && echo PASS || echo FAIL)  reports in $OUT"
exit $bad
