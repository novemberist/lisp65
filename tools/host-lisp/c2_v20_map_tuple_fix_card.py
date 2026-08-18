#!/usr/bin/env python3
"""Run the one owner-authorized product card for the corrected MAP tuple."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_asm_leaf_abi_gate as ASM_ABI  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v20_crc_carveout_card as CRC  # noqa: E402
import c2_v20_map_tuple_fix as FIX  # noqa: E402
import c2_v20_ownership_recharter as PRODUCER  # noqa: E402
import c2_v20_vma_invariant_golden as INV  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.0-map-tuple-fix-card"
PREFLIGHT = ROOT / "build/c2.3/v2.0-map-tuple-fix-card-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
RECEIPT = EVIDENCE / "c2.3-v2.0-map-tuple-fix-card-receipt.json"
FINAL_RED = EVIDENCE / "c2.3-v2.0-map-tuple-fix-card-final-red.json"
FINAL_RED_REBIND = EVIDENCE / (
    "c2.3-v2.0-map-tuple-fix-card-final-red-rebind-2026-08-14.json")
INVENTORY_REBIND = EVIDENCE / (
    "c2.3-v2.0-map-tuple-fix-card-inventory-rebind-2026-08-16.json")
HISTORICAL_FINAL_RED_SHA256 = (
    "8df43176407d923a06ac1bb5056ab514b7ee9910b2c59059cab94a4c15328b93")
PRIOR_CARD = CRC.RECEIPT
DRIVER = Path(__file__).resolve()
AUTHORIZATION_COMMIT = FIX.AUTHORIZATION_COMMIT
RECORDED_ON = "2026-08-13"
FORMAT = "lisp65-c2.3-v20-map-tuple-fix-card-v1"
LINK = 100


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    return FIX.authorization()


def configure_fix_source() -> dict[str, Any]:
    sources = (FIX.SOURCE, ROOT / "src/c2_mapped_far_convergence.s")
    PRODUCT.CONVERGENCE_SOURCES = sources
    replacement = {
        "name": "mapped-far-content-convergence",
        "trigger": PRODUCT.CONVERGENCE_FEATURE,
        "defines": PRODUCT.CONVERGENCE_DEFINES,
        "sources": sources,
    }
    scopes: list[dict[str, Any]] = []
    replaced = 0
    for scope in PRODUCT.SOURCE_OWNER_SCOPES:
        if (scope.get("name") == replacement["name"]):
            scopes.append(replacement)
            replaced += 1
        else:
            scopes.append(scope)
    require(replaced == 1, "mapped-far source owner identity is not unique")
    PRODUCT.SOURCE_OWNER_SCOPES = tuple(scopes)

    # This is deliberately after the mutation and uses the real source-list
    # consumer.  Registry closure before producer configuration would merely
    # prove the registry that the historical replacement used to discard.
    selected = tuple(str(scope["trigger"])
                     for scope in PRODUCT.SOURCE_OWNER_SCOPES)
    dummy = {"product_build_id_hex": "0x00000000",
             "artifacts": {"shelf": {"bytes": 0}}}
    return PRODUCT.source_owner_scope_gate(
        PRODUCT.definitions(dummy), selected, PRODUCT.source_list(selected))


def fix_authority() -> dict[str, Any]:
    expected = FIX.expected()
    require(load(FIX.RECEIPT) == expected,
            "primary-semantics MAP fix authority is not green")
    return expected


def prior_authority() -> dict[str, Any]:
    prior = load(PRIOR_CARD)
    require(
        prior.get("status")
            == "PASS: VMA geometry, LMA reset and CRC-aware delivery exact"
        and prior.get("attempt_accounting", {}).get("cards_consumed") == 1
        and prior["acceptance"]["VMA_golden"]["allocatable_sections"] == 103
        and prior["acceptance"]["delivered_bytes"]["identity_mismatches"] == 0,
        "green predecessor card authority absent")
    return {"green_predecessor_card": bind(PRIOR_CARD),
            "VMA_golden": bind(INV.GOLDEN)}


def source_scope_gate() -> dict[str, Any]:
    configured = configure_fix_source()
    result = PRODUCT.source_owner_scope_selftest()
    selected = result["selected"]["scopes"]
    corrected = next(row for row in selected
                     if row["name"] == "mapped-far-content-convergence")
    require(
        corrected["selected"] is True
        and corrected["sources"] == [
            "src/c2_mapped_far_convergence.s",
            "src/optional/c2_mapped_far_service_v2.s"]
        and all(row["selected"] is True
                for row in configured["scopes"])
        and result["mutations_rejected"] == 3,
        "corrected trampoline escaped source-owner scope")
    return {**result, "post_configuration_real_consumer": configured}


def real_asm_inventory_gate() -> dict[str, Any]:
    """Run the real global assembler inventory and reject the card's First Red."""
    positive = ASM_ABI.source_inventory()
    texts = {path: path.read_text(encoding="utf-8")
             for path in sorted((ROOT / "src").glob("*.s"))}
    texts[FIX.SOURCE] = FIX.SOURCE.read_text(encoding="utf-8")
    rejected = False
    try:
        ASM_ABI.source_inventory(texts)
    except ASM_ABI.GateError as error:
        rejected = "declaration is not unique" in str(error)
    require(rejected, "duplicate successor in global ASM domain survived")
    successors = {
        name: positive[name] for name in (
            "c2_map_cpu_read", "c2_map_cpu_selector")}
    require(
        all(row["source"] == "src/optional/c2_map_cpu_read.s"
            for row in successors.values())
        and all(row.get("policy") for row in positive.values()),
        "current assembler inventory contains an unclassified declaration")
    return {"status": "passed-real-global-assembler-inventory",
            "expectation": "rule-classified-candidate-inventory",
            "declared_functions": len(positive),
            "classified_functions": sorted(positive),
            "unclassified_functions": [],
            "authorized_successors": successors,
            "historical_count_expectations": 0,
            "duplicate-successor-in-global-asm-domain": "rejected"}


