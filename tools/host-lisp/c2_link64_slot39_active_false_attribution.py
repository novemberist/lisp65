#!/usr/bin/env python3
"""Attribute the Link-64 first-ACTIVE-poll false return at linked ELF level."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402


TOOLS = ROOT / "tools/llvm-mos/bin"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PRODUCT = ROOT / (
    "build/c2.2/substitution/"
    "link64-nonlto-stateless-completion-length-artifact-replay")
DONOR = ROOT / (
    "build/c2.2/substitution/"
    "link64-c1-freezer-cutpoints-WPLTO-donor-NONPROMOTABLE")
PRODUCT_ELF = PRODUCT / "lisp65-c2-substitution-linked.prg.elf"
DONOR_ELF = DONOR / "lisp65-c2-substitution-linked.prg.elf"
PRODUCT_SOURCE = PRODUCT / "generated-product-sources/c2_product_runtime.c"
DONOR_SOURCE = DONOR / "generated-product-sources/c2_product_runtime.c"
FIRST_RED = EVIDENCE / (
    "c2.2-link64-slot39-ACTIVE-return-hardware-first-red.json")
ENTRY = EVIDENCE / "c2.2-link64-slot39-entry-hold-hardware-receipt.json"
PRETHRESHOLD = EVIDENCE / (
    "c2.2-link64-slot39-prethreshold-hardware-first-red.json")
LENGTH_GATE = EVIDENCE / (
    "c2.2-link64-c1-donor-completion-phase-context-replay-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-link64-slot39-ACTIVE-false-host-ELF-attribution.json")

HEADER_SECTION = ".lisp65_rt_c2append_header"
REGION_BYTES = 50816
UNWIND_BASE = 50752
UNWIND_BYTES = 64


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def data(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink(),
            f"authority absent or not regular: {path}")
    return path.read_bytes()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    value = data(path)
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(value),
        "sha256": sha_bytes(value),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(data(path))
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def symbol_body(truth: ElfTruth, name: str) -> tuple[Any, bytes]:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    start = symbol.value - section.address
    body = truth.section_bytes(symbol.section)[start:start + symbol.bytes]
    require(symbol.bytes and len(body) == symbol.bytes,
            f"invalid sized symbol: {name}")
    return symbol, body


def bytes_at(truth: ElfTruth, section_name: str, address: int,
             length: int) -> bytes:
    section = truth.section(section_name)
    start = address - section.address
    value = truth.section_bytes(section_name)[start:start + length]
    require(0 <= start and len(value) == length,
            f"address outside section: {address:#x}")
    return value


def main() -> int:
    first_red = load(FIRST_RED)
    entry = load(ENTRY)
    prethreshold = load(PRETHRESHOLD)
    length_gate = load(LENGTH_GATE)
    require(
        first_red["status"]
            == "FIRST RED: first ACTIVE completion poll returned false"
        and entry["answer"]["first_entry_mode"] == "0xa1 (ACTIVE)"
        and entry["answer"]["first_entry_journal_result"] == "2 (PREPARED)"
        and entry["answer"]["seal_matches"] is True
        and prethreshold["hardware_First_Red"]["threshold_hold_reached"]
            is False
        and length_gate["result"]["phase_call_contexts"]["call_count"] == 5
        and data(PRODUCT_SOURCE) == data(DONOR_SOURCE),
        "Link-64 ACTIVE-false attribution authority drift")

    product = ElfTruth.read(
        PRODUCT_ELF, llvm_readobj=TOOLS / "llvm-readobj",
        include_section_data=True)
    donor = ElfTruth.read(
        DONOR_ELF, llvm_readobj=TOOLS / "llvm-readobj",
        include_section_data=True)
    product_poll, product_body = symbol_body(product, "c2_completion_poll")
    donor_poll, donor_body = symbol_body(donor, "c2_completion_poll")
    reader, reader_body = symbol_body(donor, "c2_stream_c2d_read")
    mode_length, mode_body = symbol_body(
        donor, "c2_completion_mode_length")
    crc, crc_body = symbol_body(donor, "rtov_crc_mem")

    differences = [
        (index, left, right)
        for index, (left, right) in enumerate(zip(product_body, donor_body))
        if left != right
    ]
    expected_differences = {
        0x074: (0xb4, 0xf0),
        0x129: (0xb4, 0xf0),
        0x142: (0xb0, 0xec),
        0x14c: (0x59, 0x95),
        0x159: (0x8b, 0xc7),
        0x18d: (0xb0, 0xec),
        0x1bf: (0xa8, 0xe4),
        0x1e0: (0x59, 0x95),
    }
    require(
        product_poll.value == 0xc6ca and donor_poll.value == 0xc706
        and product_poll.bytes == donor_poll.bytes == 563
        and {index: (left, right) for index, left, right in differences}
            == expected_differences
        and all(((right - left) & 0xff) == 0x3c
                for _, left, right in differences),
        "product/donor completion-poll identity drift")

    # The current discriminator establishes a false return from the first
    # ACTIVE call.  The linked function has only three false exits: invalid
    # initial arguments/mode, a false reader return, or elapsed >= 64 frames.
    # Entry state and the mode leaf exclude the first one.
    require(
        bytes_at(donor, HEADER_SECTION, 0xc772, 10)
            == bytes.fromhex("1a2056c3aad0034cf0c8")
        and bytes_at(donor, HEADER_SECTION, 0xc814, 31)
            == bytes.fromhex(
                "1f2056c38506a61a8604a61b86056407"
                "a621a5202091e6aad0034cf0c8a51f")
        and bytes_at(donor, HEADER_SECTION, 0xc8b4, 16)
            == bytes.fromhex("e51cd006a604e0408002c900a51fb02c")
        and bytes_at(donor, HEADER_SECTION, 0xc8c0, 7)
            == bytes.fromhex("a51fb02c4ce4c7"),
        "linked false-exit sequences drift")
    require(
        mode_body == bytes.fromhex(
            "c9a19012c9a5b00ec9a2f005a940a30060"
            "a930a30060a900a30060")
        and reader.value == 0xe691 and reader.bytes == 87
        and crc.value == 0x222d and crc.bytes == 74
        and len(reader_body) == 87 and len(crc_body) == 74,
        "mode-length, reader or CRC leaf identity drift")

    # For ACTIVE, the linked caller passes (offset=$c640, dst=observed,
    # length=64).  The reader's exact bounds predicate accepts equality at
    # the end of the 50,816-byte region.
    require(
        UNWIND_BASE + UNWIND_BYTES == REGION_BYTES
        and bytes_at(donor, HEADER_SECTION, 0xc81b, 17)
            == bytes.fromhex(
                "1a8604a61b86056407a621a5202091e6aa")
        and bytes.fromhex(
            "a200a40ac0c6d008a8c081900c4ce0e6") in reader_body
        and bytes.fromhex(
            "38a980e50b8508a9c6e50ac507d025") in reader_body
        and reader_body.endswith(bytes.fromhex(
            "20c4b5a2018a60c507b0dd80f8")),
        "ACTIVE reader argument or bounds proof drift")

    # A one-byte BNE-operand patch at the post-reader edge is the next exact
    # discriminator.  On success, the observed-buffer pointer remains live
    # in __rc24/__rc25 and must equal software-stack-base + 10.
    require(
        bytes_at(donor, HEADER_SECTION, 0xc828, 11)
            == bytes.fromhex("2091e6aad0034cf0c8a51f"),
        "post-reader discriminator site drift")

    value = {
        "format":
            "lisp65-c2.2-Link64-slot39-ACTIVE-false-"
            "host-ELF-attribution-v1",
        "recorded_on": "2026-07-26",
        "status":
            "first ACTIVE false narrowed to reader-return or timeout/nonmatch",
        "promotable": False,
        "scope": {
            "class": "read-only-host-ELF-attribution",
            "product_bytes_changed": 0,
            "compiler_runs": 0,
            "linker_runs": 0,
            "hardware_runs": 0,
        },
        "authority": {
            "hardware_First_Red": bind(FIRST_RED),
            "first_entry_receipt": bind(ENTRY),
            "earlier_threshold_run": bind(PRETHRESHOLD),
            "mode_length_gate": bind(LENGTH_GATE),
            "product_ELF": bind(PRODUCT_ELF),
            "diagnostic_donor_ELF": bind(DONOR_ELF),
            "product_generated_runtime": bind(PRODUCT_SOURCE),
            "donor_generated_runtime": bind(DONOR_SOURCE),
            "attribution_driver": bind(Path(__file__)),
        },
        "linked_identity": {
            "generated_runtime_sources_byteidentical": True,
            "product_poll": {
                "VMA": f"0x{product_poll.value:04x}",
                "bytes": product_poll.bytes,
            },
            "diagnostic_donor_poll": {
                "VMA": f"0x{donor_poll.value:04x}",
                "bytes": donor_poll.bytes,
            },
            "semantic_body_identity": (
                "byteidentical after the eight internal section-local target "
                "low bytes are rebased by the measured +0x3c VMA shift"),
            "raw_difference_count": len(differences),
            "raw_differences": [
                {
                    "body_offset": f"0x{index:03x}",
                    "product_byte": f"0x{left:02x}",
                    "donor_byte": f"0x{right:02x}",
                }
                for index, left, right in differences
            ],
        },
        "false_return_partition": {
            "initial_argument_or_mode_rejection": {
                "false_exit_VMA": "0xc779",
                "excluded": True,
                "reason": (
                    "the entry hold proved a non-null state pointer and "
                    "ACTIVE mode $a1; the 27-byte leaf maps $a1 to 64"),
            },
            "reader_returned_zero": {
                "reader_call_VMA": "0xc828",
                "return_test_VMA": "0xc82c",
                "false_exit_VMA": "0xc82e",
                "excluded": False,
                "static_arguments": {
                    "Bank": 5,
                    "offset": "0xc640",
                    "length": 64,
                    "destination": "poll-local observed[64]",
                },
                "static_bounds_result": (
                    "$c640 + 64 == $c680 == region end; accepted"),
            },
            "content_nonmatch_until_timeout": {
                "CRC_call_VMA": "0xc86d",
                "CRC_leaf": "rtov_crc_mem",
                "timeout_branch_VMA": "0xc8c2",
                "timeout_frames": 64,
                "excluded": False,
            },
        },
        "earlier_threshold_receipt_qualification": {
            "historical_receipt_modified": False,
            "qualification": (
                "its non-hit is true only for that earlier execution. The "
                "current ACTIVE-return run is a separate intermittent "
                "execution, so the earlier non-hit cannot exclude timeout "
                "from the current false return."),
        },
        "next_minimal_discriminator": {
            "name": "post-reader-return plus observed-buffer hold",
            "instruction_VMA": "0xc82c",
            "before": "BNE $c831 (d0 03)",
            "after": "BNE $c82c (d0 fe)",
            "executable_operand_bytes_changed": 1,
            "all_capacity_deltas": 0,
            "outcomes": {
                "bad_bytecode": (
                    "c2_stream_c2d_read returned zero despite the linked "
                    "end-of-region-equality bounds"),
                "hang": (
                    "reader returned nonzero; capture __rc0/__rc1 and "
                    "__rc24/__rc25, require observed == stack_base + 10, "
                    "then read 64 observed bytes three times"),
            },
            "hang_capture_interpretation": {
                "wrong_then_correct": "Chip-read visibility/convergence",
                "stable_wrong_or_poison": "source/destination/read divergence",
                "stable_byteidentical_to_C2J": (
                    "reader path exonerated; CRC/seal comparison is next"),
            },
            "hardware_authorized": False,
        },
        "answer": {
            "proven": (
                "the first ACTIVE poll itself returned false; initial "
                "argument/mode rejection is excluded"),
            "remaining_exact_partition": [
                "the linked Bank-5 reader returned zero",
                "the reader returned nonzero but content never matched before "
                "the 64-frame timeout",
            ],
            "product_fix_justified": False,
        },
        "claim_limit": (
            "Host/ELF attribution and next-diagnostic feasibility only. "
            "C1 remains OPEN; no hardware, product, acceptance or promotion "
            "claim."),
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-link64-slot39-ACTIVE-false-attribution: PASS "
        "remaining=reader-zero|timeout-nonmatch next=c82c")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-link64-slot39-ACTIVE-false-attribution: FIRST RED: "
            + str(error))
        raise SystemExit(2)
