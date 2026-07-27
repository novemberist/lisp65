#!/usr/bin/env python3
"""Pin the target-stable C2 runtime-overlay CRC loop after WPLTO."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Sequence

from elf_truth import ElfTruth, ElfTruthError


ROOT = Path(__file__).resolve().parents[2]
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
CRC = "rtov_crc_mem"
CATALOG = "vm_runtime_overlay_catalog_verifier"
REMOVED_CRC = "rtov_c_crc_mem"
SHARED_RETRY_HEAD = "rtov_crc_converge_shared_probe"
SHARED_RETRY_WINDOW = "rtov_crc_converge_retry_window"
SHARED_RETRY_FACADE = "c2_facade_rtov_crc_mem"
CRC_SECTION = ".text"
CATALOG_SECTION = ".lisp65_rt_rtov_catalog"
SECTION_RE = re.compile(r"^Disassembly of section (.+):$")
INSTRUCTION_RE = re.compile(
    r"^\s*([0-9a-fA-F]+):\s+([A-Za-z][A-Za-z0-9]*)"
    r"(?:\s+([^;]+?))?\s*(?:;.*)?$")
DIRECT_RE = re.compile(r"^\$([0-9a-fA-F]+)\b")


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def disassembly_rows(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    section = ""
    for raw in text.splitlines():
        match = SECTION_RE.match(raw.strip())
        if match:
            section = match.group(1)
            continue
        match = INSTRUCTION_RE.match(raw)
        if not match:
            continue
        address, opcode, operand = match.groups()
        rows.append({
            "section": section,
            "address": int(address, 16),
            "opcode": opcode.lower(),
            "operand": (operand or "").strip().lower(),
        })
    return rows


def _direct_operand(row: dict[str, Any]) -> int | None:
    match = DIRECT_RE.match(str(row["operand"]))
    return int(match.group(1), 16) if match else None


def audit_model(symbols: dict[str, dict[str, Any]],
                rows: list[dict[str, Any]]) -> dict[str, Any]:
    require(CRC in symbols and CATALOG in symbols,
            "missing C2 runtime CRC or catalog-verifier symbol")
    require(REMOVED_CRC not in symbols,
            "retired transient runtime CRC helper returned")
    crc = symbols[CRC]
    catalog = symbols[CATALOG]
    require(crc["section"] == CRC_SECTION and int(crc["bytes"]) > 0
            and crc.get("symbol_type") == "Function",
            "rtov_crc_mem is not a sized resident .text function")
    require(catalog["section"] == CATALOG_SECTION
            and int(catalog["bytes"]) > 0,
            "runtime catalog verifier section/size drift")

    def body(symbol: dict[str, Any]) -> list[dict[str, Any]]:
        start = int(symbol["value"])
        end = start + int(symbol["bytes"])
        return [row for row in rows
                if row["section"] == symbol["section"]
                and start <= int(row["address"]) < end]

    crc_body = body(crc)
    catalog_body = body(catalog)
    require(crc_body, "rtov_crc_mem disassembly is empty")
    require(not any(row["opcode"] == "dew" for row in crc_body),
            "rtov_crc_mem contains forbidden DEW regression")
    dec_operands = sorted({operand for row in crc_body
                           if row["opcode"] == "dec"
                           for operand in [_direct_operand(row)]
                           if operand is not None})
    require(len(dec_operands) >= 2,
            "rtov_crc_mem does not decrement two distinct byte operands")
    require(any(row["opcode"] == "inw" for row in crc_body),
            "rtov_crc_mem does not advance its data pointer")
    immediate_eors = {str(row["operand"]) for row in crc_body
                      if row["opcode"] == "eor"
                      and str(row["operand"]).startswith("#$")}
    require({"#$21", "#$10"} <= immediate_eors,
            "rtov_crc_mem polynomial immediates drifted")
    retry_names = (SHARED_RETRY_HEAD, SHARED_RETRY_WINDOW,
                   SHARED_RETRY_FACADE)
    retry_present = [name in symbols for name in retry_names]
    require(all(retry_present) or not any(retry_present),
            "shared CRC retry seam is only partially linked")
    mode = "direct-catalog-to-crc"
    calls: list[dict[str, Any]]
    retry_metrics: dict[str, Any] = {}
    if all(retry_present):
        head, window, facade = (symbols[name] for name in retry_names)
        require(head["section"] == ".text" and int(head["bytes"]) > 0,
                "shared retry head is not a sized resident .text function")
        require(window["section"] ==
                ".lisp65_c2_kernal_window.crc_retry"
                and int(window["bytes"]) == 52,
                "shared retry window is not the exact 52-byte tenant")
        require(facade["section"] == ".lisp65_c2_host_facade"
                and int(facade["bytes"]) == 3,
                "shared retry facade is not one three-byte vector")
        head_body, window_body, facade_body = (
            body(item) for item in (head, window, facade))
        calls = [row for row in catalog_body
                 if row["opcode"] == "jsr"
                 and _direct_operand(row) in {
                     int(head["value"]), int(crc["value"])}]
        all_head_calls = [row for row in rows
                          if row["opcode"] == "jsr"
                          and _direct_operand(row) == int(head["value"])]
        head_to_window = [row for row in head_body
                          if row["opcode"] == "jmp"
                          and _direct_operand(row) == int(window["value"])]
        window_to_facade = [row for row in window_body
                            if row["opcode"] == "jsr"
                            and _direct_operand(row) == int(facade["value"])]
        facade_to_crc = [row for row in facade_body
                         if row["opcode"] == "jmp"
                         and _direct_operand(row) == int(crc["value"])]
        require(len(calls) == 0,
                "cold catalog verifier bypassed its slice-local CRC path")
        require(len(all_head_calls) == 2,
                f"shared retry head must have two hot callsites; "
                f"found {len(all_head_calls)}")
        require(len(head_to_window) == 1 and len(window_to_facade) == 1
                and len(facade_to_crc) == 1,
                "shared CRC retry head/window/facade/leaf chain drifted")
        mode = "shared-head-to-window-to-facade-to-crc"
        retry_metrics = {
            "head_address": int(head["value"]),
            "head_bytes": int(head["bytes"]),
            "hot_callsite_count": len(all_head_calls),
            "window_address": int(window["value"]),
            "window_bytes": int(window["bytes"]),
            "facade_address": int(facade["value"]),
            "facade_bytes": int(facade["bytes"]),
            "head_to_window_edges": len(head_to_window),
            "window_to_facade_edges": len(window_to_facade),
            "facade_to_crc_edges": len(facade_to_crc),
        }
    else:
        calls = [row for row in catalog_body
                 if row["opcode"] == "jsr"
                 and _direct_operand(row) == int(crc["value"])]
        require(len(calls) == 1,
                f"catalog verifier must call resident rtov_crc_mem once; "
                f"found {len(calls)}")
    return {
        "status": "passed-target-stable-bytewise-crc-loop",
        "crc_section": crc["section"],
        "crc_address": int(crc["value"]),
        "crc_bytes": int(crc["bytes"]),
        "crc_instruction_count": len(crc_body),
        "byte_decrement_operands": dec_operands,
        "dew_count": 0,
        "pointer_progress_instruction_count": sum(
            row["opcode"] == "inw" for row in crc_body),
        "polynomial_immediates": sorted(immediate_eors),
        "catalog_section": catalog["section"],
        "catalog_crc_call_count": len(calls),
        "crc_call_mode": mode,
        "shared_retry": retry_metrics,
        "retired_crc_symbol_present": False,
    }


def audit_elf(elf: Path, *, out: Path | None = None) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=TOOLCHAIN / "llvm-readobj")
    selected_symbols = (CRC, CATALOG, REMOVED_CRC, SHARED_RETRY_HEAD,
                        SHARED_RETRY_WINDOW, SHARED_RETRY_FACADE)
    symbols = {row.name: {
        "value": row.value, "bytes": row.bytes, "section": row.section,
        "symbol_type": row.symbol_type,
    } for row in truth.symbols if row.name in selected_symbols}
    completed = subprocess.run(
        [str(TOOLCHAIN / "llvm-objdump"), "-d", "--no-show-raw-insn",
         str(elf)], check=True, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    metrics = audit_model(symbols, disassembly_rows(completed.stdout))
    value = {
        "format": "lisp65-c2-crc-codegen-gate-v2",
        "elf": str(elf),
        "metrics": metrics,
        "status": metrics["status"],
        "invariant": (
            "WPLTO rtov_crc_mem decrements separate low/high byte objects, "
            "never DEW; the catalog reaches the one resident CRC truth "
            "either directly or through the one contract-bound shared retry "
            "head/window/facade chain."),
    }
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    return value


def selftest() -> dict[str, str]:
    symbols = {
        CRC: {"value": 0x6800, "bytes": 0x20, "section": CRC_SECTION,
              "symbol_type": "Function"},
        CATALOG: {"value": 0xC400, "bytes": 0x20,
                  "section": CATALOG_SECTION, "symbol_type": "Function"},
    }
    valid = [
        {"section": CRC_SECTION, "address": 0x6800,
         "opcode": "dec", "operand": "$7d"},
        {"section": CRC_SECTION, "address": 0x6802,
         "opcode": "dec", "operand": "$7e"},
        {"section": CRC_SECTION, "address": 0x6804,
         "opcode": "inw", "operand": "$7f"},
        {"section": CRC_SECTION, "address": 0x6806,
         "opcode": "eor", "operand": "#$21"},
        {"section": CRC_SECTION, "address": 0x6808,
         "opcode": "eor", "operand": "#$10"},
        {"section": CATALOG_SECTION, "address": 0xC405,
         "opcode": "jsr", "operand": "$6800 <rtov_crc_mem>"},
    ]
    audit_model(symbols, valid)
    mutations = {
        "dew-regression": [
            {**valid[0], "opcode": "dew", "operand": "$16"}, *valid[1:]],
        "single-dec-regression": [valid[0], *valid[2:]],
        "missing-pointer-progress": [*valid[:2], *valid[3:]],
        "missing-polynomial-half": [*valid[:4], *valid[5:]],
        "missing-catalog-call": valid[:-1],
    }
    passed: dict[str, str] = {}
    for name, rows in mutations.items():
        try:
            audit_model(symbols, rows)
        except GateError as error:
            passed[name] = str(error)
        else:
            raise GateError(f"mutation was accepted: {name}")
    legacy = {**symbols, REMOVED_CRC: {
        "value": 0x6900, "bytes": 0x10, "section": CATALOG_SECTION}}
    try:
        audit_model(legacy, valid)
    except GateError as error:
        passed["retired-crc-return"] = str(error)
    else:
        raise GateError("retired CRC mutation was accepted")
    shared_symbols = {
        **symbols,
        SHARED_RETRY_HEAD: {
            "value": 0x6900, "bytes": 0x0A, "section": ".text",
            "symbol_type": "Function"},
        SHARED_RETRY_WINDOW: {
            "value": 0xFF44, "bytes": 52,
            "section": ".lisp65_c2_kernal_window.crc_retry",
            "symbol_type": "Function"},
        SHARED_RETRY_FACADE: {
            "value": 0xB5F1, "bytes": 3,
            "section": ".lisp65_c2_host_facade",
            "symbol_type": "Function"},
    }
    shared_rows = [*valid[:-1],
        {"section": ".text", "address": 0x6A00,
         "opcode": "jsr", "operand": "$6900"},
        {"section": ".text", "address": 0x6A10,
         "opcode": "jsr", "operand": "$6900"},
        {"section": ".text", "address": 0x6900,
         "opcode": "jmp", "operand": "$ff44"},
        {"section": ".lisp65_c2_kernal_window.crc_retry",
         "address": 0xFF44, "opcode": "jsr", "operand": "$b5f1"},
        {"section": ".lisp65_c2_host_facade", "address": 0xB5F1,
         "opcode": "jmp", "operand": "$6800"},
    ]
    audit_model(shared_symbols, shared_rows)
    for name, index in {
            "shared-window-bypasses-facade": -2,
            "shared-facade-bypasses-crc": -1,
            "shared-callsite-missing": 6,
    }.items():
        candidate = shared_rows.copy()
        candidate.pop(index)
        try:
            audit_model(shared_symbols, candidate)
        except GateError as error:
            passed[name] = str(error)
        else:
            raise GateError(f"shared retry mutation was accepted: {name}")
    return passed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            mutations = selftest()
            print("c2-crc-codegen-gate: SELFTEST PASS mutations="
                  + str(len(mutations)))
            return 0
        if args.elf is None:
            parser.error("--elf is required without --selftest")
        value = audit_elf(args.elf, out=args.out)
        print("c2-crc-codegen-gate: " + value["status"])
        return 0
    except (GateError, ElfTruthError, OSError, subprocess.CalledProcessError,
            ValueError) as error:
        print("c2-crc-codegen-gate: FAIL: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
