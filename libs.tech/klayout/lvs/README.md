# OR1 KLayout LVS

| file | purpose |
|---|---|
| `OR1.lvs` | extraction + comparison deck (MOS, poly/diff resistors, MOS capacitor, diode) |
| `run_lvs.sh` | one cell: extract, write SPICE, optionally compare |
| `check_lvs.sh` | every CDL cell: KLayout LVS + netgen (W/L), `LVS: PASS/FAIL` |
| `test_lvs_devices.sh` | passive devices with reference netlists + negative controls |
| `flatten_ref.py` | flattens the reference CDL for the comparer |

## Device model

* MOS: `mos4` with the channel from `diff & pol`; the substrate/well is the
  bulk terminal.
* Resistors: the body is the drawn region inside the RES marker **minus** the
  contacts, and `pol - res` / `diff - res` is used as the conducting layer so
  the two heads become two nets.  Sheet resistance: poly 20, n-diff 200,
  p-diff 2000 ohm/sq.
* MOS capacitor: poly plate over diffusion plate inside the CAP marker
  (1 fF/um^2).
* Diode: p+ anode inside the DIO marker, n-well as cathode.  *Open item* -
  both terminals currently resolve to one net (see
  `STATUS-2026-10-31-contract-conflicts.md` section 23.4).

## Notes

`netlist.flatten_circuit`, `purge`, `purge_nets` and `simplify` are not used:
in KLayout 0.30 they empty the netlist, which made `compare` trivially
succeed.  A reference with a missing transistor now correctly fails.

`make_top_level_pins` does not promote labeled nets of device-only circuits;
the deck promotes named top-level nets explicitly.

## Usage

```sh
libs.tech/klayout/lvs/check_lvs.sh        [report-dir]
libs.tech/klayout/lvs/test_lvs_devices.sh [report-dir]
```

Both exit non-zero on failure.
