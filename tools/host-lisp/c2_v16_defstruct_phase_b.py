#!/usr/bin/env python3
"""Partition the exact Link-82 defstruct stopped state into R/A/I/G.

Phase B is deliberately a design/gate artifact, not a diagnostic build.  It
binds the released Link-82 ELF and historical source, enumerates every
observable failure family on the Phase-A execution, fixes the ordinary-RAM
record layout, and proves that synthetic stopped states select exactly one of
the four pre-registered rows.  Expected opcodes always come from the bound
C2D/object schedule; refill metadata is observation, never oracle.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402
import c2_v16_defstruct_phase_a as PHASE_A_DRIVER  # noqa: E402


BASE = ROOT / "build/c2.2/v1.2.5-candidate-product-link82"
ELF = BASE / "wplto/lisp65-c2-substitution-linked.prg.elf"
DRIFTED_FINAL_ALIAS = BASE / "final/lisp65-c2-substitution-linked.prg.elf"
MAP = BASE / "wplto/lisp65-c2-substitution-linked.prg.map"
MANIFEST = BASE / "canonical-product-manifest.json"
PROFILE = BASE / "final/resolved-profile.txt"
PHASE_A = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-phase-a-host-reconstruction-receipt.json"
)
LINK82 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.5-phase-b-link82-receipt.json"
)
IRQ_DEVICE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.3-link80-bundled-hardware-receipt.json"
)
PLAN = ROOT / "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
GATES = ROOT / "mk/gates.mk"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-phase-b-guard-partition-receipt.json"
)
SOURCE_COMMIT = "fe5c98fea63236af3bddca86bf1bb955cf9a6ffe"
ELF_SHA = "3d9e4c4e7e8d0719223561c66578fb4b24058f32e42483642322a88c4884d8d6"
FORMAT = "lisp65-c2.3-v1.6-defstruct-phase-b-guard-partition-v1"
RECORDED_ON = "2026-08-04"


SOURCES = (
    "src/vm.c",
    "src/vm.h",
    "src/eval.c",
    "src/mem.c",
    "src/compile_repl.c",
    "src/c2_session_emitter.c",
    "src/c2_session_emitter.h",
    "src/c2_product_runtime.c",
    "src/c2_product_runtime.h",
    "src/c2_phase_scratch.c",
    "src/c2_phase_scratch.h",
    "src/c2_kernal_runtime.c",
    "src/c2_kernal_window.s",
    "src/interrupt.c",
)


class PhaseBError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PhaseBError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }


def git_blob(relative: str) -> bytes:
    process = subprocess.run(
        ["git", "show", f"{SOURCE_COMMIT}:{relative}"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    require(
        process.returncode == 0,
        process.stderr.decode(errors="replace").strip()
        or f"historical source absent: {relative}",
    )
    return process.stdout


def bind_git(relative: str) -> dict[str, Any]:
    data = git_blob(relative)
    return {
        "authority": "git-blob",
        "commit": SOURCE_COMMIT,
        "path": relative,
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def symbol_bytes(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    data = truth.section_bytes(symbol.section)
    begin = symbol.value - section.address
    return data[begin:begin + symbol.bytes]


def exact_elf() -> tuple[ElfTruth, dict[str, Any]]:
    manifest = load(MANIFEST)
    canonical_elf = manifest["WPLTO"]["historical_checker_boundary"][
        "current_replacement_gates"
    ][
        "pre_publish_identity"
    ]["elf"]
    require(
        canonical_elf["sha256"] == ELF_SHA
        and canonical_elf["path"] == ELF.relative_to(ROOT).as_posix()
        and bind(ELF)["sha256"] == ELF_SHA,
        "canonical Link-82 WPLTO ELF identity drift",
    )
    final_claims = [
        row
        for row in _objects(manifest)
        if row.get("path") == DRIFTED_FINAL_ALIAS.relative_to(ROOT).as_posix()
        and row.get("sha256") == ELF_SHA
    ]
    require(final_claims, "canonical manifest lacks the final Link-82 ELF role")
    final_now = bind(DRIFTED_FINAL_ALIAS)
    require(
        final_now["sha256"] != ELF_SHA,
        "local final alias unexpectedly equals the recorded drift disposition",
    )
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    require(
        len(truth.sections) == 184
        and len(truth.symbols) == 1048
        and len(truth.relocations) == 37000,
        "Link-82 structured ELF cardinality drift",
    )
    return truth, {
        "authority": bind(ELF),
        "canonical_role": canonical_elf,
        "final_alias": {
            "path": final_now["path"],
            "matches_canonical_Link82_ELF": False,
            "canonical_sha256": ELF_SHA,
        },
        "final_alias_disposition": (
            "local materialization drifted after release; not used as authority"
        ),
        "structured_counts": {
            "sections": len(truth.sections),
            "symbols": len(truth.symbols),
            "relocations": len(truth.relocations),
        },
    }


def _objects(value: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if isinstance(value, dict):
        result.append(value)
        for child in value.values():
            result.extend(_objects(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(_objects(child))
    return result


def fail_closed_graph(truth: ElfTruth) -> dict[str, Any]:
    fail = truth.symbol("c2_kernal_fail_closed")
    section = truth.section(fail.section)
    data = truth.section_bytes(fail.section)
    begin = fail.value - section.address
    body = data[begin:begin + 14]
    require(
        fail.value == 0xE08B
        and body == bytes.fromhex("78a9008d1ad0a9028d20d04c96e0"),
        "Link-82 fail-closed body drift",
    )
    red_sites = []
    needle = bytes.fromhex("a9028d20d0")
    for row in truth.sections:
        if not row.bytes or "PROGBITS" not in row.section_type:
            continue
        part = truth.section_bytes(row.name)
        for offset in range(max(0, len(part) - len(needle) + 1)):
            if part[offset:offset + len(needle)] == needle:
                red_sites.append({"section": row.name, "address": row.address + offset})
    require(
        red_sites == [{
            "section": ".lisp65_c2_kernal_window.map_switch_and_guards",
            "address": 0xE091,
        }],
        f"unique red-frame body drift: {red_sites}",
    )
    ingresses = [
        row for row in truth.relocations if row.target == "c2_kernal_fail_closed"
    ]
    require(
        [(row.source_section, row.offset, row.relocation_type) for row in ingresses]
        == [
            (".lisp65_c2_kernal_window.irq_handler", 0xE07B, "R_MOS_ADDR16"),
            (".lisp65_c2_vectors", 0xFFFC, "R_MOS_ADDR16"),
        ],
        "fail-closed ingress set drift",
    )
    irq = git_blob("src/c2_kernal_window.s").decode("utf-8")
    require(
        "lda C2K_SOURCELESS_IRQS" in irq
        and "beq .Lfirst_source_less" in irq
        and "jmp c2_kernal_fail_closed" in irq
        and ".word c2_kernal_fail_closed" in irq,
        "source-less/reset fail-closed source contract drift",
    )
    return {
        "terminal_observer": {
            "symbol": "c2_kernal_fail_closed",
            "address": "0xe08b",
            "red_store_opcode_address": "0xe093",
            "unique_red_body": True,
            "guard_is_not_blamed": True,
        },
        "direct_ingresses": [
            {
                "kind": "active-sequence-asynchronous",
                "section": ingresses[0].source_section,
                "relocation_address": "0xe07b",
                "meaning": "second consecutive source-less IRQ episode",
                "partition": "I terminal observer, or terminal co-witness for R/A/G",
            },
            {
                "kind": "external-reset-vector",
                "section": ingresses[1].source_section,
                "relocation_address": "0xfffc",
                "meaning": "RESET vector before product/session execution",
                "partition": "excluded prerequisite, not a fifth active-sequence outcome",
            },
        ],
        "reset_exclusion": {
            "no_code_relocation_to_reset_vector": True,
            "no_software_edge_from_measured_sequence": True,
            "session_rule": (
                "cold reset precedes record arm; zero monitor traffic and no reset "
                "is permitted while either measured form is active"
            ),
            "failure_policy": (
                "a reset/reboot is a session-continuity failure, never an R/A/I/G "
                "product classification"
            ),
        },
    }


def phase_a_schedule() -> dict[str, Any]:
    phase = load(PHASE_A)
    require(
        phase["format"]
        == "lisp65-c2.3-v1.6-defstruct-phase-a-host-reconstruction-v1"
        and phase["base"]["source_commit"] == SOURCE_COMMIT
        and phase["windowed_sequence"]["require"]["prim67_reads"] == 612
        and len(phase["windowed_sequence"]["forms"]) == 11
        and sum("entry" in row for row in phase["windowed_sequence"]["forms"]) == 9
        and phase["windowed_sequence"]["constructor"]["result"] == "(point 3 4)",
        "Phase-A execution authority drift",
    )
    initial = phase["windowed_sequence"]["initial_window_schedule"]
    refills = phase["windowed_sequence"]["refill_schedule"]
    require(
        initial["event_count"] == 12310
        and refills["event_count"] == 13803
        and all(
            row["expected_first_opcode"] is not None
            for row in initial["sites"] + refills["sites"]
        ),
        "Phase-A fill/opcode oracle schedule drift",
    )
    oracle_rows = [
        {
            "object": row["object"]["name"],
            "owner": {
                key: row["object"][key]
                for key in ("role", "entry_ordinal", "bank2_code_offset")
                if key in row["object"]
            },
            "payload_pc": row["payload_pc_start"],
            "expected_opcode": row["expected_first_opcode"],
            "reason": row["reason"],
        }
        for row in initial["sites"] + refills["sites"]
    ]
    return {
        "initial_window_events": initial["event_count"],
        "refill_events": refills["event_count"],
        "all_fill_events": initial["event_count"] + refills["event_count"],
        "initial_site_count": initial["site_count"],
        "refill_site_count": refills["site_count"],
        "oracle_site_count": len(oracle_rows),
        "oracle_sha256": sha_bytes(canonical(oracle_rows)),
        "oracle_rule": (
            "owner/cursor selects bound C2D/object payload after the stop; "
            "submit-return and refill metadata are never expected-byte authority"
        ),
        "exposure_observation": (
            "13,803 refills make a timing-dependent visibility failure coherent "
            "under this load; they do not prove target membership"
        ),
    }


def extract_plan(truth: ElfTruth, name: str) -> list[int]:
    data = list(symbol_bytes(truth, name))
    require(data and data[-1] == 0 and all(value != 0 for value in data[:-1]),
            f"append plan terminator/slot drift: {name}")
    return data


def source_partition(truth: ElfTruth) -> dict[str, Any]:
    source = {name: git_blob(name).decode("utf-8") for name in SOURCES}
    vm = source["src/vm.c"]
    runtime = source["src/c2_product_runtime.c"]
    emitter = source["src/c2_session_emitter.c"]
    phase = source["src/c2_phase_scratch.h"]
    mem = source["src/mem.c"]
    profile = PROFILE.read_text(encoding="utf-8")

    r_edges = [
        {
            "id": "R-OBJ-SETUP",
            "edge": "initial object/header+payload fill before first dispatch",
            "source_anchor": "OBJ_SETUP",
            "witness": "dispatcher-side completed-fill view",
        },
        {
            "id": "R-CALLER-RELOAD",
            "edge": "BUF_ENSURE_MINE caller header/literal reload after nested call",
            "source_anchor": "BUF_ENSURE_MINE",
            "witness": "dispatcher-side completed-fill view",
        },
        {
            "id": "R-WINDOW-REFILL",
            "edge": "WIN_ENSURE sequential/branch/post-return payload refill",
            "source_anchor": "WIN_ENSURE",
            "witness": "dispatcher-side cursor/owner/window/opcode view",
        },
    ]
    require(
        all(token in vm for token in (
            "#define OBJ_SETUP()", "#define BUF_ENSURE_MINE(pcur_)",
            "#define WIN_ENSURE()", "if (!vm_object_load(", "op = RD8();",
        ))
        and vm.index("WIN_ENSURE();") < vm.index("op = RD8();"),
        "VM fill/dispatcher edge contract drift",
    )

    stage_plan = extract_plan(truth, "lisp65_c2_append_stage_plan")
    publish_plan = extract_plan(
        truth, "lisp65_c2_append_persistent_publish_plan"
    )
    rollback_plan = extract_plan(truth, "lisp65_c2_append_rollback_plan")
    require(
        stage_plan == [30, 39, 33, 34, 35, 36, 0]
        and publish_plan == [37, 38, 39, 40, 0]
        and rollback_plan == [39, 41, 42, 43, 44, 45, 40, 39, 0],
        "Link-82 append plan bytes drift",
    )
    emitter_slots = [
        ("prepare", 15), ("name", 16), ("literal-prep", 17),
        ("literal-atom", 18), ("literal-append", 19), ("code", 20),
        ("final-meta", 21), ("final-crc", 22),
    ]
    a_edges = [
        {"id": "A-OWNER-ACQUIRE", "checkpoint": "phase-owner acquire/release"},
        *[
            {"id": f"A-EMIT-{slot:02d}", "checkpoint": name, "slot": slot}
            for name, slot in emitter_slots
        ],
        *[
            {"id": f"A-STAGE-{index}", "checkpoint": "stage-plan", "slot": slot}
            for index, slot in enumerate(stage_plan[:-1])
        ],
        *[
            {"id": f"A-PUBLISH-{index}", "checkpoint": "publish-plan", "slot": slot}
            for index, slot in enumerate(publish_plan[:-1])
        ],
        *[
            {"id": f"A-ROLLBACK-{index}", "checkpoint": "rollback-plan", "slot": slot}
            for index, slot in enumerate(rollback_plan[:-1])
        ],
        {"id": "A-C2J-PREPARED", "checkpoint": "C2J PREPARED fence", "C2J": 2},
        {"id": "A-C2J-ACTIVE", "checkpoint": "C2J ACTIVE publication", "C2J": 1},
        {"id": "A-C2J-CLEAR", "checkpoint": "C2J CLEAR cleanup", "C2J": 0},
    ]
    require(
        "C2J_RESULT_NONE 0u" in runtime
        and "C2J_RESULT_ACTIVE 1u" in runtime
        and "C2J_RESULT_PREPARED 2u" in runtime
        and "c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_APPEND)" in runtime
        and "c2_phase_scratch_acquire(LISP65_C2_PHASE_OWNER_EMITTER)" in emitter
        and "LISP65_C2_INSTALL_LAST_SLOT_OFFSET" in phase,
        "append/C2J/first-error edge contract drift",
    )

    expected_executed_ops = {
        "PUSHI8", "ADD", "PUSHARG0", "PUSHARG1", "PUSHARG2", "SUB",
        "MUL", "DIV", "MOD", "LESS", "GREATER", "LOGXOR", "JMPREL",
        "JFALSEREL", "EQ", "NOT", "PUSHNIL", "PUSHT", "RET", "CONS",
        "CAR", "CDR", "CONSP", "EQL", "PUSHARGN", "LOADL", "STOREL",
        "DROP", "PUSHLIT", "CALL", "CALLPRIM", "TAILCALL",
    }
    observed_ops: set[str] = set()
    observed_instructions = 0
    original_instruction = PHASE_A_DRIVER.WindowTrace.instruction

    def capture_instruction(
        instance: Any, name: str, code: Any, pc: int, spec: Any, operand: Any
    ) -> None:
        nonlocal observed_instructions
        observed_instructions += 1
        observed_ops.add(str(spec.mnemonic))
        original_instruction(instance, name, code, pc, spec, operand)

    PHASE_A_DRIVER.WindowTrace.instruction = capture_instruction
    try:
        replay = PHASE_A_DRIVER.sequence("windowed")
    finally:
        PHASE_A_DRIVER.WindowTrace.instruction = original_instruction
    require(
        observed_instructions == 199573
        and observed_ops == expected_executed_ops
        and replay["constructor"]["result"] == "(point 3 4)",
        "dynamic Phase-A opcode/replay coverage drift",
    )
    g_edges = [
        {"id": "G-BADOPCODE", "status": 2,
         "causes": ["bad fetch/opcode", "bad relative target", "stack underflow",
                    "directory/header/load failure"]},
        {"id": "G-ARITY", "status": 8,
         "causes": ["object arity guard", "primitive arity guard"]},
        {"id": "G-STACKOVER", "status": 4,
         "causes": ["frame guard", "operand/root push guard"]},
        {"id": "G-TYPEERROR", "status": 3,
         "causes": ["typed VM opcode", "typed primitive", "emitter control argument"]},
        {"id": "G-HEAPOOM", "status": 5,
         "causes": ["CONS allocation", "string/buffer/compiler allocation after GC"]},
        {"id": "G-DIRMISS", "status": 6,
         "causes": ["CALL/TAILCALL directory miss"]},
        {"id": "G-NOTDESIGNATOR", "status": 9,
         "causes": ["apply/funcall primitive designator"]},
        {"id": "G-GC-OOM", "status": 5,
         "causes": ["alloc -> gc_collect -> no freelist / mem_oom"]},
        {"id": "G-COMPILE-STATUS", "status": "tagged-VM-status",
         "causes": ["compile_run_top_form native compile/region/directory edge"]},
        {"id": "G-LISP-ABORT", "status": "tagged-error-code",
         "causes": ["vm_check_status -> lisp_abort outside an active append"]},
    ]
    require(
        all(f"OP_{name}" in vm for name in observed_ops)
        and "VM_OK=0, VM_HALT, VM_BADOPCODE, VM_TYPEERROR, VM_STACKOVER, VM_HEAPOOM," in source["src/vm.h"]
        and "VM_DIRMISS, VM_STEPLIMIT, VM_ARITY, VM_NOTDESIGNATOR" in source["src/vm.h"]
        and "void gc_collect(void)" in mem
        and "if (freelist == NIL) return alloc_oom();" in mem
        and "mem_oom = 1;" in mem
        and "-DVM_STEP_LIMIT" not in profile,
        "measured VM/GC reachable-edge contract drift",
    )

    irq = source["src/c2_kernal_window.s"]
    i_edges = [{
        "id": "I-SOURCELESS-EPISODE-2",
        "edge": "second consecutive source-less IRQ after owned-source mask",
        "required_values": ["D019&0x1f", "D01A", "episode latch", "return PC"],
    }]
    require(
        "and #$01" in irq and "sta C2K_UNOWNED_VIC" in irq
        and "lda C2K_SOURCELESS_IRQS" in irq,
        "source-less IRQ edge contract drift",
    )

    symbol_contract = {}
    for name, expected in {
        "vm_run": (0x4398, 39),
        "vm_run_inner": (0x43BF, 7913),
        "vm_check_status": (0x8EA9, 76),
        "gc_collect": (0x38F7, 1483),
        "c2_append_begin": (0xE7E4, 513),
        "c2_append_run_rollback_plan": (0xE9E5, 29),
        "c2_phase_owner": (0x0089, 1),
        "mem_oom": (0x008F, 1),
        "lisp65_c2_phase_scratch": (0xC0C6, 304),
    }.items():
        symbol = truth.symbol(name)
        require((symbol.value, symbol.bytes) == expected,
                f"Link-82 symbol drift: {name}")
        symbol_contract[name] = {
            "address": f"0x{symbol.value:04x}", "bytes": symbol.bytes,
            "section": symbol.section,
        }

    return {
        "R": r_edges,
        "A": a_edges,
        "I": i_edges,
        "G": g_edges,
        "active_outcome_classes": ["R", "A", "I", "G"],
        "append_plans": {
            "stage": stage_plan,
            "persistent_publish": publish_plan,
            "rollback": rollback_plan,
        },
        "executed_opcode_set": sorted(observed_ops),
        "dynamic_host_trace": {
            "instructions": observed_instructions,
            "constructor": replay["constructor"]["result"],
            "authority": "exact Phase-A Link-82 windowed replay",
        },
        "symbol_contract": symbol_contract,
        "coverage": {
            "refill_paths": 3,
            "append_transaction_edges": len(a_edges),
            "interrupt_edges": len(i_edges),
            "VM_GC_status_families": len(g_edges),
            "reset_is_external_prerequisite": True,
        },
    }


def record_contract() -> dict[str, Any]:
    # Every raw/unconstrained value has its own preceding tag.  Initial tags
    # are non-zero and unique; reached tags are a disjoint non-zero range.
    fields: list[dict[str, Any]] = []
    offset = 0
    initial = 0x51
    reached = 0xA1

    def stage(name: str) -> None:
        nonlocal offset, initial, reached
        fields.append({
            "name": name, "kind": "stage-tag", "offset": offset, "bytes": 1,
            "initial_sentinel": initial, "reached_tag": reached,
        })
        offset += 1
        initial += 1
        reached += 1

    def value(name: str, size: int) -> None:
        nonlocal offset, initial, reached
        fields.append({
            "name": name, "kind": "tagged-value", "tag_offset": offset,
            "value_offset": offset + 1, "value_bytes": size,
            "initial_sentinel": initial, "reached_tag": reached,
        })
        offset += 1 + size
        initial += 1
        reached += 1

    stage("record-armed")
    for view in ("previous-fill", "last-fill"):
        stage(f"{view}.complete")
        value(f"{view}.cursor", 2)
        value(f"{view}.owner", 3)
        value(f"{view}.window-base", 2)
        value(f"{view}.fetched-opcode", 1)
    stage("first-error.complete")
    value("first-error.status-or-code", 1)
    value("first-error.payload-pc", 2)
    value("first-error.opcode", 1)
    value("first-error.owner", 3)
    value("first-error.cpu-pc", 2)
    stage("append.complete")
    value("append.first-non-ok-checkpoint", 1)
    value("append.phase-owner", 1)
    value("append.c2j-state", 1)
    stage("irq.source-less-entry-2")
    value("irq.episode-latch", 1)
    value("irq.d019", 1)
    value("irq.d01a", 1)
    value("irq.interrupted-return-pc", 2)
    stage("gc.complete")
    value("gc.mem-oom", 1)
    value("gc.runs", 2)
    require(offset == 65 and len(fields) == 29, "diagnostic record geometry drift")
    initial_tags = [row["initial_sentinel"] for row in fields]
    reached_tags = [row["reached_tag"] for row in fields]
    require(
        all(value != 0 for value in initial_tags + reached_tags)
        and len(set(initial_tags + reached_tags)) == len(initial_tags + reached_tags)
        and set(initial_tags).isdisjoint(reached_tags),
        "sentinel/tag collision",
    )
    return {
        "section": ".lisp65_v16_defstruct_diagnostic_state",
        "storage": "ordinary RAM chosen by the diagnostic ELF; never ZP/window/overlay",
        "bytes": offset,
        "fields": fields,
        "nonzero_per_stage_sentinels": True,
        "separate_tag_for_every_unconstrained_value": True,
        "last_two_completed_fill_views": True,
        "reset_on_entry": True,
        "write_rule": (
            "raw bytes first, reached tag last; volatile straight-line stores only, "
            "no calls, DMA, checks, branches or product readers"
        ),
    }


def base_state() -> dict[str, Any]:
    return {
        "session_continuity": True,
        "fills": [],
        "append": {
            "reached": False, "failure_checkpoint": None, "phase_owner": 0,
            "c2j": "CLEAR", "non_ok": False,
        },
        "irq": {
            "reached": False, "source_less_entry": 0,
            "episode_latch": 0, "d019": None, "d01a": None,
            "return_pc": None,
        },
        "error": {"reached": False, "status": None, "edge": None},
        "gc": {"reached": False, "mem_oom": 0, "runs": 0},
    }


def classify(state: dict[str, Any]) -> str:
    require(state.get("session_continuity") is True,
            "session/reset prerequisite failed outside R/A/I/G")
    fills = state["fills"]
    require(len(fills) <= 2, "more than two retained fill views")
    for view in fills:
        require(view.get("tagged") is True, "untagged fill view")
        require(view.get("identity_correct") is True,
                "fill identity outside the pre-registered partition")
        require(view.get("oracle") == "bound-C2D-source",
                "refill metadata used as expected-byte oracle")
    mismatches = [row for row in fills if row["fetched"] != row["expected"]]
    append = state["append"]
    dirty_append = bool(
        append["reached"] and (
            append["non_ok"] or append["failure_checkpoint"] is not None
            or append["phase_owner"] != 0 or append["c2j"] != "CLEAR"
        )
    )
    error = state["error"]
    gc_failure = bool(state["gc"]["reached"] and state["gc"]["mem_oom"])
    irq = state["irq"]
    if mismatches:
        return "R"
    if dirty_append:
        return "A"
    if error["reached"] or gc_failure:
        require(error.get("edge") is not None or gc_failure,
                "G state lacks a named VM/GC edge")
        return "G"
    if irq["reached"]:
        require(
            irq["source_less_entry"] == 2
            and irq["episode_latch"] == 1
            and irq["d019"] is not None
            and (irq["d019"] & 0x01) == 0
            and irq["d01a"] == 1
            and irq["return_pc"] is not None,
            "IRQ state does not name the source-less entry",
        )
        return "I"
    return "NO-TERMINAL-EVENT"


def decision_table() -> dict[str, Any]:
    states: dict[str, dict[str, Any]] = {}
    clean = base_state()
    clean["fills"] = [{
        "tagged": True, "identity_correct": True, "fetched": 0x3B,
        "expected": 0x3B, "oracle": "bound-C2D-source",
    }]
    states["success-control"] = clean

    prior_append = deepcopy(clean)
    prior_append["append"] = {
        "reached": True, "failure_checkpoint": None, "phase_owner": 0,
        "c2j": "CLEAR", "non_ok": False,
    }
    states["successful-prior-appends-control"] = prior_append

    r = deepcopy(clean)
    r["fills"][-1]["fetched"] = 0x0B
    r["error"] = {"reached": True, "status": 3, "edge": "G-TYPEERROR"}
    r["irq"] = {
        "reached": True, "source_less_entry": 2,
        "episode_latch": 1, "d019": 0, "d01a": 1,
        "return_pc": 0x43BF,
    }
    states["R-refill-member"] = r

    a = deepcopy(clean)
    a["append"] = {
        "reached": True, "failure_checkpoint": 39, "phase_owner": 2,
        "c2j": "ACTIVE", "non_ok": True,
    }
    a["irq"] = {
        "reached": True, "source_less_entry": 2,
        "episode_latch": 1, "d019": 0, "d01a": 1,
        "return_pc": 0xE9E5,
    }
    states["A-append-transaction"] = a

    i = deepcopy(clean)
    i["irq"] = {
        "reached": True, "source_less_entry": 2,
        "episode_latch": 1, "d019": 0, "d01a": 1,
        "return_pc": 0x43BF,
    }
    states["I-interrupt-entry"] = i

    g = deepcopy(clean)
    g["error"] = {"reached": True, "status": 5, "edge": "G-GC-OOM"}
    g["gc"] = {"reached": True, "mem_oom": 1, "runs": 1}
    g["irq"] = {
        "reached": True, "source_less_entry": 2,
        "episode_latch": 1, "d019": 0, "d01a": 1,
        "return_pc": 0x38F7,
    }
    states["G-other-guarded"] = g

    selected = {name: classify(state) for name, state in states.items()}
    require(
        selected == {
            "success-control": "NO-TERMINAL-EVENT",
            "successful-prior-appends-control": "NO-TERMINAL-EVENT",
            "R-refill-member": "R",
            "A-append-transaction": "A",
            "I-interrupt-entry": "I",
            "G-other-guarded": "G",
        },
        f"R/A/I/G decision table drift: {selected}",
    )
    return {
        "rows": {
            "R": {
                "requires": "tagged correct cursor/owner plus source-byte mismatch",
                "attribution": "F018B content-visibility class",
            },
            "A": {
                "requires": "all fill bytes agree; tagged first non-OK checkpoint, owned phase or non-CLEAR C2J",
                "attribution": "that persistent append/C2J edge",
            },
            "I": {
                "requires": "fills/transaction/error clean; tagged second source-less entry, raw latch=1, D019 raster-clear, D01A=1 and return PC",
                "attribution": "source-less interrupt/guard-input edge",
            },
            "G": {
                "requires": "fills/transaction clean; tagged first-error or GC/OOM edge",
                "attribution": "that exact VM/GC/error edge",
            },
        },
        "synthetic_states": states,
        "selected": selected,
        "terminal_precedence": ["R", "A", "G", "I"],
        "precedence_reason": (
            "the source-less IRQ may be the terminal observer after R/A/G; pure I "
            "is selected only when all underlying planes are clean"
        ),
        "failure_outcomes": ["R", "A", "I", "G"],
        "successful_append_rule": (
            "ordinary completed appends never set first-non-ok-checkpoint; "
            "phase owner NONE plus C2J CLEAR remains a clean control"
        ),
        "fifth_active_failure_outcome": False,
    }


def audit(facts: dict[str, Any]) -> None:
    require(
        facts["identity"] == {
            "promotable": False, "product_delta_bytes": 0,
            "product_links": 0, "diagnostic_ELFs": 0, "hardware_runs": 0,
        },
        "Phase-B no-build/no-product identity boundary drift",
    )
    require(
        facts["graph"]["active_outcome_classes"] == ["R", "A", "I", "G"]
        and facts["guard"]["terminal_observer"]["guard_is_not_blamed"]
        and facts["guard"]["reset_exclusion"]["no_software_edge_from_measured_sequence"]
        and facts["decision"]["fifth_active_failure_outcome"] is False,
        "guard graph is not a complete four-row partition",
    )
    record = facts["record"]
    require(
        record["bytes"] == 65
        and record["nonzero_per_stage_sentinels"]
        and record["separate_tag_for_every_unconstrained_value"]
        and record["last_two_completed_fill_views"]
        and record["reset_on_entry"],
        "diagnostic record contract drift",
    )
    require(
        facts["schedule"]["refill_events"] == 13803
        and facts["schedule"]["all_fill_events"] == 26113
        and facts["graph"]["dynamic_host_trace"]["instructions"] == 199573
        and "never" in facts["schedule"]["oracle_rule"],
        "Phase-A fill/oracle binding drift",
    )


def mutation_check(facts: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[list[Any], Any]] = {
        "blame-guard": (["guard", "terminal_observer", "guard_is_not_blamed"], False),
        "make-promotable": (["identity", "promotable"], True),
        "claim-product-delta": (["identity", "product_delta_bytes"], 1),
        "drop-reset-exclusion": (["guard", "reset_exclusion", "no_software_edge_from_measured_sequence"], False),
        "admit-fifth-outcome": (["decision", "fifth_active_failure_outcome"], True),
        "zero-sentinel": (["record", "fields", 0, "initial_sentinel"], 0),
        "drop-value-tags": (["record", "separate_tag_for_every_unconstrained_value"], False),
        "retain-one-fill": (["record", "last_two_completed_fill_views"], False),
        "drop-record-reset": (["record", "reset_on_entry"], False),
        "flatten-refills": (["schedule", "refill_events"], 0),
        "completion-metadata-oracle": (["schedule", "oracle_rule"], "refill metadata is expected-byte authority"),
        "drop-append-edge": (["graph", "coverage", "append_transaction_edges"], 0),
        "drop-IRQ-edge": (["graph", "coverage", "interrupt_edges"], 0),
        "drop-GC-edge": (["graph", "coverage", "VM_GC_status_families"], 0),
    }
    rejected: dict[str, str] = {}
    for name, (path, value) in cases.items():
        trial = deepcopy(facts)
        target: Any = trial
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value
        try:
            audit(trial)
            require(trial["graph"]["coverage"]["append_transaction_edges"] > 0,
                    "append edge inventory empty")
            require(trial["graph"]["coverage"]["interrupt_edges"] == 1,
                    "IRQ edge inventory empty")
            require(trial["graph"]["coverage"]["VM_GC_status_families"] == 10,
                    "VM/GC edge inventory incomplete")
            tags = [row["initial_sentinel"] for row in trial["record"]["fields"]]
            require(all(tags), "zero sentinel accepted")
        except PhaseBError as error:
            rejected[name] = str(error)
        else:
            raise PhaseBError(f"mutation survived: {name}")

    unclassified = base_state()
    unclassified["fills"] = [{
        "tagged": True, "identity_correct": False, "fetched": 0x0B,
        "expected": 0x3B, "oracle": "bound-C2D-source",
    }]
    try:
        classify(unclassified)
    except PhaseBError as error:
        rejected["unclassified-fill-identity"] = str(error)
    else:
        raise PhaseBError("unclassified stopped state survived")

    reset = base_state()
    reset["session_continuity"] = False
    try:
        classify(reset)
    except PhaseBError as error:
        rejected["reset-as-fifth-outcome"] = str(error)
    else:
        raise PhaseBError("reset was classified as an active product outcome")

    bad_irq_latch = base_state()
    bad_irq_latch["irq"] = {
        "reached": True, "source_less_entry": 2,
        "episode_latch": 2, "d019": 0, "d01a": 1,
        "return_pc": 0x43BF,
    }
    try:
        classify(bad_irq_latch)
    except PhaseBError as error:
        rejected["raw-IRQ-latch-misread-as-entry-count"] = str(error)
    else:
        raise PhaseBError("invalid source-less raw latch survived")

    bad_irq_registers = base_state()
    bad_irq_registers["irq"] = {
        "reached": True, "source_less_entry": 2,
        "episode_latch": 1, "d019": 1, "d01a": 1,
        "return_pc": 0x43BF,
    }
    try:
        classify(bad_irq_registers)
    except PhaseBError as error:
        rejected["owned-raster-misclassified-as-source-less"] = str(error)
    else:
        raise PhaseBError("owned raster IRQ survived source-less classifier")

    successful_append = base_state()
    successful_append["append"] = {
        "reached": True, "failure_checkpoint": None, "phase_owner": 0,
        "c2j": "CLEAR", "non_ok": False,
    }
    require(
        classify(successful_append) == "NO-TERMINAL-EVENT",
        "successful prior append was misclassified as A",
    )
    rejected["successful-append-is-not-a-failure-checkpoint"] = (
        "clean control retained; only the first non-OK checkpoint is recordable"
    )
    require(len(rejected) == 19, "Phase-B mutation count drift")
    return rejected


def build_receipt() -> dict[str, Any]:
    truth, elf = exact_elf()
    irq_device = load(IRQ_DEVICE)
    irq_rows = {row["id"]: row for row in irq_device["product_rows"]}
    require(
        irq_rows["irq-mask-low"]["result"] == "(0 0)"
        and irq_rows["irq-mask-high"]["result"] == "0"
        and irq_rows["irq-mask-low"]["status"] == "passed"
        and irq_rows["irq-mask-high"]["status"] == "passed",
        "delivered three-register IRQ mask readback drift",
    )
    kernal_runtime = git_blob("src/c2_kernal_runtime.c").decode("utf-8")
    require(
        "ETHERNET_IRQ = 0u;" in kernal_runtime
        and "AUTOIEC_IRQ = 0xf0u;" in kernal_runtime
        and "AUDIODMA_IRQ = 0u;" in kernal_runtime
        and "(ETHERNET_IRQ & 0xc0u) != 0u" in kernal_runtime
        and "(AUTOIEC_IRQ & 0x0fu) != 0u" in kernal_runtime
        and "(AUDIODMA_IRQ & 0x0fu) != 0u" in kernal_runtime,
        "exact Link-82 source no longer establishes/readbacks the IRQ masks",
    )
    require(
        "VIC_D01A = 0x01u;" in kernal_runtime,
        "exact Link-82 source no longer arms the owned raster IRQ",
    )
    facts = {
        "identity": {
            "promotable": False, "product_delta_bytes": 0,
            "product_links": 0, "diagnostic_ELFs": 0, "hardware_runs": 0,
        },
        "schedule": phase_a_schedule(),
        "guard": fail_closed_graph(truth),
        "graph": source_partition(truth),
        "record": record_contract(),
        "decision": decision_table(),
        "delivered_interrupt_masks": {
            "programmed_values": {"$D6E1": 0, "$D697": 0xF0, "$D713": 0},
            "enable_field_readback": {
                "$D6E1 & $C0": 0, "$D697 & $0F": 0, "$D713 & $0F": 0,
            },
            "device_readback_authority": (
                "Link-80 hardware masked-enable result (0 0 0)"
            ),
            "Link82_binding": (
                "exact Link-82 source writes 00/F0/00 and verifies the three "
                "enable masks are zero; no byteidentity claim is made against Link 80"
            ),
        },
    }
    audit(facts)
    rejected = mutation_check(facts)
    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "passed-complete-Link82-defstruct-fail-closed-R-A-I-G-partition",
        "facts": facts,
        "verification": {
            "execution_witnesses": 6,
            "failure_rows_selected": 4,
            "mutations_rejected": rejected,
            "mutation_count": len(rejected),
        },
        "artifact_disposition": elf,
        "authority": {
            "Phase_A": bind(PHASE_A),
            "Link82_release_receipt": bind(LINK82),
            "Link82_canonical_manifest": bind(MANIFEST),
            "Link82_WPLTO_map": bind(MAP),
            "Link82_resolved_profile": bind(PROFILE),
            "delivered_IRQ_mask_readback": bind(IRQ_DEVICE),
            "plan": bind(PLAN),
            "gate_wiring": bind(GATES),
            "driver": bind(Path(__file__).resolve()),
            "historical_sources": {name: bind_git(name) for name in SOURCES},
        },
        "claim_limit": (
            "This is a host/source/structured-ELF partition and diagnostic-record "
            "contract for the exact released Link-82 sequence. It proves that every "
            "statically reachable active-sequence failure family is observable as R, "
            "A, I or G and that reset is an external session prerequisite. It does not "
            "build a diagnostic identity, execute hardware, attribute the historical "
            "red frame, prove F018B target membership, change product bytes or authorize "
            "a fix. The 13,803 refills are exposure evidence only."
        ),
        "next_gate": (
            "Phase C may build one byteidentical control and one non-promotable "
            "diagnostic sibling implementing this 65-byte record and decision table."
        ),
    }


def verify_receipt() -> dict[str, Any]:
    value = load(RECEIPT)
    require(value.get("format") == FORMAT, "Phase-B receipt format drift")
    for label, row in value["authority"].items():
        if label == "historical_sources":
            for name, binding in row.items():
                require(bind_git(name) == binding,
                        f"Phase-B historical source drift: {name}")
        else:
            require(bind(ROOT / row["path"]) == row,
                    f"Phase-B authority drift: {label}")
    current = build_receipt()
    require(value == current,
            "Phase-B receipt is not the exact current partition; run action required")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        record = record_contract()
        decision = decision_table()
        require(record["bytes"] == 65 and len(decision["rows"]) == 4,
                "Phase-B selftest drift")
        print("c2-v16-defstruct-phase-b: SELFTEST PASS record=65 rows=4")
        return 0
    if args.action == "run":
        value = build_receipt()
        write_json(RECEIPT, value)
    else:
        value = verify_receipt()
    coverage = value["facts"]["graph"]["coverage"]
    edge_count = sum(coverage[key] for key in (
        "refill_paths", "append_transaction_edges", "interrupt_edges",
        "VM_GC_status_families",
    ))
    print(
        "c2-v16-defstruct-phase-b: PASS "
        f"edges={edge_count} "
        f"record={value['facts']['record']['bytes']} "
        f"refills={value['facts']['schedule']['refill_events']} "
        f"mutations={value['verification']['mutation_count']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PhaseBError, ElfTruthError, OSError, KeyError, ValueError,
            json.JSONDecodeError) as error:
        print(f"c2-v16-defstruct-phase-b: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
