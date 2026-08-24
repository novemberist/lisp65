#!/usr/bin/env python3
"""Run the selector bypass with both capacity axes predecessor-derived."""

from __future__ import annotations

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

import c2_v160_boot_refill_selector_bypass as GATE  # noqa: E402
import c2_v160_boot_refill_selector_bypass_card as FIRST  # noqa: E402
import c2_v160_nested_map_swap as SWAP  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-boot-refill-selector-bypass-dual-capacity-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-boot-refill-selector-bypass-dual-capacity-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-boot-refill-selector-bypass-dual-capacity-process"
INHERITED_PROCESS = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-dual-capacity-inherited-process")
RECEIPT = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-dual-capacity-card-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-dual-capacity-card-final-red.json")
PREVIOUS_RED = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-capacity-replacement-card-final-red.json")
PREVIOUS_PARTIAL = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-capacity-replacement-card-receipt.json")
ACCEPTED_RECEIPT = ARCH / (
    "c2.3-v1.6-recovery-sanitization-library-replacement-card-receipt.json")
ACCEPTED_ELF = ROOT / (
    "build/c2.3/v1.6-recovery-sanitization-library-replacement-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
PREVIOUS_ELF = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-capacity-replacement-card/"
    "wplto/lisp65-c2-substitution-linked.prg.elf")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "b938bed0"
