#!/usr/bin/env python3
"""Attribute the terminal bounded-continuation pre-link Red."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v2.1-probe-oracle-root-padding-replacement-card"
WPLTO = BUILD / "wplto"
STATE = BUILD / "bounded-producer-continuation"
RED = ARCH / (
    "c2.3-v2.1-root-padding-bounded-producer-continuation-final-red.json")
RECEIPT = ARCH / (
    "c2.3-v2.1-root-padding-bounded-continuation-red-attribution.json")
FIRST = STATE / "materialization-probe/resident-island-a.h"
SECOND = STATE / "materialization-probe/resident-island-b.h"
ACTUAL = WPLTO / "resident-island.h"
FINAL = WPLTO / "lisp65-c2-substitution-linked.prg"
STATUS = "ATTRIBUTED FINAL RED: FROZEN-SEED-DIRECTORY-LEASE-CONFLICT"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def final_family_present() -> list[str]:
    paths = [FINAL, Path(str(FINAL) + ".elf"), Path(str(FINAL) + ".map"),
             Path(str(FINAL) + ".lto.o")]
    return [path.relative_to(ROOT).as_posix() for path in paths if path.exists()]


def validate(value: dict[str, Any]) -> None:
    mechanism = value["mechanism"]
    require(
        value.get("status") == STATUS
        and mechanism["WPLTO_directory_mode"] == "0555"
        and mechanism["probe_directory_mode"] == "0755"
        and mechanism["deterministic_materializations"] == 2
        and mechanism["materialization_outputs_byteidentical"] is True
        and mechanism["installed_header_present"] is False
        and mechanism["final_product_artifacts_present"] == []
        and value["classification"]["product_red"] is False
        and value["classification"]["seed_red"] is False
        and value["classification"]["final_link_started"] is False
        and value["disposition"]["retry_authorized"] is False
        and value["disposition"]["owner_required"] is True,
        "bounded-continuation Red attribution drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-link-started": lambda x: x["classification"].update(
            final_link_started=True),
        "blame-product": lambda x: x["classification"].update(product_red=True),
        "blame-seed": lambda x: x["classification"].update(seed_red=True),
        "hide-determinism": lambda x: x["mechanism"].update(
            materialization_outputs_byteidentical=False),
        "invent-header": lambda x: x["mechanism"].update(
            installed_header_present=True),
        "authorize-retry": lambda x: x["disposition"].update(
            retry_authorized=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate(trial)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "bounded Red attribution mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    red = load(RED)
    wplto_mode = stat.S_IMODE(os.stat(WPLTO).st_mode)
    probe_mode = stat.S_IMODE(os.stat(FIRST.parent).st_mode)
    first = bind(FIRST)
    second = bind(SECOND)
    require(
        red.get("status") ==
            "FINAL RED: BOUNDED PRODUCER CONTINUATION RETURNS TO OWNER"
        and red.get("failed_action") == "link"
        and red.get("retry_authorized") is False
        and red.get("owner_disposition_required") is True
        and "resident_island.py" in red["error"]["message"]
        and str(ACTUAL) in red["error"]["message"]
        and wplto_mode == 0o555 and probe_mode == 0o755
        and first["sha256"] == second["sha256"]
        and not ACTUAL.exists() and not final_family_present(),
        "bounded continuation failure signature drift")
    value = {
        "format": "lisp65-c2.3-v2.1-bounded-continuation-red-attribution-v1",
        "recorded_on": "2026-08-16", "status": STATUS,
        "authority": {"Final_Red": bind(RED), "driver": bind(Path(__file__))},
        "mechanism": {
            "class": "FROZEN-SEED-DIRECTORY-LEASE-CONFLICT",
            "WPLTO_directory_mode": f"{wplto_mode:04o}",
            "probe_directory_mode": f"{probe_mode:04o}",
            "deterministic_materializations": 2,
            "materialization_outputs": [first, second],
            "materialization_outputs_byteidentical": True,
            "installed_header_present": False,
            "final_product_artifacts_present": [],
            "failing_operation": (
                "atomic temporary-file creation for resident-island.h in the "
                "read-only frozen WPLTO directory"),
        },
        "classification": {"product_red": False, "seed_red": False,
            "materializer_semantics_red": False, "final_link_started": False,
            "pre_link_continuation_harness_red": True},
        "execution_accounting": red["execution_accounting"],
        "disposition": {"retry_authorized": False, "owner_required": True,
            "narrow_question": (
                "Grant a scoped write lease on the frozen WPLTO directory, "
                "or direct materialization/final-link outputs to a separately "
                "owned writable continuation directory while keeping the seed read-only.")},
        "claim_limit": (
            "Read-only attribution. It authorizes no chmod, path change, retry, "
            "final link, Completion, media or device action."),
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
        require(not RECEIPT.exists(), "bounded Red attribution receipt exists")
        RECEIPT.write_bytes(canonical(value))
    else:
        require(load(RECEIPT) == value, "bounded Red attribution receipt stale")
    print("bounded continuation Red attribution: PASS class=directory-lease "
          "materialize=2 link=0 mutations=6")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"bounded continuation Red attribution: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
