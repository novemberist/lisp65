#!/usr/bin/env python3
"""Bind the Link-62 Slot-39 non-return to its live-length corruption.

This is a pure replay over the already captured nonpromotable hardware
identity.  It adds no product bytes and performs no compiler, linker, packer
or hardware run.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
HW = ROOT / (
    "build/c2.2/hardware-link62-slot39-threshold-hold2-NONPROMOTABLE")
DONOR = ROOT / (
    "build/c2.2/substitution/"
    "link60-c1-freezer-cutpoints-WPLTO-donor-NONPROMOTABLE")
ELF = DONOR / "lisp65-c2-substitution-linked.prg.elf"
SOURCE = DONOR / "generated-product-sources/c2_product_runtime.c"
PRIOR = EVIDENCE / (
    "c2.2-link62-slot39-threshold-hold-hardware-receipt.json")
PATCH_RECEIPT = EVIDENCE / (
    "c2.2-link62-slot39-threshold-hold2-nonpromotable-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link62-slot39-threshold-length-liveness-replay-receipt.json")

VMA = 0xC356
CALLSITE = 0xC403
PROLOGUE = 0xC747
RETRY_TEST = 0xC7D2
READ_CALL = 0xC7F6
POISON_LOOP = 0xC82E
TIMEOUT_SAMPLE = 0xC8A2
THRESHOLD_BRANCH = 0xC8CA


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def regular(path: Path) -> bytes:
    info = path.lstat()
    require(
        stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode),
        f"not a regular symlink-free file: {path}")
    return path.read_bytes()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def section_at(section: bytes, address: int, length: int) -> bytes:
    start = address - VMA
    require(
        0 <= start and start + length <= len(section),
        f"address outside captured Slot 39: {address:#06x}")
    return section[start:start + length]


def write_json(path: Path, value: dict[str, Any]) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(regular(path) == data, f"generated evidence differs: {path}")
        return
    path.write_bytes(data)
    os.chmod(path, 0o444)


def build() -> dict[str, Any]:
    prior = json.loads(regular(PRIOR))
    pc = json.loads(regular(HW / "pc-captures.json"))
    section = regular(HW / "runtime-slot39.bin")
    source = regular(SOURCE).decode("utf-8")
    zp_paths = [HW / f"poll-zp-late-{index}.bin" for index in range(1, 4)]
    zp_rows = [regular(path) for path in zp_paths]

    require(
        prior["status"]
            == "completed-no-threshold-hold-inner-attempt-does-not-return"
        and len(section) == 1526
        and len(zp_rows) == 3
        and all(len(row) == 34 for row in zp_rows),
        "prior receipt or late-capture geometry drift")
    require(
        "for (i = 0; i < length; ++i)" in source
        and "c2_stream_c2d_read(" in source
        and "C2_CHIP_WRITE_COMPLETION_TIMEOUT_FRAMES" in source,
        "completion-poll source intent drift")

    # Rollback-reentry callsite: X=$40 and __rc6=$00 encode length $0040.
    require(
        section_at(section, CALLSITE, 25)
            == bytes.fromhex(
                "a2406408a4168404a4178405a9a3a0008406a000840720ffc6"),
        "rollback-reentry callsite no longer passes length $0040")

    # The linked function saves the two length bytes in __rc30/__rc20.
    require(
        section_at(section, PROLOGUE, 6)
            == bytes.fromhex("8620a6088616"),
        "linked length storage drift")

    # Retry tests __rc20 first and __rc30 only when its high byte is zero.
    require(
        section_at(section, RETRY_TEST, 20)
            == bytes.fromhex("a6208606a516f0034c2ec8a620e408f0034c2ec8"),
        "linked retry-length test drift")
    require(
        section_at(section, READ_CALL, 3) == bytes.fromhex("2091e6")
        and section_at(section, POISON_LOOP, 40)
            == bytes.fromhex(
                "a2008604a2008605a61be405d00ca61ae404d006"
                "a9a5a4088006a9ffa408511a911cc884084cd6c7")
        and section_at(section, TIMEOUT_SAMPLE, 3)
            == bytes.fromhex("ac84ff")
        and section_at(section, THRESHOLD_BRANCH, 2)
            == bytes.fromhex("b0fe"),
        "linked read/poison/timeout/hold sequence drift")

    pcs = [int(row["PC"], 16) for row in pc["rows"]]
    require(
        pcs == [0xC848, 0xC84C, 0xC850],
        "bound PC samples drift")

    decoded = []
    for index, row in enumerate(zp_rows, 1):
        decoded.append({
            "index": index,
            "poison_index_low___rc6": f"0x{row[0x08]:02x}",
            "live_length_high___rc20": f"0x{row[0x16]:02x}",
            "poll_start_high___rc21": f"0x{row[0x17]:02x}",
            "poll_start_low___rc28": f"0x{row[0x1e]:02x}",
            "live_length_low___rc30": f"0x{row[0x20]:02x}",
        })
    require(
        [row[0x08] for row in zp_rows] == [0xEC, 0xF8, 0x37]
        and all(row[0x16] == 0xBB for row in zp_rows)
        and all(row[0x20] == 0x04 for row in zp_rows)
        and all(row[0x17] == 0x05 and row[0x1E] == 0xC8
                for row in zp_rows),
        "late live-state witnesses drift")

    value = {
        "format":
            "lisp65-c2.2-Link62-slot39-threshold-length-liveness-replay-v1",
        "recorded_on": "2026-07-24",
        "status": "FIRST RED: retry length clobbered before timeout boundary",
        "promotable": False,
        "authority": {
            "prior_hardware_receipt": bind(PRIOR),
            "diagnostic_patch_receipt": bind(PATCH_RECEIPT),
            "donor_ELF": bind(ELF),
            "generated_runtime_source": bind(SOURCE),
            "runtime_Slot39_capture": bind(HW / "runtime-slot39.bin", VMA),
            "PC_captures": bind(HW / "pc-captures.json"),
            "late_ZP_captures": [bind(path, 0) for path in zp_paths],
            "evaluator": bind(Path(__file__)),
        },
        "linked_dataflow": {
            "rollback_reentry_callsite": {
                "address": "0xc403",
                "length_argument": "0x0040",
                "proof": "LDX #$40; STZ __rc6 before JSR $c6ff",
            },
            "poll_entry": {
                "address": "0xc747",
                "length_storage": {
                    "low": "__rc30/$20",
                    "high": "__rc20/$16",
                },
            },
            "nested_reader": {
                "address": "0xc7f6",
                "target": "c2_stream_c2d_read/$e691",
            },
            "retry_guard": {
                "address": "0xc7d6",
                "rule": (
                    "nonzero __rc20 jumps directly into the poison loop; "
                    "__rc30 is compared only when __rc20 is zero"),
            },
            "timeout_boundary": {
                "sample_address": "0xc8a2",
                "patched_threshold_branch": "0xc8ca",
                "reachable_only_after_poison/read/verify body returns": True,
            },
        },
        "time_separated_live_state": decoded,
        "time_separated_PCs": [f"0x{value:04x}" for value in pcs],
        "finding": {
            "entry_length": "0x0040",
            "observed_retry_length": "0xbb04",
            "poison_loop_is_live": True,
            "timeout_boundary_reached": False,
            "producer_target_seal_divergence": False,
            "root_cause": (
                "the linked poll retains length in __rc20/__rc30 across the "
                "nested Bank-5 read path; by the retry those live bytes are "
                "$bb/$04 rather than the callsite's $00/$40.  Because the "
                "high byte is nonzero, the poison loop cannot terminate and "
                "control never reaches the 64-frame timeout sample"),
            "classification": (
                "product/linked-code ABI-liveness defect across the nested "
                "read call, not a producer-seal mismatch, poll-start error, "
                "frame-counter stall or timeout-arithmetic error"),
        },
        "required_product_decision": {
            "class": "C",
            "narrow_fix_direction": (
                "preserve or reload the canonical length across every nested "
                "read attempt, then pin a mutation that clobbers call-scratch "
                "state and still requires timeout-or-convergence fail-closed"),
            "implemented_here": False,
            "upstream_claim": (
                "not made; a minimal compiler/ABI reproduction is required "
                "before attributing the defect outside this linked product"),
        },
        "execution_accounting": {
            "new_hardware_runs": 0,
            "new_product_links": 0,
            "new_compiler_runs": 0,
            "product_bytes_changed": 0,
            "latency_attempts_consumed": 0,
            "operation": "pure replay against read-only captures",
        },
        "claim_limit": (
            "Diagnostic root-cause attribution only; no product fix, C1 "
            "closure, matrix-gate, acceptance-chain, promotion or release "
            "claim."),
    }
    write_json(RECEIPT, value)
    return value


def main() -> int:
    value = build()
    print(value["status"])
    print(RECEIPT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print("c2-link62-slot39-length-liveness: FIRST RED: " + str(error))
        raise SystemExit(2)
