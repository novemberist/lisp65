#!/usr/bin/env python3
"""Pack artifact-only seam media from the selector-bypass domain pair."""

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

import c2_v160_boot_refill_selector_bypass_domain_replacement_card as TOP  # noqa: E402
import c2_v160_recovery_sanitization_media as MEDIA  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ENGINE = MEDIA.PREVIOUS
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
CARD_BUILD = ROOT / "build/c2.3/v1.6-boot-refill-selector-bypass-domain-card"
WPLTO = CARD_BUILD / "wplto"
STATIC = CARD_BUILD / "static-plane/narrow-static"
BUILD = ROOT / "build/c2.3/v1.6-boot-refill-selector-bypass-domain-media"
ADAPTER = BUILD.parent / "v1.6-selector-bypass-domain-media-closure-adapter.json"
RECEIPT = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-domain-media-receipt.json")
SESSION = ROOT / "config/c2-v160-boot-refill-selector-bypass-domain-session.json"
CLOSURE = ARCH / (
    "c2.3-v1.6-boot-refill-selector-bypass-mutation-set-resume.json")
ACCEPTANCE = CARD_BUILD / "artifact-acceptance.json"
AUTHORIZATION = "09ca21f8"
PRODUCT_REMOTE = "V16SEL3.D81"
LIBRARY_REMOTE = "V16SL3.D81"
EXPECTED = {
    "PRG": (41566,
            "3954884bc2e942f5da2f592be7b61a93613b5913c596db219bb3acc04bd1c19f"),
    "ELF": (647776,
            "bbb1547779ea2c9366fa5a29633aa07061a3607fa753043071df1780cc5ea3e4"),
}
STATUS = "PASS: V1.6 SELECTOR BYPASS DOMAIN SEAM MEDIA READY"


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
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{name}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("read-only resume over the frozen pair",
                  "green re-opens the media sequence",
                  "seam confirmation, round three"):
        require(token in text,
                f"selector-bypass media authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def closure_adapter() -> dict[str, Any]:
    closure = load(CLOSURE)
    execution = closure["execution_accounting"]
    require(closure["status"] ==
                "PASS: V1.6 SELECTOR BYPASS DOMAIN CLOSED READ-ONLY"
            and closure["frozen_pair_before"] == closure["frozen_pair_after"]
            and closure["qualification_tail"]["scope_status"] == "PASS"
            and closure["qualification_tail"]["acceptance_status"] == "PASS"
            and execution == {"qualification_resumes": 1,
                "completion_runs": 1, "WPLTO_runs": 0,
                "product_links": 0, "cards_consumed": 0,
                "media_builds": 0, "device_contacts": 0},
            "selector-bypass domain closure is not media-ready")
    value = {
        "format": "lisp65-v160-selector-bypass-domain-media-adapter-v1",
        "status": "PASS: NESTED MAP ACCEPTANCE ACTIVE-REGISTRY UNION",
        "MAP_fix_closed": True,
        "frozen_pair_before": closure["frozen_pair_before"],
        "frozen_pair_after": closure["frozen_pair_after"],
        "selector_bypass_domain_scope": bind(CLOSURE),
        "rule": "same-world adapter; no claim is re-derived",
    }
    ADAPTER.write_bytes(canonical(value))
    return value


def configure_candidate() -> None:
    """Reconstruct only the configuration consumed by the frozen final link."""
    ENGINE.TOP = TOP
    ENGINE.configure_live_chain()
    core, _activation = ENGINE.BASE.BASE.REOPEN.configure_stack(
        CARD_BUILD, TOP.PREFLIGHT)
    core.PRODUCT.BASE.configure()
    ENGINE.BASE.BASE.CAN.REPLAY.PROFILE.configure()
    if ENGINE.BASE.BASE.PRODUCT.PROFILE_RODATA_BYTES == 342:
        ENGINE.BASE.BASE.PRODUCT.configure_require_resolver_profile_geometry()
        ENGINE.BASE.BASE.PRODUCT.configure_defstruct_foundation_profile_geometry()
    ENGINE.BASE.BASE.CAN.REPLAY.BANK2.configure_bank2_stage()
    ENGINE.BASE.BASE.CAN.REPLAY.TWO.configure_two_region()
    ENGINE.BASE.BASE.CAN.REPLAY.LINK60.configure_current_pin_adapters()
    ENGINE.BASE.BASE.PRODUCT.configure_intern_session_service()
    ENGINE.BASE.BASE.PRODUCT.configure_full_map_ownership()
    ENGINE.BASE.BASE.PRODUCT.configure_low_resident_lma_reset()
    ENGINE.BASE.BASE.HEADER.configure_consumption()
    ENGINE.BASE.BASE.PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
        STATIC / "product/substitution-artifacts.json")
    ENGINE.BASE.BASE.PRODUCT.INITIAL_C2D = (
        STATIC / "product/initial.c2d-v3.bin")
    ENGINE.BASE.BASE.PRODUCT.PRODUCT_SHELF = (
        STATIC / "product/product-shelf-v4-direct.bin")
    elf = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
    section = ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj").section(
            ENGINE.BASE.BASE.PRODUCT.VERIFIER_BINDING_SECTION)
    ENGINE.BASE.BASE.PRODUCT.VERIFIER_BINDING_BASE = section.address
    ENGINE.BASE.BASE.PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address
    require(section.bytes == 40, "candidate verifier-binding size drift")


