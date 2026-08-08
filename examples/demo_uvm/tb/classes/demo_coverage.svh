class demo_coverage extends uvm_subscriber #(demo_item);
  `uvm_component_utils(demo_coverage)

  bit [`DEMO_DATA_WIDTH-1:0] sampled_data;

  covergroup data_cg;
    option.per_instance = 1;
    data_cp: coverpoint sampled_data {
      bins low  = {[0:63]};
      bins high = {[64:255]};
    }
  endgroup

  function new(string name = "demo_coverage", uvm_component parent = null);
    super.new(name, parent);
    data_cg = new();
  endfunction

  function void write(demo_item item);
    sampled_data = item.data;
    data_cg.sample();
  endfunction
endclass
