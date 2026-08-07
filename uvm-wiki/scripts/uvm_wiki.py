#!/usr/bin/env python3
"""Build or serve an offline UVM code wiki."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from uvm_wiki_core import build_index, resolve_parser
from uvm_wiki_web import serve_html, write_html


def output_directory(source: Path, value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    return (Path.cwd() / "uvm_wiki_output" / source.name).resolve()


def add_build_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--src", required=True, help="SystemVerilog/UVM source directory")
    parser.add_argument("--out", help="output directory; defaults to ./uvm_wiki_output/<source-name>")
    parser.add_argument("--parser", choices=("auto", "pyslang", "light"), default="auto", help="parser mode; default: auto")
    parser.add_argument("--source-context", type=int, default=15, help="embedded source lines before and after indexed locations")
    parser.add_argument("--no-source", action="store_true", help="do not embed source snippets in the standalone HTML")
    parser.add_argument("--rebuild", action="store_true", help="ignore incremental parse cache")


def build_project(args: argparse.Namespace) -> tuple[dict, Path, Path]:
    source = Path(args.src).expanduser().resolve()
    if not source.is_dir():
        raise SystemExit(f"source directory does not exist: {source}")
    output = output_directory(source, args.out)
    output.mkdir(parents=True, exist_ok=True)
    cache_path = output / ".cache" / "parse_cache.json"
    data = build_index(
        source_root=source,
        parser_requested=args.parser,
        cache_path=cache_path,
        source_context=0 if args.no_source else max(0, args.source_context),
        rebuild=args.rebuild,
        progress=lambda done, total, path: print(f"Indexing {done}/{total}: {path}", flush=True),
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
    return data, source, html_path


def command_build(args: argparse.Namespace) -> int:
    build_project(args)
    return 0


def command_serve(args: argparse.Namespace) -> int:
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("serve mode only permits loopback hosts: 127.0.0.1, localhost, or ::1")
    data, source, _ = build_project(args)
    serve_html(data, source, args.host, args.port)
    return 0


def command_doctor(_: argparse.Namespace) -> int:
    print(f"Python: {sys.version.split()[0]}")
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
