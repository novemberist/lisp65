#!/usr/bin/env python3
"""Replay the corrected Island-provenance gate without linking anything."""

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


FIRST_RED_OUT = ROOT / (
    "build/c2.2/substitution/link33-bss-triage-facade15-placement-probe")
FIRST_RED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-bss-triage-facade15-placement-probe-receipt.json")
FIRST_RED_RECEIPT_SHA = (
    "59209a27d73a976df4f74f57683f720b9d6a1cfe6633c74f2bb291923351fa3f")
ELF = FIRST_RED_OUT / "bss-triage-facade15-placement-seed.prg.elf"
ELF_SHA = "6644da0e46078dd0c8819188c25e9bd5b878ee387cf01719027cbba9d9c50cf3"
PRG = FIRST_RED_OUT / "bss-triage-facade15-placement-seed.prg"
PRG_SHA = "75924e481118e5510e75d02519f2cc6f50601bde69988fe20b6abe023558d3d8"
LINK32 = ROOT / (
    "build/c2.2/substitution/product-link-32-preinstall-island-guard/"
    "lisp65-c2-substitution-linked.prg")
LINK32_SHA = "189548ea52b9af748217a0da94b7dc1d5daa5f17d190f5817f2fb4af486a676a"
OUT = ROOT / "build/c2.2/substitution/link33-facade15-provenance-replay"
REPORT = OUT / "preinstall-island-provenance-replay.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-facade15-provenance-replay-receipt.json")
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
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def immutable_tree() -> dict[str, str]:
    files = sorted(path for path in FIRST_RED_OUT.rglob("*") if path.is_file())
    require(files and all(path.stat().st_mode & 0o777 == 0o444 for path in files),
            "First-Red WPLTO evidence is not entirely read-only")
    return {path.relative_to(FIRST_RED_OUT).as_posix(): sha(path)
            for path in files}


def run_replay() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "provenance replay is one-shot and already has output")
    require(sha(FIRST_RED_RECEIPT) == FIRST_RED_RECEIPT_SHA,
            "facade-15 First-Red receipt drift")
    require(sha(ELF) == ELF_SHA and sha(PRG) == PRG_SHA,
            "facade-15 WPLTO identity drift")
    require(sha(LINK32) == LINK32_SHA, "Link-32 rollback identity drift")
    before = immutable_tree()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    authorization = contract["formal_reopening_2026_07_21"][
        "independent_bss_triage_2026_07_21"][
            "facade15_successor_authorization"][
                "provenance_replay_authorization"]
    require(authorization["status"] == "authorized-pending"
            and authorization["compiler_runs"] == 0
            and authorization["linker_runs"] == 0,
            "pure-replay authorization drift")

    gate = ISLAND.static_elf_gate(ELF)
    require(gate["status"] == "passed-static-preinstallation-Island-gate",
            "corrected preinstallation-Island gate did not pass")
    interval = gate["fixed_facade_contract_interval"]
    require(interval == {
        "section": ".lisp65_c2_host_facade",
        "name": "c2_facade_handle_normalize",
        "address": 0xB5EE,
        "bytes": 3,
        "end_exclusive": 0xB5F1,
        "provenance": "fixed-facade-contract",
    }, f"contract-derived facade interval drift: {interval}")
    required_mutations = {
        "wrong-address-contract-object": "rejected",
        "wrong-size-contract-object": "rejected",
        "unlisted-facade-relocation-address": "rejected",
    }
    require(all(gate["negative_matrix"].get(name) == result
                for name, result in required_mutations.items()),
            "facade provenance mutation matrix incomplete")
    after = immutable_tree()
    require(after == before, "pure replay modified its immutable input tree")

    report = {
        "format": "lisp65-c2-link33-facade15-provenance-replay-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-pure-gate-replay-no-link",
        "execution_accounting": {
            "compiler_runs": 0,
            "linker_runs": 0,
            "product_links": 0,
            "hardware_runs": 0,
        },
        "immutable_input": {
            "first_red_receipt": bind(FIRST_RED_RECEIPT),
            "elf": bind(ELF),
            "prg": bind(PRG),
            "file_count": len(before),
            "tree_unchanged": True,
        },
        "corrected_gate": gate,
        "capacity_inherited_from_immutable_map": {
            "bank0_text": 41,
            "ordinary_bank0_bss": 229,
            "fixed_hot_block": 33,
            "resident_island": 7,
            "e000": 115,
            "e000_debit": 422,
            "claim": "no new measurement; SHA-bound WPLTO map provenance only",
        },
        "rollback_line": {"link32_sha256": LINK32_SHA, "status": "untouched"},
        "next_gate": "bind final E000 floor to 115 bytes, then fresh Link 33",
    }
    OUT.mkdir(parents=True)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    receipt = {
        **report,
        "authority": {
            "plan": bind(PLAN),
            "contract": bind(CONTRACT),
            "contract_document": bind(CONTRACT_DOC),
        },
        "replay_report": bind(REPORT),
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(REPORT, 0o444)
    os.chmod(OUT, 0o555)
    os.chmod(RECEIPT, 0o444)
    return receipt


def check() -> dict[str, Any]:
    require(RECEIPT.is_file() and REPORT.is_file(), "replay receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") == "passed-pure-gate-replay-no-link",
            "replay receipt status drift")
    require(sha(REPORT) == value["replay_report"]["sha256"],
            "replay report drift")
    require(sha(ELF) == ELF_SHA and immutable_tree(),
            "immutable replay input drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        matrix = ISLAND.facade_interval_model_selftest()
        require(matrix["wrong-address-contract-object"] == "rejected"
                and matrix["wrong-size-contract-object"] == "rejected",
                "facade provenance selftest red")
        print("c2-link33-facade15-replay: SELFTEST PASS interval=b5ee+3")
        return 0
    value = check() if args.action == "check" else run_replay()
    print("c2-link33-facade15-replay: PASS status=" + value["status"]
          + " links=0 floor-candidate=115")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, ISLAND.GateError, OSError, ValueError, KeyError,
            RuntimeError, json.JSONDecodeError) as error:
        print(f"c2-link33-facade15-replay: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
