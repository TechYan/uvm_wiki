#!/usr/bin/env python3
"""Build or serve an offline UVM code wiki."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from uvm_wiki_core import build_index, resolve_parser
from uvm_wiki_filelist import (
    derive_source_root,
    expand_project_includes,
    parse_filelists,
    require_sources_within_root,
)
from uvm_wiki_web import serve_html, serve_html_text, write_html


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def output_directory(source: Path, value: str | None, default_name: str | None = None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    return (Path.cwd() / "uvm_wiki_output" / (default_name or source.name)).resolve()


def add_build_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--src", help="source root; scans recursively unless --filelist is provided")
    parser.add_argument(
        "--filelist",
        action="append",
        help="simulator-style filelist; repeat for multiple top-level filelists",
    )
    parser.add_argument("--out", help="output directory; defaults to ./uvm_wiki_output/<source-or-filelist-name>")
    parser.add_argument("--parser", choices=("auto", "pyslang", "light"), default="auto", help="parser mode; default: auto")
    parser.add_argument("--source-context", type=int, default=15, help="embedded source lines before and after indexed locations")
    parser.add_argument("--no-source", action="store_true", help="do not embed source snippets in the standalone HTML")
    parser.add_argument("--rebuild", action="store_true", help="ignore incremental parse cache")


def project_input(
    args: argparse.Namespace,
) -> tuple[Path, list[Path] | None, list[Path], list[str], dict, str | None]:
    requested_filelists = [Path(value).expanduser().resolve() for value in (args.filelist or [])]
    if not args.src and not requested_filelists:
        raise SystemExit("provide --src for directory scan mode or --filelist for filelist mode")
    if requested_filelists:
        spec = parse_filelists(requested_filelists)
        source = Path(args.src).expanduser().resolve() if args.src else derive_source_root(spec, requested_filelists)
        if not source.is_dir():
            raise SystemExit(f"source directory does not exist: {source}")
        require_sources_within_root(spec, source)
        expand_project_includes(spec, source)
        return (
            source,
            spec.sources,
            spec.include_dirs,
            spec.defines,
            spec.metadata(source),
            requested_filelists[0].stem,
        )

    source = Path(args.src).expanduser().resolve()
    if not source.is_dir():
        raise SystemExit(f"source directory does not exist: {source}")
    return source, None, [], [], {"mode": "directory"}, None


def build_project(args: argparse.Namespace) -> tuple[dict, Path, Path]:
    source, source_paths, include_dirs, defines, input_metadata, default_name = project_input(args)
    output = output_directory(source, args.out, default_name)
    output.mkdir(parents=True, exist_ok=True)
    cache_path = output / ".cache" / "parse_cache.json"
    data = build_index(
        source_root=source,
        parser_requested=args.parser,
        cache_path=cache_path,
        source_context=0 if args.no_source else max(0, args.source_context),
        rebuild=args.rebuild,
        progress=lambda done, total, path: print(f"Indexing {done}/{total}: {path}", flush=True),
        source_paths=source_paths,
        include_dirs=include_dirs,
        defines=defines,
        input_metadata=input_metadata,
    )
    json_path = output / "uvm_wiki_ai.json"
    html_path = output / "uvm_wiki.html"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    write_html(html_path, data)
    print(f"Wrote {json_path}")
    print(f"Wrote {html_path}")
    stats = data["stats"]
    cache = data["metadata"]["cache"]
    print(
        "Parsed "
        f"files={stats['files']} classes={stats['classes']} relations={stats['relations']} "
        f"parser={data['metadata']['parser_effective']} reused={cache['reused_files']} reparsed={cache['reparsed_files']}"
    )
    input_info = data["metadata"].get("input", {})
    if input_info.get("mode") == "filelist":
        print(
            "Filelist includes "
            f"directives={input_info.get('include_directives', 0)} "
            f"macro={input_info.get('macro_include_directives', 0)} "
            f"indexed={input_info.get('included_files', 0)} "
            f"unresolved={len(input_info.get('unresolved_includes', []))} "
            f"outside_src={len(input_info.get('outside_root_includes', []))}"
        )
        warnings = list(input_info.get("warnings", []))
        for warning in warnings[:10]:
            print(f"Warning: {warning}")
        if len(warnings) > 10:
            print(f"Warning: {len(warnings) - 10} more warning(s) are recorded in uvm_wiki_ai.json")
    return data, source, html_path


def command_build(args: argparse.Namespace) -> int:
    build_project(args)
    return 0


def command_serve(args: argparse.Namespace) -> int:
    if args.host not in LOOPBACK_HOSTS:
        raise SystemExit("serve mode only permits loopback hosts: 127.0.0.1, localhost, or ::1")
    data, source, _ = build_project(args)
    serve_html(data, source, args.host, args.port)
    return 0


def command_serve_existing(args: argparse.Namespace) -> int:
    if args.host not in LOOPBACK_HOSTS:
        raise SystemExit("serve mode only permits loopback hosts: 127.0.0.1, localhost, or ::1")
    source = Path(args.src).expanduser().resolve()
    output = Path(args.out).expanduser().resolve()
    html_path = output / "uvm_wiki.html"
    json_path = output / "uvm_wiki_ai.json"
    if not source.is_dir():
        raise SystemExit(f"source directory does not exist: {source}")
    if not html_path.is_file():
        raise SystemExit(f"generated HTML does not exist: {html_path}")
    if not json_path.is_file():
        raise SystemExit(f"generated JSON does not exist: {json_path}")
    try:
        json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read generated JSON: {json_path}: {exc}") from exc
    print(f"Using existing HTML: {html_path}")
    print(f"Using existing JSON: {json_path}")
    serve_html_text(html_path.read_text(encoding="utf-8"), source, args.host, args.port)
    return 0


def command_doctor(_: argparse.Namespace) -> int:
    print(f"Python: {sys.version.split()[0]}")
    print("Input modes: directory, filelist")
    for requested in ("light", "auto"):
        effective, _syntax = resolve_parser(requested)
        print(f"Parser {requested}: {effective}")
    try:
        effective, _syntax = resolve_parser("pyslang")
        print(f"Parser pyslang: {effective} (available)")
    except RuntimeError as exc:
        print(f"Parser pyslang: unavailable ({exc})")
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an AI-friendly UVM index and a unified interactive HTML wiki.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="generate uvm_wiki.html and uvm_wiki_ai.json")
    add_build_arguments(build)
    build.set_defaults(func=command_build)
    serve = subparsers.add_parser("serve", help="generate outputs and serve full source through a localhost read-only API")
    add_build_arguments(serve)
    serve.add_argument("--host", default="127.0.0.1", help="loopback host; default: 127.0.0.1")
    serve.add_argument("--port", type=int, default=8765, help="HTTP port; default: 8765")
    serve.set_defaults(func=command_serve)
    serve_existing = subparsers.add_parser(
        "serve-existing",
        help="serve existing outputs with full-source lookup, without scanning or parsing",
    )
    serve_existing.add_argument("--src", required=True, help="source root exposed by the read-only source API")
    serve_existing.add_argument("--out", required=True, help="directory containing uvm_wiki.html and uvm_wiki_ai.json")
    serve_existing.add_argument("--host", default="127.0.0.1", help="loopback host; default: 127.0.0.1")
    serve_existing.add_argument("--port", type=int, default=8765, help="HTTP port; default: 8765")
    serve_existing.set_defaults(func=command_serve_existing)
    doctor = subparsers.add_parser("doctor", help="show Python and parser availability")
    doctor.set_defaults(func=command_doctor)
    return parser


def main() -> int:
    parser = make_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except RuntimeError as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
