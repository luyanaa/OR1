# ---------------------------------------------------------------------------
# Source: original implementation for the OR1 PDK.  The device contract
#   (parameters, rules) is ported from OpenRule1um_v2 pcells_v2.lym v2.99,
#   (c) S. Moriyama / Anagix Corporation,
#   https://github.com/mineda-support/OpenRule1um  tech/tech/macros/pcells_v2.lym
#   (Apache-2.0); the geometry is re-implemented here on the Python PCell API.
# License: Apache-2.0 (see OR1PDK/LICENSE and PROVENANCE.md).
# OR1 (OpenRule1um) KLayout PCell library
#
# Load: put this file on KLayout's macro path (Macro Editor / pymacros), or
#       start KLayout with   klayout -m or1_pcells.py
# The library registers as "or1_pcells".
#
# Ported from the upstream OpenRule1um_v2 PCell set (pcells_v2.lym, v2.99,
# S. Moriyama) to the Python PCell API.  The upstream library derives every
# device from the MinedaPCell / OpenRule1um_Basic base classes (they are not
# shipped with the PDK and hardly portable); this file implements the same
# device contract directly from the OR1 design rules instead:
#
#   * all geometry on the 0.5 um layout grid (the OR1 manufacturing grid in
#     OR1.tlef is 0.1 um and the upstream off-grid check uses 0.05 um, so 0.5
#     satisfies both)
#   * width/space 1.0, diff space 1.5, poly-diff 0.5, nwell<->pdiff 2.0,
#     contact/via 1x1 with 0.5 enclosure and 1.0 spacing
#   * parameters are clamped/rejected in coerce_parameters_impl: a PCell never
#     silently emits geometry below the rules
# ---------------------------------------------------------------------------
import pya

# GDS layers (magic cifoutput numbering)
L_NW   = (1, 0)
L_DIFF = (3, 0)
L_POLY = (5, 0)
L_HPOL = (6, 0)
L_CNT  = (7, 0)
L_M1   = (8, 0)
L_V1   = (9, 0)
L_M2   = (10, 0)
L_V2   = (11, 0)
L_M3   = (12, 0)
L_PA   = (18, 0)   # parea / pselect
L_NA   = (19, 0)   # narea / nselect
L_RES  = (15, 0)   # poly resistor marker
L_CAP  = (16, 0)
L_DIO  = (17, 0)
L_DM_DCN  = (101, 0)  # contact-on-diffusion marker
L_DM_PCN  = (102, 0)  # contact-on-poly marker
L_DM_NSCN = (103, 0)  # n-substrate contact marker
L_DM_PSCN = (104, 0)  # p-substrate contact marker

GRID = 0.5         # layout grid (um)
MIN_W = 1.0        # minimum drawn width
MIN_SPACE = 1.0    # minimum drawn space
DIFF_SPACE = 1.5
POLY_DIFF = 0.5
NW_ENCL = 2.0
CNT = 1.0          # contact/via size
CNT_ENC = 0.5      # enclosure around a contact/via
CNT_PITCH = 2.0    # contact/via pitch (1.0 space)

# Sheet resistances used only for the informational display text.
#   RS_POLY is measured (MakeLSI/Measure/16PTS/R-C.md: 500 ohm over 45/1.8 um
#   = 25 squares) and confirmed within 4 % by the 2022 22PTS TEG.
#   RS_HPOL is a HYPOTHESIS: the 22HR80k TEG cannot be built at 20 ohm/sq and
#   its ratio to the 400 ohm poly TEG implies ~3.2 kohm/sq against a design
#   assumption of 4.0 kohm/sq.  It does not affect the drawn geometry.
RS_POLY = 20.0
RS_HPOL = 3200.0


class _Base(pya.PCellDeclarationHelper):
    """Common helpers: grid snapping, validation and a box drawer."""

    def _u(self, v):
        return int(round(v / self.layout.dbu))

    def _snap(self, v):
        return round(round(v / GRID) * GRID, 3)

    def _box(self, layer, x1, y1, x2, y2):
        if x2 <= x1 or y2 <= y1:
            return
        self.cell.shapes(self._li(layer)).insert(
            pya.Box(self._u(x1), self._u(y1), self._u(x2), self._u(y2)))

    def _ring(self, layer, x1, y1, x2, y2, t):
        """Rectangular ring of thickness t."""
        self._box(layer, x1, y1, x2, y1 + t)
        self._box(layer, x1, y2 - t, x2, y2)
        self._box(layer, x1, y1 + t, x1 + t, y2 - t)
        self._box(layer, x2 - t, y1 + t, x2, y2 - t)

    def _band_centres(self, x1, y1, x2, y2, t, pitch):
        """Contact centres inside a rectangular band of thickness t."""
        pts = []
        n = int((x2 - x1) / pitch) + 1
        m = int((y2 - y1) / pitch) + 1
        for i in range(n + 1):
            for j in range(m + 1):
                x = x1 + t / 2.0 + i * pitch
                y = y1 + t / 2.0 + j * pitch
                if x > x2 - t / 2.0 or y > y2 - t / 2.0:
                    continue
                in_band = (x < x1 + t or x > x2 - t or
                           y < y1 + t or y > y2 - t)
                if in_band:
                    pts.append((x, y))
        return pts

    def _li(self, spec):
        return self.layout.layer(spec[0], spec[1])


