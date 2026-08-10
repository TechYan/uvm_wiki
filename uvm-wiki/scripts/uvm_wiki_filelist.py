#!/usr/bin/env python3
"""Resolve simulator-style source filelists for UVM Wiki indexing."""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path


SOURCE_EXTS = {".sv", ".svh", ".svp", ".v", ".vh", ".inc", ".svi", ".pkg"}
EXTERNAL_INCLUDE_NAMES = {"uvm_macros.svh"}
INCLUDE_RE = re.compile(r"^[ \t]*`include[ \t]+([^\r\n]+)", re.MULTILINE)
DEFINE_RE = re.compile(
    r"^[ \t]*`define[ \t]+([A-Za-z_]\w*)(?:\(([^)\r\n]*)\))?[ \t]*(.*)$",
    re.MULTILINE,
)
IDENTIFIER_RE = re.compile(r"[A-Za-z_]\w*")
OPTIONS_WITH_VALUE = {
    "-L",
    "-P",
    "-l",
    "-o",
    "-top",
    "--top",
    "-timescale",
    "-work",
    "-y",
}


class FilelistError(RuntimeError):
    """Raised when a filelist cannot be resolved deterministically."""


@dataclass
class FilelistSpec:
    sources: list[Path] = field(default_factory=list)
    include_dirs: list[Path] = field(default_factory=list)
    defines: list[str] = field(default_factory=list)
    filelists: list[Path] = field(default_factory=list)
    include_sources: list[Path] = field(default_factory=list)
    ignored_options: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    include_directives: int = 0
    macro_include_directives: int = 0
    unresolved_includes: list[str] = field(default_factory=list)
    outside_root_includes: list[str] = field(default_factory=list)

    def metadata(self, source_root: Path) -> dict[str, object]:
        def display(path: Path) -> str:
            try:
                return path.relative_to(source_root).as_posix()
            except ValueError:
                return str(path)

        return {
            "mode": "filelist",
            "filelists": [display(path) for path in self.filelists],
            "listed_files": len(self.sources) - len(self.include_sources),
            "included_files": len(self.include_sources),
            "include_directives": self.include_directives,
            "macro_include_directives": self.macro_include_directives,
            "unresolved_includes": list(self.unresolved_includes),
            "outside_root_includes": list(self.outside_root_includes),
            "include_dirs": [display(path) for path in self.include_dirs],
            "defines": list(self.defines),
            "ignored_options": list(self.ignored_options),
            "warnings": list(self.warnings),
        }


def _expanded_path(value: str, base: Path) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(value.strip().strip('"').strip("'")))
    path = Path(expanded)
    return (path if path.is_absolute() else base / path).resolve()


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="ignore")


def _logical_lines(text: str) -> list[str]:
    output: list[str] = []
    pending = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.endswith("\\"):
            pending += line[:-1] + " "
            continue
        output.append(pending + line)
        pending = ""
    if pending.strip():
        output.append(pending.strip())
    return output


def _tokens(text: str, path: Path) -> list[str]:
    output: list[str] = []
    for line_number, line in enumerate(_logical_lines(text), 1):
        line = re.sub(r"(^|\s)//.*$", r"\1", line).strip()
        if not line:
            continue
        lexer = shlex.shlex(line, posix=True)
        lexer.whitespace_split = True
        lexer.commenters = "#"
        try:
            output.extend(list(lexer))
        except ValueError as exc:
            raise FilelistError(f"{path}:{line_number}: {exc}") from exc
    return output


