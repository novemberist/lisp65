#!/usr/bin/env python3
"""Pack artifact-only seam media from the execution-boundary final pair."""

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

import c2_v160_execution_boundary_backstop_uint8_irq_return_replacement_card as TOP  # noqa: E402
import c2_v160_input_fidelity_reopen_replacement_card as LEAF  # noqa: E402
import c2_v160_nested_map_swap_media as BASE  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
CARD_BUILD = ROOT / (
    "build/c2.3/v1.6-execution-boundary-backstop-uint8-irq-return-"
    "replacement-card")
WPLTO = CARD_BUILD / "wplto"
STATIC = CARD_BUILD / "static-plane/narrow-static"
BUILD = ROOT / "build/c2.3/v1.6-execution-boundary-media"
ADAPTER = BUILD.parent / "v1.6-execution-boundary-media-closure-adapter.json"
RECEIPT = ARCH / "c2.3-v1.6-execution-boundary-media-receipt.json"
SESSION = ROOT / "config/c2-v160-execution-boundary-seam-session.json"
CLOSURE = ARCH / "c2.3-v1.6-execution-boundary-scope-resume.json"
ACCEPTANCE = CARD_BUILD / "artifact-acceptance.json"
AUTHORIZATION = "f2730e34"
PRODUCT_REMOTE = "V16BSTP.D81"
LIBRARY_REMOTE = "V16BSTL.D81"
EXPECTED = {
    "PRG": (41566, "62304b65eafc22d0538198db0a786821bc9244a4ac54b0e747ec362696bdaf2d"),
    "ELF": (647612, "c8b74690e682370f14c68bc837cd9642b702df024e71c82753b0b21d678fd10d"),
}
STATUS = "PASS: V1.6 EXECUTION BOUNDARY SEAM MEDIA READY"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def authority() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("artifact-only media", "seam confirmation contact",
                  "witness removal on green", "acceptance session"):
        require(token in text, f"execution-boundary media authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def closure_adapter() -> dict[str, Any]:
    closure = load(CLOSURE)
    require(closure["status"] ==
                "PASS: V1.6 EXECUTION BOUNDARY SCOPE CLOSED READ-ONLY"
            and closure["frozen_pair_before"] == closure["frozen_pair_after"]
            and closure["execution"]["WPLTO_runs"] == 0
            and closure["execution"]["product_links"] == 0,
            "execution-boundary closure is not media-ready")
    value = {"format": "lisp65-v160-execution-boundary-media-adapter-v1",
        "status": "PASS: NESTED MAP ACCEPTANCE ACTIVE-REGISTRY UNION",
        "MAP_fix_closed": True,
        "frozen_pair_before": closure["frozen_pair_before"],
        "frozen_pair_after": closure["frozen_pair_after"],
        "execution_boundary_scope": bind(CLOSURE),
        "rule": "same-world adapter; no claim is re-derived"}
    ADAPTER.write_bytes(canonical(value))
    return value


def configure_live_chain() -> None:
    original_child = LEAF.child
    previous_argv = sys.argv
    LEAF.child = lambda action: require(
        action == "_scope", f"unexpected media configuration action: {action}")
    sys.argv = [str(Path(__file__)), "_scope"]
    try:
        TOP.main()
    finally:
        sys.argv = previous_argv
        LEAF.child = original_child


def configure_candidate() -> None:
    """Reconstruct the configuration consumed by the frozen final link."""
    configure_live_chain()
    core, _activation = BASE.BASE.REOPEN.configure_stack(
        CARD_BUILD, TOP.CARD.PREFLIGHT)
    core.PRODUCT.BASE.configure()
    BASE.BASE.CAN.REPLAY.PROFILE.configure()
    if BASE.BASE.PRODUCT.PROFILE_RODATA_BYTES == 342:
        BASE.BASE.PRODUCT.configure_require_resolver_profile_geometry()
        BASE.BASE.PRODUCT.configure_defstruct_foundation_profile_geometry()
    BASE.BASE.CAN.REPLAY.BANK2.configure_bank2_stage()
    BASE.BASE.CAN.REPLAY.TWO.configure_two_region()
    BASE.BASE.CAN.REPLAY.LINK60.configure_current_pin_adapters()
    BASE.BASE.PRODUCT.configure_intern_session_service()
    BASE.BASE.PRODUCT.configure_full_map_ownership()
    BASE.BASE.PRODUCT.configure_low_resident_lma_reset()
    BASE.BASE.HEADER.configure_consumption()
    BASE.BASE.PRODUCT.PRODUCT_ARTIFACTS_MANIFEST = (
        STATIC / "product/substitution-artifacts.json")
    BASE.BASE.PRODUCT.INITIAL_C2D = STATIC / "product/initial.c2d-v3.bin"
    BASE.BASE.PRODUCT.PRODUCT_SHELF = (
        STATIC / "product/product-shelf-v4-direct.bin")
    elf = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
    section = ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj").section(
            BASE.BASE.PRODUCT.VERIFIER_BINDING_SECTION)
    BASE.BASE.PRODUCT.VERIFIER_BINDING_BASE = section.address
    BASE.BASE.PRODUCT.LINK60_VERIFIER_BINDING_BASE = section.address
    require(section.bytes == 40, "candidate verifier-binding size drift")