def session_config(product: Path, library: Path) -> dict[str, Any]:
    value = ENGINE.BASE.RED.PREV.session_config(product, library)
    value["format"] = "lisp65-c2-v160-selector-bypass-domain-session-v1"
    value["recorded_on"] = "2026-08-24"
    value["media"]["product"]["remote_name"] = PRODUCT_REMOTE
    value["media"]["library"]["remote_name"] = LIBRARY_REMOTE
    value["claim_scope"] = {
        "accepts": ["selector-bypass-domain-seam-confirmation-round-3"],
        "excludes": ["v1.6-items-1-2", "release-acceptance"],
    }
    value["rows"] = [
        {"id": "S3-1-boot", "action": "cold boot product and mount library",
         "expect": "native lisp65> prompt; no early-boot red frame"},
        {"id": "S3-2-load", "action":
            "submit (require 'v16core), then (require 'repl-comfort)",
         "expect": "t after each form"},
        {"id": "S3-3-seam", "action":
            "submit (repl) and make no further input",
         "expect": "visible l65> prompt; no red frame at the former refill seam"},
    ]
    return value


def configure_successor() -> None:
    MEDIA.TOP = TOP
    MEDIA.CARD_BUILD = CARD_BUILD
    MEDIA.WPLTO = WPLTO
    MEDIA.STATIC = STATIC
    MEDIA.BUILD = BUILD
    MEDIA.ADAPTER = ADAPTER
    MEDIA.RECEIPT = RECEIPT
    MEDIA.SESSION = SESSION
    MEDIA.CLOSURE = CLOSURE
    MEDIA.ACCEPTANCE = ACCEPTANCE
    MEDIA.AUTHORIZATION = AUTHORIZATION
    MEDIA.PRODUCT_REMOTE = PRODUCT_REMOTE
    MEDIA.LIBRARY_REMOTE = LIBRARY_REMOTE
    MEDIA.EXPECTED = EXPECTED
    MEDIA.STATUS = STATUS
    MEDIA.authority = authority
    MEDIA.closure_adapter = closure_adapter
    MEDIA.session_config = session_config
    MEDIA.configure_successor()
    ENGINE.configure_candidate = configure_candidate


def preflight() -> None:
    configure_successor()
    MEDIA.preflight()
    print("v1.6 selector-bypass domain media: PREFLIGHT PASS artifact-only")


def build() -> None:
    configure_successor()
    MEDIA.build()


def check() -> None:
    configure_successor()
    MEDIA.check()
    value = load(RECEIPT)
    require(value["status"] == STATUS
            and value["accounting"] == {"WPLTO_runs": 0,
                "product_links": 0, "product_cards": 0,
                "replacement_media_builds": 2, "device_contacts": 0}
            and value["packed_artifact_closure"]["artifact_count"] == 19
            and value["shipped_byte_facade"]["bytes"] == 98
            and value["shipped_byte_facade"]["status"] ==
                "passed-packed-prg-facade-byte-equals-final-elf"
            and value["facade_mutations"] == {"cases": 2,
                "rejected": ["null-facade", "partial-facade"]},
            "selector-bypass domain packed-media proof drift")
    print("v1.6 selector-bypass domain media: CHECK PASS")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight":
        preflight()
    elif action == "build":
        build()
    elif action == "check":
        check()
    else:
        raise RuntimeError("usage: preflight|build|check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