class OR1Contact(_Base):
    """Parameterised contact array between DIFF or POL and metal1."""

    def __init__(self):
        super(OR1Contact, self).__init__()
        self.param("on", self.TypeString, "Contact to (diff/poly)", default="diff")
        self.param("cols", self.TypeInt, "Columns", default=2)
        self.param("rows", self.TypeInt, "Rows", default=1)
        self.param("pitch", self.TypeDouble, "Pitch (um)", default=CNT_PITCH)
        self.param("metal", self.TypeBoolean, "Draw metal1 pad", default=True)

    def display_text_impl(self):
        return "OR1_CONTACT(%s, %dx%d)" % (self.on, self.cols, self.rows)

    def coerce_parameters_impl(self):
        self.cols = max(1, int(self.cols))
        self.rows = max(1, int(self.rows))
        self.pitch = max(CNT + MIN_SPACE, self._snap(self.pitch))
        if self.on not in ("diff", "poly"):
            self.on = "diff"

    def produce_impl(self):
        under = L_POLY if self.on == "poly" else L_DIFF
        w = (self.cols - 1) * self.pitch + CNT
        h = (self.rows - 1) * self.pitch + CNT
        for c in range(self.cols):
            for r in range(self.rows):
                x = c * self.pitch
                y = r * self.pitch
                self._box(L_CNT, x, y, x + CNT, y + CNT)
        # the underlying layer must enclose every contact by 0.5 um
        self._box(under, -CNT_ENC, -CNT_ENC, w + CNT_ENC, h + CNT_ENC)
        if self.metal:
            self._box(L_M1, -CNT_ENC, -CNT_ENC, w + CNT_ENC, h + CNT_ENC)


class OR1Via(_Base):
    """Via array (via1 or via2) with the metal pads above and below."""

    def __init__(self):
        super(OR1Via, self).__init__()
        self.param("cut", self.TypeString, "Cut layer", default="via1")
        self.param("cols", self.TypeInt, "Columns", default=2)
        self.param("rows", self.TypeInt, "Rows", default=2)
        self.param("pitch", self.TypeDouble, "Pitch (um)", default=CNT_PITCH)
        self.param("pad", self.TypeBoolean, "Draw metal pads", default=True)

    def display_text_impl(self):
        return "OR1_VIA(%s, %dx%d)" % (self.cut, self.cols, self.rows)

    def coerce_parameters_impl(self):
        self.cols = max(1, int(self.cols))
        self.rows = max(1, int(self.rows))
        self.pitch = max(CNT + MIN_SPACE, self._snap(self.pitch))
        if self.cut not in ("via1", "via2"):
            self.cut = "via1"

    def produce_impl(self):
        cut = L_V1 if self.cut == "via1" else L_V2
        low = L_M1 if self.cut == "via1" else L_M2
        high = L_M2 if self.cut == "via1" else L_M3
        w = (self.cols - 1) * self.pitch + CNT
        h = (self.rows - 1) * self.pitch + CNT
        for c in range(self.cols):
            for r in range(self.rows):
                x = c * self.pitch
                y = r * self.pitch
                self._box(cut, x, y, x + CNT, y + CNT)
        if self.pad:
            self._box(low, -CNT_ENC, -CNT_ENC, w + CNT_ENC, h + CNT_ENC)
            self._box(high, -CNT_ENC, -CNT_ENC, w + CNT_ENC, h + CNT_ENC)


class OR1Pad(_Base):
    """Bond pad: metal3 plate with via2/via1 stacks down to metal1."""

    def __init__(self):
        super(OR1Pad, self).__init__()
        self.param("size", self.TypeDouble, "Pad size (um)", default=12.0)
        self.param("via_pitch", self.TypeDouble, "Via pitch (um)", default=CNT_PITCH)

    def display_text_impl(self):
        return "OR1_PAD(%.1fx%.1f)" % (self.size, self.size)

    def coerce_parameters_impl(self):
        self.size = max(4.0, self._snap(self.size))
        self.via_pitch = max(CNT + MIN_SPACE, self._snap(self.via_pitch))

    def produce_impl(self):
        s = self.size
        self._box(L_M3, 0.0, 0.0, s, s)
        inset = 1.0
        x = inset
        while x + CNT <= s - inset:
            y = inset
            while y + CNT <= s - inset:
                self._box(L_V2, x, y, x + CNT, y + CNT)
                self._box(L_V1, x, y, x + CNT, y + CNT)
                y += self.via_pitch
            x += self.via_pitch
        self._box(L_M2, 0.5, 0.5, s - 0.5, s - 0.5)
        self._box(L_M1, 0.5, 0.5, s - 0.5, s - 0.5)


