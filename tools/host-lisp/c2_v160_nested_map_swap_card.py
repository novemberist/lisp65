#!/usr/bin/env python3
"""Run the one authorized v1.6 nested-MAP cold-body swap card."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v160_nested_map_swap as SWAP  # noqa: E402
import c2_v160_refill_boundary_witness_replacement_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-nested-map-swap-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-nested-map-swap-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-nested-map-swap-process"
INHERITED_PROCESS = ROOT / "build/c2.3/v1.6-nested-map-swap-inherited-process"
RECEIPT = ARCH / "c2.3-v1.6-nested-map-swap-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-nested-map-swap-card-final-red.json"
PRICING = ARCH / "c2.3-v1.6-nested-map-repricing.json"
MEDIA = ARCH / "c2.3-v1.6-refill-boundary-witness-media-repair-receipt.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "f8ded60b"
FORMAT = "lisp65-c2-v160-nested-map-swap-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 NESTED MAP SWAP ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 NESTED MAP SWAP FINAL WORLD GREEN"


def require(value: bool, message: str) -> None:
    if not value:
        raise PREV.PREV.BASE.CARD.BASE.CardError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("implementation card", "transitive map-nesting gate",
                  "placement born-derived", "all standing walls",
                  "exceptionless", "known-family reds self-dispositional"):
        require(token in text, f"nested-MAP swap authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    pricing = PREV.PREV.BASE.CARD.BASE.load(PRICING)
    media = PREV.PREV.BASE.CARD.BASE.load(MEDIA)
    source = SWAP.source_gate()
    require(pricing["status"] ==
                "PRICED: VISIBLE INSTALLER VIA COLD DISK-CHAIN SWAP"
            and media["status"] ==
                "PASS: V1.6 REPAIRED FACADE TRACE CONTACT READY"
            and source["status"] == SWAP.STATUS
            and source["emitted"]["disk_chain_to_scratch"] == 12,
            "nested-MAP predecessor, media or ABI disposition drift")
    return {"pricing": pricing, "repaired_media_world": media,
            "ABI_safe_source": source}


def configure_module() -> None:
    PREV.PREV.BASE.CARD.configure_for_paths(
        PREV.PREV.BUILD, PREV.PREV.PREFLIGHT,
        tag="nested-map-swap-" + PREV.PREV.PREFLIGHT.name)
    registration = PRODUCT.configure_refill_boundary_witness()
    require(registration["selected"] is True
            and registration["allocated"] ==
                [".lisp65_c2_mapped_diagnostic"],
            "refill witness configuration was not consumed by swap world")
    if not PREV.REGISTRY_ONLY_MUTANT:
        PREV.install_real_consumer()


def _unchecked_receipt() -> dict[str, Any]:
    return PREV.PREV.BASE.CARD.BASE.load(RECEIPT)


def install() -> None:
    PREV.BUILD = BUILD
    PREV.PREFLIGHT = PREFLIGHT
    PREV.PROCESS = PROCESS
    PREV.INHERITED_PROCESS = INHERITED_PROCESS
    PREV.NORMAL_BUILD = PROCESS / "normal-build"
    PREV.NORMAL_PREFLIGHT = PROCESS / "normal-preflight"
    PREV.MUTANT_BUILD = PROCESS / "registry-only-build"
    PREV.MUTANT_PREFLIGHT = PROCESS / "registry-only-preflight"
    PREV.RECEIPT = RECEIPT
    PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER
    PREV.AUTHORIZATION = AUTHORIZATION
    PREV.FORMAT = FORMAT
    PREV.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    PREV.FINAL_STATUS = FINAL_STATUS
    PREV.authority = authority
    PREV.predecessor = predecessor
    PREV.configure_module = configure_module
    PREV.install()
    # The inherited producer remains the canonical final-world builder.  Only
    # its geometry member changes from the historical installer placement to
    # the authorized cold-body swap; historical receipt checks must not pin
    # predecessor capacities while this successor is being emitted.
    PREV.PREV.WITNESS = SWAP
    PREV.PREV.check_receipt = _unchecked_receipt
    PREV.check_receipt = _unchecked_receipt


def append_preflight() -> None:
    path = PREFLIGHT / "preflight.json"
    value = PREV.PREV.BASE.CARD.BASE.load(path)
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "swap_authority": authority(), "pricing": bind(PRICING),
        "ABI_self_disposition": SWAP.source_gate(),
        "swap_source_mutations_rejected": SWAP.source_mutations(),
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0}})
    path.write_bytes(canonical(value))


def preflight() -> None:
    require(not any(path.exists() for path in (
        BUILD, PREFLIGHT, PROCESS, INHERITED_PROCESS, RECEIPT, FINAL_RED)),
        "nested-MAP swap card is one-shot")
    predecessor(); authority(); PREV.preflight(); append_preflight()
    print("v1.6 nested MAP swap: PREFLIGHT PASS card=0/1 "
          "stub=12 A/X=preserved")


def check_receipt() -> dict[str, Any]:
    value = PREV.PREV.BASE.CARD.BASE.load(RECEIPT)
    gate = value["nested_MAP_swap"]
    require(value["status"] == FINAL_STATUS
            and value["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_links": 1,
                "media_builds": 0, "device_contacts": 0}
            and gate["status"] == SWAP.STATUS
            and gate["ordinary"]["free_bytes"] >=
                gate["ordinary"]["floor_bytes"]
            and gate["mapped_diagnostic"]["free_bytes"] >=
                gate["mapped_diagnostic"]["floor_bytes"]
            and gate["existing_far_service"]["free_bytes"] >=
                gate["existing_far_service"]["floor_bytes"]
            and gate["return_abi"]["preserved_across_leave"] is True
            and gate["mapped_population"]["violations"] == []
            and gate["composed_image"]["result_tail_blank"] is True,
            "nested-MAP swap final receipt drift")
    return value


def card() -> None:
    predecessor(); authority(); configure_module()
    preflight_value = PREV.PREV.BASE.CARD.BASE.load(PREFLIGHT / "preflight.json")
    require(preflight_value["status"] == PREFLIGHT_STATUS
            and preflight_value["ABI_self_disposition"]["return_abi"] ==
                "unsigned-int A/X preserved across MAP leave",
            "persisted nested-MAP preflight drift")
    PREV.card()
    value = PREV.PREV.BASE.CARD.BASE.load(RECEIPT)
    gate = SWAP.final_gate(
        BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf")
    gate["mutations_rejected"] = SWAP.final_mutations(gate)
    value.update({"format": FORMAT, "status": FINAL_STATUS,
        "swap_authority": authority(), "pricing": bind(PRICING),
        "preflight": bind(PREFLIGHT / "preflight.json"),
        "nested_MAP_swap": gate,
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "media_authorized": False, "device_contacts": 0,
        "next": "scope, acceptance, artifact-only media, one seam contact"})
    RECEIPT.write_bytes(canonical(value))
    check_receipt()
    print("v1.6 nested MAP swap: CARD PASS card=1/1 final-world=green")


def record_red(error: Exception) -> None:
    value = {"format": FORMAT + "-final-red",
        "status": "FINAL RED: V1.6 NESTED MAP SWAP CARD STOPS",
        "error": {"type": type(error).__name__, "message": str(error)},
        "swap_authority": authority(), "pricing": bind(PRICING),
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "media_builds": 0,
            "device_contacts": 0}, "retry_authorized": False,
        "media_authorized": False, "device_contacts": 0,
        "next": "exceptionless disposition with complete chain"}
    FINAL_RED.write_bytes(canonical(value))


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight":
        preflight(); return 0
    if action == "card":
        card(); return 0
    if action == "check":
        check_receipt(); print("v1.6 nested MAP swap: CHECK PASS"); return 0
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
                print(f"nested-MAP Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 nested MAP swap: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
