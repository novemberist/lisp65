#!/usr/bin/env python3
"""Class-B Link-44 dynamic lookup latch: WPLTO, then one diagnostic link.

The diagnostic is deliberately not a product successor.  It reuses four
post-failure VM header-work bytes, records the first VM_DIRMISS lookup site,
and lets the existing numeric error overlay name an interned-symbol miss.
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
BASE_PRODUCT_SHA = (
    "db3112e6503ca96d572cccb7a399c91eb06028faeaa05e595454fb9502b7f926")
BASE_RECEIPT_SHA = (
    "f358d14604eac270d78e407dec9ecf43559267b1344d371ee92fb95189504ede")
FIRST_RED_SHA = (
    "affae865a776faf2cbd69d5df929d488a3ca2021eb0861d0aed1c9c0bcfe2332")
PROFILE_SHA = (
    "05a6db5519e8d023bac3bbaae5770efa909f66f26204a374d33330aff09c6b53")
BASE_FEATURES = tuple(PROFILE.value()["feature_defines"])
FEATURES = (*BASE_FEATURES, DEFINE)

PROBE_OUT = ROOT / (
    "build/c2.2/substitution/link44-dynamic-lookup-latch-wplto")
PROBE_INTERNAL = EVIDENCE / (
    "c2.2-link44-dynamic-lookup-latch-wplto-internal-structural.json")
PROBE_RECEIPT = EVIDENCE / (
    "c2.2-link44-dynamic-lookup-latch-wplto-receipt.json")
LINK_OUT = ROOT / (
    "build/c2.2/substitution/link44-dynamic-lookup-latch-diagnostic")
LINK_INTERNAL = EVIDENCE / (
    "c2.2-link44-dynamic-lookup-latch-diagnostic-internal-structural.json")
LINK_RECEIPT = EVIDENCE / (
    "c2.2-link44-dynamic-lookup-latch-diagnostic-link-receipt.json")


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


def source_gate(vm: str, vm_h: str, evaluation: str,
                *, mutations: bool = False) -> dict[str, Any]:
    hooks = (
        "VM_DIRMISS_LATCH(\n            (di >= 0 && di < 4096) "
        "? MK_BCODE((uint16_t)di) : NIL, 1u);",
        "VM_DIRMISS_LATCH(sym, 2u); vm_status = VM_DIRMISS; return 0;",
        "VM_DIRMISS_LATCH(sym, 3u); vm_status = VM_DIRMISS; goto done;",
        "VM_DIRMISS_LATCH(sym, 4u);",
    )
    required_vm = (
        "#ifdef LISP65_C2_DYNAMIC_LOOKUP_DIAGNOSTIC",
        "static C2_DYNAMIC_DIAG_FN void\nvm_dirmiss_latch",
        "vmr_hdrlen = (uint16_t)lookup;",
        "vmr_poff = (uint16_t)(site | 0x8200u);",
        "vm_dirmiss_latched_lookup(void) { return (obj)vmr_hdrlen; }",
        "vm_dirmiss_latched_context(void) { return vmr_poff; }",
        'section(".lisp65_resident_island")',
        *hooks,
    )
    required_h = (
        "obj vm_dirmiss_latched_lookup(void);",
        "uint16_t vm_dirmiss_latched_context(void);",
    )
    required_eval = (
        "vm_status == VM_DIRMISS\n            ? vm_dirmiss_latched_lookup() : NIL;",
        "code == LISP65_ERR_VM_UNDEFINED_FUNCTION && IS_SYMI(lookup)",
        "lisp_abort_symbol(LISP65_ERR_UNDEFINED_FUNCTION, lookup);",
    )
    for token in required_vm:
        require(token in vm, f"dynamic lookup VM source token absent: {token}")
    for token in required_h:
        require(token in vm_h, f"dynamic lookup header token absent: {token}")
    for token in required_eval:
        require(token in evaluation,
                f"dynamic lookup numeric-render token absent: {token}")
    require(vm.count("VM_DIRMISS_LATCH(") == 6,
            "dynamic lookup latch must have two guarded macro forms plus four callsites")
    require(vm.count("vmr_hdrlen = (uint16_t)lookup;") == 1
            and vm.count("vmr_poff = (uint16_t)(site | 0x8200u);") == 1,
            "diagnostic tuple is not written at one canonical site")
    require("static obj vm_dirmiss" not in vm
            and "static uint16_t vm_dirmiss" not in vm,
            "diagnostic allocated a second static state object")
    require("undefined function:" not in "\n".join(
        line for line in evaluation.splitlines()
        if "LISP65_C2_DYNAMIC_LOOKUP_DIAGNOSTIC" in line),
        "diagnostic branch added a private error string")

    rejected: dict[str, str] = {}
    if mutations:
        candidates: dict[str, tuple[str, str, str]] = {}
        for index, hook in enumerate(hooks, 1):
            candidates[f"missing-site-{index}"] = (
                vm.replace(hook, "/* mutated missing latch */", 1),
                vm_h, evaluation)
        candidates.update({
            "wrong-family": (
                vm.replace("site | 0x8200u", "site | 0x8100u", 1),
                vm_h, evaluation),
            "second-state": (
                vm.replace("static C2_DYNAMIC_DIAG_FN void",
                           "static obj vm_dirmiss_second_truth;\n"
                           "static C2_DYNAMIC_DIAG_FN void", 1),
                vm_h, evaluation),
            "symbol-render-removed": (
                vm, vm_h, evaluation.replace(
                    "lisp_abort_symbol(LISP65_ERR_UNDEFINED_FUNCTION, lookup);",
                    "lisp_abort_code(code);", 1)),
            "raw-context-accessor-removed": (
                vm, vm_h.replace(
                    "uint16_t vm_dirmiss_latched_context(void);", "", 1),
                evaluation),
        })
        for name, parts in candidates.items():
            try:
                source_gate(*parts, mutations=False)
            except GateError:
                rejected[name] = "rejected"
            else:
                raise GateError(
                    f"dynamic lookup source mutation accepted: {name}")
    return {
        "status": "passed-four-site-four-byte-dirmiss-latch-source-gate",
        "state_storage": ["vmr_hdrlen", "vmr_poff"],
        "new_state_bytes": 0,
        "site_map": {
            "1": "vm_run_dir-entry-length",
            "2": "OP_CLOSURE-target",
            "3": "OP_CALL-target",
            "4": "OP_TAILCALL-target",
        },
        "context_layout": {
            "lookup": "vmr_hdrlen little-endian raw obj",
            "site": "vmr_poff low byte",
            "valid_and_family": "vmr_poff high byte = 0x80 | Session(2)",
            "generation": "not stored; four-byte tuple prioritizes family",
        },
        "numeric_render": "existing undefined-function code 28 plus SYMI",
        "new_user_visible_string_bytes": 0,
        "mutations_rejected": rejected,
    }


def truth(path: Path) -> ElfTruth:
    return ElfTruth.read(path, llvm_readobj=LINK44.P.TOOLCHAIN / "llvm-readobj")


def diagnostic_elf_gate(elf: Path) -> dict[str, Any]:
    current = truth(elf)
    baseline = truth(BASE_ELF)
    reused: dict[str, Any] = {}
    for name in ("vmr_hdrlen", "vmr_poff"):
        before = baseline.symbol(name)
        after = current.symbol(name)
        require((after.value, after.bytes, after.section) ==
                (before.value, before.bytes, before.section),
                f"diagnostic state storage moved or resized: {name}")
        reused[name] = {
            "address": f"0x{after.value:04x}", "bytes": after.bytes,
            "section": after.section, "same_as_link44": True,
        }
    functions: dict[str, Any] = {}
    for name in ("vm_dirmiss_latch", "vm_dirmiss_latched_lookup",
                 "vm_dirmiss_latched_context"):
        symbol = current.symbol(name)
        require(symbol.bytes > 0 and symbol.symbol_type == "Function"
                and symbol.section == ".lisp65_resident_island",
                f"diagnostic helper is not a sized resident-Island function: {name}")
        functions[name] = {
            "address": f"0x{symbol.value:04x}", "bytes": symbol.bytes,
            "section": symbol.section,
        }
    return {
        "status": "passed-linked-four-byte-latch-and-cold-helper-placement",
        "reused_state": reused,
        "new_bss_bytes": 0,
        "helpers": functions,
        "helper_bytes": sum(row["bytes"] for row in functions.values()),
        "raw_jtag_context_available": True,
        "symbolic_numeric_render_available": True,
    }


def baseline_report() -> dict[str, Any]:
    receipt = json.loads(BASE_RECEIPT.read_text(encoding="utf-8"))
    return json.loads((ROOT / receipt["structural_report"]["path"])
                      .read_text(encoding="utf-8"))


def capacity_gate(structure: dict[str, Any]) -> dict[str, Any]:
    before = baseline_report()["fresh_replacement_gates"]
    after = structure["fresh_replacement_gates"]
    old_walls = before["walls"]
    walls = after["walls"]
    require(walls["ordinary_bank0_bss_headroom_bytes"] ==
            old_walls["ordinary_bank0_bss_headroom_bytes"],
            "diagnostic latch consumed ordinary BSS")
    require(walls["e000_headroom_bytes"] >= 115,
            "diagnostic latch crossed the restored E000 floor")
    require(all(int(walls[name]) >= 0 for name in (
                "bank0_text_headroom_bytes",
                "fixed_hot_block_headroom_bytes",
                "resident_island_headroom_bytes")),
            "diagnostic latch crossed a resident wall")
    old_capacity = before["capacity"]
    capacity = after["capacity"]
    require(capacity["session_family_bytes"] == 65438
            and capacity["session_family_headroom_bytes"] == 98
            and capacity["session_catalog_records_after"] == 50,
            "diagnostic latch changed the bound Session-family aggregate")
    deltas = {name: int(walls[name]) - int(old_walls[name])
              for name in old_walls}
    return {
        "status": "passed-diagnostic-capacity-without-boundary-change",
        "link44_walls": old_walls,
        "diagnostic_walls": walls,
        "headroom_delta_bytes": deltas,
        "ordinary_bss_delta_bytes": 0,
        "session_family_delta_bytes": 0,
        "session_catalog_delta": 0,
        "e000_floor_bytes": 115,
    }


def prerequisites(stage: str) -> dict[str, Any]:
    for path, digest in {
            BASE_PRODUCT: BASE_PRODUCT_SHA,
            BASE_RECEIPT: BASE_RECEIPT_SHA,
            FIRST_RED: FIRST_RED_SHA,
            PROFILE.PROFILE: PROFILE_SHA}.items():
        require(path.is_file() and sha(path) == digest,
                f"dynamic lookup diagnostic authority drift: {path}")
    baseline = json.loads(BASE_RECEIPT.read_text(encoding="utf-8"))
    first_red = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(baseline.get("status") ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
            and baseline.get("link_number") == 44
            and baseline["product_identity"]["product"]["sha256"] ==
                BASE_PRODUCT_SHA,
            "Link-44 rollback line is not authoritative")
    require(first_red.get("status") ==
            "first-red-product-semantics-review-required"
            and first_red["budgets"]["line_1_product_first_reds"]["after"] ==
                "2/3"
            and first_red["budgets"]["completed_latency_measurements"]
                ["after"] == "0/2",
            "dynamic top-level hardware First Red is not authoritative")
    result = {
        "link44_rollback_product": {**bind(BASE_PRODUCT),
                                    "status": "untouched"},
        "link44_structural_authority": bind(BASE_RECEIPT),
        "dynamic_top_level_hardware_first_red": bind(FIRST_RED),
        "canonical_product_profile": {
            **bind(PROFILE.PROFILE),
            "canonical_features": list(BASE_FEATURES),
            "diagnostic_only_feature": DEFINE,
        },
        "diagnostic_source_contract": source_gate(
            VM.read_text(encoding="utf-8"),
            VM_H.read_text(encoding="utf-8"),
            EVAL.read_text(encoding="utf-8"), mutations=True),
        "driver": bind(Path(__file__)),
    }
    if stage == "link":
        require(PROBE_RECEIPT.is_file(),
                "green dynamic lookup WPLTO receipt absent")
        probe = json.loads(PROBE_RECEIPT.read_text(encoding="utf-8"))
        require(probe.get("status") ==
                "passed-product-shaped-WPLTO-no-hardware-no-product-candidate",
                "dynamic lookup WPLTO probe is not green")
        result["green_diagnostic_wplto"] = bind(PROBE_RECEIPT)
    return result


def stage_paths(stage: str) -> tuple[Path, Path, Path]:
    if stage == "probe":
        return PROBE_OUT, PROBE_INTERNAL, PROBE_RECEIPT
    return LINK_OUT, LINK_INTERNAL, LINK_RECEIPT


def run_stage(stage: str) -> dict[str, Any]:
    out, internal, receipt_path = stage_paths(stage)
    require(stage in ("probe", "link"), "unknown diagnostic stage")
    require(not out.exists() and not internal.exists()
            and not receipt_path.exists(),
            f"dynamic lookup {stage} is one-shot and already consumed")
    if stage == "link":
        require(PROBE_RECEIPT.is_file(), "WPLTO must precede diagnostic link")

    old = {
        "out": LINK44.OUT, "receipt": LINK44.RECEIPT,
        "number": LINK44.LINK_NUMBER, "baseline": LINK44.BASELINE,
        "baseline_sha": LINK44.BASELINE_SHA,
        "baseline_receipt": LINK44.BASELINE_RECEIPT,
        "baseline_receipt_sha": LINK44.BASELINE_RECEIPT_SHA,
        "wplto": LINK44.WPLTO, "wplto_sha": LINK44.WPLTO_SHA,
        "hardware_first_red": LINK44.HARDWARE_FIRST_RED,
        "prerequisites": LINK44.prerequisites,
        "feature_defines": PROFILE.feature_defines,
        "prelink": LINK44.BASE_LINK.fresh_prelink_gates,
        "replacement": LINK44.BASE_LINK.replacement_gates,
        "single_link": LINK44.P.single_link,
    }

    def diagnostic_features() -> tuple[str, ...]:
        return FEATURES

    def prelink() -> dict[str, Any]:
        value = old["prelink"]()
        value["dynamic_lookup_latch_source"] = source_gate(
            VM.read_text(encoding="utf-8"),
            VM_H.read_text(encoding="utf-8"),
            EVAL.read_text(encoding="utf-8"), mutations=True)
        return value

    def replacement(product: Path, elf: Path,
                    host: dict[str, Any]) -> dict[str, Any]:
        value = old["replacement"](product, elf, host)
        value["dynamic_lookup_latch"] = diagnostic_elf_gate(elf)
        return value

    def single_link(*args: Any, **kwargs: Any) -> Any:
        lines = tuple(line for line in kwargs.get("extra_contract_lines", ())
                      if not line.startswith((
                          "mode=", "source_baseline=", "promotable=",
                          "diagnostic_define=", "delegation_class=",
                          "delegated_cycle=")))
        kwargs["extra_contract_lines"] = (
            "mode=link44-dynamic-lookup-latch-" + stage,
            "source_baseline=link44-c2-lite-v6-bank2-target-stage-replay",
            "promotable=no-permanently-diagnostic-only",
            "diagnostic_define=" + DEFINE,
            "diagnostic_question=first-dynamic-top-level-VM_DIRMISS-identity",
            "delegation_class=B",
            "delegated_cycle=1-of-3",
            "new_diagnostic_state_bytes=0",
            "green_inheritance=none",
            *lines)
        return old["single_link"](*args, **kwargs)

    authority = BASE_RECEIPT if stage == "probe" else PROBE_RECEIPT
    try:
        LINK44.OUT = out
        LINK44.RECEIPT = internal
        LINK44.LINK_NUMBER = 44
        LINK44.BASELINE = BASE_PRODUCT
        LINK44.BASELINE_SHA = BASE_PRODUCT_SHA
        LINK44.BASELINE_RECEIPT = BASE_RECEIPT
        LINK44.BASELINE_RECEIPT_SHA = BASE_RECEIPT_SHA
        LINK44.WPLTO = authority
        LINK44.WPLTO_SHA = sha(authority)
        LINK44.HARDWARE_FIRST_RED = FIRST_RED
        LINK44.prerequisites = lambda: prerequisites(stage)
        PROFILE.feature_defines = diagnostic_features
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
        PROFILE.feature_defines = old["feature_defines"]
        LINK44.BASE_LINK.fresh_prelink_gates = old["prelink"]
        LINK44.BASE_LINK.replacement_gates = old["replacement"]
        LINK44.P.single_link = old["single_link"]

    if result != 0:
        value = {
            "format": "lisp65-c2-lite-v6-dynamic-lookup-latch-first-red-v1",
            "recorded_on": "2026-07-22",
            "status": f"FIRST RED: dynamic lookup {stage} stopped",
            "promotable": False,
            "internal_receipt": bind(internal) if internal.is_file() else None,
            "link44_rollback": {**bind(BASE_PRODUCT), "status": "untouched"},
            "execution_accounting": {"hardware_runs": 0,
                                      "promotable_product_links": 0},
            "next_gate": "stop; return product or capacity question to review",
        }
        write(receipt_path, value)
        os.chmod(receipt_path, 0o444)
        return value

    internal_value = json.loads(internal.read_text(encoding="utf-8"))
    structure_path = ROOT / internal_value["structural_report"]["path"]
    structure = json.loads(structure_path.read_text(encoding="utf-8"))
    capacity = capacity_gate(structure)
    latch = structure["fresh_replacement_gates"]["dynamic_lookup_latch"]
    require(latch["status"].startswith("passed-")
            and internal_value["status"] ==
                "passed-new-c2-lite-real-abi-identity-hardware-not-run",
            "diagnostic closure did not finish fully green")
    product = ROOT / internal_value["product_identity"]["product"]["path"]
    value = {
        "format": "lisp65-c2-lite-v6-dynamic-lookup-latch-"
                  + ("wplto-v1" if stage == "probe" else
                     "diagnostic-link-v1"),
        "recorded_on": "2026-07-22",
        "status": (
            "passed-product-shaped-WPLTO-no-hardware-no-product-candidate"
            if stage == "probe" else
            "passed-nonpromotable-diagnostic-link-hardware-not-run"),
        "promotable": False,
        "delegation": {"class": "B", "cycle": "1-of-3"},
        "claim_limit": (
            "Product-shaped WPLTO capacity truth only; not a candidate."
            if stage == "probe" else
            "Permanently diagnostic identity for exactly one authorized "
            "dynamic-top-level hardware diagnosis; never promotable."),
        "authority": prerequisites(stage),
        "product_identity": {**bind(product), "diagnostic_only": True},
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
            "hardware_runs": 0,
            "promotable_product_links": 0,
        },
        "next_gate": (
            "one nonpromotable diagnostic link"
            if stage == "probe" else
            "one Class-B hardware cycle; one expression; capture latch and stop"),
    }
    write(receipt_path, value)
    os.chmod(receipt_path, 0o444)
    return value


def selftest() -> dict[str, Any]:
    value = source_gate(VM.read_text(encoding="utf-8"),
                        VM_H.read_text(encoding="utf-8"),
                        EVAL.read_text(encoding="utf-8"), mutations=True)
    require(len(value["mutations_rejected"]) == 8,
            "dynamic lookup mutation count drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("selftest", "probe", "link"))
    args = parser.parse_args()
    try:
        value = selftest() if args.stage == "selftest" else run_stage(args.stage)
        print("c2-lite-v6-dynamic-lookup-latch: " + value["status"])
        return 2 if value["status"].startswith("FIRST RED") else 0
    except (GateError, RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-lite-v6-dynamic-lookup-latch: FAIL: " + str(error),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
