#!/usr/bin/env python3
"""Build the one authorized export-SYMI successor as product Link 43."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_export_symbol_domain_wplto as DOMAIN  # noqa: E402
import c2_lite_v6_final_island_identity_successor_link as LINK42  # noqa: E402


LINK = LINK42.LINK
BASE_LINK = LINK42.BASE_LINK
P = LINK42.P
LINK_NUMBER = 43
OUT = ROOT / (
    "build/c2.2/substitution/"
    "product-link-43-c2-lite-v6-export-symbol-domain")
RECEIPT = LINK.EVIDENCE / (
    "c2.2-product-link43-c2-lite-v6-export-symbol-domain-"
    "structural-receipt.json")
BASELINE_DIR = ROOT / (
    "build/c2.2/substitution/"
    "product-link-42-c2-lite-v6-final-island-identity-replay")
BASELINE = BASELINE_DIR / "lisp65-c2-substitution-linked.prg"
BASELINE_SHA = (
    "0fa2ae3310d631ae5cebfb8634602d72c68928b8cbb575d98f604feba3a2ecb0")
BASELINE_RECEIPT = LINK.EVIDENCE / (
    "c2.2-product-link42-c2-lite-v6-final-island-identity-replay-"
    "structural-receipt.json")
BASELINE_RECEIPT_SHA = (
    "e9ba8bc2eecc96dfe190d74abcf95371bcdd05b96184d38405019f39b040698c")
WPLTO = LINK.EVIDENCE / (
    "c2.2-c2-lite-v6-export-symbol-domain-wplto-artifact-replay-receipt.json")
WPLTO_SHA = (
    "7ab92ed79b9005d40a260a2eafad1aa7eef85fb7200b7458eb3cf4351580d3b4")
CONTRACT_REBIND = LINK.EVIDENCE / (
    "c2.2-c2-lite-v6-export-symbol-domain-contract-rebind-receipt.json")
CONTRACT_REBIND_SHA = (
    "d2a36f1bb1b18e9b46d3386db1992cf65bc94e0860a18f0d8497ec67246fe59c")
HARDWARE_FIRST_RED = LINK.EVIDENCE / (
    "c2.2-product-link42-c2-lite-v6-export-symbol-domain-"
    "hardware-first-red.json")
HARDWARE_FIRST_RED_SHA = DOMAIN.FIRST_RED_SHA
CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
ADDENDUM = ROOT / "docs/planning/c2-lite-execution-contract-addendum.md"
EXPECTED_SESSION_BYTES = 65438
EXPECTED_SESSION_HEADROOM = 98


def prerequisites() -> dict[str, Any]:
    for path, digest in {
            BASELINE: BASELINE_SHA,
            BASELINE_RECEIPT: BASELINE_RECEIPT_SHA,
            WPLTO: WPLTO_SHA,
            CONTRACT_REBIND: CONTRACT_REBIND_SHA,
            HARDWARE_FIRST_RED: HARDWARE_FIRST_RED_SHA}.items():
        LINK.require(path.is_file() and LINK.sha(path) == digest,
                     f"Link-43 authority drift: {path}")
    baseline = json.loads(BASELINE_RECEIPT.read_text(encoding="utf-8"))
    qualified = json.loads(WPLTO.read_text(encoding="utf-8"))
    first_red = json.loads(HARDWARE_FIRST_RED.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    profile = LINK42.PROFILE.check()
    LINK.require(
        baseline["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and baseline["link_number"] == 42
        and baseline["product_identity"]["product"]["sha256"] ==
            BASELINE_SHA,
        "Link-42 rollback identity is not authoritative")
    LINK.require(
        qualified["status"] ==
            "passed-export-symbol-domain-WPLTO-artifact-only-replay"
        and qualified["real_353_row_plan_gate"]["accepted_real_rows"] == 353
        and qualified["real_353_row_plan_gate"]["negative_cases"] == 5
        and qualified["source_domain_gate"]["status"] ==
            "passed-one-canonical-symi-domain"
        and qualified["generated_source_domain_gate"]["status"] ==
            "passed-one-canonical-symi-domain"
        and qualified["final_island_identity_gate"]["mutation_cases"] == 11
        and qualified["aggregate_recovery"]["session_family_bytes"] ==
            EXPECTED_SESSION_BYTES
        and qualified["aggregate_recovery"]
            ["session_family_headroom_bytes"] == EXPECTED_SESSION_HEADROOM
        and qualified["product_shaped_wplto"]["fresh_gates"]["status"] ==
            "passed-artifact-only-complete-gate-replay",
        "export-symbol-domain WPLTO authority is not fully green")
    LINK.require(
        first_red["status"] == "first-red-product-semantic-review-required"
        and first_red["root_cause"]["rows_satisfying_symi"] == 353
        and first_red["root_cause"]["rows_satisfying_is_ptr"] == 0,
        "Link-42 hardware First Red is not the approved export-domain finding")
    LINK.require(
        contract["status"] ==
            "class-c-approved-export-symbol-domain-successor-link-and-line1-presmoke"
        and contract["scope"]["product_links_authorized"] == 1
        and contract["export_symbol_domain_successor_authorization"]
            ["line1_first_red_budget"] == "1/3 consumed; 2 remain"
        and contract["export_symbol_domain_successor_authorization"]
            ["latency_measurement_attempts"] == "0/2 consumed",
        "export-symbol-domain successor Class-C authority absent")
    return {
        "link42_rollback_product": LINK.bind(BASELINE),
        "link42_structural_authority": LINK.bind(BASELINE_RECEIPT),
        "export_symbol_domain_green_wplto": LINK.bind(WPLTO),
        "export_symbol_domain_contract_rebind": LINK.bind(CONTRACT_REBIND),
        "link42_export_symbol_hardware_first_red":
            LINK.bind(HARDWARE_FIRST_RED),
        "current_v6_direct_entry_authority":
            LINK.bind(LINK42.CURRENT_DIRECT.RECEIPT),
        "canonical_roots_fronts_product_profile": profile,
        "c2_lite_contract": LINK.bind(CONTRACT),
        "c2_lite_addendum": LINK.bind(ADDENDUM),
        "driver": LINK.bind(Path(__file__)),
    }


def fresh_real_plan_gate() -> dict[str, Any]:
    gate_out = OUT / "fresh-c2-lite-prelink-gates/export-symbol-domain"
    gate_out.mkdir(parents=True, exist_ok=True)
    LINK.require(
        LINK.sha(DOMAIN.REAL_PLAN) ==
            "06cb0990bc1eeacabef2d95432d64d93cc0f431a4179527a2b66c071cee9769d",
        "exact Link-42 export plan drift")
    binary = gate_out / "export-symbol-domain-host"
    command = [
        "cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-Isrc", str(DOMAIN.FIXTURE),
        "-o", str(binary)]
    subprocess.run(command, cwd=ROOT, check=True)
    run = subprocess.run(
        [str(binary), str(DOMAIN.REAL_PLAN)], cwd=ROOT,
        capture_output=True, text=True,
        env={**os.environ, "ASAN_OPTIONS": "detect_leaks=1",
             "UBSAN_OPTIONS": "halt_on_error=1"})
    stdout = gate_out / "export-symbol-domain-host.stdout.txt"
    stderr = gate_out / "export-symbol-domain-host.stderr.txt"
    stdout.write_text(run.stdout, encoding="utf-8")
    stderr.write_text(run.stderr, encoding="utf-8")
    LINK.require(
        run.returncode == 0
        and "PASS rows=353 foreign-domains-rejected=5" in run.stdout,
        "fresh exact 353-row export-domain matrix red")
    return {
        "status": "passed-fresh-real-link42-plan-and-foreign-domain-matrix",
        "accepted_real_rows": 353,
        "negative_cases": 5,
        "rejected_domains": ["heap-pointer", "NIL", "Fixnum", "BCODE",
                             "odd-damaged-SYMI"],
        "asan": "passed", "ubsan": "passed",
        "fixture": LINK.bind(DOMAIN.FIXTURE),
        "real_plan": LINK.bind(DOMAIN.REAL_PLAN),
        "binary": LINK.bind(binary), "stdout": LINK.bind(stdout),
        "stderr": LINK.bind(stderr),
    }


def main() -> int:
    LINK.require(not OUT.exists() and not RECEIPT.exists(),
                 "Link 43 is one-shot")
    old = {
        "out": LINK42.OUT, "receipt": LINK42.RECEIPT,
        "number": LINK42.LINK_NUMBER, "baseline": LINK42.BASELINE,
        "baseline_sha": LINK42.BASELINE_SHA,
        "baseline_receipt": LINK42.BASELINE_RECEIPT,
        "baseline_receipt_sha": LINK42.BASELINE_RECEIPT_SHA,
        "wplto": LINK42.WPLTO, "wplto_sha": LINK42.WPLTO_SHA,
        "hardware_first_red": LINK42.HARDWARE_FIRST_RED,
        "prerequisites": LINK42.prerequisites,
        "prelink": BASE_LINK.fresh_prelink_gates,
        "replacement": BASE_LINK.replacement_gates,
        "single_link": P.single_link,
    }

    def prelink() -> dict[str, Any]:
        value = old["prelink"]()
        value["export_symbol_domain_source"] = DOMAIN.source_domain_gate()
        value["export_symbol_domain_real_hardware_plan"] = (
            fresh_real_plan_gate())
        return value

    def replacement(product: Path, elf: Path,
                    host: dict[str, Any]) -> dict[str, Any]:
        value = old["replacement"](product, elf, host)
        generated = OUT / "generated-product-sources/c2_product_runtime.c"
        value["export_symbol_domain_generated_source"] = (
            DOMAIN.source_domain_gate(generated))
        return value

    def single_link(*args: Any, **kwargs: Any) -> Any:
        lines = tuple(
            line for line in kwargs.get("extra_contract_lines", ())
            if not line.startswith((
                "mode=", "source_baseline=",
                "final_island_wplto_authority_sha256=")))
        kwargs["extra_contract_lines"] = (
            "mode=link43-c2-lite-v6-export-symbol-domain",
            "source_baseline=link42-c2-lite-v6-final-island-identity",
            "export_symbol_domain=canonical-interned-SYMI-only",
            "export_symbol_domain_real_plan_rows=353",
            "export_symbol_domain_negative_cases=5",
            "export_symbol_domain_wplto_authority_sha256=" + WPLTO_SHA,
            "line1_first_red_budget=1-of-3-consumed",
            "latency_measurement_attempts=0-of-2-consumed",
            *lines)
        return old["single_link"](*args, **kwargs)

    try:
        LINK42.OUT = OUT
        LINK42.RECEIPT = RECEIPT
        LINK42.LINK_NUMBER = LINK_NUMBER
        LINK42.BASELINE = BASELINE
        LINK42.BASELINE_SHA = BASELINE_SHA
        LINK42.BASELINE_RECEIPT = BASELINE_RECEIPT
        LINK42.BASELINE_RECEIPT_SHA = BASELINE_RECEIPT_SHA
        LINK42.WPLTO = WPLTO
        LINK42.WPLTO_SHA = WPLTO_SHA
        LINK42.HARDWARE_FIRST_RED = HARDWARE_FIRST_RED
        LINK42.prerequisites = prerequisites
        BASE_LINK.fresh_prelink_gates = prelink
        BASE_LINK.replacement_gates = replacement
        P.single_link = single_link
        result = LINK42.main()
    finally:
        LINK42.OUT = old["out"]
        LINK42.RECEIPT = old["receipt"]
        LINK42.LINK_NUMBER = old["number"]
        LINK42.BASELINE = old["baseline"]
        LINK42.BASELINE_SHA = old["baseline_sha"]
        LINK42.BASELINE_RECEIPT = old["baseline_receipt"]
        LINK42.BASELINE_RECEIPT_SHA = old["baseline_receipt_sha"]
        LINK42.WPLTO = old["wplto"]
        LINK42.WPLTO_SHA = old["wplto_sha"]
        LINK42.HARDWARE_FIRST_RED = old["hardware_first_red"]
        LINK42.prerequisites = old["prerequisites"]
        BASE_LINK.fresh_prelink_gates = old["prelink"]
        BASE_LINK.replacement_gates = old["replacement"]
        P.single_link = old["single_link"]
    if result == 0:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        LINK.require(receipt["link_number"] == LINK_NUMBER,
                     "Link-43 receipt number drift")
        print("c2-lite-v6-export-symbol-domain-successor-link: PASS "
              f"product={receipt['product_identity']['product']['sha256']} "
              "budget=1/3 latency=0/2")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
