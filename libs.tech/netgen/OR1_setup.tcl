#---------------------------------------------------------------
# Netgen LVS setup file for OR1 (OpenRule1um)
#---------------------------------------------------------------

# Cells without devices (fillers) can be ignored in LVS
ignore class {-circuit1 FILL}
ignore class {-circuit2 FILL}

permute default
property default

# Remove parasitic device parameters that may differ between
# schematic and layout extraction
property {-circuit1 nfet} remove ad pd as ps
property {-circuit1 pfet} remove ad pd as ps
property {-circuit2 nfet} remove ad pd as ps
property {-circuit2 pfet} remove ad pd as ps

# Device model equivalences between layout-extracted names
# (pcell names from Glade / magic extraction) and schematic names
equate class {-circuit1 nchOR1ex} {-circuit2 nfet}
equate class {-circuit1 nch} {-circuit2 nfet}
equate class {-circuit1 pchOR1ex} {-circuit2 pfet}
equate class {-circuit1 pch} {-circuit2 pfet}
equate class {-circuit1 rpolyOR1_ex} {-circuit2 rpoly}
equate class {-circuit1 rpolyOR1} {-circuit2 rpoly}

# Flatten both hierarchies to compare at device level: the layout
# extraction surfaces per-tap substrate nodes as extra subckt pins,
# which prevents a clean hierarchical pin-for-pin match.
flatten class {-circuit1 *}
flatten class {-circuit2 *}
