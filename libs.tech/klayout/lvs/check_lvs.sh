#!/bin/sh
# LVS closure check for every cell that has a CDL subcircuit.
#   libs.tech/klayout/lvs/check_lvs.sh [report-dir]
# Runs the KLayout LVS deck and netgen (with W/L comparison) per cell.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
PDK=$(cd "$HERE/../../.." && pwd)
OUT=${1:-/tmp/or1_lvs_reports}
GDS="$PDK/libs.ref/or1_fd_sc/gds/or1_fd_sc.gds"
CDL="$PDK/libs.ref/or1_fd_sc/cdl/or1_fd_sc.cdl"
SETUP="$PDK/libs.tech/netgen/OR1_setup.tcl"
mkdir -p "$OUT"

CELLS=$(grep -i '^\.subckt' "$CDL" | awk '{print $2}')
printf '%-12s %-10s %-8s\n' cell klayout netgen
bad=0
for c in $CELLS; do
    # 1) KLayout LVS against the CDL
    klayout -b -zz -r "$HERE/OR1.lvs" -rd input="$GDS" -rd topcell="$c" \
            -rd schematic="$CDL" -rd report="$OUT/$c.lvsdb" \
            > "$OUT/$c.klayout.log" 2>&1 || true
    # 2) separate extraction run (no schematic) for the netgen arm
    klayout -b -zz -r "$HERE/OR1.lvs" -rd input="$GDS" -rd topcell="$c" \
            -rd target_netlist="$OUT/$c.spice" > /dev/null 2>&1 || true
    if grep -q "Netlists match" "$OUT/$c.klayout.log"; then k=pass; else k=FAIL; bad=1; fi
    if ! grep -q "^M" "$OUT/$c.spice" 2>/dev/null; then
        n=n/a
    elif netgen -batch lvs "$OUT/$c.spice $c" "$CDL $c" "$SETUP" "$OUT/$c.netgen.log" >/dev/null 2>&1; then
        if grep -q "Circuits match" "$OUT/$c.netgen.log"; then n=pass; else n=FAIL; bad=1; fi
    else
        n=FAIL; bad=1
    fi
    printf '%-12s %-10s %-8s\n' "$c" "$k" "$n"
done
echo "LVS: $([ $bad -eq 0 ] && echo PASS || echo FAIL)  reports in $OUT"
exit $bad