def preflight_value() -> dict[str, Any]:
    return {
        "format": "lisp65-c2.3-v20-map-tuple-fix-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: exactly one corrected-tuple product card armed",
        "execution_accounting": {"cards_consumed": 0, "wplto_runs": 0,
                                 "product_links": 0, "device_contacts": 0},
        "configuration": {
            "link": LINK, "full_map_ownership": True,
            "low_resident_LMA_reset": True,
            "corrected_trampoline": "src/optional/c2_mapped_far_service_v2.s",
            "tuple": {"A": "0x40", "X": "0x82"},
            "new_staging_roles": 0,
        },
        "acceptance": {
            "VMA_authority": "VMA-only-invariant-golden-v3",
            "candidate_derived_validation": True,
            "CRC_publish_last_domain_bytes": 2,
            "linked_MAP_decode": "primary-semantics A=$40 X=$82",
            "cards_authorized": 1,
        },
        "host_gates": {"fix": {
            "status": fix_authority()["status"],
            "mutations": len(fix_authority()["mutations_rejected"])},
            "source_owner_scope": source_scope_gate(),
            "real_global_ASM_inventory": real_asm_inventory_gate()},
        "authority": {
            "owner_authorization": authorization(),
            "fix_receipt": bind(FIX.RECEIPT), "prior": prior_authority(),
            "producer": bind(Path(PRODUCER.__file__).resolve()),
            "product_linker": bind(Path(PRODUCT.__file__).resolve()),
            "driver": bind(DRIVER),
        },
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(
        value.get("format") == "lisp65-c2.3-v20-map-tuple-fix-preflight-v1"
        and value.get("status")
            == "PASS: exactly one corrected-tuple product card armed"
        and value.get("execution_accounting") == {
            "cards_consumed": 0, "wplto_runs": 0,
            "product_links": 0, "device_contacts": 0}
        and value.get("configuration") == {
            "link": LINK, "full_map_ownership": True,
            "low_resident_LMA_reset": True,
            "corrected_trampoline": "src/optional/c2_mapped_far_service_v2.s",
            "tuple": {"A": "0x40", "X": "0x82"},
            "new_staging_roles": 0}
        and value["acceptance"]["cards_authorized"] == 1
        and value["acceptance"]["CRC_publish_last_domain_bytes"] == 2
        and value["host_gates"]["fix"]["mutations"] == 14
        and value["host_gates"]["real_global_ASM_inventory"][
            "duplicate-successor-in-global-asm-domain"] == "rejected"
        and value["authority"]["owner_authorization"] == authorization()
        and value["authority"]["fix_receipt"] == bind(FIX.RECEIPT)
        and value["authority"]["prior"] == prior_authority()
        and value["authority"]["driver"] == bind(DRIVER),
        "corrected-tuple card preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-old-A": lambda x: x["configuration"]["tuple"].update(A="0x80"),
        "restore-old-X": lambda x: x["configuration"]["tuple"].update(X="0x24"),
        "select-old-source": lambda x: x["configuration"].update(
            corrected_trampoline="src/c2_mapped_far_service.s"),
        "drop-full-map": lambda x: x["configuration"].update(
            full_map_ownership=False),
        "drop-LMA-reset": lambda x: x["configuration"].update(
            low_resident_LMA_reset=False),
        "detach-fix": lambda x: x["authority"]["fix_receipt"].update(
            sha256="0" * 64),
        "detach-golden": lambda x: x["authority"]["prior"]["VMA_golden"].update(
            sha256="0" * 64),
        "authorize-two-cards": lambda x: x["acceptance"].update(
            cards_authorized=2),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate_preflight(candidate)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "corrected-tuple preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "corrected-tuple preflight/card is one-shot")
    value = preflight_value()
    validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.0 MAP-tuple card: PREFLIGHT PASS fix=14 source-scope=3 card=0")


def produce_candidate() -> dict[str, Any]:
    configure_fix_source()
    PRODUCER.LINK = LINK
    PRODUCER.BUILD = BUILD
    PRODUCER.FINAL_RED = BUILD / "producer-internal-first-red.json"
    PRODUCT.configure_full_map_ownership()
    PRODUCT.configure_low_resident_lma_reset()
    return PRODUCER.produce_candidate()


def linked_tuple_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=FIX.READOBJ, include_section_data=True)
    enter = truth.symbol("c2_mapped_far_enter")
    section = truth.section(enter.section)
    raw = truth.section_bytes(enter.section)
    body = raw[enter.value - section.address:
               enter.value - section.address + enter.bytes]
    expected = bytes.fromhex("48da5aa940a282a000a3805ceaa3007afa6860")
    decoded = FIX.decode_low(0x40, 0x82)
    service = truth.symbol("c2_mapped_far_vm_code_load_converged")
    far = truth.section(".lisp65_c2_mapped_far_service")
    far_raw = truth.section_bytes(far.name)
    first_store = far_raw[0x32:0x37]
    require(
        body == expected and enter.bytes == 19
        and service.value == 0x79DC
        and FIX.map_low(service.value, decoded) == 0x2B9DC
        and FIX.map_low(0x3185, decoded) == 0x3185
        and (far.address, far.bytes) == (0x78B2, 874)
        and first_store == bytes.fromhex("a9048d00c0"),
        "linked corrected MAP tuple or entry model drift")
    return {
        "status": "passed-primary-semantics-linked-tuple",
        "symbol": "c2_mapped_far_enter", "VMA": f"0x{enter.value:04X}",
        "bytes": body.hex(), "tuple": {"A": "0x40", "X": "0x82",
                                             "Y": "0x00", "Z": "0x80"},
        "decode": decoded, "service_entry_physical": "0x02B9DC",
        "block1_unchanged": True,
        "first_descriptor_store": {"physical_PC": "0x02B8E4",
                                     "bytes": first_store.hex(),
                                     "effect": "STA $C000 <= $04"},
    }


def validate_linked_tuple(value: dict[str, Any], elf: Path) -> None:
    require(value == linked_tuple_gate(elf)
            and value["tuple"] == {"A": "0x40", "X": "0x82",
                                   "Y": "0x00", "Z": "0x80"}
            and value["decode"]["mapped_low_half_blocks"] == [3]
            and value["decode"]["physical_offset"] == "0x24000"
            and value["block1_unchanged"] is True,
            "linked tuple evidence drift")


def linked_mutations(value: dict[str, Any], elf: Path) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "old-A": lambda x: x["tuple"].update(A="0x80"),
        "old-X": lambda x: x["tuple"].update(X="0x24"),
        "old-machine-code": lambda x: x.update(
            bytes=x["bytes"].replace("a940a282", "a980a224")),
        "wrong-offset": lambda x: x["decode"].update(physical_offset="0x48000"),
        "wrong-block": lambda x: x["decode"].update(mapped_low_half_blocks=[1]),
        "wrong-entry": lambda x: x.update(service_entry_physical="0x079DC"),
        "mapped-block1": lambda x: x.update(block1_unchanged=False),
        "skip-descriptor-store": lambda x: x["first_descriptor_store"].update(
            bytes="0000000000"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate_linked_tuple(candidate, elf)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "linked MAP-tuple mutation survived")
    return rejected


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(value),
            "corrected-tuple preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "corrected-tuple product card is one-shot")
    INVOCATION.write_bytes(canonical({
        "format": "lisp65-c2.3-v20-map-tuple-card-invocation-v1",
        "recorded_on": RECORDED_ON, "status": "INVOKED",
        "authorization": authorization(), "preflight": bind(PREFLIGHT_RECEIPT),
        "driver": bind(DRIVER)}))
    artifacts = produce_candidate()
    comparison = INV.compare_elf(artifacts["elf"])
    linker = PRODUCT.low_resident_lma_reset_gate(
        artifacts["linker"].read_text(encoding="utf-8"))
    CRC.BUILD = BUILD
    delivery = CRC.delivered_bytes_gate(artifacts["elf"], artifacts["prg"])
    CRC.validate_delivery(delivery, artifacts["elf"], artifacts["prg"])
    delivery_rejected = CRC.delivery_mutations(
        delivery, artifacts["elf"], artifacts["prg"])
    tuple_gate = linked_tuple_gate(artifacts["elf"])
    tuple_rejected = linked_mutations(tuple_gate, artifacts["elf"])
    headroom = {row["id"]: row["candidate_headroom_bytes"]
                for row in comparison["capacity_measurements"]}
    receipt = {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "PASS: VMA geometry, LMA reset and CRC-aware delivery exact",
        "map_tuple_status": "PASS: corrected tuple linked and primary-decoded",
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "wplto_runs": 1, "product_link_attempts": 1, "device_contacts": 0},
        "acceptance": {
            "VMA_golden": comparison, "low_resident_linker_reset": linker,
            "delivered_bytes": delivery,
            "delivery_mutations_rejected": delivery_rejected,
            "linked_MAP_tuple": tuple_gate,
            "linked_MAP_mutations_rejected": tuple_rejected,
            "fixed_comparison_operations": 1,
            "candidate_derived_validation": True,
            "delivery_operations": 1, "historical_qualifiers": 0},
        "producer": {"mechanical_completion_only": True,
            "historical_return_nonauthoritative": artifacts["producer_return"],
            "log": bind(artifacts["producer_log"]),
            "resolved_profile": bind(artifacts["resolved_profile"])},
        "artifacts": {key: bind(artifacts[key])
                      for key in ("elf", "prg", "map", "lto", "linker")},
        "authority": {"owner_authorization": authorization(),
            "fix_receipt": bind(FIX.RECEIPT), "preflight": bind(PREFLIGHT_RECEIPT),
            "invocation": bind(INVOCATION), "driver": bind(DRIVER),
            "VMA_golden": bind(INV.GOLDEN)},
        "narrow_margins_are_not_budgets": {
            "ordinary_chain": headroom["low-resident-and-ordinary-chain"],
            "runtime_overlay": headroom["runtime-overlay-slices"],
            "bank0_state": headroom["owned-bank0-state"]},
        "next_gate": "regular media regeneration with full far-payload extent, then D1",
        "claim_limit": "One host-only card; no media, device, D2-D5 or release claim."}
    RECEIPT.write_bytes(canonical(receipt))
    print("2.0 MAP-tuple card: PASS A=40 X=82 block=3 "
          f"sections={comparison['allocatable_sections']} "
          f"margins={headroom['low-resident-and-ordinary-chain']}/"
          f"{headroom['runtime-overlay-slices']}/"
          f"{headroom['owned-bank0-state']} wplto=1 device=0")


