#!/usr/bin/env python3
"""Replay facade provenance using ELF st_shndx, without compiling or linking."""

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
import c2_preinstall_island_guard as ISLAND  # noqa: E402


WPLTO_OUT = ROOT / (
    "build/c2.2/substitution/link33-bss-triage-facade15-placement-probe")
WPLTO_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-bss-triage-facade15-placement-probe-receipt.json")
WPLTO_RECEIPT_SHA = (
    "59209a27d73a976df4f74f57683f720b9d6a1cfe6633c74f2bb291923351fa3f")
PREDECESSOR_REPLAY_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-facade15-provenance-replay-receipt.json")
PREDECESSOR_REPLAY_RECEIPT_SHA = (
    "0c55bc59500d2a3d2941b153cc1a3e029e899dcc4983b707f5717fc91dacfcd4")
ELF = WPLTO_OUT / "bss-triage-facade15-placement-seed.prg.elf"
ELF_SHA = "6644da0e46078dd0c8819188c25e9bd5b878ee387cf01719027cbba9d9c50cf3"
PRG = WPLTO_OUT / "bss-triage-facade15-placement-seed.prg"
PRG_SHA = "75924e481118e5510e75d02519f2cc6f50601bde69988fe20b6abe023558d3d8"
LINK32 = ROOT / (
    "build/c2.2/substitution/product-link-32-preinstall-island-guard/"
    "lisp65-c2-substitution-linked.prg")
LINK32_SHA = "189548ea52b9af748217a0da94b7dc1d5daa5f17d190f5817f2fb4af486a676a"
OUT = ROOT / "build/c2.2/substitution/link33-facade15-section-replay"
REPORT = OUT / "preinstall-island-section-provenance-replay.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-facade15-section-replay-receipt.json")
PLAN = ROOT / "docs/planning/c2.2-link33-coordinated-residency-plan.md"
CONTRACT = ROOT / "config/c2-kernal-unmap-contract.json"
CONTRACT_DOC = ROOT / "docs/planning/c2.2-kernal-unmap-contract.md"


class ReplayError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def immutable_tree() -> dict[str, str]:
    files = sorted(path for path in WPLTO_OUT.rglob("*") if path.is_file())
    require(files and all(path.stat().st_mode & 0o777 == 0o444 for path in files),
            "WPLTO evidence tree is not read-only")
    return {path.relative_to(WPLTO_OUT).as_posix(): sha(path) for path in files}


def authority() -> dict[str, Any]:
    require(sha(WPLTO_RECEIPT) == WPLTO_RECEIPT_SHA,
            "WPLTO First-Red receipt drift")
    require(sha(PREDECESSOR_REPLAY_RECEIPT)
            == PREDECESSOR_REPLAY_RECEIPT_SHA,
            "predecessor replay First-Red receipt drift")
    require(sha(ELF) == ELF_SHA and sha(PRG) == PRG_SHA,
            "immutable WPLTO identity drift")
    require(sha(LINK32) == LINK32_SHA, "Link-32 rollback identity drift")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    authorization = contract["formal_reopening_2026_07_21"][
        "independent_bss_triage_2026_07_21"][
            "facade15_successor_authorization"][
                "provenance_replay_authorization"][
                    "section_index_successor_replay_authorization"]
    require(authorization["status"] == "authorized-pending"
            and authorization["compiler_runs"] == 0
            and authorization["linker_runs"] == 0,
            "section-index replay authorization drift")
    return {
        "wplto_first_red": bind(WPLTO_RECEIPT),
        "predecessor_replay_first_red": bind(PREDECESSOR_REPLAY_RECEIPT),
        "plan": bind(PLAN),
        "contract": bind(CONTRACT),
        "contract_document": bind(CONTRACT_DOC),
    }


def write_result(value: dict[str, Any]) -> None:
    OUT.mkdir(parents=True)
    REPORT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    receipt = {**value, "replay_report": bind(REPORT)}
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(REPORT, 0o444)
    os.chmod(OUT, 0o555)
    os.chmod(RECEIPT, 0o444)


def run_replay() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "section-index replay is one-shot and already has output")
    bound_authority = authority()
    before = immutable_tree()
    base: dict[str, Any] = {
        "format": "lisp65-c2-link33-facade15-section-replay-v1",
        "recorded_on": "2026-07-21",
        "execution_accounting": {
            "pure_gate_replay_attempts": 1,
            "compiler_runs": 0,
            "linker_runs": 0,
            "product_links": 0,
            "hardware_runs": 0,
        },
        "authority": bound_authority,
        "immutable_input": {
            "elf": bind(ELF), "prg": bind(PRG),
            "file_count": len(before), "tree_unchanged": True,
        },
        "capacity_from_sha_bound_wplto_map": {
            "bank0_text": 41, "ordinary_bank0_bss": 229,
            "fixed_hot_block": 33, "resident_island": 7,
            "e000": 115, "e000_debit": 422,
            "claim": "provenance only; no new capacity measurement",
        },
        "rollback_line": {"link32_sha256": LINK32_SHA, "status": "untouched"},
    }
    try:
        gate = ISLAND.static_elf_gate(ELF)
        evidence = gate["fixed_facade_section_evidence"]
        require(evidence == {
            "name": "c2_facade_handle_normalize",
            "address": 0xB5EE,
            "bytes": 0,
            "type": "None",
            "section": ".lisp65_c2_host_facade",
            "st_shndx": 14,
            "owner_address": 0xB5C4,
            "owner_bytes": 45,
            "range_crosscheck": "passed",
        }, f"st_shndx facade evidence drift: {evidence}")
        required = {
            "wrong-address-contract-object": "rejected",
            "wrong-size-contract-object": "rejected",
            "wrong-elf-section-index": "rejected",
            "unlisted-facade-relocation-address": "rejected",
        }
        require(all(gate["negative_matrix"].get(name) == result
                    for name, result in required.items()),
                "section-index mutation matrix incomplete")
        value = {
            **base,
            "status": "passed-pure-section-index-gate-replay-no-link",
            "corrected_gate": gate,
            "final_e000_floor": "candidate-115-ready-for-contract-binding",
            "next_gate": "bind final E000 floor to 115 bytes, then fresh Link 33",
        }
    except (ISLAND.GateError, ReplayError, RuntimeError, KeyError) as error:
        value = {
            **base,
            "status": "FIRST RED: pure section-index provenance replay failed",
            "diagnostic": str(error),
            "final_e000_floor": "not-bound",
            "next_gate": "return to review; no retry, floor binding or Link 33",
        }
    require(immutable_tree() == before,
            "section-index replay modified immutable WPLTO evidence")
    write_result(value)
    return value


def check() -> dict[str, Any]:
    require(RECEIPT.is_file() and REPORT.is_file(), "section replay absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(sha(REPORT) == value["replay_report"]["sha256"],
            "section replay report drift")
    require(immutable_tree() and sha(ELF) == ELF_SHA,
            "section replay input drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        matrix = ISLAND.facade_interval_model_selftest()
        require(matrix["wrong-elf-section-index"] == "rejected",
                "wrong st_shndx mutation accepted")
        print("c2-link33-section-replay: SELFTEST PASS st_shndx+range")
        return 0
    value = check() if args.action == "check" else run_replay()
    print("c2-link33-section-replay: " + value["status"])
    return 0 if str(value["status"]).startswith("passed") else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, ISLAND.GateError, OSError, ValueError, KeyError,
            RuntimeError, json.JSONDecodeError) as error:
        print(f"c2-link33-section-replay: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
