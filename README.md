# UVM Wiki

UVM Wiki is an offline Codex skill for indexing SystemVerilog/UVM source once and reusing the result for both AI-assisted reading and human exploration.

It generates two canonical artifacts:

- `uvm_wiki_ai.json`: structured symbols, relations, hierarchies, TLM ports, connections, locations, and bounded source snippets for AI agents.
- `uvm_wiki.html`: one interactive application containing Architecture, Wiki Graph, TLM Connections, and Code Explorer views.

The Architecture view uses a UVM Cookbook-style visual grammar: nested test/env containers, expandable agent internals, configuration and checker blocks, resolved TLM connections, and an external virtual-interface boundary. TLM port, export, and implementation endpoints use distinct symbols and geometry-aware routing channels. A single click selects a component; double-clicking or using its enter control opens the component. Focus transitions retain the parent as a blurred context layer and preserve connections crossing into the focused component.

Wiki Graph provides three complementary projections. Inheritance and All Relations use an Obsidian-style force graph with curved links, depth cues, bounded persistent node dragging, and animated reset. Topology uses a multi-root tidy forest with curved branches and draggable rectangular nodes. The left and right sidebars can be resized with a pointer or keyboard and restored by double-clicking their dividers.

The TLM Connections view renders only connected endpoints as an interactive D3 diagram. It groups ports by `connect_phase` context and owner instance, preserves `context > instance` hierarchy paths, distinguishes port/export/implementation endpoints, and opens the exact connect-call source when a connection is selected.

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

```bash
~/.local/share/uvm-wiki/venv/bin/python \
  ~/.codex/skills/uvm-wiki/scripts/uvm_wiki.py build \
  --src /path/to/uvm/source \
  --parser auto \
  --out /path/to/output
```

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

## Codex Usage

Example request after installing the skill:

```text
Use UVM Wiki to index /project/vip and explain the component topology and TLM connections.
```

See [uvm-wiki/SKILL.md](uvm-wiki/SKILL.md) for the agent workflow and [uvm-wiki/references/schema.md](uvm-wiki/references/schema.md) for the JSON contract.

## Legacy Tool

`vip_wiki_standalone.py` is retained for compatibility with the original multi-page atlas. New deployments should use the `uvm-wiki` skill and unified HTML application.
