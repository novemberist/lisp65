#!/usr/bin/env python3
"""Build product Link 52 with cold phase self-stamping provenance."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_install_phase_discriminator_gate as PHASE  # noqa: E402
import c2_lite_v6_link51_canonical_t_successor_link as BASE  # noqa: E402


L = BASE.L
P = BASE.P
BASE_LINK = BASE.BASE_LINK
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK_NUMBER = 52
OUT = ROOT / (
    "build/c2.2/substitution/product-link-52-c2-lite-v6-phase-self-stamp")
RECEIPT = EVIDENCE / (
    "c2.2-product-link52-c2-lite-v6-phase-self-stamp-structural-receipt.json")
WPLTO = EVIDENCE / (
    "c2.2-link52-phase-self-stamp-wplto-artifact-replay-receipt.json")
WPLTO_SHA = (
    "98c248b41f16fb6b88e697e43cac7e50cafe1ba1ed7202efc1e8d70649dfc6a6")
WPLTO_AUTHORITY = EVIDENCE / (
    "c2.2-link52-phase-self-stamp-wplto-replay3-internal-structural.json")
WPLTO_AUTHORITY_SHA = (
    "f7e9113d4e56a1110ecad930be06dfca2a27b7e8262b6dd291bab23c7fee67eb")
WPLTO_SOURCE = ROOT / (
    "build/c2.2/substitution/link52-phase-self-stamp-wplto-replay3")
WPLTO_PROFILE = WPLTO_SOURCE / "resolved-profile.txt"
BASELINE = ROOT / (
    "build/c2.2/substitution/product-link-51-c2-lite-v6-canonical-t/"
    "lisp65-c2-substitution-linked.prg")
BASELINE_SHA = (
    "22ab996f5c14db54a7449c0fbcecd22ec4c0d806f72803eb7c49eb953c271629")
BASELINE_RECEIPT = EVIDENCE / (
    "c2.2-product-link51-c2-lite-v6-canonical-t-"
    "artifact-replay-structural-receipt.json")
BASELINE_RECEIPT_SHA = (
    "7f09ec4387307f0aeff785106176ded4354586b3761cc47605d84cd78f6a4b9c")
HARDWARE = EVIDENCE / "c2.2-link51-badopcode-hold-shelf-hardware-receipt.json"
HARDWARE_SHA = (
    "a5e0e0facef24a8d6d6d3d00a6892f8652aa50c358c314799ef8d62bd8a3587a")
MODE = "link52-c2-lite-v6-phase-self-stamp"
SOURCE_BASELINE = "product-link51-canonical-t"
SOURCE_GATE_STATUS = "passed-cold-phase-self-stamp-contract"
LINKED_GATE_STATUS = "passed-linked-slot-stamped-install-provenance"
FINAL_FORMAT = "lisp65-c2-lite-v6-link52-phase-self-stamp-v1"
FINAL_STATUS = "passed-new-phase-self-stamp-product-identity-hardware-not-run"
NEXT_GATE = (
    "Hardware double run: latency presmoke plus persistent slot/inner "
    "witness if BADOPCODE recurs.")
DRIVER_LABEL = "c2-lite-v6-link52-phase-self-stamp"
# Later product links may attach a new source/ELF gate at this already audited
# seam.  Defaults preserve the historical Link-52/53 behavior exactly.
EXTRA_SOURCE_GATE_KEY: str | None = None
EXTRA_SOURCE_GATE = None
EXTRA_LINKED_GATE_KEY: str | None = None
EXTRA_LINKED_GATE = None
EXTRA_CONTRACT_LINES: tuple[str, ...] = ()


class Link52Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise Link52Error(message)


def validate_authority() -> dict[str, Any]:
    for path, digest in {
            WPLTO: WPLTO_SHA,
            WPLTO_AUTHORITY: WPLTO_AUTHORITY_SHA,
            BASELINE: BASELINE_SHA,
            BASELINE_RECEIPT: BASELINE_RECEIPT_SHA,
            HARDWARE: HARDWARE_SHA,
            PHASE.CONTRACT:
                "c5c20f8f20a19dca0fa6d633ef65089c2a658e687967155991ceb1ac44ec77ab",
            }.items():
        require(path.is_file() and L.sha(path) == digest,
                f"Link-52 authority SHA drift: {path}")
    qualified = json.loads(WPLTO.read_text(encoding="utf-8"))
    structural = json.loads(WPLTO_AUTHORITY.read_text(encoding="utf-8"))
    require(qualified["status"] ==
                "passed-read-only-current-contract-WPLTO-qualification"
            and not qualified["promotable"]
            and qualified["execution_accounting"]["replay_compiler_runs"] == 0
            and qualified["execution_accounting"]["replay_linker_runs"] == 0
            and qualified["walls"] == {
                "bank0_text_headroom_bytes": 50,
                "ordinary_bank0_bss_headroom_bytes": 213,
                "fixed_hot_block_headroom_bytes": 33,
                "resident_island_headroom_bytes": 5,
                "e000_headroom_bytes": 58}
            and qualified["capacity"]["session_family_bytes"] == 65438
            and qualified["phase_self_stamp"]["source"]["status"] ==
                SOURCE_GATE_STATUS
            and qualified["phase_self_stamp"]["linked"]["status"] ==
                LINKED_GATE_STATUS
            and structural["product_identity"]["product"]["sha256"] ==
                qualified["identity"]["product"]["sha256"],
            "Link-52 phase-self-stamp WPLTO authority incomplete")
    # Link 50's historical driver consumes this one identity alias after the
    # fresh link.  It is an adapter only; the authority remains the current
    # immutable WPLTO receipt above.
    qualified = dict(qualified)
    qualified["frozen_identity"] = qualified["identity"]
    return qualified


def main() -> int:
    require(not OUT.exists() and not RECEIPT.exists(), "Link 52 is one-shot")
    authority = validate_authority()
    old = {
        "number": BASE.LINK_NUMBER, "out": BASE.OUT,
        "receipt": BASE.RECEIPT, "wplto": BASE.WPLTO,
        "wplto_sha": BASE.WPLTO_SHA,
        "wplto_authority": BASE.WPLTO_AUTHORITY,
        "wplto_authority_sha": BASE.WPLTO_AUTHORITY_SHA,
        "wplto_source": BASE.WPLTO_SOURCE,
        "wplto_profile": BASE.WPLTO_PROFILE,
        "baseline": BASE.BASELINE, "baseline_sha": BASE.BASELINE_SHA,
        "baseline_receipt": BASE.BASELINE_RECEIPT,
        "baseline_receipt_sha": BASE.BASELINE_RECEIPT_SHA,
        "validate": BASE.validate_authority,
        "legacy_prerequisites": BASE.BASE.BASE.prerequisites,
        "replacement": BASE.BASE.corrected_replacement,
        "prelink": BASE_LINK.fresh_prelink_gates,
        "single_link": P.single_link,
    }

    def prelink() -> dict[str, Any]:
        value = old["prelink"]()
        value["install_phase_self_stamp_source"] = \
            PHASE.source_gate(mutations=True)
        if EXTRA_SOURCE_GATE_KEY is not None and EXTRA_SOURCE_GATE is not None:
            value[EXTRA_SOURCE_GATE_KEY] = EXTRA_SOURCE_GATE()
        return value

    def current_legacy_prerequisites() -> dict[str, Any]:
        """Feed the current authority through the historical Link-49 seam."""
        validate_authority()
        return {
            "link51_rollback_product": {**L.bind(BASELINE),
                                        "status": "untouched"},
            "link51_structural_authority": L.bind(BASELINE_RECEIPT),
            "link51_badopcode_hardware_capture": L.bind(HARDWARE),
            "qualified_phase_self_stamp_wplto": L.bind(WPLTO),
            "complete_product_profile":
                BASE.BASE.BASE.current_profile_authority(),
            "phase_self_stamp_contract": L.bind(PHASE.CONTRACT),
            "driver": L.bind(Path(__file__)),
        }

    def replacement(product: Path, elf: Path,
                    host: dict[str, Any]) -> dict[str, Any]:
        value = old["replacement"](product, elf, host)
        value["install_phase_self_stamp"] = PHASE.linked_gate(
            elf, P.TOOLCHAIN / "llvm-readobj")
        if EXTRA_LINKED_GATE_KEY is not None and EXTRA_LINKED_GATE is not None:
            value[EXTRA_LINKED_GATE_KEY] = EXTRA_LINKED_GATE(
                elf, P.TOOLCHAIN / "llvm-readobj")
        return value

    def single_link(*args: Any, **kwargs: Any) -> Any:
        lines = tuple(line for line in kwargs.get("extra_contract_lines", ())
                      if not line.startswith((
                          "mode=", "source_baseline=", "promotable=",
                          "install_phase_", "line1_first_red_budget=",
                          "latency_measurement_attempts=")))
        kwargs["extra_contract_lines"] = (
            "mode=" + MODE,
            "source_baseline=" + SOURCE_BASELINE,
            "promotable=no-hardware-not-run",
            "install_phase_provenance=overlay-slot-self-stamp-plus-inner-marker",
            "install_phase_wplto=" + WPLTO_SHA,
            "line1_first_red_budget=2-of-3-consumed",
            "latency_measurement_attempts=0-of-2-consumed",
            *EXTRA_CONTRACT_LINES,
            *lines)
        return old["single_link"](*args, **kwargs)

    try:
        BASE.LINK_NUMBER = LINK_NUMBER
        BASE.OUT = OUT
        BASE.RECEIPT = RECEIPT
        BASE.WPLTO = WPLTO
        BASE.WPLTO_SHA = WPLTO_SHA
        BASE.WPLTO_AUTHORITY = WPLTO_AUTHORITY
        BASE.WPLTO_AUTHORITY_SHA = WPLTO_AUTHORITY_SHA
        BASE.WPLTO_SOURCE = WPLTO_SOURCE
        BASE.WPLTO_PROFILE = WPLTO_PROFILE
        BASE.BASELINE = BASELINE
        BASE.BASELINE_SHA = BASELINE_SHA
        BASE.BASELINE_RECEIPT = BASELINE_RECEIPT
        BASE.BASELINE_RECEIPT_SHA = BASELINE_RECEIPT_SHA
        BASE.validate_authority = validate_authority
        BASE.BASE.BASE.prerequisites = current_legacy_prerequisites
        BASE.BASE.corrected_replacement = replacement
        BASE_LINK.fresh_prelink_gates = prelink
        P.single_link = single_link
        result = BASE.main()
    finally:
        BASE.LINK_NUMBER = old["number"]
        BASE.OUT = old["out"]
        BASE.RECEIPT = old["receipt"]
        BASE.WPLTO = old["wplto"]
        BASE.WPLTO_SHA = old["wplto_sha"]
        BASE.WPLTO_AUTHORITY = old["wplto_authority"]
        BASE.WPLTO_AUTHORITY_SHA = old["wplto_authority_sha"]
        BASE.WPLTO_SOURCE = old["wplto_source"]
        BASE.WPLTO_PROFILE = old["wplto_profile"]
        BASE.BASELINE = old["baseline"]
        BASE.BASELINE_SHA = old["baseline_sha"]
        BASE.BASELINE_RECEIPT = old["baseline_receipt"]
        BASE.BASELINE_RECEIPT_SHA = old["baseline_receipt_sha"]
        BASE.validate_authority = old["validate"]
        BASE.BASE.BASE.prerequisites = old["legacy_prerequisites"]
        BASE.BASE.corrected_replacement = old["replacement"]
        BASE_LINK.fresh_prelink_gates = old["prelink"]
        P.single_link = old["single_link"]
    if result != 0:
        return result

    os.chmod(RECEIPT, 0o644)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    gates = receipt["fresh_replacement_gates"]
    walls = gates["walls"]
    capacity = gates["capacity"]
    phase = gates["install_phase_self_stamp"]
    product = OUT / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    map_path = Path(str(product) + ".map")
    require(receipt["link_number"] == LINK_NUMBER
            and L.sha(product) != BASELINE_SHA
            and walls["bank0_text_headroom_bytes"] >= 32
            and walls["e000_headroom_bytes"] >= 54
            and walls["ordinary_bank0_bss_headroom_bytes"] == 213
            and walls["fixed_hot_block_headroom_bytes"] >= 0
            and walls["resident_island_headroom_bytes"] >= 0
            and capacity["session_family_bytes"] <= 65536
            and phase["status"] ==
                LINKED_GATE_STATUS
            and phase["new_state_objects"] == 0
            and phase["scratch"]["bytes"] == 304,
            "Link-52 final product qualification red")
    receipt["format"] = FINAL_FORMAT
    receipt["status"] = FINAL_STATUS
    receipt["authority"]["phase_self_stamp_wplto"] = L.bind(WPLTO)
    receipt["authority"]["phase_self_stamp_structural_truth"] = \
        L.bind(WPLTO_AUTHORITY)
    receipt["authority"]["link51_rollback_product"] = {
        **L.bind(BASELINE), "status": "untouched"}
    receipt["authority"]["link51_badopcode_hardware_capture"] = \
        L.bind(HARDWARE)
    receipt["install_phase_provenance"] = {
        "contract": L.bind(PHASE.CONTRACT),
        "source_gate": PHASE.source_gate(mutations=True),
        "linked_gate": phase,
        "resident_marker_stores": 1,
        "new_state_bytes": 0,
    }
    receipt["product_identity"] = {
        "product": L.bind(product), "elf": L.bind(elf),
        "map": L.bind(map_path)}
    receipt["counters"] = {
        "class_b_diagnostic_cycles": "3/3 closed",
        "line1_product_first_reds": "2/3",
        "completed_latency_measurements": "0/2"}
    receipt["next_gate"] = NEXT_GATE
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print(DRIVER_LABEL + ": PASS "
          f"product={receipt['product_identity']['product']['sha256']} "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"e000={walls['e000_headroom_bytes']} "
          f"session={capacity['session_family_bytes']} hardware=not-run")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Link52Error, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(DRIVER_LABEL + ": FIRST RED: " + str(error),
              file=sys.stderr)
        raise SystemExit(2)
