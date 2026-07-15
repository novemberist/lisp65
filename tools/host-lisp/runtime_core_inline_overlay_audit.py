#!/usr/bin/env python3
"""Audit the reset-safe Runtime Core inline boot-overlay prototype."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


_NM_RE = re.compile(
    r"^\s*([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+(\S)\s+(.+?)\s*$"
)
_CONTROL_RE = re.compile(
    r"^\s*([0-9a-fA-F]+):\s+(jsr|jmp)\s+\$([0-9a-fA-F]+)\b",
    re.IGNORECASE,
)


def _parse_int(value: str | int) -> int:
    return value if isinstance(value, int) else int(value, 0)


def _run(command: list[str]) -> str:
    completed = subprocess.run(command, check=True, text=True, capture_output=True)
    return completed.stdout


def _parse_symbols(text: str) -> dict[str, dict[str, int | str]]:
    symbols: dict[str, dict[str, int | str]] = {}
    for raw in text.splitlines():
        match = _NM_RE.match(raw)
        if not match:
            continue
        address, size, symbol_type, name = match.groups()
        if name in symbols:
            raise ValueError("duplicate ELF symbol: %s" % name)
        symbols[name] = {
            "address": int(address, 16),
            "size": int(size, 16),
            "type": symbol_type,
        }
    return symbols


def _parse_control_references(text: str) -> list[dict[str, Any]]:
    references = []
    for raw in text.splitlines():
        match = _CONTROL_RE.match(raw)
        if match:
            source, opcode, target = match.groups()
            references.append(
                {
                    "source": int(source, 16),
                    "opcode": opcode.lower(),
                    "target": int(target, 16),
                }
            )
    return references


def _prg_info(data: bytes) -> dict[str, int]:
    if len(data) < 3:
        raise ValueError("PRG is shorter than load address plus payload")
    load_address = data[0] | (data[1] << 8)
    return {
        "bytes": len(data),
        "load_address": load_address,
        "file_end": load_address + len(data) - 2,
    }


def _address(symbols: dict[str, dict[str, int | str]], name: str) -> int:
    symbol = symbols.get(name)
    if symbol is None:
        raise ValueError("missing ELF symbol: %s" % name)
    return int(symbol["address"])


def _function_contains(
    symbols: dict[str, dict[str, int | str]], name: str, address: int
) -> bool:
    symbol = symbols.get(name)
    if symbol is None:
        return False
    start, size = int(symbol["address"]), int(symbol["size"])
    return size > 0 and start <= address < start + size


def _audit(
    symbols: dict[str, dict[str, int | str]],
    controls: list[dict[str, Any]],
    prg: dict[str, int],
    *,
    entry_name: str,
    boot_caller: str,
    runtime_entry: str,
    expected_load_address: int,
    min_boot_stack_gap: int,
    runtime_stack_budget: int,
    min_post_boot_reserve: int,
    max_file_end: int,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    required = (
        "__bss_end",
        "__heap_start",
        "__stack",
        "__lisp65_runtime_core_inline_noinit_start",
        "__lisp65_runtime_core_inline_noinit_end",
        "__lisp65_runtime_core_inline_overlay_start",
        "__lisp65_runtime_core_inline_overlay_end",
        "__lisp65_runtime_core_inline_overlay_entry",
        "__lisp65_runtime_core_inline_file_end",
        "__lisp65_boot_overlay_start",
        "__lisp65_boot_overlay_end",
        entry_name,
        boot_caller,
        runtime_entry,
    )
    missing = [name for name in required if name not in symbols]
    if missing:
        return ["missing ELF symbols: %s" % ", ".join(missing)], {}

    bss_end = _address(symbols, "__bss_end")
    heap_start = _address(symbols, "__heap_start")
    stack = _address(symbols, "__stack")
    noinit_start = _address(symbols, "__lisp65_runtime_core_inline_noinit_start")
    noinit_end = _address(symbols, "__lisp65_runtime_core_inline_noinit_end")
    overlay_start = _address(symbols, "__lisp65_runtime_core_inline_overlay_start")
    overlay_end = _address(symbols, "__lisp65_runtime_core_inline_overlay_end")
    overlay_entry = _address(symbols, "__lisp65_runtime_core_inline_overlay_entry")
    exported_file_end = _address(symbols, "__lisp65_runtime_core_inline_file_end")
    entry = _address(symbols, entry_name)
    runtime_entry_address = _address(symbols, runtime_entry)

    expected_overlay_start = (noinit_end + 2) & ~1
    boot_stack_gap = stack - overlay_end
    post_boot_stack_gap = stack - heap_start
    post_boot_reserve = post_boot_stack_gap - runtime_stack_budget
    overlay_bytes = overlay_end - overlay_start

    if noinit_start < bss_end:
        errors.append(".noinit starts before .bss ends")
    if overlay_start != expected_overlay_start:
        errors.append(
            "overlay start 0x%04x != aligned post-.noinit address 0x%04x"
            % (overlay_start, expected_overlay_start)
        )
    if heap_start > overlay_start:
        errors.append("overlay starts below the resident heap floor")
    if overlay_bytes <= 0:
        errors.append("overlay span is empty or reversed")
    if overlay_entry != entry:
        errors.append("exported overlay entry does not match %s" % entry_name)
    if not overlay_start <= entry < overlay_end:
        errors.append("overlay entry lies outside the overlay span")
    if _address(symbols, "__lisp65_boot_overlay_start") != overlay_start:
        errors.append("generic and Runtime Core overlay starts differ")
    if _address(symbols, "__lisp65_boot_overlay_end") != overlay_end:
        errors.append("generic and Runtime Core overlay ends differ")
    if exported_file_end != overlay_end:
        errors.append("linker file-end symbol does not equal overlay end")
    if prg["load_address"] != expected_load_address:
        errors.append(
            "PRG load address 0x%04x != 0x%04x"
            % (prg["load_address"], expected_load_address)
        )
    if prg["file_end"] != overlay_end:
        errors.append(
            "flat PRG file end 0x%04x != overlay end 0x%04x"
            % (prg["file_end"], overlay_end)
        )
    if prg["file_end"] >= max_file_end:
        errors.append(
            "flat PRG file end 0x%04x is not below 0x%04x"
            % (prg["file_end"], max_file_end)
        )
    if boot_stack_gap < min_boot_stack_gap:
        errors.append(
            "boot stack gap %d < %d" % (boot_stack_gap, min_boot_stack_gap)
        )
    if post_boot_reserve < min_post_boot_reserve:
        errors.append(
            "post-boot reserve %d < %d"
            % (post_boot_reserve, min_post_boot_reserve)
        )

    inbound = [
        ref
        for ref in controls
        if not overlay_start <= ref["source"] < overlay_end
        and overlay_start <= ref["target"] < overlay_end
    ]
    valid_inbound = [
        ref
        for ref in inbound
        if ref["opcode"] == "jsr"
        and ref["target"] == entry
        and _function_contains(symbols, boot_caller, ref["source"])
    ]
    if len(inbound) != 1 or len(valid_inbound) != 1:
        errors.append(
            "expected exactly one resident JSR from %s to %s; found %d inbound, %d valid"
            % (boot_caller, entry_name, len(inbound), len(valid_inbound))
        )

    runtime_calls = [
        ref
        for ref in controls
        if ref["opcode"] == "jsr"
        and ref["target"] == runtime_entry_address
        and _function_contains(symbols, boot_caller, ref["source"])
    ]
    if len(runtime_calls) != 1:
        errors.append(
            "expected exactly one %s JSR from %s; found %d"
            % (runtime_entry, boot_caller, len(runtime_calls))
        )
    if valid_inbound and runtime_calls and valid_inbound[0]["source"] >= runtime_calls[0]["source"]:
        errors.append("overlay entry is not called before the Runtime VM entry")

    metrics = {
        "prg_bytes": prg["bytes"],
        "prg_load_address": prg["load_address"],
        "prg_file_end": prg["file_end"],
        "max_file_end": max_file_end,
        "bss_end": bss_end,
        "heap_start": heap_start,
        "noinit_start": noinit_start,
        "noinit_end": noinit_end,
        "overlay_start": overlay_start,
        "overlay_end": overlay_end,
        "overlay_bytes": overlay_bytes,
        "overlay_entry": entry,
        "boot_stack_gap": boot_stack_gap,
        "min_boot_stack_gap": min_boot_stack_gap,
        "post_boot_stack_gap": post_boot_stack_gap,
        "runtime_stack_budget": runtime_stack_budget,
        "post_boot_reserve": post_boot_reserve,
        "min_post_boot_reserve": min_post_boot_reserve,
        "resident_overlay_control_refs": len(inbound),
        "boot_call_address": valid_inbound[0]["source"] if valid_inbound else None,
        "runtime_call_address": runtime_calls[0]["source"] if runtime_calls else None,
    }
    return errors, metrics


def _write_report(path: Path, errors: list[str], metrics: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "lisp65 Runtime Core inline overlay audit",
        "status=%s" % ("ok" if not errors else "fail"),
        "static_reference_scope=absolute-jsr-jmp",
    ]
    for key, value in metrics.items():
        if isinstance(value, int) and (
            key.endswith(("address", "start", "end", "entry"))
            or key in {"heap_start", "bss_end", "max_file_end"}
        ):
            lines.append("%s=0x%04x" % (key, value))
        else:
            lines.append("%s=%s" % (key, "missing" if value is None else value))
    for error in errors:
        lines.append("error=%s" % error)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def _selftest() -> int:
    def symbol(address: int, size: int = 0, symbol_type: str = "A") -> dict[str, int | str]:
        return {"address": address, "size": size, "type": symbol_type}

    symbols = {
        "__bss_end": symbol(0x7000, symbol_type="B"),
        "__heap_start": symbol(0x7000, symbol_type="B"),
        "__stack": symbol(0xD000),
        "__lisp65_runtime_core_inline_noinit_start": symbol(0x7000),
        "__lisp65_runtime_core_inline_noinit_end": symbol(0x7000),
        "__lisp65_runtime_core_inline_overlay_start": symbol(0x7002, symbol_type="T"),
        "__lisp65_runtime_core_inline_overlay_end": symbol(0x7400, symbol_type="T"),
        "__lisp65_runtime_core_inline_overlay_entry": symbol(0x7100, symbol_type="T"),
        "__lisp65_runtime_core_inline_file_end": symbol(0x7400),
        "__lisp65_boot_overlay_start": symbol(0x7002, symbol_type="T"),
        "__lisp65_boot_overlay_end": symbol(0x7400, symbol_type="T"),
        "vm_load_embedded_stdlib": symbol(0x7100, 3, "T"),
        "main": symbol(0x6000, 0x200, "T"),
        "vm_run_dir": symbol(0x6500, 0x100, "T"),
    }
    controls = [
        {"source": 0x6050, "opcode": "jsr", "target": 0x7100},
        {"source": 0x6100, "opcode": "jsr", "target": 0x6500},
    ]
    prg = {
        "bytes": 0x7400 - 0x2001 + 2,
        "load_address": 0x2001,
        "file_end": 0x7400,
    }
    options = {
        "entry_name": "vm_load_embedded_stdlib",
        "boot_caller": "main",
        "runtime_entry": "vm_run_dir",
        "expected_load_address": 0x2001,
        "min_boot_stack_gap": 0x200,
        "runtime_stack_budget": 0x2000,
        "min_post_boot_reserve": 0x2000,
        "max_file_end": 0xB000,
    }

    cases = 0
    errors, _ = _audit(symbols, controls, prg, **options)
    cases += 1
    if errors:
        print("runtime-core-inline-overlay-audit selftest: FAIL valid: %s" % errors)
        return 1

    mutations = []
    mutations.append(("misplaced", {**symbols, "__lisp65_runtime_core_inline_overlay_start": symbol(0x7004)}, controls, prg, options))
    mutations.append(("wrong-entry", {**symbols, "__lisp65_runtime_core_inline_overlay_entry": symbol(0x7101)}, controls, prg, options))
    mutations.append(("truncated-prg", symbols, controls, {**prg, "file_end": 0x73FF}, options))
    mutations.append(("file-ceiling", symbols, controls, prg, {**options, "max_file_end": 0x7400}))
    mutations.append(("boot-stack", symbols, controls, prg, {**options, "min_boot_stack_gap": 0x6000}))
    mutations.append(("post-reserve", symbols, controls, prg, {**options, "min_post_boot_reserve": 0x5000}))
    mutations.append(("missing-boot-call", symbols, controls[1:], prg, options))
    mutations.append(("extra-boot-call", symbols, controls + [{"source": 0x6060, "opcode": "jsr", "target": 0x7100}], prg, options))
    mutations.append(("boot-after-runtime", symbols, [{"source": 0x6150, "opcode": "jsr", "target": 0x7100}, controls[1]], prg, options))
    for name, case_symbols, case_controls, case_prg, case_options in mutations:
        case_errors, _ = _audit(case_symbols, case_controls, case_prg, **case_options)
        cases += 1
        if not case_errors:
            print("runtime-core-inline-overlay-audit selftest: FAIL mutation %s passed" % name)
            return 1
    print("runtime-core-inline-overlay-audit selftest: PASS cases=%d" % cases)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--prg", type=Path)
    parser.add_argument("--nm", type=Path)
    parser.add_argument("--objdump", type=Path)
    parser.add_argument("--entry", default="vm_load_embedded_stdlib")
    parser.add_argument("--boot-caller", default="main")
    parser.add_argument("--runtime-entry", default="vm_run_dir")
    parser.add_argument("--expected-load-address", default="0x2001")
    parser.add_argument("--min-boot-stack-gap", default="512")
    parser.add_argument("--runtime-stack-budget", default="8192")
    parser.add_argument("--min-post-boot-reserve", default="8192")
    parser.add_argument("--max-file-end", default="0xb000")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.selftest:
        return _selftest()
    missing_args = [
        name
        for name in ("elf", "prg", "nm", "objdump", "out")
        if getattr(args, name) is None
    ]
    if missing_args:
        parser.error("required without --selftest: %s" % ", ".join("--" + v for v in missing_args))

    try:
        symbols = _parse_symbols(
            _run([str(args.nm), "-n", "-S", "--defined-only", str(args.elf)])
        )
        controls = _parse_control_references(
            _run([str(args.objdump), "-d", "--no-show-raw-insn", str(args.elf)])
        )
        prg = _prg_info(args.prg.read_bytes())
        errors, metrics = _audit(
            symbols,
            controls,
            prg,
            entry_name=args.entry,
            boot_caller=args.boot_caller,
            runtime_entry=args.runtime_entry,
            expected_load_address=_parse_int(args.expected_load_address),
            min_boot_stack_gap=_parse_int(args.min_boot_stack_gap),
            runtime_stack_budget=_parse_int(args.runtime_stack_budget),
            min_post_boot_reserve=_parse_int(args.min_post_boot_reserve),
            max_file_end=_parse_int(args.max_file_end),
        )
        _write_report(args.out, errors, metrics)
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print("runtime-core-inline-overlay-audit: ERROR %s" % exc, file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print("runtime-core-inline-overlay-audit: FAIL %s" % error, file=sys.stderr)
        return 1
    print(
        "runtime-core-inline-overlay-audit: PASS "
        "overlay=%dB boot_gap=%d post_reserve=%d file_end=0x%04x refs=%d"
        % (
            metrics["overlay_bytes"],
            metrics["boot_stack_gap"],
            metrics["post_boot_reserve"],
            metrics["prg_file_end"],
            metrics["resident_overlay_control_refs"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
