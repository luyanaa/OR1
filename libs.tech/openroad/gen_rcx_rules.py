#!/usr/bin/env python3
"""Generate OR1.rcx_rules (OpenRCX extraction rules) for the OR1 stack.

The previous version of this file was derived from a foreign 10-metal,
0.07 um-pitch process: it declared `LayerCount 10`, carried `Metal 4..10`
sections and swept widths 0.07..0.56 um, while OR1 is a 3-metal process with
1.0 um routing width and 1.0 um spacing.  OpenRCX clamps to the widest entry
it finds, so a 1.0 um OR1 wire was extracted as a 0.56 um wire (~1.8x too much
resistance) and seven of the ten metal layers did not exist at all.
On top of that the rewrite step replaced the coupling column with a constant,
so the capacitance no longer depended on spacing.

This script emits the table from OR1's own parameters instead:

    layer   thickness (um)    Rs = rho/t (ohm/sq)   from LEF RPERSQ
    M1      0.55              0.0509                0.0509
    M2      0.65              0.0431                0.0431
    M3      0.90              0.0311                0.0311

rho = 2.8e-8 ohm*m (Al-Si-Cu).

Capacitance (1 um SiO2, eps_r = 3.9):
    area      CAREA  = 0.035 fF/um^2
    fringe    CFRINGE= 0.050 fF/um
    coupling  CC(s)  = eps0 * eps_r * t / s   (sidewall, per um of length)
                8.854e-6 * 3.9 * t / s  fF/um

Usage:
    python3 gen_rcx_rules.py > OR1.rcx_rules      (or with an output path)
"""
import sys

N_LAYERS = 3
T = {1: 0.55, 2: 0.65, 3: 0.90}          # um
RHO = 2.8e-8                              # ohm*m
LEF_RPERSQ = {1: 0.0509, 2: 0.0431, 3: 0.0311}
CAREA = 3.5e-05                           # fF/um^2
CFRINGE = 5.0e-05                         # fF/um
EPS0 = 8.854e-6                           # fF/um
EPSR = 3.9

WIDTHS = [1.0]                            # routing width (um); OpenRCX uses a
                                          # single width column per table
SPACINGS = [1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0]
# neighbour-context width grid for the RESOVER table (col0 = context width)
RESWIDTHS = [1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0]

RS = {m: RHO / (t * 1e-6) for m, t in T.items()}   # ohm/sq


def coupling(layer, s):
    """Sidewall capacitance to a neighbour at spacing s (fF per um)."""
    return EPS0 * EPSR * T[layer] / s


def r_per_nm(layer, w):
    """Resistance per nm of a wire of width w (ohm/nm)."""
    return RS[layer] / (w * 1000.0)


def width_pairs():
    return [(a, b) for a in WIDTHS for b in WIDTHS if b >= a]


def dist_block(count, width, rows):
    out = ["DIST count %d width %g" % (count, width)]
    out += [" ".join("%g" % v if i < 2 else "%.6g" % v for i, v in enumerate(r)) for r in rows]
    out.append("END DIST")
    return out


def width_table(out):
    out.append("WIDTH Table %d entries: %s" % (len(WIDTHS), " ".join("%g" % w for w in WIDTHS)))
    out.append("")


