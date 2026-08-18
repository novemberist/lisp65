#!/usr/bin/env python3
"""Loudly rebind the historical B9CD attribution after its approved repair."""

from __future__ import annotations

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
HISTORICAL = ARCH / (
    "c2.3-v2.1-local-return-identity-card-red-attribution-receipt.json")
HISTORICAL_RED = ARCH / "c2.3-v2.1-local-return-identity-card-final-red.json"
SWEEP = ARCH / "c2.3-v2.1-pinned-constant-sweep-receipt.json"
CARD_RED = ARCH / "c2.3-v2.1-pinned-constant-card-final-red.json"
CARD_ATTRIBUTION = ARCH / (
    "c2.3-v2.1-pinned-constant-card-red-attribution-receipt.json")
LEGACY = ROOT / (
    "tools/host-lisp/c2_lite_v6_link50_persistent_header_successor_link.py")
RECEIPT = ARCH / (
    "c2.3-v2.1-local-return-identity-attribution-rebind-"
    "2026-08-14-pinned-constant-sweep.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "d615bcf4"


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
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def derive() -> dict[str, Any]:
    historical = load(HISTORICAL)
    historical_red = load(HISTORICAL_RED)
    sweep = load(SWEEP)
    card_red = load(CARD_RED)
    correction = load(CARD_ATTRIBUTION)
    require(
        historical.get("status") ==
            "ATTRIBUTED FINAL RED: legacy qualification stage pins verifier base"
        and historical["new_final_red"]["implicit_expected_address"] == "0xb9cd"
        and historical["new_final_red"]["candidate_address"] == "0xb98c"
        and historical["card_disposition"]["retry_authorized"] is False
        and historical_red.get("retry_authorized") is False,
        "historical B9CD attribution drift")
    require(
        sweep.get("status") ==
            "PASS: remaining qualification constants candidate-derived; pinned=0"
        and card_red.get("status") ==
            "FINAL RED: sole pinned-constant card returns to owner"
        and card_red.get("retry_authorized") is False
        and correction.get("status") ==
            "ATTRIBUTED FINAL RED: transitive F1 helper pins overlay-size ceiling"
        and correction["authorized_work_result"]
            ["specific_candidate_stage_address"] == "0xb98c",
        "pinned-sweep successor authority drift")
    source = LEGACY.read_text(encoding="utf-8")
    require(
        "stage = BASE.ART.stage_product_gate(\n"
        "        elf, verifier_base=verifier.address)" in source
        and "stage = BASE.ART.stage_product_gate(elf)" not in source,
        "approved B9CD-to-candidate repair is not live")
    return {
        "format": "lisp65-c2.3-v21-local-return-attribution-rebind-v1",
        "recorded_on": "2026-08-14",
        "status": "PASS: loud historical B9CD attribution rebind after repair",
        "authority": {"authorization": git_binding(AUTHORIZATION, PLAN),
            "historical_attribution": bind(HISTORICAL),
            "historical_final_red": bind(HISTORICAL_RED),
            "pinned_sweep": bind(SWEEP), "successor_card_red": bind(CARD_RED),
            "successor_attribution": bind(CARD_ATTRIBUTION),
            "current_consumer": bind(LEGACY), "driver": bind(DRIVER)},
        "history": {"historical_mechanism_remains_true": True,
            "historical_receipt_rewritten": False,
            "old_implicit_address": "0xb9cd",
            "candidate_address": "0xb98c"},
        "current_source": {"implicit_historical_default_consumed": False,
            "candidate_ELF_section_address_consumed": True,
            "specific_repair_linked_green": True},
        "successor_disposition": {"card_consumed": True,
            "retry_authorized": False, "owner_disposition_required": True,
            "completion_allowed": False, "media_allowed": False,
            "device_allowed": False},
        "claim_limit": (
            "Authority/provenance rebind only. Historical attribution remains "
            "unchanged; no retry, completion, media or device action."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value == derive(), "local-return attribution rebind drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-history": lambda x: x["history"].update(
            historical_receipt_rewritten=True),
        "erase-old-mechanism": lambda x: x["history"].update(
            historical_mechanism_remains_true=False),
        "retain-old-default": lambda x: x["current_source"].update(
            implicit_historical_default_consumed=True),
        "hide-candidate-source": lambda x: x["current_source"].update(
            candidate_ELF_section_address_consumed=False),
        "authorize-retry": lambda x: x["successor_disposition"].update(
            retry_authorized=True),
        "allow-device": lambda x: x["successor_disposition"].update(
            device_allowed=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "local-return rebind mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "local-return attribution rebind exists")
    value = derive(); validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 local-return attribution rebind: PASS historical=b9cd "
          "current=candidate mutations=6")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value)
    require(rejected == mutations(value),
            "local-return attribution rebind mutation set drift")
    print("2.1 local-return attribution rebind: CHECK PASS "
          "historical=b9cd current=candidate")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check"),
            "usage: c2_v21_local_return_identity_attribution_rebind_"
            "pinned_20260814.py record|check")
    {"record": record, "check": check}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RebindError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"2.1 local-return attribution rebind: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
