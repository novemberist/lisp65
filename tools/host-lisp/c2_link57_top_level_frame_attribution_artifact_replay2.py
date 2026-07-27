#!/usr/bin/env python3
"""Read-only qualification of the artifact-profile-corrected WPLTO."""

from __future__ import annotations

import json
from pathlib import Path

import c2_link57_top_level_frame_attribution_artifact_replay as BASE


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"


def main() -> int:
    BASE.SOURCE = ROOT / (
        "build/c2.2/substitution/"
        "link57-top-level-frame-attribution-wplto4")
    BASE.PRODUCT = BASE.SOURCE / "lisp65-c2-substitution-linked.prg"
    BASE.ELF = Path(str(BASE.PRODUCT) + ".elf")
    BASE.MAP = Path(str(BASE.PRODUCT) + ".map")
    BASE.SESSION = BASE.SOURCE / "runtime-overlays-session-final.json"
    BASE.PROFILE = BASE.SOURCE / "resolved-profile.txt"
    BASE.INTERNAL = EVIDENCE / (
        "c2.2-link57-top-level-frame-attribution-wplto4-internal.json")
    BASE.FIRST_RED = EVIDENCE / (
        "c2.2-link57-top-level-frame-attribution-wplto4-"
        "qualified-first-red.json")
    BASE.RECEIPT = EVIDENCE / (
        "c2.2-link57-top-level-frame-attribution-artifact-replay2-receipt.json")
    BASE.REPORT = EVIDENCE / (
        "c2.2-link57-top-level-frame-attribution-artifact-replay2-report.json")
    result = BASE.main()
    receipt = json.loads(BASE.RECEIPT.read_text(encoding="utf-8"))
    first = json.loads(BASE.FIRST_RED.read_text(encoding="utf-8"))
    BASE.require(
        first["canonical_artifact_profile_gate"]["status"] ==
            "passed-one-canonical-artifact-profile"
        and first["canonical_artifact_profile_gate"]
            ["compiled_shelf_bytes"] == 71143,
        "corrected WPLTO did not consume one canonical artifact profile",
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
