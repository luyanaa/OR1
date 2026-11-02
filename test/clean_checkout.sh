#!/usr/bin/env bash
# Clean-checkout reproducibility check for the OR1 counter flow.
#
#   ./test/clean_checkout.sh          # structural check only (seconds)
#   ./test/clean_checkout.sh --run    # also run the flow and gate on the results
#
# The archive is taken from `git archive HEAD`, i.e. exactly what a fresh
# `git clone` gives: ignored files (runs/, *.cfg, backups) are NOT present.
# A previous bug (macro_placement.cfg ignored by *.cfg) only showed up here.
set -euo pipefail

REPO="$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/or1_clean.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/OR1"

echo "[1/4] extracting git archive HEAD -> $TMP/OR1"
git -C "$REPO" archive HEAD | tar -x -C "$TMP/OR1"

echo "[2/4] checking that every file the flow references is committed"
missing=0
for f in \
  test/librelane/config.yaml \
  test/librelane/macro_placement.cfg \
  test/librelane/counter.v \
  test/librelane/run.sh \
  libs.tech/librelane/config.tcl \
  libs.tech/librelane/or1_fd_sc/config.tcl \
  libs.tech/klayout/drc/OR1.drc \
  libs.tech/klayout/lvs/OR1.lvs \
  libs.tech/klayout/tech/OR1.map \
  libs.ref/or1_fd_sc/gds/or1_fd_sc.gds \
  libs.ref/or1_fd_sc/lef/OR1.tlef \
  libs.ref/or1_fd_sc/lef/or1_fd_sc.lef \
  libs.ref/or1_fd_sc/lib/or1_fd_sc_TT_5P0_25C.lib ; do
  if [ ! -f "$TMP/OR1/$f" ]; then
    echo "  MISSING: $f"
    missing=1
  fi
done
if [ "$missing" -ne 0 ]; then
  echo "FAIL: the flow references files that are not in a clean checkout"
  exit 1
fi

echo "[3/4] checking that no 3.3 V profile leaks into the flow config"
if grep -rn "3P3\|VDD_PIN_VOLTAGE) \"3" "$TMP/OR1/libs.tech/librelane" >/dev/null ; then
  echo "FAIL: 3.3 V corner still referenced by the PDK flow config"
  grep -rn "3P3\|VDD_PIN_VOLTAGE) \"3" "$TMP/OR1/libs.tech/librelane" || true
  exit 1
fi

echo "[4/4] structural check OK"

if [ "${1:-}" != "--run" ]; then
  echo "PASS (structural).  Use --run to run the flow from the clean copy."
  exit 0
fi

echo "[run] librelane from the clean checkout (pdk-root $TMP)"
cd "$TMP/OR1/test/librelane"
librelane --manual-pdk --pdk OR1 --pdk-root "$TMP" \
  --skip OpenROAD.CheckAntennas-1 --skip KLayout.XOR config.yaml

RUN="$(ls -td "$TMP"/OR1/test/librelane/runs/RUN_* | head -1)"
echo "[verify] $RUN"
python3 - "$RUN" <<'PY'
import sys, os
run = sys.argv[1]
def metric(name):
    for line in open(os.path.join(run, "final", "metrics.csv")):
        k, v = line.strip().split(",", 1)
        if k == name:
            return v
    return None
checks = {
    "klayout__drc_error__count": "0",
    "magic__drc_error__count": "0",
    "design__lvs_error__count": "0",
    "timing__setup_vio__count": "0",
    "timing__hold_vio__count": "0",
}
bad = []
for k, want in checks.items():
    got = metric(k)
    print(f"  {k} = {got}")
    if got != want:
        bad.append(k)
if bad:
    raise SystemExit("FAIL: " + ", ".join(bad))
print("PASS: clean checkout reproduces DRC 0 / LVS 0 / no timing violations")
PY
