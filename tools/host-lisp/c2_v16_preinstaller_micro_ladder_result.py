#!/usr/bin/env python3
"""Permanently verify the pre-installer micro-ladder device result."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v16_preinstaller_micro_ladder as BUILD  # noqa: E402
import c2_v16_preinstaller_micro_ladder_contact as CONTACT  # noqa: E402


DEVICE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-preinstaller-micro-ladder-device-receipt.json")


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def audit(value: dict[str, Any]) -> None:
    require(value["format"] ==
            "lisp65-c2.3-v1.6-preinstaller-micro-ladder-device-v1"
            and value["recorded_on"] == "2026-08-06", "receipt identity drift")
    raw = bytes.fromhex(value["ladder"]["raw_hex"])
    status = bytes.fromhex(value["state"]["status_hex"])
    require(raw == bytes.fromhex("0ee1e2e300d5")
            and CONTACT.classify(raw, status) == "OWNERSHIP-FAIL-CLOSED-EXIT"
            and value["status"] == "OWNERSHIP-FAIL-CLOSED-EXIT"
            and value["ladder"]["classification"] ==
                "OWNERSHIP-FAIL-CLOSED-EXIT",
            "ladder result/classification drift")
    require(value["ladder"]["decision_table"] ==
            BUILD.expected()["facts"]["decision_table"],
            "decision-table drift")
    require(value["quiet"]["floor_seconds"] == 27.653
            and value["quiet"]["observed_seconds"] >= 27.653,
            "quiet-floor drift")
    require(value["tuple_first"]["confirmed_before_data_reads"] is True
            and value["tuple_first"]["registers"] == {
                "A": "0x80", "B": "0x00", "MAPH": "0x8000",
                "MAPL": "0x0000", "PC": "0xb5fd", "SP": "0x01f6",
                "X": "0x03", "Y": "0x02", "Z": "0x00",
                "raw_hex": value["tuple_first"]["registers"]["raw_hex"],
                "row": value["tuple_first"]["registers"]["row"],
                "tail": value["tuple_first"]["registers"]["tail"]},
            "tuple-first binding drift")
    code = value["code_identity"]
    require(code["CPU_view"] is True and len(code["reads"]) == 1
            and code["reads"][0]["view"] == "CPU-resolved-0x0777xxxx"
            and code["owner"]["selected_owner"] == "unresolved"
            and code["owner"]["unique"] is False
            and code["owner"]["symbol_interpretation_allowed"] is False,
            "CPU-view/code-owner claim drift")
    require(value["state"] == {
        "C2J_nonzero_bytes": 0, "boot_witness": "0x44",
        "first_error_hex": "0000", "health_hex": "00000000",
        "phase_owner": "0x00", "status_hex": "0000"},
        "health/status claim drift")
    data = value["raw"]
    require(bytes.fromhex(data["C2J"]["hex"]) == bytes(64)
            and bytes.fromhex(data["phase"]["hex"]) == bytes(304)
            and data["state"]["hex"] == "0ee1e2e300d5",
            "raw data drift")
    require(all(row["view"] == "physical-Bank5-C2J"
                for row in data["C2J"]["reads"])
            and all(row["view"] == "physical-bank0-RAM-underlay"
                    for name, item in data.items() if name != "C2J"
                    for row in item["reads"]),
            "physical-data-view drift")
    require(value["result"] == {
        "CPU_left_stopped": True, "R_A_I_G": None,
        "classification": "OWNERSHIP-FAIL-CLOSED-EXIT",
        "measured_forms": 0, "mem_init_answer": None, "physical_RUNs": 1,
        "product_fault": None, "stops": 1}, "result/claim boundary drift")


def selftest() -> dict[str, Any]:
    base = load(DEVICE); audit(base)
    mutations = [
        (["recorded_on"], "2026-08-07"),
        (["ladder", "raw_hex"], "0ee1e2d300d5"),
        (["ladder", "classification"], "CHROUT-NONRETURN-OR-MAP-NOT-RESTORED"),
        (["status"], "HAND-OFF-TO-EXISTING-STATUS-TABLE"),
        (["quiet", "observed_seconds"], 1.0),
        (["tuple_first", "confirmed_before_data_reads"], False),
        (["tuple_first", "registers", "MAPH"], "0xb300"),
        (["code_identity", "CPU_view"], False),
        (["code_identity", "owner", "selected_owner"], "diagnostic-PRG"),
        (["code_identity", "owner", "symbol_interpretation_allowed"], True),
        (["state", "C2J_nonzero_bytes"], 1),
        (["state", "boot_witness"], "0xd7"),
        (["raw", "state", "reads", 0, "view"], "CPU-view"),
        (["result", "physical_RUNs"], 2),
        (["result", "stops"], 2),
        (["result", "CPU_left_stopped"], False),
        (["result", "mem_init_answer"], "never-built"),
        (["result", "R_A_I_G"], "R"),
        (["result", "product_fault"], "ownership"),
    ]
    rejected: dict[str, str] = {}
    for index, (path, replacement) in enumerate(mutations, 1):
        trial = deepcopy(base); cursor: Any = trial
        for key in path[:-1]: cursor = cursor[key]
        cursor[path[-1]] = replacement
        try: audit(trial)
        except ResultError as error: rejected[f"mutation-{index:02d}"] = str(error)
        else: raise ResultError(f"result mutation survived: {path}")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "classification": base["status"], "rejected": rejected}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "selftest"))
    args = parser.parse_args()
    value = selftest()
    if args.action == "check":
        value = {"status": "PASS", "mutations": value["mutations"],
                 "classification": value["classification"]}
    print(json.dumps(value, indent=2, sort_keys=True)); return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except (ResultError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"PREINSTALLER MICRO-LADDER RESULT FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
