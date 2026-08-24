#!/usr/bin/env python3
"""Pack artifact-only seam-confirmation media for the repaired boot refill."""

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

import c2_v160_nested_map_swap_media as BASE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
CARD_BUILD = ROOT / "build/c2.3/v1.6-boot-refill-generator-template-card"
WPLTO = CARD_BUILD / "wplto"
STATIC = CARD_BUILD / "static-plane/narrow-static"
BUILD = ROOT / "build/c2.3/v1.6-boot-refill-dma-media"
ADAPTER = ROOT / "build/c2.3/v1.6-boot-refill-dma-media-closure-adapter.json"
RECEIPT = ARCH / "c2.3-v1.6-boot-refill-dma-media-receipt.json"
SESSION = ROOT / "config/c2-v160-boot-refill-dma-session.json"
CLOSURE = ARCH / "c2.3-v1.6-boot-refill-feature-union-resume.json"
ACCEPTANCE = CARD_BUILD / "artifact-acceptance.json"
AUTHORIZATION = "84924e89"
PRODUCT_REMOTE = "V16DMA.D81"
LIBRARY_REMOTE = "V16DML.D81"
EXPECTED = {
    "PRG": (41566, "96a7d5d1c81eb15cfdad9d9bb272584a5b80ae2ad02f1d4f824c65729b34eee9"),
    "ELF": (646988, "02209a9ddda93b49bc3025f6b0caa9b2d88cb96b2504167b3ccc98d6f9ffba99"),
}
STATUS = "PASS: V1.6 BOOT REFILL DMA SEAM CONFIRMATION MEDIA READY"


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
    for token in ("green completes the dma-fix chain", "artifact-only media",
                  "seam confirmation contact"):
        require(token in text, f"boot-refill media authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def closure_adapter() -> dict[str, Any]:
    closure = load(CLOSURE)
    require(closure["status"] == "PASS: BOOT REFILL DMA FIX CHAIN CLOSED"
            and closure["frozen_pair_before"] == closure["frozen_pair_after"]
            and closure["final_ELF_gate"]["unsafe_content_DMA_count"] == 0,
            "boot-refill closure is not media-ready")
    value = {"format": "lisp65-v160-boot-refill-media-closure-adapter-v1",
        "status": "PASS: NESTED MAP ACCEPTANCE ACTIVE-REGISTRY UNION",
        "MAP_fix_closed": True,
        "frozen_pair_before": closure["frozen_pair_before"],
        "frozen_pair_after": closure["frozen_pair_after"],
        "boot_refill_DMA_fix": bind(CLOSURE),
        "rule": "same-world adapter; no claim is re-derived"}
    ADAPTER.write_bytes(canonical(value))
    return value


def configure() -> None:
    BASE.CARD_BUILD = CARD_BUILD; BASE.WPLTO = WPLTO; BASE.STATIC = STATIC
    BASE.BUILD = BUILD; BASE.RECEIPT = RECEIPT; BASE.SESSION = SESSION
    BASE.CLOSURE = ADAPTER; BASE.ACCEPTANCE = ACCEPTANCE
    BASE.AUTHORIZATION = AUTHORIZATION
    BASE.PRODUCT_REMOTE = PRODUCT_REMOTE; BASE.LIBRARY_REMOTE = LIBRARY_REMOTE
    BASE.EXPECTED = EXPECTED; BASE.STATUS = STATUS
    BASE.authority = authority


def preflight() -> None:
    require(not BUILD.exists() and not RECEIPT.exists() and not SESSION.exists(),
            "boot-refill media preparation is one-shot")
    closure_adapter(); configure(); BASE.preflight()
    print("v1.6 boot-refill media: PREFLIGHT PASS artifact-only")


def build() -> None:
    closure_adapter(); configure(); BASE.build()


def check() -> None:
    configure(); value = BASE.check()
    require(value["status"] == STATUS
            and value["accounting"] == {"WPLTO_runs": 0, "product_links": 0,
                "product_cards": 0, "replacement_media_builds": 2,
                "device_contacts": 0},
            "boot-refill media accounting drift")
    print("v1.6 boot-refill media: CHECK PASS")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "preflight": preflight()
    elif action == "build": build()
    elif action == "check": check()
    else: raise RuntimeError("usage: preflight|build|check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
