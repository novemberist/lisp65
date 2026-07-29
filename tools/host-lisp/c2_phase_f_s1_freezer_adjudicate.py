#!/usr/bin/env python3
"""Apply the existing C2 Freezer volatile-cell contract to Link-67 S1."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_phase_f_s1_link67 as S1  # noqa: E402


CONTRACT = ROOT / "config/c2-c1-freezer-cutpoint-contract.json"
ALLOWED = {0xFF83, 0xFF84, 0xFF86, 0xFF89}


def main() -> int:
    try:
        contract = S1.load(CONTRACT)
        S1.require(
            contract["hardware_protocol"]["freeze_identity"]
            == (
                "Bank 2 and Bank 3 byte-identical; Bank 5 C2D/export/C2J "
                "byte-identical; E000 byte-identical except the four "
                "contracted volatile bytes FF83, FF84, FF86 and FF89; "
                "FF89 is the source-less-path D019 diagnostic witness and "
                "not product state"),
            "canonical Freezer volatile-cell contract drift",
        )
        observations = S1.load(S1.OBSERVATIONS)
        S1.require(
            tuple(row["id"] for row in observations["rows"])
            == S1.PRE_FREEZER_IDS,
            "Freezer adjudication requires exactly ten passed prior rows",
        )
        before = S1.bind_capture_set("pre-freezer")
        after = S1.bind_capture_set("post-freezer")
        for name in ("bank2", "bank3", "bank5"):
            S1.require(
                before[name]["sha256"] == after[name]["sha256"],
                f"Freezer changed bound Chip domain: {name}",
            )
        old = (S1.OUT / "pre-freezer-e000.bin").read_bytes()
        new = (S1.OUT / "post-freezer-e000.bin").read_bytes()
        S1.require(len(old) == len(new) == 8192, "E000 capture span drift")
        differences = [
            {
                "address": f"0x{0xE000 + offset:04x}",
                "before": f"0x{left:02x}",
                "after": f"0x{right:02x}",
            }
            for offset, (left, right) in enumerate(zip(old, new))
            if left != right
        ]
        addresses = {int(row["address"], 16) for row in differences}
        S1.require(
            addresses <= ALLOWED and len(differences) <= 3,
            f"Freezer changed uncontracted E000 bytes: {differences}",
        )
        observations["rows"].append({
            "id": "idle-freezer-roundtrip",
            "status": "passed",
            "operator_action": "physical Freezer; return with F3",
            "identity_before": before,
            "identity_after": after,
            "E000": {
                "preserved_bytes": 8192 - len(differences),
                "total_bytes": 8192,
                "contract_live_cells": [
                    f"0x{address:04x}" for address in sorted(ALLOWED)],
                "observed_differences": differences,
            },
            "authority": {
                "volatile_cell_contract": S1.bind(CONTRACT),
                "adjudicator": S1.bind(Path(__file__)),
            },
        })
        observations["status"] = "freezer-passed-awaiting-final-row"
        S1.atomic_json(S1.OBSERVATIONS, observations)
        print(
            "c2-phase-f-s1-freezer-adjudicate: PASS "
            f"chip=3/3 e000={8192 - len(differences)}/8192 "
            f"volatile={','.join(row['address'] for row in differences) or 'none'}")
    except (OSError, ValueError, KeyError, json.JSONDecodeError, S1.S1Error) as error:
        print(f"c2-phase-f-s1-freezer-adjudicate: FIRST RED: {error}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
