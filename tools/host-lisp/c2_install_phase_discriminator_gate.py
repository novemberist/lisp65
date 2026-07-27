#!/usr/bin/env python3
"""Permanent gate for first-error-wins cold install provenance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from elf_truth import ElfTruth


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-install-phase-discriminator-contract.json"
SOURCES = {
    "header": ROOT / "src/c2_phase_scratch.h",
    "scratch": ROOT / "src/c2_phase_scratch.c",
    "runtime": ROOT / "src/c2_product_runtime.c",
    "emitter": ROOT / "src/c2_session_emitter.c",
    "decoder": ROOT / "scripts/c2-stream-decoder.c",
    "v2_decoder": ROOT / "scripts/c2-stream-v2-decoder.c",
    "eval": ROOT / "src/eval.c",
    "overlay": ROOT / "src/error_overlay.c",
}


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def function_body(text: str, signature: str) -> str:
    start = text.find(signature)
    require(start >= 0, f"function absent: {signature}")
    brace = text.find("{", start)
    require(brace >= 0, f"function body absent: {signature}")
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise GateError(f"unterminated function: {signature}")


def _sources() -> dict[str, str]:
    return {name: path.read_text(encoding="utf-8")
            for name, path in SOURCES.items()}


DECODER_STAMPS = (
    "LISP65_C2_PHASE_04_SLOT", "LISP65_C2_PHASE_05A_SLOT",
    "LISP65_C2_PHASE_05B_SLOT", "LISP65_C2_PHASE_06A_SLOT",
    "LISP65_C2_PHASE_06B_SLOT",
)
V2_STAMPS = (
    "LISP65_C2_PHASE_07_SLOT", "LISP65_C2_PHASE_08_SLOT",
    "LISP65_C2_PHASE_09_SLOT", "LISP65_C2_PHASE_10_SLOT",
    "LISP65_C2_PHASE_11A_SLOT", "LISP65_C2_PHASE_11B_SLOT",
    "LISP65_C2_PHASE_12_SLOT",
)
EMITTER_STAMPS = (
    "LISP65_C2_EMIT_PREPARE_SLOT", "LISP65_C2_EMIT_NAME_SLOT",
    "LISP65_C2_EMIT_LITERAL_PREP_SLOT", "LISP65_C2_EMIT_LITERAL_ATOM_SLOT",
    "LISP65_C2_EMIT_LITERAL_APPEND_SLOT", "LISP65_C2_EMIT_CODE_SLOT",
    "LISP65_C2_EMIT_FINAL_META_SLOT", "LISP65_C2_EMIT_FINAL_CRC_SLOT",
)
DIRECT_APPEND_STAMPS = (
    "LISP65_C2_APPEND_ENVELOPE_SLOT",
    "LISP65_C2_APPEND_CRC_METADATA_SLOT",
    "LISP65_C2_APPEND_RESERVE_TRANSIENT_BOUNDS_SLOT",
    "LISP65_C2_APPEND_RESERVE_TRANSIENT_CODE_SLOT",
    "LISP65_C2_APPEND_RESERVE_PERSISTENT_BOUNDS_SLOT",
    "LISP65_C2_APPEND_RESERVE_PERSISTENT_CODE_SLOT",
    "LISP65_C2_APPEND_STAGE_COPY_SLOT",
    "LISP65_C2_APPEND_STAGE_PLANE_SLOT",
    "LISP65_C2_APPEND_IMAGE_SLOT", "LISP65_C2_APPEND_ENTRIES_SLOT",
    "LISP65_C2_APPEND_HEADER_SLOT",
    "LISP65_C2_APPEND_PUBLISH_PLAN_SCAN_SLOT",
    "LISP65_C2_APPEND_PUBLISH_PLAN_RESOLVE_SLOT",
)
GUARDED_APPEND_STAMPS = (
    "LISP65_C2_APPEND_ROOTS_FRONTS_SLOT",
    "LISP65_C2_APPEND_JOURNAL_WRITE_SLOT",
    "LISP65_C2_APPEND_JOURNAL_VALIDATE_SLOT",
    "LISP65_C2_APPEND_JOURNAL_RECONSTRUCT_SLOT",
    "LISP65_C2_APPEND_ROLLBACK_PREPARE_SLOT",
    "LISP65_C2_APPEND_PUBLISH_CLEAR_SLOT",
    "LISP65_C2_APPEND_ROLLBACK_UNPUBLISH_SLOT",
    "LISP65_C2_APPEND_ROLLBACK_FINALIZE_SLOT",
    "LISP65_C2_APPEND_ABORT_CONTROL_SLOT",
)
APPEND_STAMPS = DIRECT_APPEND_STAMPS + GUARDED_APPEND_STAMPS


def fixture() -> dict[str, Any]:
    # The thirteen-path matrix now models the first-error-wins rule.  Cleanup
    # may run to completion, but neither its slot nor a later restart can
    # replace the primary witness after the lock bit is set.
    cases = {
        "transaction_begin": {"tuple_claimed": False,
                              "authority": "existing-status"},
        "emitter_failure": {"primary": "emitter", "inner": 0, "locked": 0},
        "append_failure": {"primary": "append", "inner": 0, "locked": 0},
        "append_then_local_cleanup": {
            "primary": "append", "cleanup": "rollback", "inner": 0,
            "locked": 1},
        "append_then_nonlocal_cleanup": {
            "primary": "append", "cleanup": "abort", "inner": 0,
            "locked": 1},
        "persistent_success": {
            "primary": "publish", "inner": 0, "locked": 0},
        "transient_before_inner": {
            "primary": "publish", "inner": 0, "locked": 0},
        "inner_vm": {"primary": "pre-inner", "inner": 1, "locked": 1},
        "inner_then_rollback": {
            "primary": "pre-inner", "cleanup": "rollback", "inner": 1,
            "locked": 1},
        "inner_then_abort": {
            "primary": "pre-inner", "cleanup": "abort", "inner": 1,
            "locked": 1},
        "inner_then_rebegin": {
            "primary": "pre-inner", "cleanup": "restart", "inner": 1,
            "locked": 1},
        "inner_then_final_end": {
            "primary": "pre-inner", "cleanup": "finalize", "inner": 1,
            "locked": 1},
        "success": {"primary": "pre-inner", "inner": 1, "locked": 1},
    }
    require(len(cases) == 13
            and all(cases[name]["inner"] == 1 for name in (
                "inner_vm", "inner_then_rollback", "inner_then_abort",
                "inner_then_rebegin", "inner_then_final_end", "success"))
            and all(cases[name]["primary"] == "pre-inner" for name in (
                "inner_vm", "inner_then_rollback", "inner_then_abort",
                "inner_then_rebegin", "inner_then_final_end", "success")),
            "thirteen-path first-fault fixture drift")
    return {"status": "passed-thirteen-path-first-fault-lock-model",
            "cases": cases, "cases_passed": len(cases),
            "refill_boundary_claimed": False}


def _exact_stamps(text: str, macro: str, names: tuple[str, ...]) -> None:
    compact = "".join(text.split())
    for name in names:
        require(compact.count(f"{macro}({name})") == 1,
                f"cold phase stamp absent or duplicated: {name}")


def source_gate(parts: dict[str, str] | None = None,
                *, mutations: bool = False) -> dict[str, Any]:
    text = parts or _sources()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    storage = contract["storage"]
    require(contract["schema"] == "lisp65.c2.install-first-fault-stamp.v3"
            and storage["scratch_bytes"] == 304
            and storage["offset"] == 302 and storage["bytes"] == 2
            and storage["layout"] == ["first_error_session_slot", "trace_flags"]
            and storage["trace_flags"] == {
                "inner_vm_entered_bit": 1,
                "primary_locked_bit": 128,
                "reserved_mask": 126,
            }
            and storage["new_bss_bytes"] == 0
            and storage["new_gc_roots"] == 0,
            "first-fault contract/storage drift")
    header = text["header"]
    require("#define LISP65_C2_INSTALL_TRACE_BYTES 2u" in header
            and "LISP65_C2_PHASE_SCRATCH_BYTES - LISP65_C2_INSTALL_TRACE_BYTES"
                in header
            and "#define LISP65_C2_INSTALL_INNER_ENTERED 1u" in header
            and "#define LISP65_C2_INSTALL_PRIMARY_LOCKED 128u" in header
            and "C2_INSTALL_TRACE_STAMP_SLOT_IF_UNLOCKED" in header
            and "& LISP65_C2_INSTALL_PRIMARY_LOCKED" in header
            and "C2_INSTALL_TRACE_LOCK_PRIMARY" in header
            and "(LISP65_C2_INSTALL_PRIMARY_LOCKED" in header
            and "| LISP65_C2_INSTALL_INNER_ENTERED)" in header
            and "volatile uint8_t" in header,
            "first-fault tail geometry, flags or volatile witness drift")
    require("c2_install_phase_mark" not in header
            and "c2_install_phase_mark" not in text["scratch"]
            and "LISP65_C2_INSTALL_PHASE_TAG" not in header,
            "retired resident marker seam survived")
    require("sizeof(c2e_work_state) == LISP65_C2_INSTALL_TRACE_OFFSET" in
                text["emitter"]
            and "sizeof(c2_append_state) <= LISP65_C2_INSTALL_TRACE_OFFSET" in
                text["runtime"],
            "scratch consumer overlaps the trace tail")

    _exact_stamps(text["decoder"], "C2_INSTALL_DECODER_STAMP", DECODER_STAMPS)
    _exact_stamps(text["v2_decoder"], "C2_INSTALL_V2_STAMP", V2_STAMPS)
    _exact_stamps(text["emitter"], "C2_INSTALL_TRACE_STAMP_SLOT", EMITTER_STAMPS)
    _exact_stamps(text["runtime"], "C2_INSTALL_TRACE_STAMP_SLOT",
                  DIRECT_APPEND_STAMPS)
    _exact_stamps(text["runtime"], "C2_INSTALL_TRACE_STAMP_SLOT_IF_UNLOCKED",
                  GUARDED_APPEND_STAMPS)
    prepare = function_body(text["emitter"],
                            "uint8_t c2_session_emit_prepare_phase(")
    require(prepare.count("C2_INSTALL_TRACE_RESET_INNER();") == 1
            and prepare.index("C2_INSTALL_TRACE_RESET_INNER();")
                < prepare.index("C2_INSTALL_TRACE_STAMP_SLOT("),
            "first cold emitter entry does not reset before stamping")
    install = function_body(text["runtime"], "obj c2_product_install(")
    require(install.count("C2_INSTALL_TRACE_ENTER_INNER();") == 1
            and install.index("C2_INSTALL_TRACE_ENTER_INNER();")
                < install.index("result = vm_run_dir("),
            "sole resident inner/lock marker is absent or ordered after execution")
    rollback = function_body(
        text["runtime"], "uint8_t c2_append_rollback_unpublish_phase(")
    abort = function_body(
        text["runtime"], "uint8_t c2_append_abort_control_phase(")
    guarded = "C2_INSTALL_TRACE_STAMP_SLOT_IF_UNLOCKED("
    require(rollback.count("C2_INSTALL_TRACE_LOCK_PRIMARY();") == 1
            and rollback.index("C2_INSTALL_TRACE_LOCK_PRIMARY();")
                < rollback.index(guarded),
            "local cleanup does not lock before its own stamp")
    require(abort.count("C2_INSTALL_TRACE_LOCK_PRIMARY();") == 1
            and abort.index("C2_INSTALL_TRACE_LOCK_PRIMARY();")
                < abort.index(guarded),
            "non-local cleanup does not lock before its own stamp")
    require("C2_INSTALL_V2_STAMP(LISP65_C2_PHASE_13_SLOT)" not in
                text["v2_decoder"],
            "hot refill phase writes cold install provenance")
    require(install.count("if (vm_status != VM_OK) return NIL;") == 3
            and "vm_status = VM_BADOPCODE; return NIL;" in install,
            "inner-status precedence drift")
    require("code == LISP65_ERR_VM_BAD_BYTECODE && IS_FIX(detail)" not in
                text["eval"]
            and "code == LISP65_ERR_VM_BAD_BYTECODE && IS_FIX(detail)" not in
                text["overlay"],
            "raw provenance escaped into the product renderer")

    rejected: dict[str, str] = {}
    if mutations:
        trials: dict[str, dict[str, str]] = {}

        def replace(name: str, owner: str, old: str, new: str) -> None:
            require(old in text[owner], f"mutation anchor absent: {name}")
            trial = dict(text)
            trial[owner] = trial[owner].replace(old, new, 1)
            trials[name] = trial

        replace("tail-offset-drift", "header",
                "LISP65_C2_PHASE_SCRATCH_BYTES - LISP65_C2_INSTALL_TRACE_BYTES",
                "LISP65_C2_PHASE_SCRATCH_BYTES - 1u")
        replace("emitter-overlaps-tail", "emitter",
                "sizeof(c2e_work_state) == LISP65_C2_INSTALL_TRACE_OFFSET",
                "sizeof(c2e_work_state) == LISP65_C2_PHASE_SCRATCH_BYTES")
        replace("append-overlaps-tail", "runtime",
                "sizeof(c2_append_state) <= LISP65_C2_INSTALL_TRACE_OFFSET",
                "sizeof(c2_append_state) <= LISP65_C2_PHASE_SCRATCH_BYTES")
        replace("missing-first-overlay-reset", "emitter",
                "C2_INSTALL_TRACE_RESET_INNER();", "")
        replace("missing-inner-transition", "runtime",
                "C2_INSTALL_TRACE_ENTER_INNER();", "")
        replace("inner-transition-after-vm-call", "runtime",
                "C2_INSTALL_TRACE_ENTER_INNER();\n"
                "    C2_FRAME_ATTRIBUTION_STAMP("
                "LISP65_C2_FRAME_ATTR_INNER_VM);\n"
                "    result = vm_run_dir((int)main, 0, 0);",
                "C2_FRAME_ATTRIBUTION_STAMP("
                "LISP65_C2_FRAME_ATTR_INNER_VM);\n"
                "    result = vm_run_dir((int)main, 0, 0);\n"
                "    C2_INSTALL_TRACE_ENTER_INNER();")
        replace("inner-transition-does-not-lock", "header",
                "(LISP65_C2_INSTALL_PRIMARY_LOCKED \\\n"
                "             | LISP65_C2_INSTALL_INNER_ENTERED)",
                "LISP65_C2_INSTALL_INNER_ENTERED")
        replace("missing-decoder-stamp", "decoder",
                "C2_INSTALL_DECODER_STAMP(LISP65_C2_PHASE_04_SLOT);", "")
        replace("missing-emitter-stamp", "emitter",
                "C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_EMIT_NAME_SLOT);", "")
        replace("missing-append-stamp", "runtime",
                "C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_APPEND_ENVELOPE_SLOT);", "")
        replace("wrong-slot-identity", "runtime",
                "C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_APPEND_HEADER_SLOT);",
                "C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_APPEND_ENTRIES_SLOT);")
        replace("hot-refill-stamps-trace", "v2_decoder",
                "C2_V2_SLICE(13) uint8_t c2_stream_phase_13(void *opaque) {",
                "C2_V2_SLICE(13) uint8_t c2_stream_phase_13(void *opaque) {\n"
                "    C2_INSTALL_V2_STAMP(LISP65_C2_PHASE_13_SLOT);")
        replace("cleanup-stamp-ignores-lock", "runtime",
                "C2_INSTALL_TRACE_STAMP_SLOT_IF_UNLOCKED(\n"
                "        LISP65_C2_APPEND_ROLLBACK_FINALIZE_SLOT);",
                "C2_INSTALL_TRACE_STAMP_SLOT(\n"
                "        LISP65_C2_APPEND_ROLLBACK_FINALIZE_SLOT);")
        replace("cleanup-locks-after-own-stamp", "runtime",
                "C2_INSTALL_TRACE_LOCK_PRIMARY();\n"
                "    C2_INSTALL_TRACE_STAMP_SLOT_IF_UNLOCKED(\n"
                "        LISP65_C2_APPEND_ROLLBACK_UNPUBLISH_SLOT);",
                "C2_INSTALL_TRACE_STAMP_SLOT_IF_UNLOCKED(\n"
                "        LISP65_C2_APPEND_ROLLBACK_UNPUBLISH_SLOT);\n"
                "    C2_INSTALL_TRACE_LOCK_PRIMARY();")
        replace("inner-status-overwritten", "runtime",
                "if (vm_status != VM_OK) return NIL;",
                "vm_status = VM_BADOPCODE;")
        for name, trial in trials.items():
            try:
                source_gate(trial, mutations=False)
            except (GateError, KeyError, ValueError):
                rejected[name] = "rejected"
            else:
                raise GateError(f"first-fault mutation accepted: {name}")
        expected = {name.replace("_", "-") for name in
                    contract["required_mutations"]}
        require(set(rejected) == expected,
                "first-fault mutation inventory drift")
    return {
        "status": "passed-first-error-stamp-wins-contract",
        "storage": storage,
        "writers": {"decoder": len(DECODER_STAMPS) + len(V2_STAMPS),
                    "emitter": len(EMITTER_STAMPS),
                    "append_rollback": len(APPEND_STAMPS),
                    "resident": 1},
        "cleanup_locks": ["rollback_unpublish", "abort_control", "inner_vm"],
        "fixture": fixture(), "negative_mutations": rejected,
        "renderer_change": False, "refill_boundary_claimed": False,
    }


def linked_gate(elf: Path, llvm_readobj: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=llvm_readobj)
    scratch = truth.symbol("lisp65_c2_phase_scratch")
    installer = truth.symbol("c2_product_install")
    require(scratch.symbol_type == "Object" and scratch.bytes == 304,
            "linked trace is not the existing 304-byte scratch object")
    require(installer.symbol_type == "Function" and installer.bytes > 0,
            "linked installer function absent")
    names = {row.name for row in truth.symbols}
    require("c2_install_phase_mark" not in names,
            "retired linked resident marker survived")
    extra = [row.name for row in truth.symbols
             if row.symbol_type == "Object"
             and row.name.startswith("c2_install_phase_")]
    require(not extra, "self-stamp contract introduced a state object")
    required = (
        "c2_session_emit_prepare_phase", "c2_session_emit_final_crc_phase",
        "c2_stream_phase_04", "c2_stream_phase_12",
        "c2_append_envelope_phase", "c2_append_header_phase",
        "c2_append_rollback_unpublish_phase",
        "c2_append_rollback_finalize_phase",
    )
    linked = {}
    for name in required:
        symbol = truth.symbol(name)
        require(symbol.symbol_type == "Function" and symbol.bytes > 0,
                f"linked self-stamping phase absent: {name}")
        linked[name] = {"section": symbol.section,
                        "address": symbol.value, "bytes": symbol.bytes}
    return {
        "status": "passed-linked-first-error-stamped-install-provenance",
        "scratch": {"address": scratch.value, "bytes": scratch.bytes,
                    "first_error_slot_address": scratch.value + 302,
                    "trace_flags_address": scratch.value + 303},
        "installer": {"address": installer.value, "bytes": installer.bytes},
        "representative_phase_entries": linked,
        "new_state_objects": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check-source", "check-elf"))
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--llvm-readobj", type=Path,
                        default=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    args = parser.parse_args()
    try:
        if args.command == "check-elf":
            require(args.elf is not None, "--elf is required")
        value = (source_gate(mutations=True) if args.command == "check-source"
                 else linked_gate(args.elf, args.llvm_readobj))
    except (GateError, OSError, ValueError, KeyError, TypeError,
            json.JSONDecodeError) as error:
        print(f"c2-install-phase-discriminator: FAIL: {error}", file=sys.stderr)
        return 1
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
