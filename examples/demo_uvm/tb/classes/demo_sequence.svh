class demo_sequence extends uvm_sequence #(demo_item);
  int unsigned item_count = 8;

  `uvm_object_utils(demo_sequence)

  function new(string name = "demo_sequence");
    super.new(name);
  endfunction

  task body();
    repeat (item_count) begin
      req = demo_item::type_id::create("req");
      start_item(req);
      if (!req.randomize())
        `uvm_fatal(get_type_name(), "demo_item randomization failed")
      finish_item(req);
    end
  endtask
endclass
