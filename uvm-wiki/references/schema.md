# UVM Wiki AI Schema

`uvm_wiki_ai.json` uses schema version `uvm-wiki-ai.v1`.

## Top-Level Fields

- `schema_version`: stable schema identifier.
- `metadata`: source root, source fingerprint, requested/effective parser, generation time, and cache statistics.
- `stats`: counts for files, classes, symbols, relations, ports, and connections.
- `files`: source file paths, hashes, parser, and pyslang diagnostic counts.
- `symbols`: class, module, interface, package, function, and task declarations.
- `relations`: inheritance, component creation, members, includes, imports, config-db operations, TLM declarations, and connect calls.
- `hierarchies`: precomputed component topology and class inheritance adjacency tables.
- `uvm_architecture`: static instance-oriented UVM architecture projection for agents and the Cookbook-style HTML view.
- `tlm`: normalized port declarations and connect calls.
- `snippets`: bounded source regions keyed by `relative/path:line`.
- `role_colors`: presentation colors; agents should not use them for semantic decisions.

## Symbol Shape

Important fields:

```json
{
  "id": "my_env",
  "kind": "class",
  "name": "my_env",
  "role": "env",
  "base": "uvm_env",
  "file": "src/my_env.sv",
  "line": 12
}
```

Function and task IDs use `owner.name` when an owner can be inferred.

## Relation Shape

Important fields:

```json
{
  "kind": "creates",
  "source": "my_env",
  "target": "my_agent",
  "instance": "agent",
  "file": "src/my_env.sv",
  "line": 48
}
```

Treat parser facts as navigation evidence. Verify exact behavior in the referenced source before modifying verification code.

## UVM Architecture Shape

`uvm_architecture` uses schema version `uvm-architecture.v2`. A separate hand-written `tb_arch` file is not required for the static projection.

Important fields:

- `roots`: candidate test, env, and component roots ordered for architecture browsing.
- `components`: effective component definitions after inherited child, port, config, and connect facts are merged.
- `components.<type>.children`: child instance edges with inferred instance role, source location, confidence, and inheritance state.
- `components.<type>.auxiliaries`: config objects kept outside the component topology but available to the architecture view.
- `components.<type>.ports`: effective TLM port/export/imp declarations.
- `components.<type>.connections`: effective TLM connections with resolved source and target endpoint records.
- `components.<type>.virtual_interfaces`: virtual-interface config-db accesses associated with the component.
- `connections`: directly declared architecture connections across component types.
- `externals`: indexed HDL interfaces and modules; no DUT binding is inferred without source evidence.

Resolved connection endpoints include `instance_path`, `owner_type`, `owner_role`, `port`, `path_resolved`, `port_declared`, and `confidence`. A path can be resolved even when a built-in UVM port declaration is not present in the indexed repository.

The projection is static. Runtime factory overrides, conditional build paths, dynamic instance counts, final config-db effects, and exact BFM/DUT binding require simulation topology, logs, or a future user-provided overlay.
