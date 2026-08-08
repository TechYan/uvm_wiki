`ifndef DEMO_DATA_WIDTH
`define DEMO_DATA_WIDTH 16
`endif

interface demo_if (
  input logic clk,
  input logic reset_n
);
  logic                        valid;
  logic                        ready;
  logic [`DEMO_DATA_WIDTH-1:0] data;

  modport driver_mp (
    input  clk,
    input  reset_n,
    input  ready,
    output valid,
    output data
  );

  modport monitor_mp (
    input clk,
    input reset_n,
    input valid,
    input ready,
    input data
  );
endinterface
