#!/usr/bin/env python3
"""Nonpromotable WPLTO for the L65E ABI and transient-callability fixes.

The probe starts from immutable product Link 46.  It proves the corrected
runtime-overlay entry against the real indirect dispatcher edge, derives the
complete C-called assembler-function surface from the final ELF, and exercises
the previously missing callable high-edge fixture (logical 4095 -> physical
2047) through the generated C2D-v6 consumer sources.  It creates no promotable
product candidate and authorizes no hardware run.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_lite_v6_bank2_target_stage_successor_link as LINK44  # noqa: E402
import c2_lite_v6_link45_bcode_ordinal_wplto as ORDINAL  # noqa: E402
import c2_lite_v6_roots_fronts_product_profile as PROFILE  # noqa: E402
import c2_transient_execution_lookup_gate as TRANSIENT  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASE_DIR = ROOT / (
    "build/c2.2/substitution/"
    "product-link-46-c2-lite-v6-bcode-ordinal-renderer")
BASE_PRODUCT = BASE_DIR / "lisp65-c2-substitution-linked.prg"
BASE_RECEIPT = EVIDENCE / (
    "c2.2-product-link46-c2-lite-v6-bcode-ordinal-renderer-"
    "structural-receipt.json")
HARDWARE_FIRST_RED = EVIDENCE / (
    "c2.2-product-link46-l65e-entry-abi-hardware-first-red.json")
OUT = ROOT / "build/c2.2/substitution/link46-l65e-transient-wplto"
INTERNAL = EVIDENCE / "c2.2-link46-l65e-transient-wplto-internal.json"
RECEIPT = EVIDENCE / "c2.2-link46-l65e-transient-wplto-receipt.json"

BASE_PRODUCT_SHA = (
    "6d0d1b691bf0ffd81d333663e9d97e5d83588d08dbce745f86a530fa91079416")
BASE_RECEIPT_SHA = (
    "040451a9993736f58fcf912cf600f8eeb24a8eef88f59cb540dde2f2fa05723e")
HARDWARE_FIRST_RED_SHA = (
    "832619fca14d12c8157f1ecc0d6016e4ad6af82fdcac9fa50f3d7f54ccd3ce2b")


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


def prerequisites() -> dict[str, Any]:
    for path, digest in {
            BASE_PRODUCT: BASE_PRODUCT_SHA,
            BASE_RECEIPT: BASE_RECEIPT_SHA,
            HARDWARE_FIRST_RED: HARDWARE_FIRST_RED_SHA}.items():
        require(path.is_file() and sha(path) == digest,
                f"Link-46 L65E/transient authority drift: {path}")
    baseline = json.loads(BASE_RECEIPT.read_text(encoding="utf-8"))
    first_red = json.loads(HARDWARE_FIRST_RED.read_text(encoding="utf-8"))
    require(
        baseline["link_number"] == 46
        and baseline["product_identity"]["product"]["sha256"] ==
            BASE_PRODUCT_SHA,
        "Link-46 rollback candidate is not authoritative")
    require(
        first_red["status"] ==
            "first-red-l65e-entry-consumed-wrong-llvm-mos-argument-registers"
        and first_red["accounting"]["line1_product_first_red_budget"] ==
            "unchanged-at-2/3"
        and first_red["accounting"]["completed_latency_measurements"] ==
            "0/2",
        "L65E ABI hardware First Red or counters drift")
    return {
        "link46_rollback_product": {**bind(BASE_PRODUCT),
                                    "status": "untouched"},
        "link46_structural_authority": bind(BASE_RECEIPT),
        "link46_l65e_abi_hardware_first_red": bind(HARDWARE_FIRST_RED),
        "bcode_ordinal_contract": bind(ORDINAL.CONTRACT),
        "transient_handle_contract": bind(
            ROOT / "config/c2-transient-handle-contract.json"),
        "canonical_product_profile": PROFILE.check(),
        "driver": bind(Path(__file__)),
    }


def run_probe() -> dict[str, Any]:
    require(not OUT.exists() and not INTERNAL.exists() and not RECEIPT.exists(),
            "Link-46 L65E/transient WPLTO probe is one-shot")
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
        value["bcode_ordinal_renderer_source"] = \
            ORDINAL.source_gate(run_smoke=True)
        value["assembler_leaf_abi_source"] = {
            "status": "passed-ELF-derived-policy-and-mutation-preflight",
            "inventory": ABI.source_inventory(),
            "mutations_rejected": ABI.selftest(),
        }
        value["transient_execution_lookup_source"] = \
            TRANSIENT.source_gate()
        return value

    def replacement(product: Path, elf: Path,
                    host: dict[str, Any]) -> dict[str, Any]:
        value = old["replacement"](product, elf, host)
        renderer = ORDINAL.linked_gate(elf)
        abi_path = OUT / "c2-assembler-leaf-abi-derived-final.json"
        abi = ABI.audit_elf(elf, out=abi_path)
        generated = OUT / "generated-product-sources"
        transient_source = TRANSIENT.source_gate(
            generated_runtime=generated / "c2_product_runtime.c",
            generated_hot=generated / "c2_hot_literal.c")
        transient_linked = TRANSIENT.linked_gate(elf)
        walls, capacity = value["walls"], value["capacity"]
        require(renderer["slice"] == {
                    "bytes": 1145, "cap_bytes": 1320,
                    "headroom_bytes": 175},
                f"corrected L65E linked shape red: {renderer['slice']}")
        require(abi["status"] == "passed-all-assembler-leaf-abi-contracts"
                and abi["ELF_derived_C_called_inventory"]
                    ["unclassified_C_called_functions"] == [],
                "ELF-derived assembler ABI surface is incomplete")
        require(transient_linked["status"].startswith("passed-")
                and transient_source["generated_sources"]["status"] ==
                    "passed-generated-source-domain-split",
                "transient callable high-edge is not fully linked")
        require(walls["e000_headroom_bytes"] >= 115
                and all(int(walls[name]) >= 0 for name in (
                    "bank0_text_headroom_bytes",
                    "ordinary_bank0_bss_headroom_bytes",
                    "fixed_hot_block_headroom_bytes",
                    "resident_island_headroom_bytes")),
                f"L65E/transient product wall red: {walls}")
        require(capacity["session_family_bytes"] <= 65536
                and capacity["session_family_headroom_bytes"] >= 0,
                f"L65E/transient Session aggregate red: {capacity}")
        value["bcode_ordinal_renderer"] = renderer
        value["assembler_leaf_abi_derived"] = abi
        value["assembler_leaf_abi_evidence"] = bind(abi_path)
        value["transient_execution_lookup"] = {
            "source": transient_source, "linked": transient_linked}
        return value

    def single_link(*args: Any, **kwargs: Any) -> Any:
        lines = tuple(line for line in kwargs.get("extra_contract_lines", ())
                      if not line.startswith(("mode=", "source_baseline=",
                                              "promotable=",
                                              "line1_first_red_budget=",
                                              "latency_measurement_attempts=")))
        kwargs["extra_contract_lines"] = (
            "mode=link46-l65e-abi-transient-callability-wplto",
            "source_baseline=link46-bcode-ordinal-renderer",
            "promotable=no-capacity-placement-probe-only",
            "l65e_entry_abi=context-in-rc2-rc3-no-entry-overwrite",
            "assembler_leaf_universe=ELF-derived-C-called",
            "transient_execution=logical4095-physical2047-high-domains",
            "line1_first_red_budget=2-of-3-consumed",
            "latency_measurement_attempts=0-of-2-consumed",
            *lines)
        return old["single_link"](*args, **kwargs)

    try:
        LINK44.OUT = OUT
        LINK44.RECEIPT = INTERNAL
        LINK44.LINK_NUMBER = 46
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
            "format": "lisp65-c2-lite-v6-link46-l65e-transient-wplto-first-red-v1",
            "recorded_on": "2026-07-22",
            "status": "FIRST RED: L65E/transient WPLTO stopped",
            "promotable": False,
            "internal_receipt": bind(INTERNAL),
            "link46_rollback": {**bind(BASE_PRODUCT), "status": "untouched"},
            "execution_accounting": {
                "whole_program_lto_closure_links": 1,
                "promotable_product_links": 0, "hardware_runs": 0},
            "next_gate": "stop; return measured First Red to Class-C review",
        }
        write(RECEIPT, value)
        os.chmod(RECEIPT, 0o444)
        return value

    structure_path = ROOT / internal["structural_report"]["path"]
    structure = json.loads(structure_path.read_text(encoding="utf-8"))
    gates = structure["fresh_replacement_gates"]
    product = ROOT / internal["product_identity"]["product"]["path"]
    require(
        internal["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and gates["assembler_leaf_abi_derived"]["status"] ==
            "passed-all-assembler-leaf-abi-contracts"
        and gates["transient_execution_lookup"]["linked"]["status"].startswith(
            "passed-"),
        "L65E/transient WPLTO did not complete fully green")
    value = {
        "format": "lisp65-c2-lite-v6-link46-l65e-transient-wplto-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-product-shaped-WPLTO-no-hardware-no-product-candidate",
        "promotable": False,
        "claim_limit": (
            "Host semantics, mutations, WPLTO placement and capacity only; "
            "no product link or hardware run authorized."),
        "authority": prerequisites(),
        "l65e_renderer": gates["bcode_ordinal_renderer"],
        "assembler_leaf_abi": gates["assembler_leaf_abi_derived"],
        "transient_execution_lookup": gates["transient_execution_lookup"],
        "walls": gates["walls"],
        "capacity": gates["capacity"],
        "product_shaped_identity": {**bind(product), "nonpromotable": True},
        "internal_structural_receipt": bind(INTERNAL),
        "structural_report": bind(structure_path),
        "link46_rollback": {**bind(BASE_PRODUCT), "status": "untouched"},
        "direct_source_delta": {
            "l65e_entry_bytes": -2,
            "note": (
                "The proposed four-byte deletion requires a two-byte LDA "
                "__rc2 replacement before ORA __rc3; measured net is -2 B.")},
        "execution_accounting": {
            "whole_program_lto_closure_links": 1,
            "promotable_product_links": 0, "hardware_runs": 0},
        "counters": {"line1_product_first_reds": "2/3",
                     "completed_latency_measurements": "0/2"},
        "next_gate": "separate Class-C authorization for successor product link",
    }
    write(RECEIPT, value)
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-link46-l65e-transient-wplto: PASS "
          f"text={gates['walls']['bank0_text_headroom_bytes']} "
          f"l65e={gates['bcode_ordinal_renderer']['slice']['bytes']} "
          f"session={gates['capacity']['session_family_bytes']} "
          "promotable=no hardware=not-run")
    return value


def main() -> int:
    try:
        run_probe()
        return 0
    except (GateError, ABI.GateError, TRANSIENT.GateError, OSError,
            RuntimeError, ValueError) as error:
        print("c2-lite-v6-link46-l65e-transient-wplto: FAIL: " + str(error),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