class OR1Mos(_Base):
    """Four-terminal MOS with nf fingers, shared S/D and optional body tap.

    The total effective width is w * nf; w is the width of one finger.
    Neighbouring fingers share their S/D diffusion strip (upstream semantics).
    """

    def __init__(self):
        super(OR1Mos, self).__init__()
        self.param("type", self.TypeString, "Type (n/p)", default="n")
        self.param("w", self.TypeDouble, "Finger width W (um)", default=4.0)
        self.param("l", self.TypeDouble, "Channel length L (um)", default=1.0)
        self.param("sd", self.TypeDouble, "S/D strip length (um)", default=2.0)
        self.param("nf", self.TypeInt, "Number of fingers", default=1)
        self.param("gate_contact", self.TypeBoolean, "Contact the gate poly", default=True)
        self.param("body_tie", self.TypeString, "Body tie (none/local)", default="local")
        self.param("with_via", self.TypeBoolean, "via1 + metal2 over pads", default=False)

    def display_text_impl(self):
        return "OR1_MOS(%s W=%.1f L=%.1f nf=%d, wtot=%.1f)" % (
            self.type, self.w, self.l, self.nf, self.w * self.nf)

    def coerce_parameters_impl(self):
        if self.type not in ("n", "p"):
            self.type = "n"
        self.l = max(MIN_W, self._snap(self.l))
        self.w = max(2.0, self._snap(self.w))          # 1x1 contact + 0.5 enc
        self.sd = max(2.0, self._snap(self.sd))
        self.nf = max(1, int(self.nf))
        if self.body_tie not in ("none", "local"):
            self.body_tie = "local"

    def produce_impl(self):
        self._draw_mos()

    def _draw_mos(self, ox=0.0, oy=0.0, mirror=False):
        n = self.nf
        l, w, sd = self.l, self.w, self.sd
        X = n * l + (n + 1) * sd

        def B(layer, x1, y1, x2, y2):
            if mirror:
                x1, x2 = X - x2, X - x1
            self._box(layer, ox + x1, oy + y1, ox + x2, oy + y2)

        # diffusion and gate fingers
        B(L_DIFF, 0.0, 0.0, X, w)
        for i in range(n):
            x0 = sd + i * (l + sd)
            B(L_POLY, x0, -1.0, x0 + l, w + 1.0)
        # select / well
        if self.type == "p":
            B(L_NW, -NW_ENCL, -NW_ENCL, X + NW_ENCL, w + NW_ENCL)
            sel = L_PA          # pMOS channel: p-select
        else:
            sel = L_NA          # nMOS channel: n-select
        B(sel, -0.5, -0.5, X + 0.5, w + 0.5)
        # S/D contacts and metal1 islands (one contact per strip per 2 um)
        cy = w / 2.0
        for i in range(n + 1):
            xc = sd / 2.0 + i * (l + sd)
            B(L_CNT, xc - 0.5, cy - 0.5, xc + 0.5, cy + 0.5)
            B(L_DM_DCN, xc - 1.0, cy - 1.0, xc + 1.0, cy + 1.0)
            B(L_M1, xc - 1.0, cy - 1.0, xc + 1.0, cy + 1.0)
            if self.with_via:
                B(L_V1, xc - 0.5, cy - 0.5, xc + 0.5, cy + 0.5)
                B(L_M2, xc - 1.0, cy - 1.0, xc + 1.0, cy + 1.0)
        # gate bus: connect all fingers with a poly bar above the channel
        if self.gate_contact:
            B(L_POLY, sd, w + 1.0, X - sd, w + 3.0)
            gx = X / 2.0
            B(L_CNT, gx - 0.5, w + 1.5, gx + 0.5, w + 2.5)
            B(L_DM_PCN, gx - 1.0, w + 1.0, gx + 1.0, w + 3.0)
            B(L_M1, gx - 1.0, w + 1.0, gx + 1.0, w + 3.0)
            if self.with_via:
                B(L_V1, gx - 0.5, w + 1.5, gx + 0.5, w + 2.5)
                B(L_M2, gx - 1.0, w + 1.0, gx + 1.0, w + 3.0)
        # body tap below the device
        if self.body_tie == "local":
            ty0 = -1.5 - 2.0
            B(L_DIFF, 0.0, ty0, X, ty0 + 2.0)
            tsel = L_NA if self.type == "p" else L_PA
            B(tsel, -0.5, ty0 - 0.5, X + 0.5, ty0 + 2.5)
            if self.type == "p":
                B(L_NW, -NW_ENCL, ty0 - NW_ENCL, X + NW_ENCL,
                          w + NW_ENCL)
            xc = CNT_ENC + 0.5
            while xc + 0.5 <= X - CNT_ENC:
                B(L_CNT, xc - 0.5, ty0 + 0.5, xc + 0.5, ty0 + 1.5)
                B(L_DM_NSCN if self.type == "p" else L_DM_PSCN,
                  xc - 1.0, ty0, xc + 1.0, ty0 + 2.0)
                B(L_M1, xc - 1.0, ty0 + 0.0, xc + 1.0, ty0 + 2.0)
                xc += CNT_PITCH

