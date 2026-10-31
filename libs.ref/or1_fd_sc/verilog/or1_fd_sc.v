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
module DFFPOSX1 (CLK, D, Q);
input  CLK ;
input  D ;
output Q ;
reg Q ;

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
