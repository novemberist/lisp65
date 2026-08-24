#!/usr/bin/env python3
"""Seal and check the v1.6 four-arc physical input measurement."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
SESSION = ROOT / "config/c2-v160-bound-origin-measurement-device-session.json"
MEDIA = ARCH / "c2.3-v1.6-bound-origin-measurement-media-receipt.json"
CAPTURE = ROOT / (
    "build/c2.3/v1.6-bound-origin-measurement-contact/counters-read.bin")
RECEIPT = ARCH / "c2.3-v1.6-bound-origin-measurement-result-receipt.json"
AUTHORIZATION = "166227be"
FORMAT = "lisp65-c2-v160-bound-origin-measurement-result-v1"
PHYSICAL_ATTEMPTS = 11
VISIBLE_TARGET = "a(a(a(a("


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("pressed > raw", "raw > seen", "seen > stored",
                  "stored > taken", "one short contact"):
        require(token in text, f"measurement-result authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def classify(physical: int, counters: list[int]) -> str:
    require(len(counters) == 4 and all(0 <= value < 256 for value in counters),
            "four 8-bit counters required")
    raw, seen, stored, taken = counters
    require(0 <= physical < 256, "physical attempt count must stay below 256")
    if physical > raw:
        return "keyboard-core-before-queue-present-observation"
    if raw > seen:
        return "irq-queue-read-or-filtering"
    if seen > stored:
        return "ring-write-or-admission"
    if stored > taken:
        return "consumer-take-path"
    if physical == raw == seen == stored == taken:
        return "no-loss-display-or-timing"
    return "invalid-nonmonotone-witness"


def derive(capture: bytes) -> dict[str, Any]:
    require(len(capture) == 4, "counter capture must be exactly four bytes")
    counters = list(capture)
    verdict = classify(PHYSICAL_ATTEMPTS, counters)
    require(verdict == "keyboard-core-before-queue-present-observation",
            f"bound decision-table verdict drift: {verdict}")
    require(counters == [len(VISIBLE_TARGET)] * 4,
            "visible target and internal counters disagree")
    session = load(SESSION)
    witness = session["counter_witness"]
    require(witness["addresses"] == {"raw": "0xBCFC", "seen": "0xBCFD",
            "stored": "0xBCFE", "taken": "0xBCFF"}
            and witness["maximum_physical_events"] == 255
            and witness["target_visible_text"] == VISIBLE_TARGET,
            "measurement session contract drift")
    media = load(MEDIA)
    require(media["status"] ==
                "PASS: V1.6 BOUND-ORIGIN MEASUREMENT MEDIA READY",
            "measurement media predecessor drift")
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-21",
        "status": "PASS: V1.6 INPUT LOSS LOCATED BEFORE RAW QUEUE WITNESS",
        "authority": authority(),
        "inputs": {"session": bind(SESSION), "media": bind(MEDIA)},
        "device_contact": {
            "contacts": 1, "stops": 1, "resumes": 0,
            "physical_attempts": PHYSICAL_ATTEMPTS,
            "visible_target": VISIBLE_TARGET,
            "visible_characters": len(VISIBLE_TARGET),
            "counter_addresses": ["0xBCFC", "0xBCFD", "0xBCFE", "0xBCFF"],
            "counter_order": ["raw", "seen", "stored", "taken"],
            "counter_bytes_hex": capture.hex(),
            "counter_values": counters,
            "counter_width_bits": 8,
            "capture": {"path": CAPTURE.relative_to(ROOT).as_posix(),
                        "bytes": len(capture),
                        "sha256": hashlib.sha256(capture).hexdigest()}},
        "decision": {
            "verdict": verdict,
            "arithmetic": "physical 11 > raw 8 = seen 8 = stored 8 = taken 8",
            "exonerated": ["IRQ read/filter", "ring admission/write",
                           "consumer/take", "Comfort service time as loss cause"],
            "located": "physical keyboard/core boundary before queue-present observation"},
        "release_effect": {
            "v1.6_items_1_2": "continue; this is not an owned v1.6 loss arc",
            "v1.6_items_3_4": "remain may-slip and are expected to slip",
            "device_followup": "none for this classification",
            "claim_limit": ("the contact locates these three absent attempts before "
                            "the product raw witness; it does not distinguish keyboard "
                            "matrix, debounce, core firmware, or KERNAL queue internals")}}


def validate(value: dict[str, Any]) -> None:
    capture = bytes.fromhex(value["device_contact"]["counter_bytes_hex"])
    require(value == derive(capture), "measurement-result receipt drift")


def write() -> None:
    require(CAPTURE.is_file() and not CAPTURE.is_symlink(),
            "device counter capture absent")
    value = derive(CAPTURE.read_bytes())
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 bound-origin measurement result: PASS 11>8=8=8=8")


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    if CAPTURE.is_file():
        raw = CAPTURE.read_bytes()
        require(value["device_contact"]["capture"] == {
            "path": CAPTURE.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()},
            "local counter capture differs from sealed evidence")
    print("v1.6 bound-origin measurement result: CHECK PASS verdict=platform-boundary")


def selftest() -> None:
    value = load(RECEIPT)
    rejected = 0
    for mutate in (
        lambda row: row["device_contact"].update({"physical_attempts": 8}),
        lambda row: row["device_contact"].update({"counter_bytes_hex": "08070808"}),
        lambda row: row["decision"].update({"verdict": "consumer-take-path"}),
        lambda row: row["release_effect"].update({"device_followup": "required"}),
    ):
        candidate = copy.deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except RuntimeError:
            rejected += 1
        else:
            raise RuntimeError("measurement-result mutation survived")
    require(rejected == 4, "measurement-result mutation count drift")
    print("v1.6 bound-origin measurement result: SELFTEST PASS mutations=4")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    if action == "write":
        write()
    elif action == "check":
        check()
    else:
        selftest()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
