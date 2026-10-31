# OR1 (OpenRule1um) librelane technology configuration
# Process: 1um, 3 metal, 3.3V, variant OR1

set ::env(PROCESS) 1000
set ::env(DEF_UNITS_PER_MICRON) 1000

if { ![info exist ::env(STD_CELL_LIBRARY)] } {
	set ::env(STD_CELL_LIBRARY) or1_fd_sc
}
if { ![info exist ::env(STD_CELL_LIBRARY_OPT)] } {
	set ::env(STD_CELL_LIBRARY_OPT) or1_fd_sc
}

# Power nets
set ::env(VDD_PIN) "vdd"
set ::env(GND_PIN) "gnd"
set ::env(VDD_PIN_VOLTAGE) "3.30"
set ::env(GND_PIN_VOLTAGE) "0.00"
# Cell pins are uppercase VDD/VSS in the LEF; patterns are matched case
# sensitively by add_global_connection, so use the exact LEF pin names.
set ::env(SCL_POWER_PINS) "VDD"
set ::env(SCL_GROUND_PINS) "VSS"

# Technology LEF (same for all corners; single process point)
set ::env(TECH_LEF) "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/or1_fd_sc/lef/OR1.tlef"
set ::env(TECH_LEF_MIN) "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/or1_fd_sc/lef/OR1.tlef"
set ::env(TECH_LEF_MAX) "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/or1_fd_sc/lef/OR1.tlef"
set ::env(CELLS_LEF) [glob "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/or1_fd_sc/lef/or1_fd_sc.lef"]
set ::env(GDS_FILES) [glob "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/or1_fd_sc/gds/*.gds"]
set ::env(STD_CELL_LIBRARY_CDL) "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/or1_fd_sc/cdl/or1_fd_sc.cdl"

set ::env(GPIO_PADS_LEF) ""
set ::env(GPIO_PADS_PREFIX) ""

# Optimization library (same as main)
set ::env(TECH_LEF_OPT) "$::env(TECH_LEF)"
set ::env(CELLS_LEF_OPT) $::env(CELLS_LEF)
set ::env(GDS_FILES_OPT) $::env(GDS_FILES)
set ::env(STD_CELL_LIBRARY_OPT_CDL) $::env(STD_CELL_LIBRARY_CDL)

# SCL-specific config
source "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/librelane/$::env(STD_CELL_LIBRARY)/config.tcl"

# Timing corners (single corner)
set ::env(LIB) [dict create "*tt*" [list "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/or1_fd_sc/lib/or1_fd_sc_TT_3P3_25C.lib"]]
set ::env(DEFAULT_CORNER) "nom_tt_3P3_25C"
set ::env(STA_CORNERS) [list "nom_tt_3P3_25C" "min_tt_3P3_25C" "max_tt_3P3_25C"]
set ::env(TIMING_VIOLATION_CORNERS) [list "*tt*"]
set ::env(TIMING_VIOLATION_CORNERS_OPT) [list "*tt*"]

# Constraints (librelane requires these be set)
set ::env(CLOCK_UNCERTAINTY_CONSTRAINT) 0.25
set ::env(CLOCK_TRANSITION_CONSTRAINT) 0.15
set ::env(TIME_DERATING_CONSTRAINT) 5
set ::env(IO_DELAY_CONSTRAINT) 20

# RCX rulesets (none; use LVS-style estimation)
set ::env(RCX_RULESETS) [list]

# magic setup
set ::env(MAGIC_MAGICRC) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/magic/OR1.magicrc"
set ::env(MAGIC_TECH_FILE) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/magic/OR1.tech"
set ::env(MAGIC_PDK_SETUP) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/magic/OR1.tcl"

# klayout (not yet provided; placeholders)
set ::env(KLAYOUT_TECH) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/klayout/tech/OR1.lyt"
set ::env(KLAYOUT_PROPERTIES) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/klayout/tech/OR1.lyp"
set ::env(KLAYOUT_DEF_LAYER_MAP) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/klayout/tech/OR1.map"
set ::env(PRIMARY_GDSII_STREAMOUT_TOOL) "magic"

# netgen setup
set ::env(NETGEN_SETUP_FILE) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/netgen/OR1_setup.tcl"

# Welltap / endcap: none defined; use FILL
# A tap every 20um leaves only 17um gaps, but DFFPOSX1 is 52um wide and
# detailed placement then has nowhere to put it.  Keep the interval well
# above the widest macro.
set ::env(FP_TAPCELL_DIST) 70

# Tracks
set ::env(TRACKS_INFO_FILE) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/librelane/$::env(STD_CELL_LIBRARY)/tracks.info"

