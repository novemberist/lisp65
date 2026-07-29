#!/usr/bin/env python3
"""Product-shaped WPLTO probe for the approved BCODE ordinal renderer.

The closure is deliberately nonpromotable.  It starts from immutable Link 45,
builds the complete current C2-lite product once, and qualifies the closed
NIL/SYMI/BCODE detail union, the target L65E leaf, every resident wall, and the
98-byte Session aggregate before a successor product link may be attempted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_bank2_target_stage_successor_link as LINK44  # noqa: E402
import c2_lite_v6_link44_dirmiss_e000_eviction_artifact_replay as DETAIL  # noqa: E402
import c2_lite_v6_roots_fronts_product_profile as PROFILE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASE_DIR = ROOT / (
    "build/c2.2/substitution/"
    "product-link-45-c2-lite-v6-dirmiss-detail-e000-evacuation")
BASE_PRODUCT = BASE_DIR / "lisp65-c2-substitution-linked.prg"
BASE_RECEIPT = EVIDENCE / (
    "c2.2-product-link45-c2-lite-v6-dirmiss-detail-e000-evacuation-"
    "structural-receipt.json")
HARDWARE_FIRST_RED = EVIDENCE / (
    "c2.2-product-link45-dirmiss-detail-hardware-first-red.json")
CONTRACT = ROOT / "config/c2-vm-dirmiss-bcode-ordinal-contract.json"
RENDERER_SHAPE_CONTRACT = (
    ROOT / "config/c2-vm-badopcode-detail-contract.json")
REVIEW = ROOT / "docs/planning/c2.2-link44-permanent-dirmiss-diagnostic-review.md"
EVAL = ROOT / "src/eval.c"
RUNTIME = ROOT / "src/c2_product_runtime.c"
INTERRUPT_H = ROOT / "src/interrupt.h"
OVERLAY_C = ROOT / "src/error_overlay.c"
OVERLAY_H = ROOT / "src/error_overlay.h"
OVERLAY_S = ROOT / "src/l65e_bcode_ordinal.s"
SMOKE = ROOT / "tools/host-lisp/error_overlay_smoke.py"
OUT = ROOT / "build/c2.2/substitution/link45-bcode-ordinal-wplto"
INTERNAL = EVIDENCE / "c2.2-link45-bcode-ordinal-wplto-internal.json"
RECEIPT = EVIDENCE / "c2.2-link45-bcode-ordinal-wplto-receipt.json"

BASE_PRODUCT_SHA = (
    "13aca84db1dda3e109ed4f578b9027e731df25c8d99c97a04c4b6fc95f5af6c2")
BASE_RECEIPT_SHA = (
    "906648cc9eacbd748c61b444af45906425047dc50de913d49773e28b1c869599")
HARDWARE_FIRST_RED_SHA = (
    "5c31aece9b7e7818ec55c931a55ab9b1d80353fac4ff658533fa37e3786af7f6")


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"evidence absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def _render_model(code: int, detail: int, *, bcode_symname: bool = False,
                  bcode_under_28: bool = False, symi_under_41: bool = False,
                  accept_foreign: bool = False, digits: int = 3,
                  object_digits: bool = False, drop_suffix: bool = False,
                  nil_suffix: bool = False) -> str | None:
    raw = detail & 0xffff
    is_bcode = raw >= 0xc000 and raw < 0xe000 and not raw & 1
    is_symi = raw >= 0xe000 and not raw & 1
    is_fix = bool(raw & 1)
    if raw == 0:
        base = "vm: undefined function" if code == 41 else "vm: bad bytecode"
        return base + (" #000" if nil_suffix else "")
    if code == 41:
        if is_symi and not symi_under_41:
            return None
        if not is_bcode and not (is_symi and symi_under_41) and not accept_foreign:
            return None
        base = "vm: undefined function" if code == 41 else "vm: bad bytecode"
        if drop_suffix:
            return base
        if bcode_symname:
            return base + " guessed-symbol"
        value = raw if object_digits else (((raw >> 1) - 0x6000) & 0xfff)
        return base + " #" + f"{value:0{digits}x}"[-digits:]
    if code == 28:
        if is_bcode and not bcode_under_28:
            return None
        return "undefined function: symbol"
    return None


def semantic_mutations() -> dict[str, str]:
    require(_render_model(41, 0xc000) == "vm: undefined function #000"
            and _render_model(41, 0xdffe) == "vm: undefined function #fff"
            and _render_model(41, 0) == "vm: undefined function"
            and _render_model(28, 0xe00e) == "undefined function: symbol",
            "closed detail-union oracle drift")
    trials = {
        "bcode-routed-through-symname": {"bcode_symname": True},
        "bcode-accepted-under-code28": {"bcode_under_28": True},
        "symi-accepted-under-code41": {"symi_under_41": True},
        "foreign-positive-even-accepted": {"accept_foreign": True},
        "ordinal-truncated-to-two-digits": {"digits": 2},
        "ordinal-widened-to-object-value": {"object_digits": True,
                                               "digits": 4},
        "bcode-suffix-dropped": {"drop_suffix": True},
        "nil-fabricated-suffix": {"nil_suffix": True},
    }
    rejected: dict[str, str] = {}
    for name, changes in trials.items():
        if name == "bcode-accepted-under-code28":
            survived = _render_model(28, 0xc4aa, **changes) is not None
        elif name == "symi-accepted-under-code41":
            survived = _render_model(41, 0xe00e, **changes) is not None
        elif name == "foreign-positive-even-accepted":
            survived = _render_model(41, 2, **changes) is not None
        elif name == "nil-fabricated-suffix":
            survived = _render_model(41, 0, **changes) != \
                "vm: undefined function"
        else:
            survived = _render_model(41, 0xc54a, **changes) != \
                "vm: undefined function #2a5"
        require(survived, f"mutation fixture is ineffective: {name}")
        rejected[name] = "rejected-by-canonical-closed-union-oracle"
    return rejected


def source_gate(*, run_smoke: bool) -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    evaluation = EVAL.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    interrupt_h = INTERRUPT_H.read_text(encoding="utf-8")
    overlay_c = OVERLAY_C.read_text(encoding="utf-8")
    overlay_h = OVERLAY_H.read_text(encoding="utf-8")
    overlay_s = OVERLAY_S.read_text(encoding="utf-8")
    require(contract["schema"] ==
            "lisp65.c2.vm-dirmiss-bcode-ordinal-contract.v1"
            and contract["capacity"]["l65e_slice_cap_bytes"] == 1320,
            "BCODE ordinal contract or dedicated L65E cap drift")
    require(evaluation.count(
                "code == LISP65_ERR_VM_UNDEFINED_FUNCTION && IS_SYMI(detail)")
            == 1
            and evaluation.count(
                "code == LISP65_ERR_VM_UNDEFINED_FUNCTION\n"
                 "                 && IS_BCODE(detail)") == 1
            and "code == LISP65_ERR_C2_NESTING_DEPTH" not in evaluation
            and evaluation.count("lisp_abort_detail(code, detail);") == 1,
            "terminal VM detail dispatch drift")
    require("code == LISP65_ERR_VM_BAD_BYTECODE && IS_FIX(detail)"
            not in evaluation
            and "C2AW_FAILURE" not in runtime
            and "return (obj)main;" not in runtime
            and "vm_status = VM_C2_NESTING_DEPTH;" not in runtime
            and runtime.count(
                "lisp_abort_detail(LISP65_ERR_C2_NESTING_DEPTH, MKFIX(5));")
                == 1
            and "if (C2AW_TRANSIENT(w)"
                " && depth >= C2D_MAX_TRANSIENT_DEPTH)" in runtime
            and "if (!c2_transient_fronts(&depth, &high_entries, &high_res,"
                in runtime
            and "vm_badopcode_detail(" not in runtime,
            "retired BADOPCODE sister seam drift")
    require("#define lisp_abort_detail(code, detail)" in interrupt_h
            and "lisp_abort_symbol((code), (detail))" in interrupt_h,
            "zero-byte terminal detail alias drift")
    require("obj detail;" in overlay_h
            and "context.detail = detail;" in overlay_c
            and "l65e_emit_bcode_ordinal(context->detail);" in overlay_c,
            "closed detail union or host oracle drift")
    for token in (
            ".globl\tlisp65_error_overlay_entry",
            ".type\tlisp65_error_overlay_entry,@function",
            ".size\tlisp65_error_overlay_entry,",
            ".globl\tl65e_emit_bcode_ordinal",
            ".type\tl65e_emit_bcode_ordinal,@function",
            ".size\tl65e_emit_bcode_ordinal,",
            "cpx\t#41", "cpx\t#28", "cpx\t#49", "cpx\t#60",
            "cmp\t#$c0", "cmp\t#$e0", "jsr\tsymname",
            "jsr\tl65e_emit_bcode_ordinal"):
        require(token in overlay_s, f"target renderer contract drift: {token}")
    require(overlay_s.count("jsr\temit") == 7
            and overlay_s.count("jmp\temit") == 2,
            "target renderer emit inventory drift")
    mutations = semantic_mutations()
    smoke: dict[str, Any] | None = None
    if run_smoke:
        shape_contract = json.loads(
            RENDERER_SHAPE_CONTRACT.read_text(encoding="utf-8"))
        expected = shape_contract["renderer"]["l65e_expected_shape"]
        code_bytes = (
            expected["entry_bytes"] + expected["bcode_ordinal_leaf_bytes"])
        smoke_shape = (
            f"code={code_bytes} table={expected['table_bytes']} "
            f"total={expected['slice_bytes']} "
            f"headroom="
            f"{expected['slice_cap_bytes'] - expected['slice_bytes']}")
        completed = subprocess.run(
            ["python3", str(SMOKE)], cwd=ROOT, check=True,
            capture_output=True, text=True)
        require(smoke_shape in completed.stdout
                and "bcode12-boundaries" in completed.stdout,
                "host/MOS L65E smoke did not bind expected semantics/capacity")
        smoke = {
            "status": "passed",
            "canonical_shape": smoke_shape,
            "stdout": completed.stdout.splitlines(),
        }
    return {
        "status": "passed-closed-NIL-SYMI-BCODE-one-cell-render-contract",
        "detail_domains": ["NIL", "SYMI", "BCODE"],
        "bcode_syntax": " #xxx",
        "boundary_examples": {"0": "#000", "4095": "#fff"},
        "new_cells": 0, "new_bss_bytes": 0, "new_gc_roots": 0,
        "dispatch_ownership": {
            "undefined_function": "generic vm_check_status",
            "c2_nesting_depth":
                "cold terminal lisp_abort_detail with exact Fixnum-5 detail",
            "append_badopcode": "status-only; internal detail scaffold retired",
        },
        "mutations_rejected": mutations,
        "host_and_non_lto_mos_smoke": smoke,
    }


def linked_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(
        elf, llvm_readobj=LINK44.P.TOOLCHAIN / "llvm-readobj")
    expected = json.loads(
        RENDERER_SHAPE_CONTRACT.read_text(encoding="utf-8")
    )["renderer"]["l65e_expected_shape"]
    entry = truth.symbol("lisp65_error_overlay_entry")
    ordinal = truth.symbol("l65e_emit_bcode_ordinal")
    table = truth.symbol("l65e_table")
    require(entry.symbol_type == ordinal.symbol_type == "Function"
            and entry.section == ordinal.section == ".lisp65_rt_l65e"
            and table.section == ".lisp65_rt_l65e"
            and (entry.bytes, ordinal.bytes, table.bytes) ==
                (expected["entry_bytes"],
                 expected["bcode_ordinal_leaf_bytes"],
                 expected["table_bytes"]),
            "linked target renderer citizenship/shape drift")
    sections = LINK44.P.section_table(elf)
    total = sections[".lisp65_rt_l65e"]["bytes"]
    require(total == expected["slice_bytes"]
            and total <= expected["slice_cap_bytes"],
            "dedicated linked L65E cap red: "
            f"{total}/{expected['slice_cap_bytes']}")
    entry_relocs = [row for row in truth.relocations
                    if row.source_section_index == entry.section_index
                    and entry.value <= row.offset < entry.value + entry.bytes]
    ordinal_relocs = [row for row in truth.relocations
                      if row.source_section_index == ordinal.section_index
                      and ordinal.value <= row.offset
                      < ordinal.value + ordinal.bytes]
    entry_targets = [row.target for row in entry_relocs]
    ordinal_targets = [row.target for row in ordinal_relocs]
    require("symname" in entry_targets
            and "l65e_emit_bcode_ordinal" in entry_targets
            and "l65e_emit_fixnum_coordinate" not in entry_targets
            and "symname" not in ordinal_targets
            and ordinal_targets.count("emit") == 5,
            "linked BCODE/SYMI output edge inventory drift")
    detail = DETAIL.detail_gate(truth)
    return {
        "status": "passed-linked-target-renderer-and-one-detail-seam",
        "entry": {"address": entry.value, "bytes": entry.bytes,
                  "section": entry.section},
        "ordinal_leaf": {"address": ordinal.value, "bytes": ordinal.bytes,
                          "section": ordinal.section},
        "table": {"address": table.value, "bytes": table.bytes,
                  "section": table.section},
        "slice": {"bytes": total,
                  "cap_bytes": expected["slice_cap_bytes"],
                  "headroom_bytes": expected["slice_cap_bytes"] - total},
        "entry_targets": sorted(set(entry_targets)),
        "ordinal_emit_calls": ordinal_targets.count("emit"),
        "ordinal_symname_calls": ordinal_targets.count("symname"),
        "canonical_detail_seam": detail,
    }


def prerequisites() -> dict[str, Any]:
    for path, digest in {
            BASE_PRODUCT: BASE_PRODUCT_SHA,
            BASE_RECEIPT: BASE_RECEIPT_SHA,
            HARDWARE_FIRST_RED: HARDWARE_FIRST_RED_SHA}.items():
        require(path.is_file() and sha(path) == digest,
                f"Link-45 BCODE authority drift: {path}")
    baseline = json.loads(BASE_RECEIPT.read_text(encoding="utf-8"))
    first_red = json.loads(HARDWARE_FIRST_RED.read_text(encoding="utf-8"))
    require(baseline["link_number"] == 45
            and baseline["product_identity"]["product"]["sha256"] ==
                BASE_PRODUCT_SHA,
            "Link-45 rollback candidate is not authoritative")
    require(first_red["counters"]["line1_product_first_reds"] == "2/3"
            and first_red["counters"]["completed_latency_measurements"] ==
                "0/2",
            "hardware budget authority drift")
    return {
        "link45_rollback_product": {**bind(BASE_PRODUCT), "status": "untouched"},
        "link45_structural_authority": bind(BASE_RECEIPT),
        "link45_non_symbol_hardware_first_red": bind(HARDWARE_FIRST_RED),
        "approved_contract": bind(CONTRACT),
        "approved_review": bind(REVIEW),
        "canonical_product_profile": PROFILE.check(),
        "driver": bind(Path(__file__)),
    }


def run_probe() -> dict[str, Any]:
    require(not OUT.exists() and not INTERNAL.exists() and not RECEIPT.exists(),
            "BCODE ordinal WPLTO probe is one-shot and already consumed")
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
        value["bcode_ordinal_renderer_source"] = source_gate(run_smoke=True)
        return value

    def replacement(product: Path, elf: Path,
                    host: dict[str, Any]) -> dict[str, Any]:
        value = old["replacement"](product, elf, host)
        value["bcode_ordinal_renderer"] = linked_gate(elf)
        walls = value["walls"]
        capacity = value["capacity"]
        require(walls["ordinary_bank0_bss_headroom_bytes"] == 86
                and walls["e000_headroom_bytes"] >= 115
                and all(int(walls[name]) >= 0 for name in (
                    "bank0_text_headroom_bytes",
                    "fixed_hot_block_headroom_bytes",
                    "resident_island_headroom_bytes")),
                f"BCODE ordinal product wall red: {walls}")
        require(capacity["session_family_bytes"] <= 65536
                and capacity["session_family_headroom_bytes"] >= 0,
                f"BCODE ordinal Session aggregate red: {capacity}")
        return value

    def single_link(*args: Any, **kwargs: Any) -> Any:
        lines = tuple(line for line in kwargs.get("extra_contract_lines", ())
                      if not line.startswith(("mode=", "source_baseline=",
                                              "promotable=",)))
        kwargs["extra_contract_lines"] = (
            "mode=link45-bcode-ordinal-product-shaped-wplto",
            "source_baseline=link45-dirmiss-detail-e000-evacuation",
            "promotable=no-capacity-placement-probe-only",
            "detail_union=NIL-SYMI-BCODE-existing-cell",
            "bcode_rendering=raw-12-bit-ordinal-three-lower-hex",
            "line1_first_red_budget=2-of-3-consumed",
            "latency_measurement_attempts=0-of-2-consumed",
            *lines)
        return old["single_link"](*args, **kwargs)

    try:
        LINK44.OUT = OUT
        LINK44.RECEIPT = INTERNAL
        LINK44.LINK_NUMBER = 45
        LINK44.BASELINE = BASE_PRODUCT
        LINK44.BASELINE_SHA = BASE_PRODUCT_SHA
        LINK44.BASELINE_RECEIPT = BASE_RECEIPT
        LINK44.BASELINE_RECEIPT_SHA = BASE_RECEIPT_SHA
        LINK44.WPLTO = BASE_RECEIPT
        LINK44.WPLTO_SHA = BASE_RECEIPT_SHA
        LINK44.HARDWARE_FIRST_RED = HARDWARE_FIRST_RED
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

    internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
    if result != 0:
        value = {
            "format": "lisp65-c2-lite-v6-bcode-ordinal-wplto-first-red-v1",
            "recorded_on": "2026-07-22",
            "status": "FIRST RED: BCODE ordinal WPLTO stopped",
            "promotable": False,
            "internal_receipt": bind(INTERNAL),
            "link45_rollback": {**bind(BASE_PRODUCT), "status": "untouched"},
            "execution_accounting": {"whole_program_lto_closure_links": 1,
                                     "promotable_product_links": 0,
                                     "hardware_runs": 0},
            "next_gate": "stop; return measured First Red to Class-C review",
        }
        write(RECEIPT, value)
        os.chmod(RECEIPT, 0o444)
        return value

    structure_path = ROOT / internal["structural_report"]["path"]
    structure = json.loads(structure_path.read_text(encoding="utf-8"))
    gates = structure["fresh_replacement_gates"]
    renderer = gates["bcode_ordinal_renderer"]
    require(internal["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
            and renderer["status"].startswith("passed-"),
            "BCODE ordinal WPLTO did not complete fully green")
    product = ROOT / internal["product_identity"]["product"]["path"]
    value = {
        "format": "lisp65-c2-lite-v6-bcode-ordinal-wplto-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-product-shaped-WPLTO-no-hardware-no-product-candidate",
        "promotable": False,
        "claim_limit": "Host semantics, mutations, WPLTO placement and capacity only; hardware not run.",
        "authority": prerequisites(),
        "source_gate": source_gate(run_smoke=False),
        "linked_renderer": renderer,
        "walls": gates["walls"],
        "capacity": gates["capacity"],
        "product_shaped_identity": {**bind(product), "nonpromotable": True},
        "internal_structural_receipt": bind(INTERNAL),
        "structural_report": bind(structure_path),
        "link45_rollback": {**bind(BASE_PRODUCT), "status": "untouched"},
        "execution_accounting": {"whole_program_lto_closure_links": 1,
                                 "promotable_product_links": 0,
                                 "hardware_runs": 0},
        "counters": {"class_b": "3/3 exhausted",
                     "line1_product_first_reds": "2/3",
                     "completed_latency_measurements": "0/2"},
        "next_gate": "approved successor product link",
    }
    write(RECEIPT, value)
    os.chmod(RECEIPT, 0o444)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("selftest", "probe"))
    args = parser.parse_args()
    try:
        value = (source_gate(run_smoke=True) if args.stage == "selftest"
                 else run_probe())
        print("c2-lite-v6-link45-bcode-ordinal: " + value["status"])
        return 2 if value["status"].startswith("FIRST RED") else 0
    except (GateError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print("c2-lite-v6-link45-bcode-ordinal: FAIL: " + str(error),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
