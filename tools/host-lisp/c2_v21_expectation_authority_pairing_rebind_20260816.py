#!/usr/bin/env python3
"""Bind historical expectation sweeps to the approved ABI pairing successor."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v21_abi_vocabulary_pairing as PAIR  # noqa: E402
import evidence_era as ERA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
PINNED = ARCH / "c2.3-v2.1-pinned-constant-sweep-receipt.json"
SHAPE = ARCH / "c2.3-v2.1-expectation-shape-sweep-receipt.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-expectation-authority-pairing-rebind-20260816-receipt.json")
CANONICAL = ROOT / "tools/host-lisp/c2_lite_canonical_product.py"
PRODUCER = ROOT / "tools/host-lisp/c2_asm_leaf_abi_gate.py"
GATES = ROOT / "mk/gates.mk"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "9180e59a"
PINNED_SHA256 = "b625e658973c1b8e5965f71756218bba248ec059ada36d9f6259612671874a50"
SHAPE_SHA256 = "df4affd03f1eda605dc88c903a8bd6364862a896cd0616dec766814cdad92346"
SEAL_ERA_COMMIT = "e502b1d0812e89a1b68ad465784822e4a99b3c02"
SEALED_MUTATIONS = [
    "rewrite-pinned-history", "change-shape-claim",
    "restore-vocabulary-pin", "restore-historical-check", "run-WPLTO",
    "contact-device",
]


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    authority = git_bind(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{authority['commit']}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().split())
    require("producer/consumer pairing clause" in text
            and "current vocabulary" in text
            and "artifact-only qualification replay" in text,
            "expectation authority-pairing authorization absent")
    return authority


def historical() -> tuple[dict[str, Any], dict[str, Any]]:
    require(bind(PINNED)["sha256"] == PINNED_SHA256,
            "historical pinned-constant sweep was rewritten")
    require(bind(SHAPE)["sha256"] == SHAPE_SHA256,
            "historical expectation-shape sweep was rewritten")
    pinned = load(PINNED); shape = load(SHAPE)
    require(
        pinned.get("status") ==
            "PASS: remaining qualification constants candidate-derived; pinned=0"
        and pinned.get("sweep", {}).get("pinned_count") == 0
        and shape.get("status") ==
            "PASS: remaining candidate expectation forms derive or classify"
        and shape.get("sweep", {}).get("pinned_candidate_shape_count") == 0,
        "historical expectation sweep semantic evidence drift")
    return pinned, shape


def pairing() -> dict[str, Any]:
    value = load(PAIR.RECEIPT); rejected = value.pop("mutations_rejected", None)
    current = PAIR.derive()
    PAIR.validate_sealed(value, current)
    require(rejected == PAIR.SEALED_MUTATIONS
            and value["pairing"]["historical_pin_present"] is False,
            "approved ABI vocabulary pairing successor drift")
    return value


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = GATES.read_text(encoding="utf-8") \
        if source_override is None else source_override
    old_checks = (
        "python3 tools/host-lisp/c2_v21_pinned_constant_sweep.py check",
        "python3 tools/host-lisp/c2_v21_expectation_shape_sweep.py check",
    )
    require(not any(command in source for command in old_checks),
            "historical expectation consumer still gates the paired source")
    command = (
        "python3 tools/host-lisp/"
        "c2_v21_expectation_authority_pairing_rebind_20260816.py check")
    require(source.count(command) >= 2,
            "paired expectation successor absent from live gates")
    return {"status": "PASS: historical sweeps consume paired successor",
            "historical_live_checks": 0,
            "successor_check_commands": source.count(command)}


def derive() -> dict[str, Any]:
    pinned, shape = historical()
    paired = pairing()
    return {
        "format": "lisp65-c2.3-v21-expectation-authority-pairing-rebind-v1",
        "recorded_on": "2026-08-16",
        "status": "PASS: expectation sweeps follow approved ABI pairing",
        "authority": {"owner": authorization(),
            "historical_pinned_sweep": bind(PINNED),
            "historical_shape_sweep": bind(SHAPE),
            "ABI_pairing": bind(PAIR.RECEIPT),
            "canonical_consumer": ERA.era_bind(SEAL_ERA_COMMIT, CANONICAL),
            "ABI_producer": ERA.era_bind(SEAL_ERA_COMMIT, PRODUCER),
            "driver": ERA.era_bind(SEAL_ERA_COMMIT, DRIVER)},
        "historical": {"receipts_rewritten": False,
            "claims_changed": False,
            "pinned_count": pinned["sweep"]["pinned_count"],
            "pinned_shape_count":
                shape["sweep"]["pinned_candidate_shape_count"]},
        "successor": {"pairing_status": paired["status"],
            "symbol": paired["pairing"]["symbol"],
            "value": paired["pairing"]["value"],
            "historical_pin_present": False},
        "live_gate": source_gate(),
        "execution_lock": {"WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": (
            "Authority-consumer rebind only. Historical sweep evidence and "
            "claims remain unchanged; no product or device action."),
    }


def validate(value: dict[str, Any]) -> None:
    require(
        value.get("status") ==
            "PASS: expectation sweeps follow approved ABI pairing"
        and value["historical"] == {"receipts_rewritten": False,
            "claims_changed": False, "pinned_count": 0,
            "pinned_shape_count": 0}
        and value["successor"]["historical_pin_present"] is False
        and value["live_gate"]["historical_live_checks"] == 0
        and not any(value["execution_lock"].values()),
        "expectation authority-pairing rebind drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-pinned-history": lambda x: x["historical"].update(
            receipts_rewritten=True),
        "change-shape-claim": lambda x: x["historical"].update(
            claims_changed=True),
        "restore-vocabulary-pin": lambda x: x["successor"].update(
            historical_pin_present=True),
        "restore-historical-check": lambda x: x["live_gate"].update(
            historical_live_checks=1),
        "run-WPLTO": lambda x: x["execution_lock"].update(WPLTO_runs=1),
        "contact-device": lambda x: x["execution_lock"].update(
            device_contacts=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "expectation pairing mutation survived")
    return rejected


def write() -> None:
    require(not RECEIPT.exists(), "expectation pairing rebind receipt exists")
    value = derive(); validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("expectation authority pairing: PASS historical=2 successor=ABI-pair")


def check() -> None:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value); expected = derive(); validate(expected)
    require(value == expected and rejected == SEALED_MUTATIONS
            and mutations(value) == SEALED_MUTATIONS,
            "expectation authority-pairing receipt drift")
    print("expectation authority pairing: CHECK PASS history=unchanged")


def selftest() -> None:
    value = derive(); validate(value)
    require(len(mutations(value)) == 6, "expectation pairing mutation drift")
    print("expectation authority pairing: SELFTEST PASS mutations=6")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    {"write": write, "check": check, "selftest": selftest}[
        parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"expectation authority pairing: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
