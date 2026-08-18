#!/usr/bin/env python3
"""Attribute the Final Red of the local-return-identity card."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_lite_v6_bank3_artifact_completion as STAGE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v2.1-local-return-identity-card/wplto"
ELF = BUILD / "lisp65-c2-substitution-linked.prg.elf"
FINAL_RED = ARCH / "c2.3-v2.1-local-return-identity-card-final-red.json"
PREDECESSOR = ARCH / (
    "c2.3-v2.1-text-recovery-replacement-card-red-attribution-receipt.json")
RECEIPT = ARCH / (
    "c2.3-v2.1-local-return-identity-card-red-attribution-receipt.json")
LEGACY = ROOT / "tools/host-lisp/c2_lite_v6_link50_persistent_header_successor_link.py"
MODERN = ROOT / "tools/host-lisp/c2_v150_qualification_ambient_closure.py"
CARD_DRIVER = ROOT / "tools/host-lisp/c2_v21_local_return_identity_card.py"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
RECORDED_ON = "2026-08-14"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


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


def call_identity(truth: ElfTruth, name: str, tail: bytes) -> dict[str, Any]:
    fn = truth.symbol(name)
    vector = truth.symbol("c2_facade_runtime_overlay_exec")
    section = truth.section(fn.section)
    body = truth.section_bytes(fn.section)[
        fn.value - section.address:fn.value - section.address + fn.bytes]
    pattern = bytes((0x20, vector.value & 0xFF, vector.value >> 8)) + tail
    matches = [at for at in range(len(body) - len(pattern) + 1)
               if body[at:at + len(pattern)] == pattern]
    require(len(matches) == 1, f"emitted call identity drift: {name}")
    pushed = fn.value + matches[0] + 2
    return {"function": name, "entry": f"0x{fn.value:04x}",
            "emitted_bytes": pattern.hex(),
            "hardware_pushed_return": f"0x{pushed:04x}",
            "entry_offset": pushed - fn.value}


def derive() -> dict[str, Any]:
    red = load(FINAL_RED)
    predecessor = load(PREDECESSOR)
    require(
        red.get("status")
            == "FINAL RED: local-return-identity card returns to owner"
        and red.get("retry_authorized") is False
        and red.get("owner_disposition_required") is True
        and red["attempt_accounting"] == {
            "replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "media_builds": 0,
            "device_contacts": 0}
        and predecessor.get("status")
            == "ATTRIBUTED FINAL RED: exported intra-function labels split ownership",
        "local-return card/predecessor disposition drift")
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    binding = truth.section(".lisp65_runtime_overlay_verifier_bindings")
    publish = load(BUILD / "runtime-verifier-publish-last.json")
    total = load(BUILD / "total-publish-last-domain.json")
    kernal = load(BUILD / "kernal-freedom-link.json")
    flow = kernal["control_flow_ownership"]
    require((binding.address, binding.bytes) == (0xB98C, 40)
            and publish["status"] == total["status"] == "passed"
            and publish["address"] == publish["expected_address"]
                == binding.address
            and flow["violations"] == []
            and flow["same_function_basic_block_jumps"] >= 7,
            "candidate completion/ownership did not pass before Final Red")
    require(not truth.symbols_by_name.get("c2_stream_c2d_read_return")
            and not truth.symbols_by_name.get("c2_stream_shelf_read_return"),
            "return-label promotion survived in linked ELF")
    c2d = call_identity(truth, "c2_stream_c2d_read", bytes.fromhex("aa"))
    shelf = call_identity(truth, "c2_stream_shelf_read", bytes.fromhex("8510"))
    selector = truth.symbol("c2_map_cpu_selector")
    selector_section = truth.section(selector.section)
    selector_raw = truth.section_bytes(selector.section)[
        selector.value - selector_section.address:
        selector.value - selector_section.address + selector.bytes]
    c2d_pc = int(c2d["hardware_pushed_return"], 16)
    shelf_pc = int(shelf["hardware_pushed_return"], 16)
    selector_match = (selector_raw[7] == c2d_pc >> 8
                      and selector_raw[14] == (c2d_pc & 0xFF)
                      and selector_raw[20] == shelf_pc >> 8
                      and selector_raw[27] == (shelf_pc & 0xFF))
    require(c2d["entry_offset"] == 0x4B and shelf["entry_offset"] == 0xB0
            and selector.bytes == 40 and selector_match,
            "local emitted selector identity is not green")
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    require(facade.address - (text.address + text.bytes) == 24,
            "resident reserve changed")

    legacy = LEGACY.read_text(encoding="utf-8")
    modern = MODERN.read_text(encoding="utf-8")
    require("stage = BASE.ART.stage_product_gate(elf)" in legacy
            and "ART.stage_product_gate(elf, verifier_base=verifier_base)"
                in modern
            and "repinned 40-byte section geometry drift"
                in red["error"]["message"]
            and STAGE.VERIFIER_BASE == 0xB9CD,
            "replacement-stage verifier-base mechanism drift")
    return {
        "format": "lisp65-c2.3-v2.1-local-return-red-attribution-v1",
        "recorded_on": RECORDED_ON,
        "status": (
            "ATTRIBUTED FINAL RED: legacy qualification stage pins verifier base"),
        "authority": {"final_red": bind(FINAL_RED),
            "predecessor_attribution": bind(PREDECESSOR), "ELF": bind(ELF),
            "card_driver": bind(CARD_DRIVER), "legacy_consumer": bind(LEGACY),
            "modern_contract": bind(MODERN), "driver": bind(DRIVER)},
        "authorized_fix_result": {
            "status": "GREEN",
            "return_labels_global": 0,
            "identity_depends_on_global_return_label": False,
            "c2d": c2d, "shelf": shelf,
            "selector_operands_match": selector_match,
            "ownership_violations": len(flow["violations"]),
            "same_function_basic_block_jumps":
                flow["same_function_basic_block_jumps"]},
        "green_substance": {"candidate_completion_address": "0xb98c",
            "candidate_completion_bytes": binding.bytes,
            "publish_last_status": publish["status"],
            "resident_reserve_bytes": 24,
            "cold_helper_bytes": truth.symbol("c2e_w32").bytes,
            "media_builds": 0, "device_contacts": 0},
        "new_final_red": {
            "class": "QUALIFICATION-STAGE-HISTORICAL-VERIFIER-BASE",
            "consumer": "c2_lite_v6_link50_persistent_header_successor_link.corrected_replacement",
            "call_form": "stage_product_gate(elf)",
            "implicit_expected_address": "0xb9cd",
            "candidate_address": "0xb98c",
            "difference_bytes": 0xB9CD - 0xB98C,
            "modern_contract_call_form":
                "stage_product_gate(elf, verifier_base=verifier_base)",
            "product_geometry_implicated": False,
            "local_return_identity_implicated": False,
            "ownership_model_implicated": False,
            "mechanism": (
                "The legacy replacement-stage consumer invoked the Bank-3 "
                "stage gate without the candidate verifier-base argument; its "
                "captured 0xb9cd default rejected the correct 0xb98c section."),
        },
        "card_disposition": {"replacement_card_consumed": True,
            "retry_authorized": False, "owner_disposition_required": True,
            "completion_promotion_allowed": False, "media_allowed": False,
            "device_allowed": False},
        "attempt_accounting": red["attempt_accounting"],
        "claim_limit": (
            "Read-only attribution of the consumed card. Local identities, "
            "ownership and candidate publish-last are green; no retry, media, "
            "device or release claim is authorized."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value == derive(), "local-return Final Red attribution drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-global-label": lambda x: x["authorized_fix_result"].update(
            return_labels_global=1),
        "hide-selector-match": lambda x: x["authorized_fix_result"].update(
            selector_operands_match=False),
        "blame-ownership": lambda x: x["new_final_red"].update(
            ownership_model_implicated=True),
        "blame-local-identity": lambda x: x["new_final_red"].update(
            local_return_identity_implicated=True),
        "erase-pin-difference": lambda x: x["new_final_red"].update(
            difference_bytes=0),
        "authorize-retry": lambda x: x["card_disposition"].update(
            retry_authorized=True),
        "allow-media": lambda x: x["card_disposition"].update(
            media_allowed=True),
        "claim-device": lambda x: x["attempt_accounting"].update(
            device_contacts=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "local-return attribution mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "local-return attribution receipt exists")
    value = derive(); validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 local-return red attribution: PASS local=green pin=b9cd/b98c "
          "mutations=8 retry=none")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value)
    require(rejected == mutations(value),
            "local-return attribution mutation set drift")
    print("2.1 local-return red attribution: PASS local=green pin=b9cd/b98c "
          "mutations=8 retry=none")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check"),
            "usage: c2_v21_local_return_identity_red_attribution.py record|check")
    {"record": record, "check": check}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"2.1 local-return red attribution: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
