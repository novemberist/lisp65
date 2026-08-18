#!/usr/bin/env python3
"""Bind the terminal VMA-golden card result without running another card."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v17_state_ownership_phase_b as LMA  # noqa: E402
import c2_v20_lma_repair_card as DELIVERY  # noqa: E402
import c2_v20_vma_golden_card as CARD  # noqa: E402
import c2_v20_vma_invariant_golden as INV  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.0-vma-golden-card"
WPLTO = BUILD / "wplto"
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
BOUND_PRG = WPLTO / "lisp65-c2-substitution-linked.prg"
UNBOUND_PRG = WPLTO / "lisp65-c2-substitution-unbound.prg"
PUBLISH = WPLTO / "kernal-window-publish-last.json"
RAW = BUILD / "receipts/wplto-raw.json"
BASE_RESULT = BUILD / "receipts/wplto-base-result.json"
INTERNAL = BUILD / "receipts/wplto-internal.json"
RECEIPT = EVIDENCE / "c2.3-v2.0-vma-golden-card-result-receipt.json"
RECORDED_ON = date.today().isoformat()
FORMAT = "lisp65-c2.3-v20-vma-golden-card-result-v1"
CLASSIFICATION = "ACCEPTANCE-CONTRACT-CROSSES-PUBLISH-LAST-DOMAIN"


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular artifact absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
    }


def section_delivery(prg: Path) -> dict[str, Any]:
    return DELIVERY.expected_delivery_gate(ELF, prg)


def byte_differences() -> list[dict[str, Any]]:
    truth = ElfTruth.read(
        ELF, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    image = BOUND_PRG.read_bytes()
    load_address = int.from_bytes(image[:2], "little")
    differences: list[dict[str, Any]] = []
    for name in PRODUCT.LOW_RESIDENT_LMA_SECTIONS:
        section = truth.section(name)
        expected = truth.section_bytes(name)
        offset = 2 + section.address - load_address
        actual = image[offset:offset + len(expected)]
        for relative, (elf_byte, prg_byte) in enumerate(zip(expected, actual)):
            if elf_byte != prg_byte:
                differences.append({
                    "section": name,
                    "address": section.address + relative,
                    "address_hex": f"0x{section.address + relative:04x}",
                    "section_offset": relative,
                    "elf_value": elf_byte,
                    "resident_prg_value": prg_byte,
                })
    return differences


def historical_observation() -> dict[str, Any]:
    raw = load(RAW)
    base = load(BASE_RESULT)
    internal = load(INTERNAL)
    exception = internal.get("diagnostic", {})
    require(
        raw.get("status")
            == "FIRST RED: historical checker stopped current-product L-full keymap WPLTO"
        and base.get("status")
            == "FIRST RED: product-shaped two-region package did not close"
        and base.get("WPLTO", {}).get("product_completed") is True
        and base.get("WPLTO", {}).get("return_code") == 2
        and base.get("WPLTO", {}).get("exception") is None
        and "inherited noinit/alignment geometry drift"
            in str(exception.get("message", "")),
        "historical producer qualification observation drift")
    return {
        "classification": "NONAUTHORITATIVE-HISTORICAL-QUALIFIER-RED",
        "raw_status": raw["status"],
        "base_status": base["status"],
        "historical_exception": exception,
        "mechanical_product_completed": True,
        "card_acceptance_authority": False,
        "receipts": {
            "raw": bind(RAW), "base_result": bind(BASE_RESULT),
            "internal": bind(INTERNAL),
        },
    }


def build_result() -> dict[str, Any]:
    red = load(CARD.FINAL_RED)
    require(
        red.get("status") == "FINAL RED: sole VMA-golden card returns to owner"
        and red.get("error", {}).get("message")
            == "boot-critical bytes are not exact in the existing resident PRG"
        and red.get("attempt_accounting") == {
            "cards_authorized": 1, "cards_consumed": 1,
            "wplto_runs": 1, "product_link_attempts": 1,
            "device_contacts": 0,
        }
        and red.get("retry_authorized") is False
        and red.get("owner_disposition_required") is True,
        "terminal card authority drift")

    comparison = INV.compare_elf(ELF)
    require(
        comparison.get("comparison")
            == "VMA-invariants-exact-candidate-freight-validated"
        and comparison.get("allocatable_sections") == 103
        and comparison.get("fixed_boundary_symbols") == 27,
        "candidate does not satisfy the VMA-only golden")
    margins = {
        row["id"]: row["candidate_headroom_bytes"]
        for row in comparison["capacity_measurements"]
    }

    unbound = section_delivery(UNBOUND_PRG)
    bound = section_delivery(BOUND_PRG)
    require(
        len(unbound["sections"]) == 4
        and all(row["lma_equals_vma"] and row["exact_bytes_delivered"]
                for row in unbound["sections"]),
        "unbound product is not 4/4 exact at LMA=VMA")
    require(
        len(bound["sections"]) == 4
        and all(row["lma_equals_vma"] for row in bound["sections"])
        and sum(bool(row["exact_bytes_delivered"])
                for row in bound["sections"]) == 3,
        "post-completion delivery result is not the observed 3/4 split")

    publish = load(PUBLISH)
    differences = byte_differences()
    operands = publish.get("binding_operands", [])
    operand_addresses = [row.get("address") for row in operands]
    require(
        publish.get("status") == "passed"
        and publish.get("actual_changed_bytes") == 2
        and publish.get("declared_mutation_domain_bytes") == 2
        and publish.get("changed_range_confined") is True
        and publish.get("negative_matrix") == {
            "mutated-published-crc": "rejected",
            "mutation-outside-two-byte-domain": "rejected",
        }
        and publish.get("unbound_product_sha256")
            == bind(UNBOUND_PRG)["sha256"]
        and publish.get("window_bound_product_sha256")
            == bind(BOUND_PRG)["sha256"]
        and len(differences) == 2
        and [row["address"] for row in differences] == operand_addresses
        and [row["elf_value"] for row in differences]
            == [row["compiled_value"] for row in operands]
        and [row["resident_prg_value"] for row in differences]
            == [row["published_value"] for row in operands],
        "the only delivery differences are not the declared publish-last domain")

    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED ATTRIBUTED: acceptance crossed publish-last domain",
        "classification": CLASSIFICATION,
        "attempt_accounting": red["attempt_accounting"],
        "retry_authorized": False,
        "owner_disposition_required": True,
        "card_authority": bind(CARD.FINAL_RED),
        "candidate": {
            "VMA_golden": comparison,
            "LMA_equals_VMA_sections": 4,
            "unbound_resident_sections_exact": 4,
            "completed_resident_sections_exact": 3,
            "narrow_margins_are_not_budgets": {
                "ordinary_chain": margins["low-resident-and-ordinary-chain"],
                "runtime_overlay": margins["runtime-overlay-slices"],
                "bank0_state": margins["owned-bank0-state"],
            },
            "artifacts": {
                "elf": bind(ELF), "unbound_prg": bind(UNBOUND_PRG),
                "completed_prg": bind(BOUND_PRG),
            },
        },
        "acceptance_failure": {
            "declared_contract": CARD.acceptance_contract(),
            "unbound_delivery": unbound,
            "post_completion_delivery": bound,
            "exact_post_completion_differences": differences,
            "publish_last_report": publish,
            "publish_last_report_artifact": bind(PUBLISH),
            "mechanism": (
                "The card compared the completed resident PRG with the linked "
                "ELF as whole sections. Mechanical completion is required to "
                "replace the two declared KERNAL-window CRC operands, so that "
                "comparison rejects its own permitted publish-last domain."),
        },
        "producer_observation": historical_observation(),
        "disposition": {
            "card_result": "terminal-red",
            "retry": "forbidden-by-the-one-card-contract",
            "media": "not-run",
            "device": "not-run",
            "release": "closed",
            "parity": "closed",
            "next_action": "owner-disposition-required",
        },
        "claim_limit": (
            "Read-only attribution of the consumed card. It proves green VMA "
            "geometry, green LMA reset and a two-byte acceptance/publish-last "
            "contract collision. It authorizes no retry, media, device, release "
            "or parity action."),
    }


def validate_result(value: dict[str, Any]) -> None:
    require(
        value.get("format") == FORMAT
        and value.get("status")
            == "FINAL RED ATTRIBUTED: acceptance crossed publish-last domain"
        and value.get("classification") == CLASSIFICATION
        and value.get("attempt_accounting", {}).get("cards_consumed") == 1
        and value.get("attempt_accounting", {}).get("wplto_runs") == 1
        and value.get("retry_authorized") is False
        and value.get("owner_disposition_required") is True
        and value.get("card_authority") == bind(CARD.FINAL_RED)
        and value.get("candidate", {}).get("VMA_golden", {}).get(
            "allocatable_sections") == 103
        and value.get("candidate", {}).get("VMA_golden", {}).get(
            "fixed_boundary_symbols") == 27
        and value.get("candidate", {}).get("LMA_equals_VMA_sections") == 4
        and value.get("candidate", {}).get("unbound_resident_sections_exact") == 4
        and value.get("candidate", {}).get("completed_resident_sections_exact") == 3
        and len(value.get("acceptance_failure", {}).get(
            "exact_post_completion_differences", [])) == 2
        and [row["address"] for row in value["acceptance_failure"]
                ["exact_post_completion_differences"]] == [0xB4F4, 0xB4FA]
        and value.get("producer_observation", {}).get(
            "card_acceptance_authority") is False
        and value.get("disposition", {}).get("retry")
            == "forbidden-by-the-one-card-contract",
        "persisted VMA-golden terminal attribution drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-VMA-red": lambda x: x["candidate"]["VMA_golden"].update(
            allocatable_sections=102),
        "claim-LMA-reset-red": lambda x: x["candidate"].update(
            LMA_equals_VMA_sections=3),
        "widen-difference": lambda x: x["acceptance_failure"][
            "exact_post_completion_differences"].append({"address": 0xB4FB}),
        "move-difference-outside-domain": lambda x: x["acceptance_failure"][
            "exact_post_completion_differences"][0].update(address=0xB4F5),
        "claim-postcompletion-4-of-4": lambda x: x["candidate"].update(
            completed_resident_sections_exact=4),
        "claim-product-failure": lambda x: x.update(
            classification="PRODUCT-GEOMETRY-FAILURE"),
        "authorize-retry": lambda x: x.update(retry_authorized=True),
        "erase-owner-halt": lambda x: x.update(owner_disposition_required=False),
        "erase-historical-observation": lambda x: x[
            "producer_observation"].update(card_acceptance_authority=None),
        "promote-historical-qualifier": lambda x: x[
            "producer_observation"].update(card_acceptance_authority=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_result(candidate)
        except ResultError:
            rejected.append(name)
    require(rejected == list(cases), "terminal attribution mutation survived")
    return rejected


def write() -> None:
    require(not RECEIPT.exists(), "terminal attribution receipt is immutable")
    value = build_result()
    validate_result(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.0 VMA-golden card result: FINAL RED ATTRIBUTED "
          "vma=103/27 lma=4/4 unbound=4/4 completed=3/4 "
          "publish-last-diff=2 retry=no")


def selftest() -> None:
    if RECEIPT.exists():
        value = load(RECEIPT)
    else:
        value = build_result()
    stored = value.pop("mutations_rejected", None)
    validate_result(value)
    rejected = mutations(value)
    if stored is not None:
        require(stored == rejected, "terminal attribution mutation receipt drift")
    print("2.0 VMA-golden card result: SELFTEST PASS mutations=10")


def check() -> None:
    require(RECEIPT.exists(), "terminal attribution receipt absent")
    selftest()
    print("2.0 VMA-golden card result: CHECK FINAL RED owner-halt=required")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "selftest", "check"))
    {"write": write, "selftest": selftest, "check": check}[
        parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"2.0 VMA-golden card result: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
