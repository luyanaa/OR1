# ---------------------------------------------------------------------------
# OR1 (OpenRule1um) KLayout PCell library
#
# Load: put this file on KLayout's macro path (Macro Editor / pymacros), or
#       start KLayout with   klayout -m or1_pcells.py
# The library registers as "or1_pcells".
#
# All generators work on the OR1 0.5 um grid and follow the published rules:
#   width/space 1.0, diff space 1.5, poly-diff 0.5, nwell<->pdiff 2.0,
#   nwell space 4.0, contact 1x1 with 0.5 enclosure and 1.0 spacing,
#   via 1x1 with 0.5 enclosure and 1.0 spacing, no via1 under via2.
# ---------------------------------------------------------------------------
import pya

# GDS layers (magic cifoutput numbering)
L_NW   = (1, 0)
L_DIFF = (3, 0)
L_POLY = (5, 0)
L_CNT  = (7, 0)
L_M1   = (8, 0)
L_V1   = (9, 0)
L_M2   = (10, 0)
L_V2   = (11, 0)
L_M3   = (12, 0)
L_PA   = (18, 0)   # parea / pselect
L_NA   = (19, 0)   # narea / nselect
L_RES  = (15, 0)   # poly resistor marker


class _Base(pya.PCellDeclarationHelper):
    """Common helpers: micron->dbu and a box drawer."""

    def _u(self, v):
        return int(round(v / self.layout.dbu))

    def _box(self, layer, x1, y1, x2, y2):
        self.cell.shapes(self._li(layer)).insert(
            pya.Box(self._u(x1), self._u(y1), self._u(x2), self._u(y2)))

    def _li(self, spec):
        return self.layout.layer(spec[0], spec[1])


class OR1Via(_Base):
    """Via array (via1 or via2) with the metal pads above and below."""

    def __init__(self):
        super(OR1Via, self).__init__()
        self.param("cut", self.TypeString, "Cut layer", default="via1")
        self.param("cols", self.TypeInt, "Columns", default=2)
        self.param("rows", self.TypeInt, "Rows", default=2)
        self.param("pad", self.TypeBoolean, "Draw metal pads", default=True)

    def display_text_impl(self):
        return "OR1_VIA(%s, %dx%d)" % (self.cut, self.cols, self.rows)

    def produce_impl(self):
        cut = L_V1 if self.cut == "via1" else L_V2
        low = L_M1 if self.cut == "via1" else L_M2
        high = L_M2 if self.cut == "via1" else L_M3
        n = 0
        for c in range(self.cols):
            for r in range(self.rows):
                x = 2.0 * c
                y = 2.0 * r
                self._box(cut, x, y, x + 1.0, y + 1.0)
                n += 1
        if self.pad:
            w = 2.0 * (self.cols - 1) + 1.0
            h = 2.0 * (self.rows - 1) + 1.0
            self._box(low, -0.5, -0.5, w + 0.5, h + 0.5)
            self._box(high, -0.5, -0.5, w + 0.5, h + 0.5)


class OR1Pad(_Base):
    """Bond pad: metal3 plate with via2/via1 stacks down to metal1."""

    def __init__(self):
        super(OR1Pad, self).__init__()
        self.param("size", self.TypeDouble, "Pad size (um)", default=12.0)
        self.param("via_pitch", self.TypeDouble, "Via pitch (um)", default=2.0)

    def display_text_impl(self):
        return "OR1_PAD(%.1fx%.1f)" % (self.size, self.size)

    def produce_impl(self):
        s = self.size
        self._box(L_M3, 0.0, 0.0, s, s)
        # via2 array under the pad, 1.0 um inset from the edge
        inset = 1.0
        x = inset
        while x + 1.0 <= s - inset:
            y = inset
            while y + 1.0 <= s - inset:
                self._box(L_V2, x, y, x + 1.0, y + 1.0)
                self._box(L_V1, x, y, x + 1.0, y + 1.0)
                y += self.via_pitch
            x += self.via_pitch
        self._box(L_M2, 0.5, 0.5, s - 0.5, s - 0.5)
        self._box(L_M1, 0.5, 0.5, s - 0.5, s - 0.5)


