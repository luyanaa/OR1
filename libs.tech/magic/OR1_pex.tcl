#-----------------------------------------------------------------------------
# OR1 (OpenRule1um) magic full parasitic extraction (PEX)
#
# Usage:
#   magic -dnull -noconsole -rcfile libs.tech/magic/OR1.magicrc \
#         OR1_pex.tcl -rcfile "" <gds-file> <top-cell> <out.spice>
#
# or simply:  OR1_pex.sh <gds-file> <top-cell> <out.spice>
#
# Produces a flattened SPICE netlist with
#   * M elements  : transistors from the extracted devices
#   * R elements  : distributed resistances (extresist), values from the
#                   `resist` lines of the tech file
#   * C elements  : node capacitances (areacap) above MAGIC_PEX_CTHRESH
#
# The RC model lives in the tech file extract section:
#   poly 20 ohm/sq, nwell 1.1 kohm/sq, pact/nact 42 ohm/sq,
#   metal1/2/3 0.028 ohm/sq (Al, rho=2.8e-8 ohm*m, t=1.0 um),
#   areacap 0.035 fF/um^2 for metals, 0.060 for poly.
#-----------------------------------------------------------------------------

# magic passes the script name as argv[0]; take the last three arguments
if {[llength $argv] < 3} {
    puts "usage: OR1_pex.tcl <gds-file> <top-cell> <out.spice>"
    quit
}
lassign [lrange $argv end-2 end] gdsfile topcell outspice

drc off
crashbackups disable
locking disable

puts "OR1 PEX: reading $gdsfile"
gds read $gdsfile
load $topcell
select top cell

# Magic >= 8.3.597 computes .res.ext in sequence with the normal extraction
# when `extract do resistance` is on, so the old ext2sim/extresist dance is
# not needed.
#
# `extresist threshold` is a cutoff in MILLIOHMS on the lumped node
# resistance.  The default is 10 ohm, which silently drops every on-chip
# metal segment (a 100 um x 2 um metal2 wire is only 1.4 ohm) and leaves the
# netlist with zero resistors.  Set it (and `minres`, default 1 ohm) to 0 so
# the whole network is kept.  These are set here rather than in OR1.magicrc
# because `extract style` (used by some flows) resets them.
extresist threshold 0
extresist minres 0

# local parasitic extraction with capacitance and resistance.
extract do local
extract do capacitance
extract do resistance
extract do coupling
extract do adjust
extract do unique
extract all

# The GDS carries pin labels but no magic "port" properties, so flatten the
# output hierarchy; caps to the substrate are then written as grounded caps.
ext2spice lvs
ext2spice hierarchy off
ext2spice cthresh 0.1
ext2spice rthresh 0
ext2spice extresist on
ext2spice -f ngspice -o $outspice

puts "OR1 PEX: wrote $outspice"
quit
