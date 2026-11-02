# OR1 OpenRCX / parasitics

| file | purpose |
|---|---|
| `OR1.rcx_rules` | OpenRCX extraction rules (3 metals, OR1 geometry) |
| `gen_rcx_rules.py` | generates the ruleset from the OR1 RC model |
| `check_rcx_rules.py` | structural + numeric validation, exits non-zero on failure |

## What the ruleset used to be

The first version was produced by rewriting the electrical columns of a table
taken from a *different* process and passing everything else through.  Three
defects survived that:

1. **`LayerCount 10`** with `Metal 1..10` sections, while OR1 is a 3-metal
   process (`metal1`, `via1`, `metal2`, `via2`, `metal3` in `OR1.tlef`).
2. **Width grid 0.07 .. 0.8 um** - below the LEF routing width of 1.0 um.
   OpenRCX clamps to the widest entry, so a 1.0 um OR1 wire was extracted as
   a 0.8 um wire (R 25 % high) and the area/fringe terms were wrong too.
3. **Constant coupling column** - the rewrite printed a fixed `5e-05` for every
   spacing, so the capacitance no longer depended on distance at all.

The tables also carried 0.07 um-class *spacings*, three orders of magnitude
below anything OR1 can draw.

## What it is now

`gen_rcx_rules.py` emits the table from OR1's own parameters:

| layer | t (um) | Rs = rho/t | LEF RPERSQ | rules R column |
|---|---|---|---|---|
| metal1 | 0.55 | 0.0509 | 0.0509 | 5.09091e-05 ohm/nm |
| metal2 | 0.65 | 0.0431 | 0.0431 | 4.30769e-05 ohm/nm |
| metal3 | 0.90 | 0.0311 | 0.0311 | 3.11111e-05 ohm/nm |

* geometry: widths 1 / 2 / 4 / 8 um, spacings 1 .. 16 um
* area cap 0.035 fF/um^2, fringe 0.050 fF/um
* coupling `CC(s) = eps0 * eps_r * t / s` (sidewall, per um of length)
* section inventory follows the stack: `RESOVER k` / `OVER k` for layers below
  (`k = 0` is the substrate), `UNDER j` / `DIAGUNDER j` for layers above

## Cross-check of the constants

Three independent sources agree:

| quantity | LEF | magic tech (`OR1.tech`) | RCX rules |
|---|---|---|---|
| metal1 sheet R | 0.0509 ohm/sq | 51 milliohm/sq | 0.0509 ohm/sq |
| metal2 sheet R | 0.0431 | 43 | 0.0431 |
| metal3 sheet R | 0.0311 | 31 | 0.0311 |
| metal area cap | 3.5e-05 fF/um^2 | 9 aF/lambda^2 = 0.036 fF/um^2 | 3.5e-05 |

The diffusion sheet resistance used by the LVS deck was corrected at the same
time: it carried 200 / 2000 ohm/sq (a guess) while the tech file records the
*measured* 42 ohm/sq for both n+ and p+ (`pact 42`, `nact = pact`).  The
extracted value of the 2 x 10 um test resistor is now 126 ohm (3 squares).

## Via resistance

`dumpRCValues` in the last librelane run reported **cut resistance 0** for both
via1 and via2, i.e. ideal vias.  The tech LEF now carries
`RESISTANCE 1.0 ;` on `M2_M1` and `M3_M2`, matching the magic tech
(`contact m2c/m3c 2 1000`, i.e. 1 ohm per via).

## Validation

```sh
python3 check_rcx_rules.py [OR1.rcx_rules]
```

Checks the layer count against the LEF, that no section references a
non-existent layer, that every DIST block declares its real row count, that
the width grid covers the LEF routing width, that spacings increase, that no
column is negative, and that the resistance column reproduces the LEF RPERSQ.

Current result:

```
layers   : LayerCount=3, metal sections=[1, 2, 3], LEF routing layers=['metal1', 'metal2', 'metal3']
sections : 28
widths   : [1.0, 2.0, 4.0, 8.0] (max 8 um)
R checks : 30 rows matched LEF RPERSQ
RCX RULES: PASS
```

The previous file fails the same check:

```
  - LayerCount 10 but the LEF defines 3 routing layers
  - width grid stops at 0.8 um but metal1 is 1 um wide
  - width grid stops at 0.8 um but metal2 is 1 um wide
  - width grid stops at 0.8 um but metal3 is 1 um wide
```

## Not verified here

OpenROAD / librelane are not installed in this environment, so the ruleset has
**not** been through a live `extract_parasitics` run.  The checks above are
structural and arithmetic; the first machine with OpenROAD must run a routed
design and compare the SPEF against an independent extraction (magic PEX) on
the same net before RC sign-off.
