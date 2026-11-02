#!/usr/bin/env python3
"""Emit a machine-readable sign-off record for one librelane run.

    python3 test/librelane/signoff_record.py \
        [runs/RUN_.../] > test/librelane/signoff.json

Only reads files the flow already wrote (metrics.csv, step reports, final
GDS/SPEF), plus the tool versions found on PATH.  The point is to make
regressions visible: compare the JSON between runs instead of "the flow exited
0".
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

REPO = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))


def sh(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception:
        return None


def read_metrics(run):
    path = os.path.join(run, "final", "metrics.csv")
    values = {}
    if not os.path.exists(path):
        return values
    with open(path) as fh:
        for line in fh:
            if "," not in line:
                continue
            k, v = line.strip().split(",", 1)
            values[k] = v
    return values


def num(values, key, default=None):
    v = values.get(key, default)
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def read_text(path):
    try:
        with open(path, errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""


def drt_violations(run):
    """Final detailed-route violation count (last iteration in the log)."""
    for name in sorted(os.listdir(run)):
        if "detailedrouting" not in name:
            continue
        log = read_text(os.path.join(run, name, "openroad-detailedrouting.log"))
        hits = re.findall(r"Number of violations = (\d+)", log)
        if hits:
            return int(hits[-1])
    p = os.path.join(run, "38-openroad-detailedrouting", "counter.drc")
    return len([l for l in read_text(p).splitlines() if l.strip()])


def grt_overflow(run):
    """Total congestion from the final GRT congestion report (None if absent)."""
    for name in sorted(os.listdir(run)):
        if "globalrouting" not in name:
            continue
        log = read_text(os.path.join(run, name, "openroad-globalrouting.log"))
        m = re.search(r"Total Congestion\s*\n[^\n]*\n[^\n]*?(\d+)\s*$", log, re.M)
        if m:
            return int(m.group(1))
        # fallback: the worst per-layer "Max H / Max V / Total" row
        vals = re.findall(r"^\s*\S+\s+\d+\s+\d+\s+[\d.]+\s+(\d+)\s+(\d+)\s+(\d+)\s*$", log, re.M)
        if vals:
            return max(int(v[2]) for v in vals)
    return None


def unrouted(run):
    for name in sorted(os.listdir(run)):
        if "detailedrouting" not in name:
            continue
        log = read_text(os.path.join(run, name, "openroad-detailedrouting.log"))
        m = re.search(r"(\d+)\s+(?:nets?\s+)?(?:are\s+)?unrouted", log, re.I)
        if m:
            return int(m.group(1))
        if re.search(r"all nets routed", log, re.I):
            return 0
        if re.search(r"Number of violations = 0", log):
            return 0
    return None


def disconnected_pins(run):
    """(total, critical) from the flow's report-disconnected-pins step."""
    for name in sorted(os.listdir(run)):
        if "reportdisconnectedpins" not in name:
            continue
        log = read_text(os.path.join(run, name, "odb-reportdisconnectedpins.log"))
        m = re.search(r"Found (\d+) disconnected pin\(s\), of which (\d+) are critical",
                      log)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None, None