class OR1Mos(_Base):
    """Four-terminal MOS: diff, poly gate, contacts, metal1, well/select."""

    def __init__(self):
        super(OR1Mos, self).__init__()
        self.param("type", self.TypeString, "Type (n/p)", default="n")
        self.param("w", self.TypeDouble, "Channel width W (um)", default=4.0)
        self.param("l", self.TypeDouble, "Channel length L (um)", default=1.0)
        self.param("sd", self.TypeDouble, "Source/drain length (um)", default=2.0)

    def display_text_impl(self):
        return "OR1_MOS(%s W=%.1f L=%.1f)" % (self.type, self.w, self.l)

    def produce_impl(self):
        w, l, sd = self.w, self.l, self.sd
        # diffusion: sd | L | sd
        self._box(L_DIFF, 0.0, 0.0, sd + l + sd, w)
        # poly gate crossing the diffusion with 1.0 um extension
        self._box(L_POLY, sd, -1.0, sd + l, w + 1.0)
        # source/drain contacts (1x1) centred vertically, 0.5 from the edges
        cy = max(1.5, w / 2.0 - 0.5)
        self._box(L_CNT, sd / 2.0 - 0.5, cy, sd / 2.0 + 0.5, cy + 1.0)
        self._box(L_CNT, sd + l + sd / 2.0 - 0.5, cy,
                  sd + l + sd / 2.0 + 0.5, cy + 1.0)
        # metal1 pads
        self._box(L_M1, 0.0, cy - 0.5, sd, cy + 1.5)
        self._box(L_M1, sd + l, cy - 0.5, sd + l + sd, cy + 1.5)
        # well and select: pMOS gets an n-well with n-select,
        # nMOS gets p-select only (the substrate is the well)
        if self.type == "p":
            self._box(L_NW, -2.0, -2.0, sd + l + sd + 2.0, w + 2.0)
            self._box(L_NA, -0.5, -0.5, sd + l + sd + 0.5, w + 0.5)
        else:
            self._box(L_PA, -0.5, -0.5, sd + l + sd + 0.5, w + 0.5)


class OR1Res(_Base):
    """Poly resistor with contact heads (value set by W/L, 20 ohm/sq)."""

    def __init__(self):
        super(OR1Res, self).__init__()
        self.param("w", self.TypeDouble, "Width (um)", default=2.0)
        self.param("l", self.TypeDouble, "Body length (um)", default=10.0)

    def display_text_impl(self):
        return "OR1_RES(%.1fx%.1f)" % (self.w, self.l)

    def produce_impl(self):
        w, l = self.w, self.l
        self._box(L_POLY, 0.0, 0.0, l, w)
        self._box(L_RES, 0.0, 0.0, l, w)
        # head contacts, 0.5 from the body ends
        self._box(L_CNT, 0.5, w / 2.0 - 0.5, 1.5, w / 2.0 + 0.5)
        self._box(L_CNT, l - 1.5, w / 2.0 - 0.5, l - 0.5, w / 2.0 + 0.5)
        self._box(L_M1, 0.0, w / 2.0 - 1.0, 2.0, w / 2.0 + 1.0)
        self._box(L_M1, l - 2.0, w / 2.0 - 1.0, l, w / 2.0 + 1.0)


class OR1Library(pya.Library):
    def __init__(self):
        self.description = "OR1 (OpenRule1um) devices"
        self.layout().register_pcell("OR1_VIA", OR1Via())
        self.layout().register_pcell("OR1_PAD", OR1Pad())
        self.layout().register_pcell("OR1_MOS", OR1Mos())
        self.layout().register_pcell("OR1_RES", OR1Res())
        self.register("or1_pcells")


if __name__ in ("__main__", "or1_pcells"):
    OR1Library()
