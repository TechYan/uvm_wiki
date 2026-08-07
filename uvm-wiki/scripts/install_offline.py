#!/usr/bin/env python3
"""Install the bundled Linux CPython 3.11 pyslang wheel into a user venv."""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import subprocess
import sys
import venv
from pathlib import Path


PYSLANG_VERSION = "11.0.0"
EXPECTED_PYTHON = (3, 11)
EXPECTED_MACHINE = {"x86_64", "amd64"}
MIN_GLIBC = (2, 27)


def version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for item in value.split("."):
        try:
            parts.append(int(item))
        except ValueError:
            break
    return tuple(parts)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_platform() -> None:
    if sys.platform != "linux":
        raise SystemExit(f"this offline bundle targets Linux, current platform is {sys.platform}")
    if sys.version_info[:2] != EXPECTED_PYTHON:
        raise SystemExit(f"this offline bundle requires CPython 3.11, current version is {sys.version.split()[0]}")
    machine = platform.machine().lower()
    if machine not in EXPECTED_MACHINE:
        raise SystemExit(f"this offline bundle targets x86_64, current machine is {machine}")
    libc_name, libc_version = platform.libc_ver()
    if libc_name == "glibc" and version_tuple(libc_version) < MIN_GLIBC:
        raise SystemExit(f"pyslang wheel requires glibc >= 2.27, current glibc is {libc_version}")


def verify_wheelhouse(directory: Path) -> None:
    sums_path = directory / "SHA256SUMS"
    if not sums_path.is_file():
        raise SystemExit(f"missing checksum file: {sums_path}")
    for line in sums_path.read_text(encoding="ascii").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        expected, filename = line.split(None, 1)
        wheel = directory / filename.strip()
        if not wheel.is_file():
            raise SystemExit(f"missing wheel: {wheel}")
        actual = sha256(wheel)
        if actual.lower() != expected.lower():
            raise SystemExit(f"checksum mismatch for {wheel.name}: expected {expected}, got {actual}")


def venv_python(directory: Path) -> Path:
    return directory / "bin" / "python"


def main() -> int:
    default_venv = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "uvm-wiki" / "venv"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venv", default=str(default_venv), help="target venv; default: ~/.local/share/uvm-wiki/venv")
    parser.add_argument("--recreate", action="store_true", help="clear and recreate an existing venv")
    args = parser.parse_args()

    validate_platform()
    script_dir = Path(__file__).resolve().parent
    skill_root = script_dir.parent
    wheelhouse = skill_root / "assets" / "wheelhouse" / "linux-x86_64-cp311"
    requirements = skill_root / "assets" / "requirements-pyslang.txt"
    verify_wheelhouse(wheelhouse)
    if not requirements.is_file():
        raise SystemExit(f"missing requirements file: {requirements}")

    target = Path(args.venv).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if args.recreate or not venv_python(target).is_file():
        print(f"Creating venv: {target}")
        venv.EnvBuilder(with_pip=True, clear=args.recreate).create(target)

    python = venv_python(target)
    command = [
        str(python),
        "-m",
        "pip",
        "install",
        "--no-index",
        "--find-links",
        str(wheelhouse),
        "-r",
        str(requirements),
    ]
    print("Installing bundled dependencies without network access")
    subprocess.run(command, check=True)
    subprocess.run([str(python), "-c", f"import pyslang; print('pyslang {PYSLANG_VERSION} import OK')"], check=True)
    print(f"Installed UVM Wiki parser environment: {target}")
    print(f"Use: {python} {skill_root / 'scripts' / 'uvm_wiki.py'} doctor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
