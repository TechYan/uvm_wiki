class demo_smoke_test extends uvm_test;
  `uvm_component_utils(demo_smoke_test)

  demo_env        env;
  demo_env_config cfg;

  function new(string name = "demo_smoke_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    cfg = demo_env_config::type_id::create("cfg");
    cfg.item_count = 8;
    uvm_config_db #(demo_env_config)::set(this, "env", "cfg", cfg);
    env = demo_env::type_id::create("env", this);
  endfunction

  task run_phase(uvm_phase phase);
    demo_sequence sequence;
    phase.raise_objection(this);
    sequence = demo_sequence::type_id::create("sequence");
    sequence.item_count = cfg.item_count;
    sequence.start(env.agent.sequencer);
    #20ns;
    phase.drop_objection(this);
  endtask
endclass
