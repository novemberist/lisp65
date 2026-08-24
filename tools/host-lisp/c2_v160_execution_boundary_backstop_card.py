#!/usr/bin/env python3
"""Build the owner-authorized v1.6 execution-boundary backstop."""

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

import c2_v160_execution_boundary_backstop as GATE  # noqa: E402
import c2_v160_boot_refill_generator_template_card as PREV  # noqa: E402

ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-process"
INHERITED_PROCESS = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-inherited-process"
RECEIPT = ARCH / "c2.3-v1.6-execution-boundary-backstop-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-execution-boundary-backstop-card-final-red.json"
PRICING = ARCH / "c2.3-v1.6-execution-boundary-repricing.json"
MEMBERSHIP = ARCH / "c2.3-v1.6-boot-path-followup-result.json"
CLOSED_DMA = ARCH / "c2.3-v1.6-boot-refill-feature-union-resume.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "d168fc82"
FORMAT = "lisp65-c2-v160-execution-boundary-backstop-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 EXECUTION BOUNDARY ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 EXECUTION BOUNDARY FINAL WORLD GREEN"
EXPECTED_LANDING_BYTES = 29


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text())
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
    for token in ("backstop is v1.6 freight and an acceptance condition",
                  "completeness lives at the execution boundary",
                  "host-only re-pricing first", "then the implementation card",
                  "transitive map-nesting gate and every standing wall"):
        require(token in text, f"execution-boundary authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    pricing = load(PRICING); membership = load(MEMBERSHIP); closed = load(CLOSED_DMA)
    require(pricing["status"] == "PRICED: FITS ORDINARY TEXT WITH 28 BYTES FREE"
            and membership["membership_decision"]["instance_ordinal"] == 3
            and closed["status"] == "PASS: BOOT REFILL DMA FIX CHAIN CLOSED",
            "execution-boundary predecessor drift")
    return {"repricing": bind(PRICING), "third_instance": bind(MEMBERSHIP),
            "boot_refill_final_world": bind(CLOSED_DMA)}


def install() -> None:
    PREV.BUILD = BUILD
    PREV.PREFLIGHT = PREFLIGHT
    PREV.PROCESS = PROCESS
    PREV.INHERITED_PROCESS = INHERITED_PROCESS
    PREV.RECEIPT = RECEIPT
    PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER
    PREV.AUTHORIZATION = AUTHORIZATION
    PREV.FORMAT = FORMAT
    PREV.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    PREV.FINAL_STATUS = FINAL_STATUS
    PREV.authority = authority
    PREV.predecessor = predecessor
    PREV.install()


def append_preflight() -> None:
    path = PREFLIGHT / "preflight.json"
    value = load(path)
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "execution_boundary_authority": authority(), "predecessor": predecessor(),
        "execution_boundary_source_gate": GATE.source_gate(),
        "source_mutations_rejected": GATE.source_mutations(),
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0}})
    path.write_bytes(canonical(value))


def preflight() -> None:
    require(not any(path.exists() for path in
        (BUILD, PREFLIGHT, PROCESS, INHERITED_PROCESS, RECEIPT, FINAL_RED)),
        "execution-boundary card is one-shot")
    predecessor(); authority(); GATE.source_gate(); GATE.source_mutations()
    PREV.preflight(); append_preflight()
    print("v1.6 execution boundary: PREFLIGHT PASS card=0/1")


def check_receipt() -> dict[str, Any]:
    value = load(RECEIPT)
    gate = value["execution_boundary_backstop"]
    require(value["status"] == FINAL_STATUS
            and value["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_links": 1,
                "media_builds": 0, "device_contacts": 0}
            and gate["classifier"] == {"bytes": 60, "section": ".text"}
            and gate["cleanup_free_landing"] == {
                "bytes": EXPECTED_LANDING_BYTES, "section": ".text"}
            and gate["E000_delta_bytes"] == 0
            and gate["transitive_MAP_gate"]["violations"] == [],
            "execution-boundary final receipt drift")
    if EXPECTED_LANDING_BYTES == 32:
        recovery = gate["recovery_sanitization"]
        require(recovery["entry"] == {"bytes": 9, "section": ".text"}
                and recovery["retirement"] == {"bytes": 41,
                    "section": ".lisp65_c2_mapped_far_service"}
                and recovery["shared_saved_CSR_walker"] == {"bytes": 43,
                    "section": ".lisp65_c2_mapped_far_service", "pairs": 7}
                and recovery["dominates_longjmp"] is True
                and recovery["recovery_reaches_frame_walker"] is False
                and gate["ordinary_free_bytes"] >= 18
                and gate["mapped_far_service"]["free_bytes"] >= 11,
                "recovery-sanitization final receipt drift")
    return value


def card() -> None:
    predecessor(); authority()
    pre = load(PREFLIGHT / "preflight.json")
    require(pre["status"] == PREFLIGHT_STATUS
            and pre["execution_boundary_source_gate"]["status"].endswith(" SOURCE"),
            "execution-boundary persisted preflight drift")
    PREV.card()
    elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    gate = GATE.final_gate(elf)
    mutations = GATE.final_mutations(gate)
    value = load(RECEIPT)
    value.update({"format": FORMAT, "status": FINAL_STATUS,
        "execution_boundary_authority": authority(), "predecessor": predecessor(),
        "execution_boundary_backstop": gate,
        "mutations_rejected": {"source": pre["source_mutations_rejected"],
                               "final": mutations},
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "acceptance_condition": "retired-window BRK recovers to prompt",
        "media_authorized": False, "device_contacts": 0,
        "next": "scope and acceptance; no media before review-green"})
    RECEIPT.write_bytes(canonical(value)); check_receipt()
    print("v1.6 execution boundary: CARD PASS final-world=green card=1/1")


def record_red(error: Exception) -> None:
    FINAL_RED.write_bytes(canonical({"format": FORMAT + "-final-red",
        "status": "FINAL RED: V1.6 EXECUTION BOUNDARY CARD STOPS",
        "error": {"type": type(error).__name__, "message": str(error)},
        "execution_boundary_authority": authority(), "predecessor": predecessor(),
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "media_builds": 0, "device_contacts": 0},
        "retry_authorized": False, "media_authorized": False,
        "next": "full chain to reviewer; no autonomous successor"}))


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight": preflight(); return 0
    if action == "card": card(); return 0
    if action == "check": check_receipt(); print("v1.6 execution boundary: CHECK PASS"); return 0
    return PREV.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"execution-boundary Final Red receipt failure: {receipt_error}", file=sys.stderr)
        print(f"v1.6 execution boundary: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
