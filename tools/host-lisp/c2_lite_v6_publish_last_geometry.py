#!/usr/bin/env python3
"""Authoritative C2-lite publish-last verifier-table geometry gate."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_product_substitution_link as P  # noqa: E402


CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
ADDENDUM = ROOT / "docs/planning/c2-lite-execution-contract-addendum.md"
WPLTO_ELF = ROOT / (
    "build/c2-lite/v6-bank3-stage-asm-fallback-wplto-replay2/"
    "full-product-wplto/c2-lite-v6-full-seed.prg.elf")
SECTION = ".lisp65_runtime_overlay_verifier_bindings"
ADDRESS = 0xB9CD
BYTES = 40
HISTORICAL_ADDRESS = 0xB954
HISTORICAL_C2_LITE_ADDRESS = 0xB99B


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def geometry_errors(address: int, size: int,
                    symbols: dict[str, int]) -> list[str]:
    expected = {
        "__lisp65_rtov_verifier_bindings_start": ADDRESS,
        "rtov_boot_verifiers": ADDRESS,
        "rtov_verifiers": ADDRESS + 16,
        "__lisp65_rtov_verifier_bindings_end": ADDRESS + 32,
        "__lisp65_rtov_family_stage_bindings_start": ADDRESS + 32,
        "rtov_family_stage_bindings": ADDRESS + 32,
        "__lisp65_rtov_family_stage_bindings_end": ADDRESS + BYTES,
    }
    errors: list[str] = []
    if address != ADDRESS:
        errors.append("wrong-address")
    if size != BYTES:
        errors.append("wrong-size")
    if {name: symbols.get(name) for name in expected} != expected:
        errors.append("wrong-symbol-boundary")
    return errors


def witness(elf: Path) -> dict[str, Any]:
    require(elf.is_file(), f"C2-lite geometry witness absent: {elf}")
    section = P.section_table(elf).get(SECTION)
    require(section is not None, f"C2-lite verifier section absent: {elf}")
    symbols = P.defined_symbols(elf)
    errors = geometry_errors(section["address"], section["bytes"], symbols)
    require(not errors, f"C2-lite verifier geometry red: {elf}: {errors}")
    return {
        "path": elf.relative_to(ROOT).as_posix(),
        "address": f"0x{section['address']:04x}",
        "bytes": section["bytes"],
        "symbols": {
            name: f"0x{symbols[name]:04x}" for name in (
                "__lisp65_rtov_verifier_bindings_start",
                "rtov_boot_verifiers", "rtov_verifiers",
                "__lisp65_rtov_verifier_bindings_end",
                "__lisp65_rtov_family_stage_bindings_start",
                "rtov_family_stage_bindings",
                "__lisp65_rtov_family_stage_bindings_end")
        },
    }


def collect() -> dict[str, Any]:
    config = json.loads(CONTRACT.read_text(encoding="utf-8"))
    geometry = config["publish_last_geometry"]
    table = geometry["runtime_overlay_verifier_bindings"]
    require(
        geometry["status"]
            == "class-c-repinned-for-bank3-bootstrap-artifact-completion"
        and int(table["address"], 0) == ADDRESS
        and int(table["historical_pre_c2_lite_address"], 0)
            == HISTORICAL_ADDRESS
        and int(table["historical_pre_bank3_bootstrap_address"], 0)
            == HISTORICAL_C2_LITE_ADDRESS
        and table["bytes"] == BYTES
        and int(table["wplto_witness"], 0) == ADDRESS
        and int(table["artifact_candidate_witness"], 0) == ADDRESS
        and geometry["kernal_window_crc_operands_bytes"] == 2
        and geometry["total_publish_last_domain_bytes"] == 42,
        "C2-lite publish-last config authority drift")
    addendum = ADDENDUM.read_text(encoding="utf-8").lower()
    require("c2-lite publish-last geometry" in addendum
            and "`$b9cd`" in addendum and "`$b99b`" in addendum
            and "`$b954`" in addendum
            and "42 named" in addendum,
            "C2-lite publish-last addendum authority drift")
    require(P.VERIFIER_BINDING_BASE == HISTORICAL_ADDRESS,
            "historical pre-C2-lite generic pin was rewritten")
    witnesses = [witness(WPLTO_ELF)]
    canonical_symbols = {
        "__lisp65_rtov_verifier_bindings_start": ADDRESS,
        "rtov_boot_verifiers": ADDRESS,
        "rtov_verifiers": ADDRESS + 16,
        "__lisp65_rtov_verifier_bindings_end": ADDRESS + 32,
        "__lisp65_rtov_family_stage_bindings_start": ADDRESS + 32,
        "rtov_family_stage_bindings": ADDRESS + 32,
        "__lisp65_rtov_family_stage_bindings_end": ADDRESS + BYTES,
    }
    negatives = {
        "historical-address-in-c2-lite-profile": geometry_errors(
            HISTORICAL_ADDRESS, BYTES, canonical_symbols) == ["wrong-address"],
        "wrong-size": geometry_errors(
            ADDRESS, BYTES - 1, canonical_symbols) == ["wrong-size"],
        "wrong-symbol-boundary": geometry_errors(
            ADDRESS, BYTES,
            {**canonical_symbols, "rtov_verifiers": ADDRESS + 15})
            == ["wrong-symbol-boundary"],
    }
    require(all(negatives.values()), "C2-lite geometry mutation matrix red")
    return {
        "format": "lisp65-c2-lite-v6-publish-last-geometry-v1",
        "status": "passed-authority-and-sha-bound-wplto-witness",
        "profile": "C2-lite/C2D-v6",
        "section": SECTION,
        "address": "0xb9cd",
        "bytes": BYTES,
        "historical_pre_c2_lite_address": "0xb954",
        "historical_pre_bank3_bootstrap_address": "0xb99b",
        "generic_historical_default_unchanged": True,
        "witnesses": witnesses,
        "negative_matrix": {name: "rejected" for name in negatives},
        "rule": (
            "The Bank-3 C2-lite pin is profile-specific. Historical B99B and "
            "B954 receipts and the generic pre-C2-lite default remain unchanged."),
    }


if __name__ == "__main__":
    print(json.dumps(collect(), indent=2, sort_keys=True))
