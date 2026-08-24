#!/usr/bin/env python3
"""Run the authorized direct boot-refill selector-bypass card."""

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

import c2_v160_boot_refill_selector_bypass as GATE  # noqa: E402
import c2_v160_execution_boundary_recovery_sanitization_library_replacement_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-boot-refill-selector-bypass-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-boot-refill-selector-bypass-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-boot-refill-selector-bypass-process"
INHERITED_PROCESS = ROOT / "build/c2.3/v1.6-boot-refill-selector-bypass-inherited-process"
RECEIPT = ARCH / "c2.3-v1.6-boot-refill-selector-bypass-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-boot-refill-selector-bypass-card-final-red.json"
PREVIOUS_RECEIPT = ARCH / (
    "c2.3-v1.6-recovery-sanitization-library-replacement-card-receipt.json")
ATTRIBUTION = ARCH / (
    "c2.3-v1.6-recovery-sanitization-seam-first-red-attribution.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "9395f9f7"
FORMAT = "lisp65-c2-v160-boot-refill-selector-bypass-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 BOOT REFILL SELECTOR BYPASS ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 BOOT REFILL SELECTOR BYPASS FINAL WORLD GREEN"


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
    for token in ("exactly one card", "calls c2_map_cpu_read directly",
                  "permanent final-elf gate covers the selector totally",
                  "retirement is in scope", "green re-runs the media sequence"):
        require(token in text, f"selector-bypass authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    previous = load(PREVIOUS_RECEIPT)
    attribution = load(ATTRIBUTION)
    require(previous["status"] ==
                "PASS: V1.6 RECOVERY SANITIZATION SEMANTIC FINAL WORLD GREEN"
            and attribution["status"] ==
                "ATTRIBUTED: THIRD FACADE CALLER FALLS THROUGH TO WRONG OVERLAY SINK"
            and attribution["mechanical_decision"]["boot_hardware_pushed_return"]
                == "0xa10b"
            and attribution["mechanical_decision"]["actual_sink"].startswith(
                "vm_runtime_overlay_exec"),
            "selector-bypass predecessor drift")
    return {"recovery_sanitization_final_world": bind(PREVIOUS_RECEIPT),
            "seam_First_Red_attribution": bind(ATTRIBUTION)}


def install() -> None:
    GATE.install_inherited_gate()
    PREV.CARD.BUILD = BUILD
    PREV.CARD.PREFLIGHT = PREFLIGHT
    PREV.CARD.PROCESS = PROCESS
    PREV.CARD.INHERITED_PROCESS = INHERITED_PROCESS
    PREV.CARD.RECEIPT = RECEIPT
    PREV.CARD.FINAL_RED = FINAL_RED
    PREV.CARD.DRIVER = DRIVER
    PREV.CARD.AUTHORIZATION = AUTHORIZATION
    PREV.CARD.FORMAT = FORMAT
    PREV.CARD.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    PREV.CARD.FINAL_STATUS = FINAL_STATUS
    PREV.CARD.EXPECTED_LANDING_BYTES = 32
    PREV.CARD.authority = authority
    PREV.CARD.predecessor = predecessor
    PREV.CARD.install()
    PREV.authority = authority
    PREV.predecessor = predecessor
    PREV.install = install
    PREV.FORMAT = FORMAT
    PREV.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    PREV.FINAL_STATUS = FINAL_STATUS


def append_preflight() -> None:
    path = PREFLIGHT / "preflight.json"
    value = load(path)
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "selector_bypass_authority": authority(), "predecessor": predecessor(),
        "selector_bypass_source_gate": GATE.source_gate(),
        "source_mutations_rejected": GATE.source_mutations(),
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0}})
    path.write_bytes(canonical(value))


def preflight() -> None:
    require(not any(path.exists() for path in
        (BUILD, PREFLIGHT, PROCESS, INHERITED_PROCESS, RECEIPT, FINAL_RED)),
        "selector-bypass card is one-shot")
    predecessor(); authority(); GATE.source_gate(); GATE.source_mutations()
    PREV.preflight(); append_preflight()
    print("v1.6 boot refill selector bypass: PREFLIGHT PASS card=0/1")


def check_receipt() -> dict[str, Any]:
    value = load(RECEIPT)
    gate = value["boot_refill_selector_bypass"]
    require(value["status"] == FINAL_STATUS
            and value["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_links": 1,
                "media_builds": 0, "device_contacts": 0}
            and gate["product_entry"]["direct_MAP_CPU_edges"] == 1
            and gate["product_entry"]["selector_edges"] == 0
            and gate["unsafe_content_DMA_count"] == 0
            and gate["selector_totality"]["violations"] == []
            and gate["selector_retirement"]["current_fallback_callers"] == 0
            and gate["selector_retirement"]["current_reader_callers"] == 2,
            "selector-bypass final receipt drift")
    GATE.validate_final(gate)
    return value


def card() -> None:
    predecessor(); authority()
    pre = load(PREFLIGHT / "preflight.json")
    require(pre["status"] == PREFLIGHT_STATUS
            and pre["selector_bypass_source_gate"]["selector_dependency"] is False,
            "persisted selector-bypass preflight drift")
    PREV.card()
    elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    gate = GATE.linked_read_model(elf)
    GATE.validate_final(gate)
    value = load(RECEIPT)
    value.update({"format": FORMAT, "status": FINAL_STATUS,
        "selector_bypass_authority": authority(), "predecessor": predecessor(),
        "selector_bypass_source_gate": pre["selector_bypass_source_gate"],
        "emitted_selector_bypass_gate": GATE.generated_source_gate(
            BUILD / "wplto/generated-product-sources/c2_product_runtime.c"),
        "boot_refill_selector_bypass": gate,
        "mutations_rejected": {"source": pre["source_mutations_rejected"],
                               "final": GATE.final_mutations(gate)},
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "media_authorized": False, "device_contacts": 0,
        "next": "scope, acceptance, artifact-only media, seam confirmation"})
    RECEIPT.write_bytes(canonical(value))
    check_receipt()
    print("v1.6 boot refill selector bypass: CARD PASS final-world=green")


def record_red(error: Exception) -> None:
    FINAL_RED.write_bytes(canonical({"format": FORMAT + "-final-red",
        "status": "FINAL RED: V1.6 BOOT REFILL SELECTOR BYPASS CARD STOPS",
        "error": {"type": type(error).__name__, "message": str(error)},
        "selector_bypass_authority": authority(), "predecessor": predecessor(),
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
        check_receipt(); print("v1.6 boot refill selector bypass: CHECK PASS"); return 0
    return PREV.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"selector-bypass Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 boot refill selector bypass: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