def parse_filelists(paths: list[Path]) -> FilelistSpec:
    """Parse one or more filelists and preserve first-seen source order."""

    spec = FilelistSpec()
    source_seen: set[Path] = set()
    include_seen: set[Path] = set()
    define_seen: set[str] = set()
    filelist_seen: set[Path] = set()

    def add_source(value: str, base: Path, origin: Path) -> None:
        source = _expanded_path(value, base)
        if source.suffix.lower() not in SOURCE_EXTS:
            spec.warnings.append(f"ignored non-HDL path from {origin}: {value}")
            return
        if not source.is_file():
            raise FilelistError(f"source file does not exist ({origin}): {source}")
        if source not in source_seen:
            source_seen.add(source)
            spec.sources.append(source)

    def add_include_dir(value: str, base: Path, origin: Path) -> None:
        directory = _expanded_path(value, base)
        if directory not in include_seen:
            include_seen.add(directory)
            spec.include_dirs.append(directory)
        if not directory.is_dir():
            spec.warnings.append(f"include directory does not exist ({origin}): {directory}")

    def add_define(value: str) -> None:
        item = value.strip()
        if item and item not in define_seen:
            define_seen.add(item)
            spec.defines.append(item)

    def parse_one(path: Path, stack: tuple[Path, ...] = ()) -> None:
        resolved = path.expanduser().resolve()
        if resolved in stack:
            chain = " -> ".join(str(item) for item in (*stack, resolved))
            raise FilelistError(f"cyclic nested filelist: {chain}")
        if resolved in filelist_seen:
            return
        if not resolved.is_file():
            raise FilelistError(f"filelist does not exist: {resolved}")
        filelist_seen.add(resolved)
        spec.filelists.append(resolved)
        tokens = _tokens(_read_text(resolved), resolved)
        index = 0
        while index < len(tokens):
            token = tokens[index]
            next_value = tokens[index + 1] if index + 1 < len(tokens) else None
            if token in {"-f", "-F"}:
                if next_value is None:
                    raise FilelistError(f"missing path after {token} in {resolved}")
                parse_one(_expanded_path(next_value, resolved.parent), (*stack, resolved))
                index += 2
                continue
            if token.startswith(("-f=", "-F=")):
                parse_one(_expanded_path(token.split("=", 1)[1], resolved.parent), (*stack, resolved))
                index += 1
                continue
            if token.startswith("+incdir+"):
                for value in token[len("+incdir+") :].split("+"):
                    if value:
                        add_include_dir(value, resolved.parent, resolved)
                index += 1
                continue
            if token == "-I":
                if next_value is None:
                    raise FilelistError(f"missing path after -I in {resolved}")
                add_include_dir(next_value, resolved.parent, resolved)
                index += 2
                continue
            if token.startswith("-I") and len(token) > 2:
                add_include_dir(token[2:].lstrip("="), resolved.parent, resolved)
                index += 1
                continue
            if token.startswith("+define+"):
                for value in token[len("+define+") :].split("+"):
                    add_define(value)
                index += 1
                continue
            if token == "-D":
                if next_value is None:
                    raise FilelistError(f"missing value after -D in {resolved}")
                add_define(next_value)
                index += 2
                continue
            if token.startswith("-D") and len(token) > 2:
                add_define(token[2:].lstrip("="))
                index += 1
                continue
            if token == "-v":
                if next_value is None:
                    raise FilelistError(f"missing source after -v in {resolved}")
                add_source(next_value, resolved.parent, resolved)
                index += 2
                continue
            if token.startswith("-v="):
                add_source(token.split("=", 1)[1], resolved.parent, resolved)
                index += 1
                continue
            if Path(token).suffix.lower() in SOURCE_EXTS:
                add_source(token, resolved.parent, resolved)
                index += 1
                continue
            if token in OPTIONS_WITH_VALUE:
                value = f"{token} {next_value}" if next_value is not None else token
                spec.ignored_options.append(value)
                index += 2 if next_value is not None else 1
                continue
            if token.startswith(("-", "+")):
                spec.ignored_options.append(token)
            elif token:
                spec.warnings.append(f"ignored token from {resolved}: {token}")
            index += 1

    for path in paths:
        parse_one(path)
    if not spec.sources:
        raise FilelistError("filelist did not resolve any SystemVerilog or Verilog source files")
    return spec


def derive_source_root(spec: FilelistSpec, requested_filelists: list[Path]) -> Path:
    """Choose a browsing boundary when --src is omitted."""

    candidates = [str(path) for path in spec.sources]
    candidates.extend(str(path.expanduser().resolve().parent) for path in requested_filelists)
    try:
        return Path(os.path.commonpath(candidates)).resolve()
    except ValueError as exc:
        raise FilelistError("filelist sources span unrelated roots; provide --src explicitly") from exc