# Synth helper maps (trivial: use generic mappings provided by librelane if available)
set ::env(SYNTH_LATCH_MAP) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/librelane/$::env(STD_CELL_LIBRARY)/latch_map.v"
set ::env(TRISTATE_BUFFER_MAP) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/librelane/$::env(STD_CELL_LIBRARY)/tribuff_map.v"
set ::env(FULL_ADDER_MAP) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/librelane/$::env(STD_CELL_LIBRARY)/fa_map.v"
set ::env(RIPPLE_CARRY_ADDER_MAP) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/librelane/$::env(STD_CELL_LIBRARY)/rca_map.v"
set ::env(CARRY_SELECT_ADDER_MAP) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/librelane/$::env(STD_CELL_LIBRARY)/csa_map.v"
set ::env(NO_SYNTH_CELL_LIST) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/librelane/$::env(STD_CELL_LIBRARY)/no_synth.cells"
set ::env(DRC_EXCLUDE_CELL_LIST) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/librelane/$::env(STD_CELL_LIBRARY)/drc_exclude.cells"

# Parasitic estimation layers
set ::env(DATA_WIRE_RC_LAYER) "metal2"
set ::env(CLOCK_WIRE_RC_LAYER) "metal3"

# IO layer
set ::env(FP_IO_HLAYER) "metal3"
set ::env(FP_IO_VLAYER) "metal2"

# Routing layers
set ::env(RT_MIN_LAYER) "metal2"
set ::env(RT_MAX_LAYER) "metal3"
set ::env(RT_CLOCK_MIN_LAYER) "metal2"
set ::env(GRT_LAYER_ADJUSTMENTS) "0.5,0,0"

# PDN: rail on metal1 (cell rails), stripes on metal2/metal3
set ::env(FP_PDN_RAIL_LAYER) metal1
set ::env(FP_PDN_VERTICAL_LAYER) metal2
set ::env(FP_PDN_HORIZONTAL_LAYER) metal3
set ::env(FP_PDN_RAIL_OFFSET) 0
# Rails/straps must be >=2um wide: the M2_M1/M3_M2 vias need a 2x2um pad
# (1um cut + 0.5um enclosure). With 1um straps OpenROAD drops every via
# ("No via inserted between metal1 and metal2") and the grid floats.
set ::env(FP_PDN_RAIL_WIDTH) 2.0
set ::env(FP_PDN_VWIDTH) 2.0
set ::env(FP_PDN_HWIDTH) 2.0
set ::env(FP_PDN_VSPACING) 1.0
set ::env(FP_PDN_HSPACING) 1.0
# Single-layer (metal2) stripes: horizontal metal3 stripes land inside the
# 30um rows and make wide cells (DFFPOSX1 = 58.5um) illegal for detailed
# placement.  Rails -> metal2 vertical straps is enough for this library.
set ::env(FP_PDN_MULTILAYER) 0
set ::env(FP_PDN_VOFFSET) 19
set ::env(FP_PDN_VPITCH) 200
set ::env(FP_PDN_HOFFSET) 10
set ::env(FP_PDN_HPITCH) 120

set ::env(FP_PDN_CORE_RING_VWIDTH) 2.0
set ::env(FP_PDN_CORE_RING_HWIDTH) 2.0
set ::env(FP_PDN_CORE_RING_VSPACING) 1.0
set ::env(FP_PDN_CORE_RING_HSPACING) 1.0
set ::env(FP_PDN_CORE_RING_VOFFSET) 2
set ::env(FP_PDN_CORE_RING_HOFFSET) 2

set ::env(MACRO_BLOCKAGES_LAYER) "metal1 metal2 metal3"

#-----------------------------------------------------------------------------
# Signoff checks and parasitic extraction
#-----------------------------------------------------------------------------
# KLayout DRC (generic runset contract: -rd input/topcell/report)
set ::env(KLAYOUT_DRC_RUNSET) "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/klayout/drc/OR1.drc"
# A missing runset makes librelane's KLayout.DRC step skip silently, which
# would turn "0 violations" into "check not run".  Fail loudly instead.
if { ![file exists $::env(KLAYOUT_DRC_RUNSET)] } {
	error "OR1: KLayout DRC runset not found: $::env(KLAYOUT_DRC_RUNSET)"
}

# OpenRCX extraction rules (generated from the OR1 parasitic RC model)
if { ![info exists ::env(TECH_LEFS)] } {
	set ::env(TECH_LEFS) [dict create "*tt*" [list "$::env(PDK_ROOT)/$::env(PDK)/libs.ref/or1_fd_sc/lef/OR1.tlef"]]
}
set ::env(RCX_RULESETS) [dict create "*tt*" "$::env(PDK_ROOT)/$::env(PDK)/libs.tech/openroad/OR1.rcx_rules"]

# magic full parasitic extraction (R + C).  The RC model lives in the magic
# tech file (extract section: resist / areacap / contact).
set ::env(MAGIC_RCX_CTHRESH) 0.1
set ::env(MAGIC_RCX_DO_CAPACITANCE) 1
set ::env(MAGIC_RCX_DO_RESISTANCE) 1

# Filler cells are physical-only: they carry no devices and are not present in
# the synthesized netlist, so they must be ignored by LVS.
set ::env(LVS_FLATTEN_CELLS) [list FILL FILL_05 FILL_10 FILL_15 FILL_20 FILL_25]
