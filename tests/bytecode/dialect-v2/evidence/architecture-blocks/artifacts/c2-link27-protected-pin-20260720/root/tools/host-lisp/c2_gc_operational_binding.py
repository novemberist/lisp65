#!/usr/bin/env python3
"""Verify the product GC binding without turning the stress schedule into policy."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


ROOT_KINDS = {3, 7}


def u16(data: bytes, offset: int) -> int:
    return data[offset] | data[offset + 1] << 8


def u24(data: bytes, offset: int) -> int:
    return u16(data, offset) | data[offset + 2] << 16


def function_body(source: str, name: str) -> str:
    match = re.search(rf"\b{name}\s*\([^)]*\)\s*\{{", source)
    if not match:
        raise ValueError(f"missing function {name}")
    start = match.end()
    depth = 1
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index]
    raise ValueError(f"unterminated function {name}")


def descriptor_counts(shelf: bytes) -> tuple[int, int, dict[int, int]]:
    if shelf[:4] != b"L65S" or shelf[4] != 4 or shelf[5] != 32:
        raise ValueError("not the approved L65S-v4 shelf")
    images = shelf[7]
    entries = 0
    counts: dict[int, int] = {}
    for image in range(images):
        record = shelf[32 + image * 32:64 + image * 32]
        metadata = u24(record, 13)
        if metadata + 24 > len(shelf) or shelf[metadata:metadata + 4] != b"C2I\0":
            raise ValueError(f"image {image} metadata envelope is invalid")
        entry_count = u16(shelf, metadata + 10)
        literal_count = u16(shelf, metadata + 12)
        literals = u16(shelf, metadata + 16)
        entries += entry_count
        for local in range(literal_count):
            kind = shelf[metadata + literals + local * 8]
            counts[kind] = counts.get(kind, 0) + 1
    return images, entries, counts


def check_source(source: str) -> None:
    checkpoint = function_body(source, "c2_stream_gc_checkpoint")
    scanner = function_body(source, "c2_product_gc_mark_roots")
    if "c2_pending_roots = root_count" not in checkpoint:
        raise ValueError("checkpoint does not publish the pending root span")
    if "c2_facade_gc_collect" in checkpoint:
        raise ValueError("product checkpoint still forces the host stress schedule")
    if "C2_KERNAL_RESIDENT void c2_product_gc_mark_roots" not in source:
        raise ValueError("canonical root walker is not in the owned C2 window")
    required_scan = (
        "uint8_t b[32]",
        "while (done < scan)",
        "n * 2u",
        "c2_facade_gc_mark",
        "done = (uint16_t)(done + n)",
    )
    if any(item not in scanner for item in required_scan):
        raise ValueError("canonical roots are not scanned in bounded 32-byte blocks")
    if re.search(r"(?<!facade_)\bgc_mark\s*\(", scanner):
        raise ValueError("owned root walker bypasses the fixed gc_mark facade")


def mutation_selftest(source: str) -> int:
    mutations = []
    mutations.append(source.replace(
        "c2_pending_roots = root_count;",
        "c2_pending_roots = root_count; c2_facade_gc_collect();",
        1,
    ))
    mutations.append(source.replace("uint8_t b[32];", "uint8_t b[4];", 1))
    mutations.append(source.replace(
        "C2_KERNAL_RESIDENT void c2_product_gc_mark_roots",
        "void c2_product_gc_mark_roots", 1))
    mutations.append(source.replace(
        "c2_facade_gc_mark((obj)", "gc_mark((obj)", 1))
    rejected = 0
    for mutation in mutations:
        if mutation == source:
            raise ValueError("could not install operational-binding mutation")
        try:
            check_source(mutation)
        except ValueError:
            rejected += 1
    if rejected != len(mutations):
        raise ValueError("operational-binding mutation was accepted")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shelf", type=Path, required=True)
    parser.add_argument("--c2d", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()

    shelf = args.shelf.read_bytes()
    c2d = args.c2d.read_bytes()
    source = args.source.read_text(encoding="utf-8")
    images, entries, kinds = descriptor_counts(shelf)
    if c2d[:4] != b"C2D\0" or c2d[4] != 3:
        raise ValueError("not the product C2D-v3 plane")
    roots = kinds.get(3, 0) + kinds.get(7, 0)
    if roots != u16(c2d, 24):
        raise ValueError("descriptor census and C2D root count diverge")
    check_source(source)
    mutations = mutation_selftest(source)

    block_values = 32 // 2
    reads_per_collection = (roots + block_values - 1) // block_values
    old_forced_reads = roots * roots
    result = {
        "format": "lisp65-c2-gc-operational-binding-probe-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-host-probe-only",
        "inputs": {
            "shelf": str(args.shelf),
            "shelf_sha256": hashlib.sha256(shelf).hexdigest(),
            "c2d": str(args.c2d),
            "c2d_sha256": hashlib.sha256(c2d).hexdigest(),
            "source": str(args.source),
            "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        },
        "measured": {
            "images": images,
            "entries": entries,
            "resolutions": sum(kinds.values()),
            "kind_counts": {str(key): value for key, value in sorted(kinds.items())},
            "canonical_roots": roots,
            "allocation_checkpoints": roots,
            "old_forced_collections": roots,
            "old_minimum_two_byte_root_dma_reads": old_forced_reads,
            "root_scan_block_bytes": 32,
            "root_dma_reads_per_natural_collection": reads_per_collection,
        },
        "contract_binding": {
            "product_checkpoint": "publish pending-root span; do not force the proof stress schedule",
            "host_stress": f"retains one simulated collection after each of {roots} root publications",
            "natural_gc": "marks every previously published canonical root before any later allocation",
            "collector": "non-moving; no root writeback",
        },
        "mutation_tests": {
            "forced_collection_reintroduced": "rejected",
            "two_word_scan_buffer_reintroduced": "rejected",
            "root_walker_returned_to_bank0": "rejected",
            "fixed_gc_mark_facade_bypassed": "rejected",
            "count": mutations,
        },
        "capacity": "not-linked-not-measured",
        "hardware": "not-run-not-passed",
        "claim_limit": "Host-only operational-binding and transfer-count probe. It authorizes no product link, capacity debit, hardware acceptance or promotion claim.",
    }
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        "c2-gc-operational-binding: PASS "
        f"roots={roots} forced-root-reads={old_forced_reads}->0 "
        f"natural-scan-reads={roots}->{reads_per_collection} "
        f"mutations={mutations}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
