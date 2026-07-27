#!/usr/bin/env python3
"""Product-shaped WPLTO probe for the permanent VM_DIRMISS detail seam.

This is the authorized Class-C capacity/placement probe only.  The linked
closure is permanently nonpromotable and no hardware action is part of it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_bank2_target_stage_successor_link as LINK44  # noqa: E402
import c2_lite_v6_roots_fronts_product_profile as PROFILE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
VM = ROOT / "src/vm.c"
VM_H = ROOT / "src/vm.h"
EVAL = ROOT / "src/eval.c"
COMPILE = ROOT / "src/compile_repl.c"
INTERRUPT = ROOT / "src/interrupt.c"
ERROR_OVERLAY = ROOT / "src/error_overlay.c"
CONTRACT = ROOT / "config/c2-vm-dirmiss-detail-contract.json"
REVIEW = ROOT / "docs/planning/c2.2-link44-permanent-dirmiss-diagnostic-review.md"
CORRECTION = EVIDENCE / (
    "c2.2-link44-op-closure-cycle3-interpretation-correction.json")
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
BASE_PRODUCT_SHA = (
    "db3112e6503ca96d572cccb7a399c91eb06028faeaa05e595454fb9502b7f926")
BASE_RECEIPT_SHA = (
    "f358d14604eac270d78e407dec9ecf43559267b1344d371ee92fb95189504ede")
FIRST_RED_SHA = (
    "affae865a776faf2cbd69d5df929d488a3ca2021eb0861d0aed1c9c0bcfe2332")
CORRECTION_SHA = (
    "9b79c1f9147adf80305c8a9595543266352a18600be29658fc588bc9c2ffb625")
OUT = ROOT / "build/c2.2/substitution/link44-dirmiss-detail-wplto"
INTERNAL = EVIDENCE / (
    "c2.2-link44-dirmiss-detail-wplto-internal-structural.json")
RECEIPT = EVIDENCE / "c2.2-link44-dirmiss-detail-wplto-receipt.json"


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


def source_gate(vm: str, vm_h: str, evaluation: str, compiler: str,
                interrupt: str, overlay: str, *, mutations: bool = False
                ) -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract["schema"] == "lisp65.c2.vm-dirmiss-detail-contract.v1",
            "VM_DIRMISS detail contract schema drift")
    producers = {
        "compile-inner-helper":
            "if (di < 0) return vm_dirmiss_detail(u.fn[i].name);",
        "compile-defun":
            "if (di < 0) return vm_dirmiss_detail(defname);",
        "vm-run-dir":
            "return vm_dirmiss_detail(\n            (di >= 0 && "
            "(uint16_t)di < 4096u) ? MK_BCODE((uint16_t)di) : NIL);",
        "op-closure": "if (di < 0) return vm_dirmiss_detail(sym);",
        "op-call": "} else {\n                r = vm_dirmiss_detail(sym); "
            "goto done;\n            }\n            if (vm_status != VM_OK)",
        "op-tailcall": "#endif\n                r = vm_dirmiss_detail(sym); "
            "goto done;\n            }\n#ifdef LISP65_VM_DIAGNOSTICS",
    }
    for name, token in producers.items():
        owner = compiler if name.startswith("compile-") else vm
        require(owner.count(token) == 1,
                f"VM_DIRMISS detail producer absent or duplicated: {name}")
    require(vm.count("r = vm_dirmiss_detail(sym); goto done;") == 2,
            "OP_CALL/OP_TAILCALL supplier cardinality drift")
    require(vm.count("vm_status = VM_DIRMISS;") == 1,
            "VM_DIRMISS status is written outside the one seam")
    require("obj vm_dirmiss_detail(obj detail)" in vm_h
            and "obj vm_dirmiss_detail(obj detail) {" in vm
            and "__attribute__((noinline))" in
                vm.split("obj vm_dirmiss_detail(obj detail) {", 1)[0][-80:],
            "canonical out-of-line VM_DIRMISS detail seam absent")
    require(vm.count("if (vm_status != VM_OK) { r = res; goto done; }") == 2,
            "nested OP_CALL/OP_CALLPRIM result detail is not preserved twice")
    require("if (vm_status != VM_OK) { r = detail; goto done; }" in vm,
            "OP_CLOSURE result detail is not preserved")
    require("static __attribute__((noinline)) void vm_check_status(obj detail)"
            in evaluation, "terminal status-plus-detail consumer absent")
    required_calls = (
        "vm_check_status(result);",
        "vm_check_status(r);",
    )
    require(evaluation.count(required_calls[0]) == 4
            and evaluation.count(required_calls[1]) == 2,
            "all six evaluator boundaries do not pass their exact result")
    require("code == LISP65_ERR_VM_UNDEFINED_FUNCTION && IS_SYMI(detail)"
            in evaluation
            and "lisp_abort_symbol(LISP65_ERR_UNDEFINED_FUNCTION, detail);"
            in evaluation,
            "SYMI terminal render mapping is absent")
    require("else\n            lisp_abort_code(code);" in evaluation,
            "BCODE/NIL numeric fallback is absent")
    require("LISP65_C2_DYNAMIC_LOOKUP_DIAGNOSTIC" not in vm
            and "vm_dirmiss_latched" not in vm + vm_h,
            "temporary Class-B latch survived in product sources")
    forbidden_state = (
        "vm_error_detail", "vm_dirmiss_state", "pending_vm_detail",
        "dirmiss_latch",
    )
    require(not any(name in vm + evaluation + compiler
                    for name in forbidden_state),
            "a second persistent error-detail truth was introduced")
    require("static obj pending_symbol = NIL;" in interrupt
            and "pending_symbol = symbol;" in interrupt
            and "pending_symbol = NIL;" in interrupt,
            "existing terminal pending-symbol lifecycle drift")
    require("context->code != LISP65_ERR_UNDEFINED_FUNCTION" in overlay
            and "symname(context->symbol)" in overlay,
            "existing symbol-aware L65E renderer drift")

    rejected: dict[str, str] = {}
    if mutations:
        candidates: dict[str, tuple[str, str, str, str, str, str]] = {}
        for name, token in producers.items():
            if name.startswith("compile-"):
                candidates["omit-" + name] = (
                    vm, vm_h, evaluation,
                    compiler.replace(token, "return NIL;", 1),
                    interrupt, overlay)
            else:
                candidates["omit-" + name] = (
                    vm.replace(token, "/* omitted producer */", 1), vm_h,
                    evaluation, compiler, interrupt, overlay)
        candidates.update({
            "op-call-detail-nil": (
                vm.replace(producers["op-call"],
                           producers["op-call"].replace(
                               "vm_dirmiss_detail(sym)",
                               "vm_dirmiss_detail(NIL)"), 1),
                vm_h, evaluation, compiler, interrupt, overlay),
            "op-tailcall-detail-nil": (
                vm.replace(producers["op-tailcall"],
                           producers["op-tailcall"].replace(
                               "vm_dirmiss_detail(sym)",
                               "vm_dirmiss_detail(NIL)"), 1),
                vm_h, evaluation, compiler, interrupt, overlay),
            "overwrite-inner-op-call": (
                vm.replace("if (vm_status != VM_OK) { r = res; goto done; }",
                           "if (vm_status != VM_OK) { r = NIL; goto done; }", 1),
                vm_h, evaluation, compiler, interrupt, overlay),
            "discard-inner-callprim": (
                vm.replace("if (vm_status != VM_OK) { r = res; goto done; }",
                           "if (vm_status != VM_OK) { goto done; }", 2),
                vm_h, evaluation, compiler, interrupt, overlay),
            "stale-global-detail": (
                vm.replace("obj vm_dirmiss_detail(obj detail) {",
                           "static obj vm_error_detail;\n"
                           "obj vm_dirmiss_detail(obj detail) {", 1),
                vm_h, evaluation, compiler, interrupt, overlay),
            "bcode-rendered-as-symbol": (
                vm, vm_h, evaluation.replace(
                    "IS_SYMI(detail)",
                    "(IS_SYMI(detail) || IS_BCODE(detail))", 1),
                compiler, interrupt, overlay),
            "symbol-render-bypassed": (
                vm, vm_h, evaluation.replace(
                    "lisp_abort_symbol(LISP65_ERR_UNDEFINED_FUNCTION, detail);",
                    "lisp_abort_code(code);", 1),
                compiler, interrupt, overlay),
            "second-status-writer": (
                vm.replace("return detail;", "vm_status = VM_DIRMISS; return detail;", 1),
                vm_h, evaluation, compiler, interrupt, overlay),
            "consumer-drops-detail": (
                vm, vm_h, evaluation.replace("vm_check_status(r);",
                                             "vm_check_status(NIL);", 1),
                compiler, interrupt, overlay),
        })
        for name, parts in candidates.items():
            try:
                source_gate(*parts, mutations=False)
            except (GateError, json.JSONDecodeError):
                rejected[name] = "rejected"
            else:
                raise GateError(f"VM_DIRMISS detail mutation accepted: {name}")
    return {
        "status": "passed-six-producer-one-seam-status-plus-detail-contract",
        "producer_count": 6,
        "producer_map": {name: token for name, token in producers.items()},
        "transport": {
            "pre_terminal": "ordinary obj return value plus vm_status",
            "terminal": "existing pending_symbol/pending_code",
            "c2j_bytes": 0,
            "new_bss_bytes": 0,
            "new_gc_roots": 0,
        },
        "detail_domains": ["SYMI", "BCODE", "NIL"],
        "numeric_symbol_mapping": "VM_DIRMISS+SYMI -> code 28 + symbol",
        "non_symbol_mapping": "VM_DIRMISS+BCODE/NIL -> numeric code 41",
        "mutations_rejected": rejected,
    }


def semantic_fixture() -> dict[str, Any]:
    """An executable model pins precedence and domain dispatch independently."""
    symi, bcode, nil = 0x1232, 0xC100, 0

    def produce(detail: int) -> tuple[str, int]:
        return "VM_DIRMISS", detail

    def outer(status_detail: tuple[str, int]) -> tuple[str, int]:
        return status_detail

    def consume(status_detail: tuple[str, int]) -> tuple[str, int | None]:
        status, detail = status_detail
        require(status == "VM_DIRMISS", "semantic fixture status drift")
        if detail == symi:
            return "LISP65_ERR_UNDEFINED_FUNCTION", detail
        return "LISP65_ERR_VM_UNDEFINED_FUNCTION", None

    suppliers = ["compile_inner_helper", "compile_defun", "vm_run_dir",
                 "op_closure", "op_call", "op_tailcall"]
    for _ in suppliers:
        require(outer(produce(symi)) == ("VM_DIRMISS", symi),
                "inner detail did not survive outer frame")
    require(consume(produce(symi)) ==
            ("LISP65_ERR_UNDEFINED_FUNCTION", symi),
            "SYMI semantic dispatch drift")
    require(consume(produce(bcode)) ==
            ("LISP65_ERR_VM_UNDEFINED_FUNCTION", None)
            and consume(produce(nil)) ==
            ("LISP65_ERR_VM_UNDEFINED_FUNCTION", None),
            "BCODE/NIL semantic dispatch drift")
    return {
        "status": "passed-inner-first-domain-dispatch-model",
        "suppliers": suppliers,
        "inner_detail_byteidentical_through_outer": True,
        "success_uses_error_detail": False,
        "heap_pointer_detail_allowed": False,
    }


def truth(path: Path) -> ElfTruth:
    return ElfTruth.read(path, llvm_readobj=LINK44.P.TOOLCHAIN / "llvm-readobj")


def linked_gate(elf: Path) -> dict[str, Any]:
    current = truth(elf)
    baseline = truth(BASE_ELF)
    helper = current.symbol("vm_dirmiss_detail")
    require(helper.bytes > 0 and helper.symbol_type == "Function"
            and helper.section == ".text",
            "VM_DIRMISS detail seam is not a sized Bank-0 text function")
    terminal = current.symbol("vm_check_status")
    require(terminal.bytes > 0 and terminal.symbol_type == "Function",
            "vm_check_status terminal consumer disappeared")
    cells: dict[str, Any] = {}
    for name in ("pending_code", "pending_symbol"):
        before = baseline.symbol(name)
        after = current.symbol(name)
        require((after.bytes, after.section) == (before.bytes, before.section),
                f"terminal error cell changed shape: {name}")
        cells[name] = {
            "bytes": after.bytes, "section": after.section,
            "address": f"0x{after.value:04x}",
            "shape_same_as_link44": True,
        }
    forbidden = [row.name for row in current.symbols
                 if any(token in row.name for token in
                        ("dirmiss_latch", "vm_error_detail",
                         "pending_vm_detail", "vm_dirmiss_state"))]
    require(not forbidden, "linked ELF acquired a second detail-state symbol")
    references = [row for row in current.relocations
                  if row.target == "vm_dirmiss_detail"]
    require(references, "linked closure has no relocation to the canonical seam")
    return {
        "status": "passed-linked-one-seam-existing-terminal-cells",
        "seam": {"address": f"0x{helper.value:04x}",
                 "bytes": helper.bytes, "section": helper.section,
                 "symbol_type": helper.symbol_type},
        "terminal": {"address": f"0x{terminal.value:04x}",
                     "bytes": terminal.bytes,
                     "section": terminal.section},
        "terminal_cells": cells,
        "seam_relocation_count": len(references),
        "second_detail_state_symbols": forbidden,
        "new_bss_contract_bytes": 0,
    }


def baseline_report() -> dict[str, Any]:
    receipt = json.loads(BASE_RECEIPT.read_text(encoding="utf-8"))
    return json.loads((ROOT / receipt["structural_report"]["path"])
                      .read_text(encoding="utf-8"))


def capacity_gate(structure: dict[str, Any]) -> dict[str, Any]:
    before = baseline_report()["fresh_replacement_gates"]
    after = structure["fresh_replacement_gates"]
    old_walls, walls = before["walls"], after["walls"]
    require(walls["ordinary_bank0_bss_headroom_bytes"] ==
            old_walls["ordinary_bank0_bss_headroom_bytes"],
            "status-plus-detail seam consumed ordinary BSS")
    require(walls["e000_headroom_bytes"] >= 115,
            "status-plus-detail seam crossed the restored E000 floor")
    require(all(int(walls[name]) >= 0 for name in (
                "bank0_text_headroom_bytes",
                "fixed_hot_block_headroom_bytes",
                "resident_island_headroom_bytes")),
            "status-plus-detail seam crossed a resident wall")
    capacity = after["capacity"]
    require(capacity["session_family_bytes"] == 65438
            and capacity["session_family_headroom_bytes"] == 98
            and capacity["session_catalog_records_after"] == 50,
            "status-plus-detail seam changed the Session aggregate")
    return {
        "status": "passed-product-shaped-capacity-no-boundary-change",
        "link44_walls": old_walls,
        "probe_walls": walls,
        "headroom_delta_bytes": {
            name: int(walls[name]) - int(old_walls[name])
            for name in old_walls},
        "ordinary_bss_delta_bytes": 0,
        "session_family_bytes": capacity["session_family_bytes"],
        "session_family_headroom_bytes":
            capacity["session_family_headroom_bytes"],
        "e000_floor_bytes": 115,
    }


def prerequisites() -> dict[str, Any]:
    for path, digest in {
            BASE_PRODUCT: BASE_PRODUCT_SHA,
            BASE_RECEIPT: BASE_RECEIPT_SHA,
            FIRST_RED: FIRST_RED_SHA,
            CORRECTION: CORRECTION_SHA}.items():
        require(path.is_file() and sha(path) == digest,
                f"VM_DIRMISS detail authority drift: {path}")
    baseline = json.loads(BASE_RECEIPT.read_text(encoding="utf-8"))
    first_red = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    correction = json.loads(CORRECTION.read_text(encoding="utf-8"))
    require(baseline.get("link_number") == 44
            and baseline["product_identity"]["product"]["sha256"] ==
                BASE_PRODUCT_SHA,
            "Link-44 rollback line is not authoritative")
    require(first_red["budgets"]["line_1_product_first_reds"]["after"] ==
            "2/3"
            and first_red["budgets"]["completed_latency_measurements"]["after"]
                == "0/2",
            "dynamic top-level budget authority drift")
    require(correction["budgets"]["class_b_diagnostic_cycles"] ==
            "3/3 consumed; no fourth cycle",
            "Class-B exhaustion correction is not authoritative")
    return {
        "link44_rollback_product": {**bind(BASE_PRODUCT),
                                    "status": "untouched"},
        "link44_structural_authority": bind(BASE_RECEIPT),
        "dynamic_top_level_hardware_first_red": bind(FIRST_RED),
        "class_b_interpretation_correction": bind(CORRECTION),
        "approved_contract": bind(CONTRACT),
        "approved_review_record": bind(REVIEW),
        "canonical_product_profile": PROFILE.check(),
        "driver": bind(Path(__file__)),
    }


def run_probe() -> dict[str, Any]:
    require(not OUT.exists() and not INTERNAL.exists() and not RECEIPT.exists(),
            "VM_DIRMISS detail WPLTO probe is one-shot and already consumed")
    old = {
        "out": LINK44.OUT, "receipt": LINK44.RECEIPT,
        "number": LINK44.LINK_NUMBER, "baseline": LINK44.BASELINE,
        "baseline_sha": LINK44.BASELINE_SHA,
        "baseline_receipt": LINK44.BASELINE_RECEIPT,
        "baseline_receipt_sha": LINK44.BASELINE_RECEIPT_SHA,
        "wplto": LINK44.WPLTO, "wplto_sha": LINK44.WPLTO_SHA,
        "hardware_first_red": LINK44.HARDWARE_FIRST_RED,
        "prerequisites": LINK44.prerequisites,
        "prelink": LINK44.BASE_LINK.fresh_prelink_gates,
        "replacement": LINK44.BASE_LINK.replacement_gates,
        "single_link": LINK44.P.single_link,
    }

    def prelink() -> dict[str, Any]:
        value = old["prelink"]()
        value["vm_dirmiss_detail_source"] = source_gate(
            VM.read_text(encoding="utf-8"), VM_H.read_text(encoding="utf-8"),
            EVAL.read_text(encoding="utf-8"),
            COMPILE.read_text(encoding="utf-8"),
            INTERRUPT.read_text(encoding="utf-8"),
            ERROR_OVERLAY.read_text(encoding="utf-8"), mutations=True)
        value["vm_dirmiss_detail_semantics"] = semantic_fixture()
        return value

    def replacement(product: Path, elf: Path,
                    host: dict[str, Any]) -> dict[str, Any]:
        value = old["replacement"](product, elf, host)
        value["vm_dirmiss_detail"] = linked_gate(elf)
        return value

    def single_link(*args: Any, **kwargs: Any) -> Any:
        lines = tuple(line for line in kwargs.get("extra_contract_lines", ())
                      if not line.startswith(("mode=", "source_baseline=",
                                              "promotable=",
                                              "delegation_class=")))
        kwargs["extra_contract_lines"] = (
            "mode=link44-vm-dirmiss-detail-product-shaped-wplto",
            "source_baseline=link44-c2-lite-v6-bank2-target-stage-replay",
            "promotable=no-capacity-placement-probe-only",
            "delegation_class=C-approved-contract-and-wplto-only",
            "error_detail_transport=ordinary-obj-result-plus-vm-status",
            "persistent_detail_storage=existing-pending-symbol-only",
            "class_b_budget=3-of-3-exhausted",
            "line1_first_red_budget=2-of-3-consumed",
            "latency_measurement_attempts=0-of-2-consumed",
            *lines)
        return old["single_link"](*args, **kwargs)

    try:
        LINK44.OUT = OUT
        LINK44.RECEIPT = INTERNAL
        LINK44.LINK_NUMBER = 44
        LINK44.BASELINE = BASE_PRODUCT
        LINK44.BASELINE_SHA = BASE_PRODUCT_SHA
        LINK44.BASELINE_RECEIPT = BASE_RECEIPT
        LINK44.BASELINE_RECEIPT_SHA = BASE_RECEIPT_SHA
        LINK44.WPLTO = BASE_RECEIPT
        LINK44.WPLTO_SHA = BASE_RECEIPT_SHA
        LINK44.HARDWARE_FIRST_RED = FIRST_RED
        LINK44.prerequisites = prerequisites
        LINK44.BASE_LINK.fresh_prelink_gates = prelink
        LINK44.BASE_LINK.replacement_gates = replacement
        LINK44.P.single_link = single_link
        result = LINK44.main()
    finally:
        LINK44.OUT = old["out"]
        LINK44.RECEIPT = old["receipt"]
        LINK44.LINK_NUMBER = old["number"]
        LINK44.BASELINE = old["baseline"]
        LINK44.BASELINE_SHA = old["baseline_sha"]
        LINK44.BASELINE_RECEIPT = old["baseline_receipt"]
        LINK44.BASELINE_RECEIPT_SHA = old["baseline_receipt_sha"]
        LINK44.WPLTO = old["wplto"]
        LINK44.WPLTO_SHA = old["wplto_sha"]
        LINK44.HARDWARE_FIRST_RED = old["hardware_first_red"]
        LINK44.prerequisites = old["prerequisites"]
        LINK44.BASE_LINK.fresh_prelink_gates = old["prelink"]
        LINK44.BASE_LINK.replacement_gates = old["replacement"]
        LINK44.P.single_link = old["single_link"]

    if result != 0:
        value = {
            "format": "lisp65-c2-lite-v6-vm-dirmiss-detail-wplto-first-red-v1",
            "recorded_on": "2026-07-22",
            "status": "FIRST RED: VM_DIRMISS detail WPLTO stopped",
            "promotable": False,
            "internal_receipt": bind(INTERNAL) if INTERNAL.is_file() else None,
            "link44_rollback": {**bind(BASE_PRODUCT), "status": "untouched"},
            "execution_accounting": {"whole_program_lto_closure_links": 1,
                                      "promotable_product_links": 0,
                                      "hardware_runs": 0},
            "next_gate": "stop; return the measured red to Class-C review",
        }
        write(RECEIPT, value)
        os.chmod(RECEIPT, 0o444)
        return value

    internal_value = json.loads(INTERNAL.read_text(encoding="utf-8"))
    structure_path = ROOT / internal_value["structural_report"]["path"]
    structure = json.loads(structure_path.read_text(encoding="utf-8"))
    linked = structure["fresh_replacement_gates"]["vm_dirmiss_detail"]
    capacity = capacity_gate(structure)
    require(internal_value["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
            and linked["status"].startswith("passed-"),
            "VM_DIRMISS detail closure did not finish fully green")
    product = ROOT / internal_value["product_identity"]["product"]["path"]
    value = {
        "format": "lisp65-c2-lite-v6-vm-dirmiss-detail-wplto-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-product-shaped-WPLTO-no-hardware-no-product-candidate",
        "promotable": False,
        "claim_limit": "Contract, mutations, placement and WPLTO capacity only; no product-link or hardware claim.",
        "authority": prerequisites(),
        "source_gate": source_gate(
            VM.read_text(encoding="utf-8"), VM_H.read_text(encoding="utf-8"),
            EVAL.read_text(encoding="utf-8"),
            COMPILE.read_text(encoding="utf-8"),
            INTERRUPT.read_text(encoding="utf-8"),
            ERROR_OVERLAY.read_text(encoding="utf-8"), mutations=True),
        "semantic_fixture": semantic_fixture(),
        "linked_seam": linked,
        "capacity": capacity,
        "product_shaped_identity": {**bind(product),
                                    "nonpromotable": True},
        "internal_structural_receipt": bind(INTERNAL),
        "structural_report": bind(structure_path),
        "link44_rollback": {**bind(BASE_PRODUCT), "status": "untouched"},
        "execution_accounting": {"whole_program_lto_closure_links": 1,
                                  "promotable_product_links": 0,
                                  "hardware_runs": 0},
        "counters": {"class_b": "3/3 exhausted",
                     "line1_product_first_reds": "2/3",
                     "completed_latency_measurements": "0/2"},
        "next_gate": "separate Class-C authorization for one promotable successor link",
    }
    write(RECEIPT, value)
    os.chmod(RECEIPT, 0o444)
    return value


def selftest() -> dict[str, Any]:
    value = source_gate(
        VM.read_text(encoding="utf-8"), VM_H.read_text(encoding="utf-8"),
        EVAL.read_text(encoding="utf-8"),
        COMPILE.read_text(encoding="utf-8"),
        INTERRUPT.read_text(encoding="utf-8"),
        ERROR_OVERLAY.read_text(encoding="utf-8"), mutations=True)
    require(len(value["mutations_rejected"]) == 15,
            "VM_DIRMISS detail mutation count drift")
    semantic_fixture()
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("selftest", "probe"))
    args = parser.parse_args()
    try:
        value = selftest() if args.stage == "selftest" else run_probe()
        print("c2-lite-v6-link44-dirmiss-detail: " + value["status"])
        return 2 if value["status"].startswith("FIRST RED") else 0
    except (GateError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-link44-dirmiss-detail: FAIL: " + str(error),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
