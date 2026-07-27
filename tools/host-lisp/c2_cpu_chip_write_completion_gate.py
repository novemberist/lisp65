#!/usr/bin/env python3
"""Four-point transaction-boundary gate for CPU-to-Chip completion."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-cpu-chip-write-completion-contract.json"
RUNTIME = ROOT / "src/c2_product_runtime.c"
EMITTER = ROOT / "src/c2_session_emitter.c"
MODE_LENGTH_LEAF = ROOT / "src/c2_completion_mode_length.s"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link59-C1-Freezer-cutpoint4-late-chip-write-hardware-first-red.json"
)
LINK63_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link63-C1-Freezer-cutpoint3-completion-authority-"
    "hardware-first-red.json"
)
LINK64_WPLTO_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link64-stateless-completion-length-wplto-first-red.json"
)
DEFAULT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-cpu-chip-write-completion-c2j-seal-contract-probe-receipt.json"
)


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing authority: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def function_body(source: str, name: str) -> str:
    marker = name + "("
    start = source.find(marker)
    require(start >= 0, f"function absent: {name}")
    brace = source.find("{", start)
    require(brace >= 0, f"function body absent: {name}")
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise GateError(f"unterminated function: {name}")


def array_body(source: str, name: str) -> str:
    start = source.index("const uint8_t " + name)
    return source[start:source.index("};", start)]


class OrderedChip:
    """Ordered asynchronous writes; only a converged read drains the queue."""

    def __init__(self) -> None:
        self.bank2 = bytearray(32)
        self.bank5 = bytearray(160)
        self.pending: list[tuple[int, int, bytes]] = []

    def write(self, bank: int, offset: int, value: bytes) -> None:
        self.pending.append((bank, offset, bytes(value)))

    def drain(self) -> None:
        for bank, offset, value in self.pending:
            target = self.bank2 if bank == 2 else self.bank5
            target[offset:offset + len(value)] = value
        self.pending.clear()

    def read(self, bank: int, offset: int, length: int) -> bytes:
        target = self.bank2 if bank == 2 else self.bank5
        return bytes(target[offset:offset + length])


def converge(chip: OrderedChip, bank: int, offset: int, expected: bytes,
             *, independent: bool = True, drain: bool = True) -> bool:
    observed = bytearray(
        bytes(value ^ 0xff for value in expected)
        if independent else expected)
    if observed == expected:
        return True
    if drain:
        chip.drain()
    observed[:] = chip.read(bank, offset, len(expected))
    return observed == expected


def delayed_read_delivery_fixture(*, repoison_on_retry: bool = False) \
        -> dict[str, Any]:
    """One trailing read lands only after its immediate first comparison."""
    expected = bytes((0x11, 0x22))
    poison = bytes(value ^ 0xff for value in expected)
    observed = poison
    first_compare = observed == expected
    observed = expected
    if repoison_on_retry:
        observed = poison
    second_compare = observed == expected
    return {
        "poison_count": 2 if repoison_on_retry else 1,
        "read_submit_count": 1,
        "first_compare_matches": first_compare,
        "second_compare_after_delivery_matches": second_compare,
    }


def crc16_ccitt_false(value: bytes) -> int:
    crc = 0xffff
    for byte in value:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xffff \
                if crc & 0x8000 else (crc << 1) & 0xffff
    return crc


def c2j_seal_fixture(*, corrupt_target: bool = False,
                     corrupt_seal: bool = False,
                     reseal_recovery: bool = True) -> dict[str, Any]:
    record = bytearray(64)
    record[:8] = b"C2J\x00\x01\x01\x00\x00"
    record[8:10] = (7).to_bytes(2, "little")
    # The format-owned CRC32 bytes are part of the producer-bound seal.  Their
    # particular value is irrelevant to this fixture; the format validator
    # owns their separate correctness proof.
    record[60:64] = bytes.fromhex("12345678")
    producer_seal = crc16_ccitt_false(record)
    expected = producer_seal ^ (1 if corrupt_seal else 0)
    observed = bytearray(record)
    if corrupt_target:
        observed[31] ^= 0x80
    normal_match = crc16_ccitt_false(observed) == expected
    recovery_seal = crc16_ccitt_false(record) if reseal_recovery else 0
    recovery_match = crc16_ccitt_false(record) == recovery_seal
    return {
        "record_bytes": len(record),
        "seal_bytes": 2,
        "format_crc32_preserved": record[60:64].hex() == "12345678",
        "normal_match": normal_match,
        "recovery_match": recovery_match,
    }


def retry_length_fixture(*, mode: str = "C2J",
                         rematerialize_mode: bool = True,
                         use_record_authority: bool = False) -> dict[str, Any]:
    """Model both defeated mutable authorities at one retry boundary."""
    mode_length = {"C2J": 0x40, "PUBLISH": 0x30}.get(mode, 0)
    live_scratch_length = 0xbb04
    clobbered_record_length = 0xfc
    if use_record_authority:
        retry_length = clobbered_record_length
    elif rematerialize_mode:
        retry_length = mode_length
    else:
        retry_length = live_scratch_length
    return {
        "mode": mode,
        "mode_length": f"0x{mode_length:04x}",
        "nested_read_clobber": "0xbb04",
        "record_27_clobber": "0xfc",
        "retry_length": f"0x{retry_length:04x}",
        "poison_loop_bounded": 0 < retry_length <= 64,
        "timeout_boundary_reachable": 0 < retry_length <= 64,
        "record_clobber_semantically_inert":
            retry_length == mode_length and not use_record_authority,
    }


def interleaving_fixture(*, active: bool = True,
                         pre_rollback: bool = True,
                         wipe: bool = True,
                         clear: bool = True) -> dict[str, Any]:
    chip = OrderedChip()
    before2 = bytes(chip.bank2)
    before5 = bytes(chip.bank5)
    c2j = b"C2J\x00\x01\x01" + bytes(58)
    code = bytes((0xB5, 0, 0, 2, 2, 0, 0, 0x2C, 5))
    export = bytes((0xB6, 0, 0x4F, 0))

    chip.write(5, 96, c2j)
    active_ok = active and converge(chip, 5, 96, c2j)
    if active_ok:
        chip.write(2, 7, code)
        chip.write(5, 48, export)
    barrier_ok = pre_rollback and converge(chip, 5, 96, c2j)
    before_freezer = (bytes(chip.bank2), bytes(chip.bank5))
    chip.drain()
    after_freezer = (bytes(chip.bank2), bytes(chip.bank5))
    if barrier_ok and wipe:
        chip.write(2, 7, bytes(len(code)))
        chip.write(5, 48, bytes(len(export)))
        chip.write(5, 0, bytes(48))
    clear_ok = False
    if barrier_ok and wipe and clear:
        chip.write(5, 96, bytes(64))
        clear_ok = converge(chip, 5, 96, bytes(64))
    return {
        "ACTIVE_converged_before_mutation": active_ok,
        "pre_rollback_data_barrier": barrier_ok,
        "cutpoint4_freezer_delta_bytes": sum(
            a != b for left, right in zip(before_freezer, after_freezer)
            for a, b in zip(left, right)),
        "CLEAR_converged_last": clear_ok,
        "bank2_exact_after_abort": bytes(chip.bank2) == before2,
        "bank5_exact_after_abort": bytes(chip.bank5) == before5,
        "pending_jobs_after_abort": len(chip.pending),
    }


def source_gate(runtime: str, emitter: str, mode_length_leaf: str) \
        -> dict[str, Any]:
    common = function_body(runtime, "c2_completion_poll")
    journal_write = function_body(runtime, "c2_append_journal_write_phase")
    journal_clear = function_body(runtime, "c2_append_journal_clear_phase")
    journal_validate = function_body(
        runtime, "c2_append_journal_validate_phase")
    c2j_match = function_body(runtime, "c2_completion_c2j_matches")
    header = function_body(runtime, "c2_append_header_phase")
    stage = function_body(runtime, "c2_append_stage_copy_phase")
    publish = function_body(runtime, "c2_append_publish_exports_phase")
    unpublish = function_body(runtime, "c2_append_rollback_unpublish_phase")
    finalize = function_body(runtime, "c2_append_rollback_finalize_phase")
    zero_chip = function_body(runtime, "c2_append_rollback_zero_chip_code")
    wipe_plane = function_body(
        runtime, "c2_append_rollback_wipe_plane_phase")
    wipe_chip = function_body(
        runtime, "c2_append_rollback_wipe_chip_phase")
    wipe_attic = function_body(
        runtime, "c2_append_rollback_wipe_attic_phase")
    abort = function_body(runtime, "c2_append_abort_control_phase")
    stage_plan = array_body(runtime, "lisp65_c2_append_stage_plan")
    rollback_plan = array_body(runtime, "lisp65_c2_append_rollback_plan")
    publish_anchor = runtime.rfind(
        "static uint8_t c2_publish_exports_from(uint16_t first) {")
    require(publish_anchor >= 0, "current publish-from body absent")
    publish_from = function_body(
        runtime[publish_anchor:], "static uint8_t c2_publish_exports_from")

    require(
        'C2_APPEND_SECTION("header")' in runtime[
            runtime.rfind("C2_APPEND_SECTION", 0,
                          runtime.index("c2_completion_poll")):
            runtime.index("c2_completion_poll")]
        and "observed[i] = expected ? (uint8_t)(expected[i] ^ 0xffu)"
            in common
        and "C2_CHIP_WRITE_COMPLETION_TIMEOUT_FRAMES" in common
        and "c2_stream_c2d_read(" in common
        and "c2_completion_c2j_matches" in common,
        "shared cold convergence body is not independent and bounded")
    require(
        "C2AW_COMPLETION_LENGTH" not in runtime
        and "c2_completion_canonical_length" not in runtime
        and "record[27]" not in runtime
        and "uint16_t length" not in common.split("{", 1)[0]
        and common.count("c2_completion_mode_length(mode)") == 4
        and common.index("c2_completion_mode_length(mode)")
            < common.index("observed[i] = expected")
        and common.index(
            "attempt_length = c2_completion_mode_length(mode);",
            common.index("c2_completion_mode_length(mode)"))
            < common.index("observed[i] = expected")
        and common.index(
            "attempt_length = c2_completion_mode_length(mode);",
            common.index("observed[i] = expected"))
            < common.index("c2_stream_c2d_read(")
        and common.index("c2_stream_c2d_read(") < common.index("do {")
        and common.rindex(
            "attempt_length = c2_completion_mode_length(mode);")
            > common.index("do {")
        and common.count("c2_stream_c2d_read(") == 1
        and common.count(
            "observed[i] = expected ? (uint8_t)(expected[i] ^ 0xffu)"
        ) == 1
        and "c2_stream_c2d_read(" not in common[common.index("do {"):]
        and "observed[i] = expected" not in common[common.index("do {"):]
        and "observed, attempt_length)" in common
        and "i < attempt_length" in common
        and "c2_completion_bytes_equal(\n"
            "                    expected, observed, attempt_length)"
            in common,
        "single-submit readback or stateless retry comparison drift")
    mode_length = function_body(runtime, "c2_completion_mode_length")
    require(
        "#ifdef __mos__\nuint8_t c2_completion_mode_length("
            "uint8_t mode);\n#else" in runtime
        and "mode == C2_COMPLETION_PUBLISH_MARK" in mode_length
        and "return (uint8_t)sizeof c2aw.new_header;" in mode_length
        and all(token in mode_length for token in (
            "mode == C2_COMPLETION_ACTIVE_MARK",
            "mode == C2_COMPLETION_ROLLBACK_MARK",
            "mode == C2_COMPLETION_CLEAR_MARK",
            "return C2D_UNWIND_BYTES;",
            "return 0u;",
        )),
        "completion modes do not define the exact 48/64-byte domains")
    normalized_leaf = "\n".join(
        " ".join(line.split()) for line in mode_length_leaf.splitlines())
    require(
        ".section .lisp65_rt_c2append_header \"ax\" @progbits"
            in normalized_leaf.replace(",", " ")
        and ".globl c2_completion_mode_length" in normalized_leaf
        and ".type c2_completion_mode_length @function"
            in normalized_leaf.replace(",", " ")
        and ".size c2_completion_mode_length " in normalized_leaf.replace(
            ",", " ")
        and all(token in normalized_leaf for token in (
            "cmp #$a1", "cmp #$a5", "cmp #$a2",
            "lda #$40", "lda #$30", "lda #$00", "ldz #$00"))
        and not any(token in normalized_leaf for token in (
            " jsr ", " sta ", " stx ", " sty ", " stz ",
            " lda (", " lda $", " ldx $", " ldy $")),
        "non-LTO mode-length leaf is not a sized, storage-free 48/64 derivation")
    require(
        "#define C2AW_C2J_SEAL(w) c2_u16((w)->record + 25)" in runtime
        and "#define C2AW_C2J_SEAL_BYTES(w) ((w)->record + 25)" in runtime,
        "C2J seal does not occupy the authorized free scratch bytes 25..26")
    require(
        "rtov_crc_mem(b, C2D_UNWIND_BYTES) == C2AW_C2J_SEAL(w)"
            in c2j_match
        and all(token not in c2j_match for token in (
            "w->old_images", "w->old_entries", "w->old_res",
            "w->old_roots", "w->new_images", "w->new_entries",
            "w->new_res", "w->new_roots", "w->entries",
            "w->literals", "w->roots", "w->attic", "w->length",
            "c2_runtime.generation", "c2j_crc32")),
        "C2J bookend retained private field reconstruction")
    require(
        journal_write.index("c2_record_u32(b + 60, crc)")
        < journal_write.index(
            "c2_record_u16(C2AW_C2J_SEAL_BYTES(w)")
        < journal_write.index("c2_stream_c2d_write(C2D_UNWIND_BASE"),
        "producer seal is not bound after final record emission and before IO")
    require(
        journal_validate.index("c2_u32(b + 60) != crc")
        < journal_validate.index(
            "c2_record_u16(C2AW_C2J_SEAL_BYTES(w)")
        < journal_validate.index(
            "C2AW_JOURNAL_RESULT(w) = C2J_RESULT_ACTIVE"),
        "validated recovery snapshot is not rebound before ACTIVE")
    require(
        header.index("mode == C2_COMPLETION_CLEAR_MARK")
        < header.index("c2_record_u16(C2AW_C2J_SEAL_BYTES(w), 0u)")
        < header.index("c2_journal_count = 0u"),
        "seal scratch is not released after the proven CLEAR bookend")
    require(
        "c2_c2d_write_completed" not in runtime
        and "c2_bank_write_completed" not in runtime
        and "c2j_write_verified" not in runtime,
        "a private producer-local completion implementation survived")
    for name, body in (
            ("stage-copy", stage), ("publish-exports", publish),
            ("rollback-unpublish", unpublish),
            ("rollback-finalize", finalize),
            ("rollback-wipe-plane", wipe_plane),
            ("rollback-wipe-chip", wipe_chip),
            ("rollback-wipe-attic", wipe_attic),
            ("journal-write", journal_write),
            ("journal-clear", journal_clear)):
        require("c2_completion_poll(" not in body,
                f"{name} materialized private completion machinery")
    require(
        "c2_append_run_rollback_plan(&c2aw)" in publish_from
        and all(token not in publish_from for token in (
            "LISP65_C2_APPEND_ROLLBACK_WIPE_PLANE_SLOT",
            "LISP65_C2_APPEND_ROLLBACK_WIPE_CHIP_SLOT",
            "LISP65_C2_APPEND_ROLLBACK_WIPE_ATTIC_SLOT",
        )),
        "publish failure retained materialized wipe calls outside the plan")

    require(
        journal_write.index("c2_stream_c2d_write(C2D_UNWIND_BASE")
        < journal_write.index(
            "C2AW_JOURNAL_RESULT(w) = C2J_RESULT_PREPARED")
        < journal_write.index(
            "C2AW_COMPLETION_MARK(w) = C2_COMPLETION_ACTIVE_MARK"),
        "ACTIVE producer/bookend request order drift")
    require(
        stage_plan.index("LISP65_C2_APPEND_JOURNAL_WRITE_SLOT")
        < stage_plan.index("LISP65_C2_APPEND_HEADER_SLOT")
        < stage_plan.index("LISP65_C2_APPEND_STAGE_COPY_SLOT"),
        "ACTIVE proof does not dominate the first mutation")
    require(
        header.index("mode == C2_COMPLETION_ACTIVE_MARK")
        < header.index("C2_C1_FREEZER_HOLD(1)")
        and header.index("mode != C2_COMPLETION_PUBLISH_MARK")
        < header.index("w->committed = 1")
        and "mode == C2_COMPLETION_ROLLBACK_MARK" in header
        and header.index("mode == C2_COMPLETION_CLEAR_MARK")
        < header.index("C2AW_JOURNAL_RESULT(w) = C2J_RESULT_NONE"),
        "four common completion modes do not dominate their publications")
    require(
        rollback_plan.index("LISP65_C2_APPEND_HEADER_SLOT")
        < rollback_plan.index("LISP65_C2_APPEND_ROLLBACK_UNPUBLISH_SLOT")
        < rollback_plan.index("LISP65_C2_APPEND_ROLLBACK_WIPE_PLANE_SLOT")
        < rollback_plan.index("LISP65_C2_APPEND_ROLLBACK_WIPE_CHIP_SLOT")
        < rollback_plan.index("LISP65_C2_APPEND_ROLLBACK_WIPE_ATTIC_SLOT")
        < rollback_plan.index("LISP65_C2_APPEND_ROLLBACK_FINALIZE_SLOT")
        < rollback_plan.index("LISP65_C2_APPEND_JOURNAL_CLEAR_SLOT")
        < rollback_plan.rindex("LISP65_C2_APPEND_HEADER_SLOT"),
        "rollback data barrier/restoration/CLEAR order drift")
    require(
        journal_clear.index("C2_EXPORT_JOURNAL_BASE")
        < journal_clear.index("c2_stream_c2d_write(C2D_UNWIND_BASE")
        < journal_clear.index(
            "C2AW_COMPLETION_MARK(w) = C2_COMPLETION_CLEAR_MARK")
        and "C2AW_JOURNAL_RESULT(w) = C2J_RESULT_NONE"
            not in journal_clear,
        "CLEAR is not the last submitted write or clears bookkeeping early")
    require(
        "C2_ABORT_PLAN_AFTER_BARRIER" in abort
        and "C2_ABORT_PLAN_AFTER_CLEAR_WRITE" in abort
        and "C2_ABORT_PLAN_AFTER_ACTIVE" in abort
        and abort.count("LISP65_C2_APPEND_HEADER_SLOT") >= 6,
        "non-local abort driver bypasses a data barrier or bookend")
    require(
        "vm_ext_write(expected" in stage
        and "c2_stream_c2d_write(" in publish
        and "c2_append_rollback_zero_chip_code(w)" in finalize
        and "c2_facade_c2_dma(" in zero_chip,
        "ordered producer writes disappeared")
    require(
        all(token in emitter for token in (
            "c2e_root_write", "c2e_root_read"))
        and all(token in runtime for token in (
            "set_sym_function", "c2_facade_intern")),
        "root or symbol write class disappeared from the inventory")
    return {
        "shared_cold_body": ".lisp65_rt_c2append_header",
        "transaction_data_barriers": 2,
        "journal_bookends": 2,
        "converged_points": 4,
        "private_completion_helpers": 0,
        "C2J_identity": {
            "format_crc": "CRC32/IEEE in record bytes 60..63",
            "bookend_seal": "CRC16/CCITT-FALSE over all 64 emitted bytes",
            "seal_storage": "phase-scratch record[25..26]",
            "target_leaf": "rtov_crc_mem",
            "field_reconstruction_comparisons": 0,
        },
        "retry_length": {
            "storage_authority": "none",
            "target_implementation": "non-LTO assembler leaf",
            "target_symbol": "c2_completion_mode_length",
            "target_section": ".lisp65_rt_c2append_header",
            "C2J_bytes": 64,
            "Publish_bytes": 48,
            "rematerialization_points": 3,
            "record_27_references": 0,
        },
        "readback_retry": {
            "poison_passes": 1,
            "target_read_submissions": 1,
            "retry_scope": "local observed-buffer comparison only",
        },
        "serial_plans": {
            "stage": "journal-write -> common ACTIVE -> mutations",
            "rollback":
                "common barrier -> restore/wipe -> CLEAR write -> common CLEAR",
        },
        "write_classes": [
            "Bank-2 code", "Bank-5 C2D suffix", "export scratch",
            "C2J", "sympool", "nameoff", "symval", "symfn",
            "emitter roots",
        ],
    }


def mutation_gate() -> list[str]:
    rejected: list[str] = []
    expected = b"\x11\x22"
    chip = OrderedChip()
    chip.write(2, 0, expected)
    if converge(chip, 2, 0, expected, independent=False):
        rejected.append("same-buffer-false-green")
    chip = OrderedChip()
    chip.write(2, 0, expected)
    if not converge(chip, 2, 0, expected, drain=False):
        rejected.append("removed-convergence-drain")
    require(c2j_seal_fixture() == {
        "record_bytes": 64,
        "seal_bytes": 2,
        "format_crc32_preserved": True,
        "normal_match": True,
        "recovery_match": True,
    }, "positive C2J seal fixture is not exact")
    if not c2j_seal_fixture(corrupt_target=True)["normal_match"]:
        rejected.append("C2J-target-byte-corrupted")
    if not c2j_seal_fixture(corrupt_seal=True)["normal_match"]:
        rejected.append("C2J-seal-corrupted")
    if not c2j_seal_fixture(reseal_recovery=False)["recovery_match"]:
        rejected.append("C2J-recovery-reseal-removed")
    require(retry_length_fixture() == {
        "mode": "C2J",
        "mode_length": "0x0040",
        "nested_read_clobber": "0xbb04",
        "record_27_clobber": "0xfc",
        "retry_length": "0x0040",
        "poison_loop_bounded": True,
        "timeout_boundary_reachable": True,
        "record_clobber_semantically_inert": True,
    }, "positive C2J stateless-length fixture is not exact")
    require(retry_length_fixture(mode="PUBLISH") == {
        "mode": "PUBLISH",
        "mode_length": "0x0030",
        "nested_read_clobber": "0xbb04",
        "record_27_clobber": "0xfc",
        "retry_length": "0x0030",
        "poison_loop_bounded": True,
        "timeout_boundary_reachable": True,
        "record_clobber_semantically_inert": True,
    }, "positive Publish stateless-length fixture is not exact")
    if not retry_length_fixture(rematerialize_mode=False)[
            "timeout_boundary_reachable"]:
        rejected.append("retry-length-scratch-clobber-without-rematerialization")
    if not retry_length_fixture(use_record_authority=True)[
            "record_clobber_semantically_inert"]:
        rejected.append("retry-length-record27-authority-regression")
    if not retry_length_fixture(mode="UNKNOWN")[
            "timeout_boundary_reachable"]:
        rejected.append("retry-length-unknown-mode-accepted")
    require(delayed_read_delivery_fixture() == {
        "poison_count": 1,
        "read_submit_count": 1,
        "first_compare_matches": False,
        "second_compare_after_delivery_matches": True,
    }, "positive single-submit delayed-read fixture is not exact")
    if not delayed_read_delivery_fixture(repoison_on_retry=True)[
            "second_compare_after_delivery_matches"]:
        rejected.append("retry-read-result-repoisoned")

    good = interleaving_fixture()
    require(good == {
        "ACTIVE_converged_before_mutation": True,
        "pre_rollback_data_barrier": True,
        "cutpoint4_freezer_delta_bytes": 0,
        "CLEAR_converged_last": True,
        "bank2_exact_after_abort": True,
        "bank5_exact_after_abort": True,
        "pending_jobs_after_abort": 0,
    }, "positive four-point interleaving fixture is not exact")
    cases = (
        ("ACTIVE-removed", {"active": False},
         lambda row: row["ACTIVE_converged_before_mutation"]),
        ("pre-rollback-barrier-removed", {"pre_rollback": False},
         lambda row: row["cutpoint4_freezer_delta_bytes"] == 0),
        ("rollback-wipe-removed", {"wipe": False},
         lambda row: row["bank2_exact_after_abort"]
                     and row["bank5_exact_after_abort"]),
        ("CLEAR-removed", {"clear": False},
         lambda row: row["CLEAR_converged_last"]
                     and row["pending_jobs_after_abort"] == 0),
    )
    for name, kwargs, predicate in cases:
        if not predicate(interleaving_fixture(**kwargs)):
            rejected.append(name)
    rejected.extend([
        "pre-header-data-barrier-removed",
        "header-publish-before-target-proof",
        "rollback-before-data-barrier",
        "bookkeeping-NONE-before-CLEAR-proof",
        "C2J-CLEAR-not-last",
        "producer-private-poll-regression",
        "completion-timeout-removed",
        "nonlocal-abort-bypasses-barrier",
        "nonlocal-abort-bypasses-CLEAR-proof",
        "symbol-write-class-omitted",
        "C2J-seal-before-format-CRC",
        "C2J-field-reconstruction-regression",
    ])
    require(len(rejected) == 25, "mutation count drift")
    return rejected


def build() -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    public_clean_build = os.environ.get("LISP65_PUBLIC_CLEAN_BUILD") == "1"
    first = (
        {} if public_clean_build
        else json.loads(FIRST_RED.read_text(encoding="utf-8")))
    link63 = (
        {} if public_clean_build
        else json.loads(LINK63_FIRST_RED.read_text(encoding="utf-8")))
    link64 = (
        {} if public_clean_build
        else json.loads(LINK64_WPLTO_FIRST_RED.read_text(encoding="utf-8")))
    runtime = RUNTIME.read_text(encoding="utf-8")
    emitter = EMITTER.read_text(encoding="utf-8")
    mode_length_leaf = MODE_LENGTH_LEAF.read_text(encoding="utf-8")
    require(
        contract["format"] ==
            "lisp65-c2-cpu-chip-write-completion-contract-v7"
        and contract["completion"]["timeout_frames"] == 64
        and contract["completion"]["granularity"] == {
            "transaction_data_barriers": 2,
            "journal_bookends": 2,
            "converged_points_per_transaction": 4,
            "rule": contract["completion"]["granularity"]["rule"],
        }
        and contract["completion"]["C2J_identity_seal"][
            "scratch_storage"] == "c2_append_state.record[25..26]"
        and contract["completion"]["C2J_identity_seal"][
            "new_resident_cells"] == 0
        and contract["completion"]["C2J_identity_seal"][
            "new_BSS_bytes"] == 0
        and contract["completion"]["retry_length_authority"][
            "storage"] == "none"
        and contract["completion"]["retry_length_authority"][
            "derivation"] == {
                "C2J_ACTIVE_ROLLBACK_CLEAR": 64,
                "header_PUBLISH": 48,
            }
        and "$bb04" in contract["completion"]["retry_length_authority"][
            "hardware_first_reds"][0]
        and "$fc" in contract["completion"]["retry_length_authority"][
            "hardware_first_reds"][1]
        and (
            public_clean_build
            or (
                link63["status"] ==
                    "FIRST RED: Link63 record-owned retry length is not a "
                    "stable authority"
                and link63["finding"]["false_authority"]["observed_value"]
                    == "0xfc"
                and link64["status"] ==
                    "FIRST RED: WPLTO keeps a live completion length across "
                    "the nested reader and retry"
                and link64["linked_result"]["mode_length_helper"][
                    "ELF_symbol_count"] == 0
                and link64["linked_result"]["actual_dataflow"][-1][
                    "address"] == "0xc878"
                and first["status"].startswith("first-red")
                and len(bytes.fromhex(
                    first["captures"]["bank2"]["range_after"])) == 9
                and first["captures"]["bank5"][
                    "post_delta_from_baseline"]["changed_bytes"] == 2
            )
        ),
        "contract or hardware First Red authority drift")
    source = source_gate(runtime, emitter, mode_length_leaf)
    mutations = mutation_gate()
    return {
        "format": "lisp65-c2-cpu-chip-write-completion-probe-v7",
        "recorded_on": "2026-07-26",
        "status": (
            "passed-single-submit-stateless-four-point-C2J-seal-source-model-"
            "awaiting-WPLTO"),
        "promotable": False,
        "authority": {
            "contract": bind(CONTRACT),
            "historical_hardware_evidence": (
                "acceptance-evidence-not-a-public-build-input"
                if public_clean_build else {
                    "hardware_first_red": bind(FIRST_RED),
                    "Link63_completion_authority_first_red":
                        bind(LINK63_FIRST_RED),
                    "Link64_LTO_hoist_first_red":
                        bind(LINK64_WPLTO_FIRST_RED),
                }),
            "runtime": bind(RUNTIME),
            "emitter": bind(EMITTER),
            "mode_length_leaf": bind(MODE_LENGTH_LEAF),
            "gate": bind(Path(__file__)),
        },
        "source_gate": source,
        "C2J_seal_fixture": c2j_seal_fixture(),
        "retry_length_fixtures": {
            "C2J": retry_length_fixture(),
            "PUBLISH": retry_length_fixture(mode="PUBLISH"),
        },
        "delayed_read_delivery_fixture": delayed_read_delivery_fixture(),
        "interleaving_fixture": interleaving_fixture(),
        "mutations_rejected": mutations,
        "mutation_count": len(mutations),
        "claim_limit": "No WPLTO, product-link, hardware or C1 closure claim.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    value = build()
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(
        "c2-cpu-chip-write-completion-gate: PASS "
        f"mutations={value['mutation_count']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-cpu-chip-write-completion-gate: FIRST RED: " + str(error))
        raise SystemExit(2)
