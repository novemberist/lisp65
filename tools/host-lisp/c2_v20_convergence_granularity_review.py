#!/usr/bin/env python3
"""Review Link-106 read-convergence granularity from bound artifacts.

This is a desk-only classifier.  It distinguishes authentication of the
immutable source from convergence of each later DMA destination.  A source
CRC may amortize identity work, but it cannot make a future, independently
stale destination copy trustworthy unless that verified destination is kept
and consumed or the transport itself is synchronous.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
PRICING = ARCH / "c2.3-v2.0-loading-libraries-duration-pricing-receipt.json"
CONVERGENCE = ROOT / "config/c2-f018b-content-safe-read-contract.json"
OVERLAY = ROOT / "config/c2-runtime-overlay-dma-completion-contract.json"
WRITE_REVIEW = ROOT / "docs/planning/c2.2-cpu-chip-write-completion-granularity-review.md"
PARKED = ROOT / "docs/reference/parked-items-register.md"
PHASE_SCRATCH = ROOT / "src/c2_phase_scratch.h"
MAPPED = ROOT / "src/c2_mapped_far_convergence.s"
RECEIPT = ARCH / "c2.3-v2.0-convergence-granularity-review-receipt.json"
DRIVER = Path(__file__).resolve()

AUTHORIZATION = "09144cb8"
RECORDED_ON = "2026-08-14"
FORMAT = "lisp65-c2.3-v2.0-convergence-granularity-review-v1"
BUILD = ROOT / "build/c2.3/v2.0-phase02b-header-consumption-replacement-card"
SHELF = BUILD / "static-plane/narrow-static/product/product-shelf-v4-direct.bin"
C2D = BUILD / "static-plane/narrow-static/v6-semantics/initial.c2d-v6.bin"
RUNTIME = BUILD / "wplto/generated-product-sources/c2_product_runtime.c"
DECODER = BUILD / "wplto/generated-product-sources/c2-stream-decoder.c"


class ReviewError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReviewError(message)


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


def git_authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    text = " ".join(raw.decode().split()).lower()
    require("convergence granularity commissioned" in text
            and "346,298" in text
            and "coarser granularity at equal safety" in text
            and "progress-ring instrument stays unbuilt" in text,
            "granularity-review authority drift")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def u16(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset:offset + 2], "little")


def u24(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset:offset + 3], "little")


def u32(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset:offset + 4], "little")


def crc_domains() -> dict[str, Any]:
    shelf = SHELF.read_bytes()
    c2d = C2D.read_bytes()
    require(len(shelf) == 93681 and shelf[:7] == b"L65S\x04\x20\x20",
            "Shelf identity/shape drift")
    require(len(c2d) == 33840 and c2d[:8] == b"C2D\0\x06\x30\x20\x0a",
            "C2D identity/shape drift")
    images: list[dict[str, int]] = []
    string_records: list[dict[int, int]] = []
    catalog_bytes = u16(shelf, 16)
    require(catalog_bytes == 192
            and zlib.crc32(shelf[32:32 + catalog_bytes]) == u32(shelf, 18),
            "Shelf catalog CRC drift")
    for ordinal in range(6):
        row = shelf[32 + ordinal * 32:64 + ordinal * 32]
        code = u24(row, 8); code_bytes = u16(row, 11)
        metadata = u24(row, 13); metadata_bytes = u16(row, 16)
        code_raw = shelf[code:code + code_bytes]
        metadata_raw = shelf[metadata:metadata + metadata_bytes]
        require(zlib.crc32(code_raw) == u32(row, 18),
                f"image {ordinal} code CRC drift")
        require(zlib.crc32(metadata_raw) == u32(row, 22),
                f"image {ordinal} metadata CRC drift")
        require(zlib.crc32(code_raw + metadata_raw) == u32(row, 26),
                f"image {ordinal} pair CRC drift")
        header = metadata_raw[:24]
        pool_offset = u16(header, 18); pool_bytes = u16(header, 20)
        pool = metadata_raw[pool_offset:pool_offset + pool_bytes]
        records: dict[int, int] = {}
        cursor = 0
        while cursor < len(pool):
            length = u16(pool, cursor)
            require(cursor + 2 + length <= len(pool),
                    f"image {ordinal} string pool truncation")
            records[cursor] = length
            cursor += 2 + length
        require(cursor == len(pool), f"image {ordinal} string pool tail")
        images.append({
            "ordinal": ordinal, "code": code, "code_bytes": code_bytes,
            "metadata": metadata, "metadata_bytes": metadata_bytes,
            "entry_count": u16(header, 10),
            "descriptor_count": u16(header, 12),
            "entry_offset": u16(header, 14),
            "descriptor_offset": u16(header, 16),
            "pool_offset": pool_offset, "pool_bytes": pool_bytes,
        })
        string_records.append(records)
    require([i["code_bytes"] for i in images]
            == [17238, 13544, 2940, 4083, 104, 8134],
            "code span inventory drift")
    require([i["metadata_bytes"] for i in images]
            == [20262, 14368, 3152, 1814, 230, 7588],
            "metadata span inventory drift")
    return {
        "shelf": {
            "catalog_spans": 1, "code_spans": 6, "metadata_spans": 6,
            "combined_image_spans": 6,
            "runtime_crc_passes": 19,
            "maximum_code_plus_metadata_bytes": max(
                i["code_bytes"] + i["metadata_bytes"] for i in images),
            "maximum_metadata_bytes": max(i["metadata_bytes"] for i in images),
            "meaning": "source identity; not convergence of later DMA destinations",
        },
        "c2d": {
            "bytes": len(c2d), "initial_delivery_is_immutable": True,
            "becomes_mutable_during_decode": True,
            "write_calls": 4773, "write_bytes": 16550,
            "meaning": "a static whole-image CRC expires at the first target write",
        },
        "images": images,
        "string_records": string_records,
    }


def direct_offset_price(domains: dict[str, Any], workload: dict[str, Any]) -> dict[str, Any]:
    shelf = SHELF.read_bytes()
    images = domains["images"]
    records = domains["string_records"]
    named = named_chunks = kind3 = kind3_chunks = kind58 = kind58_chunks = 0
    for image, pool_records in zip(images, records):
        metadata = image["metadata"]
        for index in range(image["entry_count"]):
            entry = shelf[metadata + image["entry_offset"] + index * 16:
                          metadata + image["entry_offset"] + (index + 1) * 16]
            wanted = u16(entry, 8)
            if wanted != 0xffff:
                require(wanted in pool_records, "entry name offset is not a record boundary")
                named += 1
                named_chunks += math.ceil(pool_records[wanted] / 16)
        for index in range(image["descriptor_count"]):
            row = shelf[metadata + image["descriptor_offset"] + index * 8:
                        metadata + image["descriptor_offset"] + (index + 1) * 8]
            if row[0] not in (3, 5, 8):
                continue
            wanted = u24(row, 4)
            require(wanted in pool_records,
                    "descriptor name offset is not a record boundary")
            chunks = math.ceil(pool_records[wanted] / 16)
            if row[0] == 3:
                kind3 += 1; kind3_chunks += chunks
            else:
                kind58 += 1; kind58_chunks += chunks
    require((named, named_chunks, kind3, kind3_chunks, kind58, kind58_chunks)
            == (497, 650, 128, 133, 1510, 1865),
            "string-reference inventory drift")
    image_base = 6 + 6 + 2929
    replacements = {
        "06b": 6 + 6 + 755 + named + named_chunks,
        "09": image_base + kind3 + kind3_chunks,
        "10": image_base + kind58 + 2 * kind58_chunks,
    }
    current = {name: workload["decoder_by_phase"][name]["shelf"]["converged_calls"]
               for name in replacements}
    removed = sum(current.values()) - sum(replacements.values())
    aggregate = workload["standard_convergence_aggregate"]
    shelf_calls = aggregate["shelf_calls"] - removed
    shelf_bytes = aggregate["shelf_bytes"] - removed * 2
    calls = shelf_calls + aggregate["c2d_calls"]
    payload = shelf_bytes + aggregate["c2d_bytes"]
    require(removed == 297068 and shelf_calls == 41083 and shelf_bytes == 524117
            and calls == 49230 and payload == 586645,
            "direct-offset price drift")
    return {
        "kind": "delivery-bound-direct-string-offset",
        "safety_precondition": "the build gate proves every static entry/descriptor offset is a string-record boundary inside the CRC-authenticated metadata; dynamic Session images retain the scan",
        "changed_target_surface": "cold static decoder only",
        "current_calls_in_affected_phases": current,
        "replacement_calls_in_affected_phases": replacements,
        "shelf_calls_removed": removed,
        "shelf_call_reduction_percent": round(100.0 * removed / aggregate["shelf_calls"], 6),
        "after": {
            "converged_calls": calls, "payload_bytes": payload,
            "shelf_calls": shelf_calls, "shelf_bytes": shelf_bytes,
            "c2d_calls": aggregate["c2d_calls"],
            "c2d_bytes": aggregate["c2d_bytes"],
        },
        "verdict": "material algorithmic reduction, but not a convergence-granularity solution: every surviving destination DMA still needs proof",
    }


def cache_price(domains: dict[str, Any], timing: dict[str, Any]) -> dict[str, Any]:
    scratch = PHASE_SCRATCH.read_text(encoding="utf-8")
    require("#define LISP65_C2_PHASE_SCRATCH_BYTES 304u" in scratch,
            "phase-scratch size drift")
    block = 256
    shelf_blocks = math.ceil(SHELF.stat().st_size / block)
    c2d_blocks = math.ceil(C2D.stat().st_size / block)
    blocks = shelf_blocks + c2d_blocks
    table_bytes = blocks * 2
    frames = blocks * int(timing["authorities"]["timeout_frames"])
    seconds = frames / float(timing["authorities"]["frames_per_second"])
    require((shelf_blocks, c2d_blocks, blocks, table_bytes) == (366, 133, 499, 998),
            "block-cache lower-bound drift")
    return {
        "largest_power_of_two_line_that_could_fit_304_byte_scratch": block,
        "ownership_status": "capacity arithmetic only; the scratch lifetime is not granted by this review",
        "delivery_bound_crc16_table_bytes": table_bytes,
        "unique_blocks_best_case": {"Shelf": shelf_blocks, "initial_C2D": c2d_blocks,
                                     "total": blocks},
        "best_case_assumption": "each physical block is filled exactly once and remains available until its final consumer; no eviction or C2D write epoch",
        "formal_timeout_component_best_case": {
            "frames": frames, "seconds": round(seconds, 6),
            "minutes": round(seconds / 60.0, 6),
            "interpretation": "failure envelope, not expected duration",
        },
        "invalidating_facts": [
            "one 256-byte line cannot retain the 37,500-byte largest image",
            "the C2D plane becomes mutable through 4,773 writes, invalidating a static block oracle unless writer epochs are owned",
            "a block fill is safe only when the destination block CRC matches delivery-bound truth before any byte is consumed",
        ],
        "verdict": "equal-safety in principle, but not a phase/image amortization in the delivered ownership: it requires new cache state, oracle freight and mutable-epoch ownership",
    }


def policy_gate(policy: dict[str, Any]) -> None:
    require(not policy["accept_source_crc_as_future_dma_convergence"],
            "source CRC incorrectly promoted to future destination truth")
    require(not policy["accept_completion_signal"],
            "completion signal accepted as content truth")
    require(not policy["claim_cache_without_owned_destination"],
            "cache claim lacks a retained verified destination")
    require(not policy["reuse_static_crc_after_c2d_write"],
            "mutable C2D accepted under expired static CRC")
    require(not policy["transfer_two_byte_wall_cost"],
            "non-equivalent two-byte wall cost transferred")
    require(not policy["inherit_historical_45_seconds"],
            "historical boot observation promoted to current bound")
    require(policy["include_publication"], "publication omitted")
    require(policy["per_read_required_in_current_stateless_dma_api"],
            "delivered stateless DMA lost destination dominance")
    require(not policy["per_read_required_for_all_possible_architectures"],
            "current API result overclaimed as universal")
    require(policy["progress_ring_commissioned"],
            "structurally required branch did not commission progress ring")
    require(not policy["progress_ring_built"],
            "desk review silently built an instrument")
    require(not policy["device_contact_authorized"],
            "desk review silently authorized device contact")


def mutations(policy: dict[str, Any]) -> list[str]:
    cases = {
        "source-crc-frees-later-dma": ("accept_source_crc_as_future_dma_convergence", True),
        "completion-is-content": ("accept_completion_signal", True),
        "cache-without-owned-destination": ("claim_cache_without_owned_destination", True),
        "static-crc-survives-c2d-write": ("reuse_static_crc_after_c2d_write", True),
        "multiply-two-byte-wall-cost": ("transfer_two_byte_wall_cost", True),
        "inherit-old-45-second-window": ("inherit_historical_45_seconds", True),
        "omit-publication": ("include_publication", False),
        "drop-current-api-per-read-rule": ("per_read_required_in_current_stateless_dma_api", False),
        "overclaim-universal-per-read-rule": ("per_read_required_for_all_possible_architectures", True),
        "skip-progress-ring-commission": ("progress_ring_commissioned", False),
        "build-ring-in-desk-review": ("progress_ring_built", True),
        "authorize-contact-from-desk-review": ("device_contact_authorized", True),
    }
    rejected: list[str] = []
    for name, (key, value) in cases.items():
        candidate = deepcopy(policy); candidate[key] = value
        try:
            policy_gate(candidate)
        except ReviewError:
            rejected.append(name)
        else:
            raise ReviewError(f"mutation survived: {name}")
    require(len(rejected) == len(cases), "mutation count drift")
    return rejected


def build_receipt() -> dict[str, Any]:
    pricing = load(PRICING)
    require(pricing["format"]
            == "lisp65-c2.3-v2.0-loading-libraries-duration-pricing-v1",
            "pricing receipt format drift")
    workload = pricing["workload"]
    aggregate = workload["standard_convergence_aggregate"]
    require(aggregate["converged_calls"] == 346298
            and aggregate["payload_bytes"] == 1180781
            and aggregate["c2d_write_calls"] == 4773,
            "pricing aggregate drift")
    mapped = MAPPED.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    decoder = DECODER.read_text(encoding="utf-8")
    require(all(token in mapped for token in (
        ".Lc2_d700_source_byte:", ".Lc2_d700_probe_wait:",
        ".Lc2_d700_primary:", ".Lc2_d705_source_byte:",
        ".Lc2_d705_probe_wait:", ".Lc2_d705_primary:")),
        "mapped verifier structure drift")
    require("return c2_physical_read_converged(base + offset" in runtime
            and "return vm_code_load_converged(" in runtime,
            "every standard read no longer uses convergence")
    require("shelf_crc32_pair" in decoder and "c2_ready = 1;" in runtime,
            "CRC/publication dominance drift")

    calls = aggregate["converged_calls"]
    payload = aggregate["payload_bytes"]
    source_probe_jobs = 2 * payload
    primary_upper = calls
    raw_jobs = calls
    require(source_probe_jobs == 2361562 and primary_upper == 346298,
            "delivered job arithmetic drift")
    domains = crc_domains()
    direct = direct_offset_price(domains, workload)
    cache = cache_price(domains, pricing["timing"])
    direct_frames = ((direct["after"]["payload_bytes"]
                      + direct["after"]["converged_calls"])
                     * pricing["timing"]["authorities"]["timeout_frames"])
    direct_seconds = direct_frames / pricing["timing"]["authorities"]["frames_per_second"]

    parked = PARKED.read_text(encoding="utf-8")
    require("CPU-side Attic transport via 28-bit addressing" in parked
            and "2-KB window prices at well under 1 ms" in parked,
            "parked synchronous-transport successor drift")
    write_review = WRITE_REVIEW.read_text(encoding="utf-8")
    require("two shared data barriers plus two journal bookends" in write_review,
            "transaction-boundary precedent drift")

    policy = {
        "accept_source_crc_as_future_dma_convergence": False,
        "accept_completion_signal": False,
        "claim_cache_without_owned_destination": False,
        "reuse_static_crc_after_c2d_write": False,
        "transfer_two_byte_wall_cost": False,
        "inherit_historical_45_seconds": False,
        "include_publication": True,
        "per_read_required_in_current_stateless_dma_api": True,
        "per_read_required_for_all_possible_architectures": False,
        "progress_ring_commissioned": True,
        "progress_ring_built": False,
        "device_contact_authorized": False,
    }
    policy_gate(policy)
    rejected = mutations(policy)

    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "PER-READ-STRUCTURALLY-REQUIRED-IN-DELIVERED-DMA-API; PROGRESS-RING-COMMISSIONED",
        "authority": {
            "commission": git_authority(), "pricing": bind(PRICING),
            "Shelf": bind(SHELF), "C2D": bind(C2D),
            "runtime": bind(RUNTIME), "decoder": bind(DECODER),
            "mapped_convergence": bind(MAPPED),
            "convergence_contract": bind(CONVERGENCE),
            "object_convergence_precedent": bind(OVERLAY),
            "write_granularity_precedent": bind(WRITE_REVIEW),
            "phase_scratch": bind(PHASE_SCRATCH),
            "parked_transport_successor": bind(PARKED), "driver": bind(DRIVER),
        },
        "delivered_unit": {
            "logical_reads": calls, "payload_bytes": payload,
            "average_payload_bytes_per_read": round(payload / calls, 6),
            "source_probe_jobs_per_payload_byte": 2,
            "source_probe_dma_jobs": source_probe_jobs,
            "possible_primary_dma_jobs": primary_upper,
            "naked_read_dma_jobs": raw_jobs,
            "minimum_job_count_multiple_vs_naked_reads": round(source_probe_jobs / raw_jobs, 6),
            "maximum_job_count_multiple_vs_naked_reads": round((source_probe_jobs + primary_upper) / raw_jobs, 6),
            "two_byte_example": {
                "naked": "one two-byte DMA job",
                "delivered_verifier": "four one-byte probe/marker jobs plus compare, and at most one primary job",
            },
            "bounded_waits": "one 64-frame wait around every source-byte probe; an additional 64-frame wait is possible once per logical read",
        },
        "steady_state_cost_comparison": {
        "measured_reference": "<20 us per two-byte vm_dma symbol read",
        "path_equivalence": False,
        "wall_time_ratio_claim": None,
        "structural_result": "the verifier performs at least 6.81945 DMA jobs per naked logical read before CPU compare/poll work; verification work dominates submission count even when no primary copy is needed",
        },
        "source_identity_domains": {
            "shelf": domains["shelf"], "c2d": domains["c2d"],
        },
        "equal_safety_test": {
            "rejected_proposal": "verify a source image/span once, then keep using ordinary stateless DMA reads",
            "why": "the CRC authenticates the immutable source, while F018B staleness occurs independently in each later destination copy; the proof does not dominate the bytes consumed",
            "minimum_valid_shapes": [
                "retain an authenticated destination cache and serve every consumer from it until invalidation",
                "use a synchronous CPU-visible transport, retaining existing source/object CRC checks for identity",
            ],
            "mutable_rule": "C2D cache truth is epoch-scoped; every target write must update synchronously or invalidate/re-prove the affected span",
        },
        "priced_alternatives": {
            "direct_static_string_offsets": {
                **direct,
                "formal_remaining_envelope": {
                    "frames": direct_frames, "seconds": round(direct_seconds, 6),
                    "days": round(direct_seconds / 86400.0, 6),
                    "interpretation": "formal failure envelope, not expected duration",
                },
            },
            "authenticated_256_byte_cache": cache,
            "whole_image_cache": {
                "largest_image_code_plus_metadata_bytes": domains["shelf"]["maximum_code_plus_metadata_bytes"],
                "largest_metadata_bytes": domains["shelf"]["maximum_metadata_bytes"],
                "owned_phase_scratch_bytes": 304,
                "fit": False,
                "verdict": "image/span granularity requires new owned storage or a synchronous mapped view",
            },
            "synchronous_cpu_transport_successor": {
                "existing_planning_price": "2 KiB CPU-side Attic copy well under 1 ms at 40 MHz",
                "status_for_link106": "not proved for Attic plus Bank-5 target domains; the accepted Link-106 contract explicitly rejected unproved flat CPU transport",
                "role": "separately commissionable architecture successor, not evidence that the delivered DMA API can coarsen safely",
            },
        },
        "decision": {
            "commission_exit": "PER-READ-STRUCTURALLY-REQUIRED-IN-CURRENT-STATELESS-DMA-API",
            "global_architecture_claim": False,
            "current_boot_expected_seconds": None,
            "reason_no_expected_duration": "the structurally-required branch of the commission applies; the exact verifier path has no transferable steady-state wall-cost measurement",
            "product_hang_claim": False,
            "product_correctness_claim": False,
            "product_facing_performance_item": True,
            "wait_only_repeat_authorized": False,
            "next_contact_authorized": False,
            "required_next_step": "host-build and qualify the already specified target-owned phase/ordinal progress ring, then return for contact authorization",
        },
        "progress_ring_commission": {
            "identity": "non-promotable diagnostic sibling; zero product-byte claim",
            "monotonic_value": "32-bit count of successfully completed standard convergence reads",
            "location_tuple": ["decoder phase", "image", "entry-or-descriptor ordinal", "publication ordinal"],
            "producer": "target-side only; no monitor, screenshot or host read while LOADING LIBRARIES is active",
            "sampling": "four commit-last target-owned ring slots at frame-separated times; one final stop and raw-first mapping-correct readback",
            "preconditions": [
                "owned slots outside every boot-active owner and ownership-validated region",
                "32-bit no-ABA proof over the full horizon",
                "sampler cannot enter monitor, stop CPU or invoke the fail-closed observation path",
                "phase/ordinal and counter commit atomically enough for the reader's seqlock rule",
            ],
            "decision_rows": {
                "growing": "live; derive the exact candidate read rate and completion estimate",
                "fixed": "loop/stall; phase and ordinal name the neighborhood",
                "reaches_ready": "boot healthy; close D1 and continue D2-D5",
            },
            "built": False, "contact_authorized": False,
        },
        "policy": policy,
        "mutations_rejected": rejected,
        "claim_limit": "Desk-only granularity review. It proves per-read destination proof is structurally required by the delivered stateless DMA API, not by every possible architecture. It commissions but does not build the progress ring, authorizes no device contact or product/media change, supplies no mean boot-time claim, and leaves D1/D2-D5 closed.",
    }


def main() -> int:
    try:
        receipt = build_receipt()
        encoded = canonical(receipt)
        if len(sys.argv) == 2 and sys.argv[1] == "--check":
            require(RECEIPT.is_file() and RECEIPT.read_bytes() == encoded,
                    "stored granularity-review receipt drift")
        elif len(sys.argv) == 1:
            RECEIPT.write_bytes(encoded)
        else:
            raise ReviewError("usage: c2_v20_convergence_granularity_review.py [--check]")
        print("c2-v20-convergence-granularity-review: PASS")
        print("delivered verifier: 2361562 source-probe jobs / 346298 logical reads")
        print("decision: per-read required in current stateless DMA API")
        print("next: progress ring commissioned; no contact authorized")
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError,
            ReviewError) as error:
        print(f"c2-v20-convergence-granularity-review: FAIL: {error}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
