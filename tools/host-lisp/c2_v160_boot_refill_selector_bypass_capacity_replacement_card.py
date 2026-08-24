#!/usr/bin/env python3
"""Replace the bypass card with the accepted-world ordinary-text floor."""

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
BUILD = ROOT / "build/c2.3/v1.6-boot-refill-selector-bypass-capacity-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-boot-refill-selector-bypass-capacity-replacement-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-boot-refill-selector-bypass-capacity-replacement-process"
INHERITED_PROCESS = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-capacity-replacement-inherited-process")
RECEIPT = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-capacity-replacement-card-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-capacity-replacement-card-final-red.json")
FIRST_RED = ARCH / "c2.3-v1.6-boot-refill-selector-bypass-card-final-red.json"
FIRST_RECEIPT = ARCH / "c2.3-v1.6-boot-refill-selector-bypass-card-receipt.json"
ACCEPTED_RECEIPT = ARCH / (
    "c2.3-v1.6-recovery-sanitization-library-replacement-card-receipt.json")
ACCEPTED_ELF = ROOT / (
    "build/c2.3/v1.6-recovery-sanitization-library-replacement-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
FIRST_RED_ELF = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "de6a3af9"
FORMAT = "lisp65-c2-v160-boot-refill-selector-bypass-capacity-replacement-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 SELECTOR BYPASS CAPACITY REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 SELECTOR BYPASS FINAL WORLD GREEN"


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
    for token in ("exactly one replacement card is authorized",
                  "accepted predecessor's final elf",
                  "restored 113-byte pin", "one wplto, one product link",
                  "artifact-only media and seam-confirmation sequence"):
        require(token in text, f"capacity replacement authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def reserve(elf: Path) -> tuple[int, dict[str, tuple[int, int]]]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    geometry = {row.name: (row.address, row.bytes) for row in truth.sections}
    return facade.address - (text.address + text.bytes), geometry


def capacity_authority() -> dict[str, Any]:
    receipt = load(ACCEPTED_RECEIPT)
    accepted_free, accepted_geometry = reserve(ACCEPTED_ELF)
    red_free, red_geometry = reserve(FIRST_RED_ELF)
    recorded = receipt["placement"]["ordinary_text_reserve_bytes"]
    value = {"authority": "accepted-predecessor-final-ELF-plus-placement-receipt",
        "accepted_ELF": bind(ACCEPTED_ELF),
        "accepted_receipt": bind(ACCEPTED_RECEIPT),
        "accepted_ELF_free_bytes": accepted_free,
        "accepted_receipt_free_bytes": recorded,
        "replacement_first_red_ELF": bind(FIRST_RED_ELF),
        "replacement_first_red_free_bytes": red_free,
        "section_count": len(accepted_geometry),
        "section_geometry_identical": accepted_geometry == red_geometry,
        "derived_no_regression_floor_bytes": accepted_free,
        "historical_nested_MAP_floor_bytes": 113}
    validate_capacity(value)
    return value


def validate_capacity(value: dict[str, Any]) -> None:
    require(value.get("authority") ==
                "accepted-predecessor-final-ELF-plus-placement-receipt"
            and value.get("accepted_ELF_free_bytes") == 18
            and value.get("accepted_receipt_free_bytes") == 18
            and value.get("replacement_first_red_free_bytes") >= 18
            and value.get("derived_no_regression_floor_bytes") == 18
            and value.get("section_count") == 199
            and value.get("section_geometry_identical") is True,
            "accepted-world capacity conversion drift")


def capacity_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-historical-113-byte-pin": lambda x: x.update(
            derived_no_regression_floor_bytes=113),
        "consume-below-accepted-predecessor": lambda x: x.update(
            replacement_first_red_free_bytes=17),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_capacity(trial)
        except RuntimeError:
            rejected.append(name)
    require(rejected == list(cases), "capacity conversion mutation survived")
    return rejected


def predecessor() -> dict[str, Any]:
    red = load(FIRST_RED); partial = load(FIRST_RECEIPT)
    require(red["status"] ==
                "FINAL RED: V1.6 BOOT REFILL SELECTOR BYPASS CARD STOPS"
            and red["error"]["message"] ==
                "final linked swap violates candidate-derived capacity floors"
            and red["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_link_attempts": 1,
                "media_builds": 0, "device_contacts": 0}
            and partial["status"] ==
                "PASS: V1.6 BOOT REFILL SELECTOR BYPASS FINAL WORLD GREEN",
            "capacity replacement predecessor drift")
    return {"selector_bypass_Final_Red": bind(FIRST_RED),
            "linked_partial_receipt": bind(FIRST_RECEIPT),
            "capacity_attribution": capacity_authority()}


def install() -> None:
    capacity = capacity_authority()
    SWAP.ORDINARY_FREE_FLOOR = capacity["derived_no_regression_floor_bytes"]
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
        "capacity_replacement_authority": authority(), "predecessor": predecessor(),
        "capacity_floor_conversion": capacity,
        "capacity_mutations_rejected": capacity_mutations(capacity),
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0}})
    path.write_bytes(canonical(value))


