from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from uvm_wiki_core import build_hierarchies, build_index, build_uvm_architecture, classify_role, parse_light  # noqa: E402
from uvm_wiki_filelist import derive_source_root, expand_project_includes, parse_filelists  # noqa: E402
from uvm_wiki_web import render_html, source_payload  # noqa: E402


class LightParserTests(unittest.TestCase):
    def test_coverage_monitor_prefers_coverage_role(self) -> None:
        self.assertEqual(classify_role("pcie_coverage_monitor", "uvm_monitor"), "coverage")

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
        self.assertEqual(creates[0]["instance"], "agent")
        self.assertEqual(creates[0]["instance_name"], '$sformatf("agent_%0d", index)')
        self.assertEqual(creates[0]["parent"], "this")
        self.assertEqual(creates[0]["line"], 9)
        self.assertEqual((connects[0]["context"], connects[0]["line"]), ("sample_env", 13))

    def test_parameterized_function_return_type_is_indexed(self) -> None:
        source = """\
class sample_monitor extends uvm_monitor;
  virtual function uvm_subscriber#(sample_txn) get_sample_sub();
    return sample_sub;
  endfunction
endclass
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "sample_monitor.sv"
            path.write_text(source, encoding="utf-8")
            parsed = parse_light(path, root)

        method = next(item for item in parsed["symbols"] if item["name"] == "get_sample_sub")
        self.assertEqual((method["kind"], method["owner"], method["line"]), ("function", "sample_monitor", 2))

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

    def test_missing_factory_type_remains_visible_in_topology_and_architecture(self) -> None:
        symbols = [
            {"kind": "class", "name": "sample_env", "base": "uvm_env", "role": "env", "file": "env.sv", "line": 1},
        ]
        relations = [
            {
                "kind": "creates",
                "source": "sample_env",
                "target": "vendor_pkg.vendor_agent",
                "instance": "agent",
                "parent": "this",
                "file": "env.sv",
                "line": 12,
            },
        ]

        topology = build_hierarchies(symbols, relations)["topology"]
        architecture = build_uvm_architecture(symbols, relations)

        topology_edge = topology["children"]["sample_env"][0]
        self.assertEqual((topology_edge["id"], topology_edge["instance"]), ("vendor_agent", "agent"))
        self.assertTrue(topology_edge["definition_missing"])
        architecture_edge = architecture["components"]["sample_env"]["children"][0]
        self.assertEqual((architecture_edge["type"], architecture_edge["instance"]), ("vendor_agent", "agent"))
        self.assertEqual(architecture_edge["qualified_type"], "vendor_pkg.vendor_agent")
        self.assertEqual(architecture_edge["role"], "agent")
        self.assertTrue(architecture_edge["definition_missing"])
        self.assertEqual(architecture_edge["line"], 12)
        self.assertEqual(architecture["unresolved_components"][0]["type"], "vendor_agent")

    def test_uvm_architecture_filters_objects_and_merges_inherited_children(self) -> None:
        symbols = [
            {"kind": "class", "name": "base_test", "base": "uvm_test", "role": "test", "file": "tb.sv", "line": 1},
            {"kind": "class", "name": "derived_test", "base": "base_test", "role": "test", "file": "tb.sv", "line": 8},
            {"kind": "class", "name": "sample_env", "base": "uvm_env", "role": "env", "file": "env.sv", "line": 1},
            {"kind": "class", "name": "sample_agent", "base": "uvm_agent", "role": "agent", "file": "agent.sv", "line": 1},
            {"kind": "class", "name": "sample_cfg", "base": "uvm_object", "role": "config", "file": "cfg.sv", "line": 1},
            {"kind": "class", "name": "sample_seq", "base": "uvm_sequence", "role": "sequence", "file": "seq.sv", "line": 1},
        ]
        relations = [
            {"kind": "creates", "source": "base_test", "target": "sample_env", "instance": "env", "parent": "this", "file": "tb.sv", "line": 5},
            {"kind": "creates", "source": "base_test", "target": "sample_cfg", "instance": "cfg", "file": "tb.sv", "line": 6},
            {"kind": "has_member", "source": "derived_test", "target": "sample_seq", "instance": "seq", "file": "tb.sv", "line": 10},
            {"kind": "creates", "source": "sample_env", "target": "sample_agent", "instance": "agent", "parent": "this", "file": "env.sv", "line": 7},
        ]

        architecture = build_uvm_architecture(symbols, relations)

        self.assertEqual(architecture["schema_version"], "uvm-architecture.v2")
        self.assertFalse(architecture["inference"]["runtime_elaborated"])
        self.assertNotIn("sample_cfg", architecture["components"])
        self.assertNotIn("sample_seq", architecture["components"])
        inherited = architecture["components"]["derived_test"]["children"]
        self.assertEqual([(item["instance"], item["type"], item["inherited"]) for item in inherited], [("env", "sample_env", True)])
        inherited_config = architecture["components"]["derived_test"]["auxiliaries"]
        self.assertEqual([(item["instance"], item["type"], item["role"]) for item in inherited_config], [("cfg", "sample_cfg", "config")])
        self.assertEqual(architecture["components"]["sample_env"]["descendant_type_count"], 1)

    def test_uvm_architecture_resolves_agent_connections_and_virtual_interface(self) -> None:
        symbols = [
            {"kind": "class", "name": "sample_test", "base": "uvm_test", "role": "test", "file": "test.sv", "line": 1},
            {"kind": "class", "name": "sample_env", "base": "uvm_env", "role": "env", "file": "env.sv", "line": 1},
            {"kind": "class", "name": "sample_agent", "base": "uvm_agent", "role": "agent", "file": "agent.sv", "line": 1},
            {"kind": "class", "name": "sample_driver", "base": "uvm_driver", "role": "driver", "file": "driver.sv", "line": 1},
            {"kind": "class", "name": "sample_sequencer", "base": "uvm_sequencer", "role": "sequencer", "file": "sequencer.sv", "line": 1},
            {"kind": "class", "name": "sample_monitor", "base": "uvm_monitor", "role": "monitor", "file": "monitor.sv", "line": 1},
            {"kind": "interface", "name": "sample_if", "role": "interface", "file": "sample_if.sv", "line": 1},
        ]
        relations = [
            {"kind": "creates", "source": "sample_test", "target": "sample_env", "instance": "env", "parent": "this", "file": "test.sv", "line": 9},
            {"kind": "creates", "source": "sample_env", "target": "sample_agent", "instance": "agent", "parent": "this", "file": "env.sv", "line": 9},
            {"kind": "creates", "source": "sample_agent", "target": "sample_driver", "instance": "driver", "parent": "this", "file": "agent.sv", "line": 10},
            {"kind": "creates", "source": "sample_agent", "target": "sample_sequencer", "instance": "sequencer", "parent": "this", "file": "agent.sv", "line": 11},
            {"kind": "creates", "source": "sample_agent", "target": "sample_monitor", "instance": "monitor", "parent": "this", "file": "agent.sv", "line": 12},
            {"kind": "declares_tlm_port", "source": "sample_driver", "target": "seq_item_port", "port_type": "uvm_seq_item_pull_port", "port_family": "seq_item", "direction": "port", "transaction_types": ["sample_item"], "file": "driver.sv", "line": 5},
            {"kind": "declares_tlm_port", "source": "sample_sequencer", "target": "seq_item_export", "port_type": "uvm_seq_item_pull_export", "port_family": "seq_item", "direction": "export", "transaction_types": ["sample_item"], "file": "sequencer.sv", "line": 5},
            {"kind": "seq_item_connect", "context": "sample_agent", "source": "sample_agent.driver.seq_item_port", "target": "sequencer.seq_item_export", "lhs": "driver.seq_item_port", "rhs": "sequencer.seq_item_export", "file": "agent.sv", "line": 22},
            {"kind": "config_db_get", "source": "sample_agent", "target": "vif", "config_type": "virtual sample_if", "scope": "", "file": "agent.sv", "line": 18},
        ]

        architecture = build_uvm_architecture(symbols, relations)

        agent = architecture["components"]["sample_agent"]
        self.assertEqual([item["role"] for item in agent["children"]], ["sequencer", "driver", "monitor"])
        self.assertEqual(agent["virtual_interfaces"][0]["type"], "sample_if")
        connection = agent["connections"][0]
        self.assertTrue(connection["resolved"])
        self.assertEqual(connection["source_endpoint"]["instance_path"], ["driver"])
        self.assertEqual(connection["target_endpoint"]["instance_path"], ["sequencer"])
        self.assertTrue(connection["source_endpoint"]["port_declared"])
        self.assertEqual(connection["source_endpoint"]["direction"], "port")
        self.assertEqual(connection["target_endpoint"]["direction"], "export")
        self.assertEqual(len(architecture["connections"]), 1)
        self.assertEqual(architecture["externals"]["interfaces"][0]["name"], "sample_if")


class FilelistTests(unittest.TestCase):
    def test_gb18030_filelist_supports_non_ascii_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_name = "\u793a\u4f8b.sv"
            (root / source_name).write_text("module sample; endmodule\n", encoding="utf-8")
            filelist = root / "files.f"
            filelist.write_bytes((f"# \u4e2d\u6587\u6ce8\u91ca\n./{source_name}\n").encode("gb18030"))

            spec = parse_filelists([filelist])

            self.assertEqual(spec.sources, [(root / source_name).resolve()])

    def test_nested_filelist_selects_sources_and_expands_project_includes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "lists").mkdir()
            (root / "src").mkdir()
            (root / "include").mkdir()
            (root / "src" / "child.sv").write_text(
                "class sample_child extends uvm_component; endclass\n",
                encoding="utf-8",
            )
            (root / "src" / "top.sv").write_text(
                '`include "sample_header.svh"\nmodule sample_top; endmodule\n',
                encoding="utf-8",
            )
            (root / "src" / "not_listed.sv").write_text("module not_listed; endmodule\n", encoding="utf-8")
            (root / "include" / "sample_header.svh").write_text(
                "class sample_header extends uvm_object; endclass\n",
                encoding="utf-8",
            )
            (root / "lists" / "nested.f").write_text("../src/child.sv\n", encoding="utf-8")
            top_filelist = root / "files.f"
            top_filelist.write_text(
                "+incdir+./include\n+define+WIDTH=8\n-f ./lists/nested.f\n./src/top.sv\n-sverilog\n",
                encoding="utf-8",
            )

            spec = parse_filelists([top_filelist])
            source_root = derive_source_root(spec, [top_filelist])
            expand_project_includes(spec, source_root)
            relative_sources = [path.relative_to(source_root).as_posix() for path in spec.sources]

            self.assertEqual(source_root, root.resolve())
            self.assertEqual(relative_sources, ["src/child.sv", "src/top.sv", "include/sample_header.svh"])
            self.assertEqual(spec.defines, ["WIDTH=8"])
            self.assertEqual(spec.ignored_options, ["-sverilog"])

            metadata = spec.metadata(source_root)
            data = build_index(
                source_root=source_root,
                parser_requested="light",
                cache_path=root / "output" / "parse_cache.json",
                source_context=0,
                source_paths=spec.sources,
                include_dirs=spec.include_dirs,
                defines=spec.defines,
                input_metadata=metadata,
            )
            self.assertEqual(data["stats"]["files"], 3)
            self.assertEqual(data["metadata"]["input"]["listed_files"], 2)
            self.assertEqual(data["metadata"]["input"]["included_files"], 1)
            self.assertNotIn("src/not_listed.sv", [item["path"] for item in data["files"]])

    def test_macro_stringify_include_closure_is_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "include").mkdir()
            (root / "include" / "defs.svh").write_text(
                '`define STRINGIFY_VALUE(value) `"value`"\n',
                encoding="utf-8",
            )
            (root / "include" / "vip_impl.svh").write_text(
                "class bundled_agent extends uvm_agent; endclass\n",
                encoding="utf-8",
            )
            (root / "pkg.sv").write_text(
                '`include "defs.svh"\n`include `STRINGIFY_VALUE(`VIP_FILE)\npackage bundled_pkg; endpackage\n',
                encoding="utf-8",
            )
            filelist = root / "files.f"
            filelist.write_text(
                "+incdir+./include\n+define+VIP_FILE=vip_impl.svh\n./pkg.sv\n",
                encoding="utf-8",
            )

            spec = parse_filelists([filelist])
            expand_project_includes(spec, root)
            relative_sources = [path.relative_to(root).as_posix() for path in spec.sources]
            metadata = spec.metadata(root)

            self.assertEqual(relative_sources, ["pkg.sv", "include/defs.svh", "include/vip_impl.svh"])
            self.assertEqual(metadata["include_directives"], 2)
            self.assertEqual(metadata["macro_include_directives"], 1)
            self.assertEqual(metadata["unresolved_includes"], [])
            data = build_index(
                source_root=root,
                parser_requested="light",
                cache_path=root / "output" / "parse_cache.json",
                source_context=0,
                source_paths=spec.sources,
                include_dirs=spec.include_dirs,
                defines=spec.defines,
                input_metadata=metadata,
            )
            self.assertIn("bundled_agent", [item["name"] for item in data["symbols"]])

    def test_svp_package_include_is_indexed_by_light_parser(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bundled_agent.svp").write_text(
                "class svp_agent extends uvm_agent; endclass\n",
                encoding="utf-8",
            )
            (root / "vip_pkg.sv").write_text(
                '`include "bundled_agent.svp"\npackage vip_pkg; endpackage\n',
                encoding="utf-8",
            )
            filelist = root / "files.f"
            filelist.write_text("./vip_pkg.sv\n", encoding="utf-8")

            spec = parse_filelists([filelist])
            expand_project_includes(spec, root)
            relative_sources = [path.relative_to(root).as_posix() for path in spec.sources]
            data = build_index(
                source_root=root,
                parser_requested="light",
                cache_path=root / "output" / "parse_cache.json",
                source_context=0,
                source_paths=spec.sources,
                include_dirs=spec.include_dirs,
                defines=spec.defines,
                input_metadata=spec.metadata(root),
            )

            self.assertEqual(relative_sources, ["vip_pkg.sv", "bundled_agent.svp"])
            self.assertEqual(data["metadata"]["input"]["included_files"], 1)
            self.assertIn("svp_agent", [item["name"] for item in data["symbols"]])

    def test_include_outside_source_root_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "project"
            vendor = workspace / "vendor"
            root.mkdir()
            vendor.mkdir()
            (vendor / "outside.svh").write_text("class outside_agent; endclass\n", encoding="utf-8")
            (root / "pkg.sv").write_text('`include "../vendor/outside.svh"\n', encoding="utf-8")
            filelist = root / "files.f"
            filelist.write_text("./pkg.sv\n", encoding="utf-8")

            spec = parse_filelists([filelist])
            expand_project_includes(spec, root)
            metadata = spec.metadata(root)

            self.assertEqual(len(spec.sources), 1)
            self.assertEqual(len(metadata["outside_root_includes"]), 1)
            self.assertIn("outside --src boundary", metadata["warnings"][-1])


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
            "uvm_architecture": {"roots": [], "components": {}},
            "tlm": {},
            "snippets": {},
        }
        html = render_html(json.loads(json.dumps(data)))
        for label in (
            "Architecture",
            "Topology",
            "Class Hierarchy",
            "TLM Connections",
            "Phase Map",
            "Wiki Graph",
            "Code Explorer",
        ):
            self.assertIn(label, html)
        nav_labels = (
            "Architecture",
            "Topology",
            "Class Hierarchy",
            "TLM Connections",
            "Phase Map",
            "Wiki Graph",
            "Code Explorer",
        )
        nav_positions = [html.index(f">{label}</button>") for label in nav_labels]
        self.assertEqual(nav_positions, sorted(nav_positions))
        self.assertIn("d3.version", html)
        self.assertIn("arch-container-box", html)
        self.assertIn("fill:#f8fafc", html)
        self.assertIn("archContextGraph", html)
        self.assertIn(
            '<g id="archBackNodes"></g><g id="archWires"></g><g id="archNodes"></g><g id="archMarks"></g>',
            html,
        )
        self.assertIn("arch-wire-halo", html)
        self.assertIn("addFocusBoundaryConnections", html)
        self.assertIn("orthogonalArchPath", html)
        self.assertNotIn("roundedArchPath", html)
        self.assertIn("routeOffset", html)
        self.assertIn("direction-implementation", html)
        self.assertIn("archTlm", html)
        self.assertIn("HDL boundary", html)
        self.assertIn('id="leftSplitter"', html)
        self.assertIn('id="rightSplitter"', html)
        self.assertIn("function bindSplitters", html)
        self.assertIn('id="sourceSplitter"', html)
        self.assertIn('id="sourceDock"', html)
        self.assertIn("--left-width", html)
        self.assertIn('id="topologyGraph"', html)
        self.assertIn('id="topologyView"', html)
        self.assertIn("function topologyForest", html)
        self.assertIn("function selectTopologyNode", html)
        self.assertIn('data-topology-location="instance"', html)
        self.assertIn('data-topology-location="definition"', html)
        self.assertIn("node.pinned=true", html)
        self.assertIn("function resetTopologyView", html)
        self.assertIn('id="hierarchyView"', html)
        self.assertIn('id="hierarchyGraph"', html)
        self.assertIn("function classHierarchyModel", html)
        self.assertIn("function toggleClassHierarchyNode", html)
        self.assertIn("function fitClassHierarchy", html)
        self.assertIn('["uvm_sequencer","uvm_sequencer_param_base"]', html)
        self.assertIn('["uvm_sequence","uvm_sequence_base"]', html)
        self.assertIn('id="phaseView"', html)
        self.assertIn('id="phaseStage"', html)
        self.assertIn("function phaseImplementation", html)
        self.assertIn("function renderPhaseMap", html)
        self.assertIn("function selectPhaseMethod", html)
        self.assertIn('.on("dblclick"', html)
        self.assertIn("arch-expand-action", html)
        self.assertNotIn("arch-enter-action", html)
        self.assertNotIn("arch-count-text", html)
        self.assertIn('id="indexBrowser"', html)
        self.assertIn("function summaryIndexItems", html)
        self.assertIn("function selectSummaryIndexEntry", html)
        self.assertIn("function renderSourcePreview", html)
        self.assertIn("renderSourcePreview(body.lines,line)", html)
        self.assertIn("focus-exit", html)
        self.assertIn("commitArchitectureBack", html)
        self.assertIn("resolveArchitecturePort", html)
        self.assertIn("symbolByOwnerAndName", html)
        self.assertIn("selectArchitecturePort", html)
        self.assertIn("arch-wire-flow", html)
        self.assertIn("arch-wire-reveal", html)
        self.assertIn("wireSelectionActive", html)
        self.assertIn("graphDisplayPosition", html)
        self.assertIn("graphDragAffected", html)
        self.assertIn("drag.affectedNodes", html)
        self.assertIn("dragEcho", html)
        self.assertIn('id="archComponentList"', html)
        self.assertIn('id="tlmGraph"', html)
        self.assertIn('id="tlmContext"', html)
        self.assertIn("function buildTlmScene", html)
        self.assertIn("tlm-wire-halo", html)
        self.assertIn('id="codeCategory"', html)
        self.assertIn("UVM_COMPONENT_ROLES", html)
        self.assertIn("definition-missing", html)
        self.assertIn("definitionMissing", html)


if __name__ == "__main__":
    unittest.main()
