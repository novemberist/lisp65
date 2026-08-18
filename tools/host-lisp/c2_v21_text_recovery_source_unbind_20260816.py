#!/usr/bin/env python3
"""Loudly unbind historical text-recovery evidence from living source."""

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
PRODUCT = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
FIRST_DRIVER = ROOT / "tools/host-lisp/c2_v21_text_recovery_card_red_attribution.py"
SECOND_DRIVER = ROOT / (
    "tools/host-lisp/c2_v21_text_recovery_replacement_red_attribution.py")
FIRST = ARCH / "c2.3-v2.1-text-recovery-card-red-attribution-receipt.json"
SECOND = ARCH / (
    "c2.3-v2.1-text-recovery-replacement-card-red-attribution-receipt.json")
RECEIPT = ARCH / "c2.3-v2.1-text-recovery-source-unbind-20260816.json"
AUTHORIZATION = "1910fd0a"
HISTORICAL_COMMIT = "681e56e0"
FORMAT = "lisp65-c2.3-v2.1-text-recovery-source-unbind-v1"
STATUS = "PASS: historical text-recovery receipts witness only their own world"


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
        check=True, text=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.lower().replace("*", "").split())
    for token in ("bounded producer continuation",
                  "historical text-recovery receipt",
                  "authorized loud, dated unbind"):
        require(token in text, f"text-recovery unbind authority absent: {token}")
    return value


def source_gate(source_overrides: dict[Path, str] | None = None) -> dict[str, Any]:
    overrides = {} if source_overrides is None else source_overrides
    first = overrides.get(FIRST_DRIVER, FIRST_DRIVER.read_text(encoding="utf-8"))
    second = overrides.get(
        SECOND_DRIVER, SECOND_DRIVER.read_text(encoding="utf-8"))
    require(
        "product_source = historical_text(HISTORICAL_CARD_COMMIT, PRODUCT)"
            in first
        and "historical_bind(\n                          HISTORICAL_CARD_COMMIT, PRODUCT)"
            in first
        and "historical_bind(\n                HISTORICAL_CARD_COMMIT, PRODUCT_DRIVER)"
            in second,
        "historical text-recovery checker still consumes living product source")
    historical = git_bind(HISTORICAL_COMMIT, PRODUCT)
    live = bind(PRODUCT)
    require(historical["sha256"] != live["sha256"],
            "unbind witness needs a real historical/live source divergence")
    return {
        "status": STATUS,
        "historical_product_source": historical,
        "living_product_source": live,
        "source_identity_equal": False,
        "historical_receipts_rewritten": False,
        "living_source_is_acceptance_predicate": False,
        "drivers": [bind(FIRST_DRIVER), bind(SECOND_DRIVER)],
    }


def validate(value: dict[str, Any]) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value["rule"] == (
            "Historical receipts witness their own world; they never gate the living one.")
        and value["gate"]["source_identity_equal"] is False
        and value["gate"]["historical_receipts_rewritten"] is False
        and value["gate"]["living_source_is_acceptance_predicate"] is False
        and len(value["historical_receipts"]) == 2,
        "text-recovery source-unbind receipt drift")


def derive() -> dict[str, Any]:
    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-16",
        "status": STATUS,
        "rule": (
            "Historical receipts witness their own world; they never gate the living one."),
        "authority": {"owner": authorization(), "driver": bind(Path(__file__))},
        "historical_receipts": [bind(FIRST), bind(SECOND)],
        "gate": source_gate(),
        "claim_limit": (
            "Class-A source-authority unbind only. Historical evidence is unchanged; "
            "no product, link, Completion, media or device action."),
    }
    validate(value)
    value["mutations_rejected"] = mutations(value)
    return value


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-history": lambda x: x["gate"].update(
            historical_receipts_rewritten=True),
        "gate-live-source": lambda x: x["gate"].update(
            living_source_is_acceptance_predicate=True),
        "erase-divergence": lambda x: x["gate"].update(source_identity_equal=True),
        "drop-receipt": lambda x: x["historical_receipts"].pop(),
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
    require(rejected == list(cases), "text-recovery unbind mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check"))
    action = parser.parse_args().action
    value = derive()
    if action == "record":
        require(not RECEIPT.exists(), "text-recovery unbind receipt exists")
        RECEIPT.write_bytes(canonical(value))
    else:
        require(json.loads(RECEIPT.read_text(encoding="utf-8")) == value,
                "text-recovery unbind receipt stale")
    print("text-recovery source unbind: PASS receipts=2 mutations=4")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (UnbindError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"text-recovery source unbind: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
