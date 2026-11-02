#!/bin/sh
# One-command PCell sign-off: geometry/DRC + device LVS, with a JSON record.
#
#   libs.tech/klayout/pymacros/check_pcells_all.sh [report-dir]
#
# Runs check_pcells.sh (build the PCell test layout, presence check, official
# DRC per cell) and test_lvs_devices.sh (KLayout LVS + netgen device checks,
# parameter values, tap connectivity, negative controls), then writes
# signoff.json into the report directory and exits non-zero on any failure.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
PDK=$(cd "$HERE/../../.." && pwd)
OUT=${1:-/tmp/or1_pcell_signoff}
mkdir -p "$OUT"

echo "== geometry / DRC =="
set +e
"$HERE/check_pcells.sh" "$OUT/drc" > "$OUT/drc.log" 2>&1
drc_rc=$?
echo "== device LVS =="
"$HERE/../lvs/test_lvs_devices.sh" "$OUT/lvs" > "$OUT/lvs.log" 2>&1
lvs_rc=$?
set -e

python3 - "$OUT" "$drc_rc" "$lvs_rc" "$PDK" <<'PY'
import json, os, re, subprocess, sys
from datetime import datetime, timezone

out, drc_rc, lvs_rc, pdk = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
drc = open(os.path.join(out, "drc.log")).read()
lvs = open(os.path.join(out, "lvs.log")).read()

cells = {}
for line in drc.splitlines():
    m = re.match(r"^(\S+)\s+drc=(\S+)$", line.strip())
    if m:
        cells[m.group(1)] = m.group(2)

# keep every check: a cell appears twice (positive check and negative control),
# so a dict keyed by name would hide the positive result
devices = []
for line in lvs.splitlines():
    m = re.match(r"^(\S+)\s+(match|MISMATCH|ok|FAIL)\b(.*)$", line.strip())
    if m:
        devices.append({"check": m.group(1), "result": m.group(2),
                        "note": m.group(3).strip(" ()")})

try:
    commit = subprocess.run(["git", "-C", pdk, "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
except Exception:
    commit = None

record = {
    "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "pdk_commit": commit,
    "drc": {"exit": drc_rc, "cells": cells,
            "pass": drc_rc == 0 and all(v == "0" for v in cells.values())},
    "lvs": {"exit": lvs_rc, "devices": devices,
            "pass": lvs_rc == 0},
    "overall_pass": drc_rc == 0 and lvs_rc == 0,
}
json.dump(record, open(os.path.join(out, "signoff.json"), "w"), indent=2)
print(json.dumps({"drc_cells": len(cells), "drc_pass": record["drc"]["pass"],
                  "lvs_checks": len(devices), "lvs_pass": record["lvs"]["pass"],
                  "overall_pass": record["overall_pass"]}, indent=2))
sys.exit(0 if record["overall_pass"] else 1)
PY
