#!/usr/bin/env python3
"""Build the authorized repair at the boot-refill generator seam."""

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

import c2_v160_boot_refill_dma_closure as CLOSURE  # noqa: E402
import c2_v160_boot_refill_dma_fix_replacement_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-boot-refill-generator-template-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-boot-refill-generator-template-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-boot-refill-generator-template-process"
INHERITED_PROCESS = ROOT / (
    "build/c2.3/v1.6-boot-refill-generator-template-inherited-process")
RECEIPT = ARCH / "c2.3-v1.6-boot-refill-generator-template-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-boot-refill-generator-template-card-final-red.json"
PREDECESSOR_RED = ARCH / (
    "c2.3-v1.6-boot-refill-map-cpu-replacement-card-final-red.json")
ATTRIBUTION = ARCH / "c2.3-v1.6-boot-refill-generated-seam-attribution.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "ed6d2a0b"
FORMAT = "lisp65-c2-v160-boot-refill-generator-template-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 EMITTED BOOT REFILL MAP-CPU ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 BOOT REFILL GENERATOR FINAL WORLD GREEN"


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
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("exactly one successor card", "generator template itself",
                  "actually emitted", "zero unsafe content readers",
                  "projection-drift receipts record the named comparison"):
        require(token in text, f"generator-template authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    red = load(PREDECESSOR_RED)
    attribution = load(ATTRIBUTION)
    require(red["status"] == "FINAL RED: V1.6 BOOT REFILL REPLACEMENT STOPS"
            and red["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_link_attempts": 1,
                "media_builds": 0, "device_contacts": 0}
            and attribution["status"] ==
                "ATTRIBUTED: GENERATOR REINTRODUCES RAW BOOT REFILL"
            and attribution["decision"]["exact_writer"] ==
                "c2_lite_v6_product_probe.generate_sources"
            and attribution["successor_authorized"] is False,
            "generator-template predecessor drift")
    return {"replacement_Final_Red": bind(PREDECESSOR_RED),
            "generated_seam_attribution": bind(ATTRIBUTION)}


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


def emitted_gate(path: Path) -> dict[str, Any]:
    return CLOSURE.generated_source_gate(path)


def append_preflight() -> None:
    path = PREFLIGHT / "preflight.json"
    value = load(path)
    value.update({"format": FORMAT + "-preflight", "status": PREFLIGHT_STATUS,
        "generator_template_authority": authority(),
        "predecessor": predecessor(), "emitted_candidate_gate": emitted_gate(
            PROCESS / "normal-build/wplto/generated-product-sources/"
            "c2_product_runtime.c"),
        "projection_drift_contract": {
            "named_comparison": True, "expected_value": True,
            "observed_value": True},
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0}})
    path.write_bytes(canonical(value))


def preflight() -> None:
    require(not any(path.exists() for path in (
        BUILD, PREFLIGHT, PROCESS, INHERITED_PROCESS, RECEIPT, FINAL_RED)),
        "generator-template card is one-shot")
    predecessor(); authority(); PREV.preflight(); append_preflight()
    print("v1.6 boot refill generator: PREFLIGHT PASS emitted=MAP-CPU card=0/1")


def check_receipt() -> dict[str, Any]:
    value = load(RECEIPT)
    gate = value["boot_refill_DMA_closure"]
    require(value["status"] == FINAL_STATUS
            and value["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_links": 1,
                "media_builds": 0, "device_contacts": 0}
            and value["emitted_candidate_gate"]["failure_propagated"] is True
            and gate["unsafe_content_DMA_count"] == 0
            and gate["product_entry"]["raw_read_edges"] == 0
            and gate["product_entry"]["MAP_CPU_edges"] >= 1
            and gate["instrument"]["neutral"] is True,
            "generator-template final receipt drift")
    return value


def card() -> None:
    predecessor(); authority()
    pre = load(PREFLIGHT / "preflight.json")
    require(pre["status"] == PREFLIGHT_STATUS
            and pre["emitted_candidate_gate"]["failure_propagated"] is True,
            "persisted emitted-source preflight drift")
    PREV.card()
    elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    gate = CLOSURE.linked_read_model(elf)
    CLOSURE.validate_final(gate)
    value = load(RECEIPT)
    value.update({"format": FORMAT, "status": FINAL_STATUS,
        "generator_template_authority": authority(),
        "predecessor": predecessor(), "emitted_candidate_gate": emitted_gate(
            BUILD / "wplto/generated-product-sources/c2_product_runtime.c"),
        "boot_refill_DMA_closure": gate,
        "mutations_rejected": CLOSURE.final_mutations(gate),
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "media_builds": 0, "device_contacts": 0},
        "media_authorized": False, "device_contacts": 0,
        "next": "scope and acceptance; no media before final-world green"})
    RECEIPT.write_bytes(canonical(value))
    check_receipt()
    print("v1.6 boot refill generator: CARD PASS unsafe=0 card=1/1")


def record_red(error: Exception) -> None:
    value = {"format": FORMAT + "-final-red",
        "status": "FINAL RED: V1.6 BOOT REFILL GENERATOR CARD STOPS",
        "error": {"type": type(error).__name__, "message": str(error)},
        "generator_template_authority": authority(),
        "predecessor": predecessor(),
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "media_builds": 0,
            "device_contacts": 0}, "retry_authorized": False,
        "media_authorized": False,
        "next": "full chain to reviewer; no autonomous successor"}
    FINAL_RED.write_bytes(canonical(value))


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight":
        preflight(); return 0
    if action == "card":
        card(); return 0
    if action == "check":
        check_receipt(); print("v1.6 boot refill generator: CHECK PASS"); return 0
    # The inherited producer launches this driver in fresh child processes for
    # its real-consumer materialization probes.  Preserve that adapter surface;
    # only the three top-level actions above belong to this wrapper.
    return PREV.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"generator-template Final Red receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"v1.6 boot refill generator: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
