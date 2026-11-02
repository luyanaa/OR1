# OR1 KLayout technology and PCell library

```
tech/OR1.lyt            technology (dbu 0.001, layer properties, pcell library)
tech/OR1.lyp            layer properties / colours
tech/OR1.map            GDS layer map
pymacros/or1_pcells.py  PCell library  ->  library name "or1_pcells"
pymacros/test_pcells.py builds one instance of every PCell
pymacros/verify_pcells.py round-trip check (GDS write -> re-read -> compare)
pymacros/example_pcells.gds  output of test_pcells.py
drc/OR1.drc             signoff DRC deck
lvs/OR1.lvs, lvs/run_lvs.sh  signoff LVS
```

## Technology file

`tech/OR1.lyt` is the technology named **OR1** (0.001 um database unit). It
references `OR1.lyp` for layer colours and `../pymacros/or1_pcells.py` for the
device library. Layer numbers used by the PCells are the PDK ones:

| layer | GDS | | layer | GDS |
|---|---|---|---|---|
| NWL | 1/0 | | ML2 | 10/0 |
| DIFF | 3/0 | | VIA2 | 11/0 |
| POL | 5/0 | | ML3 | 12/0 |
| HPOL | 6/0 | | FRAME | 14/0 |
| CNT | 7/0 | | RES | 15/0 |
| ML1 | 8/0 | | Parea | 18/0 |
| VIA1 | 9/0 | | Narea | 19/0 |

## Grid policy

| quantity | value | role |
|---|---|---|
| KLayout database unit | 0.001 um | layout precision |
| OR1 manufacturing grid (`MANUFACTURINGGRID`) | 0.1 um | mask grid |
| upstream off-grid check (DRC v1.52, `min_grid`) | 0.05 um | legality |
| PCell snap grid (`GRID` in `or1_pcells.py`) | **0.5 um** | device geometry |

The PCells snap every dimension to 0.5 um, which is a multiple of 0.5/0.1/0.05,
so the same geometry is legal under the v1.51 deck shipped here and under the
v1.52 deck's 0.05 um off-grid check.  The 0.001 um dbu only exists so DEF/LEF
input is not quantised; no PCell emits geometry off the 0.5 um grid.

## PCells

Ported from the upstream `OpenRule1um_v2` set (`pcells_v2.lym` v2.99,
S. Moriyama).  The upstream classes inherit all geometry from `MinedaPCell` /
`OpenRule1um_Basic`, which are not part of this PDK, so the *device contract*
(parameters and rules) was re-implemented on the Python PCell API.

| PCell | parameters | upstream equivalent |
|---|---|---|
| `OR1_CONTACT` | `on` (diff/poly), `cols`, `rows`, `pitch`, `metal` | contact arrays used by every device |
| `OR1_VIA` | `cut` (via1/via2), `cols`, `rows`, `pitch`, `pad` | via arrays |
| `OR1_MOS` | `type` (n/p), `w`, `l`, `sd`, `nf`, `gate_contact`, `body_tie` (none/local), `with_via` | `Nch`, `Pch` |
| `OR1_MOSGUARD` | same as `OR1_MOS` + `ring_width`, `ring_gap` | `Nch/Pch` + `Psub/Nsub_ring` |
| `OR1_RES` | `w`, `l`, `hr` | `R_poly`, `HR_poly` |
| `OR1_DIFFRES` | `type` (n/p), `w`, `l` | `R_ndiff`, `R_pdiff` |
| `OR1_DIODE` | `w`, `h`, `gap` | diode (annotation DIO) |
| `OR1_MOSCAP` | `w`, `h`, `l` | MOS capacitor |
| `OR1_RING` | `type` (p/n), `w`, `h`, `t` | `Psub_ring`, `Nsub_ring` |
| `OR1_TAPLINE` | `type` (p/n), `length`, `width` | `Psub_line`, `Nsub_line` |
| `OR1_MOSMATCH` | `OR1_MOS` + `gap` | mirrored pair |
| `OR1_RESARRAY` | `w`, `l`, `hr`, `count`, `pitch` | unit resistor row |
| `OR1_CAPARRAY` | `w`, `h`, `l`, `cols`, `rows` | unit capacitor matrix |
| `OR1_ESD` | `fingers` | guarded multi-finger NMOS template |
| `OR1_PAD` | `size`, `via_pitch` | (bond pad, not upstream) |

### Semantics

* `OR1_MOS.w` is the **width of one finger**; the effective width is
  `w * nf` and is printed in `display_text`.  Neighbouring fingers share their
  S/D diffusion strip (`sd` long), matching the upstream `nf` behaviour.
* `body_tie` = `local` adds a tap strip 1.5 um below the channel (p-select for
  nMOS, n-select inside the shared n-well for pMOS); `none` leaves the body
  floating so the caller can place `OR1_RING`/`OR1_TAPLINE` explicitly.
* `OR1_RES.hr` draws `POL + HPOL` and enforces the upstream HIPOL rules:
  HPOL encloses POL by 5 um and the body between the contact heads must be
  22-82 um (length clamped to 25-85 um).
* Invalid input is never turned into illegal geometry: every PCell implements
  `coerce_parameters_impl`, which snaps to the grid and clamps to the legal
  minimum (e.g. `l >= 1.0`, `w >= 2.0` for a 1x1 contact with 0.5 enclosure,
  `cols/rows >= 1`, ring `t >= 2.0`).

## Loading the library

The technology references the library, so opening the OR1 technology in the
KLayout GUI registers `or1_pcells`. If your KLayout build does not auto-load
technology PCell libraries, use either route:

```sh
# 1. explicit load (batch or GUI)
klayout -m /path/to/OR1PDK/OR1/libs.tech/klayout/pymacros/or1_pcells.py

# 2. make it permanent: link the macro into the KLayout macro path
ln -s /path/to/OR1PDK/OR1/libs.tech/klayout/pymacros/or1_pcells.py \
      ~/.klayout/pymacros/or1_pcells.py
```

The PCells then appear in *Tools > Manage PCells* as **OR1 (OpenRule1um)
devices**.  From Python:

```python
import or1_pcells                       # registers the library
cell = layout.create_cell("OR1_MOS", "or1_pcells",
                          {"type": "n", "w": 4.0, "l": 1.0, "nf": 2})
```

## Verification

`test_pcells.py` builds 22 instances (positive cases and variants) into
`example_pcells.gds`; `verify_pcells.py` re-reads the exported GDS and
compares shape counts and bounding boxes per cell.

```sh
klayout -b -r pymacros/test_pcells.py
klayout -b -r pymacros/verify_pcells.py          # ROUND-TRIP: PASS
for c in T_CNT_DIFF T_CNT_POLY T_VIA1 T_VIA2 T_PAD T_MOSN1 T_MOSN4 \
         T_MOSP2 T_MOSNTIE0 T_MOSVIA T_GUARDN T_GUARDP T_RES T_HRES \
         T_RINGP T_RINGN T_LINEP T_LINEN; do
  klayout -b -r drc/OR1.drc -rd input=/tmp/or1_pcells_test.gds \
          -rd topcell=$c -rd report=/tmp/$c.lyrdb
  echo "$c: $(grep -c '<item>' /tmp/$c.lyrdb)"
done
```

Last run: **22/22 cells 0 violations**, round-trip PASS.

The PCells are layout generators only - they do not carry connectivity. Use
the PDK LVS deck for extracted netlists.
