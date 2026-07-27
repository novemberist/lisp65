#!/usr/bin/env python3
"""Close matrix row B4 by replaying the installer closure on Link 57."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_preinstall_island_guard as G  # noqa: E402


MATRIX = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-cross-invariant-full-matrix-link57-review-receipt.json")
STRUCTURAL = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link57-keymap-nullary-fast-path2-structural-receipt.json")
PRODUCT_DIR = ROOT / (
    "build/c2.2/substitution/product-link-57-keymap-nullary-fast-path2")
PRODUCT = PRODUCT_DIR / "lisp65-c2-substitution-linked.prg"
ELF = PRODUCT_DIR / "lisp65-c2-substitution-linked.prg.elf"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link57-matrix-b4-installer-nonlocal-exit-replay-receipt.json")
GATE_SOURCE = ROOT / "tools/host-lisp/c2_preinstall_island_guard.py"

EXPECTED = {
    MATRIX: "62b5c3cdffa71861f48de6e6619ee40b7ea94ba144ae2653d77a39603e24e8f8",
    STRUCTURAL: "6632a7d00ea3bfaef294924ea618e0af70e34b75da929de05b2e7c451ce26059",
    PRODUCT: "7d568ceb7edab95a237ff3079fcf689768373a9ea48a5a43f355f6275ddc5df8",
    ELF: "306ba2aca61bbd2b924f3b52fd03fbbd9db95330f9c81e1190329abc147bf950",
}


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def build_receipt() -> dict[str, Any]:
    for path, expected in EXPECTED.items():
        require(path.is_file(), f"missing immutable input: {path}")
        require(sha(path) == expected,
                f"immutable Link-57 input drift: {path}")

    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    b4 = next(row for row in matrix["rows"] if row["id"] == "B4")
    require(b4["status"] == "OPEN"
            and b4["disposition"]["kind"] == "fixture",
            "accepted B4 disposition drift")
    gate = G.static_elf_gate(ELF)
    nonlocal_gate = gate["installer_non_local_exit_gate"]
    mutations = nonlocal_gate["mutations"]
    require(
        nonlocal_gate["status"]
        == "passed-zero-linked-non-local-exit-edges"
        and nonlocal_gate["linked_violations"] == [],
        "Link-57 installer closure has a non-local exit")
    require(
        mutations == {
            "clean-status-returning-failure": "passed",
            "poll-edge": "rejected",
            "abort-edge": "rejected",
            "longjmp-edge": "rejected",
            "c2j-abort-cleanup-edge": "rejected",
        },
        "B4 mutation matrix drift")
    require(gate["reachable_function_count"] == 13,
            "Link-57 installer closure identity drift")
    require(len(gate["permitted_pre_READY_manufacturing_writes"]) == 3,
            "installer zero-wipe proof drift")

    return {
        "format": "lisp65-c2.2-matrix-b4-installer-nonlocal-replay-v1",
        "recorded_on": "2026-07-23",
        "status": "passed-link57-installer-zero-non-local-exit-edges",
        "row": "B4",
        "disposition_result": "PROVEN",
        "authorities": {
            "accepted_matrix_review": bind(MATRIX),
            "link57_structural_receipt": bind(STRUCTURAL),
            "link57_product": bind(PRODUCT),
            "link57_elf": bind(ELF),
            "permanent_gate_source": bind(GATE_SOURCE),
        },
        "linked_replay": {
            "installer_root": gate["installer_root"],
            "reachable_function_count": gate["reachable_function_count"],
            "reachable_functions": gate["reachable_functions"],
            "direct_call_edge_count": len(gate["installer_direct_call_edges"]),
            "forbidden_classes": nonlocal_gate["forbidden_classes"],
            "non_local_exit_edges": nonlocal_gate["linked_violations"],
            "status_returning_failure": "retained",
            "pre_READY_zero_wipes":
                gate["permitted_pre_READY_manufacturing_writes"],
            "ready_publication": "unchanged-and-fail-closed",
        },
        "mutations": mutations,
        "execution": {
            "artifact_mode": "pure-read-only-replay",
            "compiler_runs": 0,
            "product_links": 0,
            "product_bytes_changed": 0,
            "hardware_runs": 0,
            "capacity_effect_bytes": 0,
        },
        "claim_limit": (
            "Closes B4 for the exact Link-57 identity and permanently extends "
            "the installer closure gate. It does not close any other matrix "
            "row, start the acceptance chain, promote a product or make a "
            "hardware claim."),
        "value_string": (
            "B4=PROVEN link57=exact installer-closure=13 "
            "nonlocal-exits=0 mutations=4/4 wipe=retained ready=false-on-error "
            "product-delta=0 hardware=0 acceptance=blocked"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check"))
    args = parser.parse_args()
    try:
        value = build_receipt()
        data = canonical(value)
        if args.action == "write":
            if RECEIPT.exists():
                require(RECEIPT.read_bytes() == data,
                        "refusing to overwrite divergent B4 receipt")
            else:
                RECEIPT.write_bytes(data)
            os.chmod(RECEIPT, 0o444)
            verb = "WROTE"
        else:
            require(RECEIPT.is_file() and RECEIPT.read_bytes() == data,
                    "B4 receipt absent or drifted")
            verb = "CHECK PASS"
        print(
            "c2-matrix-b4-installer-nonlocal: "
            f"{verb} closure=13 nonlocal=0 mutations=4/4 product-delta=0")
        return 0
    except (GateError, G.GateError, OSError, KeyError, ValueError,
            json.JSONDecodeError) as exc:
        print(
            "c2-matrix-b4-installer-nonlocal: FAIL " + str(exc),
            file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
