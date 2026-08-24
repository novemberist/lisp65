#!/usr/bin/env python3
"""Run the self-disposed Stored-World replacement for the nested-MAP card."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v160_nested_map_swap as SWAP  # noqa: E402
import c2_v160_nested_map_swap_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-nested-map-swap-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-nested-map-swap-replacement-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-nested-map-swap-replacement-process"
INHERITED_PROCESS = ROOT / "build/c2.3/v1.6-nested-map-swap-replacement-inherited-process"
RECEIPT = ARCH / "c2.3-v1.6-nested-map-swap-replacement-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-nested-map-swap-replacement-card-final-red.json"
PREDECESSOR_RED = ARCH / "c2.3-v1.6-nested-map-swap-card-final-red.json"
RED_ELF = (ROOT / "build/c2.3/v1.6-nested-map-swap-card/wplto/"
           "lisp65-c2-substitution-linked.prg.elf")
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2-v160-nested-map-swap-replacement-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 NESTED MAP SWAP REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 NESTED MAP SWAP REPLACEMENT FINAL WORLD GREEN"
BASE_AUTHORITY = PREV.authority


def require(value: bool, message: str) -> None:
    if not value:
        raise PREV.PREV.PREV.BASE.CARD.BASE.CardError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    base = BASE_AUTHORITY()
    plan = PLAN.read_bytes()
    require(b"Implementation card Final Red; Boot seam owner was topology-pinned"
            in plan and b"self-disposition **3/3**" in plan,
            "Stored-World self-disposition absent from live plan")
    return {"product_authority": base,
        "self_disposition": {"authority": "live-plan-before-replacement",
            "path": PLAN.relative_to(ROOT).as_posix(), "bytes": len(plan),
            "sha256": hashlib.sha256(plan).hexdigest()},
        "class": "Stored-World linked-owner topology pin",
        "budget": "3/3; no further autonomous successor"}


def predecessor() -> dict[str, Any]:
    red = PREV.PREV.PREV.BASE.CARD.BASE.load(PREDECESSOR_RED)
    require(red["status"] == "FINAL RED: V1.6 NESTED MAP SWAP CARD STOPS"
            and red["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_link_attempts": 1,
                "media_builds": 0, "device_contacts": 0},
            "nested-MAP Final Red accounting drift")
    swap = SWAP.final_gate(RED_ELF)
    boot = PRODUCT._linked_c2_lite_boot_slot_evidence(RED_ELF)
    require(swap["mapped_population"]["violations"] == []
            and boot["seam_owner"] == "vm_runtime_overlay_install_island"
            and boot["mutations_rejected"]["successor-owner-pin"] ==
                "rejected", "Stored-World conversion not proven on red ELF")
    return {"Final_Red": red, "red_ELF": bind(RED_ELF),
            "swap_exoneration": swap, "converted_boot_owner": boot}


def install() -> None:
    PREV.BUILD = BUILD
    PREV.PREFLIGHT = PREFLIGHT
    PREV.PROCESS = PROCESS
    PREV.INHERITED_PROCESS = INHERITED_PROCESS
    PREV.RECEIPT = RECEIPT
    PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER
    PREV.FORMAT = FORMAT
    PREV.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    PREV.FINAL_STATUS = FINAL_STATUS
    PREV.authority = authority
    PREV.predecessor = predecessor
    PREV.install()
    PREV.PREV.PROCESS = PROCESS
    PREV.PREV.INHERITED_PROCESS = INHERITED_PROCESS
    PREV.PREV.NORMAL_BUILD = PROCESS / "normal-build"
    PREV.PREV.NORMAL_PREFLIGHT = PROCESS / "normal-preflight"
    PREV.PREV.MUTANT_BUILD = PROCESS / "registry-only-build"
    PREV.PREV.MUTANT_PREFLIGHT = PROCESS / "registry-only-preflight"


def append_preflight() -> None:
    path = PREFLIGHT / "preflight.json"
    value = PREV.PREV.PREV.BASE.CARD.BASE.load(path)
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "replacement_authority": authority(),
        "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "red_ELF": bind(RED_ELF),
        "converted_boot_owner":
            PRODUCT._linked_c2_lite_boot_slot_evidence(RED_ELF),
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0}})
    path.write_bytes(canonical(value))


def preflight() -> None:
    require(not any(path.exists() for path in (
        BUILD, PREFLIGHT, PROCESS, INHERITED_PROCESS, RECEIPT, FINAL_RED)),
        "nested-MAP replacement card is one-shot")
    predecessor(); authority(); PREV.preflight(); append_preflight()
    print("v1.6 nested MAP replacement: PREFLIGHT PASS card=0/1 "
          "boot-owner=derived")


def check_receipt() -> dict[str, Any]:
    value = PREV.PREV.PREV.BASE.CARD.BASE.load(RECEIPT)
    gate = value["nested_MAP_swap"]
    boot = value["boot_seam_owner"]
    require(value["status"] == FINAL_STATUS
            and value["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_links": 1,
                "media_builds": 0, "device_contacts": 0}
            and gate["mapped_population"]["violations"] == []
            and gate["ordinary"]["free_bytes"] >=
                gate["ordinary"]["floor_bytes"]
            and gate["mapped_diagnostic"]["free_bytes"] >=
                gate["mapped_diagnostic"]["floor_bytes"]
            and gate["existing_far_service"]["free_bytes"] >=
                gate["existing_far_service"]["floor_bytes"]
            and boot["seam_owner"] == "vm_runtime_overlay_install_island"
            and boot["mutations_rejected"]["successor-owner-pin"] ==
                "rejected", "nested-MAP replacement receipt drift")
    return value


def card() -> None:
    predecessor(); authority()
    pre = PREV.PREV.PREV.BASE.CARD.BASE.load(PREFLIGHT / "preflight.json")
    require(pre["status"] == PREFLIGHT_STATUS,
            "persisted replacement preflight drift")
    PREV.card()
    value = PREV.PREV.PREV.BASE.CARD.BASE.load(RECEIPT)
    elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    gate = SWAP.final_gate(elf)
    gate["mutations_rejected"] = SWAP.final_mutations(gate)
    value.update({"format": FORMAT, "status": FINAL_STATUS,
        "replacement_authority": authority(),
        "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "nested_MAP_swap": gate,
        "boot_seam_owner": PRODUCT._linked_c2_lite_boot_slot_evidence(elf),
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "media_authorized": False, "device_contacts": 0,
        "next": "scope and acceptance, then artifact-only media"})
    RECEIPT.write_bytes(canonical(value))
    check_receipt()
    print("v1.6 nested MAP replacement: CARD PASS card=1/1")


def record_red(error: Exception) -> None:
    value = {"format": FORMAT + "-final-red",
        "status": "FINAL RED: V1.6 NESTED MAP SWAP REPLACEMENT STOPS",
        "error": {"type": type(error).__name__, "message": str(error)},
        "replacement_authority": authority(),
        "predecessor_Final_Red": bind(PREDECESSOR_RED),
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "media_builds": 0,
            "device_contacts": 0}, "retry_authorized": False,
        "media_authorized": False, "device_contacts": 0,
        "next": "self-disposition budget exhausted; full chain to reviewer"}
    FINAL_RED.write_bytes(canonical(value))


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight":
        preflight(); return 0
    if action == "card":
        card(); return 0
    if action == "check":
        check_receipt(); print("v1.6 nested MAP replacement: CHECK PASS"); return 0
    return PREV.main()


if __name__ == "__main__":
    install()
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"nested-MAP replacement red receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"v1.6 nested MAP replacement: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
