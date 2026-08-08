class demo_monitor extends uvm_monitor;
  `uvm_component_utils(demo_monitor)

  virtual demo_if vif;
  uvm_analysis_port #(demo_item) item_ap;

  function new(string name = "demo_monitor", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    item_ap = new("item_ap", this);
    if (!uvm_config_db #(virtual demo_if)::get(this, "", "vif", vif))
      `uvm_fatal(get_type_name(), "virtual interface was not configured")
  endfunction

  task run_phase(uvm_phase phase);
    demo_item observed;
    forever begin
      @(posedge vif.clk);
      if (vif.reset_n && vif.valid && vif.ready) begin
        observed = demo_item::type_id::create("observed");
        observed.data = vif.data;
        item_ap.write(observed);
      end
    end
  endtask
endclass