def require_sources_within_root(spec: FilelistSpec, source_root: Path) -> None:
    for path in spec.sources:
        try:
            path.relative_to(source_root)
        except ValueError as exc:
            raise FilelistError(f"filelist source is outside --src boundary: {path}") from exc


@dataclass(frozen=True)
class _Macro:
    params: tuple[str, ...] | None
    body: str


def _strip_directive_comment(value: str) -> str:
    return re.sub(r"\s+//.*$", "", value).strip()


def _macro_definitions(text: str) -> dict[str, _Macro]:
    text = re.sub(r"/\*.*?\*/", lambda match: "\n" * match.group(0).count("\n"), text, flags=re.DOTALL)
    text = re.sub(r"\\\r?\n", " ", text)
    output: dict[str, _Macro] = {}
    for match in DEFINE_RE.finditer(text):
        params = match.group(2)
        parameter_names = None if params is None else tuple(
            item.strip() for item in params.split(",") if item.strip()
        )
        output[match.group(1)] = _Macro(parameter_names, _strip_directive_comment(match.group(3)) or "1")
    return output


def _filelist_macros(defines: list[str]) -> dict[str, _Macro]:
    output: dict[str, _Macro] = {}
    for define in defines:
        name, separator, value = define.partition("=")
        name = name.strip()
        if IDENTIFIER_RE.fullmatch(name):
            output[name] = _Macro(None, value.strip() if separator and value.strip() else "1")
    return output


def _macro_arguments(text: str, opening: int) -> tuple[list[str], int] | None:
    depth = 0
    start = opening + 1
    parts: list[str] = []
    string = False
    escaped = False
    for index in range(opening, len(text)):
        char = text[index]
        if string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                string = False
            continue
        if char == '"':
            string = True
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                parts.append(text[start:index].strip())
                return parts, index + 1
        elif char == "," and depth == 1:
            parts.append(text[start:index].strip())
            start = index + 1
    return None


def _expand_macros(
    text: str,
    macros: dict[str, _Macro],
    stack: tuple[str, ...] = (),
    depth: int = 0,
) -> str:
    if depth > 32:
        return text
    output: list[str] = []
    index = 0
    while index < len(text):
        if text[index] != "`":
            output.append(text[index])
            index += 1
            continue
        match = IDENTIFIER_RE.match(text, index + 1)
        if not match:
            output.append(text[index])
            index += 1
            continue
        name = match.group(0)
        macro = macros.get(name)
        if macro is None or name in stack:
            output.append(text[index : match.end()])
            index = match.end()
            continue
        end = match.end()
        replacement = macro.body
        if macro.params is not None:
            opening = end
            while opening < len(text) and text[opening].isspace():
                opening += 1
            if opening >= len(text) or text[opening] != "(":
                output.append(text[index:end])
                index = end
                continue
            parsed = _macro_arguments(text, opening)
            if parsed is None:
                output.append(text[index:end])
                index = end
                continue
            arguments, end = parsed
            if len(arguments) != len(macro.params):
                output.append(text[index:end])
                index = end
                continue
            for parameter, argument in zip(macro.params, arguments):
                expanded_argument = _expand_macros(argument, macros, stack, depth + 1)
                replacement = re.sub(
                    rf"(?<![A-Za-z0-9_]){re.escape(parameter)}(?![A-Za-z0-9_])",
                    lambda _match, value=expanded_argument: value,
                    replacement,
                )
        replacement = replacement.replace("``", "")
        output.append(_expand_macros(replacement, macros, (*stack, name), depth + 1))
        index = end
    return "".join(output)


