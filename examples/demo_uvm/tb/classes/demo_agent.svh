class demo_agent extends uvm_agent;
  `uvm_component_utils(demo_agent)

  demo_sequencer sequencer;
  demo_driver    driver;
  demo_monitor   monitor;

  function new(string name = "demo_agent", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    monitor = demo_monitor::type_id::create("monitor", this);
    if (is_active == UVM_ACTIVE) begin
      sequencer = demo_sequencer::type_id::create("sequencer", this);
      driver    = demo_driver::type_id::create("driver", this);
    end
  endfunction

  function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);
    if (is_active == UVM_ACTIVE)
      driver.seq_item_port.connect(sequencer.seq_item_export);
  endfunction
endclass
