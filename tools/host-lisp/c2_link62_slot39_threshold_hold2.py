#!/usr/bin/env python3
"""Rebind and evaluate the second Link-62 Slot-39 threshold-hold identity.

The first diagnostic identity changed the branch operand but intentionally
left the L65R-v4 and outer family seals untouched.  Hardware rejected that
carrier at boot.  This successor preserves that First Red and applies the
same one-byte executable patch while canonically rebinding every derived
identity, including the fixed-width post-RTS family-CRC tail.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link62_slot39_threshold_hold as H  # noqa: E402
import runtime_overlay_bank as R  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASE_MANIFEST = ROOT / (
    "build/c2.2/substitution/"
    "link62-c1-freezer-cutpoints-stage-bound-NONPROMOTABLE/"
    "runtime-overlays-session-c1-freezer-link62-stage-bound.json")
OVERFLOW = ROOT / (
    "build/c2.2/substitution/"
    "link62-c1-freezer-cutpoints-stage-bound-NONPROMOTABLE/"
    "runtime-overlays-session-c1-freezer-link62-region1.bin")
FAILED_HW = ROOT / (
    "build/c2.2/hardware-link62-slot39-threshold-hold-NONPROMOTABLE")
FAILED_RECEIPT = EVIDENCE / (
    "c2.2-link62-slot39-threshold-hold-carrier-seal-hardware-first-red.json")

OUT = ROOT / (
    "build/c2.2/substitution/"
    "link62-slot39-threshold-hold2-NONPROMOTABLE")
PATCHED_CARRIER = OUT / (
    "runtime-overlays-session-link62-slot39-"
    "threshold-hold2-NONPROMOTABLE.bin")
PATCH_MANIFEST = OUT / "rebound-threshold-hold-manifest.json"
PATCH_RECEIPT = EVIDENCE / (
    "c2.2-link62-slot39-threshold-hold2-nonpromotable-receipt.json")
HW_OUT = ROOT / (
    "build/c2.2/hardware-link62-slot39-threshold-hold2-NONPROMOTABLE")
DEPLOYMENT = HW_OUT / "deployment.json"
HARDWARE_RECEIPT = EVIDENCE / (
    "c2.2-link62-slot39-threshold-hold2-hardware-receipt.json")
HARDWARE_SCRIPT = ROOT / "scripts/c2-link62-slot39-threshold-hold2-hw.sh"

SLOT = 39
TAIL_BYTES = 6
TARGET_FAMILY_CRC = 0x8D75
EXPECTED_BUILD_ID = 0x09AD0D3F
EXPECTED_VMA = 0xC356
MAX_SLICE_BYTES = 1792


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


def regular(path: Path, label: str = "artifact") -> bytes:
    try:
        info = path.lstat()
    except OSError as error:
        raise RebindError(f"missing {label}: {path}: {error}") from error
    require(
        stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode),
        f"{label} is not a regular symlink-free file: {path}")
    return path.read_bytes()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(regular(path))


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    data = regular(path)
    value: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(regular(path).decode("utf-8"))
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def write_exact(path: Path, data: bytes, mode: int = 0o444) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(regular(path) == data, f"generated artifact differs: {path}")
        return
    path.write_bytes(data)
    os.chmod(path, mode)


def write_json(path: Path, value: dict[str, Any]) -> None:
    write_exact(
        path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def parsed(image: bytes) -> R.ParsedBank:
    return R.validate_region_images(
        image,
        regular(OVERFLOW),
        expected_build_id=EXPECTED_BUILD_ID,
        expected_vma=EXPECTED_VMA,
        max_slice_bytes=MAX_SLICE_BYTES,
        format_version=R.VERSION_V4,
    )


def refresh(image: bytes, tail: bytes) -> bytes:
    require(len(tail) == TAIL_BYTES, "fixed tail width drift")
    base = parsed(H.regular(H.BASE_CARRIER))
    row = base.slices[SLOT]
    require(
        row.file_offset <= H.INSTRUCTION_FILE_OFFSET < row.file_offset + row.file_size
        and row.file_size == 1532,
        "Slot-39 carrier geometry drift")
    data = bytearray(image)
    data[H.INSTRUCTION_FILE_OFFSET:H.INSTRUCTION_FILE_OFFSET + 2] = H.AFTER
    tail_offset = row.file_offset + row.file_size - TAIL_BYTES
    data[tail_offset:tail_offset + TAIL_BYTES] = tail

    record_offset = R.HEADER_SIZE + SLOT * R.ENTRY_SIZE
    fields = list(R.ENTRY.unpack_from(data, record_offset))
    require(
        fields[0] == SLOT and fields[3] == row.file_size
        and fields[5] == row.memory_size,
        "Slot-39 record geometry drift")
    fields[9] = R.crc16_ccitt_false(
        data[row.file_offset:row.file_offset + row.file_size])
    fields[10] = 0
    raw_record = bytearray(R.ENTRY.pack(*fields))
    fields[10] = R.crc16_ccitt_false(raw_record)
    require(fields[10] != 0, "derived Slot-39 record CRC is forbidden zero")
    data[record_offset:record_offset + R.ENTRY_SIZE] = R.ENTRY.pack(*fields)

    count = len(base.slices)
    directory_end = R.HEADER_SIZE + count * R.ENTRY_SIZE
    struct.pack_into(
        "<H", data, 24,
        R.crc16_ccitt_false(data[R.HEADER_SIZE:directory_end]))
    struct.pack_into("<H", data, 26, 0)
    struct.pack_into(
        "<H", data, 26, R.crc16_ccitt_false(data[:R.HEADER_SIZE]))
    return bytes(data)


def solve_tail(source: bytes) -> tuple[bytes, bytes]:
    baseline_image = refresh(source, bytes(TAIL_BYTES))
    baseline = R.crc16_ccitt_false(baseline_image)
    columns = [
        R.crc16_ccitt_false(
            refresh(source, (1 << bit).to_bytes(TAIL_BYTES, "little")))
        ^ baseline
        for bit in range(TAIL_BYTES * 8)
    ]
    basis: dict[int, tuple[int, int]] = {}
    for bit, column in enumerate(columns):
        vector = column
        mask = 1 << bit
        while vector:
            pivot = vector.bit_length() - 1
            if pivot in basis:
                old_vector, old_mask = basis[pivot]
                vector ^= old_vector
                mask ^= old_mask
            else:
                basis[pivot] = (vector, mask)
                break
    vector = TARGET_FAMILY_CRC ^ baseline
    solution = 0
    while vector:
        pivot = vector.bit_length() - 1
        require(pivot in basis, "six-byte stage tail has no CRC solution")
        old_vector, old_mask = basis[pivot]
        vector ^= old_vector
        solution ^= old_mask
    tail = solution.to_bytes(TAIL_BYTES, "little")
    candidate = refresh(source, tail)
    require(
        R.crc16_ccitt_false(candidate) == TARGET_FAMILY_CRC,
        "outer session-family CRC was not restored")
    return tail, candidate


def validate_candidate(source: bytes, candidate: bytes) -> R.ParsedBank:
    require(len(candidate) == len(source), "carrier size changed")
    require(
        candidate[
            H.INSTRUCTION_FILE_OFFSET:H.INSTRUCTION_FILE_OFFSET + 2] == H.AFTER,
        "threshold hold instruction is absent")
    result = parsed(candidate)
    require(
        R.crc16_ccitt_false(candidate) == TARGET_FAMILY_CRC,
        "outer Link-62 session-family CRC mismatch")
    return result


def mutation_gate(source: bytes, candidate: bytes) -> dict[str, Any]:
    valid = parsed(candidate)
    row = valid.slices[SLOT]
    tail_offset = row.file_offset + row.file_size - TAIL_BYTES
    record_offset = R.HEADER_SIZE + SLOT * R.ENTRY_SIZE
    mutations: dict[str, bytearray] = {}
    mutations["threshold-operand-restored"] = bytearray(candidate)
    mutations["threshold-operand-restored"][H.INSTRUCTION_FILE_OFFSET + 1] = 0x03
    mutations["wrong-threshold-displacement"] = bytearray(candidate)
    mutations["wrong-threshold-displacement"][H.INSTRUCTION_FILE_OFFSET + 1] = 0xFD
    mutations["stale-payload-crc"] = bytearray(candidate)
    mutations["stale-payload-crc"][record_offset + 20] ^= 1
    mutations["stale-record-crc"] = bytearray(candidate)
    mutations["stale-record-crc"][record_offset + 22] ^= 1
    mutations["stale-family-tail"] = bytearray(candidate)
    mutations["stale-family-tail"][tail_offset] ^= 1
    rejected: dict[str, str] = {}
    for name, mutation in mutations.items():
        try:
            validate_candidate(source, bytes(mutation))
        except (RebindError, R.OverlayBankError):
            rejected[name] = "rejected"
        else:
            raise RebindError(f"rebind mutation accepted: {name}")
    changed = [
        index for index, pair in enumerate(zip(source, candidate))
        if pair[0] != pair[1]]
    return {
        "status": "passed-executable-patch-and-v4-rebinding",
        "instruction_VMA": f"0x{H.INSTRUCTION_VMA:04x}",
        "instruction_file_offset": H.INSTRUCTION_FILE_OFFSET,
        "instruction_before_hex": H.BEFORE.hex(),
        "instruction_after_hex": H.AFTER.hex(),
        "executable_operand_bytes_changed": 1,
        "carrier_size_delta": 0,
        "derived_identity_bytes_changed": len(changed) - 1,
        "all_changed_file_offsets": changed,
        "tail_file_offset": tail_offset,
        "tail_bytes": TAIL_BYTES,
        "payload_crc16": f"0x{row.crc16:04x}",
        "record_crc16": f"0x{row.record_crc16:04x}",
        "directory_crc16": f"0x{valid.directory_crc16:04x}",
        "header_crc16": f"0x{valid.header_crc16:04x}",
        "family_crc16": f"0x{R.crc16_ccitt_false(candidate):04x}",
        "mutations_rejected": rejected,
        "mutation_count": len(rejected),
    }


def bind_first_red() -> dict[str, Any]:
    screen = regular(FAILED_HW / "boot-screen.txt")
    require(
        b"E3e" in screen and b"lisp65>" not in screen,
        "first hardware attempt no longer proves pre-REPL E3e")
    value = {
        "format":
            "lisp65-c2.2-Link62-slot39-threshold-hold-carrier-seal-first-red-v1",
        "recorded_on": "2026-07-24",
        "status": "first-red-diagnostic-carrier-seals-not-rebound",
        "promotable": False,
        "authority": {
            "invalid_patch_receipt": bind(H.PATCH_RECEIPT),
            "invalid_deployment": bind(H.DEPLOYMENT),
            "invalid_carrier": bind(H.PATCHED_CARRIER, 0x08000000),
            "invalid_driver": bind(Path(H.__file__)),
            "invalid_hardware_driver": bind(H.HARDWARE_SCRIPT),
            "screen_text": bind(FAILED_HW / "boot-screen.txt"),
            "screen_png": bind(FAILED_HW / "boot-screen.png"),
            "late_runtime_ZP": bind(FAILED_HW / "boot-zp-late.bin", 0x70),
            "late_fixed_state": bind(FAILED_HW / "boot-fixed-late.bin"),
        },
        "observation": {
            "screen": "E3e",
            "clean_REPL_reached": False,
            "test_form_sent": False,
            "threshold_capture_taken": False,
        },
        "attribution": {
            "class": "diagnostic-harness First Red",
            "cause": (
                "the one-byte Slot-39 payload patch invalidated its L65R-v4 "
                "payload/record/directory/header identities and the outer "
                "Link-62 session-family CRC"),
            "product_finding": False,
            "repair": (
                "preserve the executable one-byte patch; canonically rebind "
                "all derived v4 identities and solve the existing six-byte "
                "post-RTS tail back to family CRC 0x8d75"),
        },
        "execution_accounting": {
            "diagnostic_hardware_cycles_consumed": 1,
            "product_links": 0,
            "compiler_runs": 0,
            "latency_attempts_consumed": 0,
        },
        "claim_limit": (
            "Harness First Red only; no threshold, product, C1, matrix-gate, "
            "acceptance-chain, promotion or release claim."),
    }
    write_json(FAILED_RECEIPT, value)
    return value


def prepare() -> dict[str, Any]:
    source, _, base_deployment = H.validate_authority()
    require(sha(BASE_MANIFEST) == (
        "e718748ed519714952d5edbe79cf41bf7237825b2c37462e5ce951545c4f7702"),
        "Link-62 stage-bound manifest authority drift")
    require(sha(OVERFLOW) == (
        "38e5771ab7f6840d487715d473a63b8e3ea268a23c6993928be7535152ad7b6b"),
        "Link-62 overflow authority drift")
    first_red = bind_first_red()
    tail, candidate = solve_tail(source)
    gate = mutation_gate(source, candidate)
    write_exact(PATCHED_CARRIER, candidate)

    manifest = {
        "format": "lisp65-Link62-slot39-threshold-hold2-manifest-v1",
        "status": "ready-nonpromotable-rebound-threshold-hold",
        "promotable": False,
        "source": bind(H.BASE_CARRIER, 0x08000000),
        "candidate": bind(PATCHED_CARRIER, 0x08000000),
        "patch_and_rebinding": gate,
        "solved_post_RTS_tail": {
            "bytes_little_endian": list(tail),
            "hex": tail.hex(),
            "width": len(tail),
        },
    }
    write_json(PATCH_MANIFEST, manifest)
    receipt = {
        "format": "lisp65-c2.2-Link62-slot39-threshold-hold2-patch-v1",
        "recorded_on": "2026-07-24",
        "status": "passed-rebound-nonpromotable-threshold-hold-hardware-not-run",
        "promotable": False,
        "authority": {
            "host_ELF_attribution": bind(H.ATTRIBUTION),
            "original_hardware_First_Red": bind(H.FIRST_RED),
            "diagnostic_harness_First_Red": bind(FAILED_RECEIPT),
            "source_carrier": bind(H.BASE_CARRIER, 0x08000000),
            "source_deployment": bind(H.BASE_DEPLOYMENT),
            "stage_bound_manifest": bind(BASE_MANIFEST),
            "overflow_region": bind(OVERFLOW, 0x08300000),
            "driver": bind(Path(__file__)),
            "hardware_driver": bind(HARDWARE_SCRIPT),
        },
        "candidate": {
            "carrier": bind(PATCHED_CARRIER, 0x08000000),
            "manifest": bind(PATCH_MANIFEST),
            "identity_separate_from_Link62_and_failed_diagnostic": True,
            "lifecycle": "nonpromotable; discard after diagnostic capture",
        },
        "patch_and_rebinding": gate,
        "construction": {
            "product_bytes_changed": 0,
            "carrier_size_delta": 0,
            "executable_operand_bytes_changed": 1,
            "compiler_runs": 0,
            "linker_runs": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "Nonpromotable diagnostic identity only; no product, C1, "
            "matrix-gate, acceptance-chain, promotion or release claim."),
    }
    write_json(PATCH_RECEIPT, receipt)

    preloads = []
    replaced = 0
    for row in base_deployment["preloads"]:
        copy = dict(row)
        if copy["sha256"] == H.SOURCE_SHA:
            copy = bind(PATCHED_CARRIER, int(copy["address"], 16))
            replaced += 1
        preloads.append(copy)
    require(replaced == 1, "source deployment does not uniquely name carrier")
    deployment = {
        "format": "lisp65-c2.2-Link62-slot39-threshold-hold2-hardware-v1",
        "recorded_on": "2026-07-24",
        "status": "ready-nonpromotable-rebound-threshold-hold-hardware",
        "promotable": False,
        "authority": {
            "patch_receipt": bind(PATCH_RECEIPT),
            "patch_manifest": bind(PATCH_MANIFEST),
            "source_deployment": bind(H.BASE_DEPLOYMENT),
            "hardware_driver": bind(HARDWARE_SCRIPT),
        },
        "product": base_deployment["product"],
        "preloads": preloads,
        "test": {
            "form": "(defun %c1e () 't)",
            "hold_VMA": f"0x{H.INSTRUCTION_VMA:04x}",
            "timeout_frames": H.TIMEOUT_FRAMES,
            "capture_intervals_seconds": [0, 1, 5],
            "capture_count": 3,
        },
        "capture_domains": load_json(H.DEPLOYMENT)["capture_domains"],
        "execution_accounting": {
            "diagnostic_hardware_cycles_consumed_before_this_identity": 1,
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs": 0,
            "latency_attempts_consumed": 0,
        },
        "claim_limit": receipt["claim_limit"],
    }
    write_json(DEPLOYMENT, deployment)
    return {
        "status": "ready-rebound",
        "carrier_sha256": sha(PATCHED_CARRIER),
        "family_crc16": gate["family_crc16"],
        "mutations": gate["mutation_count"],
    }


def verify() -> dict[str, Any]:
    source, _, base_deployment = H.validate_authority()
    candidate = regular(PATCHED_CARRIER)
    gate = mutation_gate(source, candidate)
    manifest = load_json(PATCH_MANIFEST)
    receipt = load_json(PATCH_RECEIPT)
    deployment = load_json(DEPLOYMENT)
    require(
        manifest["candidate"]["sha256"] == sha(PATCHED_CARRIER)
        and receipt["candidate"]["carrier"]["sha256"] == sha(PATCHED_CARRIER)
        and deployment["product"] == base_deployment["product"]
        and deployment["status"]
            == "ready-nonpromotable-rebound-threshold-hold-hardware",
        "successor diagnostic binding drift")
    for row in deployment["preloads"]:
        path = ROOT / row["path"]
        require(
            len(regular(path)) == row["bytes"] and sha(path) == row["sha256"],
            f"successor preload drift: {path}")
    return {
        "status": "verified-rebound",
        "carrier_sha256": sha(PATCHED_CARRIER),
        "family_crc16": gate["family_crc16"],
        "mutations": gate["mutation_count"],
    }


def evaluate() -> dict[str, Any]:
    # Reuse the already-bound witness evaluator; only its artifact namespace
    # changes.  The source tool itself remains byte-identical for its First Red.
    H.verify = verify
    H.PATCH_RECEIPT = PATCH_RECEIPT
    H.DEPLOYMENT = DEPLOYMENT
    H.PATCHED_CARRIER = PATCHED_CARRIER
    H.HW_OUT = HW_OUT
    H.HARDWARE_RECEIPT = HARDWARE_RECEIPT
    H.OUT = OUT
    H.__file__ = str(Path(__file__))
    value = H.evaluate()
    value["format"] = (
        "lisp65-c2.2-Link62-slot39-threshold-hold2-hardware-v1")
    value["authority"]["diagnostic_harness_First_Red"] = bind(FAILED_RECEIPT)
    value["execution_accounting"]["diagnostic_hardware_runs"] = 2
    value["execution_accounting"][
        "failed_harness_cycles_before_answer"] = 1
    value["diagnostic_lifecycle"]["state"] = (
        "successor-identity-discarded-after-capture")
    # H.evaluate wrote once; rewrite only if its exact successor enrichment is
    # not present yet.
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if HARDWARE_RECEIPT.exists():
        os.chmod(HARDWARE_RECEIPT, 0o644)
        HARDWARE_RECEIPT.write_bytes(data)
        os.chmod(HARDWARE_RECEIPT, 0o444)
    else:
        write_exact(HARDWARE_RECEIPT, data)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "verify", "evaluate"))
    args = parser.parse_args()
    if args.action == "prepare":
        value = prepare()
    elif args.action == "verify":
        value = verify()
    else:
        value = evaluate()
    print(
        "c2-link62-slot39-threshold-hold2: "
        + str(value.get("status", "ok")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RebindError, H.HoldError, R.OverlayBankError, OSError, ValueError,
            KeyError, json.JSONDecodeError) as error:
        print("c2-link62-slot39-threshold-hold2: FIRST RED: " + str(error))
        raise SystemExit(2)
