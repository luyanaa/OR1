// or1_fd_sc_bb.v — black-box port-only models for yosys.
//
// yosys 0.70 (nix-pinned in this environment) drops the `if` keyword when it
// re-writes `always @(posedge CLK or posedge RESET)` blocks through
// read_verilog -lib / write_verilog, producing syntactically invalid output
// that crashes the json-header and verilator-lint steps.  Black-box models
// only need the port list for link_design, so this file strips every module
// body to its port declarations.  The functional models live in or1_fd_sc.v
// (used by verilator/netlistsim where full behaviour is required).


module INVX1 (A, Y);
  input A ;
  output Y ;
endmodule

module BUFX2 (A, Y);
  input A ;
  output Y ;
endmodule

module NAND2X1 (A, B, Y);
  input A ;
  input B ;
  output Y ;
endmodule

module NOR2X1 (A, B, Y);
  input A ;
  input B ;
  output Y ;
endmodule

module DFFPOSX1 (CLK, D, Q, QB);
  input CLK ;
  input D ;
  output Q ;
  output QB ;
endmodule

module TIEHI (Y);
  output Y ;
endmodule

module TIELO (Y);
  output Y ;
endmodule

module DECAPX1 (VDD, VSS);
  input VDD ;
  input VSS ;
endmodule

module ENDCAPX1 (VDD, VSS);
  input VDD ;
  input VSS ;
endmodule

module ANTENNAX1 (VDD, VSS, DIODE);
  input VDD ;
  input VSS ;
  inout DIODE ;
endmodule

module CLKBUFX2 (A, Y);
  input A ;
  output Y ;
endmodule

module DFFRX1 (CLK, D, Q, QB, RESET);
  input CLK ;
  input D ;
  input RESET ;
  output Q ;
  output QB ;
endmodule

module DFFRX2 (CLK, D, Q, QB, RESET);
  input CLK ;
  input D ;
  input RESET ;
  output Q ;
  output QB ;
endmodule
