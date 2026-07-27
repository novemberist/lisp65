#!/usr/bin/env python3
"""Attribute Link-64 completion poison/read/CRC operands and retry order."""

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
ELF = DONOR / "lisp65-c2-substitution-linked.prg.elf"
SOURCE = DONOR / "generated-product-sources/c2_product_runtime.c"
CONTRACT = ROOT / "config/c2-cpu-chip-write-completion-contract.json"
ENTRY = EVIDENCE / "c2.2-link64-slot39-entry-hold-hardware-receipt.json"
FINAL = EVIDENCE / (
    "c2.2-link64-reader-zero-bounds-composite-hardware-first-red.json")
POSTREAD = EVIDENCE / (
    "c2.2-link64-completion-postread-timeout-host-ELF-attribution.json")
LATE_WRITE = EVIDENCE / (
    "c2.2-link59-C1-Freezer-cutpoint4-late-chip-write-"
    "hardware-first-red.json")
RECEIPT = EVIDENCE / (
    "c2.2-link64-completion-poison-operands-host-ELF-attribution.json")

HEADER = ".lisp65_rt_c2append_header"
WINDOW = ".lisp65_c2_kernal_window.c2_resident"
REOPEN = ".lisp65_c2_kernal_window.reopen_gap2"


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


def delayed_read_counterexample(attempts: int = 64) -> dict[str, Any]:
    """Model a read which becomes visible between two immediate attempts."""
    expected = bytes(range(64))
    poison = bytes([0xa5]) * 64
    observed = poison
    pending: bytes | None = None
    matches = 0
    late_results_erased = 0
    for _ in range(attempts):
        if pending is not None:
            observed = pending
        if observed == expected:
            late_results_erased += 1
        observed = poison
        pending = expected
        if observed == expected:
            matches += 1
    if pending is not None:
        observed = pending
    return {
        "attempts": attempts,
        "matches_during_poll": matches,
        "late_correct_results_erased_before_compare": late_results_erased,
        "observed_correct_after_last_delayed_delivery":
            observed == expected,
    }


def single_submit_model() -> dict[str, Any]:
    expected = bytes(range(64))
    observed = bytes([0xa5]) * 64
    pending = expected
    first_compare_matches = observed == expected
    observed = pending
    second_compare_matches = observed == expected
    return {
        "poison_count": 1,
        "read_submit_count": 1,
        "first_compare_matches": first_compare_matches,
        "second_compare_after_delivery_matches": second_compare_matches,
    }


