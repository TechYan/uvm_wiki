class demo_driver extends uvm_driver #(demo_item);
  `uvm_component_utils(demo_driver)

  virtual demo_if vif;

  function new(string name = "demo_driver", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db #(virtual demo_if)::get(this, "", "vif", vif))
      `uvm_fatal(get_type_name(), "virtual interface was not configured")
  endfunction

  task run_phase(uvm_phase phase);
    vif.valid <= 1'b0;
    vif.data  <= '0;
    forever begin
      seq_item_port.get_next_item(req);
      @(posedge vif.clk);
      vif.valid <= 1'b1;
      vif.data  <= req.data;
      do @(posedge vif.clk); while (!vif.ready);
      vif.valid <= 1'b0;
      seq_item_port.item_done();
    end
  endtask
endclass