class OR1MosGuard(OR1Mos):
    """MOS with an enclosing substrate guard ring (Psub/Nsub ring).

    The ring is drawn gap microns away from the device (diff space 1.5 um) and
    is ring_width thick, so a 1x1 contact fits with 0.5 um enclosure.  For a
    pMOS the ring diff (n-select) sits inside the same n-well, which is
    extended to enclose every diffusion by 2 um.
    """

    def __init__(self):
        super(OR1MosGuard, self).__init__()
        self.param("ring_width", self.TypeDouble, "Guard ring width (um)", default=2.0)
        self.param("ring_gap", self.TypeDouble, "Device-to-ring gap (um)", default=1.5)

    def display_text_impl(self):
        return "OR1_MOSGUARD(%s W=%.1f L=%.1f nf=%d ring=%.1f/%.1f)" % (
            self.type, self.w, self.l, self.nf, self.ring_width, self.ring_gap)

    def coerce_parameters_impl(self):
        super(OR1MosGuard, self).coerce_parameters_impl()
        self.ring_width = max(2.0, self._snap(self.ring_width))
        self.ring_gap = max(DIFF_SPACE, self._snap(self.ring_gap))

    def produce_impl(self):
        super(OR1MosGuard, self).produce_impl()
        n, l, w, sd = self.nf, self.l, self.w, self.sd
        X = n * l + (n + 1) * sd
        # body extent (select is 0.5 um outside the diffusion on each side)
        y_lo = -1.5 - 2.0 if self.body_tie == "local" else 0.0
        y_hi = (w + 3.0) if self.gate_contact else w
        bx0, by0 = -0.5, y_lo - 0.5
        bx1, by1 = X + 0.5, y_hi + 0.5
        g, t = self.ring_gap, self.ring_width
        ix0, iy0, ix1, iy1 = bx0 - g, by0 - g, bx1 + g, by1 + g
        ox0, oy0 = ix0 - t, iy0 - t
        ox1, oy1 = ix1 + t, iy1 + t
        self._ring(L_DIFF, ox0, oy0, ox1, oy1, t)
        # pMOS sits in an n-well -> n+ guard; nMOS sits in the p-substrate -> p+ guard
        sel = L_NA if self.type == "p" else L_PA
        self._ring(sel, ox0 - 0.5, oy0 - 0.5, ox1 + 0.5, oy1 + 0.5, t + 1.0)
        if self.type == "p":
            # one solid n-well covering device + ring, enclosing pdiff by 2 um
            self._box(L_NW, ox0 - NW_ENCL, oy0 - NW_ENCL,
                      ox1 + NW_ENCL, oy1 + NW_ENCL)
        tap = L_DM_NSCN if self.type == "p" else L_DM_PSCN
        for (cx, cy) in self._band_centres(ox0, oy0, ox1, oy1, t, CNT_PITCH):
            self._box(L_CNT, cx - 0.5, cy - 0.5, cx + 0.5, cy + 0.5)
            self._box(tap, cx - 1.0, cy - 1.0, cx + 1.0, cy + 1.0)
            self._box(L_M1, cx - 1.0, cy - 1.0, cx + 1.0, cy + 1.0)


class OR1Res(_Base):
    """Poly or high-res poly resistor with contact heads.

    Body sheet resistance is 20 ohm/sq (poly) - the HR variant uses the HPOL
    layer and is marked with RES, matching the upstream R_poly / HR_poly.
    """

    def __init__(self):
        super(OR1Res, self).__init__()
        self.param("w", self.TypeDouble, "Width (um)", default=2.0)
        self.param("l", self.TypeDouble, "Body length (um)", default=10.0)
        self.param("hr", self.TypeBoolean, "High-res poly (HR_poly)", default=False)

    def display_text_impl(self):
        # Rs_HPOL is a hypothesis derived from the 22PTS 22HR80k TEG (the
        # ratio to the 400 ohm poly TEG gives ~3.2 kohm/sq against a design
        # assumption of 4.0 kohm/sq); see
        # OR1PDK/docs/measure/2026-11-01-round4-traceability-and-hpol.md.
        rs = RS_HPOL if self.hr else RS_POLY
        return "OR1_RES(%s %.1fx%.1f, ~%.3g ohm)" % (
            "HR" if self.hr else "poly", self.w, self.l, rs * self.l / self.w)

    def coerce_parameters_impl(self):
        self.w = max(2.0, self._snap(self.w))   # contact head needs 2 um
        self.l = max(4.0, self._snap(self.l))
        if self.hr:
            # HIPOL body between the contact heads must be 22..82 um
            self.l = min(max(self.l, 25.0), 85.0)
            self.l = self._snap(self.l)

    def produce_impl(self):
        w, l = self.w, self.l
        # the HPOL ("high-res poly") is drawn on top of POL: the KLayout deck
        # derives hpol = HPOL & POL, so both layers are required.  HPOL must
        # enclose POL by 5 um (hpol.enclosing(hipol, 5.0)).
        self._box(L_POLY, 0.0, 0.0, l, w)
        if self.hr:
            self._box(L_HPOL, -5.0, -5.0, l + 5.0, w + 5.0)
        self._box(L_RES, 0.0, 0.0, l, w)
        # contact heads, 0.5 um from the body ends
        self._box(L_CNT, 0.5, w / 2.0 - 0.5, 1.5, w / 2.0 + 0.5)
        self._box(L_CNT, l - 1.5, w / 2.0 - 0.5, l - 0.5, w / 2.0 + 0.5)
        self._box(L_M1, 0.0, w / 2.0 - 1.0, 2.0, w / 2.0 + 1.0)
        self._box(L_M1, l - 2.0, w / 2.0 - 1.0, l, w / 2.0 + 1.0)