def main() -> int:
    entry = load(ENTRY)
    final = load(FINAL)
    postread = load(POSTREAD)
    contract = load(CONTRACT)
    late_write = load(LATE_WRITE)
    require(
        entry["answer"]["first_entry_mode"] == "0xa1 (ACTIVE)"
        and entry["answer"]["seal_matches"] is True
        and entry["answer"]["producer_seal"] == "0x2801"
        and final["status"]
            == "FIRST RED: reader succeeded; completion failed later"
        and postread["status"].startswith(
            "COMPLETE: successful ACTIVE reader")
        and contract["completion"]["readback_rule"].endswith(
            "poisoned unequal before every target read")
        and late_write["causal_attribution"]["mechanism"][0].startswith(
            "c2_stream_c2d_write returns success immediately"),
        "attribution authority drift")

    truth = ElfTruth.read(
        ELF, llvm_readobj=TOOLS / "llvm-readobj",
        include_section_data=True)
    poll, poll_body = symbol_body(truth, "c2_completion_poll")
    reader, reader_body = symbol_body(truth, "c2_stream_c2d_read")
    code_load, code_load_body = symbol_body(truth, "vm_code_load")
    dma, dma_body = symbol_body(truth, "c2_facade_target_c2_dma")
    crc, crc_body = symbol_body(truth, "rtov_crc_mem")
    phase_scratch = truth.symbol("lisp65_c2_phase_scratch")
    stack = truth.symbol("__stack")
    runtime_stack = truth.symbol(
        "__lisp65_workbench_required_runtime_stack")
    require(
        poll.value == 0xc706 and poll.bytes == 563 and poll.section == HEADER
        and reader.value == 0xe691 and reader.bytes == 87
        and reader.section == WINDOW
        and code_load.value == 0x2456 and code_load.bytes == 38
        and dma.value == 0xff90 and dma.bytes == 68 and dma.section == REOPEN
        and crc.value == 0x222d and crc.bytes == 74
        and sha_bytes(poll_body)
            == "3e9c4633182ba3983ba01fcd8e9017045d4da7be0bf488a5a658b3c5afb160e3"
        and sha_bytes(reader_body)
            == "d4bdb0340028893c980ef68ada56b973db526578434289a503e6a2f85973b1ad"
        and sha_bytes(code_load_body)
            == "6ecb3ff0176a759a065fa537c1c18390c76ead57ddfd6438adc29dce357c2b9e"
        and sha_bytes(dma_body)
            == "1eab33b719563c59e57b1c08e178ba541fad0a881c05c1f17832720e28bf679f"
        and sha_bytes(crc_body)
            == "6c53c1d1841cab65352cf611376dd5fe54335405fa083be1c29480970d36a5de",
        "linked symbol identity drift")

    # Poll-local observed[64] is software_stack_base + 10.  Poison writes
    # through that pointer; the Bank-5 reader receives the same pointer in
    # __rc2/__rc3; CRC receives it again after the reader returns.
    require(
        bytes_at(truth, HEADER, 0xc7d1, 13)
            == bytes.fromhex("18a502690a851aa5036900851b")
        and bytes_at(truth, HEADER, 0xc7ee, 7)
            == bytes.fromhex("a9ff5118911ac8")
        and bytes_at(truth, HEADER, 0xc809, 10)
            == bytes.fromhex("a518c504d0dfa9a580df")
        and bytes_at(truth, HEADER, 0xc813, 24)
            == bytes.fromhex(
                "a51f2056c38506a61a8604a61b86056407a621a5202091e6")
        and bytes_at(truth, HEADER, 0xc861, 15)
            == bytes.fromhex("a61a8604a61b8605a200a51d202d22"),
        "poison/read/CRC observed-pointer chain drift")

    # w is preserved in __rc20/__rc21.  record starts at +$b6 and its seal at
    # record[25], hence +$cf/+d0 == fixed $c195/$c196.
    require(
        phase_scratch.value == 0xc0c6 and phase_scratch.bytes == 304
        and 0xc0c6 + 0xcf == 0xc195
        and bytes_at(truth, HEADER, 0xc872, 30)
            == bytes.fromhex(
                "a5161869cf8504a51769008505a0018ad104d00fa0cfb1168504a506c504")
        and stack.value == 0xd000 and runtime_stack.value == 0x05aa
        and stack.value - runtime_stack.value == 0xca56
        and phase_scratch.value + phase_scratch.bytes == 0xc1f6,
        "producer-seal or stack/scratch identity drift")

    # Reader arguments are Bank 5, offset $c640, destination observed in Bank
    # 0, length 64.  The reader and vm_code_load only submit the DMA job.
    require(
        bytes_at(truth, WINDOW, 0xe6c3, 31)
            == bytes.fromhex(
                "a905a6048608a6058609a60a8604a6068605a6078606a60b20c4b5a2018a60")
        and code_load_body.endswith(bytes.fromhex("98 4c c7 b5"))
        and dma_body[-16:]
            == bytes.fromhex("a9008d02d7a9b98d01d7a9b98d00d760"),
        "Bank-5 reader submission chain drift")

    # The timeout retry returns to $c7e4.  That address precedes both the
    # poison loop and the reader submission, so every retry first erases a
    # result which may have landed after the preceding immediate comparison.
    require(
        bytes_at(truth, HEADER, 0xc8b4, 19)
            == bytes.fromhex(
                "e51cd006a604e0408002c900a51fb02c4ce4c7"),
        "retry edge drift")

    counterexample = delayed_read_counterexample()
    fixed_model = single_submit_model()
    require(
        counterexample == {
            "attempts": 64,
            "matches_during_poll": 0,
            "late_correct_results_erased_before_compare": 63,
            "observed_correct_after_last_delayed_delivery": True,
        }
        and fixed_model["poison_count"] == 1
        and fixed_model["read_submit_count"] == 1
        and fixed_model["first_compare_matches"] is False
        and fixed_model["second_compare_after_delivery_matches"] is True,
        "asynchronous read counterexample drift")

    source = data(SOURCE).decode("utf-8")
    common_start = source.index("static uint8_t c2_completion_poll")
    common = source[
        common_start:
        source.index(
            "#ifdef LISP65_C2_LITE_V6_PUBLISH_CLEAR_CORESIDENT",
            common_start)]
    require(
        common.index("do {") < common.index("observed[i] = expected")
        < common.index("c2_stream_c2d_read(")
        < common.index("c2_completion_c2j_matches")
        and common.count("c2_stream_c2d_read(") == 1,
        "generated retry ordering drift")

    value = {
        "format":
            "lisp65-c2.2-Link64-completion-poison-operands-"
            "host-ELF-attribution-v1",
        "recorded_on": "2026-07-26",
        "status":
            "FIRST RED: operands correct; retry re-poisons a potentially "
            "late read result before comparison",
        "promotable": False,
        "scope": {
            "class": "Class-C read-only host/ELF attribution",
            "product_bytes_changed": 0,
            "compiler_runs": 0,
            "linker_runs": 0,
            "hardware_runs": 0,
        },
        "authority": {
            "first_ACTIVE_entry_hardware": bind(ENTRY),
            "final_reader_success_hardware": bind(FINAL),
            "postreader_timeout_attribution": bind(POSTREAD),
            "late_Chip_write_hardware": bind(LATE_WRITE),
            "completion_contract_v6": bind(CONTRACT),
            "linked_ELF": bind(ELF),
            "generated_runtime": bind(SOURCE),
            "attribution_driver": bind(Path(__file__)),
        },
        "operand_attribution": {
            "poison_destination": {
                "machine_value": "poll-local observed = software stack + 10",
                "pointer_cells": "__rc24/__rc25",
                "store": "STA (__rc24),Y at $c7f2",
            },
            "target_read": {
                "source": "Bank 5:$c640..$c67f",
                "destination":
                    "the same poll-local observed pointer in Bank 0",
                "call": "c2_stream_c2d_read at $c828",
            },
            "CRC_source": {
                "pointer": "the same poll-local observed pointer",
                "call": "rtov_crc_mem at $c86d",
            },
            "expected_CRC": {
                "source": "c2_append_state.record[25..26]",
                "fixed_address_for_current_state": "$c195/$c196",
                "linked_loads": "$c881 and $c888",
                "entry_value": "0x2801",
            },
            "alias_result": {
                "poison_aliases_reader_destination": True,
                "reader_destination_aliases_CRC_source": True,
                "poison_aliases_Bank5_target": False,
                "observed_aliases_producer_seal": False,
                "verdict": "all addresses match their intended roles",
            },
        },
        "ordering_attribution": {
            "DMA_submission": (
                "$ff90 writes the 12-byte job address to $d702/$d701/$d700 "
                "and returns immediately with RTS"),
            "retry_edge": "$c8c4 JMP $c7e4",
            "retry_order": [
                "rematerialize length",
                "poison the observed buffer",
                "submit Bank-5-to-Bank-0 read",
                "immediately CRC/compare the observed buffer",
                "on nonmatch retry before poison",
            ],
            "defect": (
                "If the submitted read becomes visible after the immediate "
                "comparison, the next attempt erases that correct late "
                "result before it can be compared. Repeating the read does "
                "not establish read completion and can reproduce the exact "
                "good-before / never-good-during / good-after signature."),
            "counterexample": counterexample,
        },
        "contract_correction": {
            "old": (
                "poison before every target read and resubmit the read on "
                "every retry"),
            "new": (
                "poison once, submit exactly one ordered trailing target "
                "read, then sample only the local observed buffer until "
                "content matches or the 64-frame timeout expires"),
            "ordering_property": (
                "the one read job remains ordered after all producer writes; "
                "its eventual delivery is the completion witness"),
            "corrected_model": fixed_model,
            "permanent_product_detail_witness_required": False,
        },
        "answer": {
            "desktop_attribution_overturned_an_operand_bug": False,
            "desktop_attribution_overturned_a_retry_order_bug": True,
            "product_fix_justified": True,
            "remaining_hardware_question": (
                "whether the single-submit/local-observation form completes "
                "Cutpoints 3 and 4 on the device"),
        },
        "governance": {
            "prior_Class_B_budget": "closed at 3/3",
            "this_step": "Class-C host attribution",
            "C1": "OPEN",
            "matrix_gate": "LOCKED",
            "acceptance_chain": "LOCKED",
            "latency_attempts_consumed": 0,
        },
        "claim_limit": (
            "This receipt proves linked operand identity and exposes a valid "
            "late-read counterexample in the retry order. Hardware must still "
            "qualify the corrected product; no C1, matrix, acceptance, "
            "promotion or release claim is made."),
    }
    encoded = (
        json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if RECEIPT.exists():
        require(data(RECEIPT) == encoded, "sealed attribution receipt drift")
    else:
        RECEIPT.write_bytes(encoded)
        RECEIPT.chmod(0o444)
    print(
        "c2-link64-completion-poison-operands: FIRST RED "
        "addresses=correct retry=self-repoison")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-link64-completion-poison-operands: FIRST RED: " + str(error))
        raise SystemExit(2)
