#!/usr/bin/env python3
"""Attribute the final-red Link-115 WYSIWYG card capacity stop."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RED = ARCH / "c2.3-v2.1-wysiwyg-input-card-final-red.json"
FIX = ARCH / "c2.3-v2.1-wysiwyg-input-receipt.json"
CANDIDATE_MAP = ROOT / (
    "build/c2.3/v2.1-wysiwyg-input-card/wplto/"
    "resident-island-seed.prg.map")
PRIOR_MAP = ROOT / (
    "build/c2.3/v2.1-root-padding-configurator-parity-continuation/final/"
    "lisp65-c2-substitution-linked.prg.map")
RECEIPT = ARCH / "c2.3-v2.1-wysiwyg-input-card-red-attribution-receipt.json"
FORMAT = "lisp65-c2.3-v2.1-wysiwyg-input-card-red-attribution-v1"
STATUS = "FINAL-RED-ATTRIBUTED: WYSIWYG COSTS 17 BYTES; ORDINARY-TEXT DEFICIT 13"
RECORDED_ON = "2026-08-17"


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
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def map_values(path: Path) -> dict[str, int]:
    text = path.read_text(encoding="utf-8")
    repl = re.search(
        r"^\s*([0-9a-f]+)\s+\1\s+([0-9a-f]+)\s+1\s+.*\(\.text\.repl\)$",
        text, re.MULTILINE)
    end = re.search(
        r"^\s*([0-9a-f]+)\s+\1\s+0\s+1\s+__init_array_start = \.$",
        text, re.MULTILINE)
    facade = re.search(
        r"^\s*([0-9a-f]+)\s+\1\s+62\s+1\s+\.lisp65_c2_mapped_far_facade$",
        text, re.MULTILINE)
    require(repl is not None and end is not None and facade is not None,
            f"map geometry absent: {path}")
    return {"repl_start": int(repl.group(1), 16),
            "repl_bytes": int(repl.group(2), 16),
            "ordinary_text_end_exclusive": int(end.group(1), 16),
            "mapped_far_facade_start": int(facade.group(1), 16)}


def derive() -> dict[str, Any]:
    red, fix = load(RED), load(FIX)
    prior, candidate = map_values(PRIOR_MAP), map_values(CANDIDATE_MAP)
    require(red["status"] == "FINAL RED: WYSIWYG card returns to owner"
            and red["retry_authorized"] is False
            and red["owner_disposition_required"] is True
            and red["attempt_accounting"]["cards_consumed"] == 1
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_link_attempts"] == 1
            and "ordinary text displaced the mapped far facade"
                in red["error"]["message"],
            "WYSIWYG Final Red/card accounting drift")
    require(fix["status"].startswith("PASS: A0-TO-SPACE")
            and fix["historical_regressions"]["Link112"]
                ["canonical_object_bytes"] == 12
            and fix["historical_regressions"]["Link113"]
                ["canonical_object_bytes"] == 12,
            "host-qualified input contract drift")
    growth = candidate["repl_bytes"] - prior["repl_bytes"]
    prior_headroom = (prior["mapped_far_facade_start"]
                      - prior["ordinary_text_end_exclusive"])
    candidate_overlap = (candidate["ordinary_text_end_exclusive"]
                         - candidate["mapped_far_facade_start"])
    require(prior["repl_start"] == candidate["repl_start"] == 0xAA48
            and prior["repl_bytes"] == 0x2BF
            and candidate["repl_bytes"] == 0x2D0
            and growth == 17 and prior_headroom == 4
            and candidate_overlap == 13,
            "WYSIWYG capacity arithmetic drift")
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
        "classification": {
            "kind": "REAL PRODUCT CAPACITY STOP",
            "stage": "first/seed product link before candidate artifacts",
            "linker_guard": "ordinary text must end at/before mapped far facade",
            "guard_fired_correctly": True,
            "product_semantics_host_green": True,
            "product_candidate_exists": False,
        },
        "capacity": {"prior": prior, "candidate_seed_map": candidate,
            "repl_growth_bytes": growth,
            "prior_ordinary_text_headroom_bytes": prior_headroom,
            "ordinary_text_deficit_bytes": candidate_overlap,
            "facade_start": "0xb3b0",
            "minimum_recovery_before_any_replacement_card_bytes": 13,
            "contracted_margins_are_freight_budgets": False},
        "card_accounting": red["attempt_accounting"],
        "disposition": {
            "retry_authorized": False,
            "owner_disposition_required": True,
            "narrowest_contract_preserving_direction": (
                "price at least 13 ordinary-text bytes via semantics-preserving "
                "instruction reduction or a contracted cold-routine relocation; "
                "do not spend margins and do not weaken visible rejection"),
            "alternative": "park the WYSIWYG contract/card and keep D2 closed",
            "not_authorized": ["retry", "Completion", "media", "device", "D2"],
        },
        "authority": {"Final_Red": bind(RED), "host_fix": bind(FIX),
            "candidate_seed_map": bind(CANDIDATE_MAP),
            "prior_green_map": bind(PRIOR_MAP), "checker": bind(Path(__file__))},
        "claim_limit": (
            "Read-only Final-Red attribution. No source fix, WPLTO retry, "
            "Completion, media, device contact, or D2 authorization."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT and value["status"] == STATUS,
            "attribution identity drift")
    classification = value["classification"]
    require(classification["kind"] == "REAL PRODUCT CAPACITY STOP"
            and classification["guard_fired_correctly"] is True
            and classification["product_semantics_host_green"] is True
            and classification["product_candidate_exists"] is False,
            "capacity-stop classification drift")
    capacity = value["capacity"]
    require(capacity["repl_growth_bytes"] == 17
            and capacity["prior_ordinary_text_headroom_bytes"] == 4
            and capacity["ordinary_text_deficit_bytes"] == 13
            and capacity["minimum_recovery_before_any_replacement_card_bytes"] == 13
            and capacity["contracted_margins_are_freight_budgets"] is False,
            "capacity facts drift")
    disposition = value["disposition"]
    require(disposition["retry_authorized"] is False
            and disposition["owner_disposition_required"] is True
            and set(disposition["not_authorized"])
                == {"retry", "Completion", "media", "device", "D2"}
            and "do not weaken visible rejection"
                in disposition["narrowest_contract_preserving_direction"],
            "Final-Red disposition boundary drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "call-harness-red": lambda x: x["classification"].update(
            kind="HARNESS STOP"),
        "guard-failed": lambda x: x["classification"].update(
            guard_fired_correctly=False),
        "claim-candidate": lambda x: x["classification"].update(
            product_candidate_exists=True),
        "growth-minus-one": lambda x: x["capacity"].update(
            repl_growth_bytes=16),
        "spend-margin": lambda x: x["capacity"].update(
            contracted_margins_are_freight_budgets=True),
        "deficit-twelve": lambda x: x["capacity"].update(
            ordinary_text_deficit_bytes=12),
        "recover-twelve": lambda x: x["capacity"].update(
            minimum_recovery_before_any_replacement_card_bytes=12),
        "silent-retry": lambda x: x["disposition"].update(
            retry_authorized=True),
        "drop-owner": lambda x: x["disposition"].update(
            owner_disposition_required=False),
        "weaken-visible-error": lambda x: x["disposition"].update(
            narrowest_contract_preserving_direction="remove rejection"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "Final-Red attribution mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    value = derive()
    validate(value)
    value["mutations_rejected"] = mutations(value)
    if action == "record":
        RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        require(load(RECEIPT) == value, "Final-Red attribution receipt stale")
    else:
        require(len(value["mutations_rejected"]) == 10,
                "mutation count drift")
    print("WYSIWYG card attribution: PASS "
          f"action={action} growth=17 deficit=13 mutations=10")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"WYSIWYG card attribution: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
