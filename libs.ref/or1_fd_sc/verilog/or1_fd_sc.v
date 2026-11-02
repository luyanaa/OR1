`timescale 1ns/10ps
`celldefine
module INVX1 (A, Y);
input  A ;
output Y ;

   not (Y, A);

   specify
   endspecify

endmodule
`endcelldefine

`timescale 1ns/10ps
`celldefine
module BUFX2 (A, Y);
input  A ;
output Y ;

   buf (Y, A);

   specify
   endspecify

endmodule
`endcelldefine

`timescale 1ns/10ps
`celldefine
module NAND2X1 (A, B, Y);
input  A ;
input  B ;
output Y ;

   nand (Y, A, B);

   specify
   endspecify

endmodule
`endcelldefine

`timescale 1ns/10ps
`celldefine
module NOR2X1 (A, B, Y);
input  A ;
input  B ;
output Y ;

   nor (Y, A, B);

   specify
   endspecify

endmodule
`endcelldefine

`timescale 1ns/10ps
`celldefine
module DFFPOSX1 (CLK, D, Q, QB);
input  CLK ;
input  D ;
output Q ;
output QB ;
reg Q ;

   assign QB = ~Q;

   always @(posedge CLK)
      Q <= D;

   specify
   endspecify

endmodule
`endcelldefine

module TIEHI (Y);
output Y;
   assign Y = 1'b1;
endmodule

module TIELO (Y);
output Y;
   assign Y = 1'b0;
endmodule

module DECAPX1 (VDD, VSS);
  input VDD;
  input VSS;
endmodule

module ENDCAPX1 (VDD, VSS);
  input VDD;
  input VSS;
endmodule

module ANTENNAX1 (VDD, VSS, DIODE);
  input VDD;
  input VSS;
  inout DIODE;
endmodule

module CLKBUFX2 (A, Y);
input  A ;
output Y ;

   buf (Y, A);

   specify
   endspecify

endmodule

module DFFRX1 (CLK, D, Q, QB, RESET);
  input CLK;
  input D;
  input RESET;
  output Q;
  output QB;
  reg q;
  always @(posedge CLK or posedge RESET)
    if (RESET) q <= 1'b0;
    else       q <= D;
  assign Q  = q;
  assign QB = ~q;
endmodule

module DFFRX2 (CLK, D, Q, QB, RESET);
  input CLK;
  input D;
  input RESET;
  output Q;
  output QB;
  reg q;
  // same function as DFFRX1; the layout adds the static keeper on the
  // master node, so the master state is held instead of stored on charge
  always @(posedge CLK or posedge RESET)
    if (RESET) q <= 1'b0;
    else       q <= D;
  assign Q  = q;
  assign QB = ~q;
endmodule
