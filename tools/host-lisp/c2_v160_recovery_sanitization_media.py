#!/usr/bin/env python3
"""Pack artifact-only seam media from the recovery-sanitization final pair."""

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

import c2_v160_execution_boundary_media as PREVIOUS  # noqa: E402
import c2_v160_execution_boundary_recovery_sanitization_library_replacement_card as TOP  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
CARD_BUILD = ROOT / "build/c2.3/v1.6-recovery-sanitization-library-replacement-card"
WPLTO = CARD_BUILD / "wplto"
STATIC = CARD_BUILD / "static-plane/narrow-static"
BUILD = ROOT / "build/c2.3/v1.6-recovery-sanitization-media"
ADAPTER = BUILD.parent / "v1.6-recovery-sanitization-media-closure-adapter.json"
RECEIPT = ARCH / "c2.3-v1.6-recovery-sanitization-media-receipt.json"
SESSION = ROOT / "config/c2-v160-recovery-sanitization-seam-session.json"
CLOSURE = ARCH / (
    "c2.3-v1.6-recovery-sanitization-adapter-qualification-resume.json")
ACCEPTANCE = CARD_BUILD / "artifact-acceptance.json"
AUTHORIZATION = "773d9602"
PRODUCT_REMOTE = "V16SEAM.D81"
LIBRARY_REMOTE = "V16SLIB.D81"
EXPECTED = {
    "PRG": (41566, "0a9a950ac9d5cc422d68bd813e647d0ef70664e41ea136ff5b6b47c0a2131fa8"),
    "ELF": (647776, "93201ddea4dbbd58f6905bc93abcd49cc92b4905baffedb873743016826e4945"),
}
STATUS = "PASS: V1.6 RECOVERY SANITIZATION SEAM MEDIA READY"


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
    for token in ("artifact-only", "same-world media", "facade gate",
                  "packed-prg content proof", "seam confirmation contact",
                  "witness removal"):
        require(token in text,
                f"recovery-sanitization media authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def closure_adapter() -> dict[str, Any]:
    closure = load(CLOSURE)
    execution = closure["execution_witness"]
    require(closure["status"] ==
                "PASS: V1.6 RECOVERY SANITIZATION CLOSED READ-ONLY"
            and closure["recovery_sanitization_closed"] is True
            and closure["frozen_pair_before"] == closure["frozen_pair_after"]
            and closure["scope"]["status"] == "PASS"
            and closure["acceptance"]["status"] == "PASS"
            and execution == {"qualification_resumes": 1, "WPLTO_runs": 0,
                "product_links": 0, "cards_consumed": 0,
                "media_builds": 0, "device_contacts": 0},
            "recovery-sanitization closure is not media-ready")
    value = {
        "format": "lisp65-v160-recovery-sanitization-media-adapter-v1",
        "status": "PASS: NESTED MAP ACCEPTANCE ACTIVE-REGISTRY UNION",
        "MAP_fix_closed": True,
        "frozen_pair_before": closure["frozen_pair_before"],
        "frozen_pair_after": closure["frozen_pair_after"],
        "recovery_sanitization_scope": bind(CLOSURE),
        "rule": "same-world adapter; no claim is re-derived",
    }
    ADAPTER.write_bytes(canonical(value))
    return value


def session_config(product: Path, library: Path) -> dict[str, Any]:
    value = PREVIOUS.BASE.RED.PREV.session_config(product, library)
    value["format"] = "lisp65-c2-v160-recovery-sanitization-seam-session-v1"
    value["recorded_on"] = "2026-08-24"
    value["media"]["product"]["remote_name"] = PRODUCT_REMOTE
    value["media"]["library"]["remote_name"] = LIBRARY_REMOTE
    value["claim_scope"] = {
        "accepts": ["recovery-sanitization-refill-seam-confirmation"],
        "excludes": ["v1.6-items-1-2", "release-acceptance"],
    }
    value["rows"] = [
        {"id": "S1-boot", "action": "cold boot product and mount library",
         "expect": "native lisp65> prompt; no early-boot red frame"},
        {"id": "S2-load", "action":
            "submit (require 'v16core), then (require 'repl-comfort)",
         "expect": "t after each form"},
        {"id": "S3-seam", "action":
            "submit (repl) and make no further input",
         "expect": "visible l65> prompt; no red frame at the former refill seam"},
    ]
    return value


def configure_successor() -> None:
    PREVIOUS.TOP = TOP
    PREVIOUS.CARD_BUILD = CARD_BUILD
    PREVIOUS.WPLTO = WPLTO
    PREVIOUS.STATIC = STATIC
    PREVIOUS.BUILD = BUILD
    PREVIOUS.ADAPTER = ADAPTER
    PREVIOUS.RECEIPT = RECEIPT
    PREVIOUS.SESSION = SESSION
    PREVIOUS.CLOSURE = CLOSURE
    PREVIOUS.ACCEPTANCE = ACCEPTANCE
    PREVIOUS.AUTHORIZATION = AUTHORIZATION
    PREVIOUS.PRODUCT_REMOTE = PRODUCT_REMOTE
    PREVIOUS.LIBRARY_REMOTE = LIBRARY_REMOTE
    PREVIOUS.EXPECTED = EXPECTED
    PREVIOUS.STATUS = STATUS
    PREVIOUS.authority = authority
    PREVIOUS.closure_adapter = closure_adapter
    PREVIOUS.session_config = session_config


def preflight() -> None:
    configure_successor()
    PREVIOUS.preflight()
    print("v1.6 recovery-sanitization media: PREFLIGHT PASS artifact-only")


def build() -> None:
    configure_successor()
    PREVIOUS.build()


def check() -> None:
    configure_successor()
    PREVIOUS.check()
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
            "recovery-sanitization packed-media proof drift")
    print("v1.6 recovery-sanitization media: CHECK PASS")


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
