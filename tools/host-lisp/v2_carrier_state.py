#!/usr/bin/env python3
"""Gate the staged dialect-v2 Treewalk carrier lifecycle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


class CarrierStateError(Exception):
    pass


def _carrier_tokens(eval_source: str, vm_source: str) -> tuple[bool, ...]:
    required_eval = (
        "static obj eval_vm_bridge(",
        "static obj eval_vm_apply(",
        "vm_treewalk_call = eval_vm_bridge;",
        "vm_treewalk_apply = eval_vm_apply;",
    )
    required_vm = (
        "if (vm_treewalk_apply)",
        "if (vm_treewalk_call)",
    )
    return tuple(item in eval_source for item in required_eval) + tuple(
        item in vm_source for item in required_vm
    )


FORBIDDEN_DEFINITIONS = {
    "apply",
    "eval_vm_apply",
    "eval_vm_bridge",
    "vm_treewalk_apply",
    "vm_treewalk_call",
}
REQUIRED_CUT_DEFINITIONS = {"vm_native_apply", "vm_run"}


def _defined_symbols(elf: Path) -> set[str]:
    nm = shutil.which("llvm-nm") or shutil.which("nm")
    if nm is None:
        raise CarrierStateError("neither llvm-nm nor nm is available")
    if not elf.is_file():
        raise CarrierStateError(f"cut ELF does not exist: {elf}")
    result = subprocess.run(
        [nm, "--defined-only", str(elf)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise CarrierStateError(f"nm failed for {elf}: {result.stderr.strip()}")
    symbols: set[str] = set()
    for line in result.stdout.splitlines():
        fields = line.split()
        if fields:
            symbols.add(fields[-1])
    return symbols


def _forbidden_in(symbols: set[str]) -> set[str]:
    found: set[str] = set()
    for symbol in symbols:
        base = re.split(r"[.$]", symbol, maxsplit=1)[0]
        if base in FORBIDDEN_DEFINITIONS:
            found.add(symbol)
    return found


def check(
    expect: str, eval_source: str, vm_source: str, elf: Path | None = None,
) -> dict[str, object] | None:
    tokens = _carrier_tokens(eval_source, vm_source)
    if expect == "active" and not all(tokens):
        raise CarrierStateError("carrier is not completely active")
    if expect == "removed":
        if elf is None:
            raise CarrierStateError("removed state requires --elf with a real cut binary")
        symbols = _defined_symbols(elf)
        missing = REQUIRED_CUT_DEFINITIONS - symbols
        if missing:
            raise CarrierStateError(
                "ELF is not a linked VM carrier cut; missing: " + ", ".join(sorted(missing))
            )
        forbidden = _forbidden_in(symbols)
        if forbidden:
            raise CarrierStateError(
                "cut ELF still defines carrier symbols: " + ", ".join(sorted(forbidden))
            )
        return {
            "format": "lisp65-v2-carrier-cut-verdict-v1",
            "state": "removed",
            "elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
            "required_definitions": sorted(REQUIRED_CUT_DEFINITIONS),
            "forbidden_definitions": [],
            "defined_symbol_count": len(symbols),
        }
    return None


def selftest(eval_source: str, vm_source: str) -> None:
    check("active", eval_source, vm_source)
    for needle in (
        "static obj eval_vm_bridge(",
        "static obj eval_vm_apply(",
        "vm_treewalk_call = eval_vm_bridge;",
        "vm_treewalk_apply = eval_vm_apply;",
    ):
        try:
            check("active", eval_source.replace(needle, "removed", 1), vm_source)
        except CarrierStateError:
            continue
        raise CarrierStateError(f"selftest accepted missing carrier token: {needle}")
    for needle in ("if (vm_treewalk_apply)", "if (vm_treewalk_call)"):
        try:
            check("active", eval_source, vm_source.replace(needle, "removed"))
        except CarrierStateError:
            continue
        raise CarrierStateError(f"selftest accepted missing carrier token: {needle}")
    if _forbidden_in({"vm_native_apply", "vm_treewalk_call", "apply.constprop.0"}) != {
        "vm_treewalk_call", "apply.constprop.0"
    }:
        raise CarrierStateError("selftest symbol classifier drift")
    print("v2-carrier-state: SELFTEST PASS mutations=6 state=active symbol-audit=covered")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect", choices=("active", "removed"), default="active")
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    eval_source = (ROOT / "src/eval.c").read_text(encoding="utf-8")
    vm_source = (ROOT / "src/vm.c").read_text(encoding="utf-8")
    try:
        if args.selftest:
            selftest(eval_source, vm_source)
        verdict = check(args.expect, eval_source, vm_source, args.elf)
        if args.json_out is not None:
            if verdict is None:
                raise CarrierStateError("--json-out requires --expect removed")
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(
                json.dumps(verdict, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        suffix = f" elf={args.elf}" if args.elf else ""
        print(f"v2-carrier-state: PASS expected={args.expect}{suffix}")
        return 0
    except (CarrierStateError, OSError) as exc:
        print(f"v2-carrier-state: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
