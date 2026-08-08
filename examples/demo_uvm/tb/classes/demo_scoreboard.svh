class demo_scoreboard extends uvm_scoreboard;
  `uvm_component_utils(demo_scoreboard)

  uvm_analysis_imp #(demo_item, demo_scoreboard) item_imp;
  int unsigned observed_count;

  function new(string name = "demo_scoreboard", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    item_imp = new("item_imp", this);
  endfunction

  function void write(demo_item item);
    observed_count++;
    `uvm_info(get_type_name(), $sformatf("observed data 0x%0h", item.data), UVM_MEDIUM)
  endfunction

  function void report_phase(uvm_phase phase);
    `uvm_info(get_type_name(), $sformatf("observed %0d items", observed_count), UVM_LOW)
  endfunction
endclass
