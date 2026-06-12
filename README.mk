# UVM Wiki Atlas

Single-file offline SystemVerilog/UVM code atlas generator.

The tool scans a source directory containing `.sv`, `.svh`, and `.v` files,
then emits browser-readable wiki graphs, tree views, TLM/port views, Graphviz
DOT files, and an AI-friendly JSON atlas.

## Files

- `vip_wiki_standalone.py`: standalone Python tool, standard library only.

## Requirements

- Python 3.9 or newer is recommended.
- No pip package is required.
- Graphviz is optional. If `dot` is available in `PATH`, SVG files are rendered
  automatically. Otherwise DOT files and render commands are still generated.

## Quick Start

```powershell
python vip_wiki_standalone.py --src path\to\uvm_or_vip_source --out .atlas\atlas_wiki.html
```

If `--out` is a directory, the tool writes `atlas_wiki.html` inside it.

## Common Outputs

- `atlas_wiki.html`: interactive Obsidian-style graph with searchable dots,
  clickable relationship rows, and embedded source snippets.
- `atlas_tree.html`: collapsible inheritance and topology tree.
- `atlas_ports.html`: TLM port declaration and connection table.
- `atlas_arch.html`: pure-browser architecture and TLM flow view.
- `atlas_ai.json`: structured JSON atlas for agent lookup and learning.
- `atlas_hierarchy.dot`, `atlas_tlm.dot`, `atlas_uvm.dot`: Graphviz DOT files.
- `atlas_graphviz.html`: Graphviz preview/index page.

## Useful Options

```powershell
python vip_wiki_standalone.py --src path\to\src --out out_dir --max-nodes 420
python vip_wiki_standalone.py --src path\to\src --out atlas_wiki.html --no-dot
python vip_wiki_standalone.py --src path\to\src --out atlas_wiki.html --json-out atlas_ai.json
```

## Notes

- The generated atlas is a navigation cache. Verify exact behavior in source
  before editing design verification code.
- The HTML views are self-contained and can be copied to an offline network.
- The JSON output is intended for AI agents to query faster than repeated grep
  passes over a large codebase.