class OR1DiffRes(_Base):
    """Diffusion resistor (R_ndiff / R_pdiff).

    The OR1 rule table defines no specific resistor rules: the geometry is
    covered by the generic diff / select / contact rules, and RES (15/0) is an
    annotation marker.  A p-type body sits in an n-well (enclosed by 2 um).
    """

    def __init__(self):
        super(OR1DiffRes, self).__init__()
        self.param("type", self.TypeString, "Type (n/p)", default="n")
        self.param("w", self.TypeDouble, "Width (um)", default=2.0)
        self.param("l", self.TypeDouble, "Body length (um)", default=10.0)

    def display_text_impl(self):
        return "OR1_DIFFRES(%s %.1fx%.1f)" % (self.type, self.w, self.l)

    def coerce_parameters_impl(self):
        if self.type not in ("n", "p"):
            self.type = "n"
        self.w = max(2.0, self._snap(self.w))
        self.l = max(4.0, self._snap(self.l))

    def produce_impl(self):
        w, l = self.w, self.l
        self._box(L_DIFF, 0.0, 0.0, l, w)
        self._box(L_RES, 0.0, 0.0, l, w)
        sel = L_NA if self.type == "n" else L_PA
        self._box(sel, -0.5, -0.5, l + 0.5, w + 0.5)
        if self.type == "p":
            self._box(L_NW, -NW_ENCL, -NW_ENCL, l + NW_ENCL, w + NW_ENCL)
        self._box(L_CNT, 0.5, w / 2.0 - 0.5, 1.5, w / 2.0 + 0.5)
        self._box(L_CNT, l - 1.5, w / 2.0 - 0.5, l - 0.5, w / 2.0 + 0.5)
        self._box(L_M1, 0.0, w / 2.0 - 1.0, 2.0, w / 2.0 + 1.0)
        self._box(L_M1, l - 2.0, w / 2.0 - 1.0, l, w / 2.0 + 1.0)


class OR1Diode(_Base):
    """N-well / P-substrate diode (p+ anode inside the n-well, n+ cathode).

    Both diffusions sit inside the n-well, so the n-well encloses the p+
    diffusion by 2 um (rule 22) and the DIO (17/0) layer is an annotation
    marker (the rule table defines no diode-specific geometry rules).
    """

    def __init__(self):
        super(OR1Diode, self).__init__()
        self.param("w", self.TypeDouble, "Diffusion width (um)", default=6.0)
        self.param("h", self.TypeDouble, "Anode height (um)", default=4.0)
        self.param("gap", self.TypeDouble, "Anode-cathode gap (um)", default=1.5)

    def display_text_impl(self):
        return "OR1_DIODE(%.1fx%.1f gap=%.1f)" % (self.w, self.h, self.gap)

    def coerce_parameters_impl(self):
        self.w = max(4.0, self._snap(self.w))
        self.h = max(2.0, self._snap(self.h))
        self.gap = max(DIFF_SPACE, self._snap(self.gap))

    def produce_impl(self):
        W, H, g = self.w, self.h, self.gap
        # anode (p+ in nwell) and cathode (n+) below it
        self._box(L_DIFF, 0.0, 0.0, W, H)
        self._box(L_DIFF, 0.0, -(g + 2.0), W, -g)
        self._box(L_PA, -0.5, -0.5, W + 0.5, H + 0.5)
        self._box(L_NA, -0.5, -(g + 2.5), W + 0.5, -g + 0.5)
        self._box(L_NW, -NW_ENCL, -(g + 2.0) - NW_ENCL, W + NW_ENCL, H + NW_ENCL)
        self._box(L_DIO, -NW_ENCL, -(g + 2.0) - NW_ENCL, W + NW_ENCL, H + NW_ENCL)
        self._box(L_CNT, W / 2.0 - 0.5, H / 2.0 - 0.5, W / 2.0 + 0.5, H / 2.0 + 0.5)
        self._box(L_M1, W / 2.0 - 1.0, H / 2.0 - 1.0, W / 2.0 + 1.0, H / 2.0 + 1.0)
        yc = -(g + 1.0)
        self._box(L_CNT, W / 2.0 - 0.5, yc - 0.5, W / 2.0 + 0.5, yc + 0.5)
        # the n+ cathode is also the n-well tap: without this marker the deck
        # cannot tie the well (cathode) to the cathode metal
        self._box(L_DM_NSCN, W / 2.0 - 1.0, yc - 1.0, W / 2.0 + 1.0, yc + 1.0)
        self._box(L_M1, W / 2.0 - 1.0, yc - 1.0, W / 2.0 + 1.0, yc + 1.0)


