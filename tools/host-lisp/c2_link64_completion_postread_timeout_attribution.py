#!/usr/bin/env python3
"""Bind the Link-64 post-reader completion failure to the timeout exit."""

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
DONOR = ROOT / (
    "build/c2.2/substitution/"
    "link64-c1-freezer-cutpoints-WPLTO-donor-NONPROMOTABLE")
DONOR_ELF = DONOR / "lisp65-c2-substitution-linked.prg.elf"
DONOR_SOURCE = DONOR / "generated-product-sources/c2_product_runtime.c"
COMPOSITE = EVIDENCE / (
    "c2.2-link64-reader-zero-bounds-composite-hardware-first-red.json")
ENTRY = EVIDENCE / "c2.2-link64-slot39-entry-hold-hardware-receipt.json"
RECEIPT = EVIDENCE / (
    "c2.2-link64-completion-postread-timeout-host-ELF-attribution.json")

HEADER_SECTION = ".lisp65_rt_c2append_header"
POLL_BODY_SHA256 = (
    "3e9c4633182ba3983ba01fcd8e9017045d4da7be0bf488a5a658b3c5afb160e3")


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
    composite = load(COMPOSITE)
    entry = load(ENTRY)
    require(
        composite["status"]
            == "FIRST RED: reader succeeded; completion failed later"
        and composite["binary_discriminator"]["answer"].startswith(
            "c2_stream_c2d_read returned nonzero")
        and composite["hardware_evidence"]["zero_exit_was_not_taken"] is True
        and composite["hardware_evidence"]["postmortem"][
            "journal_result"] == "2 (PREPARED)"
        and composite["execution_accounting"][
            "commissioned_diagnostic_cycles_consumed"] == "3/3"
        and entry["answer"]["first_entry_mode"] == "0xa1 (ACTIVE)"
        and entry["answer"]["first_entry_journal_result"] == "2 (PREPARED)"
        and entry["answer"]["seal_matches"] is True,
        "hardware authority drift")

    truth = ElfTruth.read(
        DONOR_ELF, llvm_readobj=TOOLS / "llvm-readobj",
        include_section_data=True)
    poll, body = symbol_body(truth, "c2_completion_poll")
    mode_length, mode_body = symbol_body(
        truth, "c2_completion_mode_length")
    reader, reader_body = symbol_body(truth, "c2_stream_c2d_read")
    crc, crc_body = symbol_body(truth, "rtov_crc_mem")
    require(
        poll.value == 0xc706 and poll.bytes == 563
        and poll.section == HEADER_SECTION
        and sha_bytes(body) == POLL_BODY_SHA256,
        "completion-poll linked identity drift")
    require(
        mode_length.value == 0xc356 and mode_length.bytes == 27
        and reader.value == 0xe691 and reader.bytes == 87
        and crc.value == 0x222d and crc.bytes == 74
        and len(mode_body) == 27 and len(reader_body) == 87
        and len(crc_body) == 74,
        "completion dependency identity drift")

    # Reader return: zero goes directly to the common false result; nonzero
    # advances to content validation.
    require(
        bytes_at(truth, HEADER_SECTION, 0xc828, 12)
            == bytes.fromhex("2091e6aad0034cf0c8a51f20"),
        "post-reader branch drift")

    # CLEAR mismatch, CRC mismatch, and bytewise mismatch all converge at
    # $c895.  None produces the false return directly.
    require(
        bytes_at(truth, HEADER_SECTION, 0xc83e, 22)
            == bytes.fromhex(
                "a000aa8404e404d0034cecc8b11ac8c900f0f04c95c8")
        and bytes_at(truth, HEADER_SECTION, 0xc87f, 22)
            == bytes.fromhex(
                "a0018ad104d00fa0cfb1168504a506c504d0034cecc8")
        and bytes_at(truth, HEADER_SECTION, 0xc8df, 13)
            == bytes.fromhex(
                "a506d118f0e64c95c8a505d0e2"),
        "content comparison edge drift")

    # $c895 samples the stable frame count.  A nonmatch below 64 frames loops
    # to the poison/read/recompare body; only BCS at $c8c2 reaches false.
    require(
        bytes_at(truth, HEADER_SECTION, 0xc895, 18)
            == bytes.fromhex(
                "ac84ffad83ffae84ff8604c404d0f138485a")
        and bytes_at(truth, HEADER_SECTION, 0xc8b4, 19)
            == bytes.fromhex(
                "e51cd006a604e0408002c900a51fb02c4ce4c7")
        and bytes_at(truth, HEADER_SECTION, 0xc8ec, 8)
            == bytes.fromhex("a9018002a9008512"),
        "timeout or result edge drift")

    source = data(DONOR_SOURCE).decode("utf-8")
    require(
        "if (!c2_stream_c2d_read(" in source
        and "return 0u;" in source
        and "C2_CHIP_WRITE_COMPLETION_TIMEOUT_FRAMES" in source
        and "C2AW_JOURNAL_RESULT(w) = C2J_RESULT_ACTIVE;" in source,
        "generated completion source drift")

    value = {
        "format":
            "lisp65-c2.2-Link64-completion-postread-timeout-"
            "host-ELF-attribution-v1",
        "recorded_on": "2026-07-26",
        "status":
            "COMPLETE: successful ACTIVE reader followed by content "
            "nonmatch and 64-frame timeout",
        "promotable": False,
        "scope": {
            "class": "read-only-host-ELF-attribution",
            "product_bytes_changed": 0,
            "compiler_runs": 0,
            "linker_runs": 0,
            "hardware_runs": 0,
        },
        "authority": {
            "final_composite_hardware_First_Red": bind(COMPOSITE),
            "first_ACTIVE_entry_hardware_receipt": bind(ENTRY),
            "diagnostic_donor_ELF": bind(DONOR_ELF),
            "diagnostic_donor_generated_runtime": bind(DONOR_SOURCE),
            "attribution_driver": bind(Path(__file__)),
        },
        "linked_identity": {
            "completion_poll": {
                "section": poll.section,
                "VMA": f"0x{poll.value:04x}",
                "bytes": poll.bytes,
                "body_sha256": sha_bytes(body),
            },
            "reader": {
                "section": reader.section,
                "VMA": f"0x{reader.value:04x}",
                "bytes": reader.bytes,
            },
            "CRC_leaf": {
                "section": crc.section,
                "VMA": f"0x{crc.value:04x}",
                "bytes": crc.bytes,
            },
            "timeout_frames": 64,
        },
        "post_reader_control_flow": {
            "reader_call": "JSR $e691 at $c828",
            "reader_zero_exit": "JMP $c8f0 at $c82e",
            "reader_zero_excluded_by_hardware": True,
            "content_nonmatch_join": "$c895",
            "retry_edge": "JMP $c7e4 at $c8c4",
            "timeout_false_edge": "BCS $c8f0 at $c8c2",
            "success_result": "LDA #$01 at $c8ec",
            "false_result": "LDA #$00 at $c8f0",
            "only_post_reader_false_exit":
                "content comparison has not succeeded when elapsed reaches "
                "64 frames",
        },
        "hardware_interpretation": {
            "first_entry": {
                "mode": "0xa1 (ACTIVE)",
                "journal_result": "2 (PREPARED)",
                "producer_seal": "0x2801",
                "entry_target_crc16": "0x2801",
            },
            "final_cycle": {
                "reader_returned_nonzero": True,
                "journal_result_after_First_Red": "2 (PREPARED)",
                "meaning": (
                    "the ACTIVE transition never committed; its successful "
                    "reader was followed by no successful content comparison "
                    "before the timeout false return"),
            },
            "qualification": (
                "The matching entry capture proves the producer truth and "
                "target at that held entry. The final-cycle target was "
                "captured only after rollback and wipe, so it does not reveal "
                "which bytes the live poll observed during its timeout."),
        },
        "answer": {
            "disproved": [
                "offset-low bounds rejection",
                "offset-high bounds rejection",
                "length-low bounds rejection",
                "length-high bounds rejection",
                "any other zero return from c2_stream_c2d_read",
                "an immediate post-read false exit distinct from timeout",
            ],
            "proven": (
                "In the final diagnostic episode, the ACTIVE reader "
                "succeeded, content did not validate, and the linked poll "
                "returned false only through its 64-frame threshold."),
            "remaining_product_question": (
                "why the live ACTIVE target observation did not validate "
                "against the producer seal before the 64-frame threshold"),
            "product_fix_justified": False,
        },
        "governance": {
            "commissioned_diagnostic_cycles_consumed": "3/3",
            "further_Class_B_hardware_authorized": False,
            "next_step_class":
                "Class C product/contract review before any new witness or "
                "fix",
            "C1_matrix_status": "OPEN",
            "acceptance_chain_status": "LOCKED",
            "latency_attempts_consumed": 0,
        },
        "claim_limit": (
            "This receipt closes only the reader/bounds/false-exit "
            "attribution. It makes no product-fix, C1, acceptance, promotion "
            "or release claim."),
    }
    encoded = (
        json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if RECEIPT.exists():
        require(data(RECEIPT) == encoded, "sealed attribution receipt drift")
    else:
        RECEIPT.write_bytes(encoded)
        RECEIPT.chmod(0o444)
    print(
        "c2-link64-completion-postread-timeout-attribution: PASS "
        "reader=nonzero false=timeout cycles=3/3")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-link64-completion-postread-timeout-attribution: FIRST RED: "
            + str(error))
        raise SystemExit(2)
