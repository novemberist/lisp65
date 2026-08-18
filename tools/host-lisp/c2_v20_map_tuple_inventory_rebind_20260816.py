#!/usr/bin/env python3
"""Rebind Link-101's historical ASM count to the live rule classification."""

from __future__ import annotations

import argparse
from copy import deepcopy
import ast
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

import c2_v20_map_tuple_fix_card as M  # noqa: E402


PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
RECEIPT = M.INVENTORY_REBIND
FIXTURE_REBIND = M.EVIDENCE / (
    "c2.3-v2.0-map-tuple-fixture-scope-rebind-2026-08-14.json")
HISTORICAL_FIXTURE_REBIND_SHA256 = (
    "a36ce746ec706152a63d3b78d500bead17ca7ff436c5f67877a49f8c1ea56b4a")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "3cfa7a36"
RECORDED_ON = "2026-08-16"


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


def authorization() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().split())
    for token in ("29 pinned versus 31 legitimate asm functions",
                  "counted expectation converts to the rule-based classification",
                  "historical evidence untouched", "d2 second attempt"):
        require(token in text, f"inventory-rebind authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def historical() -> dict[str, Any]:
    require(hashlib.sha256(M.FINAL_RED.read_bytes()).hexdigest() ==
            M.HISTORICAL_FINAL_RED_SHA256,
            "historical Link-101 Final Red was rewritten")
    value = load(M.FINAL_RED)
    inventory = value.get("post_red_closure", {}).get(
        "real_global_ASM_inventory", {})
    require(value.get("status") ==
            "FINAL RED: corrected-tuple card returns to owner"
            and inventory == {
                "status": "passed-real-global-assembler-inventory",
                "declared_functions": 29,
                "duplicate-successor-in-global-asm-domain": "rejected"},
            "historical Link-101 inventory evidence drift")
    return value


def historical_fixture_rebind() -> dict[str, Any]:
    require(hashlib.sha256(FIXTURE_REBIND.read_bytes()).hexdigest() ==
            HISTORICAL_FIXTURE_REBIND_SHA256,
            "historical MAP-tuple fixture rebind was rewritten")
    value = load(FIXTURE_REBIND)
    inventory = value.get("current_gate", {}).get("real_global_inventory", {})
    require(
        value.get("format") ==
            "lisp65-c2.3-v20-map-tuple-fixture-scope-rebind-v1"
        and value.get("status") ==
            "PASS: MAP-tuple fixture selects owner identity, not registry cardinality"
        and value.get("change", {}).get("historical_receipt_rewritten") is False
        and value.get("change", {}).get("semantic_MAP_tuple_claim_changed") is False
        and value.get("current_gate", {}).get("selected_successor_copies") == 1
        and inventory.get("declared_functions") == 29,
        "historical MAP-tuple fixture rebind evidence drift")
    return value


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = (M.DRIVER.read_text(encoding="utf-8")
              if source_override is None else source_override)
    tree = ast.parse(source)
    function = next((ast.unparse(node) for node in tree.body
                     if isinstance(node, ast.FunctionDef)
                     and node.name == "real_asm_inventory_gate"), "")
    require(
        "ASM_ABI.source_inventory()" in function
        and "classified_functions" in function
        and "unclassified_functions" in function
        and "len(positive) == 29" not in function
        and "len(positive) != 29" not in function,
        "live inventory consumer retains a historical count expectation")
    return {"status": "PASS: live inventory is classified, not counted",
            "historical_count_pins": 0}


def derive() -> dict[str, Any]:
    old = historical()
    fixture = historical_fixture_rebind()
    live = M.real_asm_inventory_gate()
    successors = live.get("authorized_successors", {})
    historical_count = old["post_red_closure"][
        "real_global_ASM_inventory"]["declared_functions"]
    require(
        live.get("expectation") == "rule-classified-candidate-inventory"
        and live.get("unclassified_functions") == []
        and live.get("declared_functions") ==
            len(live.get("classified_functions", []))
        and live["declared_functions"] == historical_count + len(successors)
        and sorted(successors) == ["c2_map_cpu_read", "c2_map_cpu_selector"],
        "live Link-101 inventory delta is not the two authorized successors")
    return {
        "format": "lisp65-c2.3-v20-map-tuple-inventory-rebind-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: Link-101 inventory expectation is rule-classified",
        "authority": {"authorization": authorization(),
            "historical_final_red": bind(M.FINAL_RED),
            "prior_rebind": bind(M.FINAL_RED_REBIND),
            "historical_fixture_rebind": bind(FIXTURE_REBIND),
            "current_driver": bind(M.DRIVER),
            "rebind_driver": bind(DRIVER)},
        "historical": {"evidence_untouched": True,
                       "declared_functions": historical_count,
                       "fixture_rebind_evidence_untouched": True,
                       "fixture_selected_successor_copies":
                           fixture["current_gate"]["selected_successor_copies"]},
        "live_inventory": live,
        "delta": {"count": len(successors),
                  "authorized_successors": sorted(successors),
                  "classification": "all-current-members-policy-backed"},
        "change": {"expectation": "rule-based-classification",
            "historical_receipt_rewritten": False,
            "semantic_claims_changed": False},
        "claim_limit": (
            "Consumer/rebind only. Historical Link-101 evidence is untouched; "
            "no card, WPLTO, link, media or device action."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value == derive(), "Link-101 inventory rebind drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-live-count-29": lambda x: x["live_inventory"].update(
            expectation="historical-count-29"),
        "drop-authorized-successor": lambda x: x["delta"][
            "authorized_successors"].pop(),
        "accept-unclassified-member": lambda x: x["live_inventory"].update(
            unclassified_functions=["unknown_asm"]),
        "rewrite-history": lambda x: x["change"].update(
            historical_receipt_rewritten=True),
        "rewrite-fixture-history": lambda x: x["historical"].update(
            fixture_rebind_evidence_untouched=False),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "Link-101 inventory mutation survived")
    return rejected


def write() -> None:
    require(not RECEIPT.exists(), "Link-101 inventory rebind is one-shot")
    source_gate()
    value = derive(); value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("Link-101 inventory rebind: PASS historical=29 live=31 mutations=5")


def check() -> None:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    source_gate(); validate(value)
    require(rejected == mutations(value), "inventory mutation receipt drift")
    print("Link-101 inventory rebind: CHECK PASS rule-classified live=31")


def selftest() -> None:
    source_gate(); value = derive()
    require(len(mutations(value)) == 5, "inventory mutation count drift")
    print("Link-101 inventory rebind: SELFTEST PASS mutations=5")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "selftest", "check"))
    action = parser.parse_args().action
    {"write": write, "selftest": selftest, "check": check}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Link-101 inventory rebind: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
