#!/usr/bin/env python3
"""Bind the owner-approved v1.5.0 Halt #1 ship disposition."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
DEVICE = ARCH / "c2.3-v2.1-link116-name-freight-device-receipt.json"
BOOT = ARCH / "c2.3-v1.5.0-boot-duration-device-receipt.json"
RECEIPT = ARCH / "c2.3-v1.5.0-halt-1-owner-decision-receipt.json"
FORMAT = "lisp65-c2.3-v1.5.0-halt-1-owner-decision-v1"
STATUS = "PASS: HALT #1 OWNER ACCEPTED; PHASE E OPEN"


class HaltError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise HaltError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def derive() -> dict[str, Any]:
    device = load(DEVICE)
    boot = load(BOOT)
    require(device.get("status") ==
            "PASS: LINK-116 CANONICAL D1-D5 HARDWARE GREEN; HALT-1-PENDING",
            "D1-D5 authority is not green")
    require(boot.get("status") ==
            "PASS: SAME-DEVICE BOOT COMPARISON; HALT-1 DISPOSITION PENDING",
            "boot-comparison authority is not green")
    require(boot["measurements"]["v1.4.0"]["seconds"] == 31
            and boot["measurements"]["v1.5.0-candidate"]["seconds"] == 36
            and boot["comparison"]["delta_seconds"] == 5,
            "boot-comparison values drift")
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-18",
        "status": STATUS,
        "authority": {"D1_D5": bind(DEVICE), "boot_comparison": bind(BOOT),
                      "recorder": bind(Path(__file__).resolve())},
        "table": {
            "D1_D5": "green-19-physical-rows",
            "terminal_return_guard": "clean-four-empty-records-no-restore",
            "user_headroom": {
                "observed": {"symbol_slots": 34, "namepool_bytes": 545},
                "minimum": {"symbol_slots": 32, "namepool_bytes": 384},
                "status": "pass",
            },
            "boot_seconds": {"v1.4.0": 31, "v1.5.0": 36, "delta": 5},
        },
        "owner_decision": {
            "word": "Ship",
            "owner_confirmed": True,
            "ship_measured_36_second_boot": True,
            "release_notes_must_name_duration_and_reason": True,
            "pull_boot_snapshot_before_v1.5.0": False,
        },
        "snapshot_successor": {
            "status": "deferred-post-v1.5.0",
            "register": "docs/reference/parked-items-register.md",
        },
        "phase_E": "open",
        "halt_2": "closed-until-release-closure",
        "product_byte_changes_authorized": 0,
        "next": "phase-E-documentation-assets-double-readback-then-halt-2",
        "claim_limit": (
            "Halt #1 accepts the already qualified candidate and its measured "
            "36-second cold-reset boot. It authorizes Phase E only; publication "
            "still requires Halt #2 and the owner's literal publish word."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    decision = value.get("owner_decision", {})
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and decision == {
            "word": "Ship", "owner_confirmed": True,
            "ship_measured_36_second_boot": True,
            "release_notes_must_name_duration_and_reason": True,
            "pull_boot_snapshot_before_v1.5.0": False}
        and value.get("phase_E") == "open"
        and value.get("halt_2") == "closed-until-release-closure"
        and value.get("product_byte_changes_authorized") == 0
        and value.get("next") ==
            "phase-E-documentation-assets-double-readback-then-halt-2",
        "Halt #1 decision drift")
    if verify:
        require(value == derive(), "Halt #1 receipt stale")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "pull-snapshot": lambda x: x["owner_decision"].update(
            {"pull_boot_snapshot_before_v1.5.0": True}),
        "hide-boot": lambda x: x["owner_decision"].update(
            release_notes_must_name_duration_and_reason=False),
        "open-halt2": lambda x: x.update(halt_2="open"),
        "authorize-product-byte": lambda x: x.update(product_byte_changes_authorized=1),
        "close-phase-e": lambda x: x.update(phase_E="closed"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate(trial, verify=False)
        except HaltError:
            rejected.append(name)
    require(rejected == list(cases), "Halt #1 mutation survived")
    return rejected


def write() -> int:
    require(not RECEIPT.exists(), "Halt #1 receipt already exists")
    value = derive()
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("v1.5 Halt #1: PASS owner=Ship boot=36s Phase-E=open")
    return 0


def check() -> int:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value), "Halt #1 mutation set drift")
    print("v1.5 Halt #1 check: PASS owner=Ship boot=36s Phase-E=open")
    return 0


def selftest() -> int:
    value = derive(); validate(value, verify=False); mutations(value)
    print("v1.5 Halt #1 selftest: PASS mutations=5")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    return {"write": write, "check": check, "selftest": selftest}[
        parser.parse_args().action]()


if __name__ == "__main__":
    raise SystemExit(main())
