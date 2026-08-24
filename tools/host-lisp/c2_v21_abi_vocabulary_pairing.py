#!/usr/bin/env python3
"""Bind the ABI producer and canonical consumer to one status vocabulary."""

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

import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_lite_canonical_product as CONSUMER  # noqa: E402
import evidence_era as ERA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
ELF = ROOT / ("build/c2.3/v2.1-terminal-screen-lease-card/wplto/"
              "lisp65-c2-substitution-linked.prg.elf")
REPORT = ROOT / ("build/c2.3/v2.1-terminal-screen-lease-card/"
                 "abi-vocabulary-pairing-report.json")
RECEIPT = ARCH / "c2.3-v2.1-abi-vocabulary-pairing-receipt.json"
DRIVER = Path(__file__).resolve()
PRODUCER = ROOT / "tools/host-lisp/c2_asm_leaf_abi_gate.py"
CONSUMER_SOURCE = ROOT / "tools/host-lisp/c2_lite_canonical_product.py"
AUTHORIZATION = "9180e59a"
SEAL_ERA_COMMIT = "2a292fc3d9964198df039f60cd21d35cac410543"
SEALED_MUTATIONS = [
    "restore-historical-pin", "rename-consumer-only", "hide-unclassified",
    "authorize-wplto", "source-restore-historical-pin",
]


class PairingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PairingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().split())
    require("producer/consumer pairing clause" in text
            and "current vocabulary" in text,
            "ABI vocabulary-pairing authorization absent")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def source_gate(producer: str | None = None,
                consumer: str | None = None) -> dict[str, Any]:
    producer = PRODUCER.read_text(encoding="utf-8") if producer is None else producer
    consumer = (CONSUMER_SOURCE.read_text(encoding="utf-8")
                if consumer is None else consumer)
    symbol = "ELF_DERIVED_C_CALLED_STATUS"
    value = ABI.ELF_DERIVED_C_CALLED_STATUS
    require(
        f'"status": {symbol}' in producer
        and f'derived["status"] == ABI.{symbol}' in consumer
        and "passed-ELF-derived-C-called-assembler-universe" not in consumer,
        "ABI producer/consumer vocabulary is not symbol-paired")
    return {"status": "PASS: consumer follows producer vocabulary symbol",
            "symbol": symbol, "value": value, "historical_pin_present": False}


def derive() -> dict[str, Any]:
    report = ABI.audit_elf(ELF, out=REPORT, require_bank3_chain=True)
    consumer = CONSUMER.fresh_real_abi_gate(ELF, report_path=REPORT)
    inventory = report["ELF_derived_C_called_inventory"]
    require(inventory["status"] == ABI.ELF_DERIVED_C_CALLED_STATUS
            and inventory["unclassified_C_called_functions"] == []
            and consumer["all_callers_classified"] is True,
            "current linked ABI producer/consumer pair is red")
    return {"format": "lisp65-c2.3-v2.1-ABI-vocabulary-pairing-v1",
        "recorded_on": "2026-08-16",
        "status": "PASS: ABI vocabulary producer/consumer paired",
        "authority": {"owner": authorization(), "producer": bind(PRODUCER),
            "consumer": bind(CONSUMER_SOURCE), "frozen_ELF": bind(ELF),
            "driver": bind(DRIVER)},
        "pairing": source_gate(),
        "linked_witness": {"producer_status": inventory["status"],
            "transitive_functions": inventory["transitive_function_count"],
            "unclassified": inventory["unclassified_C_called_functions"],
            "CRC_callsites": consumer["callsite_count"]},
        "execution_lock": {"WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0}}


def validate(value: dict[str, Any], expected: dict[str, Any]) -> None:
    require(value == expected, "ABI vocabulary pairing drift")


def validate_sealed(value: dict[str, Any], current: dict[str, Any]) -> None:
    """Keep the receipt in its era while proving the live producer/consumer pair."""
    require(
        value.get("format") == current.get("format")
        and value.get("status") == current.get("status")
        and value.get("pairing") == current.get("pairing")
        and value.get("linked_witness") == current.get("linked_witness")
        and value.get("execution_lock") == current.get("execution_lock")
        and value.get("authority", {}).get("owner") ==
            current.get("authority", {}).get("owner")
        and value.get("authority", {}).get("frozen_ELF") ==
            current.get("authority", {}).get("frozen_ELF")
        and value.get("authority", {}).get("producer") ==
            ERA.era_bind(SEAL_ERA_COMMIT, PRODUCER)
        and value.get("authority", {}).get("consumer") ==
            ERA.era_bind(SEAL_ERA_COMMIT, CONSUMER_SOURCE)
        and value.get("authority", {}).get("driver") ==
            ERA.era_bind(SEAL_ERA_COMMIT, DRIVER),
        "sealed ABI producer/consumer pairing drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-historical-pin": lambda x: x["pairing"].update(
            historical_pin_present=True),
        "rename-consumer-only": lambda x: x["pairing"].update(value="other"),
        "hide-unclassified": lambda x: x["linked_witness"].update(
            unclassified=["hidden"]),
        "authorize-wplto": lambda x: x["execution_lock"].update(WPLTO_runs=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial, value)
        except PairingError:
            rejected.append(name)
    producer = PRODUCER.read_text(encoding="utf-8")
    consumer = CONSUMER_SOURCE.read_text(encoding="utf-8")
    old = consumer.replace(
        "derived[\"status\"] == ABI.ELF_DERIVED_C_CALLED_STATUS",
        "derived[\"status\"] == \"passed-ELF-derived-C-called-assembler-universe\"",
        1)
    try:
        source_gate(producer, old)
    except PairingError:
        rejected.append("source-restore-historical-pin")
    require(rejected == list(cases) + ["source-restore-historical-pin"],
            "ABI vocabulary mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "ABI vocabulary pairing receipt exists")
    value = derive(); value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 ABI vocabulary: PASS paired=transitive CRC=10")


def check() -> None:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    current = derive(); validate_sealed(value, current)
    require(rejected == SEALED_MUTATIONS
            and mutations(current) == SEALED_MUTATIONS,
            "ABI pairing mutation receipt drift")
    print("2.1 ABI vocabulary: CHECK PASS sealed-era live-pair=producer+consumer")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check"))
    {"record": record, "check": check}[parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"2.1 ABI vocabulary: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
