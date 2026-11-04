#!/usr/bin/env python3
"""Split the OR1 std-cell CDL into one per-cell SPICE netlist.

Usage:
    python3 cdl_to_spice.py <or1_fd_sc.cdl> <outdir>

Each .subckt/.ends block in the CDL is written as <outdir>/<CELL>.spice with
the port list preserved as a plain .subckt header (no VDD/VSS reshuffling:
the ngspice decks that include these files map the pins themselves).  Only
MOSFET lines are kept, and SPICE continuation lines ('+') are merged back
into the M line they belong to - the same convention or1_char.py's
load_cell() expects.  Blocks without any device line (FILL/TAP/...) still
get a file containing a marker comment so the split is auditable.
"""
import os
import re
import sys


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: cdl_to_spice.py <cdl> <outdir>")
    cdl_path, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)

    # Collect lines into subckt blocks.
    blocks = []          # list of (name, [lines])
    current = None
    for raw in open(cdl_path):
        line = raw.rstrip("\n")
        s = line.strip()
        low = s.lower()
        if low.startswith(".subckt"):
            if current is not None:
                raise SystemExit("nested .subckt at %s" % low)
            name = s.split()[1].upper()
            current = (name, [s])
        elif low.startswith(".ends"):
            if current is None:
                raise SystemExit(".ends without .subckt at %s" % low)
            blocks.append(current)
            current = None
        elif current is not None:
            current[1].append(s)
    if current is not None:
        raise SystemExit("unterminated .subckt %s" % current[0])

    for name, lines in blocks:
        out_lines = []
        for s in lines:
            if s.startswith("+"):
                # continuation: merge into the previous device line
                if out_lines:
                    out_lines[-1] += " " + s[1:].strip()
                continue
            if s.startswith("M") or s.lower().startswith(".subckt"):
                out_lines.append(s)
        header = out_lines[0]  # the .subckt line
        mlines = [l for l in out_lines[1:]]
        path = os.path.join(outdir, name + ".spice")
        with open(path, "w") as f:
            f.write("* %s: split from %s (M lines only)\n" % (name,
                                                             os.path.basename(cdl_path)))
            f.write(header + "\n")
            if not mlines:
                f.write("* (no M lines: non-device cell)\n")
            for l in mlines:
                f.write(l + "\n")
            f.write(".ends %s\n" % name)
        print("%-10s %d M lines -> %s" % (name, len(mlines), path))


if __name__ == "__main__":
    main()