def _include_target(expression: str, macros: dict[str, _Macro]) -> str | None:
    expanded = _expand_macros(_strip_directive_comment(expression), macros).replace('`"', '"').strip()
    expanded = os.path.expandvars(os.path.expanduser(expanded))
    quoted = re.fullmatch(r'"(.*)"', expanded)
    if quoted:
        value = quoted.group(1).strip().strip('"')
        return value or None
    if "`" in expanded or not expanded or any(char.isspace() for char in expanded):
        return None
    return expanded.strip('"\'') or None


def _include_directives(text: str) -> list[tuple[int, str]]:
    text = re.sub(r"/\*.*?\*/", lambda match: "\n" * match.group(0).count("\n"), text, flags=re.DOTALL)
    return [
        (text.count("\n", 0, match.start()) + 1, _strip_directive_comment(match.group(1)))
        for match in INCLUDE_RE.finditer(text)
    ]


def expand_project_includes(spec: FilelistSpec, source_root: Path) -> None:
    """Add the project-local, macro-expanded `include closure to the index."""

    source_root = source_root.resolve()
    listed_sources = list(spec.sources)
    queue = list(spec.sources)
    seen = set(queue)
    include_sources: list[Path] = []
    filelist_dirs = list(dict.fromkeys(path.parent for path in spec.filelists))
    macros = _filelist_macros(spec.defines)
    directives: dict[tuple[Path, int, str], None] = {}
    unresolved: dict[tuple[Path, int, str], str] = {}
    outside: dict[tuple[Path, int, str], str] = {}
    macro_version = 0

    def display(path: Path) -> str:
        try:
            return path.relative_to(source_root).as_posix()
        except ValueError:
            return str(path)

    def resolve_directive(key: tuple[Path, int, str]) -> None:
        source, line, expression = key
        unresolved.pop(key, None)
        outside.pop(key, None)
        target = _include_target(expression, macros)
        if not target:
            unresolved[key] = f"{display(source)}:{line}: {expression}"
            return
        target_path = Path(target)
        if target_path.is_absolute():
            candidates = [target_path]
        else:
            search_roots = [source.parent, *spec.include_dirs, *filelist_dirs, source_root]
            search_roots = list(dict.fromkeys(path.resolve() for path in search_roots))
            candidates = [root / target_path for root in search_roots]
        include = next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)
        if include is None:
            if Path(target).name not in EXTERNAL_INCLUDE_NAMES:
                unresolved[key] = f"{display(source)}:{line}: {expression} -> {target}"
            return
        try:
            include.relative_to(source_root)
        except ValueError:
            outside[key] = f"{display(source)}:{line}: {expression} -> {include}"
            return
        if include.suffix.lower() not in SOURCE_EXTS:
            unresolved[key] = (
                f"{display(source)}:{line}: {expression} -> {display(include)} "
                f"(unsupported extension {include.suffix or '<none>'})"
            )
            return
        if include not in seen:
            seen.add(include)
            queue.append(include)
            include_sources.append(include)

    cursor = 0
    retried_version = -1
    while True:
        while cursor < len(queue):
            source = queue[cursor]
            cursor += 1
            text = _read_text(source)
            for name, macro in _macro_definitions(text).items():
                if macros.get(name) != macro:
                    macros[name] = macro
                    macro_version += 1
            for line, expression in _include_directives(text):
                key = (source, line, expression)
                directives[key] = None
                resolve_directive(key)
        if macro_version == retried_version:
            break
        retried_version = macro_version
        for key in list(unresolved):
            resolve_directive(key)

    spec.sources = [*listed_sources, *include_sources]
    spec.include_sources = include_sources
    spec.include_directives = len(directives)
    spec.macro_include_directives = sum(
        1 for _source, _line, expression in directives if not expression.lstrip().startswith('"')
    )
    spec.unresolved_includes = sorted(unresolved.values())
    spec.outside_root_includes = sorted(outside.values())
    for item in spec.unresolved_includes:
        warning = f"unresolved include: {item}"
        if warning not in spec.warnings:
            spec.warnings.append(warning)
    for item in spec.outside_root_includes:
        warning = f"include outside --src boundary: {item}; widen --src to index it"
        if warning not in spec.warnings:
            spec.warnings.append(warning)