def preflight() -> None:
    require(not any(path.exists() for path in
        (BUILD, PREFLIGHT, PROCESS, INHERITED_PROCESS, RECEIPT, FINAL_RED)),
        "selector-bypass capacity replacement is one-shot")
    predecessor(); authority(); capacity_mutations(capacity_authority())
    FIRST.preflight(); append_preflight()
    print("v1.6 selector bypass capacity replacement: PREFLIGHT PASS card=0/1")


def final_capacity(elf: Path) -> dict[str, Any]:
    free, geometry = reserve(elf)
    authority_value = capacity_authority()
    value = {"authority": authority_value["authority"],
        "derived_no_regression_floor_bytes": authority_value[
            "derived_no_regression_floor_bytes"],
        "candidate_free_bytes": free, "candidate_section_count": len(geometry),
        "passes": free >= authority_value["derived_no_regression_floor_bytes"]}
    require(value["passes"] is True and value["candidate_free_bytes"] == 18,
            "replacement candidate consumed accepted ordinary reserve")
    return value


def check_receipt() -> dict[str, Any]:
    value = load(RECEIPT)
    gate = value["boot_refill_selector_bypass"]
    capacity = value["capacity_floor_conversion"]
    require(value["status"] == FINAL_STATUS
            and value["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_links": 1,
                "media_builds": 0, "device_contacts": 0}
            and capacity == {"authority":
                "accepted-predecessor-final-ELF-plus-placement-receipt",
                "derived_no_regression_floor_bytes": 18,
                "candidate_free_bytes": 18, "candidate_section_count": 199,
                "passes": True}
            and gate["product_entry"]["direct_MAP_CPU_edges"] == 1
            and gate["product_entry"]["selector_edges"] == 0,
            "selector-bypass capacity replacement receipt drift")
    GATE.validate_final(gate)
    return value


def card() -> None:
    predecessor(); authority()
    pre = load(PREFLIGHT / "preflight.json")
    require(pre["status"] == PREFLIGHT_STATUS
            and pre["capacity_floor_conversion"][
                "derived_no_regression_floor_bytes"] == 18,
            "persisted capacity replacement preflight drift")
    FIRST.card()
    elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    value = load(RECEIPT)
    value.update({"format": FORMAT, "status": FINAL_STATUS,
        "capacity_replacement_authority": authority(), "predecessor": predecessor(),
        "capacity_floor_conversion": final_capacity(elf),
        "capacity_mutations_rejected": pre["capacity_mutations_rejected"],
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "media_authorized": False, "device_contacts": 0,
        "next": "scope, acceptance, artifact-only media, seam confirmation"})
    RECEIPT.write_bytes(canonical(value)); check_receipt()
    print("v1.6 selector bypass capacity replacement: CARD PASS final-world=green")


def record_red(error: Exception) -> None:
    FINAL_RED.write_bytes(canonical({"format": FORMAT + "-final-red",
        "status": "FINAL RED: V1.6 SELECTOR BYPASS CAPACITY REPLACEMENT STOPS",
        "error": {"type": type(error).__name__, "message": str(error)},
        "capacity_replacement_authority": authority(), "predecessor": predecessor(),
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
        check_receipt(); print("v1.6 selector bypass capacity replacement: CHECK PASS"); return 0
    return FIRST.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"capacity replacement Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 selector bypass capacity replacement: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
