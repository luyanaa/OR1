#!/bin/sh
# OR1 KLayout LVS wrapper.
#
#   run_lvs.sh <layout.gds> <top-cell> <reference.cdl> [<out-prefix>]
#
# librelane's KLayout.LVS step in this build is hard-coded for the IHP PDKs,
# so the OR1 LVS deck is invoked through this wrapper (same contract).
set -e
GDS=$1; TOP=$2; REF=$3; OUT=${4:-/tmp/or1_lvs}
HERE=$(cd "$(dirname "$0")" && pwd)
klayout -b -zz -r "$HERE/OR1.lvs" \
    -rd input="$GDS" -rd topcell="$TOP" \
    -rd schematic="$REF" \
    -rd report="${OUT}.lvsdb" \
    -rd target_netlist="${OUT}.spice"
