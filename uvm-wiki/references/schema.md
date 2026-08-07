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