class OR1MosCap(_Base):
    """MOS capacitor: poly over diffusion, gate and plate brought out on M1.

    Single-poly process, so the capacitor is the MOS structure itself: the
    poly strip crosses the diffusion, the diffusion on both sides is the
    bottom plate, the poly extension above is the top plate.
    """

    def __init__(self):
        super(OR1MosCap, self).__init__()
        self.param("w", self.TypeDouble, "Plate width (um)", default=6.0)
        self.param("h", self.TypeDouble, "Plate height (um)", default=4.0)
        self.param("l", self.TypeDouble, "Poly gate length (um)", default=2.0)

    def display_text_impl(self):
        return "OR1_MOSCAP(%.1fx%.1f L=%.1f)" % (self.w, self.h, self.l)

    def coerce_parameters_impl(self):
        self.w = max(4.0, self._snap(self.w))
        self.h = max(2.0, self._snap(self.h))
        self.l = max(MIN_W, self._snap(self.l))
        # The bottom-plate contacts sit at x=0.5..1.5 and W-1.5..W-0.5; the poly
        # strip is centred, so L > W-3 would put the gate over a contact and the
        # deck reports dcn-MOS overlap.  (W-2 was not enough: found by the
        # OR1_PCELL_SWEEP run at the l clamping bound.)
        if self.l > self.w - 3.0:
            self.l = self.w - 3.0

    def produce_impl(self):
        W, H, L = self.w, self.h, self.l
        x0 = (W - L) / 2.0
        self._box(L_DIFF, 0.0, 0.0, W, H)
        self._box(L_NA, -0.5, -0.5, W + 0.5, H + 0.5)
        # CAP marker: lets the LVS deck extract the structure as a capacitor
        # and not as an nMOS transistor
        self._box(L_CAP, 0.0, 0.0, W, H)
        # poly strip crossing the plate, 1 um overhang and a head above
        self._box(L_POLY, x0, -1.0, x0 + L, H + 3.0)
        self._box(L_CNT, x0 + L / 2.0 - 0.5, H + 1.5, x0 + L / 2.0 + 0.5, H + 2.5)
        self._box(L_M1, x0 + L / 2.0 - 1.0, H + 1.5, x0 + L / 2.0 + 1.0, H + 2.5)
        # bottom plate contacts on both sides of the gate
        self._box(L_CNT, 0.5, H / 2.0 - 0.5, 1.5, H / 2.0 + 0.5)
        self._box(L_M1, 0.0, H / 2.0 - 1.0, 2.0, H / 2.0 + 1.0)
        self._box(L_CNT, W - 1.5, H / 2.0 - 0.5, W - 0.5, H / 2.0 + 0.5)
        self._box(L_M1, W - 2.0, H / 2.0 - 1.0, W, H / 2.0 + 1.0)


class OR1Ring(_Base):
    """Guard ring / substrate ring (Psub_ring, Nsub_ring).

    t is the diffusion ring width (>= 2 um so a 1x1 contact fits with 0.5 um
    enclosure).  For a p-ring the diffusion is p-select; for an n-ring it is
    n-select inside an n-well that encloses the ring by 2 um.
    """

    def __init__(self):
        super(OR1Ring, self).__init__()
        self.param("type", self.TypeString, "Type (p/n)", default="p")
        self.param("w", self.TypeDouble, "Outer width (um)", default=20.0)
        self.param("h", self.TypeDouble, "Outer height (um)", default=20.0)
        self.param("t", self.TypeDouble, "Ring diffusion width (um)", default=2.0)

    def display_text_impl(self):
        return "OR1_RING(%s %.1fx%.1f t=%.1f)" % (self.type, self.w, self.h, self.t)

    def coerce_parameters_impl(self):
        if self.type not in ("p", "n"):
            self.type = "p"
        self.t = max(2.0, self._snap(self.t))
        self.w = max(2 * self.t + 4.0, self._snap(self.w))
        self.h = max(2 * self.t + 4.0, self._snap(self.h))

    def produce_impl(self):
        w, h, t = self.w, self.h, self.t
        self._ring(L_DIFF, 0.0, 0.0, w, h, t)
        sel = L_PA if self.type == "p" else L_NA
        self._ring(sel, -0.5, -0.5, w + 0.5, h + 0.5, t + 1.0)
        if self.type == "n":
            self._ring(L_NW, -NW_ENCL, -NW_ENCL, w + NW_ENCL, h + NW_ENCL,
                       t + 2 * NW_ENCL)
        # Substrate-tap marker: the LVS deck treats DM_nscn(103)/DM_pscn(104)
        # as the authoritative well/substrate connection, so every tap contact
        # needs one (2x2 around the 1x1 contact, the standard-cell pattern).
        tap = L_DM_NSCN if self.type == "n" else L_DM_PSCN
        for (cx, cy) in self._band_centres(0.0, 0.0, w, h, t, CNT_PITCH):
            self._box(L_CNT, cx - 0.5, cy - 0.5, cx + 0.5, cy + 0.5)
            self._box(tap, cx - 1.0, cy - 1.0, cx + 1.0, cy + 1.0)
            self._box(L_M1, cx - 1.0, cy - 1.0, cx + 1.0, cy + 1.0)