def final_red(error: BaseException) -> None:
    if RECEIPT.exists() or FINAL_RED.exists() or not INVOCATION.exists():
        return
    artifacts = {}
    for name, relative in {
        "elf": "wplto/lisp65-c2-substitution-linked.prg.elf",
        "prg": "wplto/lisp65-c2-substitution-linked.prg",
        "map": "wplto/lisp65-c2-substitution-linked.prg.map",
        "producer_log": "receipts/v20-producer.log"}.items():
        path = BUILD / relative
        if path.is_file():
            artifacts[name] = bind(path)
    base_result_path = BUILD / "receipts/wplto-base-result.json"
    base_result = load(base_result_path) if base_result_path.is_file() else {}
    accounting = base_result.get("execution_accounting", {})
    internal_path = BUILD / "receipts/wplto-internal.json"
    internal = load(internal_path) if internal_path.is_file() else {}
    root_message = internal.get("diagnostic", {}).get("message", "")
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v20-map-tuple-fix-card-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: corrected-tuple card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "root_cause": {
            "class": "GLOBAL-ASM-INVENTORY-DUPLICATE-SUCCESSOR",
            "message": root_message,
            "product_artifacts_emitted": False,
        },
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "wplto_runs": accounting.get("whole_program_LTO_closure_links", 0),
            "product_link_attempts": accounting.get("promotable_product_links", 0),
            "device_contacts": 0},
        "retry_authorized": False, "owner_disposition_required": True,
        "artifacts": artifacts,
        "authority": {"owner_authorization": authorization(),
            "preflight": bind(PREFLIGHT_RECEIPT), "invocation": bind(INVOCATION),
            "driver": bind(DRIVER)}}))


