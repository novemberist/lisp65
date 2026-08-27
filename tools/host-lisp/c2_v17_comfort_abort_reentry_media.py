#!/usr/bin/env python3
"""Pack the two-stage abort-reentry repair without rebuilding the product."""

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

import c2_v17_comfort_abort_reentry_fix_card as FIX  # noqa: E402
import c2_v17_comfort_phase1b_acceptance_media as MEDIA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
BUILD = ROOT / "build/c2.3/v1.7-comfort-abort-reentry-media-r1"
ADAPTER = BUILD.parent / "v1.7-comfort-abort-reentry-media-r1-adapter.json"
RECEIPT = ARCH / "c2.3-v1.7-comfort-abort-reentry-media-r1-receipt.json"
SESSION = ROOT / "config/c2-v17-comfort-abort-reentry-device-session.json"
AUTHORIZATION = "f48a12a8"
PRODUCT_REMOTE = "V17R1.D81"
LIBRARY_REMOTE = "V17R1L.D81"
FORMAT = "lisp65-c2-v17-comfort-abort-reentry-media-r1-v1"
STATUS = "PASS: V1.7 COMFORT ABORT REENTRY MEDIA READY"
EXPECTED = {
    "PRG": (41566,
            "f5a9c160ef68bcb595e3cf8e522f8510312ba7c26cc7580f5991e326308e3a8b"),
    "ELF": (647588,
            "86f93483800ebf2b9b29e88752cb8fbbd4632ba52ee2fc94e16fb2ba3bbec9f4"),
}


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
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in (
        "consumes the session's one-repair-round path",
        "the one repair round is bound to a two-stage landing",
        "re-arming ready is explicitly not a repair",
    ):
        require(token in text, f"abort-reentry media authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def configure() -> None:
    """Project the existing media producer onto the accepted repair world."""
    MEDIA.PHASE = FIX
    MEDIA.CARD_BUILD = FIX.BUILD
    MEDIA.WPLTO = FIX.BUILD / "wplto"
    MEDIA.STATIC = FIX.BUILD / "static-plane/narrow-static"
    MEDIA.BUILD = BUILD
    MEDIA.ADAPTER = ADAPTER
    MEDIA.RECEIPT = RECEIPT
    MEDIA.SESSION = SESSION
    MEDIA.CLOSURE = FIX.RECEIPT
    MEDIA.ACCEPTANCE = FIX.BUILD / "artifact-acceptance.json"
    MEDIA.AUTHORIZATION = AUTHORIZATION
    MEDIA.PRODUCT_REMOTE = PRODUCT_REMOTE
    MEDIA.LIBRARY_REMOTE = LIBRARY_REMOTE
    MEDIA.EXPECTED = EXPECTED
    MEDIA.STATUS = STATUS
    MEDIA.COMFORT_MANIFEST = FIX.LIBRARY.with_suffix(".manifest.json")
    MEDIA.COMFORT_BLOB = FIX.LIBRARY.with_suffix(".blob.bin")
    MEDIA.authority = authority
    MEDIA.configure_successor()


def annotate() -> None:
    value = load(RECEIPT)
    value["format"] = FORMAT
    value["repair_world"] = {
        "closure": bind(FIX.RECEIPT),
        "source_pair": load(FIX.RECEIPT)["artifacts_after"],
        "abort_reentry": "two-stage-final-ELF-green",
        "WPLTO_runs": 0,
        "product_links": 0,
    }
    RECEIPT.write_bytes(canonical(value))


def preflight() -> None:
    configure()
    MEDIA.preflight()
    print("v1.7 Comfort abort reentry media: PREFLIGHT PASS artifact-only")


def build() -> None:
    configure()
    MEDIA.build()
    annotate()
    check()
    print("v1.7 Comfort abort reentry media: BUILD PASS WPLTO=0 link=0")


def check() -> None:
    configure()
    MEDIA.check()
    value = load(RECEIPT)
    closure = load(FIX.RECEIPT)
    session = load(SESSION)
    source_pair = closure["artifacts_after"]
    require(
        value["format"] == FORMAT
        and value["status"] == STATUS
        and value["repair_world"] == {
            "closure": bind(FIX.RECEIPT),
            "source_pair": source_pair,
            "abort_reentry": "two-stage-final-ELF-green",
            "WPLTO_runs": 0,
            "product_links": 0,
        }
        and source_pair["PRG"]["sha256"] == EXPECTED["PRG"][1]
        and source_pair["ELF"]["sha256"] == EXPECTED["ELF"][1]
        and closure["final_product"]["abort_reentry_fix"]["status"]
            == "PASS: TWO-STAGE ABORT REENTRY PROVED IN FINAL ELF"
        and value["accounting"] == {"WPLTO_runs": 0, "product_links": 0,
            "product_cards": 0, "replacement_media_builds": 2,
            "device_contacts": 0}
        and session["media"]["product"]["remote_name"] == PRODUCT_REMOTE
        and session["media"]["library"]["remote_name"] == LIBRARY_REMOTE
        and session["decision_table"]["daily-use-blocker"].startswith(
            "at most one repair round"),
        "abort-reentry Same-World media proof drift")
    print("v1.7 Comfort abort reentry media: CHECK PASS contact=one-owner-session")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in (
        "preflight", "build", "check"),
        "usage: c2_v17_comfort_abort_reentry_media.py preflight|build|check")
    {"preflight": preflight, "build": build, "check": check}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"v1.7 Comfort abort reentry media: FAIL {error}",
              file=sys.stderr)
        raise SystemExit(2)
