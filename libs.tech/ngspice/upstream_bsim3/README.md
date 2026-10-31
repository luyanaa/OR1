# Upstream BSIM3V3 device models

Source: `mineda-support/OpenRule1um` → `tech/tech/models/BSIM3V3N.mod`,
`BSIM3V3P.mod` (commit 85dbacfb05351c5116158f4d8e0d5c995d3b4ad1).

* LEVEL = 8 (BSIM3v3.3), TOX = 1.403e-8, VTH0 = 0.71559 (nch), U0 = 420.668
* model names: `nch` / `pch` (the LEVEL=1 set in `../OR1_models.spice` uses
  `NMOS` / `PMOS`; the characterisation netlists carry `nfet` / `pfet`)

Use these for electrical analysis that must agree with upstream.  The
LEVEL=1 file next to it is explicitly *virtual* ("tentative parameters") and
is only meant for fast functional simulation - it is not a characterised
process model and must be labelled as estimated wherever it is used.
