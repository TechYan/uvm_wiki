class demo_env_config extends uvm_object;
  uvm_active_passive_enum is_active = UVM_ACTIVE;
  int unsigned item_count = 8;

  `uvm_object_utils_begin(demo_env_config)
    `uvm_field_enum(uvm_active_passive_enum, is_active, UVM_DEFAULT)
    `uvm_field_int(item_count, UVM_DEFAULT)
  `uvm_object_utils_end

  function new(string name = "demo_env_config");
    super.new(name);
  endfunction
endclass
