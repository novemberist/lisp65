#!/usr/bin/env python3
"""Keep the v1.12 ownership closure in the source world it witnessed."""

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
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
DRIVER = ROOT / "tools/host-lisp/c2_v112_ownership_opt_in_closure.py"
CONTRACT = ROOT / "config/c2-v112-ownership-opt-in-closure.json"
HISTORICAL = ARCH / "c2.3-v1.12-ownership-opt-in-closure-receipt.json"
RECEIPT = ARCH / "c2.3-v1.12-ownership-opt-in-historical-unbind-20260817.json"
AUTHORIZATION = "bdc22229"
HISTORICAL_COMMIT = "99095e04"
FORMAT = "lisp65-c2-v112-ownership-opt-in-historical-unbind-v1"
STATUS = "PASS: v1.12 ownership closure witnesses only its historical world"


class UnbindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise UnbindError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_blob(commit: str, path: Path) -> tuple[bytes, dict[str, Any]]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return raw, {"authority": "git-blob", "commit": full, "path": name,
                 "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    raw, value = git_blob(AUTHORIZATION, PLAN)
    text = " ".join(raw.decode().lower().replace("*", "").split())
    for token in ("separate continuation target authorized",
                  "historical v1.12 ownership-opt-in gate straggler",
                  "authorized loud, dated unbind"):
        require(token in text, f"v1.12 unbind authority absent: {token}")
    return value


def historical_world() -> dict[str, Any]:
    receipt_raw, receipt = git_blob(HISTORICAL_COMMIT, HISTORICAL)
    driver_raw, driver = git_blob(HISTORICAL_COMMIT, DRIVER)
    contract_raw, contract = git_blob(HISTORICAL_COMMIT, CONTRACT)
    value = json.loads(receipt_raw)
    require(
        HISTORICAL.read_bytes() == receipt_raw
        and value.get("status") ==
            "passed-complete-opt-in-and-canonical-seed-closure"
        and value.get("recorded_on") == "2026-08-07"
        and value["authorities"]["closure_gate"]["sha256"] ==
            hashlib.sha256(driver_raw).hexdigest()
        and value["contract"]["sha256"] == hashlib.sha256(contract_raw).hexdigest()
        and value["inventory"]["mutations_rejected"] == 62
        and value["canonical_seed_link"]["seed_links"] == 1
        and value["canonical_seed_link"]["product_links"] == 0
        and value["product_completed"] is False,
        "historical v1.12 closure identity drift")
    return {
        "commit": receipt["commit"],
        "receipt": receipt,
        "closure_driver": driver,
        "contract": contract,
        "living_receipt_byteidentical": True,
        "living_source_is_acceptance_predicate": False,
        "historical_receipt_rewritten": False,
    }


def validate(value: dict[str, Any]) -> None:
    world = value["historical_world"]
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value["rule"] ==
            "Historical receipts witness their own world; they never gate the living one."
        and world["living_receipt_byteidentical"] is True
        and world["living_source_is_acceptance_predicate"] is False
        and world["historical_receipt_rewritten"] is False,
        "v1.12 ownership historical-unbind receipt drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "gate-living-source": lambda x: x["historical_world"].update(
            living_source_is_acceptance_predicate=True),
        "rewrite-history": lambda x: x["historical_world"].update(
            historical_receipt_rewritten=True),
        "lose-byte-identity": lambda x: x["historical_world"].update(
            living_receipt_byteidentical=False),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate(trial)
        except UnbindError:
            rejected.append(name)
    require(rejected == list(cases), "v1.12 historical-unbind mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-17",
        "status": STATUS,
        "rule":
            "Historical receipts witness their own world; they never gate the living one.",
        "authority": {"owner": authorization(), "driver": bind(Path(__file__))},
        "historical_world": historical_world(),
        "claim_limit": (
            "Class-A authority unbind only. Historical evidence remains byte-identical; "
            "no product, link, Completion, media or device action."),
    }
    validate(value)
    value["mutations_rejected"] = mutations(value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check"))
    action = parser.parse_args().action
    value = derive()
    if action == "record":
        require(not RECEIPT.exists(), "v1.12 historical-unbind receipt exists")
        RECEIPT.write_bytes(canonical(value))
    else:
        require(RECEIPT.read_bytes() == canonical(value),
                "v1.12 historical-unbind receipt stale")
    print("v1.12 ownership historical unbind: PASS world=99095e04 mutations=3")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (UnbindError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"v1.12 ownership historical unbind: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
