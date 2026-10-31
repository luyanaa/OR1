# OR1 KLayout technology and PCell library

```
tech/OR1.lyt            technology (dbu 0.001, layer properties, pcell library)
tech/OR1.lyp            layer properties / colours
tech/OR1.map            GDS layer map
pymacros/or1_pcells.py  PCell library  ->  library name "or1_pcells"
pymacros/test_pcells.py self-test (builds one instance of each PCell)
pymacros/example_pcells.gds  output of the self-test
drc/OR1.drc             signoff DRC deck
lvs/OR1.lvs, lvs/run_lvs.sh  signoff LVS
```

## Technology file

`tech/OR1.lyt` is the technology named **OR1** (0.001 um database unit, the
same grid as the PDK GDS). It references `OR1.lyp` for the layer colours and
`../pymacros/or1_pcells.py` for the device library. The layer numbers used by
the PCells are the PDK ones:

| layer | GDS |
|---|---|
| NWL | 1/0 |
| DIFF | 3/0 |
| POL | 5/0 |
| CNT | 7/0 |
| ML1 | 8/0 |
| VIA1 | 9/0 |
| ML2 | 10/0 |
| VIA2 | 11/0 |
| ML3 | 12/0 |
| RES | 15/0 |
| FRAME | 14/0 |
| Parea | 18/0 |
| Narea | 19/0 |

## PCells

All generators work on the 0.5 um grid and follow the published OR1 rules
(minimum width/space 1.0, diff space 1.5, poly-diff 0.5, nwell-to-pdiff 2.0,
nwell space 4.0, contact/via 1x1 with 0.5 enclosure and 1.0 spacing).

| PCell | parameters | description |
|---|---|---|
| `OR1_VIA` | `cut` = via1/via2, `cols`, `rows`, `pad` | via array with metal pads above and below (0.5 um enclosure) |
| `OR1_PAD` | `size`, `via_pitch` | bond pad: ML3 plate with via2/via1 stack down to ML1 (1.0 um inset, 2.0 um pitch) |
| `OR1_MOS` | `type` = n/p, `w`, `l`, `sd` | four-terminal MOS: DIFF, POL gate (1.0 um overhang), source/drain contacts + ML1, Parea or NWL+Narea |
| `OR1_RES` | `w`, `l` | poly resistor with RES marker and two contact heads (20 ohm/sq) |

`OR1_VIA` and `OR1_MOS` produce geometry that is legal under the signoff deck;
`OR1_PAD` and `OR1_RES` likewise for their own shapes (see verification below).

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

The PCells then appear in *Tools > Manage PCells* / the library list as
**OR1 (OpenRule1um) devices**, and are available in the "New PCell" dialog.

From Python (e.g. inside librelane or a KLayout script):

```python
import or1_pcells                       # registers the library
cell = layout.create_cell("OR1_MOS", "or1_pcells",
                          {"type": "n", "w": 4.0, "l": 1.0, "sd": 2.0})
```

## Verification

`pymacros/test_pcells.py` builds `pymacros/example_pcells.gds` with one
instance of each PCell. Running the signoff deck on every generated cell
gives **0 violations**:

```sh
klayout -b -r test_pcells.py
for c in T_VIA1 T_VIA2 T_PAD T_MOSN T_MOSP T_RES; do
  klayout -b -r ../drc/OR1.drc -rd input=/tmp/or1_pcells_test.gds \
          -rd topcell=$c -rd report=/tmp/$c.lyrdb
  echo "$c: $(grep -c '<item>' /tmp/$c.lyrdb)"
done
```

Result at the time of writing: all six cells report `0`.

The PCells are layout generators only - they do not carry connectivity. Use
the PDK LVS deck for extracted netlists.