class OR1TapLine(_Base):
    """Substrate tap line (Psub_line, Nsub_line)."""

    def __init__(self):
        super(OR1TapLine, self).__init__()
        self.param("type", self.TypeString, "Type (p/n)", default="p")
        self.param("length", self.TypeDouble, "Length (um)", default=20.0)
        self.param("width", self.TypeDouble, "Diffusion width (um)", default=2.0)

    def display_text_impl(self):
        return "OR1_TAPLINE(%s %.1fx%.1f)" % (self.type, self.length, self.width)

    def coerce_parameters_impl(self):
        if self.type not in ("p", "n"):
            self.type = "p"
        self.width = max(2.0, self._snap(self.width))
        self.length = max(4.0, self._snap(self.length))

    def produce_impl(self):
        L, W = self.length, self.width
        self._box(L_DIFF, 0.0, 0.0, L, W)
        sel = L_PA if self.type == "p" else L_NA
        self._box(sel, -0.5, -0.5, L + 0.5, W + 0.5)
        if self.type == "n":
            self._box(L_NW, -NW_ENCL, -NW_ENCL, L + NW_ENCL, W + NW_ENCL)
        tap = L_DM_NSCN if self.type == "n" else L_DM_PSCN
        x = CNT_ENC + 0.5
        while x + 0.5 <= L - CNT_ENC:
            self._box(L_CNT, x - 0.5, W / 2.0 - 0.5, x + 0.5, W / 2.0 + 0.5)
            self._box(tap, x - 1.0, W / 2.0 - 1.0, x + 1.0, W / 2.0 + 1.0)
            self._box(L_M1, x - 1.0, W / 2.0 - 1.0, x + 1.0, W / 2.0 + 1.0)
            x += CNT_PITCH


class OR1MosMatch(OR1Mos):
    """Matched pair: two identical devices, the second mirrored about the gap."""

    def __init__(self):
        super(OR1MosMatch, self).__init__()
        self.param("gap", self.TypeDouble, "Device gap (um)", default=1.5)

    def display_text_impl(self):
        return "OR1_MOSMATCH(%s W=%.1f L=%.1f nf=%d gap=%.1f)" % (
            self.type, self.w, self.l, self.nf, self.gap)

    def coerce_parameters_impl(self):
        super(OR1MosMatch, self).coerce_parameters_impl()
        self.gap = max(DIFF_SPACE, self._snap(self.gap))

    def produce_impl(self):
        X = self.nf * self.l + (self.nf + 1) * self.sd
        self._draw_mos()
        self._draw_mos(X + self.gap, 0.0, mirror=True)


class OR1ResArray(OR1Res):
    """Array of unit poly resistors in a row (series/parallel wiring by hand)."""

    def __init__(self):
        super(OR1ResArray, self).__init__()
        self.param("count", self.TypeInt, "Number of units", default=4)
        self.param("pitch", self.TypeDouble, "Unit pitch (um)", default=0.0)

    def display_text_impl(self):
        return "OR1_RESARRAY(%s %.1fx%.1f x%d)" % (
            "HR" if self.hr else "poly", self.w, self.l, self.count)

    def coerce_parameters_impl(self):
        super(OR1ResArray, self).coerce_parameters_impl()
        self.count = max(1, int(self.count))
        self.pitch = self._snap(self.pitch)
        if self.pitch < self.l + MIN_SPACE:
            self.pitch = self._snap(self.l + 2.0)

    def produce_impl(self):
        for i in range(self.count):
            ox = i * self.pitch
            w, l = self.w, self.l
            self._box(L_POLY, ox, 0.0, ox + l, w)
            self._box(L_RES, ox, 0.0, ox + l, w)
            if self.hr:
                self._box(L_HPOL, ox - 5.0, -5.0, ox + l + 5.0, w + 5.0)
            self._box(L_CNT, ox + 0.5, w / 2.0 - 0.5, ox + 1.5, w / 2.0 + 0.5)
            self._box(L_CNT, ox + l - 1.5, w / 2.0 - 0.5, ox + l - 0.5, w / 2.0 + 0.5)
            self._box(L_M1, ox, w / 2.0 - 1.0, ox + 2.0, w / 2.0 + 1.0)
            self._box(L_M1, ox + l - 2.0, w / 2.0 - 1.0, ox + l, w / 2.0 + 1.0)


