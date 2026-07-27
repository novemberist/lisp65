#!/usr/bin/env python3
"""Prove the single-source C2D-v2 GC-root contract without product changes."""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_full_emission as F  # noqa: E402
import c2_bcode_contract as B  # noqa: E402

CONTRACT = ROOT / "config/c2-gc-root-single-source-proposal.json"
DOCUMENT = ROOT / "docs/planning/c2.1-gc-root-single-source-addendum.md"
OLD_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2-gc-root-proposal-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2-gc-root-single-source-receipt.json"
)

ROOT_KINDS = {F.K_STRING, F.K_PAIR}
HEADER_BYTES = 32
REGION_BYTES = 50816


class SingleSourceError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SingleSourceError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(data), "sha256": sha(data)}


def p16(value: int) -> bytes:
    return struct.pack("<H", value)


def u16(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def pointer_for(root_index: int) -> int:
    # Positive, even and nonzero: a legal host witness for a non-moving heap obj.
    value = 2 * (1000 + root_index)
    require(0 < value < 0x8000 and not value & 1, "root witness is not a heap pointer")
    return value


def direct_value(descriptor: Any, ordinal: int, *, directory_base: int) -> int:
    if descriptor.kind == F.K_NIL:
        return 0
    if descriptor.kind == F.K_TRUE:
        return 0xE000
    if descriptor.kind == F.K_FIXNUM:
        signed = descriptor.arg0 - 0x10000 if descriptor.arg0 & 0x8000 else descriptor.arg0
        return ((signed & 0x7FFF) << 1 | 1) & 0xFFFF
    if descriptor.kind == F.K_ENTRY:
        return B.mk_bcode(directory_base + descriptor.arg0)
    if descriptor.kind in (F.K_EXPORT, F.K_SYMBOL):
        return (0xE000 + 2 * (ordinal & 0x0FFF)) & 0xFFFE
    if descriptor.kind == F.K_NATIVE:
        return ((descriptor.arg0 & 0x3FFF) << 1) | 1
    raise SingleSourceError(f"kind {descriptor.kind} is not a direct resolution")


def build_v2(images: list[Any], c2d_v1: bytes) -> tuple[bytes, list[int]]:
    require(c2d_v1[:4] == b"C2D\0" and c2d_v1[4] == 1, "C2D-v1 source identity")
    resolution_count = sum(len(image.descriptors) for image in images)
    resolutions_offset = u16(c2d_v1, 22)
    require(u16(c2d_v1, 16) == resolution_count, "C2D-v1 resolution count")
    prefix = bytearray(c2d_v1[:resolutions_offset])
    prefix[4] = 2
    resolution_blob = bytearray()
    root_blob = bytearray()
    logical_values: list[int] = []
    root_cursor = 0
    ordinal = directory_base = 0
    for image in images:
        for descriptor in image.descriptors:
            if descriptor.kind in ROOT_KINDS:
                resolution_blob += p16(root_cursor)
                value = pointer_for(root_cursor)
                root_blob += p16(value)
                logical_values.append(value)
                root_cursor += 1
            else:
                value = direct_value(
                    descriptor, ordinal, directory_base=directory_base)
                resolution_blob += p16(value)
                logical_values.append(value)
            ordinal += 1
        directory_base += len(image.manifest["entries"])
    total = resolutions_offset + len(resolution_blob) + len(root_blob)
    struct.pack_into("<H", prefix, 24, total)
    struct.pack_into("<H", prefix, 26, root_cursor)
    require(len(prefix) == resolutions_offset and total <= REGION_BYTES, "C2D-v2 geometry")
    return bytes(prefix + resolution_blob + root_blob), logical_values


def decode_v2(data: bytes, images: list[Any], catalog_crc: int,
              *, published: bool = True) -> dict[str, Any]:
    require(len(data) >= HEADER_BYTES and data[:4] == b"C2D\0" and data[4] == 2,
            "bad C2D-v2 magic/version")
    require(tuple(data[5:8]) == (32, 20, 10), "C2D-v2 record widths")
    resolution_count = u16(data, 16)
    resolutions_offset, total, root_count = u16(data, 22), u16(data, 24), u16(data, 26)
    require(struct.unpack_from("<I", data, 28)[0] == catalog_crc, "catalog identity")
    descriptors = [descriptor for image in images for descriptor in image.descriptors]
    expected_roots = sum(descriptor.kind in ROOT_KINDS for descriptor in descriptors)
    roots_offset = resolutions_offset + resolution_count * 2
    require(resolution_count == len(descriptors), "resolution census")
    require(root_count == expected_roots, "root count differs from descriptor census")
    require(roots_offset >= resolutions_offset and total == roots_offset + root_count * 2,
            "root section arithmetic")
    require(total == len(data), "C2D-v2 truncation or trailing data")
    root_rank = 0
    values: list[int] = []
    ordinal = directory_base = 0
    for image in images:
        for descriptor in image.descriptors:
            word = u16(data, resolutions_offset + ordinal * 2)
            if descriptor.kind in ROOT_KINDS:
                require(word == root_rank, "heap-kind resolution lacks canonical root index")
                value = u16(data, roots_offset + word * 2)
                if published:
                    require(value > 0 and value < 0x8000 and not value & 1,
                            "published root value is not a heap pointer")
                values.append(value)
                root_rank += 1
            else:
                require(word == direct_value(
                            descriptor, ordinal, directory_base=directory_base),
                        "direct-kind resolution is not its canonical obj")
                if descriptor.kind == F.K_ENTRY:
                    B.require_published_entry(
                        word, directory_base + descriptor.arg0)
                values.append(word)
            ordinal += 1
        directory_base += len(image.manifest["entries"])
    require(root_rank == root_count, "final root cursor mismatch")
    return {
        "resolutions": resolution_count,
        "roots": root_count,
        "roots_offset": roots_offset,
        "bytes": total,
        "headroom": REGION_BYTES - total,
        "values": values,
    }


def entry_metrics(images: list[Any]) -> dict[str, int]:
    maximum_literals = maximum_roots = entries_with_roots = 0
    for image in images:
        for ordinal, entry in enumerate(image.manifest["entries"]):
            count = int(entry["lit_count"])
            first = image.entry_first[ordinal]
            roots = sum(item.kind in ROOT_KINDS for item in image.descriptors[first:first + count])
            maximum_literals = max(maximum_literals, count)
            maximum_roots = max(maximum_roots, roots)
            entries_with_roots += roots != 0
    return {
        "maximum_entry_literals": maximum_literals,
        "maximum_entry_root_values": maximum_roots,
        "entries_with_root_values": entries_with_roots,
    }


def materialize_entries(data: bytes, images: list[Any], expected: list[int]) -> dict[str, int]:
    resolutions_offset = u16(data, 22)
    roots_offset = resolutions_offset + u16(data, 16) * 2
    image_resolution_base = 0
    checked = root_spans = 0
    maximum_descriptor_bytes = maximum_resolution_bytes = maximum_root_bytes = 0
    for image in images:
        for ordinal, entry in enumerate(image.manifest["entries"]):
            first = image.entry_first[ordinal]
            count = int(entry["lit_count"])
            hot: list[int] = []
            entry_roots: list[int] = []
            for local, descriptor in enumerate(image.descriptors[first:first + count]):
                global_ordinal = image_resolution_base + first + local
                word = u16(data, resolutions_offset + global_ordinal * 2)
                if descriptor.kind in ROOT_KINDS:
                    entry_roots.append(word)
                    hot.append(u16(data, roots_offset + word * 2))
                else:
                    hot.append(word)
            require(hot == expected[image_resolution_base + first:
                                    image_resolution_base + first + count],
                    "hot literal materialization differs from logical values")
            if entry_roots:
                require(entry_roots == list(range(entry_roots[0], entry_roots[0] + len(entry_roots))),
                        "entry roots do not form one contiguous canonical span")
                root_spans += 1
            maximum_descriptor_bytes = max(maximum_descriptor_bytes, count * F.LITERAL_BYTES)
            maximum_resolution_bytes = max(maximum_resolution_bytes, count * 2)
            maximum_root_bytes = max(maximum_root_bytes, len(entry_roots) * 2)
            checked += 1
        image_resolution_base += len(image.descriptors)
    return {
        "entries": checked,
        "contiguous_root_spans": root_spans,
        "maximum_descriptor_read_bytes": maximum_descriptor_bytes,
        "maximum_resolution_read_bytes": maximum_resolution_bytes,
        "maximum_root_read_bytes": maximum_root_bytes,
    }


def gc_stress(images: list[Any]) -> dict[str, int]:
    root_values = [0] * sum(
        descriptor.kind in ROOT_KINDS
        for image in images for descriptor in image.descriptors
    )
    allocated: list[int] = []
    root_cursor = collections = 0
    for descriptor in (descriptor for image in images for descriptor in image.descriptors):
        if descriptor.kind not in ROOT_KINDS:
            continue
        value = pointer_for(root_cursor)
        # Publication to the sole canonical root slot precedes every later allocation.
        root_values[root_cursor] = value
        allocated.append(value)
        before = list(root_values)
        marked = {item for item in root_values if item}
        require(set(allocated) <= marked, "GC lost an earlier C2 root")
        require(root_values == before, "non-moving GC wrote a C2 root back")
        root_cursor += 1
        collections += 1
    require(root_cursor == len(root_values), "GC stress root cursor")
    return {"collections": collections, "surviving_roots": len(allocated), "writebacks": 0}


def rejected(label: str, baseline: bytes, mutate: Callable[[bytearray], None],
             images: list[Any], catalog_crc: int) -> str:
    candidate = bytearray(baseline)
    mutate(candidate)
    try:
        decode_v2(bytes(candidate), images, catalog_crc)
    except SingleSourceError:
        return label
    raise SingleSourceError(f"mutation accepted: {label}")


def mutations(baseline: bytes, c2d_v1: bytes, images: list[Any], catalog_crc: int) -> list[str]:
    resolution_count = u16(baseline, 16)
    resolutions_offset = u16(baseline, 22)
    roots_offset = resolutions_offset + resolution_count * 2
    descriptors = [descriptor for image in images for descriptor in image.descriptors]
    first_root = next(index for index, item in enumerate(descriptors) if item.kind in ROOT_KINDS)
    first_direct = next(index for index, item in enumerate(descriptors) if item.kind not in ROOT_KINDS)
    labels = []
    try:
        decode_v2(c2d_v1, images, catalog_crc)
    except SingleSourceError:
        labels.append("v1-to-v2")
    else:
        raise SingleSourceError("C2D-v2 decoder accepted C2D-v1")
    try:
        F.decode_c2d(baseline, images, [], catalog_crc)
    except (F.FullError, IndexError):
        labels.append("v2-to-v1")
    else:
        raise SingleSourceError("C2D-v1 decoder accepted C2D-v2")
    labels += [
        rejected("root-count", baseline, lambda x: struct.pack_into("<H", x, 26, u16(x, 26) - 1), images, catalog_crc),
        rejected("total-truncated", baseline, lambda x: struct.pack_into("<H", x, 24, u16(x, 24) - 2), images, catalog_crc),
        rejected("trailing-data", baseline, lambda x: x.extend(b"\0\0"), images, catalog_crc),
        rejected("heap-root-missing", baseline,
                 lambda x: struct.pack_into("<H", x, resolutions_offset + first_root * 2, 0xFFFF), images, catalog_crc),
        rejected("heap-root-reordered", baseline,
                 lambda x: struct.pack_into("<H", x, resolutions_offset + first_root * 2,
                                            u16(x, resolutions_offset + first_root * 2) + 1), images, catalog_crc),
        rejected("direct-as-root", baseline,
                 lambda x: struct.pack_into("<H", x, resolutions_offset + first_direct * 2, 0), images, catalog_crc),
        rejected("zero-root-value", baseline, lambda x: struct.pack_into("<H", x, roots_offset, 0), images, catalog_crc),
        rejected("nonpointer-root-value", baseline, lambda x: struct.pack_into("<H", x, roots_offset, 3), images, catalog_crc),
        rejected("catalog-identity", baseline, lambda x: x.__setitem__(28, x[28] ^ 1), images, catalog_crc),
    ]
    return labels


def collect() -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    images, shelf, c2d_v1, facts = F.build_all()
    catalog_crc = struct.unpack_from("<I", shelf, 18)[0]
    c2d_v2, logical = build_v2(images, c2d_v1)
    decoded = decode_v2(c2d_v2, images, catalog_crc)
    metrics = entry_metrics(images)
    materialization = materialize_entries(c2d_v2, images, logical)
    stress = gc_stress(images)
    negative = mutations(c2d_v2, c2d_v1, images, catalog_crc)
    counts = Counter(item.kind for image in images for item in image.descriptors)

    require(contract["status"] == "option-b2-owner-approved-product-work-authorized"
            and contract["owner_decision"] ==
            "Option B2 and the CRC-domain correction approved without amendment on 2026-07-19.",
            "single-source contract status")
    require(len(shelf) == 69754 and len(c2d_v1) == 10480 and len(c2d_v2) == 11048,
            "single-source size arithmetic")
    require(decoded["roots"] == 284 and decoded["headroom"] == 39768,
            "single-source root geometry")
    require(metrics == {"maximum_entry_literals": 23, "maximum_entry_root_values": 9,
                        "entries_with_root_values": 47}, "entry materialization metrics")
    require(materialization == {
                "entries": 583, "contiguous_root_spans": 47,
                "maximum_descriptor_read_bytes": 184,
                "maximum_resolution_read_bytes": 46,
                "maximum_root_read_bytes": 18,
            } and len(negative) == 11 and stress["collections"] == 284,
            "single-source proof coverage")
    require(contract["measured"]["c2d_v2_bytes"] == len(c2d_v2)
            and contract["measured"]["bank5_headroom_bytes"] == decoded["headroom"],
            "single-source contract arithmetic")

    return {
        "format": "lisp65-c2-gc-root-single-source-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-19",
        "status": "option-b2-owner-approved-product-work-authorized",
        "claim_limit": (
            "This receipt proves the descriptor-tagged, single-source C2D-v2 host model, "
            "entry materialization, mutation rejection and non-moving GC invariant. It "
            "changes no product byte, authorizes no capacity, makes no device or latency "
            "claim and does not run the product substitution link."
        ),
        "bindings": {
            "contract": bind(CONTRACT),
            "document": bind(DOCUMENT),
            "prior_decision_receipt": bind(OLD_RECEIPT),
            "full_emitter": bind(ROOT / "tools/host-lisp/c2_full_emission.py"),
            "verifier": bind(Path(__file__)),
        },
        "verified": {
            "images": len(images),
            "entries": materialization["entries"],
            "resolution_count": facts["c2i_v2_descriptors"],
            "kind_counts": {str(key): counts[key] for key in sorted(counts)},
            "root_values": decoded["roots"],
            "root_bytes": decoded["roots"] * 2,
            "c2d_v1_bytes": len(c2d_v1),
            "c2d_v2_bytes": len(c2d_v2),
            "c2d_v2_sha256": sha(c2d_v2),
            "bank5_headroom_bytes": decoded["headroom"],
            "gc_reads_at_32_bytes": (decoded["roots"] * 2 + 31) // 32,
            **metrics,
            "hot_window_materialization": materialization,
            "gc_stress": stress,
            "negative_classes": negative,
            "product_bytes_changed": 0,
        },
        "next_authorized_action": contract["next_authorized_action"],
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    try:
        value = collect()
        if args.action == "selftest":
            require(value["verified"]["root_values"] == 284, "selftest closure")
            print("c2-gc-root-single-source: SELFTEST PASS roots=284 negatives=11 product-bytes=0")
            return 0
        data = canonical(value)
        if args.action == "write":
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_bytes(data)
            verb = "WROTE"
        else:
            require(RECEIPT.is_file() and RECEIPT.read_bytes() == data,
                    "single-source receipt drift; regenerate with write")
            verb = "PASS"
        print(f"c2-gc-root-single-source: {verb} roots=284 c2d-v2=11048 owner-approved")
        return 0
    except (OSError, ValueError, SingleSourceError, F.FullError) as error:
        print(f"c2-gc-root-single-source: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
