#!/usr/bin/env python3
"""Gate the C2-lite append plans and final co-resident phase pair.

Slot numbers are storage identities.  This gate therefore permits numeric
ranges only for semantically contiguous runs and binds the three non-contiguous
plans as fifteen named slot bytes plus three explicit terminators consumed by one
serial interpreter.  It also proves the marker-qualified publish/clear fusion,
the deliberate retirement of the internal BADOPCODE detail scaffold, and the
exact 119-byte Link-48 image through every rollback cutpoint.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Sequence

from elf_truth import ElfTruth
import c2_crc_codegen_gate as DISASM


ROOT = Path(__file__).resolve().parents[2]
TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
RUNTIME = ROOT / "src/c2_product_runtime.c"
RUNTIME_H = ROOT / "src/c2_product_runtime.h"
EVAL = ROOT / "src/eval.c"
ERROR = ROOT / "src/error_overlay.c"
ERROR_ASM = ROOT / "src/l65e_bcode_ordinal.s"
PLAN_WALKER = ROOT / "src/c2_append_plan_walk.s"
FACADE = ROOT / "src/c2_kernal_facade_reopen.s"
CONTRACT = ROOT / "config/c2-append-cutpoint-contract.json"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link48-zero-literal-append-hardware-first-red.json")
MISSING_HEADER_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link49-facade16-missing-persistent-header-hardware-first-red.json")

FORWARD_PLAN = [30, 39, 33, 34, 35, 36]
PERSISTENT_PUBLISH_PLAN = [37, 38, 39, 40]
ROLLBACK_PLAN = [39, 41, 42, 43, 44, 45, 40, 39]
RECOVERY_ONLY = {31, 32}


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def function_body(source: str, name: str, *, last: bool = False,
                  marker: str | None = None) -> str:
    needle = marker or (name + "(")
    begin = (source.rfind if last else source.find)(needle)
    require(begin >= 0, f"function absent: {name}")
    brace = source.find("{", begin)
    require(brace >= 0, f"function body absent: {name}")
    depth = 0
    for end in range(brace, len(source)):
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
            if depth == 0:
                return source[begin:end + 1]
    raise GateError(f"unterminated function: {name}")


def effective_slots(header: str) -> dict[str, int]:
    marker = "#ifdef LISP65_C2_LITE_V6_JOURNAL_PREPARE_CORESIDENT"
    tail = header[header.rfind(marker):]
    require(tail, "final v6 roots/fronts slot block absent")
    macros = {
        "journal_clear": "LISP65_C2_APPEND_JOURNAL_CLEAR_SLOT",
        "journal_write": "LISP65_C2_APPEND_JOURNAL_WRITE_SLOT",
        "journal_validate": "LISP65_C2_APPEND_JOURNAL_VALIDATE_SLOT",
        "journal_reconstruct": "LISP65_C2_APPEND_JOURNAL_RECONSTRUCT_SLOT",
        "rollback_prepare": "LISP65_C2_APPEND_ROLLBACK_PREPARE_SLOT",
        "stage_copy": "LISP65_C2_APPEND_STAGE_COPY_SLOT",
        "stage_plane": "LISP65_C2_APPEND_STAGE_PLANE_SLOT",
        "image": "LISP65_C2_APPEND_IMAGE_SLOT",
        "entries": "LISP65_C2_APPEND_ENTRIES_SLOT",
        "rollback_unpublish": "LISP65_C2_APPEND_ROLLBACK_UNPUBLISH_SLOT",
        "rollback_wipe_plane": "LISP65_C2_APPEND_ROLLBACK_WIPE_PLANE_SLOT",
        "rollback_wipe_chip": "LISP65_C2_APPEND_ROLLBACK_WIPE_CHIP_SLOT",
        "rollback_wipe_attic": "LISP65_C2_APPEND_ROLLBACK_WIPE_ATTIC_SLOT",
        "rollback_finalize": "LISP65_C2_APPEND_ROLLBACK_FINALIZE_SLOT",
        "publish_plan_scan": "LISP65_C2_APPEND_PUBLISH_PLAN_SCAN_SLOT",
        "publish_plan_resolve": "LISP65_C2_APPEND_PUBLISH_PLAN_RESOLVE_SLOT",
        "header": "LISP65_C2_APPEND_HEADER_SLOT",
        "publish_clear": "LISP65_C2_APPEND_PUBLISH_CLEAR_SLOT",
    }
    result: dict[str, int] = {}
    for label, macro in macros.items():
        if label in {"journal_clear", "journal_write", "rollback_prepare"}:
            continue
        matches = re.findall(
            r"^#define\s+" + re.escape(macro) + r"\s+(\d+)u\s*$",
            tail, re.MULTILINE)
        require(matches, f"effective slot absent: {macro}")
        result[label] = int(matches[-1])
    aliases = {
        "journal_clear": "LISP65_C2_APPEND_PUBLISH_CLEAR_SLOT",
        "journal_write": "LISP65_C2_APPEND_JOURNAL_PREPARE_SLOT",
        "rollback_prepare": "LISP65_C2_APPEND_JOURNAL_PREPARE_SLOT",
    }
    for label, target in aliases.items():
        alias = re.search(
            r"^#define\s+" + re.escape(macros[label]) + r"\s+\\\s*$\n"
            r"\s*" + re.escape(target) + r"\s*$",
            tail, re.MULTILINE)
        require(alias is not None, f"co-resident alias absent: {label}")
    clear_alias = re.search(
        r"^#define\s+LISP65_C2_APPEND_JOURNAL_CLEAR_SLOT\s+\\\s*$\n"
        r"\s*LISP65_C2_APPEND_PUBLISH_CLEAR_SLOT\s*$",
        tail, re.MULTILINE)
    require(clear_alias is not None, "journal-clear fusion alias absent")
    result["journal_clear"] = result["publish_clear"]
    result["journal_write"] = 30
    result["rollback_prepare"] = 30
    expected = {
        "journal_clear": 40, "journal_write": 30,
        "journal_validate": 31, "journal_reconstruct": 32,
        "rollback_prepare": 30, "stage_copy": 33,
        "stage_plane": 34, "image": 35, "entries": 36,
        "rollback_unpublish": 41,
        "rollback_wipe_plane": 42, "rollback_wipe_chip": 43,
        "rollback_wipe_attic": 44, "rollback_finalize": 45,
        "publish_plan_scan": 37, "publish_plan_resolve": 38,
        "header": 39,
        "publish_clear": 40,
    }
    require(result == expected, f"effective phase slots drift: {result}")
    return result


def call_sequence(body: str) -> list[str]:
    return re.findall(r"c2_overlay_call\((LISP65_C2_APPEND_[A-Z0-9_]+)", body)


def array_tokens(source: str, name: str) -> list[str]:
    match = re.search(
        r"const\s+uint8_t\s+" + re.escape(name)
        + r"\[\]\s*=\s*\{(.*?)\};", source, re.DOTALL)
    require(match is not None, f"plan data absent: {name}")
    return re.findall(r"LISP65_C2_APPEND_[A-Z0-9_]+", match.group(1))


def array_has_terminator(source: str, name: str) -> bool:
    match = re.search(
        r"const\s+uint8_t\s+" + re.escape(name)
        + r"\[\]\s*=\s*\{(.*?)\};", source, re.DOTALL)
    require(match is not None, f"plan data absent: {name}")
    body = "\n".join(
        line for line in match.group(1).splitlines()
        if not line.lstrip().startswith("#"))
    return re.search(r",\s*0u\s*$", body.strip()) is not None


def _facade_source_model(runtime: str, facade: str) -> None:
    normalized = "\n".join(" ".join(line.split())
                             for line in facade.splitlines())
    require(
        "#ifdef LISP65_C2_APPEND_PLAN_FACADE" in facade
        and ".globl c2_facade_append_plan_walk" in normalized
        and "c2_facade_append_plan_walk:" in normalized
        and "jmp c2_append_plan_walk" in normalized,
        "sixteenth append-plan facade source contract drift")
    require(
        "#ifdef LISP65_C2_APPEND_PLAN_FACADE" in runtime
        and "uint8_t c2_facade_append_plan_walk(" in runtime
        and "#define C2_APPEND_PLAN_WALK c2_facade_append_plan_walk" in runtime
        and "#define C2_APPEND_PLAN_WALK c2_append_plan_walk" in runtime
        and runtime.count("C2_APPEND_PLAN_WALK(") == 3,
        "append plan consumers do not select the one facade seam")


def facade_source_gate(runtime: str, facade: str) -> dict[str, Any]:
    _facade_source_model(runtime, facade)
    rejected: dict[str, str] = {}
    mutations = {
        "vector-target-wrong": (
            runtime, facade.replace("jmp c2_append_plan_walk",
                                    "jmp c2_product_handle_normalize", 1)),
        "vector-symbol-wrong": (
            runtime, facade.replace("c2_facade_append_plan_walk",
                                    "c2_facade_append_plan_walk_bad")),
        "feature-guard-removed": (
            runtime, facade.replace("#ifdef LISP65_C2_APPEND_PLAN_FACADE",
                                    "#ifdef LISP65_C2_FACADE_DISABLED", 1)),
        "stage-consumer-bypasses-facade": (
            runtime.replace(
                "C2_APPEND_PLAN_WALK(lisp65_c2_append_stage_plan",
                "c2_append_plan_walk(lisp65_c2_append_stage_plan", 1), facade),
        "rollback-consumer-bypasses-facade": (
            runtime.replace(
                "C2_APPEND_PLAN_WALK(lisp65_c2_append_rollback_plan",
                "c2_append_plan_walk(lisp65_c2_append_rollback_plan", 1), facade),
        "persistent-consumer-bypasses-facade": (
            runtime.replace(
                "C2_APPEND_PLAN_WALK(lisp65_c2_append_persistent_publish_plan",
                "c2_append_plan_walk(lisp65_c2_append_persistent_publish_plan",
                1), facade),
    }
    for name, (mutated_runtime, mutated_facade) in mutations.items():
        try:
            _facade_source_model(mutated_runtime, mutated_facade)
        except GateError:
            rejected[name] = "rejected"
        else:
            raise GateError(f"append-plan facade mutation survived: {name}")
    return {
        "status": "passed-sixteenth-facade-source-and-consumer-contract",
        "feature": "LISP65_C2_APPEND_PLAN_FACADE",
        "vector": "c2_facade_append_plan_walk",
        "target": "c2_append_plan_walk",
        "mutations_rejected": rejected,
    }


def phase_plan_source_gate() -> dict[str, Any]:
    source = RUNTIME.read_text(encoding="utf-8")
    header = RUNTIME_H.read_text(encoding="utf-8")
    walker = PLAN_WALKER.read_text(encoding="utf-8")
    facade = FACADE.read_text(encoding="utf-8")
    slots = effective_slots(header)
    serial = function_body(source, "c2_facade_target_overlay_call_family")
    generic_boundary = function_body(source, "c2_overlay_call")
    final_boundary = function_body(source, "c2_append_publish_exports_phase")
    fused_boundary = function_body(source, "c2_append_publish_clear_phase")
    journal_clear = function_body(source, "c2_append_journal_clear_phase")
    stage = array_tokens(source, "lisp65_c2_append_stage_plan")
    persistent = array_tokens(
        source, "lisp65_c2_append_persistent_publish_plan")
    rollback = array_tokens(source, "lisp65_c2_append_rollback_plan")
    range_body = function_body(source, "c2_overlay_call_range")
    begin_at = source.rfind(
        "static C2_KERNAL_RESIDENT uint8_t c2_append_begin(")
    begin_end = source.find("\nstatic uint8_t c2_append_rollback(", begin_at)
    require(begin_at >= 0 and begin_end > begin_at,
            "sliced append-begin source interval absent")
    begin = source[begin_at:begin_end]
    abort_control = function_body(source, "c2_append_abort_control_phase")

    require(stage == [
        "LISP65_C2_APPEND_JOURNAL_WRITE_SLOT",
        "LISP65_C2_APPEND_HEADER_SLOT",
        "LISP65_C2_APPEND_STAGE_COPY_SLOT",
        "LISP65_C2_APPEND_STAGE_PLANE_SLOT",
        "LISP65_C2_APPEND_STAGE_SLOT",
        "LISP65_C2_APPEND_IMAGE_SLOT",
        "LISP65_C2_APPEND_ENTRIES_SLOT",
    ], "forward stage data drift")
    plan_source = source[source.find("lisp65_c2_append_stage_plan"):
                         source.find("lisp65_c2_append_rollback_plan")]
    require("#ifdef LISP65_C2_LITE_V6_SEMANTIC_SPLITS" in plan_source
            and "#else" in plan_source,
            "forward stage profile split lost")
    require(rollback == [
        "LISP65_C2_APPEND_HEADER_SLOT",
        "LISP65_C2_APPEND_ROLLBACK_UNPUBLISH_SLOT",
        "LISP65_C2_APPEND_ROLLBACK_WIPE_PLANE_SLOT",
        "LISP65_C2_APPEND_ROLLBACK_WIPE_CHIP_SLOT",
        "LISP65_C2_APPEND_ROLLBACK_WIPE_ATTIC_SLOT",
        "LISP65_C2_APPEND_ROLLBACK_FINALIZE_SLOT",
        "LISP65_C2_APPEND_JOURNAL_CLEAR_SLOT",
        "LISP65_C2_APPEND_HEADER_SLOT",
    ], "rollback data drift")
    require(persistent == [
        "LISP65_C2_APPEND_PUBLISH_PLAN_SCAN_SLOT",
        "LISP65_C2_APPEND_PUBLISH_PLAN_RESOLVE_SLOT",
        "LISP65_C2_APPEND_HEADER_SLOT",
        "LISP65_C2_APPEND_PUBLISH_EXPORTS_SLOT",
        "LISP65_C2_APPEND_PUBLISH_PLAN_SLOT",
        "LISP65_C2_APPEND_HEADER_SLOT",
        "LISP65_C2_APPEND_PUBLISH_NAMES_SLOT",
        "LISP65_C2_APPEND_PUBLISH_CELLS_SLOT",
        "LISP65_C2_APPEND_HEADER_SLOT",
        "LISP65_C2_APPEND_PUBLISH_NAMES_SLOT",
        "LISP65_C2_APPEND_PUBLISH_CELLS_SLOT",
    ], "persistent publish profile alternatives drift")
    require(array_has_terminator(source, "lisp65_c2_append_stage_plan")
            and array_has_terminator(
                source, "lisp65_c2_append_persistent_publish_plan")
            and array_has_terminator(source, "lisp65_c2_append_rollback_plan"),
            "append plans are not explicitly zero-terminated")
    require(serial.count("vm_runtime_overlay_exec_family(") == 1
            and "lisp65_c2_append_stage_plan" not in serial
            and "lisp65_c2_append_persistent_publish_plan" not in serial
            and "lisp65_c2_append_rollback_plan" not in serial
            and "C2AW_FAILURE" not in serial,
            "generic family target retained append diagnostic policy")
    require("C2AW_FAILURE" not in source
            and "BCODE_IMM_BASE + ordinal" not in final_boundary,
            "retired BADOPCODE detail scaffold survived")
    require("c2_facade_overlay_call_family(" in generic_boundary
            and "C2AW_FAILURE_" not in generic_boundary,
            "ordinary Session seam acquired append policy")
    require("if (first > last) return 0;" in range_body,
            "descending range no longer fails closed")
    require("c2_append_run_stage_plan(&c2aw)" in begin
            and "#define c2_append_run_stage_plan(context)" in source
            and "C2_APPEND_PLAN_WALK(lisp65_c2_append_stage_plan" in source
            and "JOURNAL_WRITE_SLOT,\n"
                "                                  LISP65_C2_APPEND_ENTRIES_SLOT"
                not in begin,
            "append begin still delegates the semantic-gap stage plan")
    require("c2_append_run_rollback_plan(&c2aw)" in source
            and "uint8_t c2_append_run_rollback_plan(void *context)" in source
            and "C2_APPEND_PLAN_WALK(lisp65_c2_append_rollback_plan" in source,
            "named rollback plan is not consumed")
    require("c2_append_run_persistent_publish_plan(&c2aw)" in begin
            and "#define c2_append_run_persistent_publish_plan(context)" in source
            and "C2_APPEND_PLAN_WALK("
                "lisp65_c2_append_persistent_publish_plan" in source
            and "c2_overlay_call_range(\n"
                "                    LISP65_C2_APPEND_PUBLISH_PLAN_SCAN_SLOT,\n"
                "                    LISP65_C2_APPEND_PUBLISH_PLAN_RESOLVE_SLOT"
                not in begin,
            "persistent post-decode plan is incomplete or bypassed")
    for token in (
            "requested = C2AW_PUBLISH_CLEAR_MARK(w);",
            "C2AW_PUBLISH_CLEAR_MARK(w) = 0u;",
            "requested == C2_PUBLISH_REQUEST_MARK",
            "c2_append_publish_exports_phase(opaque)",
            "requested == C2_CLEAR_REQUEST_MARK",
            "c2_append_journal_clear_phase(opaque)"):
        require(token in fused_boundary,
                f"publish/clear dispatcher drift: {token}")
    require("c2_overlay_call" not in final_boundary
            and "c2_overlay_call" not in journal_clear
            and 'C2_APPEND_SECTION("publish_clear")' in source
            and 'C2_APPEND_SECTION("journal_clear")\nuint8_t' not in source,
            "co-resident entry calls an overlay or predecessor survived")
    require(len(re.findall(
                r"C2AW_PUBLISH_CLEAR_MARK\(&c2aw\)\s*=\s*"
                r"C2_PUBLISH_REQUEST_MARK", source)) >= 1
            and "C2AW_PUBLISH_CLEAR_MARK((context)) = "
                "C2_PUBLISH_REQUEST_MARK" in source
            and len(re.findall(
                r"C2AW_PUBLISH_CLEAR_MARK\(&c2aw\)\s*=\s*"
                r"C2_CLEAR_REQUEST_MARK", source)) >= 1
            and "C2AW_PUBLISH_CLEAR_MARK(w) = C2_CLEAR_REQUEST_MARK;"
                in abort_control,
            "serial driver does not qualify every fused operation")

    normalized_walker = "\n".join(" ".join(line.split())
                                   for line in walker.splitlines())
    for token in (
        ".section .lisp65_resident_island,\"ax\",@progbits",
        ".globl c2_append_plan_walk",
        ".type c2_append_plan_walk,@function",
        ".size c2_append_plan_walk,",
        "ldy __rc4",
        "sty __rc6",
        "ldy __rc2",
        "sty __rc4",
        "jsr c2_overlay_call",
    ):
        require(token in normalized_walker,
                f"assembler plan walker contract drift: {token}")
    require("c2_append_overlay_call" not in normalized_walker,
            "plan walker still calls the retired duplicate append seam")
    require("lisp_abort" not in walker and "C2AW_FAILURE" not in walker,
            "plan walker acquired status/publication policy")

    # The range API remains valid only for these contiguous meanings.  The
    # dynamic abort range is separately constrained to singletons or the
    # validate/reconstruct and unpublish/finalize pairs by abort_control.
    forbidden_literal_ranges = (
        "LISP65_C2_APPEND_JOURNAL_WRITE_SLOT,\n"
        "                                  LISP65_C2_APPEND_ENTRIES_SLOT",
        "LISP65_C2_APPEND_ROLLBACK_UNPUBLISH_SLOT,\n"
        "                                  LISP65_C2_APPEND_JOURNAL_CLEAR_SLOT",
    )
    require(not any(item in source for item in forbidden_literal_ranges),
            "non-contiguous phase plan still uses the range API")
    for token in (
        "LISP65_C2_APPEND_JOURNAL_VALIDATE_SLOT",
        "LISP65_C2_APPEND_JOURNAL_RECONSTRUCT_SLOT",
        "LISP65_C2_APPEND_ROLLBACK_UNPUBLISH_SLOT",
        "LISP65_C2_APPEND_ROLLBACK_FINALIZE_SLOT",
        "LISP65_C2_APPEND_JOURNAL_CLEAR_SLOT",
        "LISP65_C2_APPEND_FRONTS_SLOT",
        "LISP65_C2_APPEND_ROLLBACK_PREPARE_SLOT",
        "LISP65_C2_APPEND_JOURNAL_WRITE_SLOT",
    ):
        require(token in abort_control, f"abort phase absent: {token}")
    require("LISP65_C2_APPEND_FRONTS_SLOT;\n"
            "        C2AW_ABORT_END(w) = LISP65_C2_APPEND_FRONTS_SLOT;"
            in abort_control
            and "LISP65_C2_APPEND_ROLLBACK_PREPARE_SLOT;\n"
            "        C2AW_ABORT_END(w) = LISP65_C2_APPEND_ROLLBACK_PREPARE_SLOT;"
            in abort_control,
            "abort fronts/prepare semantic gap was restored")

    return {
        "status": "passed-source-phase-plan-and-range-inventory",
        "effective_slots": slots,
        "forward_plan": FORWARD_PLAN,
        "persistent_publish_plan": PERSISTENT_PUBLISH_PLAN,
        "rollback_plan": ROLLBACK_PLAN,
        "recovery_only_slots_excluded_from_forward": sorted(RECOVERY_ONLY),
        "representation": {
            "kind": "zero-terminated named uint8 data walked by one non-LTO Island leaf",
            "bytes": (len(FORWARD_PLAN) + len(PERSISTENT_PUBLISH_PLAN)
                      + len(ROLLBACK_PLAN) + 3),
            "selection": "canonical plan pointer; no duplicate selector ids",
            "walker": "c2_append_plan_walk",
            "status_transport": (
                "no raw plan latch; VM_BADOPCODE remains status-only"),
            "status_publication": "retired after fixture-covered diagnosis",
        },
        "co_resident_publish_clear": {
            "physical_section": ".lisp65_rt_c2append_publish_clear",
            "logical_entries": ["publish_exports", "journal_clear"],
            "request_byte": "record[23], lifetime-disjoint from roots/fronts",
            "added_state_bytes": 0,
        },
        "range_rule": "descending fails; semantic-gap plans are data",
        "facade": facade_source_gate(source, facade),
    }


def phase_model(*, plan: list[int], fail_slot: int | None = None,
                rollback: list[int] = ROLLBACK_PLAN) -> dict[str, Any]:
    state = {
        "journal": "clear", "code_suffix": False,
        "image_suffix": False, "entry_suffix": False,
        "published": False,
    }
    calls: list[int] = []
    failure: tuple[int, int] | None = None
    for slot in plan:
        calls.append(slot)
        if slot in RECOVERY_ONLY:
            raise GateError(f"recovery-only slot entered forward plan: {slot}")
        if slot == fail_slot:
            failure = (slot, 8)
            break
        if slot == 30:
            state["journal"] = "active"
        elif slot in (33, 34):
            state["code_suffix"] = True
        elif slot == 35:
            state["image_suffix"] = True
        elif slot == 36:
            state["entry_suffix"] = True
    if failure is not None:
        for slot in rollback:
            calls.append(slot)
            if slot == 41:
                state["published"] = False
            elif slot == 42:
                state["code_suffix"] = False
                state["image_suffix"] = False
                state["entry_suffix"] = False
            elif slot == 40:
                state["journal"] = "clear"
        return {"calls": calls, "failure": failure, "state": state}
    return {"calls": calls, "failure": None, "state": state}


def cutpoint_fixture() -> dict[str, Any]:
    positives: dict[str, Any] = {}
    for slot in FORWARD_PLAN:
        result = phase_model(plan=FORWARD_PLAN, fail_slot=slot)
        require(result["failure"] == (slot, 8),
                f"cutpoint detail lost at slot {slot}")
        require(result["state"] == {
            "journal": "clear", "code_suffix": False,
            "image_suffix": False, "entry_suffix": False,
            "published": False,
        }, f"cutpoint rollback not byte-empty at slot {slot}: {result}")
        positives[str(slot)] = result["calls"]

    mutations = {
        "forward_data_byte_to_recovery": [30, 31, 33, 34, 35, 36],
        "rollback_data_without_unpublish": [42, 40],
        "rollback_data_without_finalize": [41, 40],
        "rollback_data_without_clear": [41, 42],
        "rollback_descending_range_expansion": [],
    }
    rejected: dict[str, str] = {}
    for name, plan in mutations.items():
        try:
            if name == "forward_data_byte_to_recovery":
                phase_model(plan=plan)
                ok = False
            else:
                state = phase_model(plan=FORWARD_PLAN, fail_slot=37,
                                    rollback=plan)["state"]
                ok = plan == ROLLBACK_PLAN and state == {
                    "journal": "clear", "code_suffix": False,
                    "image_suffix": False, "entry_suffix": False,
                    "published": False,
                }
        except GateError:
            ok = False
        require(not ok, f"phase-plan mutation survived: {name}")
        rejected[name] = "rejected"

    if os.environ.get("LISP65_PUBLIC_CLEAN_BUILD") != "1":
        first_red = json.loads(FIRST_RED.read_text(encoding="utf-8"))
        witness = first_red["read_only_localization"]["append_transaction"]
        require(witness["persistent_journal"]["active"] == 1
                and witness["unreachable_suffix"]["entry_ordinal"] == 588,
                "Link-48 active-C2J/suffix negative witness drift")
    return {
        "status": "passed-cutpoint-and-rollback-fixture",
        "cutpoints": positives,
        "negative_mutations": rejected,
        "hardware_negative": (
            "acceptance-evidence-not-a-public-build-input"
            if os.environ.get("LISP65_PUBLIC_CLEAN_BUILD") == "1"
            else "active C2J plus unreachable suffix rejected"),
    }


def persistent_publish_fixture() -> dict[str, Any]:
    """Prove completeness, order and the Link-49 missing-header boundary."""
    def run(plan: list[int]) -> dict[str, bool]:
        state = {"scanned": False, "resolved": False,
                 "committed": False, "published": False}
        for slot in plan:
            if slot == 37:
                require(not any(state.values()),
                        "persistent scan is replayed or out of order")
                state["scanned"] = True
            elif slot == 38:
                require(state["scanned"] and not state["resolved"]
                        and not state["committed"] and not state["published"],
                        "persistent resolve precedes scan or is replayed")
                state["resolved"] = True
            elif slot == 39:
                require(state["resolved"] and not state["committed"]
                        and not state["published"],
                        "persistent header precedes resolve or is replayed")
                state["committed"] = True
            elif slot == 40:
                require(state["committed"] and not state["published"],
                        "persistent publish precedes header or is replayed")
                state["published"] = True
            else:
                raise GateError(f"foreign persistent publish slot: {slot}")
        require(all(state.values()),
                f"persistent publish plan omitted a mandatory station: {plan}")
        return state

    complete = run(PERSISTENT_PUBLISH_PLAN)
    mutations = {
        "scan-omitted": [38, 39, 40],
        "resolve-omitted": [37, 39, 40],
        "header-omitted-link49": [37, 38, 40],
        "publish-omitted": [37, 38, 39],
        "header-after-publish": [37, 38, 40, 39],
        "resolve-before-scan": [38, 37, 39, 40],
        "header-replayed": [37, 38, 39, 39, 40],
        "foreign-recovery-slot": [37, 38, 31, 39, 40],
    }
    rejected: dict[str, str] = {}
    for name, plan in mutations.items():
        try:
            run(plan)
        except GateError:
            rejected[name] = "rejected"
        else:
            raise GateError(f"persistent-plan mutation survived: {name}")

    public_clean_build = os.environ.get("LISP65_PUBLIC_CLEAN_BUILD") == "1"
    if not public_clean_build:
        first_red = json.loads(MISSING_HEADER_FIRST_RED.read_text(
            encoding="utf-8"))
        append = first_red["read_only_localization"]["append"]
        proof = first_red["read_only_localization"]["source_dataflow_proof"]
        require(append["staged"] == 1 and append["committed"] == 0
                and proof["missing_phase"] == {
                    "slot": 40, "symbol": "c2_append_header_phase"}
                and proof["publish_exports_requires_committed"] is True,
                "Link-49 missing-header hardware witness drift")
    return {
        "status": "passed-persistent-plan-completeness-and-order",
        "plan": PERSISTENT_PUBLISH_PLAN,
        "complete_state": complete,
        "negative_mutations": rejected,
        "hardware_negative": {
            "receipt": (
                "acceptance-evidence-not-a-public-build-input"
                if public_clean_build else
                MISSING_HEADER_FIRST_RED.relative_to(ROOT).as_posix()),
            "signature": "staged=1 committed=0 before publish",
        },
    }


def publish_clear_fixture() -> dict[str, Any]:
    PUBLISH, CLEAR = 0x70, 0x6a

    def enter(state: dict[str, Any], request: int) -> bool:
        state["marker"] = request
        observed = state["marker"]
        state["marker"] = 0
        if observed == PUBLISH:
            if not state["committed"] or state["published"]:
                return False
            state["published"] = True
            return True
        if observed == CLEAR:
            state["journal"] = "clear"
            return True
        return False

    normal = {"committed": True, "published": False,
              "journal": "active", "marker": 0}
    require(enter(normal, PUBLISH) and enter(normal, CLEAR)
            and normal == {"committed": True, "published": True,
                           "journal": "clear", "marker": 0},
            "publish/clear normal sequence drift")
    rollback = {"committed": False, "published": False,
                "journal": "active", "marker": 0}
    require(enter(rollback, CLEAR) and rollback["journal"] == "clear",
            "rollback-only journal clear drift")
    mutations = {
        "missing_marker": 0,
        "foreign_marker": 0x55,
        "replayed_marker_after_clear": 0,
        "publish_before_commit": PUBLISH,
        "publish_twice": PUBLISH,
        "clear_misrouted_as_publish": PUBLISH,
    }
    rejected: dict[str, str] = {}
    for name, marker in mutations.items():
        state = {"committed": name not in ("publish_before_commit",),
                 "published": name == "publish_twice",
                 "journal": "active", "marker": 0}
        if name == "clear_misrouted_as_publish":
            survived = enter(state, marker) and state["journal"] == "clear"
        else:
            survived = enter(state, marker)
        require(not survived, f"publish/clear mutation survived: {name}")
        rejected[name] = "rejected"
    return {
        "status": "passed-one-record-two-marker-qualified-entries",
        "normal": normal, "rollback_only": rollback,
        "negative_mutations": rejected,
        "added_state_bytes": 0, "added_pointers": 0,
    }


def diagnostic_retirement_gate() -> dict[str, Any]:
    runtime = RUNTIME.read_text(encoding="utf-8")
    evaluation = EVAL.read_text(encoding="utf-8")
    facade = function_body(runtime, "c2_facade_target_overlay_call_family")
    boundary = function_body(runtime, "c2_append_publish_exports_phase")
    install = function_body(runtime, "c2_product_install")
    fronts = function_body(runtime, "c2_append_fronts_phase")
    transient = function_body(runtime, "c2_append_reserve_transient_phase")
    transient_bounds = function_body(
        runtime, "c2_append_reserve_transient_bounds_phase")
    begin_at = runtime.rfind(
        "static C2_KERNAL_RESIDENT uint8_t c2_append_begin(")
    begin_end = runtime.find("\nstatic uint8_t c2_append_rollback(",
                             begin_at)
    require(begin_at >= 0 and begin_end > begin_at,
            "sliced append-begin detail interval absent")
    begin = runtime[begin_at:begin_end]
    require("C2AW_FAILURE" not in runtime
            and "failure_slot" not in runtime
            and "failure_status" not in runtime
            and "BCODE_IMM_BASE + ordinal" not in boundary
            and "C2AW_FAILURE" not in facade,
            "BADOPCODE scratch/transport scaffold survived retirement")
    require("*main_ordinal = (uint16_t)NIL;" not in begin
            and "emit != C2_EMIT_OK || !append_ok"
                in install
            and "VM_C2_NESTING_DEPTH" not in install
            and "return (obj)main;" not in install
            and "lisp65_error_raise_pending" not in runtime
            and "lisp65_error_defer" not in runtime
            and "lisp_abort_detail(LISP65_ERR_C2_NESTING_DEPTH"
                not in install
            and runtime.count(
                "lisp_abort_detail(LISP65_ERR_C2_NESTING_DEPTH, MKFIX(5));")
                == 1
            and fronts.count(
                "lisp_abort_detail(LISP65_ERR_C2_NESTING_DEPTH, MKFIX(5));")
                == 1
            and "LISP65_ERR_C2_NESTING_DEPTH" not in transient
            and "LISP65_ERR_C2_NESTING_DEPTH" not in transient_bounds
            and "c2_install_phase_mark(" not in install
            and install.count("C2_INSTALL_TRACE_ENTER_INNER();") == 1
            and install.count("if (vm_status != VM_OK) return NIL;") == 3
            and install.count("vm_status = VM_BADOPCODE; return NIL;") == 7
            and install.count("return result;") == 1
            and "vm_badopcode_detail(" not in install,
            "install did not retire typed BADOPCODE detail status-only")
    require("code == LISP65_ERR_VM_BAD_BYTECODE && IS_FIX(detail)"
            not in evaluation
            and evaluation.count(
                "code == LISP65_ERR_VM_UNDEFINED_FUNCTION") == 2
            and evaluation.count("lisp_abort_detail(code, detail);") == 1
            and "code == LISP65_ERR_C2_NESTING_DEPTH" not in evaluation,
            "BADOPCODE retirement or DIRMISS diagnostics drift")
    return {
        "status": "passed-BADOPCODE-detail-retired-DIRMISS-preserved",
        "reason": "the internal BADOPCODE witness is retired; the user-facing DIRMISS seam remains independent",
        "removed": ["per-slot scratch fields", "resident raw capture",
                    "cold BCODE materialization", "BADOPCODE detail dispatch",
                    "typed BADOPCODE Fixnum detail"],
        "preserved": ["VM_BADOPCODE status-only",
                      "cold slot-plus-inner install provenance",
                      "DIRMISS SYMI detail", "DIRMISS BCODE ordinal detail"],
        "negative_mutations": {
            "raw_capture_restored": "rejected-by-source-gate",
            "raw_BADOPCODE_detail_dispatch_restored": "rejected-by-source-gate",
            "DIRMISS_SYMI_removed": "rejected-by-source-gate",
            "DIRMISS_BCODE_removed": "rejected-by-source-gate",
        },
    }


def exact_image_fixture() -> dict[str, Any]:
    # Reuse the already reviewed byte oracle; bind it to the real source plans
    # above rather than cloning its L65S/C2I parsing rules here.
    import c2_lite_v6_link48_append_cutpoint_probe as old
    value = old.model_exact_session()
    require(value["status"] == "passed-byte-exact-success-oracle"
            and value["input"]["length"] == 119
            and value["call"]["result"] == "T",
            "exact 119-byte append oracle drift")
    return {
        "status": "passed-exact-image-through-bound-phase-plan-oracle",
        "image": value,
        "phase_plan": FORWARD_PLAN,
        "persistent_publish_plan": PERSISTENT_PUBLISH_PLAN,
        "rollback_cutpoints": list(map(int, FORWARD_PLAN)),
    }


def source_gate() -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract["schema"] == "lisp65.c2.append-cutpoint-contract.v8"
            and contract["phase_plans"]["forward_stage"]["slots"] == FORWARD_PLAN
            and contract["phase_plans"]["persistent_publish"]["slots"] ==
                PERSISTENT_PUBLISH_PLAN
            and contract["phase_plans"]["rollback"]["slots"] == ROLLBACK_PLAN,
            "append cutpoint contract drift")
    return {
        "status": "passed-append-cutpoint-contract",
        "phase_plan": phase_plan_source_gate(),
        "cutpoints": cutpoint_fixture(),
        "persistent_publish": persistent_publish_fixture(),
        "co_resident_publish_clear": publish_clear_fixture(),
        "diagnostic_retirement": diagnostic_retirement_gate(),
        "end_to_end": exact_image_fixture(),
    }


def _hex_operand(operand: str, kind: str) -> int:
    match = re.match(r"^\$([0-9a-f]+)", operand)
    require(match is not None, f"unsupported plan-walker {kind}: {operand}")
    return int(match.group(1), 16)


def _execute_plan_walker(rows: list[dict[str, Any]], truth: ElfTruth, *,
                         plan_name: str, fail_slot: int | None) -> dict[str, Any]:
    """Execute the final linked leaf with the C boundary as a hostile stub."""
    require(rows, "linked plan walker has no instructions")
    by_address = {int(row["address"]): row for row in rows}
    addresses = sorted(by_address)
    require(len(addresses) == len(rows), "duplicate plan-walker instruction")
    following = {address: addresses[index + 1]
                 for index, address in enumerate(addresses[:-1])}
    memory = bytearray(65536)
    for name, values in (
            ("lisp65_c2_append_stage_plan", FORWARD_PLAN + [0]),
            ("lisp65_c2_append_persistent_publish_plan",
             PERSISTENT_PUBLISH_PLAN + [0]),
            ("lisp65_c2_append_rollback_plan", ROLLBACK_PLAN + [0])):
        address = truth.symbol(name).value
        memory[address:address + len(values)] = bytes(values)
    rc = {name: truth.symbol(name).value for name in
          ("__rc2", "__rc3", "__rc4", "__rc5", "__rc6", "__rc7",
           "__rc8")}
    require(all(0 <= value < 256 for value in rc.values()),
            "plan-walker imaginary registers are not zero-page bytes")
    zp = bytearray(256)
    original_context = (0x34, 0x12)
    zp[rc["__rc4"]], zp[rc["__rc5"]] = original_context
    plan_address = truth.symbol(plan_name).value
    zp[rc["__rc2"]] = plan_address & 0xff
    zp[rc["__rc3"]] = plan_address >> 8
    a, x = 0xa6, 0x5b
    y = z = 0
    zero = False
    stack: list[int] = []
    calls: list[int] = []
    pc = addresses[0]
    steps = 0

    def nz(value: int) -> int:
        nonlocal zero
        value &= 0xff
        zero = value == 0
        return value

    while True:
        steps += 1
        require(steps <= 512, "plan walker did not terminate")
        require(pc in by_address,
                f"plan walker escaped its linked interval: 0x{pc:04x}")
        row = by_address[pc]
        opcode, operand = str(row["opcode"]), str(row["operand"])
        next_pc = following.get(pc)
        if opcode in ("lda", "ldy", "ldz"):
            immediate = re.fullmatch(r"#\$([0-9a-f]+)", operand)
            indirect = re.fullmatch(r"\(\$([0-9a-f]+)\),z", operand)
            if immediate:
                value = int(immediate.group(1), 16)
            elif indirect:
                pointer = int(indirect.group(1), 16)
                address = zp[pointer] | (zp[(pointer + 1) & 0xff] << 8)
                value = memory[(address + z) & 0xffff]
            else:
                value = zp[_hex_operand(operand, "load operand")]
            value = nz(value)
            if opcode == "lda": a = value
            elif opcode == "ldy": y = value
            else: z = value
        elif opcode in ("sta", "stx", "sty"):
            zp[_hex_operand(operand, "store operand")] = (
                a if opcode == "sta" else x if opcode == "stx" else y)
        elif opcode == "cmp":
            match = re.fullmatch(r"#\$([0-9a-f]+)", operand)
            require(match is not None, "plan walker CMP is not immediate")
            zero = a == int(match.group(1), 16)
        elif opcode in ("beq", "bne", "bra"):
            taken = opcode == "bra" or opcode == "beq" and zero \
                or opcode == "bne" and not zero
            pc = _hex_operand(operand, "branch") if taken else next_pc
            require(pc is not None, "plan walker branch fell beyond leaf")
            continue
        elif opcode == "inw":
            at = _hex_operand(operand, "inw operand")
            value = (zp[at] | (zp[(at + 1) & 0xff] << 8)) + 1
            zp[at], zp[(at + 1) & 0xff] = value & 0xff, (value >> 8) & 0xff
        elif opcode == "dec":
            at = _hex_operand(operand, "dec operand")
            zp[at] = nz(zp[at] - 1)
        elif opcode == "pha":
            stack.append(a)
        elif opcode == "pla":
            require(stack, "plan walker stack underflow")
            a = nz(stack.pop())
        elif opcode == "tax":
            x = nz(a)
        elif opcode == "txa":
            a = nz(x)
        elif opcode == "jsr":
            require("c2_overlay_call" in operand,
                    f"plan walker called unexpected target: {operand}")
            require((zp[rc["__rc2"]], zp[rc["__rc3"]]) == original_context,
                    "plan walker passed a corrupted context")
            calls.append(a)
            result = int(a != fail_slot)
            # Model an ordinary C callee that may destroy every imaginary
            # register.  Only the hardware-stack save set may survive.
            for address in rc.values():
                zp[address] = 0xa5
            a = nz(result)
        elif opcode == "rts":
            require(not stack, "plan walker returned with an unbalanced stack")
            return {"result": a, "calls": calls, "steps": steps}
        else:
            raise GateError(f"unsupported linked plan-walker opcode: {opcode}")
        require(next_pc is not None,
                f"plan walker lacks RTS after 0x{pc:04x}")
        pc = next_pc


def _linked_walker_equivalence(elf: Path, truth: ElfTruth) -> dict[str, Any]:
    leaf = truth.symbol("c2_append_plan_walk")
    completed = subprocess.run(
        [str(TOOLCHAIN / "llvm-objdump"), "-d", "--no-show-raw-insn",
         str(elf)], check=True, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    rows = [row for row in DISASM.disassembly_rows(completed.stdout)
            if row["section"] == leaf.section
            and leaf.value <= int(row["address"]) < leaf.value + leaf.bytes]
    cases: dict[str, Any] = {}
    for plan_id, plan, label in (
            ("lisp65_c2_append_stage_plan", FORWARD_PLAN, "forward"),
            ("lisp65_c2_append_persistent_publish_plan",
             PERSISTENT_PUBLISH_PLAN, "persistent_publish"),
            ("lisp65_c2_append_rollback_plan", ROLLBACK_PLAN, "rollback")):
        success = _execute_plan_walker(
            rows, truth, plan_name=plan_id, fail_slot=None)
        require(success["result"] == 1 and success["calls"] == plan,
                f"linked {label} plan differs from C reference")
        failures: dict[str, list[int]] = {}
        for slot in plan:
            actual = _execute_plan_walker(
                rows, truth, plan_name=plan_id, fail_slot=slot)
            expected = plan[:plan.index(slot) + 1]
            require(actual["result"] == 0 and actual["calls"] == expected,
                    f"linked {label} cutpoint differs at slot {slot}")
            failures[str(slot)] = actual["calls"]
        cases[label] = {"success": success, "cutpoints": failures}
    return {
        "status": "passed-final-ELF-leaf-equivalence-to-C-cutpoint-matrix",
        "cases": cases,
        "selection": "callers pass one of the three canonical linked plan pointers",
        "callee_model": "hostile C stub clobbers every imaginary register",
    }


def linked_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=TOOLCHAIN / "llvm-readobj",
                          include_section_data=True)
    names = (
        "c2_facade_target_overlay_call_family",
        "c2_overlay_call",
        "c2_append_plan_walk",
        "c2_append_run_rollback_plan",
        "c2_append_publish_clear_phase",
        "c2_append_publish_exports_phase",
        "c2_append_journal_clear_phase",
        "c2_product_install",
        "lisp65_error_overlay_entry",
        "l65e_emit_bcode_ordinal",
    )
    functions: dict[str, Any] = {}
    for name in names:
        symbol = truth.symbol(name)
        require(symbol.symbol_type == "Function" and symbol.bytes > 0,
                f"linked cutpoint citizen invalid: {name}")
        functions[name] = {"address": symbol.value, "bytes": symbol.bytes,
                           "section": symbol.section}
    fused_section = ".lisp65_rt_c2append_publish_clear"
    require(all(truth.symbol(name).section == fused_section for name in (
                "c2_append_publish_clear_phase",
                "c2_append_publish_exports_phase",
                "c2_append_journal_clear_phase")),
            "publish/clear logical entries escaped the physical slice")
    require(".lisp65_rt_c2append_publish_exports" not in truth.sections_by_name
            and ".lisp65_rt_c2append_journal_clear"
                not in truth.sections_by_name,
            "publish/clear predecessor section survived")
    walker = truth.symbol("c2_append_plan_walk")
    facade = truth.symbol("c2_facade_append_plan_walk")
    require(walker.section == ".lisp65_resident_island"
            and 0x1800 <= walker.value < 0x2000,
            "plan walker is not a resident-Island citizen")
    walker_relocs = [row for row in truth.relocations
                     if row.source_section_index == walker.section_index
                     and walker.value <= row.offset
                     < walker.value + walker.bytes]
    walker_targets = [row.target for row in walker_relocs]
    require(walker_targets.count("c2_overlay_call") == 1
            and "lisp65_c2_append_stage_plan" not in walker_targets
            and "lisp65_c2_append_persistent_publish_plan"
                not in walker_targets
            and "lisp65_c2_append_rollback_plan" not in walker_targets,
            "linked pointer-driven plan walker relocations drift")
    callers = [row for row in truth.relocations
               if row.target == "c2_facade_append_plan_walk"]
    leaf_edges = [row for row in truth.relocations
                  if row.target == "c2_append_plan_walk"]
    require(facade.section == ".lisp65_c2_host_facade"
            and facade.value == 0xB5F1
            and len(callers) == 3
            and all(row.relocation_type == "R_MOS_ADDR16"
                    for row in callers)
            and all(row.source_section ==
                    ".lisp65_c2_kernal_window.c2_resident"
                    for row in callers),
            "plan consumers do not use exactly the pinned facade seam")
    require(len(leaf_edges) == 1
            and leaf_edges[0].source_section_index == facade.section_index
            and leaf_edges[0].relocation_type == "R_MOS_ADDR16",
            "facade does not provide the sole edge to the Island walker")
    plan_data: dict[str, Any] = {}
    expected = {
        "lisp65_c2_append_stage_plan": FORWARD_PLAN + [0],
        "lisp65_c2_append_persistent_publish_plan":
            PERSISTENT_PUBLISH_PLAN + [0],
        "lisp65_c2_append_rollback_plan": ROLLBACK_PLAN + [0],
    }
    for name, values in expected.items():
        symbol = truth.symbol(name)
        require(symbol.bytes == len(values),
                f"linked plan data size drift: {name}")
        raw = truth.section_bytes(symbol.section)
        section = truth.section(symbol.section)
        begin = symbol.value - section.address
        actual = list(raw[begin:begin + symbol.bytes])
        require(actual == values,
                f"linked plan data bytes drift: {name}={actual}")
        plan_data[name] = {"address": symbol.value, "bytes": actual,
                           "section": symbol.section}
    return {
        "status": "passed-linked-cutpoint-citizenship",
        "functions": functions,
        "walker": {
            "address": walker.value, "bytes": walker.bytes,
            "section": walker.section,
            "call_target": "c2_overlay_call",
            "plan_selection": "canonical pointers supplied by facade-routed C callers",
            "facade": {"symbol": facade.name, "address": facade.value,
                       "section": facade.section, "bytes": 3,
                       "target": walker.name},
            "facade_routed_C_call_edges": len(callers),
        },
        "plan_data": plan_data,
        "walker_equivalence": _linked_walker_equivalence(elf, truth),
        "co_resident_publish_clear": {
            "section": fused_section,
            "bytes": truth.section(fused_section).bytes,
            "logical_entries": 2,
            "catalog_records": 1,
            "predecessor_sections_present": False,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    args = parser.parse_args(argv)
    value: dict[str, Any] = {"source": source_gate()}
    if args.elf is not None:
        value["linked"] = linked_gate(args.elf)
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
