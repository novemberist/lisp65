#!/usr/bin/env python3
"""Validate the owner-approved C2 runtime-family lifetime contract."""

from __future__ import annotations

import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-runtime-slice-lifetime-substitution-contract.json"


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def validate(value: dict) -> None:
    require(value.get("format") ==
            "lisp65-c2-runtime-slice-lifetime-substitution-contract-v1",
            "format drift")
    boundary = value["format_boundary"]
    require(boundary == {
        "runtime_store": "L65R-v1",
        "file_offset_bits_per_family": 16,
        "bytes_per_family": 65536,
        "maximum_dense_slots_per_family": 64,
        "general_multibank_store":
            "not introduced; recorded C3-class growth path",
    }, "L65R boundary drift")
    families = value["families"]
    require(set(families) == {"boot-validation", "session-runtime"},
            "family census drift")
    boot = families["boot-validation"]
    session = families["session-runtime"]
    require(boot["id"] == 1 and boot["physical_base"] == "0x08200000"
            and boot["generation"] == 0, "boot family binding drift")
    require(session["id"] == 2
            and session["physical_base"] == "0x08000000"
            and session["generation"] == "nonzero-current-c2-generation",
            "session family binding drift")
    require(boot["slots"] == [
        "catalog-verifier", "record-verifier", "c2-decode-00",
        "c2-decode-01", "c2-decode-02a", "c2-decode-02b",
        "c2-decode-03", "resident-island-installer",
    ], "boot slot map drift")
    measured = value["measured_input"]
    require(measured["boot_only_raw_bytes"] == 6605
            and measured["boot_only_rounded_bytes"] == 7168,
            "boot-exclusive measurement drift")
    require(measured["combined_deficit_bytes"] ==
            measured["bank0_relief_required_bytes"]
            + measured["single_store_overflow_bytes"] == 3305,
            "deficit arithmetic drift")
    require(measured["boot_only_rounded_bytes"] >
            measured["combined_deficit_bytes"],
            "lifetime substitution no longer closes the measured deficit")
    transition = value["transition"]
    require(transition["switch_cutpoint"] ==
            "after successful phase 3 and before any phase 4 call",
            "switch cutpoint drift")
    require("generation-invalidating prepare operation" in
            transition["reverse_transition"], "restage ordering drift")
    cases = value["required_negative_cases"]
    require(len(cases) == 8 and len(set(cases)) == 8,
            "negative-case census drift")


def mutation_tests(value: dict) -> int:
    mutations = []
    def add(path, replacement):
        candidate = copy.deepcopy(value)
        target = candidate
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = replacement
        mutations.append(candidate)
    add(("format_boundary", "file_offset_bits_per_family"), 24)
    add(("format_boundary", "bytes_per_family"), 131072)
    add(("families", "boot-validation", "physical_base"), "0x08000000")
    add(("families", "boot-validation", "generation"), 1)
    add(("families", "session-runtime", "physical_base"), "0x08200000")
    add(("transition", "switch_cutpoint"), "after publication")
    add(("transition", "reverse_transition"), "allowed")
    add(("measured_input", "boot_only_rounded_bytes"), 3072)
    bad = copy.deepcopy(value)
    bad["required_negative_cases"].pop()
    mutations.append(bad)
    rejected = 0
    for candidate in mutations:
        try:
            validate(candidate)
        except GateError:
            rejected += 1
    require(rejected == len(mutations), "a lifetime-contract mutation passed")
    return rejected


def main() -> int:
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    validate(value)
    rejected = mutation_tests(value)
    print("c2-runtime-slice-lifetime: PASS "
          f"families=2 negative-cases=8 mutations-rejected={rejected} "
          "u16-store=unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
