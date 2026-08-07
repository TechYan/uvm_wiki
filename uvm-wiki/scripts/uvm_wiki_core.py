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
CACHE_VERSION = 3
PYSLANG_AST_MAX_BYTES = 512 * 1024
SOURCE_EXTS = {".sv", ".svh", ".v", ".vh"}
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
    r"(?:(?:[A-Za-z_][\w:<>#\[\]\s]*)\s+)?(?:(?P<class>[A-Za-z_]\w*)::)?(?P<name>[A-Za-z_]\w*)\s*\("
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
        ("test", ("uvm_test", "_test")),
        ("env", ("uvm_env", "_env", "_uvc")),
        ("agent", ("uvm_agent", "_agent")),
        ("driver", ("uvm_driver", "_driver", "_drv")),
        ("monitor", ("uvm_monitor", "_monitor", "_mon")),
        ("sequencer", ("uvm_sequencer", "_sequencer", "_seqr")),
        ("scoreboard", ("uvm_scoreboard", "_scoreboard", "_scbd", "_sbd")),
        ("sequence_item", ("uvm_sequence_item", "_transaction", "_item", "_packet", "_pkt", "_tlp")),
        ("sequence", ("uvm_sequence", "_sequence", "_seq")),
        ("config", ("_config", "_cfg", "cfg_info")),
        ("coverage", ("coverage", "_cov")),
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
                relations.append({"kind": "creates", "source": statement_owner(match.start()), "target": normalize_type(match.group(1)), "instance": argument(args or "", 0), "file": relative, "line": match_line})
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
                    relations.append({"kind": f"config_db_{match.group(2)}", "source": statement_owner(match.start()), "target": argument(args, 2), "config_type": " ".join(match.group(1).split()), "file": relative, "line": match_line})

        field = FIELD_RE.match(clean) if len(clean) < 16384 else None
        if field:
            for variable in field.group("vars").split(","):
                fields.append({"owner": statement_owner(field.start()), "type": field.group("type"), "instance": variable.strip().split("[", 1)[0].strip(), "file": relative, "line": location(field.start())})

    return {"symbols": symbols, "relations": relations, "fields": fields, "parser": "light", "diagnostics": 0}


def _syntax_name(node: dict[str, Any]) -> str | None:
    value = node.get("name")
    if isinstance(value, dict):
        text = value.get("text")
        return text if isinstance(text, str) else None
    return value if isinstance(value, str) else None


def _walk_syntax(value: Any, output: list[tuple[str, str]]) -> None:
    if isinstance(value, dict):
        kind = value.get("kind")
        name = _syntax_name(value)
        mapping = {
            "ClassDeclaration": "class",
            "ModuleDeclaration": "module",
            "InterfaceDeclaration": "interface",
            "ProgramDeclaration": "program",
            "PackageDeclaration": "package",
            "FunctionDeclaration": "function",
            "TaskDeclaration": "task",
        }
        if isinstance(kind, str) and kind in mapping and name:
            output.append((mapping[kind], name))
        for child in value.values():
            _walk_syntax(child, output)
    elif isinstance(value, list):
        for child in value:
            _walk_syntax(child, output)


def parse_with_pyslang(path: Path, root: Path, syntax: Any) -> dict[str, Any]:
    result = parse_light(path, root)
    tree = syntax.SyntaxTree.fromFile(str(path))
    declarations: list[tuple[str, str]] = []
    _walk_syntax(json.loads(tree.to_json()), declarations)
    existing = {(item["kind"], item["name"]) for item in result["symbols"]}
    relative = path.relative_to(root).as_posix()
    for kind, name in declarations:
        if (kind, name) not in existing:
            result["symbols"].append({"id": name, "kind": kind, "name": name, "role": classify_role(name) if kind == "class" else kind, "file": relative, "line": 1, "pyslang_only": True})
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


def save_cache(path: Path, parser: str, entries: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"cache_version": CACHE_VERSION, "parser": parser, "entries": entries}
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
            target = str(relation.get("target", ""))
            parent, child = (target, source) if reverse else (source, target)
            if not parent or not child or parent == child:
                continue
            if not reverse and (parent not in classes or child not in classes):
                continue
            item = {"id": child, "instance": relation.get("instance"), "kind": relation.get("kind"), "file": relation.get("file"), "line": relation.get("line")}
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
) -> dict[str, Any]:
    source_root = source_root.resolve()
    parser_effective, syntax = resolve_parser(parser_requested)
    previous = {} if rebuild else load_cache(cache_path)
    previous_entries = previous.get("entries", {}) if previous.get("parser") == parser_effective else {}
    entries: dict[str, Any] = {}
    files_meta: list[dict[str, Any]] = []
    reparsed = 0
    reused = 0

    source_paths = list(iter_sources(source_root))
    total_files = len(source_paths)
    for file_number, path in enumerate(source_paths, 1):
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
                    parsed = parse_with_pyslang(path, source_root, syntax) if parser_effective == "pyslang" else parse_light(path, source_root)
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
            save_cache(cache_path, parser_effective, entries)

    save_cache(cache_path, parser_effective, entries)
    symbols = [symbol for entry in entries.values() for symbol in entry["parsed"].get("symbols", [])]
    relations = [relation for entry in entries.values() for relation in entry["parsed"].get("relations", [])]
    fields = [field for entry in entries.values() for field in entry["parsed"].get("fields", [])]
    symbols = _dedupe(symbols, ("id", "kind", "file", "line"))
    class_names = {symbol["name"] for symbol in symbols if symbol.get("kind") == "class"}
    for field in fields:
        if field.get("type") in class_names and field.get("owner") in class_names:
            relations.append({"kind": "has_member", "source": field["owner"], "target": field["type"], "instance": field.get("instance"), "file": field.get("file"), "line": field.get("line")})
    relations = _dedupe(relations, ("kind", "source", "target", "instance", "file", "line"))

    fingerprint = hashlib.sha256()
    for file in sorted(files_meta, key=lambda item: item["path"]):
        fingerprint.update(file["path"].encode())
        fingerprint.update(file["sha256"].encode())

    role_counts = Counter(symbol.get("role", symbol.get("kind", "unknown")) for symbol in symbols)
    relation_counts = Counter(relation.get("kind", "unknown") for relation in relations)
    hierarchies = build_hierarchies(symbols, relations)
    tlm = build_tlm(symbols, relations)
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
            "parser_fallback_files": fallback_files,
            "cache": {"reused_files": reused, "reparsed_files": reparsed, "cache_path": str(cache_path)},
        },
        "stats": {
            "files": len(files_meta),
            "symbols": len(symbols),
            "classes": sum(1 for item in symbols if item.get("kind") == "class"),
            "relations": len(relations),
            "ports": len(tlm["ports"]),
            "connections": len(tlm["connections"]),
            "roles": dict(role_counts),
            "relation_kinds": dict(relation_counts),
        },
        "files": files_meta,
        "symbols": symbols,
        "relations": relations,
        "hierarchies": hierarchies,
        "tlm": tlm,
        "snippets": snippets,
        "role_colors": ROLE_COLORS,
    }
