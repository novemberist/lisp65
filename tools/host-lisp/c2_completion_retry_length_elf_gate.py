#!/usr/bin/env python3
"""Structured ELF gate for stateless, mode-derived completion length."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from elf_truth import ElfTruth, ElfTruthError


ROOT = Path(__file__).resolve().parents[2]
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
CONTRACT = ROOT / "config/c2-cpu-chip-write-completion-contract.json"
RECORD_OFFSET = 182
RETIRED_LENGTH_OFFSET = RECORD_OFFSET + 27
MODE_LENGTH_SECTION = ".lisp65_rt_c2append_header"
MODE_LENGTH_BODY = bytes.fromhex(
    "c9a19012c9a5b00ec9a2f005a940a30060a930a30060a900a30060")


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"gate authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def all_offsets(value: bytes, needle: bytes) -> list[int]:
    return [
        offset for offset in range(0, len(value) - len(needle) + 1)
        if value.startswith(needle, offset)
    ]


def u16(value: int) -> bytes:
    return bytes((value & 0xff, value >> 8))


def symbol_body(truth: ElfTruth, name: str) -> tuple[Any, bytes]:
    symbol = truth.symbol(name)
    require(symbol.bytes > 0, f"ELF symbol lacks bound size: {name}")
    section = truth.section(symbol.section)
    start = symbol.value - section.address
    body = truth.section_bytes(symbol.section)[start:start + symbol.bytes]
    require(len(body) == symbol.bytes, f"ELF extraction drift: {name}")
    return symbol, body


def immediate_offsets(body: bytes, value: int) -> list[int]:
    # LDA/LDX/LDY immediate are the only admitted constant materializers.
    return [
        offset for offset in range(len(body) - 1)
        if body[offset] in (0xa9, 0xa2, 0xa0)
        and body[offset + 1] == value
    ]


def jsr_offsets(body: bytes) -> list[int]:
    return [
        offset for offset in range(len(body) - 2)
        if body[offset] == 0x20
    ]


def absolute_jumps(body: bytes, base: int) -> list[tuple[int, int]]:
    return [
        (offset, body[offset + 1] | body[offset + 2] << 8)
        for offset in range(len(body) - 2)
        if body[offset] == 0x4c
        and base <= (body[offset + 1] | body[offset + 2] << 8)
            < base + len(body)
    ]


def audit_bodies(poll_body: bytes, poll_address: int, reader_address: int,
                 helper_body: bytes, helper_address: int,
                 retired_address: int) -> dict[str, Any]:
    helper_call = bytes((0x20, *u16(helper_address)))
    reader_call = bytes((0x20, *u16(reader_address)))
    helper_calls = all_offsets(poll_body, helper_call)
    reader_calls = all_offsets(poll_body, reader_call)
    require(
        len(helper_calls) == 4 and len(reader_calls) == 1,
        "linked poll does not retain initial plus three mode-length calls")
    pre_poison = helper_calls[1]
    reader = reader_calls[0]
    require(
        all(offset >= 2 and poll_body[offset - 2] == 0xa5
            for offset in (helper_calls[0], helper_calls[2], helper_calls[3])),
        "a direct mode-length call does not load its mode argument into A")

    # llvm-mos has emitted two equivalent storage forms.  The earlier form
    # copies the mode with LDA/STA immediately before the pre-poison call,
    # leaving A live for that call.  The single-submit form calls directly
    # from the incoming byte, then preserves that byte with LDX/STX for the
    # post-reader retry loop.  Prove either actual linked dataflow rather than
    # pinning one instruction spelling.
    if (pre_poison >= 4
            and poll_body[pre_poison - 2] == 0x85
            and poll_body[pre_poison - 4] == 0xa5):
        mode_handoff_shape = "pre-poison-LDA-STA"
        incoming_mode_operand = poll_body[pre_poison - 3]
        canonical_mode_operand = poll_body[pre_poison - 1]
        require(
            poll_body[helper_calls[0] - 1] == incoming_mode_operand
            and poll_body[helper_calls[2] - 1] == canonical_mode_operand
            and poll_body[helper_calls[3] - 1] == canonical_mode_operand,
            "LDA/STA mode handoff is not consumed by all later calls")
    else:
        require(
            pre_poison >= 2 and poll_body[pre_poison - 2] == 0xa5,
            "pre-poison mode-length call lacks a linked mode load")
        mode_handoff_shape = "direct-call-then-LDX-STX-preserve"
        incoming_mode_operand = poll_body[pre_poison - 1]
        require(
            poll_body[helper_calls[0] - 1] == incoming_mode_operand
            and poll_body[helper_calls[2] - 1] == incoming_mode_operand,
            "direct mode calls do not consume one incoming mode byte")
        copies = [
            (offset, poll_body[offset + 3])
            for offset in range(
                helper_calls[0] + 3, min(reader, len(poll_body) - 3))
            if poll_body[offset:offset + 3]
                == bytes((0xa6, incoming_mode_operand, 0x86))
        ]
        require(
            len(copies) == 1
            and poll_body[helper_calls[3] - 1] == copies[0][1],
            "direct mode form lacks one linked LDX/STX preservation")
        canonical_mode_operand = copies[0][1]

    require(
        helper_calls[0] < helper_calls[1] < helper_calls[2]
        < reader < helper_calls[3],
        "mode length is not rematerialized before poison, DMA and comparison")

    retired = u16(retired_address)
    require(
        not all_offsets(poll_body, retired)
        and not all_offsets(helper_body, retired),
        "retired record[27] authority remains referenced")
    require(
        not jsr_offsets(helper_body)
        and immediate_offsets(helper_body, 0x30)
        and immediate_offsets(helper_body, 0x40)
        and helper_body == MODE_LENGTH_BODY,
        "mode-length helper is not a call-free 48/64 constant derivation")

    backward_jumps_after_reader = [
        (offset, target) for offset, target in absolute_jumps(
            poll_body, poll_address)
        if offset > reader and target < poll_address + offset
    ]
    require(backward_jumps_after_reader,
            "linked poll has no auditable retry backedge")
    pre_poison_setup = poll_address + pre_poison - 2
    pre_compare_setup = poll_address + helper_calls[3] - 2
    retry_edges = [
        row for row in backward_jumps_after_reader
        if row[1] == pre_compare_setup
    ]
    require(
        len(retry_edges) in (1, 2),
        "retry edge does not enter the local pre-compare rematerialization")
    retry = retry_edges[0]
    require(
        poll_body[helper_calls[3] - 2] == 0xa5
        and poll_body[helper_calls[3] - 1] == canonical_mode_operand
        and not any(
            target == pre_poison_setup
            for _, target in backward_jumps_after_reader),
        "retry target does not reload mode or still re-enters poison")

    return {
        "retired_record_27_address": f"0x{retired_address:04x}",
        "retired_record_27_references": 0,
        "helper": {
            "address": f"0x{helper_address:04x}",
            "bytes": len(helper_body),
            "Publish_constant": 48,
            "C2J_constant": 64,
            "nested_calls": 0,
        },
        "poll": {
            "address": f"0x{poll_address:04x}",
            "bytes": len(poll_body),
            "initial_validation_call":
                f"0x{poll_address + helper_calls[0]:04x}",
            "pre_poison_call":
                f"0x{poll_address + helper_calls[1]:04x}",
            "pre_poison_mode_setup": f"0x{pre_poison_setup:04x}",
            "mode_handoff_shape": mode_handoff_shape,
            "incoming_mode_zero_page":
                f"0x{incoming_mode_operand:02x}",
            "canonical_mode_zero_page":
                f"0x{canonical_mode_operand:02x}",
            "pre_DMA_call":
                f"0x{poll_address + helper_calls[2]:04x}",
            "nested_reader_call": f"0x{poll_address + reader:04x}",
            "pre_compare_call":
                f"0x{poll_address + helper_calls[3]:04x}",
            "pre_compare_mode_setup": f"0x{pre_compare_setup:04x}",
            "retry_edge": {
                "address": f"0x{poll_address + retry[0]:04x}",
                "target": f"0x{retry[1]:04x}",
            },
            "retry_edges": [
                {
                    "address": f"0x{poll_address + offset:04x}",
                    "target": f"0x{target:04x}",
                }
                for offset, target in retry_edges
            ],
            "retry_edge_count": len(retry_edges),
            "single_submit": {
                "reader_call_count": 1,
                "retry_target_is_after_reader": retry[1]
                    > poll_address + reader,
                "retry_target_is_after_poison": retry[1]
                    > pre_poison_setup,
            },
        },
        "rematerialization_call_count": len(helper_calls) - 1,
    }


def mutations(poll_body: bytes, poll_address: int, reader_address: int,
              helper_body: bytes, helper_address: int,
              retired_address: int) -> list[str]:
    good = audit_bodies(
        poll_body, poll_address, reader_address, helper_body, helper_address,
        retired_address)
    calls = [
        int(good["poll"][name], 16) - poll_address
        for name in ("pre_poison_call", "pre_DMA_call", "pre_compare_call")
    ]
    retries = [
        int(row["address"], 16) - poll_address
        for row in good["poll"]["retry_edges"]]
    cases: list[tuple[str, bytearray, bytearray]] = []
    for name, offset in zip((
            "pre-poison-rematerialization-removed",
            "pre-DMA-rematerialization-removed",
            "pre-compare-rematerialization-removed"), calls):
        mutant = bytearray(poll_body)
        mutant[offset] = 0xea
        cases.append((name, mutant, bytearray(helper_body)))

    mutant = bytearray(poll_body)
    for retry in retries:
        mutant[retry + 1:retry + 3] = u16(poll_address + calls[2] + 3)
    cases.append((
        "retry-bypasses-rematerialization",
        mutant, bytearray(helper_body)))

    mutant = bytearray(poll_body)
    for retry in retries:
        mutant[retry + 1:retry + 3] = u16(
            int(good["poll"]["pre_poison_mode_setup"], 16))
    cases.append((
        "retry-reenters-poison-and-reader",
        mutant, bytearray(helper_body)))

    mutant = bytearray(poll_body)
    mutant[calls[0] - 1] ^= 1
    cases.append((
        "canonical-mode-store-diverges",
        mutant, bytearray(helper_body)))

    mutant = bytearray(poll_body)
    mutant[calls[2] - 1] ^= 1
    cases.append((
        "retry-target-mode-reload-diverges",
        mutant, bytearray(helper_body)))

    for name, constant in (
            ("Publish-length-changed", 0x30),
            ("C2J-length-changed", 0x40)):
        mutant_helper = bytearray(helper_body)
        offset = immediate_offsets(helper_body, constant)[0]
        mutant_helper[offset + 1] ^= 1
        cases.append((name, bytearray(poll_body), mutant_helper))

    mutant_helper = bytearray(helper_body)
    mutant_helper[:3] = bytes((0xad, *u16(retired_address)))
    cases.append((
        "record27-authority-reintroduced",
        bytearray(poll_body), mutant_helper))

    rejected: list[str] = []
    for name, mutant_poll, mutant_helper in cases:
        try:
            audit_bodies(
                bytes(mutant_poll), poll_address, reader_address,
                bytes(mutant_helper), helper_address, retired_address)
        except GateError:
            rejected.append(name)
    require(len(rejected) == len(cases),
            "stateless-length linked mutations were not all rejected")
    return rejected


def audit_phase_calls(header_body: bytes, header_address: int,
                      poll_address: int) -> dict[str, Any]:
    """Bind every header-phase poll edge to its linked mode and payload.

    The retry-length gate historically proved only the four poll-to-leaf
    edges.  That is insufficient if a phase passes the wrong mode into the
    poll.  These patterns are deliberately read from the final section bytes:
    they prove the two-way ACTIVE/ROLLBACK entry, CLEAR, the pre-publication
    C2J fence, and the final 48-byte header comparison.
    """
    call = bytes((0x20, *u16(poll_address)))
    calls = all_offsets(header_body, call)
    require(len(calls) in (4, 5),
            "append-header lacks the four semantic completion-poll roles")

    zero_expected = bytes.fromhex("a2008606a2008607")

    def require_null_mode(call_offset: int, mode: int, label: str) -> None:
        setup = bytes((0xa9, mode)) + zero_expected
        require(
            call_offset >= len(setup)
            and header_body[call_offset - len(setup):call_offset] == setup,
            f"{label} poll edge is not mode {mode:02X} with a NULL payload")

    if len(calls) == 4:
        lowering_shape = "WPLTO-fused-ACTIVE-or-ROLLBACK"
        active_rollback, clear, publish_fence, publish_header = calls
        require(
            active_rollback >= 34
            and bytes.fromhex("a9a18016") in
                header_body[active_rollback - 34:active_rollback]
            and bytes.fromhex("a9a3") in
                header_body[active_rollback - 18:active_rollback]
            and header_body[active_rollback - len(zero_expected):
                            active_rollback] == zero_expected,
            "ACTIVE/ROLLBACK poll edge lost its two linked modes or NULL "
            "payload")
        call_rows = [
            {
                "role": "C2J_ACTIVE_or_ROLLBACK_bookend",
                "offset": active_rollback,
                "modes": ["0xa1", "0xa3"],
                "derived_lengths": [64, 64],
                "expected": "NULL",
            },
        ]
    else:
        lowering_shape = "instrumented-split-ACTIVE-and-ROLLBACK"
        active, rollback, clear, publish_fence, publish_header = calls
        require_null_mode(active, 0xa1, "ACTIVE")
        require_null_mode(rollback, 0xa3, "ROLLBACK")
        call_rows = [
            {
                "role": "C2J_ACTIVE_bookend",
                "offset": active,
                "modes": ["0xa1"],
                "derived_lengths": [64],
                "expected": "NULL",
            },
            {
                "role": "C2J_ROLLBACK_bookend",
                "offset": rollback,
                "modes": ["0xa3"],
                "derived_lengths": [64],
                "expected": "NULL",
            },
        ]

    require_null_mode(clear, 0xa4, "CLEAR")
    require_null_mode(publish_fence, 0xa3, "pre-publication data fence")
    publish_setup = bytes.fromhex(
        "a9a248a005b1028506c8b102850768")
    require(
        publish_header >= len(publish_setup)
        and header_body[publish_header - len(publish_setup):
                        publish_header] == publish_setup,
        "final header proof is not mode A2 with the linked non-NULL header")

    call_rows.extend((
        {
            "role": "C2J_CLEAR_bookend",
            "offset": clear,
            "modes": ["0xa4"],
            "derived_lengths": [64],
            "expected": "NULL",
        },
        {
            "role": "pre_publish_payload_fence",
            "offset": publish_fence,
            "modes": ["0xa3"],
            "derived_lengths": [64],
            "expected": "NULL",
        },
        {
            "role": "published_header_target_proof",
            "offset": publish_header,
            "modes": ["0xa2"],
            "derived_lengths": [48],
            "expected": "w->new_header",
        },
    ))
    for row in call_rows:
        row["address"] = f"0x{header_address + row.pop('offset'):04x}"

    return {
        "phase_symbol": "c2_append_header_phase",
        "phase_address": f"0x{header_address:04x}",
        "poll_target": f"0x{poll_address:04x}",
        "lowering_shape": lowering_shape,
        "call_count": len(calls),
        "semantic_role_count": 4,
        "calls": call_rows,
    }


def phase_call_mutations(header_body: bytes, header_address: int,
                         poll_address: int) -> list[str]:
    calls = all_offsets(
        header_body, bytes((0x20, *u16(poll_address))))
    require(len(calls) in (4, 5), "phase-call mutation seed drift")
    cases: list[tuple[str, int, int]] = []

    def locate(call_offset: int, needle: bytes, label: str) -> int:
        window_start = max(0, call_offset - 40)
        offsets = all_offsets(
            header_body[window_start:call_offset], needle)
        require(len(offsets) == 1,
                f"phase-call mutation anchor drift: {label}")
        return window_start + offsets[0]

    if len(calls) == 4:
        active = locate(calls[0], bytes.fromhex("a9a1"), "ACTIVE") + 1
        rollback = locate(calls[0], bytes.fromhex("a9a3"), "ROLLBACK") + 1
        clear, publish_fence, publish_header = calls[1:]
    else:
        active = calls[0] - 9
        rollback = calls[1] - 9
        clear, publish_fence, publish_header = calls[2:]
    cases.extend((
        ("ACTIVE-mode-swapped", active, 0xa2),
        ("ROLLBACK-mode-swapped", rollback, 0xa2),
        ("CLEAR-mode-swapped", clear - 9, 0xa1),
        ("payload-fence-mode-swapped", publish_fence - 9, 0xa2),
        ("header-mode-swapped", publish_header - 14, 0xa3),
        ("header-expected-pointer-store-removed",
         publish_header - 8, 0xea),
    ))
    rejected: list[str] = []
    for name, offset, replacement in cases:
        mutant = bytearray(header_body)
        mutant[offset] = replacement
        try:
            audit_phase_calls(bytes(mutant), header_address, poll_address)
        except GateError:
            rejected.append(name)
    require(len(rejected) == len(cases),
            "phase-to-poll linked mutations were not all rejected")
    return rejected


def audit_elf(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(
        elf, llvm_readobj=READOBJ, include_section_data=True)
    poll, poll_body = symbol_body(truth, "c2_completion_poll")
    reader = truth.symbol("c2_stream_c2d_read")
    scratch = truth.symbol("lisp65_c2_phase_scratch")
    helper, helper_body = symbol_body(
        truth, "c2_completion_mode_length")
    header, header_body = symbol_body(truth, "c2_append_header_phase")
    require(
        reader.bytes > 0 and scratch.bytes >= RETIRED_LENGTH_OFFSET + 1,
        "completion reader or phase scratch lacks sized ELF identity")
    require(
        helper.binding == "Global"
        and helper.symbol_type == "Function"
        and helper.section == MODE_LENGTH_SECTION
        and poll.section == MODE_LENGTH_SECTION
        and helper.bytes == len(MODE_LENGTH_BODY),
        "mode-length leaf lost named/sized append-header ELF citizenship")
    helper_edges = [
        row for row in truth.relocations
        if row.target == helper.name
    ]
    require(
        len(helper_edges) == 4
        and all(row.relocation_type == "R_MOS_ADDR16"
                and row.source_section_index == poll.section_index
                and poll.value <= row.offset - 1
                    < poll.value + poll.bytes
                for row in helper_edges),
        "final ELF does not contain exactly four direct poll-to-leaf edges")
    retired = scratch.value + RETIRED_LENGTH_OFFSET
    linked = audit_bodies(
        poll_body, poll.value, reader.value, helper_body, helper.value, retired)
    phase_calls = audit_phase_calls(header_body, header.value, poll.value)
    phase_mutations = phase_call_mutations(
        header_body, header.value, poll.value)
    linked["structured_call_edges"] = [
        {
            "source_section": row.source_section,
            "relocation_offset": f"0x{row.offset:04x}",
            "call_address": f"0x{row.offset - 1:04x}",
            "type": row.relocation_type,
            "target": row.target,
        }
        for row in sorted(helper_edges, key=lambda row: row.offset)
    ]
    rejected = mutations(
        poll_body, poll.value, reader.value, helper_body, helper.value, retired)
    return {
        "status":
            "passed-linked-stateless-mode-derived-completion-length",
        "poll": {
            "symbol": poll.name,
            "section": poll.section,
            "address": f"0x{poll.value:04x}",
            "bytes": poll.bytes,
        },
        "helper": {
            "symbol": helper.name,
            "section": helper.section,
            "address": f"0x{helper.value:04x}",
            "bytes": helper.bytes,
        },
        "reader": {
            "symbol": reader.name,
            "address": f"0x{reader.value:04x}",
            "bytes": reader.bytes,
        },
        "linked_dataflow": linked,
        "phase_call_contexts": phase_calls,
        "phase_mutations_rejected": phase_mutations,
        "phase_mutation_count": len(phase_mutations),
        "mutations_rejected": rejected,
        "mutation_count": len(rejected),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("elf", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    args.elf = args.elf.resolve()
    if args.receipt:
        args.receipt = args.receipt.resolve()
    result = audit_elf(args.elf)
    value = {
        "format": "lisp65-c2-stateless-completion-length-ELF-gate-v3",
        "recorded_on": "2026-07-26",
        "status": result["status"],
        "authority": {
            "contract": bind(CONTRACT),
            "ELF": bind(args.elf),
            "gate": bind(Path(__file__)),
        },
        "result": result,
    }
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
    print(
        "c2-stateless-completion-length-elf-gate: PASS "
        f"rematerializations="
        f"{result['linked_dataflow']['rematerialization_call_count']} "
        f"mutations={result['mutation_count']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, ElfTruthError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-stateless-completion-length-elf-gate: FIRST RED: " + str(error))
        raise SystemExit(2)
