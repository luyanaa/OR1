# OR1_FRAME — OpenMPW PTC06 padframe (reconstructed)

The ISHI-KAI OpenMPW PTC06-2 repository does not ship a standalone frame GDS;
the pad ring only exists inside the assembled submission layout
(`Submitted/all_members_layout.gds`).  This directory contains the frame
extracted from it.

## Provenance

* source: `https://github.com/ishi-kai/ISHI-KAI_Multiple_Projects_OpenMPW_PTC06-2`
  → `Submitted/all_members_layout.gds` (branch `main`, 2 152 308 bytes)
* top cell in the source: `chip18_V9_OR1`
* reconstruction: keep only the frame children
  (`pad3512_V4_OR1`, `pad3512_V5_OR1`, `PAD60_V6_OR1`, `Via$7`), drop every
  member-project cell (OPAMPs, inverters, NAND/DFF, logos, `Via2$1` power
  hook-ups), prune unreachable cells, rename the top cell to `OR1_FRAME`.

## Contents

```
gds/or1_frame.gds     5 cells, top OR1_FRAME, 28 KB
```

| item | value |
|---|---|
| die extent | (−900, −900) … (900, 900) µm — **1.800 × 1.800 mm** |
| pads `pad3512_V4_OR1` | 64 |
| pads `pad3512_V5_OR1` | 8 |
| pads `PAD60_V6_OR1` | 9 |
| total pads | **81** |
| via arrays `Via$7` | 206 instances |

Pad cell names are the ones used by the upstream layout; `pad3512_*` are the
3.5 × 12 µm style pads, `PAD60_V6_OR1` the larger corner/power pads.

## Use

Read the frame as a top-level assembly template and place the design inside:

```sh
klayout OR1_FRAME.gds        # or:  gds read or1_frame.gds
```

The frame is hierarchy-preserving (pads stay as cells), so it can be merged
into another layout with `Layout#read` / cell references, or flattened if a
single-level template is preferred.

## Note

The upstream pin list (`docs/pin_list.pdf`) and the submission README define
the pad ordering; this GDS reproduces the geometry only (no pin names are
attached to the pad cells in the source layout).
