#!/usr/bin/env python3
"""Generate OR1.rcx_rules (OpenRCX extraction rules) from the OR1 RC model.

OpenRCX's rules format is a set of width/spacing lookup tables.  This script
takes a structurally valid reference table and rewrites its electrical
columns with the OR1 model values, per metal layer.

OpenRule1um metallisation is aluminium, and the three layers are not equally
thick (a 1 um CMOS stack is normally graded so the top metal can carry the
power grid):

    layer   thickness (um)     Rs = rho / t        value used
    M1      0.50 - 0.60        0.047 - 0.056       0.051 ohm/sq
    M2      0.60 - 0.70        0.040 - 0.047       0.043 ohm/sq
    M3      0.80 - 1.00        0.028 - 0.035       0.031 ohm/sq

rho = 2.8e-8 ohm*m (Al-Si-Cu; bulk Al is 2.65e-8, 2.8-3.0e-8 is the usual
range for IC Al alloys).

NOTE: LibreLane calls `extract_parasitics -lef_res`, so OpenRCX takes the wire
resistance from the LEF `RESISTANCE RPERSQ` of each routing layer, not from the
resistance columns of this file.  Keep the two in step:

    metal1 RPERSQ 0.0509   metal2 RPERSQ 0.0431   metal3 RPERSQ 0.0311
    (libs.ref/or1_fd_sc/lef/OR1.tlef)

The capacitance columns below ARE used (CPERSQDIST only covers area).  The same per-layer Rs is used by the magic tech file
(`resist ... /metalN` in milliohm/sq), so both extractors stay consistent.

Capacitance is unchanged (1 um SiO2, eps_r = 3.9):
    C area   = 0.035 fF/um^2      C fringe = 0.050 fF/um

The geometry grid (widths/spacings) of the reference table is retained; values
are clamped/interpolated by OpenRCX for larger geometries.  The transformation
is idempotent, so the rules can be regenerated in place:

    python3 gen_rcx_rules.py OR1.rcx_rules > tmp && mv tmp OR1.rcx_rules
"""
import re, sys

AL_RHO = 2.8e-8                    # ohm*m (Al-Si-Cu)

# Film thickness per metal layer (m).  Change only these.
AL_T = {
    1: 0.55e-6,                    # 0.50 - 0.60 um
    2: 0.65e-6,                    # 0.60 - 0.70 um
    3: 0.90e-6,                    # 0.80 - 1.00 um (top metal, power grid)
}

# Sheet resistance per layer (ohm/sq): 0.051 / 0.043 / 0.031
RS = {layer: AL_RHO / thickness for layer, thickness in AL_T.items()}

CFRINGE = 5.0e-05                  # fF/um
CAREA = 3.5e-05                    # fF/um^2

def main(src):
    section = None
    metal = 1
    for ln in open(src).read().splitlines():
        s = ln.strip()
        m = re.match(r'^Metal (\d+) (RESOVER|OVER|UNDER|DIAGUNDER|DIAGOVER)\b', s)
        if m:
            metal = int(m.group(1))
            section = m.group(2)
        if s and s[0].isdigit() and section:
            parts = s.split()
            if len(parts) == 4:
                try:
                    w = float(parts[0])
                except ValueError:
                    print(ln); continue
                rs = RS.get(metal, RS[1])
                if section == 'RESOVER':
                    r = rs / (w * 1000.0) if w > 0 else 0.0
                    print(f"{parts[0]} {parts[1]} 0 {r:.6g}")
                else:
                    r = rs / ((w if w > 0 else 1.0) * 1000.0)
                    print(f"{parts[0]} {CFRINGE:.3g} {CAREA:.3g} {r:.6g}")
                continue
        print(ln)

if __name__ == '__main__':
    main(sys.argv[1])
