module demo_top;
  import uvm_pkg::*;
  import demo_pkg::*;

  logic clk = 1'b0;
  logic reset_n = 1'b0;

  always #5ns clk = ~clk;

  demo_if demo_vif (
    .clk     (clk),
    .reset_n (reset_n)
  );

  demo_dut dut (
    .clk     (clk),
    .reset_n (reset_n),
    .valid   (demo_vif.valid),
    .ready   (demo_vif.ready),
    .data    (demo_vif.data)
  );

  initial begin
    repeat (4) @(posedge clk);
    reset_n = 1'b1;
  end

  initial begin
    uvm_config_db #(virtual demo_if)::set(null, "*", "vif", demo_vif);
    run_test("demo_smoke_test");
  end
endmodule
