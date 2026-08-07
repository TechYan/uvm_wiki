from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from uvm_wiki_core import build_hierarchies, parse_light  # noqa: E402
from uvm_wiki_web import render_html, source_payload  # noqa: E402


class LightParserTests(unittest.TestCase):
    def test_nested_create_and_tlm_locations(self) -> None:
        source = """\

class sample_env extends uvm_env;
  `uvm_component_utils(sample_env)

  uvm_analysis_port #(sample_txn) analysis_ap;
  sample_agent agent;

  function void build_phase(uvm_phase phase);
    agent = sample_agent::type_id::create($sformatf("agent_%0d", index), this);
  endfunction

  function void connect_phase(uvm_phase phase);
    agent.driver.seq_item_port.connect(agent.sequencer.seq_item_export);
  endfunction
endclass
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "sample_env.sv"
            path.write_text(source, encoding="utf-8")
            parsed = parse_light(path, root)

        ports = [item for item in parsed["relations"] if item["kind"] == "declares_tlm_port"]
        creates = [item for item in parsed["relations"] if item["kind"] == "creates"]
        connects = [item for item in parsed["relations"] if item["kind"] == "seq_item_connect"]
        self.assertEqual((ports[0]["source"], ports[0]["line"]), ("sample_env", 5))
        self.assertEqual(creates[0]["instance"], '$sformatf("agent_%0d", index)')
        self.assertEqual(creates[0]["line"], 9)
        self.assertEqual((connects[0]["context"], connects[0]["line"]), ("sample_env", 13))

    def test_topology_prefers_create_over_matching_member(self) -> None:
        symbols = [
            {"kind": "class", "name": "sample_env", "role": "env"},
            {"kind": "class", "name": "sample_agent", "role": "agent"},
        ]
        relations = [
            {"kind": "has_member", "source": "sample_env", "target": "sample_agent", "instance": "agent", "line": 4},
            {"kind": "creates", "source": "sample_env", "target": "sample_agent", "instance": "agent", "line": 9},
        ]
        tree = build_hierarchies(symbols, relations)["topology"]
        self.assertEqual(len(tree["children"]["sample_env"]), 1)
        self.assertEqual(tree["children"]["sample_env"][0]["kind"], "creates")


class WebTests(unittest.TestCase):
    def test_source_payload_rejects_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "good.sv").write_text("module good; endmodule\n", encoding="utf-8")
            self.assertEqual(source_payload(root, "good.sv")["line_count"], 1)
            with self.assertRaises(ValueError):
                source_payload(root, "../outside.sv")

    def test_rendered_html_contains_unified_views(self) -> None:
        data = {
            "stats": {},
            "metadata": {},
            "symbols": [],
            "relations": [],
            "hierarchies": {},
            "tlm": {},
            "snippets": {},
        }
        html = render_html(json.loads(json.dumps(data)))
        for label in ("Architecture", "Wiki Graph", "TLM Connections", "Code Explorer"):
            self.assertIn(label, html)


if __name__ == "__main__":
    unittest.main()
