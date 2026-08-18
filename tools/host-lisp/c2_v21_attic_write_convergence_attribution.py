#!/usr/bin/env python3
"""Attribute and price the cold-stager Attic write/readback boundary.

The stopped breadcrumb proves that the first role-4 sector did not pass the
combined write/readback comparison in 192 raster wraps.  It does not identify
which half failed: the initial Enhanced-DMA submission chains both halves, and
every retry submits only the Attic-to-Bank-0 readback descriptor.  This desk
gate binds that exact implementation and prices a poison-first experiment
whose observer is the independently proven MAP CPU path.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
STAGER = ROOT / "scripts/r3-cold-stager-main.c"
BREADCRUMB = ARCH / (
    "c2.3-v2.1-loading-libraries-stage-breadcrumb-contact-receipt.json")
MAP_RESULT = ARCH / (
    "c2.3-v2.0-loading-libraries-progress-map-device-receipt.json")
L10 = ARCH / "c2.2-v1.2.4-phase-m-hardware-receipt.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-attic-write-convergence-attribution-receipt.json")
DRIVER = Path(__file__).resolve()

AUTHORIZATION = "b83f419e"
FORMAT = "lisp65-c2.3-v2.1-attic-write-convergence-attribution-v1"
RECORDED_ON = "2026-08-15"
SECTOR_BYTES = 254
TIMEOUT_WRAPS = 192
ROLE4_BYTES = 65423


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in ("attic write-convergence finding",
                  "poison-first verification", "product-liveness ordinal",
                  "diagnostic staging path is retired"):
        require(token in text, f"attribution authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": digest(raw)}


def implementation(source: str | None = None) -> dict[str, Any]:
    text = STAGER.read_text(encoding="utf-8") if source is None else source
    initial = text[text.index("static void c2_attic_stage_copy_readback("):
                   text.index("static void c2_attic_retry_readback(void)")]
    retry = text[text.index("static void c2_attic_retry_readback(void)"):
                 text.index("enum c2_stage_domain")]
    loop = text[text.index("for (poll = 0; poll < count; poll++)"):
                text.index("#ifdef LISP65_G5_IO_TRIGGER_PROBE", text.index(
                    "for (poll = 0; poll < count; poll++)"))]
    flat_initial = " ".join(initial.split())
    require(
        "c2_attic_stage_jobs[0]" in initial
        and "src, dst" in initial
        and "DMA_COPY_CMD | R3_DMA_CHAIN" in initial
        and "c2_attic_stage_jobs[1]" in initial
        and "dst, readback" in initial
        and "&c2_attic_retry_job, dst, readback, count, DMA_COPY_CMD" in flat_initial
        and "mos16lo(c2_attic_retry_job)" in retry
        and "c2_attic_stage_jobs" not in retry
        and "c2_target_readback[poll] = 0xa5u" in loop
        and "c2_target_readback[poll] != sector_payload[poll]" in loop
        and "c2_attic_retry_readback();" in loop,
        "cold-stager Attic write/readback structure drift")
    return {
        "initial_submission": {
            "descriptor_0": "Bank-0 sector_payload -> 28-bit Attic target",
            "descriptor_1": "same Attic target -> Bank-0 readback",
            "relationship": "one Enhanced-DMA chain"},
        "retry_submission": "Attic target -> Bank-0 readback only",
        "poisoned_before_submission": "Bank-0 readback buffer only (0xA5)",
        "not_poisoned": "Attic target",
        "comparison": "Bank-0 readback bytes == sector_payload bytes",
        "causal_limit": (
            "one timeout proves the combined write/readback boundary only; "
            "a pass can also consume matching pre-existing Attic bytes")}


def evidence() -> dict[str, Any]:
    crumb = load(BREADCRUMB)
    map_result = load(MAP_RESULT)
    l10 = load(L10)
    row = crumb.get("breadcrumb", {})
    probe = map_result.get("probe", {})
    captures = l10.get("M2_L10", {}).get("captures", [])
    require(
        crumb.get("status") == "BREADCRUMB-COMMITTED"
        and row.get("reason", {}).get("meaning") == "convergence-timeout"
        and row.get("role") == 4 and row.get("sector_ordinal") == 0
        and row.get("destination") == "0x08000000"
        and row.get("completed_length") == 0
        and row.get("expected_length") == ROLE4_BYTES
        and row.get("running_crc") == "0xffffffff"
        and row.get("wraps") == TIMEOUT_WRAPS
        and probe.get("decision") == "MAP-CPU-BANK5-AND-ATTIC-TARGET-GREEN"
        and probe.get("attic") == "PASS"
        and any(row.get("elapsed_after_launch_ms") == 714
                and row.get("matches_expected") is True for row in captures),
        "Attic convergence evidence drift")
    return {
        "breadcrumb": bind(BREADCRUMB),
        "observed_boundary": {
            "role": 4, "sector_ordinal": 0, "destination": "0x08000000",
            "payload_bytes_committed": 0, "timeout_wraps": TIMEOUT_WRAPS,
            "running_crc": "0xffffffff"},
        "independent_observer": {
            "receipt": bind(MAP_RESULT),
            "fact": "MAP CPU reads of Attic base passed 256 repeated reads"},
        "historical_L10": {
            "receipt": bind(L10), "known_convergence_point_ms": 714,
            "scope": "read-side historical evidence; not a write-side attribution"}}


def pricing() -> dict[str, Any]:
    sectors = math.ceil(ROLE4_BYTES / SECTOR_BYTES)
    require(sectors == 258, "role-4 sector price drift")
    return {
        "role4": {"bytes": ROLE4_BYTES, "logical_sectors": sectors,
                  "maximum_sector_bytes": SECTOR_BYTES},
        "current_success_floor": {
            "enhanced_DMA_jobs_per_sector": 2,
            "role4_jobs": sectors * 2,
            "note": "one write plus one chained D705 readback; retries excluded"},
        "causal_poison_first_product_protocol": {
            "per_sector": [
                "fill existing 254-byte Bank-0 readback buffer with bytewise "
                "complement of this sector payload",
                "D705-write poison to the exact Attic destination",
                "MAP-CPU-read the exact destination until every poison byte is visible",
                "D705-write payload to the exact Attic destination",
                "MAP-CPU-read until every payload byte is visible"],
            "enhanced_DMA_jobs_per_sector": 2,
            "role4_jobs": sectors * 2,
            "extra_DMA_jobs_vs_success_floor": 0,
            "CPU_bytes_compared_per_successful_sector": 2 * SECTOR_BYTES,
            "role4_CPU_byte_comparisons_floor": 2 * ROLE4_BYTES,
            "new_static_buffer_bytes": 0,
            "why_causal": (
                "the complement differs at every byte, so payload acceptance "
                "cannot be satisfied by target history")},
        "one_contact_attribution_extension": {
            "after_payload_MAP_success": (
                "submit the legacy Attic-to-Bank-0 readback once and retain both "
                "observer results"),
            "decision_table": {
                "poison_never_seen_by_MAP": "Attic write-side failure",
                "poison_seen_payload_never_seen_by_MAP": "payload write-side failure",
                "payload_seen_by_MAP_legacy_readback_mismatch": "D705 readback visibility failure",
                "payload_seen_by_both": "intermittent boundary did not reproduce"},
            "additional_DMA_jobs_per_sector_when_enabled": 1,
            "scope": "evidence option only; not required by the product protocol"},
        "timeout": {
            "standing_bound_wraps_per_stage": TIMEOUT_WRAPS,
            "must_be_separately_repriced": True,
            "reason": "714 ms is read evidence and cannot price a cold Attic write"}}


def derive() -> dict[str, Any]:
    value = {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "HOST-ATTRIBUTED-COMBINED-BOUNDARY; POISON-FIRST-PRICED",
        "authority": authority(),
        "inputs": {"stager": bind(STAGER), "driver": bind(DRIVER)},
        "implementation": implementation(), "evidence": evidence(),
        "price": pricing(),
        "decision": {
            "current_evidence": "WRITE-VS-READBACK-UNDECIDED",
            "product_relevance": True,
            "next_target_evidence": "separately authorized poison/MAP/legacy-readback row",
            "ordinary_product_passes_exonerate_write": False},
        "permanent_rule": (
            "A matching target comparison proves an effective write only after "
            "a distinguishing target precondition has itself been observed."),
        "claim_limit": (
            "Desk attribution and price only; no stager fix, product card, medium "
            "or device contact is authorized by this receipt.")}
    value["mutations"] = mutations(value)
    audit(value)
    return value


def audit(value: dict[str, Any]) -> None:
    price = value.get("price", {})
    protocol = price.get("causal_poison_first_product_protocol", {})
    steps = protocol.get("per_sector", [])
    require(
        value.get("status") ==
            "HOST-ATTRIBUTED-COMBINED-BOUNDARY; POISON-FIRST-PRICED"
        and value.get("decision", {}).get("current_evidence") ==
            "WRITE-VS-READBACK-UNDECIDED"
        and value.get("decision", {}).get("product_relevance") is True
        and value.get("decision", {}).get(
            "ordinary_product_passes_exonerate_write") is False
        and protocol.get("extra_DMA_jobs_vs_success_floor") == 0
        and protocol.get("new_static_buffer_bytes") == 0
        and protocol.get("role4_CPU_byte_comparisons_floor") == 130846
        and len(steps) == 5
        and "complement" in steps[0]
        and "every poison byte is visible" in steps[2]
        and "complement differs at every byte" in protocol.get("why_causal", "")
        and price.get("timeout", {}).get("must_be_separately_repriced") is True
        and value.get("claim_limit", "").startswith("Desk attribution"),
        "Attic write attribution receipt drift")


def mutations(base: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-write-convicted": lambda x: x["decision"].update(
            current_evidence="WRITE-SIDE-CONVICTED"),
        "exonerate-from-old-pass": lambda x: x["decision"].update(
            ordinary_product_passes_exonerate_write=True),
        "drop-product-relevance": lambda x: x["decision"].update(
            product_relevance=False),
        "poison-only-readback": lambda x: x["price"][
            "causal_poison_first_product_protocol"].update(
                why_causal="Bank-0 readback was poisoned"),
        "skip-poison-observation": lambda x: x["price"][
            "causal_poison_first_product_protocol"]["per_sector"].pop(2),
        "reuse-source-as-poison": lambda x: x["price"][
            "causal_poison_first_product_protocol"].update(
                role4_CPU_byte_comparisons_floor=ROLE4_BYTES),
        "invent-write-timeout-price": lambda x: x["price"]["timeout"].update(
            must_be_separately_repriced=False),
        "authorize-device": lambda x: x.update(
            claim_limit="Device contact authorized."),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(base); mutate(candidate)
        try:
            audit(candidate)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "Attic attribution mutation survived")
    return rejected


def source_mutations() -> list[str]:
    source = STAGER.read_text(encoding="utf-8")
    cases = {
        "retry-resubmits-write": source.replace(
            "c2_edma_prepare(\n        &c2_attic_retry_job, dst, readback, count, DMA_COPY_CMD);",
            "c2_edma_prepare(\n        &c2_attic_retry_job, src, dst, count, DMA_COPY_CMD);", 1),
        "no-chained-readback": source.replace(
            "&c2_attic_stage_jobs[0], src, dst, count,\n"
            "                    DMA_COPY_CMD | R3_DMA_CHAIN",
            "&c2_attic_stage_jobs[0], src, dst, count,\n"
            "                    DMA_COPY_CMD", 1),
        "no-readback-poison": source.replace(
            "c2_target_readback[poll] = 0xa5u;",
            "c2_target_readback[poll] = sector_payload[poll];", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            implementation(candidate)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "Attic source mutation survived")
    return rejected


def write() -> None:
    value = derive()
    value["source_mutations"] = source_mutations()
    RECEIPT.write_bytes(canonical(value))
    print("Attic write convergence: PASS combined-boundary poison-first-priced")


def check() -> None:
    value = derive()
    value["source_mutations"] = source_mutations()
    require(load(RECEIPT) == value, "Attic attribution receipt stale")
    print("Attic write convergence check: PASS mutations=8+3")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "check"
    if action == "write": write()
    elif action == "check": check()
    elif action == "selftest":
        value = derive(); require(len(value["mutations"]) == 8, "mutation drift")
        require(len(source_mutations()) == 3, "source mutation drift")
        print("Attic write convergence selftest: PASS mutations=8+3")
    else:
        raise AttributionError(f"unknown action: {action}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AttributionError as error:
        print(f"Attic write convergence: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