FORMAT = "lisp65-c2-v160-boot-refill-selector-bypass-dual-capacity-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 SELECTOR BYPASS DUAL CAPACITY ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 SELECTOR BYPASS DUAL CAPACITY FINAL WORLD GREEN"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").replace("`", "").split())
    for token in ("second self-disposition", "exactly one further replacement card",
                  "ordinary text derives 18", "far service derives 11",
                  "restoring either historical pin"):
        require(token in text, f"dual-capacity authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def geometry(elf: Path) -> tuple[int, int, dict[str, tuple[int, int]]]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    service = truth.section(".lisp65_c2_mapped_far_service")
    return (facade.address - (text.address + text.bytes),
            SWAP.FAR_CAPACITY - service.bytes,
            {row.name: (row.address, row.bytes) for row in truth.sections})


def capacity_authority() -> dict[str, Any]:
    receipt = load(ACCEPTED_RECEIPT)
    accepted_ordinary, accepted_far, accepted_geometry = geometry(ACCEPTED_ELF)
    previous_ordinary, previous_far, previous_geometry = geometry(PREVIOUS_ELF)
    value = {"authority": "accepted-predecessor-final-ELF-plus-two-capacity-receipts",
        "accepted_ELF": bind(ACCEPTED_ELF),
        "accepted_receipt": bind(ACCEPTED_RECEIPT),
        "accepted_ELF_ordinary_free_bytes": accepted_ordinary,
        "accepted_receipt_ordinary_free_bytes": receipt["placement"][
            "ordinary_text_reserve_bytes"],
        "accepted_ELF_far_free_bytes": accepted_far,
        "accepted_receipt_far_free_bytes": receipt["active_frame_final_gate"][
            "far_service"]["free_bytes"],
        "previous_replacement_ELF": bind(PREVIOUS_ELF),
        "previous_replacement_ordinary_free_bytes": previous_ordinary,
        "previous_replacement_far_free_bytes": previous_far,
        "section_count": len(accepted_geometry),
        "section_geometry_identical": accepted_geometry == previous_geometry,
        "derived_ordinary_floor_bytes": accepted_ordinary,
        "derived_no_regression_floor_bytes": accepted_ordinary,
        "derived_far_floor_bytes": accepted_far,
        "historical_pins": {"ordinary_free_bytes": 113,
                            "far_free_bytes": 15}}
    validate_capacity(value)
    return value


def validate_capacity(value: dict[str, Any]) -> None:
    require(value.get("authority") ==
                "accepted-predecessor-final-ELF-plus-two-capacity-receipts"
            and value.get("accepted_ELF_ordinary_free_bytes") == 18
            and value.get("accepted_receipt_ordinary_free_bytes") == 18
            and value.get("accepted_ELF_far_free_bytes") == 11
            and value.get("accepted_receipt_far_free_bytes") == 11
            and value.get("previous_replacement_ordinary_free_bytes") >= 18
            and value.get("previous_replacement_far_free_bytes") >= 11
            and value.get("derived_ordinary_floor_bytes") == 18
            and value.get("derived_no_regression_floor_bytes") == 18
            and value.get("derived_far_floor_bytes") == 11
            and value.get("section_count") == 199
            and value.get("section_geometry_identical") is True,
            "dual accepted-world capacity conversion drift")


def capacity_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-historical-ordinary-113-pin": lambda x: x.update(
            derived_ordinary_floor_bytes=113),
        "restore-historical-far-15-pin": lambda x: x.update(
            derived_far_floor_bytes=15),
        "consume-ordinary-below-predecessor": lambda x: x.update(
            previous_replacement_ordinary_free_bytes=17),
        "consume-far-below-predecessor": lambda x: x.update(
            previous_replacement_far_free_bytes=10),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_capacity(trial)
        except RuntimeError:
            rejected.append(name)
    require(rejected == list(cases), "dual-capacity mutation survived")
    return rejected


def predecessor() -> dict[str, Any]:
    red = load(PREVIOUS_RED); partial = load(PREVIOUS_PARTIAL)
    require(red["status"] ==
                "FINAL RED: V1.6 SELECTOR BYPASS CAPACITY REPLACEMENT STOPS"
            and red["error"]["message"] ==
                "final linked swap violates candidate-derived capacity floors"
            and red["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_link_attempts": 1,
                "media_builds": 0, "device_contacts": 0}
            and partial["status"] ==
                "PASS: V1.6 SELECTOR BYPASS FINAL WORLD GREEN",
            "dual-capacity predecessor drift")
    return {"ordinary_capacity_replacement_Final_Red": bind(PREVIOUS_RED),
            "linked_partial_receipt": bind(PREVIOUS_PARTIAL),
            "dual_capacity_attribution": capacity_authority()}


def final_capacity(elf: Path) -> dict[str, Any]:
    ordinary, far, rows = geometry(elf)
    authority_value = capacity_authority()
    value = {"authority": authority_value["authority"],
        "derived_ordinary_floor_bytes": 18, "candidate_ordinary_free_bytes": ordinary,
        "derived_far_floor_bytes": 11, "candidate_far_free_bytes": far,
        "candidate_section_count": len(rows),
        "passes": ordinary >= 18 and far >= 11}
    require(value["passes"] is True and ordinary == 18 and far == 11,
            "dual-capacity candidate consumed accepted reserve")
    return value


def check_receipt() -> dict[str, Any]:
    value = load(RECEIPT)
    capacity = value["capacity_floor_conversion"]
    require(value["status"] == FINAL_STATUS
            and value["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_links": 1,
                "media_builds": 0, "device_contacts": 0}
            and capacity == {"authority":
                "accepted-predecessor-final-ELF-plus-two-capacity-receipts",
                "derived_ordinary_floor_bytes": 18,
                "candidate_ordinary_free_bytes": 18,
                "derived_far_floor_bytes": 11,
                "candidate_far_free_bytes": 11,
                "candidate_section_count": 199, "passes": True}
            and value["boot_refill_selector_bypass"]["product_entry"][
                "direct_MAP_CPU_edges"] == 1
            and value["boot_refill_selector_bypass"]["product_entry"][
                "selector_edges"] == 0,
            "dual-capacity selector-bypass receipt drift")
    GATE.validate_final(value["boot_refill_selector_bypass"])
    return value


def install() -> None:
    capacity = capacity_authority()
    SWAP.ORDINARY_FREE_FLOOR = capacity["derived_ordinary_floor_bytes"]
    SWAP.FAR_FREE_FLOOR = capacity["derived_far_floor_bytes"]
    GATE.install_inherited_gate()
    FIRST.PREV.CARD.BUILD = BUILD
    FIRST.PREV.CARD.PREFLIGHT = PREFLIGHT
    FIRST.PREV.CARD.PROCESS = PROCESS
    FIRST.PREV.CARD.INHERITED_PROCESS = INHERITED_PROCESS
    FIRST.PREV.CARD.RECEIPT = RECEIPT
    FIRST.PREV.CARD.FINAL_RED = FINAL_RED
    FIRST.PREV.CARD.DRIVER = DRIVER
    FIRST.PREV.CARD.AUTHORIZATION = AUTHORIZATION
    FIRST.PREV.CARD.FORMAT = FORMAT
    FIRST.PREV.CARD.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    FIRST.PREV.CARD.FINAL_STATUS = FINAL_STATUS
    FIRST.PREV.CARD.EXPECTED_LANDING_BYTES = 32
    FIRST.PREV.CARD.authority = authority
    FIRST.PREV.CARD.predecessor = predecessor
    FIRST.PREV.CARD.install()
    FIRST.PREV.authority = authority
    FIRST.PREV.predecessor = predecessor
    FIRST.PREV.install = install
    FIRST.PREV.FORMAT = FORMAT
    FIRST.PREV.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    FIRST.PREV.FINAL_STATUS = FINAL_STATUS
    FIRST.BUILD = BUILD
    FIRST.PREFLIGHT = PREFLIGHT
    FIRST.PROCESS = PROCESS
    FIRST.INHERITED_PROCESS = INHERITED_PROCESS
    FIRST.RECEIPT = RECEIPT
    FIRST.FINAL_RED = FINAL_RED
    FIRST.AUTHORIZATION = AUTHORIZATION
    FIRST.FORMAT = FORMAT
    FIRST.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    FIRST.FINAL_STATUS = FINAL_STATUS
    FIRST.authority = authority
    FIRST.predecessor = predecessor
    FIRST.install = install


def append_preflight() -> None:
    path = PREFLIGHT / "preflight.json"
    value = load(path)
    capacity = capacity_authority()
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "dual_capacity_authority": authority(), "predecessor": predecessor(),
        "dual_capacity_floor_conversion": capacity,
        "dual_capacity_mutations_rejected": capacity_mutations(capacity),
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0}})
    path.write_bytes(canonical(value))


def preflight() -> None:
    require(not any(path.exists() for path in
        (BUILD, PREFLIGHT, PROCESS, INHERITED_PROCESS, RECEIPT, FINAL_RED)),
        "dual-capacity selector-bypass card is one-shot")
    predecessor(); authority(); capacity_mutations(capacity_authority())
    FIRST.preflight(); append_preflight()
    print("v1.6 selector bypass dual capacity: PREFLIGHT PASS card=0/1")


def card() -> None:
    predecessor(); authority()
    pre = load(PREFLIGHT / "preflight.json")
    require(pre["status"] == PREFLIGHT_STATUS
            and pre["dual_capacity_floor_conversion"][
                "derived_ordinary_floor_bytes"] == 18
            and pre["dual_capacity_floor_conversion"][
                "derived_far_floor_bytes"] == 11,
            "persisted dual-capacity preflight drift")
    FIRST.card()
    elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    value = load(RECEIPT)
    value.update({"format": FORMAT, "status": FINAL_STATUS,
        "dual_capacity_authority": authority(), "predecessor": predecessor(),
        "capacity_floor_conversion": final_capacity(elf),
        "capacity_mutations_rejected": pre[
            "dual_capacity_mutations_rejected"],
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "media_authorized": False, "device_contacts": 0,
        "next": "scope, acceptance, artifact-only media, seam confirmation"})
    RECEIPT.write_bytes(canonical(value)); check_receipt()
    print("v1.6 selector bypass dual capacity: CARD PASS final-world=green")


def record_red(error: Exception) -> None:
    FINAL_RED.write_bytes(canonical({"format": FORMAT + "-final-red",
        "status": "FINAL RED: V1.6 SELECTOR BYPASS DUAL CAPACITY STOPS",
        "error": {"type": type(error).__name__, "message": str(error)},
        "dual_capacity_authority": authority(), "predecessor": predecessor(),
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "media_builds": 0, "device_contacts": 0},
        "retry_authorized": False, "media_authorized": False,
        "next": "exceptionless disposition with complete chain"}))


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight": preflight(); return 0
    if action == "card": card(); return 0
    if action == "check":
        check_receipt(); print("v1.6 selector bypass dual capacity: CHECK PASS"); return 0
    return FIRST.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"dual-capacity Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 selector bypass dual capacity: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
