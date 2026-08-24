#!/usr/bin/env python3
"""Attribute the zero-byte-alias card's remaining LTO BSS byte."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
OLD = ROOT / "build/c2.3/v1.6-boot-refill-generator-template-card/wplto/resident-island-seed.prg.map"
RED = ROOT / "build/c2.3/v1.6-execution-boundary-backstop-alias-card/wplto/resident-island-seed.prg.map"
CARD_RED = ARCH / "c2.3-v1.6-execution-boundary-backstop-alias-card-final-red.json"
OUT = ARCH / "c2.3-v1.6-execution-boundary-alias-lto-attribution.json"
ALIASES = {
    "c2_backstop_pending_code": "pending_code",
    "c2_backstop_pending_symbol": "pending_symbol",
    "c2_backstop_rtov_loaded_len": "rtov_loaded_len",
    "c2_backstop_rtov_busy": "rtov_busy",
}


def require(value: bool, message: str) -> None:
    if not value: raise RuntimeError(message)


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def symbol_rows(path: Path) -> dict[str, dict[str, int]]:
    rows: dict[str, dict[str, int]] = {}
    for line in path.read_text().splitlines():
        match = re.match(r"^\s*([0-9a-f]+)\s+[0-9a-f]+\s+([0-9a-f]+)\s+1\s+(\S+)$", line)
        if match and ":(" not in match.group(3):
            rows[match.group(3)] = {"address": int(match.group(1), 16),
                                    "bytes": int(match.group(2), 16)}
    return rows


def derive() -> dict[str, Any]:
    old = symbol_rows(OLD); red = symbol_rows(RED)
    identities = {}
    for alias, owner in ALIASES.items():
        require(alias in red and owner in red and
                red[alias]["address"] == red[owner]["address"],
                f"alias identity drift: {alias}")
        identities[alias] = {"owner": owner,
            "address": f"0x{red[alias]['address']:04x}",
            "owner_address": f"0x{red[owner]['address']:04x}",
            "same_address": True, "additional_allocated_bytes": 0}
    require(old["lisp_toplevel_active"]["bytes"] == 1
            and red["lisp_toplevel_active"]["bytes"] == 2,
            "lisp_toplevel_active width discriminator drift")
    return {"format": "lisp65-c2-v160-execution-boundary-alias-lto-attribution-v1",
        "status": "ATTRIBUTED: EXTERNAL ASM USE RESTORES C INT WIDTH TO TWO BYTES",
        "recorded_on": "2026-08-23",
        "inputs": {"predecessor_map": bind(OLD), "alias_red_map": bind(RED),
                   "alias_card_Final_Red": bind(CARD_RED)},
        "alias_result": {"aliases_are_zero_byte": True,
                         "identities": identities},
        "remaining_byte": {"symbol": "lisp_toplevel_active",
            "predecessor_emitted_bytes": old["lisp_toplevel_active"]["bytes"],
            "alias_candidate_emitted_bytes": red["lisp_toplevel_active"]["bytes"],
            "delta_bytes": 1,
            "mechanism": "external assembler consumption prevents whole-program narrowing of the C int object"},
        "BSS": {"predecessor_bytes": 1585, "candidate_bytes": 1586,
                "required_validation_margin": 5, "observed_validation_margin": 4},
        "decision": {"zero_byte_alias_hypothesis": "proved for all four authorized aliases",
            "card_result": "red because a fifth, previously global int identity widened",
            "narrow_successor_candidate":
                "make lisp_toplevel_active explicitly uint8_t in declaration and definition, then prove all C consumers and final ELF agree",
            "successor_authorized": False},
        "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "media_builds": 0, "device_contacts": 0},
        "next": "review decision; the one authorized alias replacement is consumed"}


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"write", "check"},
            "usage: c2_v160_execution_boundary_alias_lto_attribution.py write|check")
    raw = (json.dumps(derive(), indent=2, sort_keys=True) + "\n").encode()
    if sys.argv[1] == "write": OUT.write_bytes(raw)
    else: require(OUT.read_bytes() == raw, "alias-LTO attribution receipt drift")
    print("v1.6 execution boundary alias LTO: ATTRIBUTED aliases=zero active=1->2")
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error:
        print(f"v1.6 execution boundary alias LTO: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
