#!/usr/bin/env python3
"""Loudly detach the immutable v2.0 device row from living far-service source.

The stopped-state observation remains historical evidence.  Its source hashes
describe the world that produced it; they are not a live-source acceptance
predicate after the authorized phase-9 ABI successor changed that source.
"""

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

import c2_v20_building_heap_device_result as OLD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
HISTORICAL = OLD.RECEIPT
LIVE_SOURCE = ROOT / "src/c2_mapped_far_convergence.s"
ABI_CONTRACT = ROOT / "config/c2-mapped-far-abi-preservation-contract-v2.json"
ABI_GATE = ROOT / "tools/host-lisp/c2_asm_leaf_abi_gate.py"
RECEIPT = ARCH / (
    "c2.3-v2.0-building-heap-device-source-unbind-phase9-"
    "20260815-receipt.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "7fa52735"


class UnbindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise UnbindError(message)


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


def historical_audit(value: dict[str, Any]) -> None:
    rejected = value.pop("mutations_rejected", None)
    OLD.validate(value, verify=False)
    require(rejected == OLD.mutations(value),
            "historical BUILDING-HEAP mutation receipt drift")
    source = value["authorities"]["mapped_far_body_source"]
    require(source["sha256"] != bind(LIVE_SOURCE)["sha256"],
            "historical and living mapped-far sources no longer differ")


def derive() -> dict[str, Any]:
    old = load(HISTORICAL)
    historical_audit(deepcopy(old))
    authority = git_bind(AUTHORIZATION, PLAN)
    text = subprocess.run(
        ["git", "show", f"{authority['commit']}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode().lower()
    require("historical v2.0 receipt unbinds" in text
            and "one replacement card" in text,
            "phase-9 source-unbind authority absent")
    value = {
        "format": "lisp65-c2.3-v20-building-heap-source-unbind-v1",
        "recorded_on": "2026-08-15",
        "status": "PASS: historical v2.0 row detached from living source",
        "authority": {
            "owner": authority,
            "historical_device_receipt": bind(HISTORICAL),
            "living_ABI_contract": bind(ABI_CONTRACT),
            "living_ABI_gate": bind(ABI_GATE),
            "driver": bind(DRIVER),
        },
        "historical_observation": {
            "status": old["status"],
            "recorded_on": old["recorded_on"],
            "mapped_far_body_source": old["authorities"]
                ["mapped_far_body_source"],
            "receipt_rewritten": False,
            "claim_changed": False,
        },
        "living_successor": {
            "mapped_far_body_source": bind(LIVE_SOURCE),
            "acceptance_authority": "phase-9 linked ABI successor gates",
            "historical_source_is_live_predicate": False,
        },
        "claim_limit": (
            "Source-closure successor only; no historical bytes or claims "
            "changed and no WPLTO, link, media or device contact occurred."),
    }
    value["mutations_rejected"] = mutations(value)
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    require(
        value.get("status")
            == "PASS: historical v2.0 row detached from living source"
        and value["historical_observation"]["receipt_rewritten"] is False
        and value["historical_observation"]["claim_changed"] is False
        and value["living_successor"]
            ["historical_source_is_live_predicate"] is False
        and value["historical_observation"]["mapped_far_body_source"]
            ["sha256"]
            != value["living_successor"]["mapped_far_body_source"]["sha256"],
        "historical v2.0 source-unbind drift")


def mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-history": lambda x: x["historical_observation"].update(
            receipt_rewritten=True),
        "change-historical-claim": lambda x: x["historical_observation"].update(
            claim_changed=True),
        "rebind-history-to-live-source": lambda x: x["historical_observation"].update(
            mapped_far_body_source=x["living_successor"]["mapped_far_body_source"]),
        "make-old-source-live-predicate": lambda x: x["living_successor"].update(
            historical_source_is_live_predicate=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(base)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate(trial)
        except UnbindError:
            rejected.append(name)
    require(rejected == list(cases), "source-unbind mutation survived")
    return rejected


def build() -> None:
    require(not RECEIPT.exists(), "source-unbind receipt already exists")
    RECEIPT.write_bytes(canonical(derive()))
    print("v2.0 BUILDING-HEAP source unbind: PASS historical!=living")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value)
    require(rejected == mutations(value), "source-unbind mutation drift")
    require(value == {k: v for k, v in derive().items()
                      if k != "mutations_rejected"},
            "source-unbind authority drift")
    print("v2.0 BUILDING-HEAP source unbind check: PASS")


def selftest() -> None:
    value = derive()
    require(len(value["mutations_rejected"]) == 4,
            "source-unbind mutation count drift")
    print("v2.0 BUILDING-HEAP source unbind selftest: PASS mutations=4")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check", "selftest"))
    {"build": build, "check": check, "selftest": selftest}[
        parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (UnbindError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"v2.0 BUILDING-HEAP source unbind: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
