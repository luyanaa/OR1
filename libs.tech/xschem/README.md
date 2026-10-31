# OR1 — xschem

Symbol library and configuration for the OR1 (OpenRule1um) 1 µm CMOS PDK,
derived from the original OpenRule1um LTspice library
(`KLayout/OpenRule1um/tech/tech/symbols/LTspice/OR1LIB/*.asy`).

```
libs.tech/xschem/
├── xschemrc          # library path + netlist settings
├── mk_syms.py        # .asy -> .sym converter (re-run if OR1LIB changes)
└── symbols/          # 19 xschem symbols
```

## Symbols

| group | symbols |
|---|---|
| MOS | `NMOS`, `PMOS`, `NMOST`, `PMOST`, `MOSCAPT`, `NMOS_ESD`, `PMOS_ESD` |
| diodes | `NDIO`, `PDIO`, `diode_nwell_V4`, `diode_pwell_V4` |
| resistors | `R_POLY`, `R_POLYT`, `HR_POLY`, `HR_POLYT`, `RDIF`, `presistor` |
| capacitors | `CAP`, `pcapacitor` |

Each symbol carries the same SPICE device letter and model name as the LTspice
original (`SYMATTR Prefix` / `SYMATTR Value`), and the same pin names, ordered
by the original `SpiceOrder` so that `@pinlist` expands to the right
`D G S B` / `PLUS MINUS` order.  Body geometry is the OR1LIB drawing scaled
0.5× onto the 8-unit xschem grid.

## Use

```sh
OR1_ROOT=/path/to/OR1PDK/OR1 \
xschem -rcfile $OR1_ROOT/libs.tech/xschem/xschemrc my_tb.sch
```

Add the device models to the testbench (a `code` block, or in the netlist):

```
.include /path/to/OR1PDK/OR1/libs.tech/ngspice/OR1_models.spice
```

The models are `LEVEL=1` cards (`NMOS`, `PMOS`) plus the poly resistor and diode
models; the characterisation deck `libs.tech/ngspice/or1_char.py` uses the same
file.

## Regenerating

```sh
python3 mk_syms.py \
  /path/to/MakeLSI_OpenRule1um/KLayout/OpenRule1um/tech/tech/symbols/LTspice/OR1LIB \
  symbols
```
