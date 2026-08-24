#!/usr/bin/env python3
"""Prepare fresh same-world media for the sixth v1.6 display contact."""

from __future__ import annotations

import argparse
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

import c2_v160_queue_owner_device_preparation as PREV  # noqa: E402


BASE = PREV.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-display-ownership-device-preparation"
RECEIPT = ARCH / "c2.3-v1.6-display-ownership-device-preparation-receipt.json"
SESSION = ROOT / "config/c2-v160-display-ownership-device-session.json"
CLOSURE = ARCH / "c2.3-v1.6-display-ownership-replacement-card-receipt.json"
DISPLAY = ARCH / "c2.3-v1.6-display-ownership-receipt.json"
AUTHORIZATION = "516a73fc"
PRODUCT_REMOTE = "V16D6.D81"
LIBRARY_REMOTE = "V16L6.D81"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("%rl-screen-tail", "%fasl-fs", "33", "594",
                  "real-framebuffer gate", "viewport arithmetic"):
        require(token in text, f"display media authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def session_config(product: Path, library: Path) -> dict[str, Any]:
    value = PREV.session_config(product, library)
    value["format"] = "lisp65-c2-v160-display-ownership-device-session-v1"
    value["recorded_on"] = "2026-08-22"
    value["media"]["product"]["remote_name"] = PRODUCT_REMOTE
    value["media"]["library"]["remote_name"] = LIBRARY_REMOTE
    value["claim_scope"] = {
        "accepts_on_green": ["v1.6-item-1-cursor-navigation",
                              "v1.6-item-2-comfort-repl",
                              "display-ownership-handoff"],
        "excludes": ["D5-headroom", "v1.6-items-3-4",
                     "release-acceptance", "v1.7-retired-window-backstop"]}
    value["rows"] = [
        {"id": "D1", "action": (
            "cold boot product, mount library physically, require v16core and "
            "repl-comfort, then submit (repl)"),
         "expect": "both requires return t and Comfort displays l65>"},
        {"id": "D2-composed-entry", "action": (
            "At l65>, type (list 1 3) without editing it"),
         "expect": (
            "l65> and (list 1 3) share one row; the cursor begins immediately "
            "after the prompt and the prompt itself is not editable")},
        {"id": "D2-defined-handoff", "action": "press Return once",
         "expect": (
            "the completed row contains only (1 3); no input or prompt suffix "
            "survives, and the next l65> shares its row with the cursor")},
        {"id": "D2-edit-composed", "action": (
            "type (list 1 3), move left twice, insert 2 followed by a space, "
            "then press Return"),
         "expect": (
            "the edited row remains prompt-aligned and evaluates to exactly "
            "(1 2 3) with no stale framebuffer cells")},
        {"id": "D2-viewport", "action": (
            "enter a line long enough to move the viewport, then move left "
            "across the one-column scroll edge and return to the end"),
         "expect": (
            "prompt cells stay fixed, input scrolls by one column, cursor follows, "
            "and the 250-character line contract remains available")},
        {"id": "D2-input-regression", "action": (
            "slowly enter a(a(a(a( and count attempts; then type a rapid short "
            "lowercase phrase and edit its middle"),
         "expect": (
            "all intended characters appear once, lowercase remains lowercase, "
            "and typing feel remains responsive without swallowed keys")},
    ]
    value["display_witness"] = {
        "active_row": "l65> (list 1 3)",
        "handoff_row": "(1 3)",
        "forbidden_residue": "(1 3) 1 3)",
        "owner_rule": "one framebuffer owner at a time; defined handoff"}
    return value


def configure() -> None:
    BASE.BUILD = BUILD
    BASE.CARD = PREV.CARD
    BASE.WPLTO = PREV.WPLTO
    BASE.STATIC = PREV.STATIC
    BASE.TARGET = BUILD / "canonical-product"
    BASE.SHARED = BUILD / "shared-system"
    BASE.LIBRARY = BUILD / "library"
    BASE.RECEIPT = RECEIPT
    BASE.SESSION = SESSION
    BASE.EXPECTED = PREV.EXPECTED
    BASE.configure_candidate = PREV.configure_candidate
    BASE.complete = PREV.complete
    BASE.session_config = session_config


def preflight() -> None:
    configure()
    closure = load(CLOSURE)
    display = load(DISPLAY)
    require(not BUILD.exists() and not RECEIPT.exists() and not SESSION.exists(),
            "display device preparation is one-shot")
    require(closure["status"] == "PASS: V1.6 DISPLAY OWNERSHIP GREEN"
            and display["status"] ==
                "PASS: COMFORT DISPLAY HAS ONE OWNER AND DEFINED HANDOFF"
            and display["composed_framebuffer"]["result_row"] == "(1 3)"
            and display["composed_framebuffer"]["result_tail_blank"] is True,
            "display-ownership predecessor drift")
    product = PREV.WPLTO / "lisp65-c2-substitution-linked.prg"
    elf = Path(str(product) + ".elf")
    require((product.stat().st_size, BASE.sha(product)) == PREV.EXPECTED["PRG"]
            and (elf.stat().st_size, BASE.sha(elf)) == PREV.EXPECTED["ELF"],
            "display candidate pair drift")
    print("v1.6 display media: PREFLIGHT PASS "
          f"authority={authority()['commit'][:8]} media=0 device=0")


def build() -> None:
    configure()
    manifest = BASE.SHARED / "candidate-manifest.json"
    library = BASE.LIBRARY / "lisp65-library.d81"
    if BUILD.exists() and manifest.is_file() and not library.exists():
        # The first invocation stopped while compiling the library projection,
        # after canonical Completion and product media were already sealed.
        # Resume that same producer at its missing owned output; never rebuild
        # the accepted pair or the completed product side.
        BASE.library_media()
        value = BASE.finish(load(manifest))
    else:
        value = BASE.build()
    value["format"] = "lisp65-c2-v160-display-ownership-device-preparation-v1"
    value["recorded_on"] = "2026-08-22"
    value["successor_authority"] = authority()
    value["display_closure"] = bind(CLOSURE)
    value["display_contract"] = bind(DISPLAY)
    value["status"] = "PASS: V1.6 DISPLAY OWNERSHIP SIXTH CONTACT READY"
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 display media: PASS media=2 contact=ready")


def check() -> dict[str, Any]:
    configure()
    value = load(RECEIPT)
    require(value["format"] ==
                "lisp65-c2-v160-display-ownership-device-preparation-v1"
            and value["status"] ==
                "PASS: V1.6 DISPLAY OWNERSHIP SIXTH CONTACT READY",
            "display preparation receipt drift")
    for row in [*value["accepted_pair"].values(), value["completion"],
                value["media_closure"], *value["media"].values(),
                value["session"], value["display_closure"],
                value["display_contract"]]:
        require(bind(ROOT / row["path"]) == row,
                f"display artifact identity drift: {row['path']}")
    pair = BASE.PAIR.pair_identity(ROOT / value["media"]["product"]["path"],
                                   ROOT / value["media"]["library"]["path"])
    require(pair == value["same_world_pair"], "display pair identity drift")
    session = load(SESSION)
    require(session["media"]["product"]["remote_name"] == PRODUCT_REMOTE
            and session["media"]["library"]["remote_name"] == LIBRARY_REMOTE
            and [row["id"] for row in session["rows"][:3]] == [
                "D1", "D2-composed-entry", "D2-defined-handoff"]
            and session["display_witness"]["handoff_row"] == "(1 3)",
            "display session drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "build", "check"))
    action = parser.parse_args().action
    if action == "preflight":
        preflight()
    elif action == "build":
        build()
    else:
        check()
        print("v1.6 display media: CHECK PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