def selftest() -> None:
    fix_authority(); prior_authority(); source_scope_gate()
    real_asm_inventory_gate(); INV.selftest()
    value = preflight_value(); validate_preflight(value)
    require(len(preflight_mutations(value)) == 8,
            "corrected-tuple preflight mutation count drift")
    print("2.0 MAP-tuple card: SELFTEST PASS fix=14 preflight=8 "
          "real-ASM-domain=green card=one")


def check() -> None:
    selftest()
    require(not (RECEIPT.exists() and FINAL_RED.exists()),
            "corrected-tuple card has two outcomes")
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(hashlib.sha256(FINAL_RED.read_bytes()).hexdigest()
                    == HISTORICAL_FINAL_RED_SHA256,
                "historical corrected-tuple Final Red was rewritten")
        require(value["retry_authorized"] is False
                and value["owner_disposition_required"] is True,
                "corrected-tuple Final Red drift")
        require(
            value["attempt_accounting"] == {
                "cards_authorized": 1, "cards_consumed": 1,
                "wplto_runs": 1, "product_link_attempts": 0,
                "device_contacts": 0}
            and value["root_cause"] == {
                "class": "GLOBAL-ASM-INVENTORY-DUPLICATE-SUCCESSOR",
                "message": "assembler function declaration is not unique: "
                           "vm_code_load_converged",
                "product_artifacts_emitted": False}
            and value["post_red_closure"] == {
                "status": "PASS: successor isolated behind explicit owner scope",
                "successor_source": bind(FIX.SOURCE),
                "driver": {
                    "bytes": 21998,
                    "path": "tools/host-lisp/c2_v20_map_tuple_fix_card.py",
                    "sha256": (
                        "78e697a0129a2b7b80057827e1385e2c096f0c2fecc0a15b8cadb873a0a1c088")},
                "real_global_ASM_inventory": {
                    "status": "passed-real-global-assembler-inventory",
                    "declared_functions": 29,
                    "duplicate-successor-in-global-asm-domain": "rejected"},
                "retry_authorized": False}
            and not any(name in value["artifacts"]
                        for name in ("elf", "prg", "map")),
            "corrected-tuple Final Red accounting/root cause drift")
        rebind = load(FINAL_RED_REBIND)
        require(
            rebind.get("format")
                == "lisp65-c2.3-v20-map-tuple-final-red-rebind-v1"
            and rebind.get("status")
                == "PASS: loud semantic-preserving MAP-tuple receipt rebind"
            and rebind["authority"]["historical_final_red"] == bind(FINAL_RED)
            and rebind["authority"]["current_driver"] == {
                "bytes": 24557,
                "path": "tools/host-lisp/c2_v20_map_tuple_fix_card.py",
                "sha256": (
                    "1649756c28156ec8fa398bcfccbb885faaa98c5fb53071b5f76b9f0fee5fedc3")}
            and rebind["change"]["allowed_paths"]
                == ["post_red_closure.driver"]
            and rebind["change"]["semantic_claims_changed"] is False
            and rebind["change"]["historical_receipt_rewritten"] is False,
            "corrected-tuple dated Final-Red rebind drift")
        inventory_rebind = load(INVENTORY_REBIND)
        live = real_asm_inventory_gate()
        require(
            inventory_rebind.get("format") ==
                "lisp65-c2.3-v20-map-tuple-inventory-rebind-v1"
            and inventory_rebind.get("status") ==
                "PASS: Link-101 inventory expectation is rule-classified"
            and inventory_rebind["authority"]["historical_final_red"] ==
                bind(FINAL_RED)
            and inventory_rebind["authority"]["prior_rebind"] ==
                bind(FINAL_RED_REBIND)
            and inventory_rebind["authority"]["historical_fixture_rebind"] ==
                bind(EVIDENCE / (
                    "c2.3-v2.0-map-tuple-fixture-scope-rebind-2026-08-14.json"))
            and inventory_rebind["authority"]["current_driver"] == bind(DRIVER)
            and inventory_rebind["historical"] == {
                "evidence_untouched": True, "declared_functions": 29,
                "fixture_rebind_evidence_untouched": True,
                "fixture_selected_successor_copies": 1}
            and inventory_rebind["live_inventory"] == live
            and live["expectation"] == "rule-classified-candidate-inventory"
            and live["declared_functions"] ==
                len(live["classified_functions"])
            and live["unclassified_functions"] == []
            and sorted(live["authorized_successors"]) == [
                "c2_map_cpu_read", "c2_map_cpu_selector"]
            and inventory_rebind["change"]["historical_receipt_rewritten"]
                is False
            and inventory_rebind["change"]["semantic_claims_changed"] is False,
            "corrected-tuple inventory classification rebind drift")
        print("2.0 MAP-tuple card: CHECK FINAL RED historical=unchanged live=bound")
        return
    if not RECEIPT.exists():
        print("2.0 MAP-tuple card: CHECK ARMED card=unused")
        return
    value = load(RECEIPT)
    elf = ROOT / value["artifacts"]["elf"]["path"]
    require(value["map_tuple_status"]
                == "PASS: corrected tuple linked and primary-decoded"
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["acceptance"]["linked_MAP_tuple"] == linked_tuple_gate(elf)
            and len(value["acceptance"]["linked_MAP_mutations_rejected"]) == 8,
            "green corrected-tuple card receipt drift")
    print("2.0 MAP-tuple card: CHECK PASS VMA=green MAP=A40/X82")


def main() -> int:
    action = argparse.ArgumentParser(description=__doc__)
    action.add_argument("action", choices=("selftest", "preflight", "card", "check"))
    selected = action.parse_args().action
    {"selftest": selftest, "preflight": preflight,
     "card": card, "check": check}[selected]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                final_red(error)
            except Exception as receipt_error:
                print(f"2.0 MAP-tuple card receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.0 MAP-tuple card: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
