#!/usr/bin/env python3
"""Generate Oracle-bound fixtures for L65M block-read validator paths."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

from l65m_contract import ContractError, RUNTIME_STATUS_BY_ERROR, validate_image


HEADER_BYTES = 38
ENTRY_BYTES = 8
NODE_BYTES = 10
SOURCE_BLOCK_BYTES = 256
ENTRY_RECORD_BLOCK_BYTES = 120
ENTRY_HASH_BLOCK_BYTES = 120
NAME_HASH_BUCKET_BITS = 4096
NODE_SEGMENT_BLOCK_BYTES = 120
NODE_RECORD_BLOCK_BYTES = 240
PATCH_SEGMENT_BLOCK_BYTES = 120
PATCH_RECORD_BLOCK_BYTES = 240
ENTRY_BLOCK_COUNTS = (15, 16, 17, 29, 30, 31, 32, 33)
NODE_SEGMENT_BLOCK_COUNTS = (11, 12, 13)
NODE_BLOCK_COUNTS = (23, 24, 25)
PATCH_BLOCK_COUNTS = (29, 30, 31, 59, 60, 61)
BITSET_BOUNDARY_OFFSETS = (1023, 1024, 1025, 2047, 2048, 2049)
LIT_NIL = 2
LIT_SYMBOL = 4
LIT_LIST = 6
LIT_STRING = 7


@dataclass(frozen=True)
class Case:
    name: str
    image: bytes
    expected_status: str
    expected_new_symbols: int
    expected_patches: int = 0


def align2(value: int) -> int:
    return (value + 1) & ~1


def put16(dst: bytearray, off: int, value: int) -> None:
    dst[off : off + 2] = value.to_bytes(2, "little")


def put32(dst: bytearray, off: int, value: int) -> None:
    dst[off : off + 4] = value.to_bytes(4, "little")


def name_hash16(name: bytes) -> int:
    value = 0x9E37
    for byte in name:
        value = ((value << 2) | (value >> 14)) & 0xFFFF
        value ^= byte
    return value


def packed_names(names: list[bytes]) -> tuple[bytes, list[int]]:
    pool = bytearray()
    offsets = []
    for name in names:
        offsets.append(len(pool))
        pool.extend(name)
        pool.append(0)
    return bytes(pool), offsets


def pool_with_name_at(name: bytes, offset: int) -> bytes:
    if offset == 0:
        return name + b"\0"
    return b"p" * (offset - 1) + b"\0" + name + b"\0"


def make_image(
    entry_names: list[bytes],
    *,
    pool: bytes | None = None,
    entry_name_offsets: list[int] | None = None,
    node_name_offsets: list[int] | None = None,
    node_kinds: list[int] | None = None,
    node_children: list[list[int]] | None = None,
    patch_targets: list[int] | None = None,
    target_length: int | None = None,
) -> bytes:
    if pool is None:
        pool, derived_offsets = packed_names(entry_names)
        if entry_name_offsets is None:
            entry_name_offsets = derived_offsets
    if entry_name_offsets is None or len(entry_name_offsets) != len(entry_names):
        raise ValueError("every entry needs one string-pool offset")
    node_name_offsets = node_name_offsets or []
    node_kinds = node_kinds or [LIT_SYMBOL] * len(node_name_offsets)
    if len(node_kinds) != len(node_name_offsets):
        raise ValueError("every node needs one kind")
    node_children = node_children or [[] for _ in node_name_offsets]
    if len(node_children) != len(node_name_offsets):
        raise ValueError("every node needs one child list")
    indices = [child for children in node_children for child in children]
    if any(child >= len(node_name_offsets) for child in indices):
        raise ValueError("node child is outside the node table")

    patch_targets = patch_targets or []
    if patch_targets and len(entry_names) != 1:
        raise ValueError("patch fixtures require exactly one entry")
    if len(patch_targets) > 255:
        raise ValueError("one code object supports at most 255 literal patches")
    if any(target >= len(node_name_offsets) for target in patch_targets):
        raise ValueError("patch target is outside the node table")
    code_object = bytearray((0xB5, 0, 0, 0, 0, 0, len(patch_targets)))
    code_object.extend(b"\0\0" * len(patch_targets))
    code_object = bytes(code_object)
    blob = code_object * len(entry_names)
    entries_off = HEADER_BYTES
    index_off = align2(entries_off + len(entry_names) * ENTRY_BYTES)
    nodes_off = align2(index_off + len(indices) * 2)
    patches_off = align2(nodes_off + len(node_name_offsets) * NODE_BYTES)
    strings_off = align2(patches_off + len(patch_targets) * 4)

    if target_length is not None:
        metadata_target = target_length - 4 - len(blob)
        if metadata_target < strings_off or metadata_target & 1:
            raise ValueError(f"cannot form exact source length {target_length}")
        pool_target = metadata_target - strings_off
        if pool_target < len(pool) + 2:
            raise ValueError(f"source length {target_length} leaves no padding string")
        padding = pool_target - len(pool)
        pool += b"q" * (padding - 1) + b"\0"

    metadata_len = align2(strings_off + len(pool))
    metadata = bytearray(metadata_len)
    metadata[0:4] = b"L65M"
    metadata[4] = 1
    metadata[5] = HEADER_BYTES
    put16(metadata, 12, len(blob))
    put16(metadata, 14, metadata_len)
    put16(metadata, 16, len(entry_names))
    put16(metadata, 18, len(indices))
    put16(metadata, 20, len(node_name_offsets))
    put16(metadata, 22, len(patch_targets))
    put16(metadata, 24, entries_off)
    put16(metadata, 26, index_off)
    put16(metadata, 28, nodes_off)
    put16(metadata, 30, patches_off)
    put16(metadata, 32, strings_off)
    put16(metadata, 34, len(pool))

    code_off = 0
    for index, name_off in enumerate(entry_name_offsets):
        at = entries_off + index * ENTRY_BYTES
        put16(metadata, at, name_off)
        put16(metadata, at + 4, code_off)
        put16(metadata, at + 6, len(code_object))
        code_off += len(code_object)
    for index, child in enumerate(indices):
        put16(metadata, index_off + index * 2, child)
    child_cursor = 0
    for index, (kind, name_off, children) in enumerate(
        zip(node_kinds, node_name_offsets, node_children)
    ):
        at = nodes_off + index * NODE_BYTES
        metadata[at] = kind
        if kind == LIT_LIST:
            put16(metadata, at + 4, child_cursor)
            put16(metadata, at + 6, len(children))
            put16(metadata, at + 8, 0xFFFF)
        elif kind in (LIT_SYMBOL, LIT_STRING):
            if children:
                raise ValueError("symbol/string nodes cannot have children")
            put16(metadata, at + 8, name_off)
        else:
            if children:
                raise ValueError("immediate nodes cannot have children")
            put16(metadata, at + 8, 0xFFFF)
        child_cursor += len(children)
    for index, target in enumerate(patch_targets):
        at = patches_off + index * 4
        put16(metadata, at, 7 + index * 2)
        put16(metadata, at + 2, target)
    metadata[strings_off : strings_off + len(pool)] = pool

    image = bytearray(4)
    put16(image, 0, len(blob))
    put16(image, 2, metadata_len)
    image.extend(blob)
    image.extend(metadata)
    if target_length is not None and len(image) != target_length:
        raise AssertionError((len(image), target_length))
    return bytes(image)


def mutate_record_byte(
    image: bytes,
    *,
    section_header_off: int,
    record_bytes: int,
    record_index: int,
    field_off: int,
    value: int,
) -> bytes:
    mutated = bytearray(image)
    blob_len = int.from_bytes(mutated[0:2], "little")
    metadata_off = 4 + blob_len
    section_off = int.from_bytes(
        mutated[metadata_off + section_header_off : metadata_off + section_header_off + 2],
        "little",
    )
    mutated[metadata_off + section_off + record_index * record_bytes + field_off] = value
    return bytes(mutated)


def make_cases() -> list[Case]:
    cases: list[Case] = []

    for depth, status in ((9, "L65M_OK"), (10, "L65M_ERR_GRAPH")):
        cases.append(Case(
            f"literal-graph-depth-{depth}",
            make_image(
                [b"depth"],
                pool=b"depth\0",
                entry_name_offsets=[0],
                node_name_offsets=[0] * depth,
                node_kinds=[LIT_LIST] * (depth - 1) + [LIT_NIL],
                node_children=[[index + 1] for index in range(depth - 1)] + [[]],
                patch_targets=[0],
            ),
            status,
            2 if status == "L65M_OK" else 0xFFFF,
            1 if status == "L65M_OK" else 0xFFFF,
        ))

    collision_names = [b"am", b"ba"]
    if name_hash16(collision_names[0]) != name_hash16(collision_names[1]):
        raise AssertionError("declared phase-05 collision no longer collides")
    cases.append(Case(
        "hash-collision-distinct-names",
        make_image(collision_names),
        "L65M_OK",
        2,
    ))

    bucket_collision_names = [b"e", b"ahaa"]
    bucket_hashes = [name_hash16(name) for name in bucket_collision_names]
    if (bucket_hashes[0] == bucket_hashes[1] or
            bucket_hashes[0] & (NAME_HASH_BUCKET_BITS - 1)
            != bucket_hashes[1] & (NAME_HASH_BUCKET_BITS - 1)):
        raise AssertionError("declared phase-05 bucket collision no longer collides")
    cases.append(Case(
        "hash-bucket-collision-distinct-hashes",
        make_image(bucket_collision_names),
        "L65M_OK",
        2,
    ))

    hash_block_entries = ENTRY_HASH_BLOCK_BYTES // ENTRY_BYTES
    cross_block_names = [f"entry-{index:02d}".encode("ascii")
                         for index in range(hash_block_entries - 1)]
    cross_block_names.extend((b"am", b"ba"))
    cases.append(Case(
        "hash-collision-across-entry-block",
        make_image(cross_block_names),
        "L65M_OK",
        len(cross_block_names),
    ))

    duplicate_block_names = [f"unique-{index:02d}".encode("ascii")
                             for index in range(hash_block_entries - 1)]
    duplicate_block_names.extend((b"same", b"same"))
    cases.append(Case(
        "duplicate-across-entry-block",
        make_image(duplicate_block_names),
        "L65M_ERR_ENTRIES",
        0xFFFF,
    ))

    duplicate_pool = b"same\0same\0"
    cases.append(Case(
        "duplicate-text-distinct-offsets",
        make_image(
            [b"same", b"same"],
            pool=duplicate_pool,
            entry_name_offsets=[0, 5],
        ),
        "L65M_ERR_ENTRIES",
        0xFFFF,
    ))

    different_tail_pool = b"same\0left\0same\0right\0"
    cases.append(Case(
        "duplicate-text-different-tail-bytes",
        make_image(
            [b"same", b"same"],
            pool=different_tail_pool,
            entry_name_offsets=[0, 10],
        ),
        "L65M_ERR_ENTRIES",
        0xFFFF,
    ))

    cases.append(Case(
        "entry-name-length-32",
        make_image([b"n" * 32]),
        "L65M_OK",
        1,
    ))
    cases.append(Case(
        "entry-name-length-33",
        make_image([b"n" * 33]),
        "L65M_ERR_STRINGS",
        0xFFFF,
    ))

    for length in (SOURCE_BLOCK_BYTES - 1, SOURCE_BLOCK_BYTES, SOURCE_BLOCK_BYTES + 1):
        entry_names = [b"boundary"] if length & 1 else [b"left", b"right"]
        cases.append(Case(
            f"source-length-{length}",
            make_image(entry_names, target_length=length),
            "L65M_OK",
            len(entry_names),
        ))

    utf8_offset = SOURCE_BLOCK_BYTES - 1
    for label, name, status in (
        ("valid", b"\xc2\xa2", "L65M_OK"),
        ("invalid", b"\xc2A", "L65M_ERR_STRINGS"),
    ):
        cases.append(Case(
            f"utf8-{label}-across-source-block",
            make_image(
                [name],
                pool=pool_with_name_at(name, utf8_offset),
                entry_name_offsets=[utf8_offset],
            ),
            status,
            1 if status == "L65M_OK" else 0xFFFF,
        ))

    for terminator in (
        SOURCE_BLOCK_BYTES - 1,
        SOURCE_BLOCK_BYTES,
        SOURCE_BLOCK_BYTES + 1,
    ):
        entry_off = terminator + 1
        pool = b"s" * terminator + b"\0entry\0"
        cases.append(Case(
            f"string-literal-nul-at-{terminator}",
            make_image(
                [b"entry"],
                pool=pool,
                entry_name_offsets=[entry_off],
                node_name_offsets=[0],
                node_kinds=[LIT_STRING],
            ),
            "L65M_OK",
            1,
        ))

    for count in ENTRY_BLOCK_COUNTS:
        names = [f"entry-{index:02d}".encode("ascii") for index in range(count)]
        cases.append(Case(
            f"entry-record-block-count-{count}",
            make_image(names),
            "L65M_OK",
            count,
        ))

    for count in NODE_BLOCK_COUNTS:
        pool = b"entry\0symbol\0"
        cases.append(Case(
            f"node-record-block-count-{count}",
            make_image(
                [b"entry"],
                pool=pool,
                entry_name_offsets=[0],
                node_name_offsets=[6] * count,
            ),
            "L65M_OK",
            2,
        ))

    for count in NODE_SEGMENT_BLOCK_COUNTS:
        names = [b"entry"] + [f"node-{index:02d}".encode("ascii") for index in range(count)]
        pool, offsets = packed_names(names)
        cases.append(Case(
            f"node-segment-block-count-{count}",
            make_image(
                [names[0]],
                pool=pool,
                entry_name_offsets=[offsets[0]],
                node_name_offsets=offsets[1:],
            ),
            "L65M_OK",
            count + 1,
        ))

    for count in PATCH_BLOCK_COUNTS:
        cases.append(Case(
            f"patch-record-block-count-{count}",
            make_image(
                [b"entry"],
                pool=b"entry\0literal\0",
                entry_name_offsets=[0],
                node_name_offsets=[6],
                patch_targets=[0] * count,
            ),
            "L65M_OK",
            2,
            count,
        ))

    entry_boundary_count = ENTRY_RECORD_BLOCK_BYTES // ENTRY_BYTES
    entry_boundary_image = make_image(
        [f"bad-entry-{index:02d}".encode("ascii")
         for index in range(entry_boundary_count + 3)]
    )
    for relation, index in (
        ("before", entry_boundary_count - 1),
        ("at", entry_boundary_count),
        ("after", entry_boundary_count + 1),
    ):
        cases.append(Case(
            f"invalid-entry-record-{relation}-block-boundary",
            mutate_record_byte(
                entry_boundary_image,
                section_header_off=24,
                record_bytes=ENTRY_BYTES,
                record_index=index,
                field_off=2,
                value=1,
            ),
            "L65M_ERR_ENTRIES",
            0xFFFF,
        ))

    for block_bytes in (PATCH_SEGMENT_BLOCK_BYTES, PATCH_RECORD_BLOCK_BYTES):
        boundary_count = block_bytes // 4
        boundary_image = make_image(
            [b"entry"],
            pool=b"entry\0literal\0",
            entry_name_offsets=[0],
            node_name_offsets=[6],
            patch_targets=[0] * (boundary_count + 3),
        )
        for relation, index in (
            ("before", boundary_count - 1),
            ("at", boundary_count),
            ("after", boundary_count + 1),
        ):
            cases.append(Case(
                f"invalid-patch-record-{relation}-{block_bytes}-byte-boundary",
                mutate_record_byte(
                    boundary_image,
                    section_header_off=30,
                    record_bytes=4,
                    record_index=index,
                    field_off=2,
                    value=0xFF,
                ),
                "L65M_ERR_PATCH",
                0xFFFF,
                0xFFFF,
            ))

    node_boundary_count = NODE_RECORD_BLOCK_BYTES // NODE_BYTES
    node_boundary_image = make_image(
        [b"entry"],
        pool=b"entry\0symbol\0",
        entry_name_offsets=[0],
        node_name_offsets=[6] * (node_boundary_count + 3),
    )
    for relation, index in (
        ("before", node_boundary_count - 1),
        ("at", node_boundary_count),
        ("after", node_boundary_count + 1),
    ):
        cases.append(Case(
            f"invalid-node-record-{relation}-block-boundary",
            mutate_record_byte(
                node_boundary_image,
                section_header_off=28,
                record_bytes=NODE_BYTES,
                record_index=index,
                field_off=1,
                value=1,
            ),
            "L65M_ERR_NODE",
            0xFFFF,
        ))

    for offset in BITSET_BOUNDARY_OFFSETS:
        name = f"segment-{offset}".encode("ascii")
        pool = pool_with_name_at(name, offset)
        cases.append(Case(
            f"bitset-segment-offset-{offset}",
            make_image(
                [name],
                pool=pool,
                entry_name_offsets=[offset],
                node_name_offsets=[offset],
            ),
            "L65M_OK",
            1,
        ))
    return cases


def check_cases(cases: list[Case]) -> None:
    for case in cases:
        summary = None
        try:
            summary = validate_image(case.image)
            actual = "L65M_OK"
        except ContractError as exc:
            actual = RUNTIME_STATUS_BY_ERROR[exc.code]
        if actual != case.expected_status:
            raise AssertionError(
                f"{case.name}: oracle status {actual}, expected {case.expected_status}"
            )
        if summary is not None and summary.literal_patches != case.expected_patches:
            raise AssertionError(
                f"{case.name}: oracle patches {summary.literal_patches}, "
                f"expected {case.expected_patches}"
            )


def render_header(cases: list[Case]) -> str:
    lines = [
        "/* generated by tools/host-lisp/l65m_bulkread_fixtures.py; do not edit */",
        "#ifndef LISP65_L65M_BULKREAD_CASES_H",
        "#define LISP65_L65M_BULKREAD_CASES_H",
        "",
        "typedef struct {",
        "    const char *name;",
        "    const uint8_t *data;",
        "    uint16_t length;",
        "    l65m_status expected_status;",
        "    uint16_t expected_new_symbols;",
        "    uint16_t expected_patches;",
        "} l65m_bulkread_case;",
        "",
    ]
    for index, case in enumerate(cases):
        lines.append(f"static const uint8_t l65m_bulkread_data_{index}[] = {{")
        for off in range(0, len(case.image), 16):
            chunk = case.image[off : off + 16]
            lines.append("    " + ", ".join(f"0x{byte:02x}" for byte in chunk) + ",")
        lines.extend(("};", ""))
    lines.append("static const l65m_bulkread_case l65m_bulkread_cases[] = {")
    for index, case in enumerate(cases):
        lines.append(
            f'    {{ "{case.name}", l65m_bulkread_data_{index}, '
            f"{len(case.image)}u, {case.expected_status}, "
            f"{case.expected_new_symbols}u, {case.expected_patches}u }},"
        )
    lines.extend((
        "};",
        f"static const uint16_t l65m_bulkread_case_count = {len(cases)}u;",
        "",
        "#endif /* LISP65_L65M_BULKREAD_CASES_H */",
        "",
    ))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit-c-header", type=Path)
    parser.add_argument("--check-c-header", type=Path)
    args = parser.parse_args()
    if args.emit_c_header and args.check_c_header:
        parser.error("choose only one header operation")
    cases = make_cases()
    check_cases(cases)
    rendered = render_header(cases)
    if args.emit_c_header:
        args.emit_c_header.parent.mkdir(parents=True, exist_ok=True)
        args.emit_c_header.write_text(rendered, encoding="ascii")
    if args.check_c_header:
        try:
            actual = args.check_c_header.read_text(encoding="ascii")
        except OSError as exc:
            print(f"l65m-bulkread-fixtures: {exc}", file=sys.stderr)
            return 1
        if actual != rendered:
            print("l65m-bulkread-fixtures: generated C header is stale", file=sys.stderr)
            return 1
    print(
        f"l65m-bulkread-fixtures: PASS cases={len(cases)} "
        f"collision=0x{name_hash16(b'am'):04x} source-boundary=255/256/257 "
        "utf8-crossing=valid/invalid string-nul=255/256/257 "
        "entry-blocks=15/16/17,29/30/31,32/33 node-blocks=23/24/25 "
        "node-segment-blocks=11/12/13 patch-blocks=29/30/31,59/60/61 "
        "invalid-record-boundaries=entry+node+patch-before/at/after "
        "name-lengths=32/33 graph-depth=9/10 "
        "bitset-offsets=1023/1024/1025,2047/2048/2049"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
