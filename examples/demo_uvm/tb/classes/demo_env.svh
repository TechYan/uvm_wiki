class demo_env extends uvm_env;
  `uvm_component_utils(demo_env)

  demo_env_config cfg;
  demo_agent       agent;
  demo_scoreboard  scoreboard;
  demo_coverage    coverage;

  function new(string name = "demo_env", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db #(demo_env_config)::get(this, "", "cfg", cfg))
      cfg = demo_env_config::type_id::create("cfg");
    agent = demo_agent::type_id::create("agent", this);
    agent.is_active = cfg.is_active;
    scoreboard = demo_scoreboard::type_id::create("scoreboard", this);
    coverage = demo_coverage::type_id::create("coverage", this);
  endfunction

  function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);
    agent.monitor.item_ap.connect(scoreboard.item_imp);
    agent.monitor.item_ap.connect(coverage.analysis_export);
  endfunction
endclass
