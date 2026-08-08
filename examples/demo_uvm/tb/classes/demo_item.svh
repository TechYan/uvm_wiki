class demo_item extends uvm_sequence_item;
  rand bit [`DEMO_DATA_WIDTH-1:0] data;

  `uvm_object_utils_begin(demo_item)
    `uvm_field_int(data, UVM_DEFAULT)
  `uvm_object_utils_end

  function new(string name = "demo_item");
    super.new(name);
  endfunction

  constraint data_c {
    data inside {[0:255]};
  }
endclass
