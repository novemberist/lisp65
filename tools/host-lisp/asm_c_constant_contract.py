#!/usr/bin/env python3
"""Generate and audit every intentional C/assembler constant mirror."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config" / "asm-c-constant-contract.json"
FORMAT = "lisp65-asm-c-constant-contract-v1"
INCLUDE_TOKEN = '.include\t"build/generated/asm-c-contract.inc"'
EQU = re.compile(r"^\.equ\s+([A-Z0-9_]+),\s*([0-9]+)\s*$", re.MULTILINE)
NUMERIC_IMMEDIATE = re.compile(r"^\s*([a-z][a-z0-9]*)\s+(#(?:\$[0-9a-f]+|[0-9]+))(?:\s*;.*)?$", re.I)
NUMERIC_JUMP = re.compile(r"^\s*(?:jmp|jsr)\s+(?:\$[0-9a-f]+|[0-9]+)(?:\s*;.*)?$", re.I)


class ContractError(RuntimeError):
    pass


def load_contract(path: Path = CONTRACT) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read contract: {exc}") from exc
    if not isinstance(value, dict) or value.get("format") != FORMAT:
        raise ContractError("asm/C constant contract format drift")
    return value


def discovered_sources(value: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for raw_root in value.get("scan_roots", []):
        root = ROOT / raw_root
        if not root.is_dir():
            raise ContractError(f"missing assembler scan root: {raw_root}")
        for pattern in ("*.s", "*.S"):
            found.update(path.relative_to(ROOT).as_posix() for path in root.rglob(pattern))
    return found


def validate_inventory(value: dict[str, Any]) -> list[dict[str, Any]]:
    rows = value.get("assembler_sources")
    if not isinstance(rows, list) or not rows:
        raise ContractError("assembler source inventory must be a non-empty list")
    paths = [row.get("path") for row in rows if isinstance(row, dict)]
    if len(paths) != len(rows) or len(set(paths)) != len(paths):
        raise ContractError("assembler source inventory contains invalid/duplicate paths")
    found = discovered_sources(value)
    if set(paths) != found:
        raise ContractError(
            "assembler source inventory drift: "
            f"missing={sorted(found - set(paths))} stale={sorted(set(paths) - found)}"
        )
    for row in rows:
        path = ROOT / row["path"]
        authority = ROOT / str(row.get("authority", ""))
        if not path.is_file() or not authority.is_file():
            raise ContractError(f"missing assembler source/authority: {row['path']}")
        kind = row.get("kind")
        if kind == "hardware-algorithm-contract":
            if row.get("gate") != "mega65-math-override-check":
                raise ContractError("mega65 math source lost its dedicated gate")
        elif kind == "f011-transaction-context-contract":
            if row.get("gate") != "f011-transaction-context-check":
                raise ContractError("F011 guard source lost its dedicated gate")
        elif kind != "generated-c-contract":
            raise ContractError(f"unknown assembler contract kind: {kind}")
    return rows


def compile_output(value: dict[str, Any], cc: str) -> bytes:
    generator = ROOT / str(value.get("generator", ""))
    if not generator.is_file():
        raise ContractError("missing C contract generator")
    with tempfile.TemporaryDirectory(prefix="lisp65-asm-contract-") as raw:
        binary = Path(raw) / "emit"
        built = subprocess.run(
            [cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-Isrc", "-Iscripts",
             str(generator), "-o", str(binary)],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        if built.returncode:
            raise ContractError(f"C contract generator compile failed:\n{built.stdout}")
        emitted = subprocess.run(
            [str(binary)], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if emitted.returncode:
            raise ContractError(
                "C contract generator execution failed: "
                + emitted.stderr.decode("utf-8", errors="replace")
            )
        return emitted.stdout


def parse_equ(data: bytes) -> dict[str, int]:
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ContractError("generated assembler contract is not ASCII") from exc
    pairs: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line or line.startswith(";"):
            continue
        match = EQU.fullmatch(line)
        if not match:
            raise ContractError(f"invalid generated assembler contract line: {line!r}")
        pairs.append((match.group(1), match.group(2)))
    if len(pairs) != len(set(name for name, _ in pairs)):
        raise ContractError("generated assembler contract has duplicate symbols")
    return {name: int(raw) for name, raw in pairs}


def validate_sources(rows: list[dict[str, Any]], symbols: dict[str, int]) -> None:
    expected: set[str] = set()
    for row in rows:
        if row["kind"] != "generated-c-contract":
            continue
        text = (ROOT / row["path"]).read_text(encoding="utf-8")
        if INCLUDE_TOKEN not in text:
            raise ContractError(f"generated include missing from {row['path']}")
        required = row.get("generated_symbols")
        if not isinstance(required, list) or not required:
            raise ContractError(f"empty generated symbol list: {row['path']}")
        for name in required:
            if not isinstance(name, str) or text.count(name) != 1:
                raise ContractError(f"assembler symbol use must be unique: {row['path']}:{name}")
            expected.add(name)
        permitted = set(row.get("permitted_numeric_immediates", []))
        observed: list[str] = []
        for line in text.splitlines():
            match = NUMERIC_IMMEDIATE.fullmatch(line)
            if match:
                observed.append(f"{match.group(1).lower()}\t{match.group(2).lower()}")
            if NUMERIC_JUMP.fullmatch(line):
                raise ContractError(f"raw numeric jump survived in {row['path']}: {line.strip()}")
        if set(observed) != permitted or len(observed) != len(permitted):
            raise ContractError(
                f"numeric immediate inventory drift in {row['path']}: "
                f"expected={sorted(permitted)} observed={observed}"
            )
    if set(symbols) != expected:
        raise ContractError(
            "generated symbol inventory drift: "
            f"missing={sorted(expected - set(symbols))} extra={sorted(set(symbols) - expected)}"
        )


def validate(value: dict[str, Any], data: bytes) -> dict[str, int]:
    rows = validate_inventory(value)
    symbols = parse_equ(data)
    validate_sources(rows, symbols)
    if symbols["ASM_L65M_COMMIT_ABI"] != 4:
        raise ContractError("current Directory-only product must expose commit ABI 4")
    return symbols


def generate(value: dict[str, Any], cc: str, out: Path) -> None:
    data = compile_output(value, cc)
    validate(value, data)
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_suffix(out.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(out)


def check(value: dict[str, Any], cc: str, out: Path) -> dict[str, int]:
    expected = compile_output(value, cc)
    symbols = validate(value, expected)
    if out.is_symlink() or not out.is_file() or out.read_bytes() != expected:
        raise ContractError("generated assembler contract drift; regenerate before linking")
    return symbols


def selftest() -> None:
    good = b".equ\tA, 1\n.equ\tB, 2\n"
    if parse_equ(good) != {"A": 1, "B": 2}:
        raise ContractError("valid generated include was rejected")
    for bad in (b".equ\tA, 1\n.equ\tA, 2\n", b".equ\tA, $01\n"):
        try:
            parse_equ(bad)
        except ContractError:
            pass
        else:
            raise ContractError("mutated generated include survived")
    value = load_contract()
    rows = validate_inventory(value)
    if len(rows) != 4 or discovered_sources(value) != {row["path"] for row in rows}:
        raise ContractError("inventory closure selftest drift")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "check", "selftest", "report"))
    parser.add_argument("--cc", default="cc")
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        value = load_contract(args.contract)
        out = args.out or ROOT / value["generated_include"]
        if args.command == "generate":
            generate(value, args.cc, out)
        elif args.command == "check":
            symbols = check(value, args.cc, out)
            print(f"asm/C constant contract: PASS ({len(symbols)} generated mirrors, {len(value['assembler_sources'])} sources)")
        elif args.command == "selftest":
            selftest()
            print("asm/C constant contract selftest: PASS")
        else:
            data = compile_output(value, args.cc)
            symbols = validate(value, data)
            for name, number in symbols.items():
                print(f"{name}={number}")
    except ContractError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
