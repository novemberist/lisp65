#!/usr/bin/env python3
"""Run the last selector-bypass replacement with derived receipt adapters."""

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

import c2_v160_boot_refill_selector_bypass_dual_capacity_replacement_card as DUAL  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-boot-refill-selector-bypass-adapter-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-boot-refill-selector-bypass-adapter-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-boot-refill-selector-bypass-adapter-process"
INHERITED_PROCESS = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-adapter-inherited-process")
RECEIPT = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-adapter-card-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-adapter-card-final-red.json")
PREVIOUS_RED = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-dual-capacity-card-final-red.json")
PREVIOUS_PARTIAL = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-dual-capacity-card-receipt.json")
PREVIOUS_ELF = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-dual-capacity-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "e554555c"
FORMAT = "lisp65-c2-v160-boot-refill-selector-bypass-adapter-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 SELECTOR BYPASS ADAPTER REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 SELECTOR BYPASS ADAPTER FINAL WORLD GREEN"


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
    for token in ("third and last self-disposition", "exactly one replacement card",
                  "consume the three gate-carried", "any further red returns"):
        require(token in text, f"adapter replacement authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def validate_adapter_gate(gate: dict[str, Any]) -> None:
    for name in ("ordinary", "mapped_diagnostic", "existing_far_service"):
        row = gate[name]
        require(row["free_bytes"] >= row["floor_bytes"],
                f"receipt adapter rejects {name} capacity floor")


def adapter_mutations(gate: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-adapter-ordinary-113-pin": lambda x: x["ordinary"].update(
            floor_bytes=113),
        "restore-adapter-far-15-pin": lambda x: x["existing_far_service"].update(
            floor_bytes=15),
        "ordinary-below-carried-floor": lambda x: x["ordinary"].update(
            free_bytes=x["ordinary"]["floor_bytes"] - 1),
        "far-below-carried-floor": lambda x: x["existing_far_service"].update(
            free_bytes=x["existing_far_service"]["floor_bytes"] - 1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(gate); mutate(trial)
        try:
            validate_adapter_gate(trial)
        except RuntimeError:
            rejected.append(name)
    require(rejected == list(cases), "receipt-adapter mutation survived")
    return rejected


def predecessor() -> dict[str, Any]:
    red = load(PREVIOUS_RED); partial = load(PREVIOUS_PARTIAL)
    gate = partial["nested_MAP_swap"]
    require(red["status"] ==
                "FINAL RED: V1.6 SELECTOR BYPASS DUAL CAPACITY STOPS"
            and red["error"]["message"] == "nested-MAP swap final receipt drift"
            and red["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_link_attempts": 1,
                "media_builds": 0, "device_contacts": 0}
            and partial["status"] ==
                "PASS: V1.6 SELECTOR BYPASS DUAL CAPACITY FINAL WORLD GREEN"
            and gate["ordinary"] == {"disk_stub_bytes": 12,
                "floor_bytes": 18, "free_bytes": 18, "installer_bytes": 211}
            and gate["mapped_diagnostic"]["free_bytes"] == 47
            and gate["mapped_diagnostic"]["floor_bytes"] == 47
            and gate["existing_far_service"]["free_bytes"] == 11
            and gate["existing_far_service"]["floor_bytes"] == 11,
            "receipt-adapter predecessor drift")
    validate_adapter_gate(gate)
    return {"dual_capacity_Final_Red": bind(PREVIOUS_RED),
            "linked_partial_receipt": bind(PREVIOUS_PARTIAL),
            "linked_candidate_ELF": bind(PREVIOUS_ELF),
            "linked_gate_capacity": {
                name: {"free_bytes": gate[name]["free_bytes"],
                       "floor_bytes": gate[name]["floor_bytes"]}
                for name in ("ordinary", "mapped_diagnostic",
                             "existing_far_service")},
            "adapter_mutations_rejected": adapter_mutations(gate)}


def install() -> None:
    DUAL.BUILD = BUILD
    DUAL.PREFLIGHT = PREFLIGHT
    DUAL.PROCESS = PROCESS
    DUAL.INHERITED_PROCESS = INHERITED_PROCESS
    DUAL.RECEIPT = RECEIPT
    DUAL.FINAL_RED = FINAL_RED
    DUAL.PREVIOUS_RED = PREVIOUS_RED
    DUAL.PREVIOUS_PARTIAL = PREVIOUS_PARTIAL
    DUAL.PREVIOUS_ELF = PREVIOUS_ELF
    DUAL.DRIVER = DRIVER
    DUAL.AUTHORIZATION = AUTHORIZATION
    DUAL.FORMAT = FORMAT
    DUAL.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    DUAL.FINAL_STATUS = FINAL_STATUS
    DUAL.authority = authority
    DUAL.predecessor = predecessor
    DUAL.install()


def append_preflight() -> None:
    path = PREFLIGHT / "preflight.json"
    value = load(path)
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "adapter_replacement_authority": authority(),
        "adapter_predecessor": predecessor(),
        "receipt_adapter_rule": "free_bytes >= gate-carried floor_bytes",
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0}})
    path.write_bytes(canonical(value))


