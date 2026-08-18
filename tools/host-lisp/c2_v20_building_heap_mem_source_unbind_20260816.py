#!/usr/bin/env python3
"""Loudly detach the historical BUILDING-HEAP row from living mem.c."""

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

import c2_v20_building_heap_attribution as OLD  # noqa: E402
import c2_v21_probe_oracle_root_fix as ROOT_FIX  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
MEM = ROOT / "src/mem.c"
RECEIPT = ARCH / (
    "c2.3-v2.0-building-heap-mem-source-unbind-20260816-receipt.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "7e4a1f86"
FORMAT = "lisp65-c2.3-v20-building-heap-mem-source-unbind-v1"
STATUS = "PASS: HISTORICAL-BUILDING-HEAP-MEM-DETACHED-FROM-LIVE-SOURCE"


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


def authorization() -> dict[str, Any]:
    value = git_bind(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode().lower()
    text = " ".join(raw.replace("`", "").split())
    require("historical building-heap receipt" in text
            and "mem.c as a living source" in text
            and "authorized loud, dated unbind" in text,
            "BUILDING-HEAP mem-source unbind authorization absent")
    return value


def historical_audit(value: dict[str, Any]) -> None:
    rejected = value.pop("mutations_rejected", None)
    OLD.validate(value, verify=False)
    require(rejected == OLD.mutations(value),
            "historical BUILDING-HEAP mutation set drift")


def derive() -> dict[str, Any]:
    old = load(OLD.RECEIPT)
    historical_audit(deepcopy(old))
    historical_mem = old["phase_binding"]["source_bindings"]["mem"]
    current_mem = bind(MEM)
    root = load(ROOT_FIX.RECEIPT)
    require(historical_mem["path"] == current_mem["path"]
            and historical_mem["sha256"] != current_mem["sha256"]
            and root.get("status") == ROOT_FIX.STATUS
            and root["authority"]["mem"] == current_mem
            and ROOT_FIX.source_contract()["reader_count"] == 9,
            "historical/live mem boundary or root semantics drift")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-16", "status": STATUS,
        "authority": {"owner": authorization(),
            "historical_receipt": bind(OLD.RECEIPT),
            "prior_loud_rebind": bind(OLD.LATEST_REBIND),
            "living_root_fix": bind(ROOT_FIX.RECEIPT),
            "driver": bind(DRIVER)},
        "historical_observation": {
            "status": old["status"], "recorded_on": old["recorded_on"],
            "mem_source": historical_mem, "receipt_rewritten": False,
            "claim_changed": False},
        "living_successor": {"mem_source": current_mem,
            "acceptance_authority": "nine-reader MAP-CPU root gate",
            "historical_mem_is_live_predicate": False,
            "root_reader_count": 9, "DMA_probe_jobs": 0,
            "completion_signal_trusted": False},
        "execution_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": (
            "Authority-only source unbind. Historical evidence and claims "
            "are unchanged; current mem semantics remain gated by the root fix."),
    }
    value["mutations_rejected"] = mutations(value)
    validate(value)
    return value


def validate(value: dict[str, Any]) -> None:
    history = value["historical_observation"]
    live = value["living_successor"]
    require(value.get("format") == FORMAT and value.get("status") == STATUS
            and history["receipt_rewritten"] is False
            and history["claim_changed"] is False
            and history["mem_source"]["path"] == live["mem_source"]["path"]
            and history["mem_source"]["sha256"] != live["mem_source"]["sha256"]
            and live["historical_mem_is_live_predicate"] is False
            and live["root_reader_count"] == 9
            and live["DMA_probe_jobs"] == 0
            and live["completion_signal_trusted"] is False
            and value["execution_accounting"] == {"WPLTO_runs": 0,
                "product_links": 0, "media_builds": 0, "device_contacts": 0},
            "BUILDING-HEAP mem-source unbind drift")


def mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-history": lambda x: x["historical_observation"].update(
            receipt_rewritten=True),
        "change-claim": lambda x: x["historical_observation"].update(
            claim_changed=True),
        "revive-live-predicate": lambda x: x["living_successor"].update(
            historical_mem_is_live_predicate=True),
        "lose-reader": lambda x: x["living_successor"].update(
            root_reader_count=8),
        "restore-probe": lambda x: x["living_successor"].update(
            DMA_probe_jobs=1),
        "trust-completion": lambda x: x["living_successor"].update(
            completion_signal_trusted=True),
        "invent-link": lambda x: x["execution_accounting"].update(
            product_links=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(base); trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate(trial)
        except UnbindError:
            rejected.append(name)
    require(rejected == list(cases), "BUILDING-HEAP unbind mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    value = derive()
    if action == "record":
        require(not RECEIPT.exists(), "BUILDING-HEAP unbind receipt exists")
        RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        require(load(RECEIPT) == value, "BUILDING-HEAP unbind receipt stale")
    else:
        require(len(value["mutations_rejected"]) == 7,
                "BUILDING-HEAP unbind mutation count drift")
    print(f"BUILDING-HEAP mem-source unbind: PASS action={action} mutations=7")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (UnbindError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"BUILDING-HEAP mem-source unbind: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