class OR1CapArray(OR1MosCap):
    """Matrix of unit MOS capacitors (unit cells left to be wired by hand)."""

    def __init__(self):
        super(OR1CapArray, self).__init__()
        self.param("cols", self.TypeInt, "Columns", default=2)
        self.param("rows", self.TypeInt, "Rows", default=2)
        self.param("pitch_x", self.TypeDouble, "Horizontal pitch (um)", default=0.0)
        self.param("pitch_y", self.TypeDouble, "Vertical pitch (um)", default=0.0)

    def display_text_impl(self):
        return "OR1_CAPARRAY(%.1fx%.1f L=%.1f %dx%d)" % (
            self.w, self.h, self.l, self.cols, self.rows)

    def coerce_parameters_impl(self):
        super(OR1CapArray, self).coerce_parameters_impl()
        self.cols = max(1, int(self.cols))
        self.rows = max(1, int(self.rows))
        self.pitch_x = self._snap(self.pitch_x)
        self.pitch_y = self._snap(self.pitch_y)
        if self.pitch_x < self.w + MIN_SPACE:
            self.pitch_x = self._snap(self.w + 2.0)
        if self.pitch_y < self.h + 4.0:
            self.pitch_y = self._snap(self.h + 5.0)

    def produce_impl(self):
        W, H, L = self.w, self.h, self.l
        x0 = (W - L) / 2.0
        for r in range(self.rows):
            for c in range(self.cols):
                ox, oy = c * self.pitch_x, r * self.pitch_y
                self._box(L_DIFF, ox, oy, ox + W, oy + H)
                self._box(L_NA, ox - 0.5, oy - 0.5, ox + W + 0.5, oy + H + 0.5)
                self._box(L_CAP, ox, oy, ox + W, oy + H)
                self._box(L_POLY, ox + x0, oy - 1.0, ox + x0 + L, oy + H + 3.0)
                self._box(L_CNT, ox + x0 + L / 2 - 0.5, oy + H + 1.5,
                          ox + x0 + L / 2 + 0.5, oy + H + 2.5)
                self._box(L_M1, ox + x0 + L / 2 - 1.0, oy + H + 1.5,
                          ox + x0 + L / 2 + 1.0, oy + H + 2.5)
                self._box(L_CNT, ox + 0.5, oy + H / 2 - 0.5, ox + 1.5, oy + H / 2 + 0.5)
                self._box(L_M1, ox, oy + H / 2 - 1.0, ox + 2.0, oy + H / 2 + 1.0)
                self._box(L_CNT, ox + W - 1.5, oy + H / 2 - 0.5, ox + W - 0.5, oy + H / 2 + 0.5)
                self._box(L_M1, ox + W - 2.0, oy + H / 2 - 1.0, ox + W, oy + H / 2 + 1.0)


class OR1Esd(OR1MosGuard):
    """ESD layout template: guarded multi-finger NMOS (ggNMOS style).

    This is a *layout template*, not a qualified ESD device: the OR1 rule
    table defines no ESD-specific rules, so the structure must be validated
    against the process before use.
    """

    def __init__(self):
        super(OR1Esd, self).__init__()
        self.param("fingers", self.TypeInt, "ESD fingers", default=4)

    def display_text_impl(self):
        return "OR1_ESD(nf=%d W=%.1f L=%.1f)" % (self.nf, self.w, self.l)

    def coerce_parameters_impl(self):
        super(OR1Esd, self).coerce_parameters_impl()
        self.nf = max(2, int(self.fingers))
        self.ring_width = max(2.0, self._snap(self.ring_width))
        self.type = "n"


class OR1Library(pya.Library):
    def __init__(self):
        self.description = "OR1 (OpenRule1um) devices"
        self.layout().register_pcell("OR1_CONTACT", OR1Contact())
        self.layout().register_pcell("OR1_VIA", OR1Via())
        self.layout().register_pcell("OR1_PAD", OR1Pad())
        self.layout().register_pcell("OR1_MOS", OR1Mos())
        self.layout().register_pcell("OR1_MOSGUARD", OR1MosGuard())
        self.layout().register_pcell("OR1_RES", OR1Res())
        self.layout().register_pcell("OR1_DIFFRES", OR1DiffRes())
        self.layout().register_pcell("OR1_DIODE", OR1Diode())
        self.layout().register_pcell("OR1_MOSCAP", OR1MosCap())
        self.layout().register_pcell("OR1_MOSMATCH", OR1MosMatch())
        self.layout().register_pcell("OR1_RESARRAY", OR1ResArray())
        self.layout().register_pcell("OR1_CAPARRAY", OR1CapArray())
        self.layout().register_pcell("OR1_ESD", OR1Esd())
        self.layout().register_pcell("OR1_RING", OR1Ring())
        self.layout().register_pcell("OR1_TAPLINE", OR1TapLine())
        self.register("or1_pcells")


if __name__ in ("__main__", "or1_pcells"):
    OR1Library()
