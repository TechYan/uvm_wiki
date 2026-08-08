#!/usr/bin/env python3
"""Resolve simulator-style source filelists for UVM Wiki indexing."""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path


SOURCE_EXTS = {".sv", ".svh", ".v", ".vh"}
EXTERNAL_INCLUDE_NAMES = {"uvm_macros.svh"}
INCLUDE_RE = re.compile(r'^\s*`include\s+"([^"]+)"', re.MULTILINE)
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


def expand_project_includes(spec: FilelistSpec, source_root: Path) -> None:
    """Add project-local `include files so class headers remain indexable."""

    seen = set(spec.sources)
    queue = list(spec.sources)
    include_sources: list[Path] = []
    while queue:
        source = queue.pop(0)
        text = _read_text(source)
        for value in INCLUDE_RE.findall(text):
            expanded = os.path.expandvars(os.path.expanduser(value))
            candidates = [source.parent / expanded]
            candidates.extend(directory / expanded for directory in spec.include_dirs)
            include = next((item.resolve() for item in candidates if item.is_file()), None)
            if include is None:
                if Path(value).name in EXTERNAL_INCLUDE_NAMES:
                    continue
                warning = f"unresolved include from {source}: {value}"
                if warning not in spec.warnings:
                    spec.warnings.append(warning)
                continue
            try:
                include.relative_to(source_root)
            except ValueError:
                continue
            if include.suffix.lower() not in SOURCE_EXTS or include in seen:
                continue
            seen.add(include)
            spec.sources.append(include)
            include_sources.append(include)
            queue.append(include)
    spec.include_sources = include_sources