def session_config(product: Path, library: Path) -> dict[str, Any]:
    value = BASE.RED.PREV.session_config(product, library)
    value["format"] = "lisp65-c2-v160-execution-boundary-seam-session-v1"
    value["recorded_on"] = "2026-08-23"
    value["media"]["product"]["remote_name"] = PRODUCT_REMOTE
    value["media"]["library"]["remote_name"] = LIBRARY_REMOTE
    value["claim_scope"] = {"accepts": ["execution-boundary-seam-confirmation"],
        "excludes": ["v1.6-items-1-2", "release-acceptance"]}
    value["rows"] = [
        {"id": "B1-boot", "action": "cold boot product and mount library",
         "expect": "native lisp65> prompt; no boot red frame"},
        {"id": "B2-load", "action":
            "submit (require 'v16core), then (require 'repl-comfort)",
         "expect": "t after each form"},
        {"id": "B3-seam", "action": "submit (repl) and make no further input",
         "expect": "visible l65> prompt; no red frame at the former refill seam"},
    ]
    return value


def configure() -> None:
    BASE.CARD_BUILD = CARD_BUILD; BASE.WPLTO = WPLTO; BASE.STATIC = STATIC
    BASE.BUILD = BUILD; BASE.RECEIPT = RECEIPT; BASE.SESSION = SESSION
    BASE.CLOSURE = ADAPTER; BASE.ACCEPTANCE = ACCEPTANCE
    BASE.AUTHORIZATION = AUTHORIZATION
    BASE.PRODUCT_REMOTE = PRODUCT_REMOTE; BASE.LIBRARY_REMOTE = LIBRARY_REMOTE
    BASE.EXPECTED = EXPECTED; BASE.STATUS = STATUS
    BASE.authority = authority; BASE.configure_candidate = configure_candidate
    BASE.session_config = session_config


def preflight() -> None:
    require(not BUILD.exists() and not RECEIPT.exists() and not SESSION.exists()
            and not ADAPTER.exists(),
            "execution-boundary media preparation is one-shot")
    closure_adapter(); configure(); BASE.preflight()
    print("v1.6 execution-boundary media: PREFLIGHT PASS artifact-only")


def build() -> None:
    closure_adapter(); configure(); BASE.build()


def check() -> None:
    configure(); value = BASE.check()
    require(value["status"] == STATUS
            and value["accounting"] == {"WPLTO_runs": 0, "product_links": 0,
                "product_cards": 0, "replacement_media_builds": 2,
                "device_contacts": 0},
            "execution-boundary media accounting drift")
    print("v1.6 execution-boundary media: CHECK PASS")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight": preflight()
    elif action == "build": build()
    elif action == "check": check()
    else: raise RuntimeError("usage: preflight|build|check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
