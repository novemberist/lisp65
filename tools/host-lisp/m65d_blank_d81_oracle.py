#!/usr/bin/env python3
"""Independent full-image oracle for M65D writes to a blank 1581 D81.

The device/bytecode model supplies only the sectors it wrote.  This module
applies those writes to a standards-shaped blank D81 and asks the existing
filesystem model plus the separate BAM-sanity checker to validate the result.
It deliberately does not use M65D's directory walker for its verdict.
"""

from __future__ import annotations

import argparse
import hashlib
from types import SimpleNamespace

import d81_bam_sanity as BAM
import d81_persistence_fault as D81


class OracleError(AssertionError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise OracleError(message)


def blank_user_image(label: bytes = b"L65WORK", disk_id: bytes = b"65") -> bytes:
    _require(1 <= len(label) <= 16, "blank D81 label must contain 1..16 bytes")
    _require(len(disk_id) == 2, "blank D81 ID must contain exactly two bytes")
    image = D81.blank_image(directory_sectors=1)
    header = D81.sector_offset(D81.DIRECTORY_TRACK, 0)
    image[header + 2] = 0x44
    image[header + 3] = 0
    image[header + 4 : header + 20] = bytes(
        (value | 0x80) if index < len(label) else 0xA0
        for index, value in enumerate(label.ljust(16, b" "))
    )
    image[header + 22 : header + 28] = bytes((disk_id[0], disk_id[1], 0xA0, ord("3"), ord("D"), 0xA0))
    return bytes(image)


def _expected_content(spec: dict) -> bytes:
    if "content" in spec:
        value = spec["content"]
        _require(isinstance(value, str), "external D81 content must be a string")
        return value.encode("ascii")
    repeat = spec.get("content_repeat")
    _require(isinstance(repeat, dict), "external D81 oracle needs content or content_repeat")
    text = repeat.get("text")
    count = repeat.get("count")
    _require(isinstance(text, str) and len(text) == 1, "content_repeat.text must be one character")
    _require(isinstance(count, int) and count > 0, "content_repeat.count must be positive")
    return text.encode("ascii") * count


def materialize(vm) -> tuple[bytes, bytes]:
    before = blank_user_image()
    after = bytearray(before)
    for key, sector in vm.disk_written.items():
        _require(
            isinstance(key, tuple) and len(key) == 2,
            "device model emitted a malformed sector key",
        )
        track, sector_no = key
        payload = bytes(sector)
        _require(len(payload) == D81.SECTOR_SIZE, "device model emitted a short sector")
        off = D81.sector_offset(track, sector_no)
        after[off : off + D81.SECTOR_SIZE] = payload
    return before, bytes(after)


def verify_vm_image(vm, spec: dict) -> dict:
    _require(isinstance(spec, dict), "external D81 oracle specification must be an object")
    name = spec.get("name")
    _require(isinstance(name, str) and name, "external D81 oracle needs a filename")
    content = _expected_content(spec)
    expected_blocks = (len(content) + 253) // 254
    if "expected_blocks" in spec:
        _require(spec["expected_blocks"] == expected_blocks, "external D81 expected_blocks drift")

    _require((40, 0) not in vm.disk_written, "M65D wrote the 1581 header sector")
    before, after = materialize(vm)
    before_header = D81.get_sector(before, D81.DIRECTORY_TRACK, 0)
    after_header = D81.get_sector(after, D81.DIRECTORY_TRACK, 0)
    _require(after_header == before_header, "M65D modified the 1581 header sector")

    D81.validate_bam(after)
    counts, bam_errors = BAM.bam_free_counts(after)
    entries, directory_blocks, directory_errors = BAM.directory_entries(after)
    _require(not bam_errors, "BAM count/bitmap mismatch: %s" % "; ".join(bam_errors))
    _require(not directory_errors, "directory walk failed: %s" % "; ".join(directory_errors))

    visible = D81.visible_files(after)
    wanted = D81.fold_name(name).replace(bytes([0xA0]), b" ").rstrip(b" ")
    _require(visible == {wanted: content}, "independent directory parser saw %r" % visible)

    matching = [
        slot for slot in D81.directory_slots(after)
        if slot.record[2] and D81.entry_name(slot.record) == wanted
    ]
    _require(len(matching) == 1, "filename is absent or duplicated in the real directory")
    slot = matching[0]
    _require(slot.track == 40 and slot.sector >= 3, "file was published outside the real directory")
    chain = D81.file_chain(after, slot.record)
    _require(len(chain) == expected_blocks, "file-chain block count drift")
    _require(len(chain) == len(set(chain)), "file chain contains a duplicate allocation")

    allocated = D81.allocated_sectors(after)
    _require(allocated == set(chain), "BAM leak or double allocation: allocated=%r chain=%r" % (sorted(allocated), chain))
    free_blocks = sum(counts) - counts[D81.DIRECTORY_TRACK - 1]
    _require(entries == 1, "external directory entry count is not one")
    _require(directory_blocks == expected_blocks, "directory block total drift")
    _require(free_blocks + directory_blocks == 3160, "BAM lost or gained data blocks")

    return {
        "result": "pass",
        "witnesses": ["d81_persistence_fault", "d81_bam_sanity"],
        "header_not_written": True,
        "header_unchanged": True,
        "directory_slot": "T%d/S%d#%d" % (slot.track, slot.sector, slot.index),
        "file_blocks": expected_blocks,
        "allocated_equals_visible_chain": True,
        "no_double_allocation": True,
        "free_plus_file_blocks": free_blocks + directory_blocks,
    }


def verify_media_change_phase(vm, phase: str) -> dict:
    """Two-witness, two-medium oracle for terminal mount-token changes."""
    expectations = {
        "before-data-write": {
            "operation": 1,
            "changed": set(),
            "allocated": set(),
        },
        "before-bam-write": {
            "operation": 2,
            "changed": {(1, 0)},
            "allocated": set(),
        },
        "before-directory-write": {
            "operation": 3,
            "changed": {(1, 0), (40, 1)},
            "allocated": {(1, 0)},
        },
    }
    _require(phase in expectations, "unknown media-change phase")
    expected = expectations[phase]
    trace = vm.disk_write_trace
    _require(len(trace) == expected["operation"], "write trace continued after terminal mismatch")
    rejected = trace[-1]
    _require(
        rejected.get("operation") == expected["operation"]
        and rejected.get("reason") == "media-changed-during-transaction"
        and rejected.get("success") is False,
        "terminal write trace does not identify the mount-token mismatch",
    )

    before_a = blank_user_image(b"G6MEDIAA", b"A1")
    after_a = bytearray(before_a)
    for (track, sector), payload in vm.disk_written.items():
        off = D81.sector_offset(track, sector)
        after_a[off : off + D81.SECTOR_SIZE] = bytes(payload)
    after_a = bytes(after_a)
    before_b = blank_user_image(b"OTHERWORK", b"B2")
    after_b = bytes(before_b)  # no F011 command follows the rejected guard

    changed_a = set(_writes_between(before_a, after_a))
    changed_b = set(_writes_between(before_b, after_b))
    _require(changed_a == expected["changed"], "source-medium phase delta drift: %r" % sorted(changed_a))
    _require(not changed_b and after_b == before_b, "target medium was mutated")
    _require(D81.get_sector(after_a, 40, 0) == D81.get_sector(before_a, 40, 0), "source header changed")
    _require(D81.get_sector(after_b, 40, 0) == D81.get_sector(before_b, 40, 0), "target header changed")
    D81.validate_bam(after_a)
    D81.validate_bam(after_b)
    _require(D81.visible_files(after_a) == {}, "source published a precommit file")
    _require(D81.visible_files(after_b) == {}, "target published a file")
    _require(D81.allocated_sectors(after_a) == expected["allocated"], "source BAM phase state drift")
    _require(D81.allocated_sectors(after_b) == set(), "target BAM changed")
    _counts_a, bam_errors_a = BAM.bam_free_counts(after_a)
    _counts_b, bam_errors_b = BAM.bam_free_counts(after_b)
    _entries_a, _blocks_a, dir_errors_a = BAM.directory_entries(after_a)
    _entries_b, _blocks_b, dir_errors_b = BAM.directory_entries(after_b)
    _require(not bam_errors_a and not bam_errors_b, "BAM count/bitmap mismatch in phase oracle")
    _require(not dir_errors_a and not dir_errors_b, "directory parser rejected phase image")

    return {
        "result": "pass",
        "phase": phase,
        "terminal_status": 12,
        "injected_write_operation": expected["operation"],
        "source_changed_sectors": ["T%d/S%d" % pair for pair in sorted(changed_a)],
        "source_visible_files": 0,
        "target_changed_sectors": [],
        "target_byte_identical": True,
        "source_sha256": hashlib.sha256(after_a).hexdigest(),
        "target_before_sha256": hashlib.sha256(before_b).hexdigest(),
        "target_after_sha256": hashlib.sha256(after_b).hexdigest(),
        "witnesses": ["d81_persistence_fault", "d81_bam_sanity"],
    }


def verify_residual_window_boundary(vm, phase: str) -> dict:
    """Characterize, but deliberately do not call safe, the stock-core gap."""
    targets = {
        "data": (1, 0),
        "bam": (40, 1),
        "directory": (40, 3),
    }
    _require(phase in targets, "unknown residual-window phase")
    target = targets[phase]
    trace = vm.disk_write_trace
    _require(len(trace) == 1, "residual-window command was followed by another write")
    row = trace[0]
    _require(
        row.get("operation") == 1
        and row.get("track") == target[0]
        and row.get("sector") == target[1]
        and row.get("success") is False
        and row.get("command_success") is True
        and row.get("foreign_write") is True
        and row.get("reason") == "media-changed-in-residual-window",
        "residual-window trace does not bind one foreign command followed by status 12",
    )
    _require(vm.disk_written == {}, "source medium changed during isolated boundary command")
    _require(
        set(vm.disk_foreign_written) == {target},
        "residual window changed more or fewer than the one targeted foreign sector",
    )

    source_before = blank_user_image(b"G6MEDIAA", b"A1")
    source_after = bytes(source_before)
    foreign_before = blank_user_image(b"G6MEDIAB", b"B2")
    foreign_after = bytearray(foreign_before)
    payload = bytes(vm.disk_foreign_written[target])
    _require(len(payload) == D81.SECTOR_SIZE, "foreign command emitted a short sector")
    offset = D81.sector_offset(*target)
    foreign_after[offset : offset + D81.SECTOR_SIZE] = payload
    foreign_after = bytes(foreign_after)
    source_delta = set(_writes_between(source_before, source_after))
    foreign_delta = set(_writes_between(foreign_before, foreign_after))
    _require(not source_delta and source_before == source_after, "source image is not byte-identical")
    _require(foreign_delta == {target}, "foreign full-image delta exceeds one sector")

    foreign_valid = True
    try:
        D81.validate_bam(foreign_after)
        D81.visible_files(foreign_after)
        _counts, bam_errors = BAM.bam_free_counts(foreign_after)
        _entries, _blocks, directory_errors = BAM.directory_entries(foreign_after)
        if bam_errors or directory_errors:
            foreign_valid = False
    except (AssertionError, ValueError):
        foreign_valid = False
    return {
        "result": "known-contract-boundary-characterized",
        "safety_pass": False,
        "phase": phase,
        "terminal_status": 12,
        "source_changed_sectors": [],
        "source_byte_identical": True,
        "foreign_changed_sectors": ["T%d/S%d" % target],
        "foreign_changed_sector_count": 1,
        "writes_after_detection": 0,
        "foreign_filesystem_valid_after": foreign_valid,
        "damage_class": (
            "unallocated-data-sector-only" if phase == "data"
            else "filesystem-metadata-may-be-invalid"
        ),
        "witnesses": ["full-image-sector-diff", "d81_persistence_fault", "d81_bam_sanity"],
    }


def _writes_between(before: bytes, after: bytes) -> dict[tuple[int, int], list[int]]:
    writes: dict[tuple[int, int], list[int]] = {}
    for track in range(1, D81.TRACKS + 1):
        for sector in range(D81.SECTORS_PER_TRACK):
            old = D81.get_sector(before, track, sector)
            new = D81.get_sector(after, track, sector)
            if old != new:
                writes[(track, sector)] = list(new)
    return writes


def _expect_reject(label: str, vm, spec: dict) -> None:
    try:
        verify_vm_image(vm, spec)
    except (OracleError, AssertionError, ValueError):
        return
    raise AssertionError("external D81 negative guard accepted %s" % label)


def selftest() -> None:
    blank = blank_user_image()
    created = D81.plan_transaction(blank, "new", "oracle", b"a" * 700).final
    vm = SimpleNamespace(disk_written=_writes_between(blank, created))
    report = verify_vm_image(
        vm,
        {"name": "oracle", "content_repeat": {"text": "a", "count": 700}, "expected_blocks": 3},
    )
    _require(report["file_blocks"] == 3, "positive multi-sector selftest drift")

    header_corrupt = bytearray(created)
    header_off = D81.sector_offset(40, 0)
    header_corrupt[header_off + 32] = 0x81
    _expect_reject(
        "header write",
        SimpleNamespace(disk_written=_writes_between(blank, bytes(header_corrupt))),
        {"name": "oracle", "content_repeat": {"text": "a", "count": 700}},
    )

    leaked = bytearray(created)
    extra = next(pair for pair in D81.free_in_half(leaked, 1) if pair not in D81.allocated_sectors(leaked))
    D81.set_sector_free(leaked, extra[0], extra[1], False)
    _expect_reject(
        "orphan BAM allocation",
        SimpleNamespace(disk_written=_writes_between(blank, bytes(leaked))),
        {"name": "oracle", "content_repeat": {"text": "a", "count": 700}},
    )

    replaced = D81.plan_transaction(created, "replace", "oracle", b"b" * 509).final
    verify_vm_image(
        SimpleNamespace(disk_written=_writes_between(blank, replaced)),
        {"name": "oracle", "content_repeat": {"text": "b", "count": 509}, "expected_blocks": 3},
    )

    for phase, target in (("data", (1, 0)), ("bam", (40, 1)), ("directory", (40, 3))):
        payload = [0] * D81.SECTOR_SIZE
        payload[2] = 65
        report = verify_residual_window_boundary(
            SimpleNamespace(
                disk_written={}, disk_foreign_written={target: payload},
                disk_write_trace=[{
                    "operation": 1, "track": target[0], "sector": target[1],
                    "success": False, "command_success": True, "foreign_write": True,
                    "reason": "media-changed-in-residual-window",
                }],
            ),
            phase,
        )
        _require(report["safety_pass"] is False, "boundary selftest was mislabeled safe")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if not args.selftest:
        ap.error("only --selftest is supported")
    selftest()
    print("m65d-blank-d81-oracle: PASS positive=2 negative=2 boundary-characterized=3 safety-pass=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
