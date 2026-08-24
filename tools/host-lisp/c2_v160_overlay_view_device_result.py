#!/usr/bin/env python3
"""Bind the one reproduced overlay-view read to its predeclared decision table."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / ("build/c2.3/v1.6-items12-hybrid-owner-contact/"
                  "overlay-view-reproduction-stopped-state/capture.json")
PREVIOUS = ROOT / ("build/c2.3/v1.6-items12-hybrid-owner-contact/"
                   "hybrid-entry-first-red-stopped-state/capture.json")
ATTRIBUTION = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                      "c2.3-v1.6-overlay-view-attribution-receipt.json")
OUT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
              "c2.3-v1.6-overlay-view-device-result-receipt.json")
EXPECTED = {
    "capture": "83eae64fc16cb6a1f69fd6e4a2f3c84fc284cff12d1fb044c262a0f6074218b2",
    "previous_capture": "73827d43bb82102b434bd81a92bc2ce216bf9c3c5b67cc85b3b9b29a89188992",
    "attribution": "e5854f32f855ddb7017a0a550a3ebf33df0e81f198377c7a936675393d2c4599",
}


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"file absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def rows(document: dict[str, Any]) -> dict[str, bytes]:
    return {row["name"]: bytes.fromhex(row["observed_hex"])
            for row in document["reads"]}


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"check", "write"},
            "usage: c2_v160_overlay_view_device_result.py check|write")
    identities = {"capture": bind(CAPTURE), "previous_capture": bind(PREVIOUS),
                  "attribution": bind(ATTRIBUTION)}
    require({key: row["sha256"] for key, row in identities.items()} == EXPECTED,
            "device-result identity drift")
    current = json.loads(CAPTURE.read_text(encoding="utf-8"))
    previous = json.loads(PREVIOUS.read_text(encoding="utf-8"))
    observed = rows(current)
    require(current["tuple"] == previous["tuple"],
            "reproduction did not reach the original stopped tuple")
    require(current["discipline"] == {"CPU_left_stopped": True,
            "D2_D5_executed": False, "raw_first": True, "resets": 0,
            "resumes": 0, "runs": 0, "stops": 1,
            "tuple_before_memory": True}, "capture discipline drift")
    require(observed["live-target-neighborhood"] == bytes(25),
            "live target is not the predeclared all-zero branch")
    require(observed["rtov-lifecycle"] == bytes.fromhex("00020000"),
            "runtime-overlay lifecycle tuple drift")
    require(observed["rtov-family-state"] == bytes.fromhex("00020100"),
            "session family/generation state drift")
    require(observed["c2-journal-count"] == b"\0\0", "journal control drift")
    require(observed["slot50-record"] == bytes.fromhex(
        "3200060000f7970656c39706fe0301004a53287edb74c19f0003000000000000"),
        "slot-50 registry record drift")
    require(observed["slot50-durable-source"] == bytes.fromhex(
        "604818a50269f88502a50369ff850368a4"),
        "slot-50 durable source drift")

    result = {
        "format": "lisp65-c2.3-v1.6-overlay-view-device-result-v1",
        "status": "SELECTED-STALE-CONTROL-AFTER-WIPE",
        "recorded_on": "2026-08-20", "inputs": identities,
        "reproduction": {"tuple_byte_identical_to_first_red": True,
                         "PC": current["tuple"]["PC"],
                         "SP": current["tuple"]["SP"],
                         "MAPL": current["tuple"]["MAPL"],
                         "stack_signature": "B=1, continuation $c5b8",
                         "one_stop": True, "resumes": 0, "resets": 0},
        "raw_decision": {
            "live_target_c5a8_c5c0": observed["live-target-neighborhood"].hex(),
            "rtov_busy": 0, "rtov_island_state": 2,
            "rtov_loaded_len": 0, "rtov_fault": 0,
            "rtov_family": 2, "rtov_family_generation": 1,
            "c2_journal_count": 0,
            "slot50_record_matches": True,
            "slot50_durable_source_matches": True,
        },
        "candidate_disposition": {
            "stale_boot_view": "excluded: live target is all zero and family is session generation 1",
            "cleared_lifecycle_with_slice_bytes_remaining": "excluded: no slice bytes remain in the live neighborhood",
            "durable_source_or_registry_corruption": "excluded: record and source are byte-identical",
            "selected": "control transfer into the fully wiped runtime-overlay target after retirement",
        },
        "mechanism_boundary": ("The read selects the post-wipe stale-control class. "
            "It does not yet identify which control-flow edge reaches $c5b6 after "
            "the lifecycle has retired the slice; that edge is a host/ELF attribution, "
            "not a reason to infer a fix."),
        "device_disposition": "CPU left stopped; owner may power the device off",
        "claim_limit": "Result binding only. No fix, card, link, medium, resume, or further device access.",
    }
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if sys.argv[1] == "write":
        OUT.write_text(encoded, encoding="utf-8")
    else:
        require(OUT.is_file() and OUT.read_text(encoding="utf-8") == encoded,
                "device-result receipt absent or stale")
    print("v1.6 overlay-view device result: PASS selected=stale-control-after-wipe")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResultError, OSError, ValueError, KeyError) as error:
        print(f"v1.6 overlay-view device result: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
