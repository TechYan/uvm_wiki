# UVM Wiki

UVM Wiki is an offline Codex skill for indexing SystemVerilog/UVM source once and reusing the result for both AI-assisted reading and human exploration. It can scan a source directory or follow simulator-style filelists.

It generates two canonical artifacts:

- `uvm_wiki_ai.json`: structured symbols, relations, hierarchies, TLM ports, connections, locations, and bounded source snippets for AI agents.
- `uvm_wiki.html`: one interactive application containing Architecture, Topology, Class Hierarchy, TLM Connections, Phase Map, Wiki Graph, and Code Explorer views.

The Architecture view uses a UVM Cookbook-style visual grammar: nested test/env containers, expandable agent internals, configuration and checker blocks, resolved TLM connections, and an external virtual-interface boundary. TLM port, export, and implementation endpoints use distinct symbols and horizontally terminated routing channels. Clicking an endpoint opens its declaration when the index has a local location; clicking a wire opens the corresponding connect call. A component list mirrors the current layer. A single click selects a component; double-clicking or using its enter control opens the component. Focus transitions retain the parent as a blurred context layer and preserve connections crossing into the focused component. A parent-bearing factory create remains visible even when its component type definition is unavailable; the instance is marked as definition-missing and links to the create statement. Distinct static instance candidates are displayed separately even when they share the same unresolved type, avoiding misleading aggregate instance counts.

Wiki Graph provides two complementary projections. Inheritance uses a centered circular Obsidian-style force graph with straight links; All Relations retains curved links and depth cues for dense data. Topology is a separate top-level view using a multi-root tidy forest with draggable instance-labeled nodes. Every distinct static instance remains separate, including repeated resolved or missing-definition types under one parent. Missing component definitions are retained as dashed warning nodes and link to their individual factory-create evidence. Selecting a topology node opens its factory-create or member-declaration evidence by default, while the selection panel provides a second direct entry to the class definition when one exists. The Related panel can filter by relation kind and search source, target, or location text.

Class Hierarchy presents a collapsible left-to-right inheritance tree. It groups known UVM library bases above indexed classes, distinguishes library links from source-backed `extends` relations, and supports component, object/sequence, and all-class scopes. Phase Map presents declared and effective inherited UVM phase implementations as a searchable matrix; every populated cell jumps to the implementing function or task. The left and right sidebars and the bottom source preview can be resized with a pointer or keyboard and restored by double-clicking their dividers.

The TLM Connections view renders only connected endpoints as an interactive D3 diagram. It groups ports by `connect_phase` context and owner instance, preserves `context > instance` hierarchy paths, distinguishes port/export/implementation endpoints, and opens the exact connect-call source when a connection is selected.

Code Explorer hides the graph sidebars and provides category-driven definition lists for UVM components, interfaces, sequences, sequence items, classes, modules, packages, functions, tasks, and source files. Serve mode also exposes full-text source search.

No separate `tb_arch` description is required. The architecture is projected from static source evidence in the JSON index. Runtime factory overrides, dynamic instances, and exact DUT/BFM binding remain explicitly unresolved unless runtime evidence is added later.

## Offline Linux Install

The bundled dependency package targets Linux x86_64, CPython 3.11, and glibc 2.27 or newer. It installs into a user-owned virtual environment and does not require root or network access.

```bash
mkdir -p ~/.codex/skills
cp -a uvm-wiki ~/.codex/skills/uvm-wiki
python3.11 ~/.codex/skills/uvm-wiki/scripts/install_offline.py
~/.local/share/uvm-wiki/venv/bin/python ~/.codex/skills/uvm-wiki/scripts/uvm_wiki.py doctor
```

The wheel checksum is verified before installation. The default environment is `~/.local/share/uvm-wiki/venv`; use `--venv /personal/path` to choose another location.

## Build

Directory scan mode recursively indexes `.sv`, `.svh`, `.svp`, `.v`, `.vh`, `.inc`, `.svi`, and `.pkg` files under `--src`:

```bash
~/.local/share/uvm-wiki/venv/bin/python \
  ~/.codex/skills/uvm-wiki/scripts/uvm_wiki.py build \
  --src /path/to/uvm/source \
  --parser auto \
  --out /path/to/output
```

Filelist mode indexes listed compilation units plus project-local include files:

```bash
~/.local/share/uvm-wiki/venv/bin/python \
  ~/.codex/skills/uvm-wiki/scripts/uvm_wiki.py build \
  --src /path/to/project \
  --filelist /path/to/project/sim/filelist.f \
  --parser auto \
  --out /path/to/output
```

`--src` is optional with `--filelist`, but specifying it is recommended because it defines relative source paths and the full-source browsing boundary. Repeat `--filelist` for multiple top-level manifests. Nested `-f`/`-F`, `+incdir+`, `-I`, `+define+`, `-D`, explicit `-v` files, environment variables, comments, and line continuations are supported. Package include closure supports literal names, object macros, and common stringify wrappers. Include lookup checks the including file, include directories, filelist directories, and `--src`; unresolved or outside-boundary includes are printed and recorded under `metadata.input`. This is static per-file parsing, not simulator elaboration.

Parser modes:

- `auto`: prefer pyslang and fall back to the dependency-free light parser.
- `pyslang`: require pyslang; a failing or very large individual source file uses light fallback and is recorded in JSON metadata.
- `light`: use only the Python standard-library parser.

Normal builds reuse the per-file cache in `<output>/.cache/parse_cache.json`. Add `--rebuild` to force a full reparse.

## Browse Full Source

Portable build mode embeds bounded snippets. To browse and search the complete source tree, run the read-only loopback service:

```bash
~/.local/share/uvm-wiki/venv/bin/python \
  ~/.codex/skills/uvm-wiki/scripts/uvm_wiki.py serve \
  --src /path/to/uvm/source \
  --parser auto \
  --out /path/to/output \
  --port 8765
```

Open `http://127.0.0.1:8765`. The server rejects paths outside `--src` and serves only supported HDL source extensions.

To start the source API from existing outputs without scanning or parsing again:

```bash
~/.local/share/uvm-wiki/venv/bin/python \
  ~/.codex/skills/uvm-wiki/scripts/uvm_wiki.py serve-existing \
  --src /path/to/uvm/source \
  --out /path/to/output \
  --port 8765
```

## Codex Usage

Example request after installing the skill:

```text
Use UVM Wiki to index /project/vip and explain the component topology and TLM connections.
```

See [uvm-wiki/SKILL.md](uvm-wiki/SKILL.md) for the agent workflow and [uvm-wiki/references/schema.md](uvm-wiki/references/schema.md) for the JSON contract.

The repository includes a sanitized complete example under [examples/demo_uvm](examples/demo_uvm). See [docs/INTRANET_GUIDE.md](docs/INTRANET_GUIDE.md) for offline deployment and operation, and [docs/INTRODUCTION.md](docs/INTRODUCTION.md) for a concise presentation document with image placeholders.

## Legacy Tool

`vip_wiki_standalone.py` is retained for compatibility with the original multi-page atlas. New deployments should use the `uvm-wiki` skill and unified HTML application.
