---
name: uvm-wiki
description: Build and query an offline AI-friendly code index and unified interactive wiki for SystemVerilog/UVM repositories. Use when Codex needs to analyze a VIP/UVC/testbench source directory, explain UVM component topology or inheritance, inspect TLM ports and connect calls, create uvm_wiki_ai.json, launch a read-only full-source browser, or reuse an incremental code index instead of repeatedly grepping a large verification repository.
---

# UVM Wiki

Generate one canonical JSON index and one unified HTML application for both AI agents and verification engineers. Keep source directories read-only and write every generated artifact outside the source tree unless the user explicitly chooses an output directory inside it.

## Choose A Parser

Use `--parser auto` by default:

- `auto`: use pyslang when available; otherwise fall back to the standard-library light parser.
- `pyslang`: require pyslang and fail clearly when it is unavailable. Individual parse failures and very large files use a recorded light-parser fallback so one file cannot block the repository.
- `light`: use the dependency-free parser for restricted environments.

Run the environment check when parser availability is uncertain:

```bash
python scripts/uvm_wiki.py doctor
```

On the supported offline target (Linux x86_64, CPython 3.11, glibc 2.27+), install the bundled pyslang wheel into the user venv:

```bash
python3.11 scripts/install_offline.py
```

Then run the tool with:

```bash
~/.local/share/uvm-wiki/venv/bin/python scripts/uvm_wiki.py doctor
```

## Build A Portable Wiki

Use build mode when the result must open without a local service:

```bash
python scripts/uvm_wiki.py build --src /path/to/uvm --parser auto --out /path/to/output
```

This writes:

- `uvm_wiki_ai.json`: canonical AI index.
- `uvm_wiki.html`: unified Architecture, Wiki Graph, TLM Connections, and Code Explorer application. Architecture uses nested test/env containers, expandable agent internals, config blocks, TLM overlays, and virtual-interface boundaries.
- `.cache/parse_cache.json`: file-level incremental cache.

Build mode embeds bounded source snippets. Adjust or disable them when needed:

```bash
python scripts/uvm_wiki.py build --src /path/to/uvm --source-context 20
python scripts/uvm_wiki.py build --src /path/to/uvm --no-source
```

## Browse The Full Source Tree

Use serve mode for complete source files and full-text search:

```bash
python scripts/uvm_wiki.py serve --src /path/to/uvm --parser auto --out /path/to/output --port 8765
```

Open `http://127.0.0.1:8765`. The service is read-only, binds to loopback, rejects traversal outside `--src`, and serves only SystemVerilog source extensions.

## Reuse The Index

Prefer an existing `uvm_wiki_ai.json` when its `metadata.source_fingerprint` still matches the current source tree. Query `symbols`, `relations`, `hierarchies`, and `tlm` before reading source files. Use file and line locations from the index to open only relevant code.

Normal builds reuse unchanged files. Force a complete reparse only when required:

```bash
python scripts/uvm_wiki.py build --src /path/to/uvm --rebuild
```

Read [references/schema.md](references/schema.md) when an agent needs the JSON field contract.

For architecture questions, query `uvm_architecture` before rebuilding topology from raw relations. It contains inherited component children, config auxiliaries, effective ports, resolved connection endpoints, and virtual-interface access evidence. Treat it as a static projection: do not claim runtime factory overrides, dynamic instance counts, final config-db effects, or exact DUT/BFM bindings without simulation evidence.

## Validate A Delivery

Before handing off an offline bundle:

1. Run `doctor` with the intended Python interpreter.
2. Build one small VIP in `light` mode.
3. Build one representative VIP in `pyslang` mode.
4. Run the same build again and confirm `reparsed_files` is zero.
5. Open the unified HTML and inspect Architecture, Wiki Graph, TLM Connections, and Code Explorer.
6. Start serve mode and confirm full-source lookup works only under the configured source root.
