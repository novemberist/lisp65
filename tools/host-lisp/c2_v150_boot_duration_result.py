#!/usr/bin/env python3
"""Bind the same-device v1.4.0/v1.5.0 cold-reset boot comparison."""

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
V14 = ROOT / (
    "build/release-v1.4.0/pack-product-a/lisp65-1.4.0/media/"
    "lisp65-product.d81")
V15 = ROOT / (
    "build/c2.3/v2.1-wysiwyg-text-recovery-media/shared-system/"
    "lisp65-product.d81")
CONTACT = ROOT / "build/c2.3/v1.5.0-boot-duration-contact"
V14_READBACK = CONTACT / "V14BOOT-readback.d81"
V15_READBACK = CONTACT / "V15BOOT-readback.d81"
RECEIPT = ARCH / "c2.3-v1.5.0-boot-duration-device-receipt.json"
FORMAT = "lisp65-c2.3-v1.5.0-boot-duration-device-v1"
STATUS = "PASS: SAME-DEVICE BOOT COMPARISON; HALT-1 DISPOSITION PENDING"
V14_SHA = "ed4e5c7281913e351550f10533a585c2516a7a0a4214a66cf93cf35252aee306"
V15_SHA = "b1445da2a0d7c0d673b2481723b1f1f922008606066efc8c46ed0e51f0e96831"


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"evidence absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def derive() -> dict[str, Any]:
    device = load(DEVICE)
    require(device.get("status") ==
            "PASS: LINK-116 CANONICAL D1-D5 HARDWARE GREEN; HALT-1-PENDING",
            "canonical D1-D5 device authority absent")
    require(V14.read_bytes() == V14_READBACK.read_bytes(),
            "v1.4.0 staged-media readback mismatch")
    require(V15.read_bytes() == V15_READBACK.read_bytes(),
            "v1.5.0 staged-media readback mismatch")
    require(bind(V14)["sha256"] == V14_SHA and bind(V15)["sha256"] == V15_SHA,
            "boot-comparison product identity drift")
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-18",
        "status": STATUS,
        "authority": {
            "canonical_D1_D5": bind(DEVICE),
            "recorder": bind(Path(__file__).resolve()),
        },
        "choreography": {
            "same_physical_device": True,
            "same_owner_stopwatch": True,
            "start": "physical-reset-press-after-Freezer-mount",
            "stop": "first-visible-lisp65-prompt",
            "post_reset_automated_accesses": 0,
            "unit": "whole-seconds-owner-observed",
        },
        "measurements": {
            "v1.4.0": {
                "seconds": 31,
                "remote_name": "V14BOOT.D81",
                "source": bind(V14),
                "readback": bind(V14_READBACK),
                "terminal": "lisp65>",
            },
            "v1.5.0-candidate": {
                "seconds": 36,
                "remote_name": "V15BOOT.D81",
                "source": bind(V15),
                "readback": bind(V15_READBACK),
                "terminal": "lisp65>",
            },
        },
        "comparison": {
            "delta_seconds": 5,
            "relative_slowdown_percent": 16.1,
            "new_duration_class": False,
            "candidate_liveness_visible": True,
            "reason": (
                "v1.5 uses hardware-proved MAP CPU transport for the bulk "
                "library path and retains the safety work introduced by the "
                "F018B closure"),
        },
        "owner_disposition": None,
        "next": "halt-1-owner-choice-ship-36s-or-pull-boot-snapshot-forward",
        "claim_limit": (
            "Same-device cold-reset-to-prompt comparison only. The recorded "
            "five-second slowdown is release evidence; whether it ships is "
            "reserved to Halt #1."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    measurements = value.get("measurements", {})
    comparison = value.get("comparison", {})
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and measurements.get("v1.4.0", {}).get("seconds") == 31
        and measurements.get("v1.5.0-candidate", {}).get("seconds") == 36
        and measurements.get("v1.4.0", {}).get("source", {}).get("sha256") == V14_SHA
        and measurements.get("v1.5.0-candidate", {}).get("source", {}).get("sha256") == V15_SHA
        and comparison.get("delta_seconds") == 5
        and comparison.get("relative_slowdown_percent") == 16.1
        and comparison.get("new_duration_class") is False
        and value.get("choreography", {}).get("post_reset_automated_accesses") == 0
        and value.get("owner_disposition") is None
        and value.get("next") ==
            "halt-1-owner-choice-ship-36s-or-pull-boot-snapshot-forward",
        "boot-duration result claim drift")
    if verify:
        require(value == derive(), "boot-duration device receipt stale")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "alter-baseline": lambda x: x["measurements"]["v1.4.0"].update(seconds=30),
        "alter-candidate": lambda x: x["measurements"]["v1.5.0-candidate"].update(seconds=35),
        "alter-delta": lambda x: x["comparison"].update(delta_seconds=4),
        "alter-v14-identity": lambda x: x["measurements"]["v1.4.0"]["source"].update(sha256="0" * 64),
        "claim-automated-observation": lambda x: x["choreography"].update(post_reset_automated_accesses=1),
        "preempt-owner": lambda x: x.update(owner_disposition="ship"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate(trial, verify=False)
        except ResultError:
            rejected.append(name)
    require(rejected == list(cases), "boot-duration mutation survived")
    return rejected


def write() -> int:
    require(not RECEIPT.exists(), "boot-duration device receipt exists")
    value = derive()
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("v1.5 boot-duration device result: PASS 31s -> 36s delta=+5s")
    return 0


def check() -> int:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value), "boot-duration mutation set drift")
    print("v1.5 boot-duration device check: PASS 31s -> 36s delta=+5s")
    return 0


def selftest() -> int:
    value = derive()
    validate(value, verify=False)
    mutations(value)
    print("v1.5 boot-duration device selftest: PASS mutations=6")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    return {"write": write, "check": check, "selftest": selftest}[
        parser.parse_args().action]()


if __name__ == "__main__":
    raise SystemExit(main())
