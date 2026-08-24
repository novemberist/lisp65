#!/usr/bin/env python3
"""Attribute the liveness replacement Seed-link capacity red."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-liveness-fix-replacement-card/wplto"
LINKER = BUILD / "c2-substitution.ld"
MAP = BUILD / "resident-island-seed.prg.map"
FINAL_RED = ARCH / "c2.3-v1.6-liveness-fix-replacement-card-final-red.json"
OUT = ARCH / "c2.3-v1.6-liveness-linker-pin-attribution.json"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def bind(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def derive() -> dict[str, object]:
    linker = LINKER.read_text(encoding="utf-8")
    mapped = MAP.read_text(encoding="utf-8")
    pin = "SIZEOF(.lisp65_c2_mapped_far_service) == 1382"
    require(linker.count(pin) == 1, "stored 1382-byte linker pin absent")
    match = re.search(
        r"^\s*78b2\s+2b8b2\s+([0-9a-f]+)\s+1\s+"
        r"\.lisp65_c2_mapped_far_service$", mapped, re.MULTILINE)
    require(match is not None, "emitted mapped-far map row absent")
    emitted = int(match.group(1), 16)
    require(emitted == 1425 and emitted <= 1499,
            "emitted mapped-far price/capacity drift")
    red = json.loads(FINAL_RED.read_text(encoding="utf-8"))
    require(red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_link_attempts"] == 1
            and not red["artifacts"], "replacement-card accounting drift")
    return {"format": "lisp65-c2-v160-liveness-linker-pin-attribution-v1",
        "status": "ATTRIBUTED: STORED 1382-BYTE LINKER PIN REJECTED 1425-BYTE CANDIDATE",
        "recorded_on": "2026-08-20",
        "inputs": {"Final_Red": bind(FINAL_RED), "linker": bind(LINKER),
                   "seed_map": bind(MAP)},
        "both_sides": {"stored_world": {"service_bytes": 1382,
            "end_exclusive": "0x7e18", "source": "emitted linker assertion"},
            "candidate_world": {"service_bytes": emitted,
                "capacity_bytes": 1499, "end_exclusive": "0x7e43",
                "source": "failed Seed-link map"}},
        "classification": {"known_family": "derived-not-pinned capacity freight",
            "product_mechanism_exonerated": True,
            "real_compiler_consumption_proved": True,
            "fix": "validate candidate-derived size against fixed 1499-byte arena"},
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "final_links": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Attributes the Seed-link red only; authorizes no retry, media, or device contact."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "write"))
    action = parser.parse_args().action
    raw = (json.dumps(derive(), indent=2, sort_keys=True) + "\n").encode()
    if action == "write":
        OUT.write_bytes(raw)
    else:
        require(OUT.is_file() and OUT.read_bytes() == raw,
                "liveness linker-pin attribution receipt drift")
    print("v1.6 liveness linker pin: ATTRIBUTED stored=1382 candidate=1425 capacity=1499")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
