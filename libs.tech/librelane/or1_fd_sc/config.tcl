# OR1 standard cell library config for librelane

# Three profiles: synthesis/typical use the TT 5.0 V corner; SS/FF are
# estimated voltage corners for fast/slow analysis.
set ::env(LIB_SYNTH) "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/or1_fd_sc/lib/or1_fd_sc_TT_5P0_25C.lib"
set ::env(LIB_TYPICAL) $::env(LIB_SYNTH)
set ::env(LIB_SLOWEST) "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/or1_fd_sc/lib/or1_fd_sc_SS_4P5_85C.lib"
set ::env(LIB_FASTEST) "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/or1_fd_sc/lib/or1_fd_sc_FF_5P5_0C.lib"

# No mux/adder helper cells in this library
set ::env(SYNTH_MUX4_MAP) ""
set ::env(SYNTH_MUX_MAP) ""

# Placement site
set ::env(PLACE_SITE) "unit"
set ::env(PLACE_SITE_WIDTH) 1.0
set ::env(PLACE_SITE_HEIGHT) 30.0

# No welltap/endcap/decap/diode/antenna cells in this library; reuse FILL
set ::env(FP_WELLTAP_CELL) "TAP"
set ::env(FP_ENDCAP_CELL) "FILL"
set ::env(DECAP_CELL) ""
set ::env(DIODE_CELL) ""
set ::env(FAKEDIODE_CELL) ""

# Driving cell / min buf / tie cells
set ::env(SYNTH_DRIVING_CELL) "INVX1"
set ::env(SYNTH_DRIVING_CELL_PIN) "Y"
set ::env(OUTPUT_CAP_LOAD) "50.0"
set ::env(SYNTH_MIN_BUF_PORT) "BUFX2 A Y"
# No dedicated tie cells: use BUFX2 with constant input? librelane requires a cell
# Use BUFX2 output for tiehi and tie through inverter for tielo is not ideal;
# simplest: point both at BUFX2 and rely on netlist not needing tie cells.
set ::env(SYNTH_TIEHI_CELL) "TIEHI/Y"
set ::env(SYNTH_TIELO_CELL) "TIELO/Y"

# CTS
set ::env(CELL_CLK_PORT) "CLK"
set ::env(CTS_ROOT_BUFFER) "BUFX2"
set ::env(ROOT_CLK_BUFFER) "BUFX2"
set ::env(CTS_CLK_BUFFER_LIST) "BUFX2"

set ::env(PL_LIB) $::env(LIB_TYPICAL)

set ::env(FILL_CELL) "FILL_25 FILL_20 FILL_15 FILL_10 FILL_05"
set ::env(RE_BUFFER_CELL) "BUFX2"

set ::env(GPL_CELL_PADDING) {0}
set ::env(DPL_CELL_PADDING) {0}
set ::env(CELL_PAD_EXCLUDE) "FILL"

set ::env(CTS_MAX_CAP) 1.5
set ::env(MAX_TRANSITION_CONSTRAINT) 1.0
set ::env(MAX_FANOUT_CONSTRAINT) 10
set ::env(MAX_CAPACITANCE_CONSTRAINT) 0.2

# NOTE: MAGIC_DRC_MAGLEFS and MAGIC_EXT_ABSTRACT_CELLS are librelane
# config variables (not env vars); set them in the design config.yaml,
# e.g. MAGIC_DRC_MAGLEFS: [pdk::or1_fd_sc/maglef/*.mag].
# CELL_SPICE_MODELS below IS honored (read by read_pdk_spice in magic).
# Annotate abstracted-cell port order from the reference CDL during
# LVS extraction (magic readspice). Pin names in the cell GDS match
# the CDL pin names (fixed 2026-10-31: X->Y, CK->CLK, stray A removed).
set ::env(CELL_SPICE_MODELS) "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/or1_fd_sc/cdl/or1_fd_sc.cdl"
