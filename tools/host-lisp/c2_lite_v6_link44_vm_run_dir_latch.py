#!/usr/bin/env python3
"""Class-B cycle 1: one-site, JTAG-raw vm_run_dir DIRMISS latch."""

from __future__ import annotations

import argparse
import hashlib
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
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
DEFINE = "LISP65_C2_DYNAMIC_LOOKUP_DIAGNOSTIC"
VM = ROOT / "src/vm.c"
VM_H = ROOT / "src/vm.h"
EVAL = ROOT / "src/eval.c"
BASE_DIR = ROOT / (
    "build/c2.2/substitution/"
    "product-link-44-c2-lite-v6-bank2-target-stage-replay")
BASE_PRODUCT = BASE_DIR / "lisp65-c2-substitution-linked.prg"
BASE_ELF = Path(str(BASE_PRODUCT) + ".elf")
BASE_RECEIPT = EVIDENCE / (
    "c2.2-product-link44-c2-lite-v6-bank2-target-stage-replay-"
    "structural-receipt.json")
FIRST_RED = EVIDENCE / (
    "c2.2-product-link44-c2-lite-v6-dynamic-top-level-"
    "hardware-first-red.json")
FULL_LATCH_RED = EVIDENCE / (
    "c2.2-link44-dynamic-lookup-latch-wplto-first-red-diagnosis.json")
BASE_PRODUCT_SHA = (
    "db3112e6503ca96d572cccb7a399c91eb06028faeaa05e595454fb9502b7f926")
BASE_RECEIPT_SHA = (
    "f358d14604eac270d78e407dec9ecf43559267b1344d371ee92fb95189504ede")
FIRST_RED_SHA = (
    "affae865a776faf2cbd69d5df929d488a3ca2021eb0861d0aed1c9c0bcfe2332")
FULL_LATCH_RED_SHA = (
    "8a6d9ddf8d5442f28eda694a704fa5e687c27c15054582f3ebd659cf5739f057")
PROFILE_SHA = (
    "05a6db5519e8d023bac3bbaae5770efa909f66f26204a374d33330aff09c6b53")
BASE_FEATURES = tuple(PROFILE.value()["feature_defines"])
FEATURES = (*BASE_FEATURES, DEFINE)

PROBE_OUT = ROOT / (
    "build/c2.2/substitution/link44-vm-run-dir-latch-wplto")
PROBE_INTERNAL = EVIDENCE / (
    "c2.2-link44-vm-run-dir-latch-wplto-internal-structural.json")
PROBE_RECEIPT = EVIDENCE / (
    "c2.2-link44-vm-run-dir-latch-wplto-receipt.json")
PROBE_REPLAY_RECEIPT = EVIDENCE / (
    "c2.2-link44-vm-run-dir-latch-wplto-pure-replay-receipt.json")
LINK_OUT = ROOT / (
    "build/c2.2/substitution/link44-vm-run-dir-latch-diagnostic")
LINK_INTERNAL = EVIDENCE / (
    "c2.2-link44-vm-run-dir-latch-diagnostic-internal-structural.json")
