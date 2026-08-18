#!/usr/bin/env python3
"""Run the sole owner-authorized 2.0 publish-last carve-out card."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v17_state_ownership_phase_b as LMA  # noqa: E402
import c2_v20_ownership_recharter as PRODUCER  # noqa: E402
import c2_v20_vma_golden_card as PRIOR_CARD  # noqa: E402
import c2_v20_vma_golden_card_result as PRIOR_RESULT  # noqa: E402
import c2_v20_vma_invariant_golden as INV  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
OWNER_COMMIT = "2483d118e2f352e754da325b4de883891d2afd14"
BUILD = ROOT / "build/c2.3/v2.0-crc-carveout-card"
PREFLIGHT = ROOT / "build/c2.3/v2.0-crc-carveout-card-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
RECEIPT = EVIDENCE / "c2.3-v2.0-crc-carveout-card-receipt.json"
FINAL_RED = EVIDENCE / "c2.3-v2.0-crc-carveout-card-final-red.json"
DRIVER = Path(__file__).resolve()
RECORDED_ON = date.today().isoformat()
FORMAT = "lisp65-c2.3-v20-crc-carveout-card-v1"
HIGH = PRODUCT.KERNAL_CRC_BINDING_HIGH_ADDRESS
LOW = PRODUCT.KERNAL_CRC_BINDING_LOW_ADDRESS
CARVEOUT = (HIGH, LOW)


class CarveoutCardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CarveoutCardError(message)


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


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{relative}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {
        "authority": "git-blob", "commit": commit, "path": relative,
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
    }


def authorization() -> dict[str, Any]:
    authority = git_bind(OWNER_COMMIT, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{OWNER_COMMIT}:{authority['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode("utf-8").split())
    require(
        "CRC carve-out, one card" in text
        and "independently computed CRC value" in text
        and "every other byte stays identity-bound" in text
        and "forbids any growth of the exception set" in text
        and "Exactly one card" in text,
        "CRC carve-out owner authorization absent")
    return authority


def prior_authority() -> dict[str, Any]:
    red = load(PRIOR_CARD.FINAL_RED)
    result = load(PRIOR_RESULT.RECEIPT)
    require(
        red.get("status") == "FINAL RED: sole VMA-golden card returns to owner"
        and red.get("retry_authorized") is False
        and result.get("classification")
            == "ACCEPTANCE-CONTRACT-CROSSES-PUBLISH-LAST-DOMAIN"
        and result.get("candidate", {}).get("LMA_equals_VMA_sections") == 4
        and len(result.get("acceptance_failure", {}).get(
            "exact_post_completion_differences", [])) == 2,
        "terminal predecessor or two-byte attribution absent")
    return {
        "terminal_card": bind(PRIOR_CARD.FINAL_RED),
        "terminal_attribution": bind(PRIOR_RESULT.RECEIPT),
        "VMA_golden": bind(INV.GOLDEN),
    }


def crc16_oracle(data: bytes) -> int:
    """Independent local CCITT-FALSE oracle; does not consume completion."""
    value = 0xFFFF
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            top = bool(value & 0x8000)
            value = (value << 1) & 0xFFFF
            if top:
                value ^= 0x1021
    return value


def extract_oracle_window(elf: Path) -> bytes:
    with tempfile.TemporaryDirectory(
            prefix="c2-v20-crc-oracle-", dir=BUILD.parent) as temporary:
        output = Path(temporary) / "window.bin"
        command = [
            str(ROOT / "tools/llvm-mos/bin/llvm-objcopy"),
            "-O", "binary", "--gap-fill=0",
        ]
        command.extend(
            f"--only-section={section}" for section in PRODUCT.KERNAL_SECTIONS)
        command.extend([str(elf), str(output)])
        subprocess.run(command, cwd=ROOT, check=True)
        data = output.read_bytes()
    require(len(data) == PRODUCT.KERNAL_WINDOW_BYTES,
            "independent KERNAL-window extraction length drift")
    return data


def validate_byte_model(
        linked: bytes, completed: bytes, base: int,
        carveout: tuple[int, ...], crc: int) -> None:
    require(carveout == CARVEOUT,
            "publish-last exception set differs from the two named operands")
    require(len(linked) == len(completed),
            "completion changed resident product length")
    require(base <= HIGH < base + len(linked)
            and base <= LOW < base + len(linked),
            "publish-last operands escaped the delivered span")
    for offset, (before, after) in enumerate(zip(linked, completed)):
        address = base + offset
        expected = (
            crc >> 8 if address == HIGH
            else crc & 0xFF if address == LOW
            else before)
        require(after == expected,
                f"delivered byte violates identity/CRC contract at 0x{address:04x}")


def byte_model_selftest() -> list[str]:
    base = 0xB4F0
    linked = bytearray(range(16))
    linked[HIGH - base] = 0xA5
    linked[LOW - base] = 0x5A
    crc = 0xA0B3
    completed = bytearray(linked)
    completed[HIGH - base] = crc >> 8
    completed[LOW - base] = crc & 0xFF
    validate_byte_model(bytes(linked), bytes(completed), base, CARVEOUT, crc)

    cases: dict[str, Callable[[], None]] = {
        "grow-exception-set": lambda: validate_byte_model(
            bytes(linked), bytes(completed), base, (*CARVEOUT, 0xB4F5), crc),
        "move-high-operand": lambda: validate_byte_model(
            bytes(linked), bytes(completed), base, (HIGH + 1, LOW), crc),
        "drop-low-operand": lambda: validate_byte_model(
            bytes(linked), bytes(completed), base, (HIGH,), crc),
        "mutate-high-CRC": lambda: validate_byte_model(
            bytes(linked), bytes(completed[:HIGH - base]
                                 + bytes([0xA1])
                                 + completed[HIGH - base + 1:]),
            base, CARVEOUT, crc),
        "mutate-low-CRC": lambda: validate_byte_model(
            bytes(linked), bytes(completed[:LOW - base]
                                 + bytes([0xB2])
                                 + completed[LOW - base + 1:]),
            base, CARVEOUT, crc),
        "mutate-identity-byte": lambda: validate_byte_model(
            bytes(linked), bytes(bytes([completed[0] ^ 1]) + completed[1:]),
            base, CARVEOUT, crc),
        "wrong-independent-CRC": lambda: validate_byte_model(
            bytes(linked), bytes(completed), base, CARVEOUT, crc ^ 1),
        "truncate-product": lambda: validate_byte_model(
            bytes(linked), bytes(completed[:-1]), base, CARVEOUT, crc),
    }
    rejected: list[str] = []
    for name, run in cases.items():
        try:
            run()
        except CarveoutCardError:
            rejected.append(name)
    require(rejected == list(cases), "CRC carve-out model mutation survived")
    return rejected


def acceptance_contract() -> dict[str, Any]:
    return {
        "fixed_authority": "VMA-only-invariant-golden-v3",
        "candidate_derived": [
            "section-sizes-against-fixed-capacity-arenas",
            "numeric-LMAs-complete-and-non-overlapping",
            "overlay-end-from-candidate-section-extent",
        ],
        "delivery": {
            "identity_scope": "all-four-low-resident-section-bytes-except-two",
            "publish_last_value_scope": [
                {"name": "kernal-window-crc-high", "address": HIGH},
                {"name": "kernal-window-crc-low", "address": LOW},
            ],
            "oracle": "independent-ELF-window-extraction-plus-local-CCITT-FALSE",
            "exception_domain_bytes": 2,
            "exception_domain_growth": "forbidden",
        },
        "mechanical_completion": "producer-owned-not-an-acceptance-operation",
        "historical_qualifiers": 0,
    }


def validate_preflight(value: dict[str, Any]) -> None:
    require(
        value.get("format") == "lisp65-c2.3-v20-crc-carveout-preflight-v1"
        and value.get("status") == "PASS: exactly one CRC-carveout card armed"
        and value.get("execution_accounting") == {
            "cards_consumed": 0, "product_links": 0,
            "wplto_runs": 0, "device_contacts": 0,
        }
        and value.get("authority", {}).get("owner_authorization")
            == authorization()
        and value["authority"].get("prior") == prior_authority()
        and value["authority"].get("producer")
            == bind(Path(PRODUCER.__file__).resolve())
        and value["authority"].get("product_linker")
            == bind(Path(PRODUCT.__file__).resolve())
        and value["authority"].get("driver") == bind(DRIVER)
        and value.get("producer_configuration") == {
            "full_map_ownership": True,
            "low_resident_LMA_reset": True,
            "new_staging_roles": 0,
        }
        and value.get("acceptance") == acceptance_contract()
        and value.get("carveout_model_mutations") == byte_model_selftest(),
        "CRC carve-out card preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "detach-authorization": lambda x: x["authority"][
            "owner_authorization"].update(sha256="0" * 64),
        "replace-golden": lambda x: x["authority"]["prior"][
            "VMA_golden"].update(sha256="0" * 64),
        "change-producer": lambda x: x["authority"]["producer"].update(
            sha256="0" * 64),
        "drop-LMA-reset": lambda x: x["producer_configuration"].update(
            low_resident_LMA_reset=False),
        "grow-exception-domain": lambda x: x["acceptance"]["delivery"].update(
            exception_domain_bytes=3),
        "replace-independent-oracle": lambda x: x["acceptance"][
            "delivery"].update(oracle="completion-report"),
        "permit-domain-growth": lambda x: x["acceptance"]["delivery"].update(
            exception_domain_growth="permitted"),
        "add-historical-qualifier": lambda x: x["acceptance"].update(
            historical_qualifiers=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_preflight(candidate)
        except CarveoutCardError:
            rejected.append(name)
    require(rejected == list(cases), "CRC carve-out preflight mutation survived")
    return rejected


def build_preflight() -> dict[str, Any]:
    return {
        "format": "lisp65-c2.3-v20-crc-carveout-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: exactly one CRC-carveout card armed",
        "execution_accounting": {
            "cards_consumed": 0, "product_links": 0,
            "wplto_runs": 0, "device_contacts": 0,
        },
        "authority": {
            "owner_authorization": authorization(),
            "prior": prior_authority(),
            "producer": bind(Path(PRODUCER.__file__).resolve()),
            "product_linker": bind(Path(PRODUCT.__file__).resolve()),
            "driver": bind(DRIVER),
        },
        "producer_configuration": {
            "full_map_ownership": True,
            "low_resident_LMA_reset": True,
            "new_staging_roles": 0,
        },
        "acceptance": acceptance_contract(),
        "carveout_model_mutations": byte_model_selftest(),
    }


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "CRC carve-out preflight/card is one-shot")
    value = build_preflight()
    validate_preflight(value)
    value["preflight_mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.0 CRC carve-out card: PREFLIGHT PASS "
          "carveout=2 model-mutations=8 preflight-mutations=8 "
          "cards=0 wplto=0 device=0")


def produce_candidate() -> dict[str, Any]:
    PRODUCER.BUILD = BUILD
    PRODUCER.FINAL_RED = BUILD / "producer-internal-first-red.json"
    PRODUCT.configure_full_map_ownership()
    PRODUCT.configure_low_resident_lma_reset()
    return PRODUCER.produce_candidate()


def delivered_bytes_gate(elf: Path, completed_prg: Path) -> dict[str, Any]:
    truth = ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    image = completed_prg.read_bytes()
    require(len(image) >= 2, "resident PRG is truncated")
    load_address = int.from_bytes(image[:2], "little")
    window = extract_oracle_window(elf)
    oracle_crc = crc16_oracle(window)
    rows: list[dict[str, Any]] = []
    concatenated_linked = bytearray()
    concatenated_completed = bytearray()
    concatenated_addresses: list[int] = []
    for name in PRODUCT.LOW_RESIDENT_LMA_SECTIONS:
        section = truth.section(name)
        linked = truth.section_bytes(name)
        lma = LMA.section_lma(elf, name)
        offset = 2 + section.address - load_address
        inside = offset >= 2 and offset + len(linked) <= len(image)
        completed = image[offset:offset + len(linked)] if inside else b""
        identity_mismatches: list[str] = []
        crc_values: list[dict[str, Any]] = []
        if inside:
            for relative, (before, after) in enumerate(zip(linked, completed)):
                address = section.address + relative
                if address in CARVEOUT:
                    expected = oracle_crc >> 8 if address == HIGH else oracle_crc & 0xFF
                    crc_values.append({
                        "address": address, "expected": expected,
                        "observed": after, "correct": after == expected,
                    })
                elif before != after:
                    identity_mismatches.append(f"0x{address:04x}")
                concatenated_linked.append(before)
                concatenated_completed.append(after)
                concatenated_addresses.append(address)
        rows.append({
            "section": name,
            "vma": f"0x{section.address:04x}",
            "lma": f"0x{lma:04x}",
            "bytes": section.bytes,
            "resident_prg_offset": offset if inside else None,
            "lma_equals_vma": lma == section.address,
            "inside_resident_prg": inside,
            "identity_mismatches_outside_publish_last": identity_mismatches,
            "publish_last_values": crc_values,
        })
    require(concatenated_addresses == sorted(concatenated_addresses),
            "low-resident delivery spans are not VMA ordered")
    # Validate each actual section at its own address; no gaps become implied
    # identity exceptions merely because the four sections are discontiguous.
    for row in rows:
        section = truth.section(row["section"])
        linked = truth.section_bytes(row["section"])
        offset = 2 + section.address - load_address
        completed = image[offset:offset + len(linked)]
        validate_byte_model(linked, completed, section.address, CARVEOUT,
                            oracle_crc) if HIGH in range(
                                section.address, section.address + len(linked)) else require(
                                    completed == linked,
                                    f"non-carveout section identity drift: {row['section']}")
    report = load(WPLTO_REPORT := BUILD / "wplto/kernal-window-publish-last.json")
    require(
        report.get("declared_mutation_domain_bytes") == 2
        and [entry.get("address") for entry in report.get("binding_operands", [])]
            == list(CARVEOUT),
        "producer publish-last report domain differs from acceptance domain")
    return {
        "status": "passed-identity-plus-independent-CRC-value",
        "candidate_elf": bind(elf),
        "completed_resident_prg": bind(completed_prg),
        "load_address": f"0x{load_address:04x}",
        "sections": rows,
        "identity_bytes": sum(row["bytes"] for row in rows) - 2,
        "identity_mismatches": 0,
        "publish_last": {
            "addresses": list(CARVEOUT),
            "bytes": 2,
            "independent_window_bytes": len(window),
            "independent_window_sha256": hashlib.sha256(window).hexdigest(),
            "independent_crc16": f"0x{oracle_crc:04x}",
            "observed_values": [
                image[2 + address - load_address] for address in CARVEOUT],
            "values_correct": True,
            "producer_report": bind(WPLTO_REPORT),
        },
        "new_staging_roles": 0,
    }


def validate_delivery(value: dict[str, Any], elf: Path, prg: Path) -> None:
    expected = delivered_bytes_gate(elf, prg)
    require(value == expected, "CRC-carveout delivered-byte evidence drift")
    rows = value["sections"]
    require(
        len(rows) == 4
        and [row["section"] for row in rows]
            == list(PRODUCT.LOW_RESIDENT_LMA_SECTIONS)
        and all(row["lma_equals_vma"] and row["inside_resident_prg"]
                for row in rows)
        and all(not row["identity_mismatches_outside_publish_last"]
                for row in rows)
        and value["publish_last"]["addresses"] == list(CARVEOUT)
        and value["publish_last"]["bytes"] == 2
        and value["publish_last"]["values_correct"] is True
        and value["publish_last"]["observed_values"] == [
            int(value["publish_last"]["independent_crc16"], 16) >> 8,
            int(value["publish_last"]["independent_crc16"], 16) & 0xFF,
        ]
        and value["new_staging_roles"] == 0,
        "delivered bytes violate identity plus independent CRC contract")


def delivery_mutations(value: dict[str, Any], elf: Path, prg: Path) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "drop-section": lambda x: x["sections"].pop(),
        "rewrite-LMA": lambda x: x["sections"][0].update(lma="0x2f4a3"),
        "grow-carveout": lambda x: x["publish_last"]["addresses"].append(0xB4FB),
        "widen-carveout-bytes": lambda x: x["publish_last"].update(bytes=3),
        "replace-independent-CRC": lambda x: x["publish_last"].update(
            independent_crc16="0xa0b2"),
        "accept-wrong-high": lambda x: x["publish_last"][
            "observed_values"].__setitem__(0, 0xA1),
        "accept-wrong-low": lambda x: x["publish_last"][
            "observed_values"].__setitem__(1, 0xB2),
        "hide-identity-mismatch": lambda x: x["sections"][1][
            "identity_mismatches_outside_publish_last"].append("0xb5c4"),
        "replace-oracle-window": lambda x: x["publish_last"].update(
            independent_window_sha256="0" * 64),
        "add-staging-role": lambda x: x.update(new_staging_roles=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_delivery(candidate, elf, prg)
        except CarveoutCardError:
            rejected.append(name)
    require(rejected == list(cases), "CRC delivery mutation survived")
    return rejected


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    preflight_rejected = value.pop("preflight_mutations_rejected", None)
    validate_preflight(value)
    require(preflight_rejected == preflight_mutations(value),
            "CRC carve-out preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "CRC carve-out product card is one-shot")
    INVOCATION.write_bytes(canonical({
        "format": "lisp65-c2.3-v20-crc-carveout-invocation-v1",
        "recorded_on": RECORDED_ON,
        "status": "INVOKED: terminal outcome required",
        "authorization": authorization(),
        "preflight": bind(PREFLIGHT_RECEIPT),
        "driver": bind(DRIVER),
    }))
    artifacts = produce_candidate()
    comparison = INV.compare_elf(artifacts["elf"])
    linker_gate = PRODUCT.low_resident_lma_reset_gate(
        artifacts["linker"].read_text(encoding="utf-8"))
    delivery = delivered_bytes_gate(artifacts["elf"], artifacts["prg"])
    validate_delivery(delivery, artifacts["elf"], artifacts["prg"])
    rejected = delivery_mutations(delivery, artifacts["elf"], artifacts["prg"])
    headroom = {
        row["id"]: row["candidate_headroom_bytes"]
        for row in comparison["capacity_measurements"]
    }
    receipt = {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "PASS: VMA geometry, LMA reset and CRC-aware delivery exact",
        "attempt_accounting": {
            "cards_authorized": 1, "cards_consumed": 1,
            "wplto_runs": 1, "product_link_attempts": 1,
            "device_contacts": 0,
        },
        "acceptance": {
            "VMA_golden": comparison,
            "low_resident_linker_reset": linker_gate,
            "delivered_bytes": delivery,
            "delivery_mutations_rejected": rejected,
            "fixed_comparison_operations": 1,
            "candidate_derived_validation": True,
            "delivery_operations": 1,
            "historical_qualifiers": 0,
        },
        "producer": {
            "mechanical_completion_only": True,
            "historical_return_nonauthoritative": artifacts["producer_return"],
            "log": bind(artifacts["producer_log"]),
            "resolved_profile": bind(artifacts["resolved_profile"]),
        },
        "artifacts": {
            key: bind(artifacts[key])
            for key in ("elf", "prg", "map", "lto", "linker")
        },
        "authority": {
            "owner_authorization": authorization(),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "invocation": bind(INVOCATION),
            "driver": bind(DRIVER),
            "VMA_golden": bind(INV.GOLDEN),
        },
        "narrow_margins_are_not_budgets": {
            "ordinary_chain": headroom["low-resident-and-ordinary-chain"],
            "runtime_overlay": headroom["runtime-overlay-slices"],
            "bank0_state": headroom["owned-bank0-state"],
        },
        "next_gate": (
            "Regenerate current-world media closure and loudly retire the "
            "Link-97 closure before the D1-D5 session."),
        "claim_limit": (
            "One host-only card. No media, device, release, publication or "
            "parity claim."),
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.0 CRC carve-out card: PASS "
          f"sections={comparison['allocatable_sections']} "
          f"boundaries={comparison['fixed_boundary_symbols']} "
          "LMA=4/4 identity+CRC=passed mutations=10 "
          f"margins={headroom['low-resident-and-ordinary-chain']}/"
          f"{headroom['runtime-overlay-slices']}/"
          f"{headroom['owned-bank0-state']} wplto=1 device=0")


def record_final_red(error: BaseException) -> None:
    require(not RECEIPT.exists() and not FINAL_RED.exists(),
            "CRC carve-out terminal result is immutable")
    artifacts: dict[str, dict[str, Any]] = {}
    for name, relative in {
        "elf": "wplto/lisp65-c2-substitution-linked.prg.elf",
        "prg": "wplto/lisp65-c2-substitution-linked.prg",
        "map": "wplto/lisp65-c2-substitution-linked.prg.map",
        "lto": "wplto/resident-island-seed.prg.lto.o",
        "linker": "wplto/c2-substitution.ld",
        "publish_last": "wplto/kernal-window-publish-last.json",
        "producer_log": "receipts/v20-producer.log",
    }.items():
        path = BUILD / relative
        if path.is_file():
            artifacts[name] = bind(path)
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v20-crc-carveout-card-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: sole CRC-carveout card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {
            "cards_authorized": 1, "cards_consumed": 1,
            "wplto_runs": int((BUILD / "wplto").exists()),
            "product_link_attempts": int((BUILD / "wplto").exists()),
            "device_contacts": 0,
        },
        "retry_authorized": False,
        "owner_disposition_required": True,
        "artifacts": artifacts,
        "authority": {
            "owner_authorization": authorization(),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "invocation": bind(INVOCATION),
            "driver": bind(DRIVER),
        },
        "claim_limit": "The sole authorized CRC-carveout card is consumed.",
    }))


def selftest() -> None:
    authorization(); prior_authority(); INV.selftest()
    require(len(byte_model_selftest()) == 8,
            "CRC carve-out model mutation count drift")
    require(len(PRODUCT.low_resident_lma_reset_mutation_selftest()) == 7,
            "LMA reset mutation count drift")
    print("2.0 CRC carve-out card: SELFTEST PASS "
          "carveout=2 model-mutations=8 card=one")


def check() -> None:
    selftest()
    require(not (RECEIPT.exists() and FINAL_RED.exists()),
            "CRC carve-out card has two terminal outcomes")
    if FINAL_RED.exists():
        red = load(FINAL_RED)
        require(red.get("retry_authorized") is False
                and red.get("owner_disposition_required") is True,
                "CRC carve-out Final-Red disposition drift")
        print("2.0 CRC carve-out card: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        print("2.0 CRC carve-out card: CHECK ARMED card=unused")
        return
    value = load(RECEIPT)
    require(
        value.get("status")
            == "PASS: VMA geometry, LMA reset and CRC-aware delivery exact"
        and value.get("attempt_accounting", {}).get("cards_consumed") == 1
        and value.get("acceptance", {}).get("historical_qualifiers") == 0
        and value.get("acceptance", {}).get("delivered_bytes", {}).get(
            "publish_last", {}).get("addresses") == list(CARVEOUT)
        and len(value.get("acceptance", {}).get(
            "delivery_mutations_rejected", [])) == 10,
        "green CRC carve-out card receipt drift")
    print("2.0 CRC carve-out card: CHECK PASS "
          "golden=green LMA=4/4 delivery=identity+independent-CRC")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("selftest", "preflight", "card", "check"))
    {"selftest": selftest, "preflight": preflight,
     "card": card, "check": check}[parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_final_red(error)
            except Exception as receipt_error:
                print("2.0 CRC carve-out card: receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"2.0 CRC carve-out card: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
