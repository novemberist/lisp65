#!/usr/bin/env python3
"""Purely replay the profile-derived section inventory on the immutable seed."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link33_product_profile as PROFILE  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402


SEED_ROOT = ROOT / (
    "build/c2.2/substitution/product-link-33-profile-bound-final")
SEED = SEED_ROOT / "resident-island-seed.prg"
SEED_SHA = "f49dfae7bbf82790619fe915ed177240cf2364a354ef29c9b417b4dc9350fe17"
SEED_ELF_SHA = "f15c68c6586c03463a69a6c45e52f431576ae67ecbf73b6fc6b095eb02e5153e"
SEED_LTO_SHA = "5f326a7a2d416ef19d3035d305c155c128b81dcbe877fee26469a3de3119219d"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link33-profile-bound-structural-receipt.json")
FIRST_RED_SHA = "7e128fcbe3caa248d78de9dcc7594c005829338a99cc61f60c2a7b0fb3e18715"
PROFILE_BINDING = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-product-profile-binding-replay-receipt.json")
PROFILE_BINDING_SHA = (
    "2ac45ba1b02bc995693f8a8ee84034a233b4481f526db03c4a8a85258647d3c6")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-profile-derived-section-inventory-replay-receipt.json")


class ReplayError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def tree_sha(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(
            f"{sha(path)}  {path.relative_to(root).as_posix()}\n".encode(
                "ascii"))
    return digest.hexdigest()


def mutation_gate(expected: list[str], sections: list[dict[str, object]]) \
        -> dict[str, str]:
    def rejected(rows: list[dict[str, object]], *, set_only: bool = False) -> None:
        violations = P._final_section_inventory_violations(expected, rows)
        require("section-name-set" in violations,
                f"section-name mutation escaped: {violations}")
        if not set_only:
            require("section-count" in violations,
                    f"section-count mutation escaped: {violations}")

    missing = sections[1:]
    extra = [*sections, {"name": ".unlisted-profile-section",
                         "address": 0, "bytes": 0, "flags": []}]
    resurrected = [dict(row) for row in sections]
    roots = next(index for index, row in enumerate(resurrected)
                 if row["name"] == ".lisp65_rt_c2append_roots")
    resurrected[roots]["name"] = ".lisp65_rt_c2append_capacity"
    rejected(missing)
    rejected(extra)
    rejected(resurrected, set_only=True)
    return {
        "missing-expected-name": "rejected-count-and-set",
        "additional-unknown-name": "rejected-count-and-set",
        "same-count-old-profile-resurrection": "rejected-name-set",
    }


def check() -> dict[str, Any]:
    require(SEED.is_file() and sha(SEED) == SEED_SHA,
            "immutable profile-bound seed drift")
    require(sha(Path(str(SEED) + ".elf")) == SEED_ELF_SHA
            and sha(Path(str(SEED) + ".lto.o")) == SEED_LTO_SHA,
            "immutable seed ELF/LTO evidence drift")
    require(sha(FIRST_RED) == FIRST_RED_SHA,
            "profile-bound inventory First-Red receipt drift")
    require(sha(PROFILE_BINDING) == PROFILE_BINDING_SHA,
            "canonical profile binding receipt drift")
    before = tree_sha(SEED_ROOT)
    PROFILE.configure(P)
    expectation = P.final_section_inventory_expectation()
    report = P.final_section_inventory_check(SEED)
    expected = list(expectation["names"])
    sections = list(report["actual_sections"])
    require(expectation["base_pin_names"] == 140
            and expectation["expected_names"] == 167,
            "profile-derived inventory cardinality drift")
    require(len(expectation["removed_from_link28"]) == 4
            and len(expectation["added_by_configured_profile"]) == 31,
            "profile-derived inventory attribution drift")
    require(report["status"] == "passed"
            and len(sections) == len(expected) == 167,
            "profile-derived inventory replay is not green")
    matrix = mutation_gate(expected, sections)
    after = tree_sha(SEED_ROOT)
    require(after == before, "pure replay modified immutable seed evidence")
    return {
        "format": "lisp65-c2-link33-profile-derived-inventory-replay-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-profile-derived-inventory-pure-replay-no-link",
        "canonical_profile_object": PROFILE.receipt_identity(),
        "source_evidence": {
            "first_red_receipt": bind(FIRST_RED),
            "profile_binding_receipt": bind(PROFILE_BINDING),
            "seed": bind(SEED),
            "seed_elf": bind(Path(str(SEED) + ".elf")),
            "seed_lto_object": bind(Path(str(SEED) + ".lto.o")),
            "seed_tree_sha256_before": before,
            "seed_tree_sha256_after": after,
            "seed_tree_unchanged": True,
        },
        "derivation": {
            "base_link28_names": expectation["base_pin_names"],
            "expected_link33_names": expectation["expected_names"],
            "removed_from_link28": expectation["removed_from_link28"],
            "added_by_configured_profile":
                expectation["added_by_configured_profile"],
            "removed_count": 4,
            "added_count": 31,
            "rule": expectation["derivation"],
            "actual_name_set_matches_exactly": True,
        },
        "negative_matrix": matrix,
        "llvm_sympart": report["llvm_sympart"],
        "execution_accounting": {
            "compiler_runs": 0, "linker_runs": 0,
            "product_links": 0, "hardware_runs": 0,
        },
        "claim_limit": (
            "Only the exact profile-derived final-section name set and count "
            "are accepted on one immutable seed ELF. No capacity, product or "
            "hardware result is inherited."),
        "next_gate": "one fresh separately gated Link 33 attempt",
    }


def run() -> dict[str, Any]:
    require(not RECEIPT.exists(), "inventory replay is one-shot")
    value = check()
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "check"))
    args = parser.parse_args()
    value = check() if args.action == "check" else run()
    print("c2-link33-section-inventory-replay: " + value["status"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, PROFILE.ProfileError, OSError, ValueError, KeyError,
            json.JSONDecodeError, RuntimeError) as error:
        print(f"c2-link33-section-inventory-replay: FAIL {error}",
              file=sys.stderr)
        raise SystemExit(2)