def emit(out):
    # OpenRCX grammar (extRCmodel.cpp readRules{,Over,Under,OverUnder,res2}):
    #   Metal m <SECTION>              section header + "WIDTH Table" line
    #   Metal m <SECKEY> <ctx>         one context header per neighbour metal
    #   DIST count N width <w>         ONE DIST block PER WIDTH ENTRY (widthCnt
    #   <rows>                         of them, in WIDTH-table order, each keyed
    #   END DIST                       by its own "width <w>"), per context.
    # RESOVER rows are (w_nm, s, 0, res); cap rows are (s_um, cc, cfringe, res).
    out.append("Extraction Rules for OpenRCX")
    out.append("")
    out.append("DIAGMODEL ON")
    out.append("")
    out.append("LayerCount %d" % N_LAYERS)
    out.append("DensityRate 1  0")
    out.append("")
    out.append("DensityModel 0")
    out.append("")

    # OpenRCX grammar (extRCmodel.cpp).  With a single width-table entry each
    # section has ONE DIST block per context.  RESOVER rows are
    #   (neighbour_width, spacing, 0, res)   -> readRC_res2 reads col0 as the
    #   context width and col1 as the spacing; it groups rows into per-spacing
    #   measureTableR_ entries keyed on changes in col0, and getComputeRC_res
    #   indexes that by dist1/dist2, so the grid must start at (0,0) and cover
    #   the full width x spacing sweep.  Cap-table rows are
    #   (spacing, cc, cfringe, res).
    for m in range(1, N_LAYERS + 1):
        # ---- RESOVER k : resistance with layer k below (0 = substrate) ----
        out.append("Metal %d RESOVER" % m)
        width_table(out)
        for k in range(0, m):
            out.append("Metal %d RESOVER %d" % (m, k))
            if k == 0:
                rows = []
                for a in [0.0] + RESWIDTHS:
                    for b in RESWIDTHS:
                        if a > 0 and b < a:
                            continue
                        # res grows slightly as the context wire narrows /
                        # spacing shrinks, giving the parser distinct values to
                        # index while staying centred on RPERSQ/w.
                        res = r_per_nm(m, WIDTHS[0]) * (1.0 + 0.15 * a / (b + 0.5))
                        rows.append((a, b, 0.0, res))
                out += dist_block(len(rows), WIDTHS[0], rows)
            else:
                # a metal directly below shields resistance -> flat substrate
                # value, single row.
                out += dist_block(1, WIDTHS[0], [(0.0, 0.0, 0.0, r_per_nm(m, WIDTHS[0]))])
        out.append("")

        # ---- OVER k : coupling to layer k below (0 = substrate) ----
        out.append("Metal %d OVER" % m)
        width_table(out)
        for k in range(0, m):
            out.append("Metal %d OVER %d" % (m, k))
            rows = []
            for s in SPACINGS:
                cc = CAREA if k == 0 else coupling(m, s)
                rows.append((s, cc, CAREA, r_per_nm(m, WIDTHS[0])))
            out += dist_block(len(rows), WIDTHS[0], rows)
        out.append("")

        # ---- UNDER j : coupling to layer j above ----
        if m < N_LAYERS:
            out.append("Metal %d UNDER" % m)
            width_table(out)
            for j in range(m + 1, N_LAYERS + 1):
                out.append("Metal %d UNDER %d" % (m, j))
                rows = [(s, coupling(m, s), CAREA, r_per_nm(m, WIDTHS[0])) for s in SPACINGS]
                out += dist_block(len(rows), WIDTHS[0], rows)
            out.append("")

            out.append("Metal %d DIAGUNDER" % m)
            width_table(out)
            for j in range(m + 1, N_LAYERS + 1):
                out.append("Metal %d DIAGUNDER %d" % (m, j))
                rows = [(s, coupling(m, s) * 0.5, CAREA, r_per_nm(m, WIDTHS[0])) for s in SPACINGS]
                out += dist_block(len(rows), WIDTHS[0], rows)
            out.append("")

        # ---- OVERUNDER : interior metal coupling to a neighbour below AND a
        # neighbour above.  Required for 1 < m < N_LAYERS; without it the
        # parser leaves _capOverUnder[m] null and calcMinMaxRC segfaults. ----
        if m > 1 and m < N_LAYERS:
            out.append("Metal %d OVERUNDER" % m)
            width_table(out)
            for u in range(1, m):
                for o in range(m + 1, N_LAYERS + 1):
                    out.append("Metal %d OVER %d UNDER %d" % (m, u, o))
                    rows = [(s, coupling(m, s), CAREA, r_per_nm(m, WIDTHS[0])) for s in SPACINGS]
                    out += dist_block(len(rows), WIDTHS[0], rows)
                    out.append("")

    out.append("END DensityModel 0")


def main():
    out = []
    emit(out)
    text = "\n".join(out) + "\n"
    if len(sys.argv) > 1:
        open(sys.argv[1], "w").write(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
