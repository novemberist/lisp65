#!/usr/bin/env python3
"""Fault oracle for the AP6 D81 copy-on-write persistence contract.

The model treats one complete 256-byte sector write as the smallest durable
operation.  It injects a crash after every such operation in this order:

1. write and verify every sector of the replacement chain;
2. allocate that chain with one BAM-sector write;
3. publish it with one directory-sector write (the commit point);
4. release the old chain with one BAM-sector write per affected BAM half.

Before step 3, a new file must remain invisible and a replaced file must still
resolve to its old contents.  From step 3 onward, the complete new contents
must be visible.  A post-commit crash may leave old sectors allocated, but may
not change any other durable state.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass


SECTOR_SIZE = 256
TRACKS = 80
SECTORS_PER_TRACK = 40
IMAGE_SIZE = TRACKS * SECTORS_PER_TRACK * SECTOR_SIZE
DIRECTORY_TRACK = 40
BAM_ENTRY_BASE = 16
BAM_ENTRY_SIZE = 6
DIR_ENTRY_SIZE = 32
MAX_PAYLOAD = 8192


class PlanError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DirSlot:
    track: int
    sector: int
    index: int
    record: bytes


@dataclass(frozen=True)
class WriteOp:
    kind: str
    label: str
    offset: int
    data: bytes


@dataclass(frozen=True)
class Transaction:
    mode: str
    name: str
    payload: bytes
    before: bytes
    operations: tuple[WriteOp, ...]
    commit_index: int
    new_chain: tuple[tuple[int, int], ...]
    old_chain: tuple[tuple[int, int], ...]
    final: bytes


def sector_offset(track: int, sector: int) -> int:
    if not (1 <= track <= TRACKS and 0 <= sector < SECTORS_PER_TRACK):
        raise ValueError("sector out of range T%d/S%d" % (track, sector))
    return ((track - 1) * SECTORS_PER_TRACK + sector) * SECTOR_SIZE


def get_sector(image: bytes | bytearray, track: int, sector: int) -> bytes:
    off = sector_offset(track, sector)
    result = bytes(image[off : off + SECTOR_SIZE])
    if len(result) != SECTOR_SIZE:
        raise ValueError("short sector T%d/S%d" % (track, sector))
    return result


def bam_half(track: int) -> int:
    if not 1 <= track <= TRACKS:
        raise ValueError("track out of range: %d" % track)
    return 1 if track <= 40 else 2


def bam_entry_relative(track: int) -> int:
    return BAM_ENTRY_BASE + BAM_ENTRY_SIZE * ((track - 1) if track <= 40 else (track - 41))


def bam_locations(track: int, sector: int) -> tuple[int, int, int]:
    entry = sector_offset(DIRECTORY_TRACK, bam_half(track)) + bam_entry_relative(track)
    return entry, entry + 1 + sector // 8, 1 << (sector % 8)


def sector_is_free(image: bytes | bytearray, track: int, sector: int) -> bool:
    _, bitmap_off, mask = bam_locations(track, sector)
    return bool(image[bitmap_off] & mask)


def set_sector_free(image: bytearray, track: int, sector: int, free: bool) -> None:
    count_off, bitmap_off, mask = bam_locations(track, sector)
    was_free = bool(image[bitmap_off] & mask)
    if was_free == free:
        return
    if free:
        image[bitmap_off] |= mask
        image[count_off] += 1
    else:
        image[bitmap_off] &= 0xFF ^ mask
        image[count_off] -= 1


def validate_bam(image: bytes | bytearray) -> None:
    for track in range(1, TRACKS + 1):
        count_off, _, _ = bam_locations(track, 0)
        entry = count_off
        bits = sum(byte.bit_count() for byte in image[entry + 1 : entry + BAM_ENTRY_SIZE])
        if image[count_off] != bits:
            raise AssertionError(
                "T%d BAM count %d != bitmap bits %d" % (track, image[count_off], bits)
            )


def fold_name(name: str) -> bytes:
    try:
        raw = name.encode("ascii")
    except UnicodeEncodeError as exc:
        raise PlanError("BAD_NAME", "filename is not ASCII") from exc
    if not 1 <= len(raw) <= 16:
        raise PlanError("BAD_NAME", "filename must contain 1..16 ASCII bytes")
    folded = bytes(byte - 32 if 97 <= byte <= 122 else byte for byte in raw)
    return folded + bytes([0xA0]) * (16 - len(folded))


def entry_name(record: bytes) -> bytes:
    return bytes(record[5:21]).replace(bytes([0xA0]), b" ").rstrip(b" ")


def make_dir_record(name: str, chain: tuple[tuple[int, int], ...]) -> bytes:
    record = bytearray(DIR_ENTRY_SIZE)
    record[2] = 0x81
    record[3], record[4] = chain[0]
    record[5:21] = fold_name(name)
    record[30] = len(chain) & 0xFF
    record[31] = len(chain) >> 8
    return bytes(record)


def blank_image(directory_sectors: int = 1) -> bytearray:
    if not 1 <= directory_sectors <= 32:
        raise ValueError("directory sector count must be 1..32")
    image = bytearray(IMAGE_SIZE)
    for track in range(1, TRACKS + 1):
        count_off, _, _ = bam_locations(track, 0)
        if track == DIRECTORY_TRACK:
            image[count_off : count_off + BAM_ENTRY_SIZE] = bytes(BAM_ENTRY_SIZE)
        else:
            image[count_off] = SECTORS_PER_TRACK
            image[count_off + 1 : count_off + BAM_ENTRY_SIZE] = bytes([0xFF]) * 5

    bam1 = sector_offset(DIRECTORY_TRACK, 1)
    bam2 = sector_offset(DIRECTORY_TRACK, 2)
    image[bam1 : bam1 + 2] = bytes((DIRECTORY_TRACK, 2))
    image[bam2 : bam2 + 2] = bytes((0, 0xFF))
    header = sector_offset(DIRECTORY_TRACK, 0)
    image[header : header + 2] = bytes((DIRECTORY_TRACK, 3))
    for index in range(directory_sectors):
        sector = 3 + index
        off = sector_offset(DIRECTORY_TRACK, sector)
        if index + 1 < directory_sectors:
            image[off : off + 2] = bytes((DIRECTORY_TRACK, sector + 1))
        else:
            image[off : off + 2] = bytes((0, 0xFF))
    validate_bam(image)
    return image


def directory_slots(image: bytes | bytearray) -> list[DirSlot]:
    header = get_sector(image, DIRECTORY_TRACK, 0)
    track, sector = header[0], header[1]
    result: list[DirSlot] = []
    seen: set[tuple[int, int]] = set()
    fuel = 64
    while track:
        if fuel == 0:
            raise ValueError("directory walk exhausted fuel")
        fuel -= 1
        key = (track, sector)
        if key in seen:
            raise ValueError("directory loop at T%d/S%d" % key)
        seen.add(key)
        data = get_sector(image, track, sector)
        for index in range(8):
            base = index * DIR_ENTRY_SIZE
            result.append(DirSlot(track, sector, index, data[base : base + DIR_ENTRY_SIZE]))
        track, sector = data[0], data[1]
    return result


def file_chain(image: bytes | bytearray, record: bytes) -> tuple[tuple[int, int], ...]:
    track, sector = record[3], record[4]
    chain: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    while track:
        key = (track, sector)
        if key in seen or len(chain) >= TRACKS * SECTORS_PER_TRACK:
            raise ValueError("file-chain loop at T%d/S%d" % key)
        seen.add(key)
        chain.append(key)
        data = get_sector(image, track, sector)
        track, sector = data[0], data[1]
    if not chain:
        raise ValueError("empty file chain")
    return tuple(chain)


def read_record_payload(image: bytes | bytearray, record: bytes) -> bytes:
    out = bytearray()
    chain = file_chain(image, record)
    for index, (track, sector) in enumerate(chain):
        data = get_sector(image, track, sector)
        if index + 1 < len(chain):
            if data[0:2] != bytes(chain[index + 1]):
                raise ValueError("broken chain link at T%d/S%d" % (track, sector))
            out.extend(data[2:])
        else:
            if data[0] != 0 or not 1 <= data[1] <= 255:
                raise ValueError("bad final-sector marker at T%d/S%d" % (track, sector))
            out.extend(data[2 : 2 + data[1] - 1])
    blocks = record[30] | (record[31] << 8)
    if blocks != len(chain):
        raise ValueError("directory block count %d != chain length %d" % (blocks, len(chain)))
    return bytes(out)


def visible_files(image: bytes | bytearray) -> dict[bytes, bytes]:
    result: dict[bytes, bytes] = {}
    for slot in directory_slots(image):
        if slot.record[2] == 0:
            continue
        name = entry_name(slot.record)
        if name in result:
            raise ValueError("duplicate visible directory name %r" % name)
        result[name] = read_record_payload(image, slot.record)
    return result


def free_in_half(image: bytes | bytearray, half: int) -> list[tuple[int, int]]:
    tracks = range(1, 40) if half == 1 else range(41, TRACKS + 1)
    return [
        (track, sector)
        for track in tracks
        for sector in range(SECTORS_PER_TRACK)
        if sector_is_free(image, track, sector)
    ]


def allocate_chain(image: bytes | bytearray, blocks: int) -> tuple[tuple[int, int], ...]:
    for half in (1, 2):
        candidates = free_in_half(image, half)
        if len(candidates) >= blocks:
            return tuple(candidates[:blocks])
    raise PlanError(
        "NO_SPACE",
        "no BAM half contains %d free sectors (total free may be larger)" % blocks,
    )


def chain_sector(payload: bytes, chain: tuple[tuple[int, int], ...], index: int) -> bytes:
    data = bytearray(SECTOR_SIZE)
    start = index * 254
    chunk = payload[start : start + 254]
    if index + 1 < len(chain):
        if len(chunk) != 254:
            raise AssertionError("short non-final payload chunk")
        data[0], data[1] = chain[index + 1]
    else:
        data[0] = 0
        data[1] = len(chunk) + 1
    data[2 : 2 + len(chunk)] = chunk
    return bytes(data)


def apply_op(image: bytes | bytearray, operation: WriteOp) -> bytes:
    if len(operation.data) != SECTOR_SIZE or operation.offset % SECTOR_SIZE:
        raise AssertionError("write operation is not one complete sector")
    result = bytearray(image)
    result[operation.offset : operation.offset + SECTOR_SIZE] = operation.data
    return bytes(result)


def bam_write_for(
    image: bytes | bytearray, sectors: tuple[tuple[int, int], ...], free: bool
) -> WriteOp:
    halves = {bam_half(track) for track, _ in sectors}
    if len(halves) != 1:
        raise AssertionError("one BAM write may only update one BAM half")
    half = next(iter(halves))
    staged = bytearray(image)
    for track, sector in sectors:
        set_sector_free(staged, track, sector, free)
    off = sector_offset(DIRECTORY_TRACK, half)
    action = "free" if free else "allocate"
    return WriteOp("bam-" + action, "%s BAM%d" % (action, half), off, bytes(staged[off : off + SECTOR_SIZE]))


def directory_write_for(
    image: bytes | bytearray, slot: DirSlot, name: str, chain: tuple[tuple[int, int], ...]
) -> WriteOp:
    data = bytearray(get_sector(image, slot.track, slot.sector))
    link = bytes(data[0:2])
    base = slot.index * DIR_ENTRY_SIZE
    data[base : base + DIR_ENTRY_SIZE] = make_dir_record(name, chain)
    data[0:2] = link
    return WriteOp(
        "directory-commit",
        "commit %s at T%d/S%d#%d" % (name, slot.track, slot.sector, slot.index),
        sector_offset(slot.track, slot.sector),
        bytes(data),
    )


def plan_transaction(before: bytes, mode: str, name: str, payload: bytes) -> Transaction:
    if len(before) != IMAGE_SIZE:
        raise PlanError("BAD_IMAGE", "D81 image size %d != %d" % (len(before), IMAGE_SIZE))
    if mode not in ("new", "replace"):
        raise PlanError("BAD_MODE", "mode must be new or replace")
    if not 1 <= len(payload) <= MAX_PAYLOAD:
        raise PlanError(
            "TOO_LARGE",
            "payload length %d is outside 1..%d" % (len(payload), MAX_PAYLOAD),
        )
    wanted = fold_name(name).replace(bytes([0xA0]), b" ").rstrip(b" ")
    slots = directory_slots(before)
    matches = [slot for slot in slots if slot.record[2] and entry_name(slot.record) == wanted]
    free_slots = [slot for slot in slots if slot.record[2] == 0]
    if len(matches) > 1:
        raise PlanError("DUPLICATE", "directory contains duplicate name %s" % name)
    if mode == "new":
        if matches:
            raise PlanError("DUPLICATE", "directory already contains %s" % name)
        if not free_slots:
            raise PlanError("DIRECTORY_FULL", "directory has no free entry")
        slot = free_slots[0]
        old_chain: tuple[tuple[int, int], ...] = ()
    else:
        if not matches:
            raise PlanError("NOT_FOUND", "replace target %s is absent" % name)
        slot = matches[0]
        old_chain = file_chain(before, slot.record)

    blocks = (len(payload) + 253) // 254
    new_chain = allocate_chain(before, blocks)
    operations: list[WriteOp] = []
    state = before
    for index, (track, sector) in enumerate(new_chain):
        operation = WriteOp(
            "data",
            "data %d/%d T%d/S%d" % (index + 1, len(new_chain), track, sector),
            sector_offset(track, sector),
            chain_sector(payload, new_chain, index),
        )
        operations.append(operation)
        state = apply_op(state, operation)
        if get_sector(state, track, sector) != operation.data:
            raise AssertionError("data-sector verify failed")

    allocation = bam_write_for(state, new_chain, False)
    operations.append(allocation)
    state = apply_op(state, allocation)
    validate_bam(state)

    commit = directory_write_for(state, slot, name, new_chain)
    operations.append(commit)
    commit_index = len(operations) - 1
    state = apply_op(state, commit)

    old_by_half: dict[int, list[tuple[int, int]]] = {}
    for sector in old_chain:
        old_by_half.setdefault(bam_half(sector[0]), []).append(sector)
    for half in sorted(old_by_half):
        cleanup = bam_write_for(state, tuple(old_by_half[half]), True)
        operations.append(cleanup)
        state = apply_op(state, cleanup)
        validate_bam(state)

    return Transaction(
        mode,
        name,
        payload,
        before,
        tuple(operations),
        commit_index,
        new_chain,
        old_chain,
        state,
    )


def allocated_sectors(image: bytes | bytearray) -> set[tuple[int, int]]:
    return {
        (track, sector)
        for track in list(range(1, 40)) + list(range(41, TRACKS + 1))
        for sector in range(SECTORS_PER_TRACK)
        if not sector_is_free(image, track, sector)
    }


def verify_fault_state(transaction: Transaction, state: bytes, operation_index: int) -> None:
    validate_bam(state)
    before_files = visible_files(transaction.before)
    actual_files = visible_files(state)
    wanted = fold_name(transaction.name).replace(bytes([0xA0]), b" ").rstrip(b" ")
    if operation_index < transaction.commit_index:
        if actual_files != before_files:
            raise AssertionError("pre-commit fault changed the visible directory/files")
        return

    expected_files = dict(before_files)
    expected_files[wanted] = transaction.payload
    if actual_files != expected_files:
        raise AssertionError("post-commit fault does not expose the complete new file")

    current_allocated = allocated_sectors(state)
    final_allocated = allocated_sectors(transaction.final)
    extra = current_allocated - final_allocated
    missing = final_allocated - current_allocated
    if missing:
        raise AssertionError("post-commit fault lost committed sectors: %s" % sorted(missing))
    if not extra.issubset(set(transaction.old_chain)):
        raise AssertionError("post-commit fault leaked non-old sectors: %s" % sorted(extra))

    leaked = extra
    allowed_offsets: set[int] = set()
    for track, sector in leaked:
        count_off, bitmap_off, _ = bam_locations(track, sector)
        allowed_offsets.add(count_off)
        allowed_offsets.add(bitmap_off)
    differences = {
        offset
        for offset, (current, final) in enumerate(zip(state, transaction.final))
        if current != final
    }
    if not differences.issubset(allowed_offsets):
        raise AssertionError(
            "post-commit state differs outside old-sector leak metadata: %s"
            % sorted(differences - allowed_offsets)[:12]
        )


def seed_file(image: bytes, name: str, payload: bytes) -> bytes:
    transaction = plan_transaction(image, "new", name, payload)
    return transaction.final


def exhaust_half(image: bytearray, half: int) -> None:
    for track, sector in free_in_half(image, half):
        set_sector_free(image, track, sector, False)
    validate_bam(image)


def payload(length: int, salt: int) -> bytes:
    return bytes(((index * 29 + salt) & 0xFF) for index in range(length))


def run_transaction_case(label: str, image: bytes, mode: str, name: str, data: bytes) -> tuple[int, Transaction]:
    transaction = plan_transaction(image, mode, name, data)
    state = transaction.before
    checked = 0
    for index, operation in enumerate(transaction.operations):
        state = apply_op(state, operation)
        verify_fault_state(transaction, state, index)
        checked += 1
    if state != transaction.final:
        raise AssertionError("%s did not reach its planned final image" % label)
    return checked, transaction


def expect_plan_error(label: str, image: bytes, mode: str, name: str, data: bytes, code: str) -> None:
    original = bytes(image)
    try:
        plan_transaction(original, mode, name, data)
    except PlanError as exc:
        if exc.code != code:
            raise AssertionError("%s returned %s, expected %s" % (label, exc.code, code)) from exc
    else:
        raise AssertionError("%s unexpectedly planned successfully" % label)
    if bytes(image) != original:
        raise AssertionError("%s changed its input image on planning failure" % label)


def expect_oracle_reject(label: str, transaction: Transaction, state: bytes, index: int) -> None:
    try:
        verify_fault_state(transaction, state, index)
    except (AssertionError, ValueError):
        return
    raise AssertionError("negative oracle guard did not reject %s" % label)


def selftest() -> tuple[int, int, int]:
    cases = 0
    fault_points = 0

    matrix = (
        ("new-one", "new", "n1", payload(1, 1), None),
        ("new-two", "new", "n2", payload(255, 2), None),
        ("new-many", "new", "nn", payload(700, 3), None),
        ("replace-one", "replace", "r1", payload(100, 4), payload(300, 31)),
        ("replace-two", "replace", "r2", payload(255, 5), payload(30, 32)),
        ("replace-many", "replace", "rn", payload(700, 6), payload(40, 33)),
    )
    retained_transaction: Transaction | None = None
    for label, mode, name, data, old in matrix:
        image = bytes(blank_image())
        if old is not None:
            image = seed_file(image, name, old)
        checked, transaction = run_transaction_case(label, image, mode, name, data)
        fault_points += checked
        cases += 1
        if label == "replace-two":
            retained_transaction = transaction

    low = bytes(blank_image())
    checked, low_transaction = run_transaction_case("bam-low", low, "new", "blo", payload(600, 7))
    if {bam_half(track) for track, _ in low_transaction.new_chain} != {1}:
        raise AssertionError("low-half case did not allocate from BAM1")
    cases += 1
    fault_points += checked

    high_image = blank_image()
    exhaust_half(high_image, 1)
    checked, high_transaction = run_transaction_case(
        "bam-high", bytes(high_image), "new", "bhi", payload(600, 8)
    )
    if {bam_half(track) for track, _ in high_transaction.new_chain} != {2}:
        raise AssertionError("high-half case did not allocate from BAM2")
    cases += 1
    fault_points += checked

    cross_image = blank_image()
    exhaust_half(cross_image, 1)
    cross_seeded = bytearray(seed_file(bytes(cross_image), "cross", payload(300, 41)))
    for sector in range(3):
        set_sector_free(cross_seeded, 1, sector, True)
    checked, cross_transaction = run_transaction_case(
        "bam-cross-half-replace",
        bytes(cross_seeded),
        "replace",
        "cross",
        payload(255, 42),
    )
    if {bam_half(track) for track, _ in cross_transaction.new_chain} != {1}:
        raise AssertionError("cross-half replacement did not allocate its new chain from BAM1")
    if {bam_half(track) for track, _ in cross_transaction.old_chain} != {2}:
        raise AssertionError("cross-half replacement did not release its old chain through BAM2")
    cases += 1
    fault_points += checked

    checked, _ = run_transaction_case(
        "max-8192", bytes(blank_image()), "new", "max8192", payload(MAX_PAYLOAD, 9)
    )
    cases += 1
    fault_points += checked
    expect_plan_error(
        "over-8192", bytes(blank_image()), "new", "over", payload(MAX_PAYLOAD + 1, 10), "TOO_LARGE"
    )
    cases += 1

    full_medium = blank_image()
    exhaust_half(full_medium, 1)
    exhaust_half(full_medium, 2)
    expect_plan_error("full-medium-new", bytes(full_medium), "new", "full", b"x", "NO_SPACE")
    cases += 1
    replace_full = seed_file(bytes(blank_image()), "rf", b"old")
    replace_full_mutable = bytearray(replace_full)
    exhaust_half(replace_full_mutable, 1)
    exhaust_half(replace_full_mutable, 2)
    expect_plan_error(
        "full-medium-replace", bytes(replace_full_mutable), "replace", "rf", b"new", "NO_SPACE"
    )
    cases += 1

    split = blank_image()
    exhaust_half(split, 1)
    exhaust_half(split, 2)
    set_sector_free(split, 1, 0, True)
    set_sector_free(split, 41, 0, True)
    expect_plan_error("split-halves", bytes(split), "new", "split", payload(255, 11), "NO_SPACE")
    cases += 1

    full_directory = bytes(blank_image(directory_sectors=2))
    for index in range(16):
        full_directory = seed_file(full_directory, "f%02d" % index, bytes((index + 1,)))
    expect_plan_error(
        "full-directory-new", full_directory, "new", "extra", b"x", "DIRECTORY_FULL"
    )
    cases += 1
    checked, _ = run_transaction_case(
        "full-directory-replace", full_directory, "replace", "f07", payload(255, 12)
    )
    cases += 1
    fault_points += checked

    if retained_transaction is None:
        raise AssertionError("negative-guard transaction missing")
    transaction = retained_transaction
    state = transaction.before
    for index in range(transaction.commit_index):
        state = apply_op(state, transaction.operations[index])
    early_publish = apply_op(state, transaction.operations[transaction.commit_index])
    expect_oracle_reject(
        "early directory publication",
        transaction,
        early_publish,
        transaction.commit_index - 1,
    )

    committed = transaction.before
    for index in range(transaction.commit_index + 1):
        committed = apply_op(committed, transaction.operations[index])
    corrupt = bytearray(committed)
    corrupt[sector_offset(*transaction.new_chain[0]) + 2] ^= 0xFF
    expect_oracle_reject("committed payload corruption", transaction, bytes(corrupt), transaction.commit_index)

    unrelated = bytearray(committed)
    old_set = set(transaction.old_chain)
    new_set = set(transaction.new_chain)
    candidate = next(
        sector
        for sector in free_in_half(unrelated, 1) + free_in_half(unrelated, 2)
        if sector not in old_set and sector not in new_set
    )
    set_sector_free(unrelated, candidate[0], candidate[1], False)
    expect_oracle_reject("non-old post-commit leak", transaction, bytes(unrelated), transaction.commit_index)
    negative_guards = 3

    return cases, fault_points, negative_guards


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="run the synthetic AP6 new/replace and fault-injection matrix",
    )
    args = parser.parse_args(argv)
    if not args.selftest:
        parser.error("this isolated oracle currently exposes --selftest only")
    try:
        cases, fault_points, negative_guards = selftest()
    except (AssertionError, PlanError, ValueError) as exc:
        print("d81-persistence-fault: FAIL:", exc, file=sys.stderr)
        return 1
    print(
        "d81-persistence-fault: PASS cases=%d fault_points=%d negative_guards=%d "
        "max_payload=%d bam_halves=2"
        % (cases, fault_points, negative_guards, MAX_PAYLOAD)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