def spef_totals(run):
    path = os.path.join(run, "final", "spef", "tt", "counter.tt.spef")
    txt = read_text(path)
    if not txt:
        return {}
    r = [float(m.group(1)) for m in re.finditer(r"^\s*\d+\s+\S+\s+\S+\s+([\d.eE+-]+)", txt, re.M)]
    # SPEF: *RES sections list "<id> <node> <node> <value>"; *CAP similar
    res_total = sum(float(m.group(1)) for m in
                    re.finditer(r"^\s*\d+\s+\S+\s+\S+\s+([\d.eE+-]+)\s*$", txt, re.M))
    caps = [float(m.group(1)) for m in
            re.finditer(r"^\s*\d+\s+\S+\s+([\d.eE+-]+)\s*$", txt, re.M)]
    return {
        "spef_file": path,
        "spef_lines": len(txt.splitlines()),
        "spef_resistance_entries": len(r),
        "spef_capacitance_entries": len(caps),
        "spef_total_capacitance_pf": round(sum(caps), 6),
    }


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    run = sys.argv[1] if len(sys.argv) > 1 else None
    if run is None:
        runs = os.path.join(REPO, "test", "librelane", "runs")
        cands = sorted((os.path.join(runs, d) for d in os.listdir(runs)
                        if d.startswith("RUN_")), key=os.path.getmtime)
        run = cands[-1]
    run = os.path.realpath(run)
    m = read_metrics(run)
    commit = sh(["git", "-C", REPO, "rev-parse", "HEAD"])
    dirty = sh(["git", "-C", REPO, "status", "--porcelain"]) or ""

    gds = os.path.join(run, "final", "gds", "counter.gds")
    checks = {
        "klayout_drc": int(float(m.get("klayout__drc_error__count", -1))),
        "magic_drc": int(float(m.get("magic__drc_error__count", -1))),
        "lvs_errors": int(float(m.get("design__lvs_error__count", -1))),
        "lvs_unmatched_devices": int(float(m.get("design__lvs_unmatched_device__count", -1))),
        "lvs_unmatched_nets": int(float(m.get("design__lvs_unmatched_net__count", -1))),
        "lvs_unmatched_pins": int(float(m.get("design__lvs_unmatched_pin__count", -1))),
        "max_slew_violations": int(float(m.get("design__max_slew_violation__count", -1))),
        "max_cap_violations": int(float(m.get("design__max_cap_violation__count", -1))),
        "max_fanout_violations": int(float(m.get("design__max_fanout_violation__count", -1))),
    }
    timing = {
        "corner": "nom_tt_5P0_25C",
        "setup_ws_ns": num(m, "timing__setup__ws"),
        "hold_ws_ns": num(m, "timing__hold__ws"),
        "setup_violations": int(float(m.get("timing__setup_vio__count", -1))),
        "hold_violations": int(float(m.get("timing__hold_vio__count", -1))),
        "setup_tns_ns": num(m, "timing__setup__tns"),
        "hold_tns_ns": num(m, "timing__hold__tns"),
    }
    design = {
        "instance_count": int(float(m.get("design__instance__count", -1))),
        "stdcell_instances": int(float(m.get("design__instance__count__stdcell", -1))),
        "stdcell_area_um2": num(m, "design__instance__area__stdcell"),
        "utilization": num(m, "design__instance__utilization"),
        "die_area_um2": num(m, "design__die__area"),
        "core_area_um2": num(m, "design__core__area"),
    }
    disc_total, disc_critical = disconnected_pins(run)
    pdn = {
        "vdd_grid_error_lines": len([l for l in read_text(os.path.join(
            run, "17-openroad-generatepdn", "vdd-grid-errors.rpt")).splitlines() if l.strip()]),
        "gnd_grid_error_lines": len([l for l in read_text(os.path.join(
            run, "17-openroad-generatepdn", "gnd-grid-errors.rpt")).splitlines() if l.strip()]),
        "ir_drop_report": "not run (RUN_IRDROP_REPORT: false)",
    }
    record = {
        "design": "counter",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git": {"commit": commit, "dirty": bool(dirty.strip())},
        "tools": {
            "librelane": sh(["librelane", "--version"]),
            "openroad": sh(["bash", "-lc",
                            "ls -d /nix/store/*openroad-*/bin/openroad 2>/dev/null | head -1"]) or None,
            "klayout": sh(["klayout", "-v"]),
            "magic": sh(["magic", "--version"]),
            "ngspice": sh(["ngspice", "--version"]),
        },
        "pdk": {
            "name": "OR1",
            "corner": "nom_tt_5P0_25C",
            "supply_v": 5.0,
            "library": "libs.ref/or1_fd_sc/lib/or1_fd_sc_TT_5P0_25C.lib",
        },
        "run": run,
        "design_metrics": design,
        "routing": {
            "grt_max_overflow": grt_overflow(run),
            "drt_violation_lines": drt_violations(run),
            "unrouted_nets": unrouted(run),
        },
        "checks": checks,
        "timing": timing,
        "pdn": pdn,
        "connectivity": {
            "disconnected_pins_total": disc_total,
            "disconnected_pins_critical": disc_critical,
            "note": "ERROR_ON_DISCONNECTED_PINS is false; this is the independent count",
        },
        "extraction": spef_totals(run),
        "gds": {"path": gds, "sha256": sha256(gds) if os.path.exists(gds) else None},
    }
    json.dump(record, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
