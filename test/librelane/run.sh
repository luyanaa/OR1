#!/usr/bin/env bash
# Reproduce the OR1 librelane smoke test (counter: 4x DFFPOSX1 + 14 gates).
#
#   ./run.sh [/path/to/OR1PDK]
#
# Expected result: Antenna / LVS / DRC all "Passed".
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
pdk_root="${1:-$(cd "$here/../../../.." && pwd)}"
cd "$here"

exec librelane --manual-pdk --pdk or1 --pdk-root "$pdk_root" \
    --skip OpenROAD.CheckAntennas-1 \
    --skip OpenROAD.FillInsertion \
    --skip KLayout.XOR \
    config.yaml
