#!/usr/bin/env python3
"""Verify the autonomous post-v1.6 housekeeping block.

The receipt separates sealed release facts from facts that must stay live.
It never rewrites either: housekeeping is a read-only member of check-source.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/post-release/"
    "v160-post-release-housekeeping-receipt.json")
PUBLICATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/post-release/"
    "v160-public-publication-receipt-20260825.json")
RULEBOOK = ROOT / "docs/reference/gate-and-tool-register.md"
REGISTER = ROOT / "docs/reference/parked-items-register.md"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
PREPLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
REPORT = ROOT / "docs/planning/2.4-post-v1.6-housekeeping-report.md"
DOCUMENT_INDEX = ROOT / "config/document-index.json"
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
ITEM1 = ARCH / "c2.3-v1.6-item1-only-candidate-r1-receipt.json"
D5 = ARCH / "c2.3-v1.6-item1-d5-result-receipt.json"


class HousekeepingError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HousekeepingError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing file: {path.relative_to(ROOT)}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object expected: {path.relative_to(ROOT)}")
    return value


def tracked_paths() -> set[str]:
    process = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(process.returncode == 0,
            process.stderr.strip() or "git ls-files failed")
    return set(process.stdout.splitlines())


def first_red_population() -> list[str]:
    markers = ("first-red", "first_red", "red-attribution")
    result = []
    for path in ARCH.glob("*.json"):
        name = path.name.lower()
        if ("v1.6" in name or "v160" in name) and any(
                marker in name for marker in markers):
            result.append(str(path.relative_to(ROOT)))
    return sorted(result)


RULES = (
    "Instrument law",
    "Single owner and defined-state handoff",
    "Final-world and shipped-byte claims",
    "Phase-owned guards and outputs",
    "Enforce what is recorded",
    "Forecasts are floors",
    "Coverage is derived, not enumerated",
    "Domain-aware addresses",
    "Declared-width shared state",
    "Diagnostic freight lives in diagnostic worlds",
    "Anti-rabbit-hole triage",
)


def derived_capacity(value: dict[str, Any]) -> dict[str, Any]:
    item = load(ITEM1)
    publication = load(PUBLICATION)
    d5 = load(D5)
    final = item["final_product"]
    backstop = final["execution_backstop"]
    cold = final["mapped_product_cold"]
    free = d5["D5_user_headroom"]["free"]
    linked_sha = final["DMA"]["ELF"]["sha256"]
    require(linked_sha == publication["product_authority"]["linked_elf_sha256"],
            "capacity candidate is not the published linked ELF")
    require(free["symbol_slots"] ==
            publication["product_authority"]["symbol_slots_free"]
            and free["namepool_bytes"] ==
            publication["product_authority"]["namepool_bytes_free"],
            "D5 and publication headroom differ")
    intervals = value.get("post_descope_capacity", {}).get(
        "e000_free_intervals", [])
    require(intervals and all(
        isinstance(row.get("first"), int)
        and isinstance(row.get("last_exclusive"), int)
        and 0xE000 <= row["first"] < row["last_exclusive"] <= 0xFF80
        for row in intervals), "E000 interval authority malformed")
    require(all(left["last_exclusive"] <= right["first"]
                for left, right in zip(intervals, intervals[1:])),
            "E000 interval authority overlaps or is unordered")
    widths = [row["last_exclusive"] - row["first"] for row in intervals]
    return {
        "authority_linked_elf_sha256": linked_sha,
        "symbol_slots_free": free["symbol_slots"],
        "namepool_bytes_free": free["namepool_bytes"],
        "ordinary_text_free_bytes": backstop["ordinary_free_bytes"],
        "mapped_far_service_free_bytes": backstop["mapped_far_service"]["free_bytes"],
        "e000_free_intervals": intervals,
        "e000_free_total_bytes": sum(widths),
        "e000_largest_contiguous_hole_bytes": max(widths),
        "mapped_product_cold_free_bytes": cold["free_bytes"],
        "mapped_product_cold_capacity_bytes": cold["capacity_bytes"],
        "diagnostic_arena_present": final["diagnostic_freight_absent"] is False,
    }


def evidence_inventory() -> dict[str, int]:
    paths = sorted((ROOT / "tests/bytecode/dialect-v2/evidence").rglob("*.json"))
    invalid = []
    for path in paths:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            invalid.append(f"{path.relative_to(ROOT)}: {error}")
    require(not invalid, f"invalid evidence JSON: {invalid[:3]}")
    return {"json_receipts": len(paths), "invalid_json_receipts": 0}


def document_classes() -> dict[str, str]:
    value = load(DOCUMENT_INDEX)
    return {row["path"]: row["class"] for row in value["documents"]}


def validate(value: dict[str, Any]) -> dict[str, Any]:
    require(value.get("format") == "lisp65-v160-post-release-housekeeping-v1",
            "housekeeping receipt format drift")
    require(value.get("status") == "passed-host-only",
            "housekeeping status drift")
    scope = value.get("scope", {})
    require(scope == {"device_contacts": 0, "product_links": 0,
                      "product_behavior_changes": 0,
                      "public_release_mutations": 0},
            "housekeeping claim boundary drift")

    publication = load(PUBLICATION)
    public = value.get("public_release", {})
    require(public.get("main") == publication["public_git"]["main_after"]
            == publication["public_git"]["commit"]
            and public.get("tag") == "v1.6.0"
            and publication["verification"]["public_main_remote_head"] ==
                public["main"],
            "release did not land on public main")

    require(value.get("post_descope_capacity") == derived_capacity(value),
            "post-descope capacity receipt drift")
    require(value.get("historical_first_reds") == first_red_population(),
            "v1.6 first-red archive population drift")
    tracked = tracked_paths()
    require(all(path in tracked for path in value["historical_first_reds"]),
            "historical first-red archive contains untracked evidence")

    rulebook = RULEBOOK.read_text(encoding="utf-8")
    for rule in RULES:
        require(f"**{rule}.**" in rulebook,
                f"input-fidelity rule absent from rulebook: {rule}")
    require(rulebook.count("| **") >= len(RULES),
            "rulebook mutation table is malformed")

    plan = PLAN.read_text(encoding="utf-8")
    require("SEALED — 2026-08-25 (post-v1.6 housekeeping block)" in plan
            and "Posten 2 moved intact" in plan
            and "v1.7" in plan,
            "v1.6 freight plan is not sealed")
    preplan = PREPLAN.read_text(encoding="utf-8")
    require("Status: **inventory only — not commissioned**" in preplan
            and "sealed `(repl)` fault file" in preplan,
            "v1.7 pre-plan commission boundary drift")
    register = REGISTER.read_text(encoding="utf-8")
    for token in ("DELIVERED in v1.6.0: REPL cursor navigation",
                  "v1.7 Comfort freight set",
                  "Post-descope capacity watch",
                  "released set plus none"):
        require(token in register, f"parked register grooming absent: {token}")

    classes = document_classes()
    require(classes.get(str(PLAN.relative_to(ROOT))) == "historical",
            "sealed v1.6 plan is not historical")
    require(classes.get(str(PREPLAN.relative_to(ROOT))) == "current",
            "v1.7 pre-plan is not current")
    require(classes.get(str(REPORT.relative_to(ROOT))) == "current",
            "2.4 report is not indexed")

    evidence = evidence_inventory()
    recorded_evidence = value.get("evidence_hygiene", {})
    require(recorded_evidence.get("invalid_json_receipts") == 0
            and recorded_evidence.get("logical_archive") ==
                "tracked-in-place; citations preserved"
            and evidence["json_receipts"] >=
                recorded_evidence.get("minimum_json_receipts", 0),
            "evidence hygiene receipt drift")
    return {"rules": len(RULES),
            "first_reds": len(value["historical_first_reds"]),
            "evidence_json": evidence["json_receipts"]}


def selftest(value: dict[str, Any]) -> None:
    cases = []
    mutants = []
    trial = deepcopy(value)
    trial["public_release"]["main"] = "0" * 40
    mutants.append(("public-main-not-release", trial))
    trial = deepcopy(value)
    trial["post_descope_capacity"]["symbol_slots_free"] = 104
    mutants.append(("stored-capacity-world", trial))
    trial = deepcopy(value)
    trial["post_descope_capacity"]["e000_free_total_bytes"] = 194
    mutants.append(("stored-e000-aggregate", trial))
    trial = deepcopy(value)
    trial["historical_first_reds"] = trial["historical_first_reds"][1:]
    mutants.append(("unarchived-first-red", trial))
    trial = deepcopy(value)
    trial["scope"]["device_contacts"] = 1
    mutants.append(("housekeeping-device-claim", trial))
    for name, mutant in mutants:
        try:
            validate(mutant)
        except HousekeepingError:
            cases.append(name)
        else:
            raise HousekeepingError(f"housekeeping mutation survived: {name}")
    require(cases == [name for name, _ in mutants],
            "housekeeping mutation set drift")
    print("v1.6 post-release housekeeping: SELFTEST PASS mutations=5")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", nargs="?", choices=("check", "selftest"),
                        default="check")
    args = parser.parse_args()
    try:
        value = load(RECEIPT)
        if args.action == "selftest":
            selftest(value)
        else:
            result = validate(value)
            print("v1.6 post-release housekeeping: PASS "
                  f"rules={result['rules']} first-reds={result['first_reds']} "
                  f"evidence-json={result['evidence_json']}")
        return 0
    except (HousekeepingError, KeyError, TypeError, ValueError) as error:
        print(f"v1.6 post-release housekeeping: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