LINK_RECEIPT = EVIDENCE / (
    "c2.2-link44-vm-run-dir-latch-diagnostic-link-receipt.json")


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def source_gate(vm: str, header: str, evaluation: str,
                *, mutations: bool = False) -> dict[str, Any]:
    region_start = "obj vm_run_dir(int di, const obj *args, uint8_t n) {"
    region_end = "#if defined(LISP65_COMPILE_REPL)"
    require(region_start in vm and region_end in vm,
            "vm_run_dir diagnostic region absent")
    region = vm.split(region_start, 1)[1].split(region_end, 1)[0]
    required = (
        "static uint16_t vmr_hdrlen, vmr_poff;",
        "vmr_hdrlen = (uint16_t)di;",
        "vmr_poff = 0x8201u;",
    )
    for token in required:
        require(token in vm, f"vm_run_dir latch token absent: {token}")
    require(region.count("vmr_hdrlen = (uint16_t)di;") == 1
            and region.count("vmr_poff = 0x8201u;") == 1,
            "vm_run_dir raw tuple is not unique at site 1")
    require(vm.count("vmr_hdrlen = (uint16_t)di;") == 1
            and vm.count("vmr_poff = 0x8201u;") == 1,
            "diagnostic stores escaped the one-site region")
    require(vm.count("vmr_poff = 0x82") == 1,
            "a second Session-family diagnostic site was introduced")
    forbidden = (
        "vm_dirmiss_latch", "vm_dirmiss_latched_lookup",
        "vm_dirmiss_latched_context", "VM_DIRMISS_LATCH(",
    )
    require(not any(token in vm for token in forbidden),
            "multi-site/helper diagnostic survived the sequential cut")
    require(DEFINE not in header and DEFINE not in evaluation,
            "JTAG-raw cycle retained a renderer or public accessor")
    require("lisp_abort_symbol(LISP65_ERR_UNDEFINED_FUNCTION" not in
            evaluation.split("static __attribute__((noinline)) void "
                             "vm_check_status", 1)[1].split("#endif", 1)[0],
            "JTAG-raw cycle retained named-symbol rendering")

    rejected: dict[str, str] = {}
    if mutations:
        candidates = {
            "lookup-store-removed": vm.replace(
                "vmr_hdrlen = (uint16_t)di;", "/* removed */", 1),
            "context-store-removed": vm.replace(
                "vmr_poff = 0x8201u;", "/* removed */", 1),
            "wrong-site": vm.replace("0x8201u", "0x8203u", 1),
            "wrong-family": vm.replace("0x8201u", "0x8101u", 1),
            "valid-bit-removed": vm.replace("0x8201u", "0x0201u", 1),
            "second-state": vm.replace(
                "static uint16_t vmr_hdrlen, vmr_poff;",
                "static uint16_t vmr_hdrlen, vmr_poff, vm_diag_second;", 1),
            "helper-reintroduced": vm.replace(
                "vmr_hdrlen = (uint16_t)di;",
                "vm_dirmiss_latch((obj)di, 1u);", 1),
            "second-site": vm.replace(
                "if (di < 0) { vm_status = VM_DIRMISS; return 0; }",
                "if (di < 0) { vmr_poff = 0x8202u; "
                "vm_status = VM_DIRMISS; return 0; }", 1),
        }
        for name, candidate in candidates.items():
            try:
                source_gate(candidate, header, evaluation, mutations=False)
            except GateError:
                rejected[name] = "rejected"
            else:
                raise GateError(f"vm_run_dir latch mutation accepted: {name}")
    return {
        "status": "passed-one-site-jtag-raw-vm-run-dir-latch-source-gate",
        "site": 1,
        "site_name": "vm_run_dir-entry-length",
        "tuple": {
            "vmr_hdrlen": "raw signed int directory ordinal, little-endian",
            "vmr_poff_low": "site = 1",
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
    row = table.symbol(name)
    run = subprocess.run(
        [str(LINK44.P.TOOLCHAIN / "llvm-objdump"), "-d",
         "--no-show-raw-insn", "--symbolize-operands", str(path)],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=True)
    lines: list[str] = []
    for line in run.stdout.splitlines():
        match = re.match(r"^\s*([0-9a-f]+):", line)
        if match and row.value <= int(match.group(1), 16) < row.value + row.bytes:
            lines.append(line)
    require(lines, f"no linked disassembly for {name}")
    return "\n".join(lines)


def linked_gate(path: Path) -> dict[str, Any]:
    before = elf(BASE_ELF)
    after = elf(path)
    cells: dict[str, Any] = {}
    for name in ("vmr_hdrlen", "vmr_poff"):
        base = before.symbol(name)
        row = after.symbol(name)
        require(row.bytes == base.bytes == 2 and row.section == base.section,
                f"one-site latch does not reuse the two-byte cell: {name}")
        cells[name] = {"address": f"0x{row.value:04x}",
                       "bytes": row.bytes, "section": row.section}
    require(not any(after.symbols_by_name.get(name) for name in (
                "vm_dirmiss_latch", "vm_dirmiss_latched_lookup",
                "vm_dirmiss_latched_context")),
            "sequential latch linked a helper or renderer accessor")
    body = function_body(path, "vm_run_dir", after)
    referenced: dict[str, list[str]] = {}
    for name, cell in cells.items():
        address = int(cell["address"], 16)
        rows = [line.strip() for line in body.splitlines()
                if re.search(rf"\$(?:{address:x}|{address + 1:x})\b", line)]
        require(rows, f"vm_run_dir does not write/reference latch cell {name}")
        referenced[name] = rows
    sizes = {}
    for name in ("vm_run_dir", "vm_run_inner", "vm_check_status"):
        a, b = before.symbol(name), after.symbol(name)
        sizes[name] = {"link44_bytes": a.bytes,
                       "diagnostic_bytes": b.bytes,
                       "delta_bytes": b.bytes - a.bytes}
    foreign_references: dict[str, dict[str, Any]] = {}
    for name in ("vm_run_inner", "vm_check_status"):
        other_body = function_body(path, name, after)
        baseline_body = function_body(BASE_ELF, name, before)
        by_cell: dict[str, Any] = {}
        for cell_name, cell in cells.items():
            address = int(cell["address"], 16)
            baseline_address = before.symbol(cell_name).value
            hits = [line.strip() for line in other_body.splitlines()
                    if re.search(
                        rf"\$(?:{address:x}|{address + 1:x})\b", line)]
            baseline_hits = [line.strip() for line in baseline_body.splitlines()
                             if re.search(
                                 rf"\$(?:{baseline_address:x}|"
                                 rf"{baseline_address + 1:x})\b", line)]
            require(len(hits) == len(baseline_hits),
                    f"one-site latch changed {name} reference cardinality "
                    f"for {cell_name}")
            by_cell[cell_name] = {
                "link44_references": len(baseline_hits),
                "diagnostic_references": len(hits),
            }
        foreign_references[name] = by_cell
    return {
        "status": "passed-linked-one-site-two-cell-jtag-raw-latch",
        "cells": cells,
        "vm_run_dir_references": referenced,
        "function_sizes": sizes,
        "uninstrumented_function_latch_references": foreign_references,
        "size_rule": "sizes are provenance; absence of latch dataflow is the invariant",
        "new_bss_bytes": 0,
        "helper_functions": 0,
        "renderer_delta_bytes": 0,
    }


def baseline_structure() -> dict[str, Any]:
    receipt = json.loads(BASE_RECEIPT.read_text(encoding="utf-8"))
    return json.loads((ROOT / receipt["structural_report"]["path"])
                      .read_text(encoding="utf-8"))


def capacity_gate(structure: dict[str, Any]) -> dict[str, Any]:
    before = baseline_structure()["fresh_replacement_gates"]
    after = structure["fresh_replacement_gates"]
    old, new = before["walls"], after["walls"]
    require(new["ordinary_bank0_bss_headroom_bytes"] ==
            old["ordinary_bank0_bss_headroom_bytes"],
            "one-site latch consumed or displaced ordinary BSS")
    require(new["resident_island_headroom_bytes"] ==
            old["resident_island_headroom_bytes"],
            "JTAG-raw cycle changed the resident Island")
    require(new["fixed_hot_block_headroom_bytes"] ==
            old["fixed_hot_block_headroom_bytes"],
            "one-site latch changed the fixed hot block")
    require(new["e000_headroom_bytes"] == old["e000_headroom_bytes"]
            and new["e000_headroom_bytes"] >= 115,
            "one-site latch changed the E000 window or floor")
    require(new["bank0_text_headroom_bytes"] >= 0,
            "one-site latch exceeds the measured Bank-0 text corridor")
    capacity = after["capacity"]
    require(capacity["session_family_bytes"] == 65438
            and capacity["session_family_headroom_bytes"] == 98,
            "one-site latch changed the Session-family aggregate")
    return {
        "status": "passed-one-site-diagnostic-capacity",
        "link44_walls": old,
        "diagnostic_walls": new,
        "headroom_delta_bytes": {
            name: int(new[name]) - int(old[name]) for name in old},
        "session_family_bytes": 65438,
        "session_family_headroom_bytes": 98,
        "new_bss_bytes": 0,
        "window_delta_bytes": 0,
    }


def prerequisites(stage: str) -> dict[str, Any]:
    for path, digest in {
            BASE_PRODUCT: BASE_PRODUCT_SHA, BASE_RECEIPT: BASE_RECEIPT_SHA,
            FIRST_RED: FIRST_RED_SHA, FULL_LATCH_RED: FULL_LATCH_RED_SHA,
            PROFILE.PROFILE: PROFILE_SHA}.items():
        require(path.is_file() and sha(path) == digest,
                f"vm_run_dir latch authority drift: {path}")
    baseline = json.loads(BASE_RECEIPT.read_text(encoding="utf-8"))
    first_red = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    full = json.loads(FULL_LATCH_RED.read_text(encoding="utf-8"))
    require(baseline["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
            and baseline["product_identity"]["product"]["sha256"] ==
                BASE_PRODUCT_SHA,
            "Link-44 rollback identity is not authoritative")
    require(first_red["status"] ==
            "first-red-product-semantics-review-required"
            and first_red["budgets"]["line_1_product_first_reds"]["after"] ==
                "2/3"
            and first_red["budgets"]["completed_latency_measurements"]
                ["after"] == "0/2",
            "dynamic top-level First Red authority drift")
    require(full["status"] == "first-red-class-b-capacity-review-required"
            and full["measured_attribution"]["text"]["delta_bytes"] == 181,
            "full-latch capacity First Red is not authoritative")
    result = {
        "link44_rollback": {**bind(BASE_PRODUCT), "status": "untouched"},
        "link44_structure": bind(BASE_RECEIPT),
        "dynamic_top_level_first_red": bind(FIRST_RED),
        "full_latch_capacity_first_red": bind(FULL_LATCH_RED),
        "canonical_profile": {**bind(PROFILE.PROFILE),
                              "features": list(BASE_FEATURES)},
        "one_site_source_gate": source_gate(
            VM.read_text(encoding="utf-8"),
            VM_H.read_text(encoding="utf-8"),
            EVAL.read_text(encoding="utf-8"), mutations=True),
        "driver": bind(Path(__file__)),
    }
    if stage == "link":
        require(PROBE_REPLAY_RECEIPT.is_file(),
                "green one-site WPLTO pure replay absent")
        probe = json.loads(PROBE_REPLAY_RECEIPT.read_text(encoding="utf-8"))
        require(probe["status"] ==
                "passed-vm-run-dir-latch-WPLTO-pure-replay-no-hardware",
                "one-site WPLTO is not green")
        result["green_one_site_wplto"] = bind(PROBE_REPLAY_RECEIPT)
    return result


def paths(stage: str) -> tuple[Path, Path, Path]:
    return ((PROBE_OUT, PROBE_INTERNAL, PROBE_RECEIPT) if stage == "probe"
            else (LINK_OUT, LINK_INTERNAL, LINK_RECEIPT))


def run_stage(stage: str) -> dict[str, Any]:
    out, internal, receipt_path = paths(stage)
    require(stage in ("probe", "link"), "invalid one-site stage")
    require(not out.exists() and not internal.exists()
            and not receipt_path.exists(), f"one-site {stage} is one-shot")
    if stage == "link":
        require(PROBE_REPLAY_RECEIPT.is_file(),
                "green pure replay must precede diagnostic link")
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
        value["vm_run_dir_latch_source"] = source_gate(
            VM.read_text(encoding="utf-8"),
            VM_H.read_text(encoding="utf-8"),
            EVAL.read_text(encoding="utf-8"), mutations=True)
        return value

    def replacement(product: Path, product_elf: Path,
                    host: dict[str, Any]) -> dict[str, Any]:
        value = old["replacement"](product, product_elf, host)
        value["vm_run_dir_latch"] = linked_gate(product_elf)
        return value

    def single_link(*args: Any, **kwargs: Any) -> Any:
        lines = tuple(line for line in kwargs.get("extra_contract_lines", ())
                      if not line.startswith((
                          "mode=", "source_baseline=", "promotable=",
                          "diagnostic_define=", "delegation_class=",
                          "delegated_cycle=")))
        kwargs["extra_contract_lines"] = (
            "mode=link44-vm-run-dir-jtag-raw-latch-" + stage,
            "source_baseline=link44-c2-lite-v6-bank2-target-stage-replay",
            "promotable=no-permanently-diagnostic-only",
            "diagnostic_define=" + DEFINE,
            "diagnostic_site=vm_run_dir-only",
            "diagnostic_renderer=none-jtag-raw",
            "delegation_class=B", "delegated_cycle=1-of-3",
            "new_diagnostic_state_bytes=0", "green_inheritance=none",
            *lines)
        return old["single_link"](*args, **kwargs)

    authority = BASE_RECEIPT if stage == "probe" else PROBE_REPLAY_RECEIPT
    try:
        LINK44.OUT, LINK44.RECEIPT = out, internal
        LINK44.LINK_NUMBER = 44
        LINK44.BASELINE, LINK44.BASELINE_SHA = BASE_PRODUCT, BASE_PRODUCT_SHA
        LINK44.BASELINE_RECEIPT = BASE_RECEIPT
        LINK44.BASELINE_RECEIPT_SHA = BASE_RECEIPT_SHA
        LINK44.WPLTO, LINK44.WPLTO_SHA = authority, sha(authority)
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
            "format": "lisp65-c2-lite-v6-vm-run-dir-latch-first-red-v1",
            "recorded_on": "2026-07-22",
            "status": f"FIRST RED: vm_run_dir latch {stage} stopped",
            "promotable": False,
            "internal_receipt": bind(internal) if internal.is_file() else None,
            "link44_rollback": {**bind(BASE_PRODUCT), "status": "untouched"},
            "execution_accounting": {"hardware_runs": 0,
                                      "class_b_cycles_consumed": 0},
            "next_gate": "stop and review the first red",
        }
        write(receipt_path, value)
        os.chmod(receipt_path, 0o444)
        return value

    internal_value = json.loads(internal.read_text(encoding="utf-8"))
    structure_path = ROOT / internal_value["structural_report"]["path"]
    structure = json.loads(structure_path.read_text(encoding="utf-8"))
    capacity = capacity_gate(structure)
    latch = structure["fresh_replacement_gates"]["vm_run_dir_latch"]
    require(internal_value["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
            and latch["status"].startswith("passed-"),
            "one-site diagnostic closure did not finish green")
    product = ROOT / internal_value["product_identity"]["product"]["path"]
    value = {
        "format": "lisp65-c2-lite-v6-vm-run-dir-latch-"
                  + ("wplto-v1" if stage == "probe" else
                     "diagnostic-link-v1"),
        "recorded_on": "2026-07-22",
        "status": ("passed-vm-run-dir-latch-WPLTO-no-hardware"
                   if stage == "probe" else
                   "passed-nonpromotable-vm-run-dir-latch-hardware-not-run"),
        "promotable": False,
        "delegation": {"class": "B", "cycle": "1-of-3"},
        "identity": {**bind(product), "diagnostic_only": True},
        "internal_structural_receipt": bind(internal),
        "structural_report": bind(structure_path),
        "source_gate": source_gate(
            VM.read_text(encoding="utf-8"),
            VM_H.read_text(encoding="utf-8"),
            EVAL.read_text(encoding="utf-8"), mutations=True),
        "linked_latch": latch,
        "capacity": capacity,
        "link44_rollback": {**bind(BASE_PRODUCT), "status": "untouched"},
        "execution_accounting": {
            "whole_program_lto_closure_links": 1,
            "hardware_runs": 0, "promotable_product_links": 0,
        },
        "next_gate": ("one nonpromotable diagnostic link" if stage == "probe"
                      else "deploy once; submit one expression; JTAG-read tuple"),
    }
    write(receipt_path, value)
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
        print("c2-lite-v6-vm-run-dir-latch: " + value["status"])
        return 2 if value["status"].startswith("FIRST RED") else 0
    except (GateError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print("c2-lite-v6-vm-run-dir-latch: FAIL: " + str(error),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
