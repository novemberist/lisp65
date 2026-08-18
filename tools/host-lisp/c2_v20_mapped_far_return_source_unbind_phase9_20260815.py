#!/usr/bin/env python3
"""Keep the mapped-far return row historical after the phase-9 source split."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v20_mapped_far_return_attribution as OLD  # noqa: E402
import c2_v20_building_heap_device_source_unbind_phase9_20260815 as UNBIND  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = ARCH / (
    "c2.3-v2.0-mapped-far-return-source-unbind-phase9-"
    "20260815-receipt.json")
DRIVER = Path(__file__).resolve()


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


def validate(value: dict[str, Any]) -> None:
    require(value.get("status")
            == "PASS: mapped-far return row remains historical"
            and value["result"] == {
                "historical_receipt_changed": False,
                "historical_claim_changed": False,
                "living_source_is_historical_predicate": False,
                "product_work": 0,
            }
            and value["historical"]["far_body_source"]["sha256"]
                != value["living"]["far_body_source"]["sha256"],
            "mapped-far return source-unbind drift")


def mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-history": lambda x: x["result"].update(
            historical_receipt_changed=True),
        "change-claim": lambda x: x["result"].update(
            historical_claim_changed=True),
        "restore-live-predicate": lambda x: x["result"].update(
            living_source_is_historical_predicate=True),
        "run-product": lambda x: x["result"].update(product_work=1),
        "replace-source": lambda x: x["historical"].update(
            far_body_source=x["living"]["far_body_source"]),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(base); trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate(trial)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "mapped-far source-unbind mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    old = load(OLD.RECEIPT)
    rejected = old.pop("mutations_rejected", None)
    OLD.validate(old)
    require(rejected == OLD.mutations(old),
            "historical mapped-far return mutations drift")
    unbind = load(UNBIND.RECEIPT)
    unbind_rejected = unbind.pop("mutations_rejected", None)
    UNBIND.validate(unbind)
    require(unbind_rejected == UNBIND.mutations(unbind),
            "phase-9 source-unbind authority drift")
    value = {
        "format": "lisp65-c2.3-v20-mapped-far-return-source-unbind-v1",
        "recorded_on": "2026-08-15",
        "status": "PASS: mapped-far return row remains historical",
        "authority": {"historical_receipt": bind(OLD.RECEIPT),
                      "source_unbind": bind(UNBIND.RECEIPT),
                      "driver": bind(DRIVER)},
        "historical": {"status": old["status"],
            "far_body_source": old["authorities"]["far_body_source"]},
        "living": {"far_body_source": bind(OLD.BODY)},
        "result": {"historical_receipt_changed": False,
            "historical_claim_changed": False,
            "living_source_is_historical_predicate": False,
            "product_work": 0},
        "claim_limit": "Historical closure only; no product or device claim.",
    }
    validate(value); value["mutations_rejected"] = mutations(value)
    return value


def build() -> None:
    require(not RECEIPT.exists(), "mapped-far source-unbind receipt exists")
    RECEIPT.write_bytes(canonical(derive()))
    print("v2.0 mapped-far return source unbind: PASS")


def check() -> None:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value)
    expected = derive(); expected.pop("mutations_rejected", None)
    require(value == expected and rejected == mutations(value),
            "mapped-far return source-unbind authority drift")
    print("v2.0 mapped-far return source unbind check: PASS")


def selftest() -> None:
    value = derive()
    require(len(value["mutations_rejected"]) == 5, "mutation count drift")
    print("v2.0 mapped-far return source unbind selftest: PASS mutations=5")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check", "selftest"))
    {"build": build, "check": check, "selftest": selftest}[
        parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v2.0 mapped-far return source unbind: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
