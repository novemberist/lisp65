#!/usr/bin/env python3
"""Bind the stopped-device table-head discriminator and its claim boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-domain-media/"
    "device-blank-table-heads-20260824/capture.json")
DRIVER = ROOT / "tools/host-lisp/c2_v160_selector_bypass_blank_table_heads_capture.py"
PRIOR = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-selector-bypass-blank-cycle-attribution.json")
ELF = ROOT / (
    "build/c2.3/v1.6-boot-refill-selector-bypass-domain-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
OUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-selector-bypass-blank-table-heads-attribution.json")
FORMAT = "lisp65-c2.3-v1.6-selector-bypass-blank-table-heads-attribution-v1"

EXPECTED = {
    "capture": "b089f3fcf0bfbce00a0ec1df68df5d9fced66768474168f782ca498c429db653",
    "driver": "1ffdf81c8533e4fdc5fe4a9c8b229c8fca5079ba048e7035d9d57d262ca0daed",
    "prior": "1282b8f4ac446d17156345e961d0dbdc5f5943bdc46aa867f84103c28fe5b8c4",
    "ELF": "bbb1547779ea2c9366fa5a29633aa07061a3607fa753043071df1780cc5ea3e4",
}


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def assertions(value: dict[str, Any]) -> bool:
    heads = value["table_head_comparison"]
    return (
        value["stopped_state_identity"] == {
            "PC": "0x2020", "SP": "0x011e", "X": "0x00",
            "MAPH": "0x8000", "MAPL": "0x0000",
        }
        and len(heads) == 13
        and all(row["live_target"] == row["ELF_target"] for row in heads)
        and all(row["live_target"] != "0x8040" for row in heads)
        and value["contact_accounting"] == {
            "additional_stops": 0, "resumes": 0, "runs": 0,
            "resets": 0, "input_events": 0, "bytes_read": 26,
            "CPU_left_stopped": True,
        }
    )


def derive() -> dict[str, Any]:
    inputs = {
        "capture": bind(CAPTURE), "driver": bind(DRIVER),
        "prior": bind(PRIOR), "ELF": bind(ELF),
    }
    require({name: row["sha256"] for name, row in inputs.items()} == EXPECTED,
            "table-head attribution identity drift")
    capture = load(CAPTURE)
    prior = load(PRIOR)
    require(capture["comparison"] == {
        "divergent": [], "expected_count": 13, "observed_count": 13,
        "targets_8040": [],
        "verdict": "ALL TABLE HEADS MATCH: indirect table-dispatch class excluded",
    }, "capture comparison drift")
    require(capture["discipline"] == {
        "CPU_left_stopped": True, "additional_stops": 0, "input": 0,
        "resets": 0, "resumes": 0, "runs": 0,
    }, "capture discipline drift")
    expected_rows = prior["open_mechanism"][
        "next_minimal_live_discriminator_if_state_is_still_available"]["reads"]
    require(len(expected_rows) == 13, "prior table population drift")
    live_rows = capture["reads"]
    require(len(live_rows) == 13, "live table population drift")

    comparison = []
    for expected, live in zip(expected_rows, live_rows):
        address = int(live["physical_address"], 16)
        require(address == int(expected["address"], 16),
                "table address/order drift")
        target = int.from_bytes(bytes.fromhex(live["observed_hex"]), "little")
        elf_target = int(expected["expected"], 16)
        comparison.append({
            "address": f"0x{address:04x}", "x": 0,
            "ELF_target": f"0x{elf_target:04x}",
            "live_target": f"0x{target:04x}",
            "match": target == elf_target,
        })

    tuple_ = capture["tuple"]
    value = {
        "format": FORMAT,
        "status": "ATTRIBUTED: 13/13 TABLE HEADS MATCH; TABLE DISPATCH EXCLUDED",
        "recorded_on": "2026-08-24",
        "authority": (
            "owner authorized exactly 26 read-only bytes from the conserved stopped CPU"),
        "inputs": inputs,
        "stopped_state_identity": {
            key: tuple_[key] for key in ("PC", "SP", "X", "MAPH", "MAPL")
        },
        "contact_accounting": {
            "additional_stops": 0, "resumes": 0, "runs": 0,
            "resets": 0, "input_events": 0, "bytes_read": 26,
            "CPU_left_stopped": True,
        },
        "table_head_comparison": comparison,
        "decision": {
            "excluded_class": (
                "all thirteen X=0 indirect-table heads are byte-identical to "
                "ElfTruth and none targets the non-boundary $8040"),
            "remaining_classes": [
                "a corrupted RTS/RTI continuation before stack overwrite",
                "a live-mutated direct transfer outside the authorized reads",
            ],
            "next_instrument_to_price": (
                "a pre-wrap control-edge witness that records the final non-cycle "
                "transfer into $8040 before the 2020<->8040 cycle erases its predecessor"),
        },
        "claim_limit": (
            "This receipt excludes the X=0 indirect-table-dispatch class only. It "
            "does not identify the first ingress, authorize a fix, build, medium, "
            "resume, reset or another device read."),
    }
    require(assertions(value), "table-head attribution assertions failed")
    return value


def selftest() -> None:
    value = derive()
    mutations = []
    short = json.loads(json.dumps(value))
    short["table_head_comparison"].pop()
    mutations.append(short)
    drift = json.loads(json.dumps(value))
    drift["table_head_comparison"][0]["live_target"] = "0x8040"
    mutations.append(drift)
    resumed = json.loads(json.dumps(value))
    resumed["contact_accounting"]["resumes"] = 1
    mutations.append(resumed)
    for mutation in mutations:
        require(not assertions(mutation), "table-head attribution mutation accepted")
    print(f"v1.6 selector blank table-head attribution: SELFTEST PASS "
          f"mutations={len(mutations)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    if action == "selftest":
        selftest()
        return 0
    value = derive()
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if action == "write":
        OUT.write_text(encoded, encoding="utf-8")
    else:
        require(OUT.is_file() and OUT.read_text(encoding="utf-8") == encoded,
                "selector blank table-head attribution receipt drift")
    print("v1.6 selector blank table-head attribution: PASS heads=13/13 "
          "table-dispatch=excluded ingress=open")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError) as error:
        print(f"selector-blank-table-head-attribution: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
