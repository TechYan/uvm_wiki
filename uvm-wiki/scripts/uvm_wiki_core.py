#!/usr/bin/env python3
"""SystemVerilog/UVM indexing core shared by build and serve modes."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


SCHEMA_VERSION = "uvm-wiki-ai.v1"
ARCHITECTURE_SCHEMA_VERSION = "uvm-architecture.v2"
CACHE_VERSION = 8
PYSLANG_AST_MAX_BYTES = 512 * 1024
SOURCE_EXTS = {".sv", ".svh", ".v", ".vh", ".inc", ".svi", ".pkg"}
SKIP_DIRS = {".git", ".svn", "__pycache__", ".uvm_wiki", "node_modules"}
OPAQUE_EXTS = {".zip", ".tgz", ".gz", ".so", ".dll", ".a", ".o", ".obj", ".exe", ".key", ".pem"}

ROLE_COLORS = {
    "test": "#0f766e",
    "env": "#2563eb",
    "agent": "#0891b2",
    "driver": "#dc2626",
    "monitor": "#16a34a",
    "sequencer": "#7c3aed",
    "sequence": "#9333ea",
    "sequence_item": "#ea580c",
    "scoreboard": "#be123c",
    "config": "#ca8a04",
    "coverage": "#4f46e5",
    "interface": "#0284c7",
    "module": "#475569",
    "component": "#475569",
    "class": "#64748b",
    "external": "#94a3b8",
}

CLASS_RE = re.compile(
    r"^\s*(?:(virtual)\s+)?class\s+([A-Za-z_]\w*)"
    r"(?:\s*#\s*\((.*?)\))?"
    r"(?:\s+extends\s+([A-Za-z_][\w:]*)(?:\s*#\s*\(.*?\))?)?\s*;",
    re.S,
)
MODULE_RE = re.compile(r"^\s*(module|interface|program|package)\s+([A-Za-z_]\w*)\b")
INCLUDE_RE = re.compile(r'^\s*`include\s+"([^"]+)"')
IMPORT_RE = re.compile(r"^\s*import\s+([A-Za-z_][\w:]*)::\*\s*;")
CREATE_RE = re.compile(r"([A-Za-z_][\w:]*)\s*(?:#\s*\([^;]*?\))?\s*::\s*type_id\s*::\s*create\s*\(", re.S)
VENDOR_NEW_RE = re.compile(r"`" + "AV" + r"ERY_NEW(?:_PARENT)?\s*\(\s*([A-Za-z_][\w:]*)\s*,", re.S)
VENDOR_NEW_TOKEN = "`" + "AV" + "ERY_NEW"
CONNECT_RE = re.compile(r"([A-Za-z_][\w\.\[\]]*)\s*\.\s*connect\s*\(\s*([A-Za-z_][\w\.\[\]]*)")
CONFIG_RE = re.compile(r"uvm_config_db\s*#\s*\((.*?)\)\s*::\s*(set|get)\s*\(", re.S)
TLM_DECL_RE = re.compile(
    r"\b(?P<port_type>uvm_[A-Za-z0-9_]*(?:port|export|imp)[A-Za-z0-9_]*)"
    r"\s*(?:#\s*\((?P<params>.*?)\))?\s+"
    r"(?P<vars>[A-Za-z_]\w*(?:\s*\[[^\]]+\])?(?:\s*,\s*[A-Za-z_]\w*(?:\s*\[[^\]]+\])?)*)\s*;",
    re.S,
)
FIELD_RE = re.compile(
    r"^\s*(?:rand\s+)?(?P<type>[A-Za-z_]\w*)"
    r"(?:\s*#\s*\([^;]*\))?\s+"
    r"(?P<vars>[A-Za-z_]\w*(?:\s*\[[^\]]+\])?(?:\s*,\s*[A-Za-z_]\w*(?:\s*\[[^\]]+\])?)*)\s*;",
    re.S,
)
METHOD_RE = re.compile(
    r"^\s*(?:extern\s+)?(?:virtual\s+)?(?P<kind>function|task)\s+(?:automatic\s+)?"
    r"(?:(?:[A-Za-z_][\w:<>#()\[\],\s]*)\s+)?(?:(?P<class>[A-Za-z_]\w*)::)?(?P<name>[A-Za-z_]\w*)\s*\("
)


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="ignore")


def strip_comments(text: str) -> str:
    out: list[str] = []
    i = 0
    block = False
    string = False
    while i < len(text):
        pair = text[i : i + 2]
        ch = text[i]
        if block:
            if pair == "*/":
                out.extend("  ")
                i += 2
                block = False
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if not string and pair == "/*":
            out.extend("  ")
            i += 2
            block = True
            continue
        if not string and pair == "//":
            while i < len(text) and text[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch == '"' and (i == 0 or text[i - 1] != "\\"):
            string = not string
        out.append(ch)
        i += 1
    return "".join(out)


def normalize_type(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().split("#", 1)[0].replace("::", ".")


def classify_role(name: str, base: str | None = None) -> str:
    text = f"{name} {base or ''}".lower()
    rules = [
        ("config", ("_config", "_cfg", "cfg_info")),
        ("test", ("uvm_test", "_test")),
        ("env", ("uvm_env", "_env", "_uvc")),
        ("agent", ("uvm_agent", "_agent")),
        ("driver", ("uvm_driver", "_driver", "_drv")),
        ("coverage", ("coverage", "_cov")),
        ("monitor", ("uvm_monitor", "_monitor", "_mon")),
        ("sequencer", ("uvm_sequencer", "_sequencer", "_seqr")),
        ("scoreboard", ("uvm_scoreboard", "_scoreboard", "_scbd", "_sbd")),
        ("sequence_item", ("uvm_sequence_item", "_transaction", "_item", "_packet", "_pkt", "_tlp")),
        ("sequence", ("uvm_sequence", "_sequence", "_seq")),
    ]
    for role, terms in rules:
        if any(term in text for term in terms):
            return role
    return "class"


def port_family(port_type: str) -> str:
    value = port_type.lower()
    for family in ("seq_item", "analysis", "transport", "put", "get_peek", "get", "peek", "master", "slave"):
        if family in value:
            return family
    return "tlm"


def port_direction(port_type: str) -> str:
    value = port_type.lower()
    if "export" in value:
        return "export"
    if "imp" in value:
        return "implementation"
    if "port" in value:
        return "port"
    return "unknown"


def split_args(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    quoted = False
    previous = ""
    for ch in value:
        if ch == '"' and previous != "\\":
            quoted = not quoted
        if not quoted:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth = max(0, depth - 1)
            elif ch == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
                previous = ch
                continue
        current.append(ch)
        previous = ch
    if current:
        parts.append("".join(current).strip())
    return parts


def argument(value: str, index: int) -> str | None:
    values = split_args(value)
    if index >= len(values):
        return None
    item = values[index].strip()
    match = re.match(r'"([^"]*)"', item)
    return match.group(1) if match else item


def balanced_args(text: str, opening: int) -> str | None:
    depth = 0
    quoted = False
    previous = ""
    start = opening + 1
    for index in range(opening, len(text)):
        ch = text[index]
        if ch == '"' and previous != "\\":
            quoted = not quoted
        if not quoted:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return text[start:index]
        previous = ch
    return None


def statement_chunks(lines: list[str]) -> Iterable[tuple[int, str]]:
    buffer: list[str] = []
    start = 1
    for line_no, line in enumerate(lines, 1):
        if not buffer and not line.strip():
            continue
        if not buffer:
            start = line_no
        buffer.append(line)
        if ";" in line:
            yield start, "\n".join(buffer)
            buffer = []
    if buffer and "".join(buffer).strip():
        yield start, "\n".join(buffer)


def owner_for_line(ranges: list[tuple[str, int, int | None]], line: int) -> str | None:
    for owner, start, end in reversed(ranges):
        if start <= line and (end is None or line <= end):
            return owner
    return None


def parse_light(path: Path, root: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    source = strip_comments(read_text(path))
    lines = source.splitlines()
    symbols: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    fields: list[dict[str, Any]] = []

    class_lines: dict[int, str] = {}
    collecting = False
    buffer: list[str] = []
    start = 0
    for line_no, line in enumerate(lines, 1):
        if not collecting and re.match(r"^\s*(?:virtual\s+)?class\b", line):
            collecting = True
            start = line_no
            buffer = [line]
        elif collecting:
            buffer.append(line)
        if collecting and ";" in line:
            match = CLASS_RE.match(" ".join("\n".join(buffer).split()))
            if match:
                name = match.group(2)
                base = normalize_type(match.group(4))
                symbols.append({"id": name, "kind": "class", "name": name, "base": base, "role": classify_role(name, base), "file": relative, "line": start})
                class_lines[start] = name
                if base:
                    relations.append({"kind": "extends", "source": name, "target": base, "file": relative, "line": start})
            collecting = False
            buffer = []

    ranges: list[tuple[str, int, int | None]] = []
    stack: list[tuple[str, int]] = []
    for line_no, line in enumerate(lines, 1):
        if line_no in class_lines:
            stack.append((class_lines[line_no], line_no))
        if re.match(r"^\s*endclass\b", line) and stack:
            owner, begin = stack.pop()
            ranges.append((owner, begin, line_no))
        declaration = MODULE_RE.match(line)
        if declaration:
            kind, name = declaration.groups()
            symbols.append({"id": name, "kind": kind, "name": name, "role": "interface" if kind == "interface" else kind, "file": relative, "line": line_no})
        include = INCLUDE_RE.match(line)
        if include:
            relations.append({"kind": "include", "source": relative, "target": include.group(1), "file": relative, "line": line_no})
        package_import = IMPORT_RE.match(line)
        if package_import:
            relations.append({"kind": "import", "source": relative, "target": package_import.group(1), "file": relative, "line": line_no})
    for owner, begin in stack:
        ranges.append((owner, begin, None))

    method_ranges: list[tuple[str, int, int | None]] = []
    current_method: tuple[str, int] | None = None
    for line_no, line in enumerate(lines, 1):
        method = METHOD_RE.match(line)
        if method:
            owner = method.group("class") or owner_for_line(ranges, line_no)
            name = method.group("name")
            if owner:
                symbol_id = f"{owner}.{name}"
                symbols.append({"id": symbol_id, "kind": method.group("kind"), "name": name, "owner": owner, "role": method.group("kind"), "file": relative, "line": line_no})
            if method.group("class"):
                current_method = (method.group("class"), line_no)
        if current_method and re.match(r"^\s*end(?:function|task)\b", line):
            owner, begin = current_method
            method_ranges.append((owner, begin, line_no))
            current_method = None

    for line_no, statement in statement_chunks(lines):
        clean = statement

        def location(offset: int) -> int:
            return line_no + clean[:offset].count("\n")

        def statement_owner(offset: int) -> str:
            match_line = location(offset)
            return owner_for_line(ranges, match_line) or owner_for_line(method_ranges, match_line) or relative

        if "::type_id" in clean and "create" in clean:
            for match in CREATE_RE.finditer(clean):
                match_line = location(match.start())
                args = balanced_args(clean, match.end() - 1)
                values = split_args(args or "")
                instance_name = argument(args or "", 0)
                assignment = re.search(r"([A-Za-z_]\w*(?:\s*\[[^\]]+\])?)\s*=\s*$", clean[: match.start()])
                instance = assignment.group(1).replace(" ", "") if assignment else instance_name
                relation = {
                    "kind": "creates",
                    "source": statement_owner(match.start()),
                    "target": normalize_type(match.group(1)),
                    "instance": instance,
                    "file": relative,
                    "line": match_line,
                }
                if instance_name and instance_name != instance:
                    relation["instance_name"] = instance_name
                if len(values) > 1:
                    relation["parent"] = argument(args or "", 1)
                relations.append(relation)
        if VENDOR_NEW_TOKEN in clean:
            for match in VENDOR_NEW_RE.finditer(clean):
                match_line = location(match.start())
                opening = clean.find("(", match.start(), match.end())
                args = balanced_args(clean, opening) if opening >= 0 else None
                relations.append({"kind": "creates", "source": statement_owner(match.start()), "target": normalize_type(match.group(1)), "instance": argument(args or "", 1), "file": relative, "line": match_line})
        if "uvm_" in clean and any(term in clean for term in ("port", "export", "imp")):
            for match in TLM_DECL_RE.finditer(clean):
                match_line = location(match.start())
                ptype = match.group("port_type")
                params = " ".join((match.group("params") or "").split())
                for variable in match.group("vars").split(","):
                    port = variable.strip().split("[", 1)[0].strip()
                    relations.append({"kind": "declares_tlm_port", "source": statement_owner(match.start()), "target": port, "port_type": ptype, "port_family": port_family(ptype), "direction": port_direction(ptype), "transaction_types": split_args(params) if params else [], "file": relative, "line": match_line})
        if "connect" in clean and "." in clean:
            for match in CONNECT_RE.finditer(clean):
                match_line = location(match.start())
                lhs, rhs = match.groups()
                kind = "seq_item_connect" if "seq_item" in lhs or "seq_item" in rhs else "tlm_connect"
                owner = statement_owner(match.start())
                relations.append({"kind": kind, "source": f"{owner}.{lhs}", "target": rhs, "context": owner, "lhs": lhs, "rhs": rhs, "file": relative, "line": match_line})
        if "uvm_config_db" in clean:
            for match in CONFIG_RE.finditer(clean):
                match_line = location(match.start())
                args = balanced_args(clean, match.end() - 1)
                if args is not None:
                    relation = {
                        "kind": f"config_db_{match.group(2)}",
                        "source": statement_owner(match.start()),
                        "target": argument(args, 2),
                        "config_type": " ".join(match.group(1).split()),
                        "file": relative,
                        "line": match_line,
                    }
                    scope = argument(args, 1)
                    value = argument(args, 3)
                    if scope is not None:
                        relation["scope"] = scope
                    if value is not None:
                        relation["value"] = value
                    relations.append(relation)

        field = FIELD_RE.match(clean) if len(clean) < 16384 else None
        if field:
            for variable in field.group("vars").split(","):
                fields.append({"owner": statement_owner(field.start()), "type": field.group("type"), "instance": variable.strip().split("[", 1)[0].strip(), "file": relative, "line": location(field.start())})

    return {"symbols": symbols, "relations": relations, "fields": fields, "parser": "light", "diagnostics": 0}


def _syntax_declarations(tree: Any, path: Path, syntax: Any) -> list[tuple[str, str, int]]:
    """Return declarations physically defined in path, excluding included files."""

    output: list[tuple[str, str, int]] = []
    expected = os.path.normcase(str(path.resolve()))
    mapping = {
        "ClassDeclaration": "class",
        "ModuleDeclaration": "module",
        "InterfaceDeclaration": "interface",
        "ProgramDeclaration": "program",
        "PackageDeclaration": "package",
        "FunctionDeclaration": "function",
        "TaskDeclaration": "task",
    }

    def handler(kind: str) -> Callable[[Any], None]:
        def visit(node: Any) -> None:
            token = getattr(node, "name", None)
            name = getattr(token, "valueText", None)
            if not name:
                return
            location = node.sourceRange.start
            filename = Path(str(tree.sourceManager.getFileName(location)))
            if not filename.is_absolute():
                filename = (Path.cwd() / filename).resolve()
            if os.path.normcase(str(filename.resolve())) != expected:
                return
            output.append((kind, str(name), int(tree.sourceManager.getLineNumber(location))))

        return visit

    lookup = {
        syntax_kind: handler(kind)
        for syntax_name, kind in mapping.items()
        if (syntax_kind := getattr(syntax.SyntaxKind, syntax_name, None)) is not None
    }
    tree.root.visit(lookup_table=lookup)
    return output


def parse_with_pyslang(
    path: Path,
    root: Path,
    syntax: Any,
    include_dirs: Iterable[Path] = (),
    defines: Iterable[str] = (),
) -> dict[str, Any]:
    result = parse_light(path, root)
    include_paths = [str(item) for item in include_dirs]
    predefined = list(defines)
    if include_paths or predefined:
        import pyslang  # type: ignore
        from pyslang import parsing  # type: ignore

        preprocessor = parsing.PreprocessorOptions()
        preprocessor.additionalIncludePaths = include_paths
        preprocessor.predefines = predefined
        tree = syntax.SyntaxTree.fromFile(str(path), pyslang.SourceManager(), pyslang.Bag([preprocessor]))
    else:
        tree = syntax.SyntaxTree.fromFile(str(path))
    declarations = _syntax_declarations(tree, path, syntax)
    existing = {(item["kind"], item["name"]) for item in result["symbols"]}
    relative = path.relative_to(root).as_posix()
    for kind, name, line in declarations:
        if (kind, name) not in existing:
            result["symbols"].append({"id": name, "kind": kind, "name": name, "role": classify_role(name) if kind == "class" else kind, "file": relative, "line": line, "pyslang_only": True})
    result["parser"] = "pyslang"
    result["diagnostics"] = len(tree.diagnostics)
    return result


def try_pyslang() -> Any | None:
    try:
        from pyslang import syntax  # type: ignore

        return syntax
    except Exception:
        return None


def resolve_parser(requested: str) -> tuple[str, Any | None]:
    syntax = try_pyslang()
    if requested == "light":
        return "light", None
    if requested == "pyslang":
        if syntax is None:
            raise RuntimeError("pyslang mode requested but pyslang is not installed; run scripts/install_offline.py")
        return "pyslang", syntax
    return ("pyslang", syntax) if syntax is not None else ("light", None)


def iter_sources(root: Path) -> Iterable[Path]:
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS)
        for filename in sorted(filenames):
            path = Path(directory) / filename
            if path.suffix.lower() in SOURCE_EXTS:
                yield path


def file_signature(path: Path) -> dict[str, Any]:
    stat = path.stat()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "sha256": digest}


def load_cache(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if value.get("cache_version") == CACHE_VERSION else {}
    except (OSError, ValueError, TypeError):
        return {}


def save_cache(path: Path, parser: str, entries: dict[str, Any], context_fingerprint: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cache_version": CACHE_VERSION,
        "parser": parser,
        "context_fingerprint": context_fingerprint,
        "entries": entries,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _dedupe(items: list[dict[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    output: list[dict[str, Any]] = []
    for item in items:
        key = tuple(item.get(field) for field in fields)
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output


def build_hierarchies(symbols: list[dict[str, Any]], relations: list[dict[str, Any]]) -> dict[str, Any]:
    classes = {item["name"]: item for item in symbols if item.get("kind") == "class"}

    def relation_tree(kinds: set[str], reverse: bool = False) -> dict[str, Any]:
        children: dict[str, list[dict[str, Any]]] = {}
        edge_positions: dict[tuple[str, str, str], int] = {}
        parents: set[str] = set()
        child_names: set[str] = set()
        for relation in relations:
            if relation.get("kind") not in kinds:
                continue
            source = str(relation.get("source", "")).split(".", 1)[0]
            target = str(relation.get("target", "")).split(".")[-1]
            parent, child = (target, source) if reverse else (source, target)
            if not parent or not child or parent == child:
                continue
            definition_missing = child not in classes
            if not reverse:
                if parent not in classes:
                    continue
                # A parent-bearing factory create is sufficient instance evidence
                # even when the vendor component type is outside the index.
                if definition_missing and not (
                    relation.get("kind") == "creates" and relation.get("parent")
                ):
                    continue
            item = {
                "id": child,
                "instance": relation.get("instance"),
                "kind": relation.get("kind"),
                "file": relation.get("file"),
                "line": relation.get("line"),
            }
            if not reverse and definition_missing:
                item["definition_missing"] = True
            instance_key = "" if reverse else str(item.get("instance") or "")
            edge_key = (parent, child, instance_key)
            siblings = children.setdefault(parent, [])
            prior_position = edge_positions.get(edge_key)
            if prior_position is None:
                edge_positions[edge_key] = len(siblings)
                siblings.append(item)
            elif siblings[prior_position].get("kind") == "has_member" and item.get("kind") == "creates":
                # A build-phase create and its class member declaration describe the same instance.
                siblings[prior_position] = item
            parents.add(parent)
            child_names.add(child)
        roots = sorted(parents - child_names, key=lambda name: ({"test": 0, "env": 1, "agent": 2}.get(classes.get(name, {}).get("role", ""), 9), name))
        if not roots:
            roots = sorted(parents, key=lambda name: (-len(children.get(name, [])), name))[:80]
        for key in children:
            children[key] = sorted(children[key], key=lambda item: (str(item.get("instance") or ""), item["id"]))
        return {"roots": roots, "children": children}

    return {
        "topology": relation_tree({"creates", "has_member"}),
        "inheritance": relation_tree({"extends"}, reverse=True),
    }


def build_uvm_architecture(symbols: list[dict[str, Any]], relations: list[dict[str, Any]]) -> dict[str, Any]:
    """Project parser facts into a static, instance-oriented UVM architecture."""

    component_roles = {"test", "env", "agent", "driver", "monitor", "sequencer", "scoreboard", "coverage"}
    object_roles = {"config", "sequence", "sequence_item"}
    component_bases = {
        "uvm_component",
        "uvm_test",
        "uvm_env",
        "uvm_agent",
        "uvm_driver",
        "uvm_monitor",
        "uvm_sequencer",
        "uvm_scoreboard",
        "uvm_subscriber",
        "uvm_reg_predictor",
    }
    object_bases = {"uvm_object", "uvm_sequence", "uvm_sequence_item", "uvm_transaction", "uvm_report_object"}
    role_order = {
        "test": 0,
        "env": 1,
        "agent": 2,
        "sequencer": 3,
        "driver": 4,
        "monitor": 5,
        "scoreboard": 6,
        "coverage": 7,
        "component": 8,
        "config": 9,
    }

    def symbol_score(item: dict[str, Any]) -> tuple[int, int, int]:
        return (
            0 if item.get("pyslang_only") else 1,
            1 if item.get("base") else 0,
            1 if int(item.get("line") or 1) > 1 else 0,
        )

    classes: dict[str, dict[str, Any]] = {}
    for item in symbols:
        if item.get("kind") != "class" or not item.get("name"):
            continue
        name = str(item["name"])
        if name not in classes or symbol_score(item) > symbol_score(classes[name]):
            classes[name] = dict(item)

    base_by_name = {name: item.get("base") for name, item in classes.items()}
    for relation in relations:
        if relation.get("kind") != "extends":
            continue
        source = str(relation.get("source") or "")
        target = normalize_type(str(relation.get("target") or ""))
        if source in classes and target and not base_by_name.get(source):
            base_by_name[source] = target

    def short_type(value: str | None) -> str:
        return str(value or "").split(".")[-1]

    def class_name(value: Any) -> str:
        text = str(value or "")
        return text if text in classes else short_type(text)

    component_status: dict[str, bool] = {}
    component_reason: dict[str, str] = {}

    def is_component(name: str, visiting: set[str] | None = None) -> bool:
        if name in component_status:
            return component_status[name]
        item = classes.get(name)
        if not item:
            return False
        visiting = set() if visiting is None else set(visiting)
        if name in visiting:
            return False
        visiting.add(name)
        base = class_name(base_by_name.get(name))
        terminal = short_type(base).lower()
        if terminal in component_bases:
            component_status[name] = True
            component_reason[name] = "uvm_base"
            return True
        if terminal.endswith("_component") or terminal == "component":
            component_status[name] = True
            component_reason[name] = "component_base"
            return True
        if terminal in object_bases:
            component_status[name] = False
            return False
        if base in classes and is_component(base, visiting):
            component_status[name] = True
            component_reason[name] = "base_chain"
            return True
        role = str(item.get("role") or "")
        inferred = not base and role in component_roles and "uvm" in name.lower()
        component_status[name] = inferred
        if inferred:
            component_reason[name] = "uvm_role"
        return inferred

    for name in classes:
        is_component(name)

    # A parent-bearing factory create is strong component evidence even when a
    # proprietary base class is outside the indexed source tree.
    changed = True
    while changed:
        changed = False
        for relation in relations:
            if relation.get("kind") != "creates" or not relation.get("parent"):
                continue
            source = class_name(str(relation.get("source") or "").split(".", 1)[0])
            target = class_name(relation.get("target"))
            target_item = classes.get(target)
            if not component_status.get(source, False) or not target_item:
                continue
            if target_item.get("role") in object_roles or short_type(base_by_name.get(target)).lower() in object_bases:
                continue
            if not component_status.get(target, False):
                component_status[target] = True
                component_reason[target] = "component_factory_create"
                changed = True

    component_names = {name for name, status in component_status.items() if status}

    def declared_component_role(name: str) -> str:
        role = str(classes.get(name, {}).get("role") or "component")
        return role if role in component_roles else "component"

    def inferred_instance_role(type_name: str, instance: str | None = None) -> str:
        declared = declared_component_role(type_name)
        if declared != "component":
            return declared
        normalized = re.sub(r"[^a-z0-9]+", "_", f"{instance or ''}_{type_name}").strip("_").lower()
        patterns = [
            ("scoreboard", r"(?:^|_)(?:scoreboard|scbd|sbd)(?:_|$|\d)"),
            ("sequencer", r"(?:^|_)(?:sequencer|seqr)(?:_|$|\d)"),
            ("monitor", r"(?:^|_)(?:monitor|mon)(?:_|$|\d)"),
            ("driver", r"(?:^|_)(?:driver|drv)(?:_|$|\d)"),
            ("coverage", r"(?:^|_)(?:coverage|cov)(?:_|$|\d)"),
            ("agent", r"(?:^|_)agent(?:_|$|\d)"),
            ("env", r"(?:^|_)env(?:_|$|\d)"),
        ]
        for role, pattern in patterns:
            if re.search(pattern, normalized):
                return role
        return "component"

    def edge_key(edge: dict[str, Any]) -> str:
        instance = str(edge.get("instance") or "")
        return instance if instance else f"@type:{edge.get('type')}"

    def relation_edge(relation: dict[str, Any], source: str, target: str, role: str) -> dict[str, Any]:
        instance = str(relation.get("instance") or "").strip()
        edge = {
            "instance": instance or target,
            "type": target,
            "role": role,
            "relation": relation.get("kind"),
            "declared_in": source,
            "file": relation.get("file"),
            "line": relation.get("line"),
            "confidence": "high" if relation.get("kind") == "creates" else "medium",
        }
        if relation.get("instance_name"):
            edge["instance_name"] = relation["instance_name"]
        qualified_type = str(relation.get("target") or "")
        if qualified_type and qualified_type != target:
            edge["qualified_type"] = qualified_type
        return edge

    direct_children: dict[str, dict[str, dict[str, Any]]] = {}
    direct_auxiliaries: dict[str, dict[str, dict[str, Any]]] = {}
    for relation in relations:
        if relation.get("kind") not in {"creates", "has_member"}:
            continue
        source = class_name(str(relation.get("source") or "").split(".", 1)[0])
        target = class_name(relation.get("target"))
        if source not in component_names or source == target:
            continue
        instance = str(relation.get("instance") or "").strip()
        definition_missing = target not in classes
        if definition_missing:
            # uvm_component factory creation carries a parent argument. Keep
            # that evidence without promoting unknown uvm_object creates.
            if relation.get("kind") != "creates" or not relation.get("parent"):
                continue
            edge = relation_edge(relation, source, target, inferred_instance_role(target, instance))
            edge["definition_missing"] = True
            siblings = direct_children.setdefault(source, {})
        elif target in component_names:
            edge = relation_edge(relation, source, target, inferred_instance_role(target, instance))
            siblings = direct_children.setdefault(source, {})
        else:
            target_role = str(classes[target].get("role") or classify_role(target, base_by_name.get(target)))
            if target_role != "config":
                continue
            edge = relation_edge(relation, source, target, "config")
            siblings = direct_auxiliaries.setdefault(source, {})
        key = instance or f"@type:{target}"
        prior = siblings.get(key)
        if prior is None or (prior.get("relation") == "has_member" and edge["relation"] == "creates"):
            siblings[key] = edge

    def effective_edges(
        name: str,
        direct: dict[str, dict[str, dict[str, Any]]],
        cache: dict[str, list[dict[str, Any]]],
        visiting: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        if name in cache:
            return [dict(item) for item in cache[name]]
        visiting = set() if visiting is None else set(visiting)
        if name in visiting:
            return []
        visiting.add(name)
        merged: dict[str, dict[str, Any]] = {}
        base = class_name(base_by_name.get(name))
        if base in component_names:
            for child in effective_edges(base, direct, cache, visiting):
                merged[edge_key(child)] = dict(child)
        for child in direct.get(name, {}).values():
            merged[edge_key(child)] = dict(child)
        output = []
        for child in merged.values():
            child["inherited"] = child.get("declared_in") != name
            output.append(child)
        output.sort(key=lambda item: (role_order.get(str(item.get("role")), 99), str(item.get("instance") or ""), str(item.get("type") or "")))
        cache[name] = output
        return [dict(item) for item in output]

    child_cache: dict[str, list[dict[str, Any]]] = {}
    auxiliary_cache: dict[str, list[dict[str, Any]]] = {}

    def effective_children(name: str) -> list[dict[str, Any]]:
        return effective_edges(name, direct_children, child_cache)

    def effective_auxiliaries(name: str) -> list[dict[str, Any]]:
        return effective_edges(name, direct_auxiliaries, auxiliary_cache)

    direct_ports: dict[str, dict[str, dict[str, Any]]] = {}
    direct_config_accesses: dict[str, list[dict[str, Any]]] = {}
    direct_connections: dict[str, list[dict[str, Any]]] = {}
    for relation in relations:
        kind = str(relation.get("kind") or "")
        if kind == "declares_tlm_port":
            owner = class_name(str(relation.get("source") or "").split(".", 1)[0])
            if owner not in component_names:
                continue
            name = str(relation.get("target") or "")
            direct_ports.setdefault(owner, {})[name] = {
                "name": name,
                "port_type": relation.get("port_type"),
                "family": relation.get("port_family"),
                "direction": relation.get("direction"),
                "transaction_types": relation.get("transaction_types", []),
                "declared_in": owner,
                "file": relation.get("file"),
                "line": relation.get("line"),
            }
        elif kind in {"config_db_get", "config_db_set"}:
            owner = class_name(str(relation.get("source") or "").split(".", 1)[0])
            if owner not in component_names:
                continue
            direct_config_accesses.setdefault(owner, []).append(
                {
                    "operation": kind.rsplit("_", 1)[-1],
                    "field": relation.get("target"),
                    "config_type": relation.get("config_type"),
                    "scope": relation.get("scope"),
                    "value": relation.get("value"),
                    "declared_in": owner,
                    "file": relation.get("file"),
                    "line": relation.get("line"),
                }
            )
        elif kind in {"tlm_connect", "seq_item_connect"}:
            owner = class_name(relation.get("context") or str(relation.get("source") or "").split(".", 1)[0])
            if owner not in component_names:
                continue
            direct_connections.setdefault(owner, []).append(
                {
                    "kind": kind,
                    "lhs": relation.get("lhs") or relation.get("source"),
                    "rhs": relation.get("rhs") or relation.get("target"),
                    "declared_in": owner,
                    "file": relation.get("file"),
                    "line": relation.get("line"),
                }
            )

    port_cache: dict[str, list[dict[str, Any]]] = {}
    config_access_cache: dict[str, list[dict[str, Any]]] = {}
    connection_cache: dict[str, list[dict[str, Any]]] = {}

    def effective_ports(name: str, visiting: set[str] | None = None) -> list[dict[str, Any]]:
        if name in port_cache:
            return [dict(item) for item in port_cache[name]]
        visiting = set() if visiting is None else set(visiting)
        if name in visiting:
            return []
        visiting.add(name)
        merged: dict[str, dict[str, Any]] = {}
        base = class_name(base_by_name.get(name))
        if base in component_names:
            for port in effective_ports(base, visiting):
                merged[str(port.get("name") or "")] = dict(port)
        for key, port in direct_ports.get(name, {}).items():
            merged[key] = dict(port)
        output = []
        for port in merged.values():
            port["inherited"] = port.get("declared_in") != name
            output.append(port)
        output.sort(key=lambda item: str(item.get("name") or ""))
        port_cache[name] = output
        return [dict(item) for item in output]

    def effective_list(
        name: str,
        direct: dict[str, list[dict[str, Any]]],
        cache: dict[str, list[dict[str, Any]]],
        key_fields: tuple[str, ...],
        visiting: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        if name in cache:
            return [dict(item) for item in cache[name]]
        visiting = set() if visiting is None else set(visiting)
        if name in visiting:
            return []
        visiting.add(name)
        merged: dict[tuple[Any, ...], dict[str, Any]] = {}
        base = class_name(base_by_name.get(name))
        if base in component_names:
            for item in effective_list(base, direct, cache, key_fields, visiting):
                merged[tuple(item.get(field) for field in key_fields)] = dict(item)
        for item in direct.get(name, []):
            merged[tuple(item.get(field) for field in key_fields)] = dict(item)
        output = []
        for item in merged.values():
            item["inherited"] = item.get("declared_in") != name
            output.append(item)
        cache[name] = output
        return [dict(item) for item in output]

    def effective_config_accesses(name: str) -> list[dict[str, Any]]:
        return effective_list(name, direct_config_accesses, config_access_cache, ("operation", "field", "config_type", "file", "line"))

    def effective_connections(name: str) -> list[dict[str, Any]]:
        return effective_list(name, direct_connections, connection_cache, ("kind", "lhs", "rhs", "file", "line"))

    def match_child(type_name: str, token: str) -> dict[str, Any] | None:
        token_base = re.sub(r"\[[^\]]*\]", "", token)
        candidates = effective_children(type_name)
        for child in candidates:
            if str(child.get("instance") or "") == token:
                return child
        for child in candidates:
            child_base = re.sub(r"\[[^\]]*\]", "", str(child.get("instance") or ""))
            if child_base == token_base:
                return child
        return None

    def resolve_endpoint(context: str, expression: Any) -> dict[str, Any]:
        raw = str(expression or "")
        clean = re.sub(r"\s+", "", raw)
        parts = [part for part in clean.split(".") if part and part != "this"]
        path_tokens, port_name = (parts[:-1], parts[-1]) if parts else ([], "")
        current_type = context
        instance_path: list[str] = []
        path_resolved = True
        owner_role = inferred_instance_role(context, context)
        unresolved_at = None
        for token in path_tokens:
            child = match_child(current_type, token)
            if not child:
                path_resolved = False
                unresolved_at = token
                break
            instance_path.append(str(child.get("instance") or token))
            current_type = str(child.get("type") or current_type)
            owner_role = str(child.get("role") or inferred_instance_role(current_type, token))
        port = next((item for item in effective_ports(current_type) if item.get("name") == port_name), None) if path_resolved else None
        output = {
            "expression": raw,
            "requested_path": path_tokens,
            "instance_path": instance_path,
            "owner_type": current_type,
            "owner_role": owner_role,
            "port": port_name,
            "path_resolved": path_resolved,
            "port_declared": bool(port),
            "confidence": "high" if path_resolved and port else "medium" if path_resolved else "low",
        }
        if unresolved_at:
            output["unresolved_at"] = unresolved_at
        if port:
            output.update(
                {
                    "port_type": port.get("port_type"),
                    "family": port.get("family"),
                    "direction": port.get("direction"),
                    "transaction_types": port.get("transaction_types", []),
                }
            )
        return output

    def resolved_connection(context: str, item: dict[str, Any]) -> dict[str, Any]:
        lhs = resolve_endpoint(context, item.get("lhs"))
        rhs = resolve_endpoint(context, item.get("rhs"))
        return {
            **item,
            "context": context,
            "source_endpoint": lhs,
            "target_endpoint": rhs,
            "resolved": bool(lhs["path_resolved"] and rhs["path_resolved"]),
            "confidence": "high" if lhs["path_resolved"] and rhs["path_resolved"] else "low",
        }

    def virtual_interface_type(config_type: Any) -> str | None:
        value = str(config_type or "").strip()
        if not value.lower().startswith("virtual "):
            return None
        value = value[8:].strip()
        if value.lower().startswith("interface "):
            value = value[10:].strip()
        value = value.split("#", 1)[0].split()[0]
        return normalize_type(value.split(".", 1)[0])

    def virtual_interfaces(accesses: list[dict[str, Any]]) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()
        for access in accesses:
            interface_type = virtual_interface_type(access.get("config_type"))
            if not interface_type:
                continue
            key = (interface_type, access.get("field"), access.get("operation"), access.get("file"), access.get("line"))
            if key in seen:
                continue
            seen.add(key)
            output.append(
                {
                    "type": interface_type,
                    "field": access.get("field"),
                    "operation": access.get("operation"),
                    "scope": access.get("scope"),
                    "declared_in": access.get("declared_in"),
                    "inherited": access.get("inherited", False),
                    "file": access.get("file"),
                    "line": access.get("line"),
                    "confidence": "high",
                }
            )
        return output

    def descendants(name: str, visiting: set[str] | None = None) -> set[str]:
        visiting = set() if visiting is None else set(visiting)
        if name in visiting:
            return set()
        visiting.add(name)
        output: set[str] = set()
        for child in effective_children(name):
            child_type = str(child.get("type") or "")
            if not child_type or child_type in visiting:
                continue
            output.add(child_type)
            output.update(descendants(child_type, visiting))
        return output

    components: dict[str, dict[str, Any]] = {}
    for name in sorted(component_names):
        symbol = classes[name]
        children = effective_children(name)
        auxiliaries = effective_auxiliaries(name)
        ports = effective_ports(name)
        accesses = effective_config_accesses(name)
        connections = [resolved_connection(name, item) for item in effective_connections(name)]
        declared_count = sum(1 for child in children if not child.get("inherited"))
        components[name] = {
            "type": name,
            "role": declared_component_role(name),
            "base": base_by_name.get(name),
            "file": symbol.get("file"),
            "line": symbol.get("line"),
            "classification": component_reason.get(name, "component_relation"),
            "children": children,
            "auxiliaries": auxiliaries,
            "ports": ports,
            "connections": connections,
            "config_accesses": accesses,
            "virtual_interfaces": virtual_interfaces(accesses),
            "child_count": len(children),
            "declared_child_count": declared_count,
            "inherited_child_count": len(children) - declared_count,
            "auxiliary_count": len(auxiliaries),
            "descendant_type_count": len(descendants(name)),
            "port_count": len(ports),
            "connection_count": len(connections),
        }

    unresolved_by_type: dict[str, dict[str, Any]] = {}
    for owner, component in components.items():
        for child in component["children"]:
            if not child.get("definition_missing"):
                continue
            type_name = str(child.get("type") or "")
            unresolved = unresolved_by_type.setdefault(
                type_name,
                {"type": type_name, "role": child.get("role") or "component", "instances": []},
            )
            unresolved["instances"].append(
                {
                    "owner": owner,
                    "instance": child.get("instance"),
                    "relation": child.get("relation"),
                    "file": child.get("file"),
                    "line": child.get("line"),
                    "inherited": child.get("inherited", False),
                }
            )
    unresolved_components = sorted(unresolved_by_type.values(), key=lambda item: item["type"])

    contained_types = {str(child.get("type")) for item in components.values() for child in item["children"]}
    candidates = [name for name, item in components.items() if item["child_count"] and item["role"] == "test"]
    candidates.extend(name for name, item in components.items() if item["child_count"] and item["role"] == "env" and name not in contained_types)
    candidates.extend(name for name, item in components.items() if item["child_count"] and name not in contained_types)
    candidates = list(dict.fromkeys(candidates))
    if not candidates:
        candidates = [name for name, item in components.items() if item["child_count"]]

    def root_key(name: str) -> tuple[Any, ...]:
        item = components[name]
        return (
            role_order.get(item["role"], 99),
            0 if "uvm" in name.lower() else 1,
            0 if item["declared_child_count"] else 1,
            0 if name.lower().endswith("_base") else 1,
            -item["descendant_type_count"],
            name,
        )

    candidates.sort(key=root_key)
    roots = [
        {
            "type": name,
            "role": components[name]["role"],
            "child_count": components[name]["child_count"],
            "descendant_type_count": components[name]["descendant_type_count"],
            "file": components[name]["file"],
            "line": components[name]["line"],
        }
        for name in candidates
    ]
    architecture_connections = [
        resolved_connection(name, item)
        for name in sorted(component_names)
        for item in direct_connections.get(name, [])
    ]
    external_interfaces = sorted(
        [
            {"name": item.get("name"), "role": "interface", "file": item.get("file"), "line": item.get("line")}
            for item in symbols
            if item.get("kind") == "interface" and item.get("name")
        ],
        key=lambda item: (str(item.get("name") or ""), str(item.get("file") or "")),
    )
    external_modules = sorted(
        [
            {"name": item.get("name"), "role": "module", "file": item.get("file"), "line": item.get("line")}
            for item in symbols
            if item.get("kind") == "module" and item.get("name")
        ],
        key=lambda item: (str(item.get("name") or ""), str(item.get("file") or "")),
    )
    return {
        "schema_version": ARCHITECTURE_SCHEMA_VERSION,
        "inference": {
            "mode": "static_source",
            "runtime_elaborated": False,
            "evidence": [
                "component inheritance",
                "factory create",
                "component member declaration",
                "TLM connect call",
                "config-db virtual interface access",
            ],
            "limitations": [
                "factory overrides",
                "conditional build paths",
                "dynamic instance counts",
                "runtime config effects",
                "exact BFM and DUT binding",
            ],
        },
        "default_root": candidates[0] if candidates else None,
        "roots": roots,
        "components": components,
        "unresolved_components": unresolved_components,
        "connections": architecture_connections,
        "externals": {"interfaces": external_interfaces, "modules": external_modules},
    }


def build_tlm(symbols: list[dict[str, Any]], relations: list[dict[str, Any]]) -> dict[str, Any]:
    classes = {item["name"]: item for item in symbols if item.get("kind") == "class"}
    ports: list[dict[str, Any]] = []
    connections: list[dict[str, Any]] = []
    for relation in relations:
        if relation.get("kind") == "declares_tlm_port":
            owner = str(relation.get("source", "")).split(".", 1)[0]
            ports.append({"owner": owner, "owner_role": classes.get(owner, {}).get("role", "class"), "name": relation.get("target"), "port_type": relation.get("port_type"), "family": relation.get("port_family"), "direction": relation.get("direction"), "transaction_types": relation.get("transaction_types", []), "file": relation.get("file"), "line": relation.get("line")})
        elif relation.get("kind") in {"tlm_connect", "seq_item_connect"}:
            connections.append({"kind": relation.get("kind"), "context": relation.get("context") or str(relation.get("source", "")).split(".", 1)[0], "lhs": relation.get("lhs") or relation.get("source"), "rhs": relation.get("rhs") or relation.get("target"), "file": relation.get("file"), "line": relation.get("line")})
    return {"ports": ports, "connections": connections}


def build_snippets(root: Path, locations: list[dict[str, Any]], context: int, limit: int = 2500) -> dict[str, Any]:
    if context <= 0:
        return {}
    wanted: dict[tuple[str, int], None] = {}
    for item in locations:
        file = item.get("file")
        line = item.get("line")
        if file and line:
            wanted.setdefault((str(file), int(line)), None)
            if len(wanted) >= limit:
                break
    file_cache: dict[str, list[str]] = {}
    snippets: dict[str, Any] = {}
    for file, line in wanted:
        try:
            lines = file_cache.setdefault(file, read_text(root / file).splitlines())
        except OSError:
            continue
        start = max(1, line - context)
        end = min(len(lines), line + context)
        snippets[f"{file}:{line}"] = {"file": file, "line": line, "start": start, "end": end, "lines": [{"line": index, "text": lines[index - 1]} for index in range(start, end + 1)]}
    return snippets


def build_index(
    source_root: Path,
    parser_requested: str,
    cache_path: Path,
    source_context: int = 15,
    rebuild: bool = False,
    progress: Callable[[int, int, str], None] | None = None,
    source_paths: Iterable[Path] | None = None,
    include_dirs: Iterable[Path] = (),
    defines: Iterable[str] = (),
    input_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_root = source_root.resolve()
    parser_effective, syntax = resolve_parser(parser_requested)
    include_paths = [path.resolve() for path in include_dirs]
    predefined = list(defines)
    context_payload = json.dumps(
        {"include_dirs": [str(path) for path in include_paths], "defines": predefined},
        sort_keys=True,
        separators=(",", ":"),
    )
    context_fingerprint = hashlib.sha256(context_payload.encode()).hexdigest()
    previous = {} if rebuild else load_cache(cache_path)
    previous_entries = (
        previous.get("entries", {})
        if previous.get("parser") == parser_effective
        and previous.get("context_fingerprint", "") == context_fingerprint
        else {}
    )
    entries: dict[str, Any] = {}
    files_meta: list[dict[str, Any]] = []
    reparsed = 0
    reused = 0

    requested_paths = list(source_paths) if source_paths is not None else list(iter_sources(source_root))
    selected_paths: list[Path] = []
    seen_paths: set[Path] = set()
    for requested_path in requested_paths:
        path = requested_path.resolve()
        try:
            path.relative_to(source_root)
        except ValueError as exc:
            raise RuntimeError(f"source file is outside the configured source root: {path}") from exc
        if path.suffix.lower() not in SOURCE_EXTS or not path.is_file() or path in seen_paths:
            continue
        seen_paths.add(path)
        selected_paths.append(path)

    total_files = len(selected_paths)
    for file_number, path in enumerate(selected_paths, 1):
        relative = path.relative_to(source_root).as_posix()
        signature = file_signature(path)
        cached = previous_entries.get(relative)
        if cached and cached.get("signature") == signature:
            parsed = cached["parsed"]
            reused += 1
        else:
            try:
                if parser_effective == "pyslang" and signature["size"] > PYSLANG_AST_MAX_BYTES:
                    parsed = parse_light(path, source_root)
                    parsed["parser"] = "light-large-file"
                    parsed["parser_note"] = f"pyslang AST JSON skipped above {PYSLANG_AST_MAX_BYTES} bytes"
                else:
                    parsed = (
                        parse_with_pyslang(path, source_root, syntax, include_paths, predefined)
                        if parser_effective == "pyslang"
                        else parse_light(path, source_root)
                    )
            except Exception as exc:
                parsed = parse_light(path, source_root)
                parsed["parser"] = "light-fallback"
                parsed["parser_error"] = str(exc)
            reparsed += 1
        entries[relative] = {"signature": signature, "parsed": parsed}
        file_meta = {"path": relative, **signature, "parser": parsed.get("parser"), "diagnostics": parsed.get("diagnostics", 0)}
        if parsed.get("parser_error"):
            file_meta["parser_error"] = parsed["parser_error"]
        if parsed.get("parser_note"):
            file_meta["parser_note"] = parsed["parser_note"]
        files_meta.append(file_meta)
        if progress and (file_number == 1 or file_number % 25 == 0 or file_number == total_files):
            progress(file_number, total_files, relative)
        if file_number % 25 == 0:
            save_cache(cache_path, parser_effective, entries, context_fingerprint)

    save_cache(cache_path, parser_effective, entries, context_fingerprint)
    symbols = [symbol for entry in entries.values() for symbol in entry["parsed"].get("symbols", [])]
    relations = [relation for entry in entries.values() for relation in entry["parsed"].get("relations", [])]
    fields = [field for entry in entries.values() for field in entry["parsed"].get("fields", [])]
    symbols = _dedupe(symbols, ("id", "kind", "file", "line"))
    class_names = {symbol["name"] for symbol in symbols if symbol.get("kind") == "class"}
    for field in fields:
        field_type = str(normalize_type(str(field.get("type") or "")) or "").split(".")[-1]
        if field_type in class_names and field.get("owner") in class_names:
            relations.append({"kind": "has_member", "source": field["owner"], "target": field_type, "instance": field.get("instance"), "file": field.get("file"), "line": field.get("line")})
    relations = _dedupe(relations, ("kind", "source", "target", "instance", "file", "line"))

    fingerprint = hashlib.sha256()
    for file in sorted(files_meta, key=lambda item: item["path"]):
        fingerprint.update(file["path"].encode())
        fingerprint.update(file["sha256"].encode())

    role_counts = Counter(symbol.get("role", symbol.get("kind", "unknown")) for symbol in symbols)
    relation_counts = Counter(relation.get("kind", "unknown") for relation in relations)
    hierarchies = build_hierarchies(symbols, relations)
    tlm = build_tlm(symbols, relations)
    architecture = build_uvm_architecture(symbols, relations)
    snippets = build_snippets(source_root, symbols + relations, source_context)
    fallback_files = sum(1 for item in files_meta if parser_effective == "pyslang" and item.get("parser") != "pyslang")
    return {
        "schema_version": SCHEMA_VERSION,
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_root": str(source_root),
            "source_fingerprint": fingerprint.hexdigest(),
            "parser_requested": parser_requested,
            "parser_effective": parser_effective,
            "parser_strategy": "per_file_syntax",
            "parser_fallback_files": fallback_files,
            "input": input_metadata or {"mode": "directory"},
            "cache": {"reused_files": reused, "reparsed_files": reparsed, "cache_path": str(cache_path)},
        },
        "stats": {
            "files": len(files_meta),
            "symbols": len(symbols),
            "classes": sum(1 for item in symbols if item.get("kind") == "class"),
            "relations": len(relations),
            "ports": len(tlm["ports"]),
            "connections": len(tlm["connections"]),
            "components": len(architecture["components"]),
            "unresolved_components": len(architecture["unresolved_components"]),
            "architecture_roots": len(architecture["roots"]),
            "roles": dict(role_counts),
            "relation_kinds": dict(relation_counts),
        },
        "files": files_meta,
        "symbols": symbols,
        "relations": relations,
        "hierarchies": hierarchies,
        "uvm_architecture": architecture,
        "tlm": tlm,
        "snippets": snippets,
        "role_colors": ROLE_COLORS,
    }
