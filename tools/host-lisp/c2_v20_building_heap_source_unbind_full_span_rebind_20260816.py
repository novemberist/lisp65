#!/usr/bin/env python3
"""Loudly rebind the living ABI-gate authority after afe63882.

The immutable BUILDING-HEAP observation and its first source-unbind receipt
remain historical.  This successor only advances the living acceptance-gate
identity to the authorized current source.
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

import evidence_era as ERA  # noqa: E402

ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
PREDECESSOR = ARCH / (
    "c2.3-v2.0-building-heap-device-source-unbind-phase9-"
    "20260815-receipt.json")
ABI_GATE = ROOT / "tools/host-lisp/c2_asm_leaf_abi_gate.py"
RECEIPT = ARCH / (
    "c2.3-v2.0-building-heap-source-unbind-full-span-rebind-"
    "20260816-receipt.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "afe63882"
FORMAT = "lisp65-c2.3-v20-building-heap-source-unbind-rebind-v2"
SEAL_ERA_COMMIT = "2cc1da14334686c0f860f9f291e5da1ebb81ed65"
SEALED_MUTATIONS = [
    "rewrite-predecessor", "change-observation", "revive-source-predicate",
    "inherit-old-gate", "rename-gate-path", "silent-rebind",
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
    value = git_bind(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode().lower()
    require("unrelated v2.0 source-unbind authority drift" in raw
            and "authorized loud, dated rebind" in raw,
            "v2.0 full-span rebind authority absent")
    return value


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR)
    require(
        value.get("format")
            == "lisp65-c2.3-v20-building-heap-source-unbind-v1"
        and value.get("status")
            == "PASS: historical v2.0 row detached from living source"
        and value["historical_observation"]["receipt_rewritten"] is False
        and value["historical_observation"]["claim_changed"] is False
        and value["living_successor"]
            ["historical_source_is_live_predicate"] is False
        and value.get("mutations_rejected") == [
            "rewrite-history", "change-historical-claim",
            "rebind-history-to-live-source", "make-old-source-live-predicate"],
        "predecessor source-unbind receipt drift")
    return value


def derive() -> dict[str, Any]:
    old = predecessor()
    prior_gate = old["authority"]["living_ABI_gate"]
    current_gate = ERA.era_bind(SEAL_ERA_COMMIT, ABI_GATE)
    require(prior_gate["path"] == current_gate["path"]
            and prior_gate["sha256"] != current_gate["sha256"],
            "authorized ABI-gate drift absent or changed domain")
    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-16",
        "status": "PASS: v2.0 source-unbind living authority loudly rebound",
        "authority": {"owner": authorization(),
                      "predecessor": bind(PREDECESSOR),
                      "driver": ERA.era_bind(SEAL_ERA_COMMIT, DRIVER)},
        "historical_contract": {
            "predecessor_rewritten": False,
            "historical_observation_changed": False,
            "historical_source_is_live_predicate": False},
        "living_acceptance_gate": {
            "prior": prior_gate,
            "current": current_gate,
            "same_path": True,
            "binding_kind": "loud-dated-successor"},
        "claim_limit": (
            "Authority-only rebind: no historical receipt, observation, "
            "product byte, WPLTO, link, medium or device state changed."),
    }
    value["mutations_rejected"] = mutations(value)
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    history = value["historical_contract"]
    gates = value["living_acceptance_gate"]
    require(
        value.get("format") == FORMAT
        and value.get("status")
            == "PASS: v2.0 source-unbind living authority loudly rebound"
        and history == {"predecessor_rewritten": False,
                        "historical_observation_changed": False,
                        "historical_source_is_live_predicate": False}
        and gates["same_path"] is True
        and gates["binding_kind"] == "loud-dated-successor"
        and gates["prior"]["path"] == gates["current"]["path"]
        and gates["prior"]["sha256"] != gates["current"]["sha256"],
        "v2.0 source-unbind rebind drift")
    require(
        gates["current"] == ERA.era_bind(SEAL_ERA_COMMIT, ABI_GATE)
        and value.get("authority", {}).get("driver") ==
            ERA.era_bind(SEAL_ERA_COMMIT, DRIVER),
        "v2.0 source-unbind provenance escaped its sealing era")


def mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-predecessor": lambda x: x["historical_contract"].update(
            predecessor_rewritten=True),
        "change-observation": lambda x: x["historical_contract"].update(
            historical_observation_changed=True),
        "revive-source-predicate": lambda x: x["historical_contract"].update(
            historical_source_is_live_predicate=True),
        "inherit-old-gate": lambda x: x["living_acceptance_gate"].update(
            current=deepcopy(x["living_acceptance_gate"]["prior"])),
        "rename-gate-path": lambda x: x["living_acceptance_gate"]
            ["current"].update(path="historical/other-gate.py"),
        "silent-rebind": lambda x: x["living_acceptance_gate"].update(
            binding_kind="silent"),
        "collapse-era-to-live": lambda x: x["living_acceptance_gate"].update(
            current=ERA.era_bind("HEAD", ABI_GATE)),
        "restore-working-tree-binding": lambda x: x["authority"].update(
            driver=bind(DRIVER)),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(base); trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate(trial)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "v2.0 rebind mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "v2.0 rebind receipt already exists")
    value = derive(); RECEIPT.write_bytes(canonical(value))
    print("v2.0 source-unbind full-span rebind: PASS mutations=6")


def check() -> None:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    expected = derive(); expected.pop("mutations_rejected", None)
    require(value == expected and rejected == SEALED_MUTATIONS
            and len(mutations(value)) == 8,
            "v2.0 source-unbind rebind receipt drift")
    print("v2.0 source-unbind full-span rebind: CHECK PASS "
          "sealed=6 live-era=8")


def selftest() -> None:
    value = derive()
    require(len(value["mutations_rejected"]) == 8,
            "v2.0 rebind mutation count drift")
    print("v2.0 source-unbind full-span rebind: SELFTEST PASS mutations=8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    {"record": record, "check": check, "selftest": selftest}[
        parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RebindError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"v2.0 source-unbind full-span rebind: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
