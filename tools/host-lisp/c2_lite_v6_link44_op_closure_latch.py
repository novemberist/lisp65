#!/usr/bin/env python3
"""Class-B cycle 2: one-site, JTAG-raw OP_CLOSURE DIRMISS latch."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_bank2_target_stage_successor_link as LINK44  # noqa: E402
import c2_lite_v6_roots_fronts_product_profile as PROFILE  # noqa: E402
import c2_lite_v6_link44_vm_run_dir_latch as CYCLE1  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
DEFINE = "LISP65_C2_DYNAMIC_LOOKUP_DIAGNOSTIC"
VM = ROOT / "src/vm.c"
VM_H = ROOT / "src/vm.h"
EVAL = ROOT / "src/eval.c"
BASE_DIR = CYCLE1.BASE_DIR
BASE_PRODUCT = CYCLE1.BASE_PRODUCT
BASE_ELF = CYCLE1.BASE_ELF
BASE_RECEIPT = CYCLE1.BASE_RECEIPT
FIRST_RED = CYCLE1.FIRST_RED
FULL_LATCH_RED = CYCLE1.FULL_LATCH_RED
BASE_FEATURES = tuple(PROFILE.value()["feature_defines"])
FEATURES = (*BASE_FEATURES, DEFINE)
CYCLE1_RECEIPT = EVIDENCE / "c2.2-link44-vm-run-dir-latch-hardware-cycle1-receipt.json"
CYCLE1_CORRECTION = EVIDENCE / (
    "c2.2-link44-vm-run-dir-latch-hardware-cycle1-interpretation-correction.json")

PROBE_OUT = ROOT / "build/c2.2/substitution/link44-op-closure-latch-wplto"
PROBE_INTERNAL = EVIDENCE / "c2.2-link44-op-closure-latch-wplto-internal-structural.json"
PROBE_RECEIPT = EVIDENCE / "c2.2-link44-op-closure-latch-wplto-receipt.json"
LINK_OUT = ROOT / "build/c2.2/substitution/link44-op-closure-latch-diagnostic"
LINK_INTERNAL = EVIDENCE / "c2.2-link44-op-closure-latch-diagnostic-internal-structural.json"
LINK_RECEIPT = EVIDENCE / "c2.2-link44-op-closure-latch-diagnostic-link-receipt.json"


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def source_gate(vm: str, header: str, evaluation: str,
                *, mutations: bool = False) -> dict[str, Any]:
    start = "static uint8_t vm_op_closure(obj sym, uint8_t nuv, uint16_t stack_base) {"
    end = "#endif\n\n/* VM-natives apply"
    require(start in vm and end in vm, "OP_CLOSURE diagnostic region absent")
    region = vm.split(start, 1)[1].split(end, 1)[0]
    for token in (
            "static uint16_t vmr_hdrlen, vmr_poff;",
            "vmr_hdrlen = (uint16_t)sym;",
            "vmr_poff = 0x8202u;"):
        require(token in vm, f"OP_CLOSURE latch token absent: {token}")
    require(region.count("vmr_hdrlen = (uint16_t)sym;") == 1
            and region.count("vmr_poff = 0x8202u;") == 1,
            "OP_CLOSURE raw tuple is not unique at site 2")
    require(vm.count("vmr_hdrlen = (uint16_t)sym;") == 1
            and vm.count("vmr_poff = 0x8202u;") == 1
            and vm.count("vmr_poff = 0x82") == 1,
            "diagnostic stores escaped the one-site region")
    vm_run_dir = vm.split("obj vm_run_dir(int di,", 1)[1].split(
        "#if defined(LISP65_COMPILE_REPL)", 1)[0]
    require("vmr_hdrlen =" not in vm_run_dir and "vmr_poff =" not in vm_run_dir,
            "cycle-1 vm_run_dir instrumentation survived")
    require(not any(token in vm for token in (
        "vm_dirmiss_latch", "vm_dirmiss_latched_lookup",
        "vm_dirmiss_latched_context", "VM_DIRMISS_LATCH(")),
        "multi-site/helper diagnostic survived the sequential cut")
    require(DEFINE not in header and DEFINE not in evaluation,
            "JTAG-raw cycle retained a renderer or public accessor")

    rejected: dict[str, str] = {}
    if mutations:
        candidates = {
            "lookup-store-removed": vm.replace(
                "vmr_hdrlen = (uint16_t)sym;", "/* removed */", 1),
            "context-store-removed": vm.replace(
                "vmr_poff = 0x8202u;", "/* removed */", 1),
            "wrong-site": vm.replace("0x8202u", "0x8203u", 1),
            "wrong-family": vm.replace("0x8202u", "0x8102u", 1),
            "valid-bit-removed": vm.replace("0x8202u", "0x0202u", 1),
            "second-state": vm.replace(
                "static uint16_t vmr_hdrlen, vmr_poff;",
                "static uint16_t vmr_hdrlen, vmr_poff, vm_diag_second;", 1),
            "helper-reintroduced": vm.replace(
                "vmr_hdrlen = (uint16_t)sym;",
                "vm_dirmiss_latch(sym, 2u);", 1),
            "second-site": vm.replace(
                "vm_status = VM_DIRMISS; goto done;",
                "vmr_poff = 0x8203u; vm_status = VM_DIRMISS; goto done;", 1),
        }
        for name, candidate in candidates.items():
            try:
                source_gate(candidate, header, evaluation, mutations=False)
            except GateError:
                rejected[name] = "rejected"
            else:
                raise GateError(f"OP_CLOSURE latch mutation accepted: {name}")
    return {
        "status": "passed-one-site-jtag-raw-op-closure-latch-source-gate",
        "site": 2,
        "site_name": "OP_CLOSURE-target",
        "tuple": {
            "vmr_hdrlen": "raw target obj, little-endian",
            "vmr_poff_low": "site = 2",
            "vmr_poff_high": "0x82 = valid bit plus Session family 2",
        },
        "new_state_bytes": 0,
        "new_string_bytes": 0,
        "renderer": "none; JTAG only",
        "instrumented_sites": 1,
        "mutations_rejected": rejected,
    }


def elf(path: Path) -> ElfTruth:
    return ElfTruth.read(path, llvm_readobj=LINK44.P.TOOLCHAIN / "llvm-readobj")


def function_body(path: Path, name: str, table: ElfTruth) -> str:
    return CYCLE1.function_body(path, name, table)


def linked_gate(path: Path) -> dict[str, Any]:
    before, after = elf(BASE_ELF), elf(path)
    cells: dict[str, Any] = {}
    for name in ("vmr_hdrlen", "vmr_poff"):
        base, row = before.symbol(name), after.symbol(name)
        require(row.bytes == base.bytes == 2 and row.section == base.section,
                f"cycle-2 latch does not reuse the two-byte cell: {name}")
        cells[name] = {"address": f"0x{row.value:04x}", "bytes": row.bytes,
                       "section": row.section}
    require(not any(after.symbols_by_name.get(name) for name in (
        "vm_dirmiss_latch", "vm_dirmiss_latched_lookup",
        "vm_dirmiss_latched_context")),
        "cycle-2 latch linked a helper or renderer accessor")
    body = function_body(path, "vm_op_closure", after)
    references: dict[str, list[str]] = {}
    for name, cell in cells.items():
        address = int(cell["address"], 16)
        rows = [line.strip() for line in body.splitlines()
                if re.search(rf"\$(?:{address:x}|{address + 1:x})\b", line)]
        require(rows, f"vm_op_closure does not write latch cell {name}")
        references[name] = rows

    foreign: dict[str, dict[str, Any]] = {}
    for name in ("vm_run_dir", "vm_run_inner", "vm_check_status"):
        current_body = function_body(path, name, after)
        baseline_body = function_body(BASE_ELF, name, before)
        by_cell: dict[str, Any] = {}
        for cell_name, cell in cells.items():
            address = int(cell["address"], 16)
            baseline_address = before.symbol(cell_name).value
            hits = [line for line in current_body.splitlines()
                    if re.search(rf"\$(?:{address:x}|{address + 1:x})\b", line)]
            old_hits = [line for line in baseline_body.splitlines()
                        if re.search(
                            rf"\$(?:{baseline_address:x}|{baseline_address + 1:x})\b",
                            line)]
            require(len(hits) == len(old_hits),
                    f"cycle-2 latch changed {name} references to {cell_name}")
            by_cell[cell_name] = {
                "link44_references": len(old_hits),
                "diagnostic_references": len(hits),
            }
        foreign[name] = by_cell
    sizes = {}
    for name in ("vm_op_closure", "vm_run_dir", "vm_run_inner", "vm_check_status"):
        a, b = before.symbol(name), after.symbol(name)
        sizes[name] = {"link44_bytes": a.bytes, "diagnostic_bytes": b.bytes,
                       "delta_bytes": b.bytes - a.bytes}
    return {
        "status": "passed-linked-one-site-op-closure-two-cell-jtag-raw-latch",
        "cells": cells,
        "vm_op_closure_references": references,
        "function_sizes": sizes,
        "uninstrumented_function_latch_references": foreign,
        "new_bss_bytes": 0,
        "helper_functions": 0,
        "renderer_delta_bytes": 0,
    }


def cycle1_authority() -> dict[str, Any]:
    original = json.loads(CYCLE1_RECEIPT.read_text(encoding="utf-8"))
    correction = json.loads(CYCLE1_CORRECTION.read_text(encoding="utf-8"))
    require(original.get("status") == "site1-silent-next-site-review-required"
            and original.get("capture", {}).get("site_hit") is False
            and original.get("capture", {}).get("bytes_hex") == "13001300",
            "cycle-1 hardware result is not the silent-site authority")
    original_binding = correction.get("original_receipt", {})
    require(original_binding.get("path") == CYCLE1_RECEIPT.relative_to(ROOT).as_posix()
            and original_binding.get("bytes") == CYCLE1_RECEIPT.stat().st_size
            and original_binding.get("sha256") == CYCLE1.sha(CYCLE1_RECEIPT)
            and correction.get("status") == "corrected-site1-silent-no-lookup-identity"
            and correction.get("authoritative_disposition", {}).get("lookup_identity")
                == "not captured",
            "cycle-1 interpretation correction drift")
    return {
        "hardware_cycle1": CYCLE1.bind(CYCLE1_RECEIPT),
        "interpretation_correction": CYCLE1.bind(CYCLE1_CORRECTION),
    }


def prerequisites(stage: str) -> dict[str, Any]:
    for path, digest in {
            BASE_PRODUCT: CYCLE1.BASE_PRODUCT_SHA,
            BASE_RECEIPT: CYCLE1.BASE_RECEIPT_SHA,
            FIRST_RED: CYCLE1.FIRST_RED_SHA,
            FULL_LATCH_RED: CYCLE1.FULL_LATCH_RED_SHA,
            PROFILE.PROFILE: CYCLE1.PROFILE_SHA}.items():
        require(path.is_file() and CYCLE1.sha(path) == digest,
                f"OP_CLOSURE latch authority drift: {path}")
    result = {
        "link44_rollback": {**CYCLE1.bind(BASE_PRODUCT), "status": "untouched"},
        "link44_structure": CYCLE1.bind(BASE_RECEIPT),
        "dynamic_top_level_first_red": CYCLE1.bind(FIRST_RED),
        "full_latch_capacity_first_red": CYCLE1.bind(FULL_LATCH_RED),
        "sequential_predecessor": cycle1_authority(),
        "canonical_profile": {**CYCLE1.bind(PROFILE.PROFILE),
                              "features": list(BASE_FEATURES)},
        "one_site_source_gate": source_gate(
            VM.read_text(encoding="utf-8"), VM_H.read_text(encoding="utf-8"),
            EVAL.read_text(encoding="utf-8"), mutations=True),
        "driver": CYCLE1.bind(Path(__file__)),
    }
    if stage == "link":
        require(PROBE_RECEIPT.is_file(), "green cycle-2 WPLTO receipt absent")
        probe = json.loads(PROBE_RECEIPT.read_text(encoding="utf-8"))
        require(probe.get("status") ==
                "passed-op-closure-latch-WPLTO-no-hardware",
                "cycle-2 WPLTO is not green")
        result["green_cycle2_wplto"] = CYCLE1.bind(PROBE_RECEIPT)
    return result


def stage_paths(stage: str) -> tuple[Path, Path, Path]:
    return ((PROBE_OUT, PROBE_INTERNAL, PROBE_RECEIPT) if stage == "probe"
            else (LINK_OUT, LINK_INTERNAL, LINK_RECEIPT))


def run_stage(stage: str) -> dict[str, Any]:
    out, internal, receipt_path = stage_paths(stage)
    require(stage in ("probe", "link"), "invalid cycle-2 stage")
    require(not out.exists() and not internal.exists() and not receipt_path.exists(),
            f"cycle-2 {stage} is one-shot")
    if stage == "link":
        require(PROBE_RECEIPT.is_file(), "green WPLTO must precede cycle-2 link")
    old = {
        "out": LINK44.OUT, "receipt": LINK44.RECEIPT,
        "number": LINK44.LINK_NUMBER, "baseline": LINK44.BASELINE,
        "baseline_sha": LINK44.BASELINE_SHA,
        "baseline_receipt": LINK44.BASELINE_RECEIPT,
        "baseline_receipt_sha": LINK44.BASELINE_RECEIPT_SHA,
        "wplto": LINK44.WPLTO, "wplto_sha": LINK44.WPLTO_SHA,
        "hardware_first_red": LINK44.HARDWARE_FIRST_RED,
        "prerequisites": LINK44.prerequisites,
        "features": PROFILE.feature_defines,
        "prelink": LINK44.BASE_LINK.fresh_prelink_gates,
        "replacement": LINK44.BASE_LINK.replacement_gates,
        "single_link": LINK44.P.single_link,
    }

    def feature_defines() -> tuple[str, ...]:
        return FEATURES

    def prelink() -> dict[str, Any]:
        value = old["prelink"]()
        value["op_closure_latch_source"] = source_gate(
            VM.read_text(encoding="utf-8"), VM_H.read_text(encoding="utf-8"),
            EVAL.read_text(encoding="utf-8"), mutations=True)
        return value

    def replacement(product: Path, product_elf: Path,
                    host: dict[str, Any]) -> dict[str, Any]:
        value = old["replacement"](product, product_elf, host)
        value["op_closure_latch"] = linked_gate(product_elf)
        return value

    def single_link(*args: Any, **kwargs: Any) -> Any:
        lines = tuple(line for line in kwargs.get("extra_contract_lines", ())
                      if not line.startswith((
                          "mode=", "source_baseline=", "promotable=",
                          "diagnostic_define=", "delegation_class=",
                          "delegated_cycle=")))
        kwargs["extra_contract_lines"] = (
            "mode=link44-op-closure-jtag-raw-latch-" + stage,
            "source_baseline=link44-c2-lite-v6-bank2-target-stage-replay",
            "promotable=no-permanently-diagnostic-only",
            "diagnostic_define=" + DEFINE,
            "diagnostic_site=OP_CLOSURE-only",
            "diagnostic_renderer=none-jtag-raw",
            "delegation_class=B", "delegated_cycle=2-of-3",
            "new_diagnostic_state_bytes=0", "green_inheritance=none", *lines)
        return old["single_link"](*args, **kwargs)

    authority = BASE_RECEIPT if stage == "probe" else PROBE_RECEIPT
    try:
        LINK44.OUT, LINK44.RECEIPT = out, internal
        LINK44.LINK_NUMBER = 44
        LINK44.BASELINE, LINK44.BASELINE_SHA = BASE_PRODUCT, CYCLE1.BASE_PRODUCT_SHA
        LINK44.BASELINE_RECEIPT = BASE_RECEIPT
        LINK44.BASELINE_RECEIPT_SHA = CYCLE1.BASE_RECEIPT_SHA
        LINK44.WPLTO, LINK44.WPLTO_SHA = authority, CYCLE1.sha(authority)
        LINK44.HARDWARE_FIRST_RED = FIRST_RED
        LINK44.prerequisites = lambda: prerequisites(stage)
        PROFILE.feature_defines = feature_defines
        LINK44.BASE_LINK.fresh_prelink_gates = prelink
        LINK44.BASE_LINK.replacement_gates = replacement
        LINK44.P.single_link = single_link
        result = LINK44.main()
    finally:
        LINK44.OUT, LINK44.RECEIPT = old["out"], old["receipt"]
        LINK44.LINK_NUMBER = old["number"]
        LINK44.BASELINE, LINK44.BASELINE_SHA = old["baseline"], old["baseline_sha"]
        LINK44.BASELINE_RECEIPT = old["baseline_receipt"]
        LINK44.BASELINE_RECEIPT_SHA = old["baseline_receipt_sha"]
        LINK44.WPLTO, LINK44.WPLTO_SHA = old["wplto"], old["wplto_sha"]
        LINK44.HARDWARE_FIRST_RED = old["hardware_first_red"]
        LINK44.prerequisites = old["prerequisites"]
        PROFILE.feature_defines = old["features"]
        LINK44.BASE_LINK.fresh_prelink_gates = old["prelink"]
        LINK44.BASE_LINK.replacement_gates = old["replacement"]
        LINK44.P.single_link = old["single_link"]

    if result != 0:
        value = {
            "format": "lisp65-c2-lite-v6-op-closure-latch-first-red-v1",
            "recorded_on": "2026-07-22",
            "status": f"FIRST RED: OP_CLOSURE latch {stage} stopped",
            "promotable": False,
            "internal_receipt": CYCLE1.bind(internal) if internal.is_file() else None,
            "link44_rollback": {**CYCLE1.bind(BASE_PRODUCT), "status": "untouched"},
            "execution_accounting": {"hardware_runs": 0,
                                     "class_b_cycles_consumed": 1},
            "next_gate": "stop on the first red",
        }
        CYCLE1.write(receipt_path, value)
        os.chmod(receipt_path, 0o444)
        return value

    internal_value = json.loads(internal.read_text(encoding="utf-8"))
    structure_path = ROOT / internal_value["structural_report"]["path"]
    structure = json.loads(structure_path.read_text(encoding="utf-8"))
    capacity = CYCLE1.capacity_gate(structure)
    latch = structure["fresh_replacement_gates"]["op_closure_latch"]
    require(internal_value["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
            and latch["status"].startswith("passed-"),
            "cycle-2 diagnostic closure did not finish green")
    product = ROOT / internal_value["product_identity"]["product"]["path"]
    value = {
        "format": "lisp65-c2-lite-v6-op-closure-latch-" +
                  ("wplto-v1" if stage == "probe" else "diagnostic-link-v1"),
        "recorded_on": "2026-07-22",
        "status": ("passed-op-closure-latch-WPLTO-no-hardware" if stage == "probe"
                   else "passed-nonpromotable-op-closure-latch-hardware-not-run"),
        "promotable": False,
        "delegation": {"class": "B", "cycle": "2-of-3"},
        "identity": {**CYCLE1.bind(product), "diagnostic_only": True},
        "internal_structural_receipt": CYCLE1.bind(internal),
        "structural_report": CYCLE1.bind(structure_path),
        "source_gate": source_gate(
            VM.read_text(encoding="utf-8"), VM_H.read_text(encoding="utf-8"),
            EVAL.read_text(encoding="utf-8"), mutations=True),
        "linked_latch": latch,
        "capacity": capacity,
        "sequential_predecessor": cycle1_authority(),
        "link44_rollback": {**CYCLE1.bind(BASE_PRODUCT), "status": "untouched"},
        "execution_accounting": {
            "whole_program_lto_closure_links": 1,
            "hardware_runs": 0, "promotable_product_links": 0,
            "class_b_cycles_consumed_before_run": 1,
        },
        "next_gate": ("one nonpromotable cycle-2 diagnostic link" if stage == "probe"
                      else "deploy once; submit one expression; JTAG-read tuple"),
    }
    CYCLE1.write(receipt_path, value)
    os.chmod(receipt_path, 0o444)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("selftest", "probe", "link"))
    args = parser.parse_args()
    try:
        value = (source_gate(VM.read_text(encoding="utf-8"),
                             VM_H.read_text(encoding="utf-8"),
                             EVAL.read_text(encoding="utf-8"), mutations=True)
                 if args.stage == "selftest" else run_stage(args.stage))
        print("c2-lite-v6-op-closure-latch: " + value["status"])
        return 2 if value["status"].startswith("FIRST RED") else 0
    except (GateError, CYCLE1.GateError, RuntimeError, OSError, ValueError,
            KeyError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        print("c2-lite-v6-op-closure-latch: FAIL: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