def preflight() -> None:
    require(not any(path.exists() for path in
        (BUILD, PREFLIGHT, PROCESS, INHERITED_PROCESS, RECEIPT, FINAL_RED)),
        "selector-bypass adapter replacement is one-shot")
    predecessor(); authority(); DUAL.preflight(); append_preflight()
    print("v1.6 selector bypass adapter: PREFLIGHT PASS card=0/1")


def check_receipt() -> dict[str, Any]:
    value = load(RECEIPT)
    gate = value["nested_MAP_swap"]
    validate_adapter_gate(gate)
    require(value["status"] == FINAL_STATUS
            and value["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_links": 1,
                "media_builds": 0, "device_contacts": 0}
            and value["receipt_adapter_conversion"]["rule"] ==
                "free_bytes >= gate-carried floor_bytes"
            and value["receipt_adapter_conversion"]["mutations_rejected"] == [
                "restore-adapter-ordinary-113-pin",
                "restore-adapter-far-15-pin",
                "ordinary-below-carried-floor", "far-below-carried-floor"]
            and value["boot_refill_selector_bypass"]["product_entry"][
                "direct_MAP_CPU_edges"] == 1
            and value["boot_refill_selector_bypass"]["product_entry"][
                "selector_edges"] == 0,
            "selector-bypass adapter replacement receipt drift")
    DUAL.GATE.validate_final(value["boot_refill_selector_bypass"])
    return value


def card() -> None:
    predecessor(); authority()
    pre = load(PREFLIGHT / "preflight.json")
    require(pre["status"] == PREFLIGHT_STATUS,
            "persisted adapter replacement preflight drift")
    DUAL.card()
    value = load(RECEIPT); gate = value["nested_MAP_swap"]
    value.update({"format": FORMAT, "status": FINAL_STATUS,
        "adapter_replacement_authority": authority(),
        "adapter_predecessor": predecessor(),
        "receipt_adapter_conversion": {
            "rule": "free_bytes >= gate-carried floor_bytes",
            "capacities": {name: {"free_bytes": gate[name]["free_bytes"],
                                  "floor_bytes": gate[name]["floor_bytes"]}
                for name in ("ordinary", "mapped_diagnostic",
                             "existing_far_service")},
            "mutations_rejected": adapter_mutations(gate)},
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "media_authorized": False, "device_contacts": 0,
        "next": "scope, acceptance, artifact-only media, seam confirmation"})
    RECEIPT.write_bytes(canonical(value)); check_receipt()
    print("v1.6 selector bypass adapter: CARD PASS final-world=green")


def record_red(error: Exception) -> None:
    FINAL_RED.write_bytes(canonical({"format": FORMAT + "-final-red",
        "status": "FINAL RED: V1.6 SELECTOR BYPASS ADAPTER REPLACEMENT STOPS",
        "error": {"type": type(error).__name__, "message": str(error)},
        "adapter_replacement_authority": authority(),
        "adapter_predecessor": predecessor(),
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "media_builds": 0,
            "device_contacts": 0},
        "retry_authorized": False, "media_authorized": False,
        "next": "reviewer disposition with complete three-card chain"}))


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight": preflight(); return 0
    if action == "card": card(); return 0
    if action == "check":
        check_receipt(); print("v1.6 selector bypass adapter: CHECK PASS"); return 0
    return DUAL.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"adapter replacement Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 selector bypass adapter: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
