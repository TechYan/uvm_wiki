module demo_dut (
  input  logic                         clk,
  input  logic                         reset_n,
  input  logic                         valid,
  output logic                         ready,
  input  logic [`DEMO_DATA_WIDTH-1:0] data
);

  logic [31:0] accepted_count;

  assign ready = reset_n;

  always_ff @(posedge clk or negedge reset_n) begin
    if (!reset_n)
      accepted_count <= '0;
    else if (valid && ready)
      accepted_count <= accepted_count + 1'b1;
  end

endmodule
