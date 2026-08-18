#!/usr/bin/env python3
"""Loudly rebind the MAP-mask authority across the screen-only byte delta."""

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

import c2_v21_map_mask_fix as FIX  # noqa: E402
import c2_v21_terminal_screen_lease as LEASE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
SOURCE = ROOT / "src/optional/c2_map_cpu_read.s"
HISTORICAL = FIX.RECEIPT
SCREEN = LEASE.RECEIPT
FINAL_RED = ARCH / "c2.3-v2.1-terminal-screen-lease-card-final-red.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-terminal-screen-map-authority-rebind-receipt.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "9180e59a"
SCREEN_COMMIT = "cbcae624"
RECORDED_ON = "2026-08-16"


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def authorization() -> dict[str, Any]:
    value = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode()
    text = " ".join(raw.lower().split())
    for token in ("map mask checker binding the pre-fix source sha",
                  "authority rebinds loudly",
                  "authorized one-byte delta", "no wplto", "no relink"):
        require(token in text, f"MAP-authority rebind token absent: {token}")
    return value


def source_lineage() -> dict[str, Any]:
    before = git_binding(f"{SCREEN_COMMIT}^", SOURCE)
    after = git_binding(SCREEN_COMMIT, SOURCE)
    current = bind(SOURCE)
    require(before["sha256"] == load(HISTORICAL)["authority"]["source"]["sha256"]
            and after["path"] == current["path"]
            and after["bytes"] == current["bytes"]
            and after["sha256"] == current["sha256"],
            "screen source lineage does not join historical/current authority")
    diff = subprocess.run(
        ["git", "diff", f"{SCREEN_COMMIT}^", SCREEN_COMMIT, "--",
         SOURCE.relative_to(ROOT).as_posix()], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout
    require(diff.count("\n-\tlda #0\n") == 1
            and diff.count("\n+\tlda #$29\n") == 1
            and "sbc #0" not in diff and "and #$0f" not in diff,
            "authorized source delta is not the single screen immediate")
    return {"pre_screen": before, "post_screen": after,
            "semantic_instruction_delta_bytes": 1,
            "old_immediate": "0x00", "new_immediate": "0x29",
            "MAP_construction_changed": False}


def derive() -> dict[str, Any]:
    old = load(HISTORICAL)
    rejected = old.pop("mutations_rejected", None)
    FIX.validate(old, verify=False)
    require(isinstance(rejected, list) and len(rejected) == 9,
            "historical MAP-mask mutation authority drift")
    current = FIX.derive()
    comparison = deepcopy(current)
    comparison["authority"]["source"] = old["authority"]["source"]
    require(comparison == old,
            "MAP-mask authority moved beyond the authorized source binding")
    require(
        current["emitted_construction"] == old["emitted_construction"]
        and current["model"] == old["model"]
        and current["placement_price"] == old["placement_price"],
        "screen delta changed MAP construction/model/placement")
    return {
        "format": "lisp65-c2.3-v2.1-terminal-screen-MAP-authority-rebind-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: MAP authority loudly rebound across screen-only byte",
        "authority": {"owner": authorization(),
            "historical_MAP_mask": bind(HISTORICAL),
            "screen_lease": bind(SCREEN), "card_Final_Red": bind(FINAL_RED),
            "driver": bind(DRIVER)},
        "source_lineage": source_lineage(),
        "semantic_equivalence": {
            "emitted_construction": current["emitted_construction"],
            "model": current["model"],
            "placement_price": current["placement_price"],
            "historical_mutations_preserved": rejected},
        "execution_lock": {"WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "claim_limit": (
            "Authority-only successor; the historical receipt is immutable."),
    }


def validate(value: dict[str, Any], expected: dict[str, Any]) -> None:
    require(value == expected, "terminal-screen MAP authority rebind drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "widen-source-delta": lambda x: x["source_lineage"].update(
            semantic_instruction_delta_bytes=2),
        "claim-map-change": lambda x: x["source_lineage"].update(
            MAP_construction_changed=True),
        "alter-mask-model": lambda x: x["semantic_equivalence"]["model"]
            ["positive"].update(MAPL="0xffc0"),
        "drop-historical-lineage": lambda x: x["authority"].pop(
            "historical_MAP_mask"),
        "authorize-wplto": lambda x: x["execution_lock"].update(WPLTO_runs=1),
        "authorize-link": lambda x: x["execution_lock"].update(product_links=1),
        "consume-card": lambda x: x["execution_lock"].update(cards_consumed=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial, value)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "MAP-authority rebind mutation survived")
    return rejected


def placement_contract() -> dict[str, Any]:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    expected = derive()
    validate(value, expected)
    require(rejected == mutations(expected), "MAP rebind mutation receipt drift")
    price = value["semantic_equivalence"]["placement_price"]
    return {"authority": RECEIPT.relative_to(ROOT).as_posix(),
        "reader_address": 0x2277,
        "reader_bytes": price["expected_linked_bytes"],
        "ordinary_reserve_bytes": price["expected_reserve_bytes"],
        "text_end_exclusive": 0xB3B0 - price["expected_reserve_bytes"],
        "facade_address": 0xB3B0, "delta_bytes": 1}


def record() -> None:
    require(not RECEIPT.exists(), "MAP-authority rebind receipt exists")
    value = derive(); value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 MAP authority rebind: PASS screen-byte=1 MAP-change=0")


def check() -> None:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    expected = derive(); validate(value, expected)
    require(rejected == mutations(expected), "MAP rebind mutation receipt drift")
    print("2.1 MAP authority rebind: CHECK PASS WPLTO=0 link=0 card=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check"))
    {"record": record, "check": check}[parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"2.1 MAP authority rebind: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
