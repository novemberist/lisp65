#!/usr/bin/env python3
"""Class-A qualification of the immutable WPLTO4 artifact profile."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import c2_link57_l_full_keymap_current_product_wplto as CURRENT


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / (
    "build/c2.2/substitution/link57-top-level-frame-attribution-wplto4")
INTERNAL = EVIDENCE / (
    "c2.2-link57-top-level-frame-attribution-wplto4-internal.json")
INHERITED = EVIDENCE / (
    "c2.2-link57-top-level-frame-attribution-wplto4-first-red.json")
OUT = EVIDENCE / (
    "c2.2-link57-top-level-frame-attribution-wplto4-"
    "qualified-first-red.json")


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing WPLTO4 replay input: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def snapshot() -> dict[str, tuple[int, str]]:
    return {
        path.relative_to(SOURCE).as_posix(): (path.stat().st_size, sha(path))
        for path in SOURCE.rglob("*") if path.is_file()
    }


def main() -> int:
    require(not OUT.exists(), "WPLTO4 profile replay is one-shot")
    before = snapshot()
    internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
    inherited = json.loads(INHERITED.read_text(encoding="utf-8"))
    gate = CURRENT.canonical_artifact_profile_gate(SOURCE)
    require(
        internal["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and internal["execution_accounting"]["product_closure_links"] == 1
        and inherited["status"] == "FIRST RED: install-phase WPLTO stopped"
        and gate["status"] == "passed-one-canonical-artifact-profile"
        and gate["compiled_shelf_bytes"] == 71143
        and gate["legacy_balance_shelf_bytes"] == 70897
        and before == snapshot(),
        "immutable WPLTO4 artifact-profile qualification red",
    )
    value = {
        "format":
            "lisp65-c2-top-level-frame-attribution-wplto-boundary-v2",
        "recorded_on": "2026-07-23",
        "status":
            "FIRST RED: historical checker stopped current-product "
            "L-full keymap WPLTO",
        "promotable": False,
        "canonical_artifact_profile_gate": gate,
        "authority": {
            "internal_WPLTO": bind(INTERNAL),
            "inherited_historical_checker_red": bind(INHERITED),
            "current_product_WPLTO_driver": bind(Path(CURRENT.__file__)),
            "artifact_profile_replay": bind(Path(__file__)),
        },
        "execution_accounting": {
            "whole_program_lto_closure_links": 1,
            "compiler_or_linker_runs_in_this_replay": 0,
            "promotable_product_links": 0,
            "hardware_runs": 0,
            "latency_attempts_consumed": 0,
        },
        "next_gate":
            "Class-A read-only qualification of the immutable diagnostic ELF",
    }
    OUT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(OUT, 0o444)
    print(
        "c2-link57-frame-attribution-WPLTO4-profile-replay: PASS "
        "shelf=71143 legacy-report=70897 links=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
