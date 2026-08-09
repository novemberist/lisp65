#!/usr/bin/env python3
"""Correct the v1.6 full-run Slot-39 provenance claim.

The consumed device record stores the install trace's last-slot byte.  It was
named "first-non-ok" by the diagnostic record, but Link 82's rollback plan
re-enters the header phase (Slot 39) before the following phase locks the
trace.  This checker binds that ordering from the linked ELF and the exact
source commit, preserves the useful device facts, and loudly supersedes the
R/A/I/G=A classification without manufacturing a new target claim.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RESULT = EVIDENCE / (
    "c2.3-v1.6-defstruct-ownership-crc-full-run-result-receipt.json")
DEVICE = EVIDENCE / (
    "c2.3-v1.6-defstruct-ownership-crc-full-run-device-receipt.json")
PHASE_A = EVIDENCE / (
    "c2.3-v1.6-defstruct-phase-a-host-reconstruction-receipt.json")
PHASE_B = EVIDENCE / (
    "c2.3-v1.6-defstruct-phase-b-guard-partition-receipt.json")
LINK71 = EVIDENCE / (
    "c2.2-link71-persistent-append-provenance-correction-receipt.json")
OWNER75 = ROOT / "docs/planning/c2.2-link75-defstruct-red-frame-owner-decision.md"
PLAN = ROOT / "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
GATES = ROOT / "mk/gates.mk"
DRIVER = Path(__file__).resolve()
OUT = EVIDENCE / (
    "c2.3-v1.6-defstruct-slot39-provenance-correction-receipt.json")
REBIND = EVIDENCE / (
    "c2.3-v1.6-defstruct-slot39-provenance-correction-rebind-2026-08-06.json")
ELF = ROOT / (
    "build/c2.2/v1.2.5-candidate-product-link82/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
SOURCE_COMMIT = "fe5c98fea63236af3bddca86bf1bb955cf9a6ffe"
FORMAT = "lisp65-c2.3-v1.6-defstruct-slot39-provenance-correction-v1"
RECORDED_ON = "2026-08-06"


class CorrectionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CorrectionError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def git_blob(path: str) -> bytes:
    process = subprocess.run(
        ["git", "show", f"{SOURCE_COMMIT}:{path}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(process.returncode == 0,
            process.stderr.decode(errors="replace") or f"git blob absent: {path}")
    return process.stdout


def bind_git(path: str) -> dict[str, Any]:
    data = git_blob(path)
    return {
        "authority": "git-blob", "commit": SOURCE_COMMIT, "path": path,
        "bytes": len(data), "sha256": sha_bytes(data),
    }


def symbol_bytes(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    at = symbol.value - section.address
    data = truth.section_bytes(section.name)[at:at + symbol.bytes]
    require(len(data) == symbol.bytes, f"symbol data incomplete: {name}")
    return data


def ordered(text: str, tokens: list[str], label: str) -> None:
    cursor = 0
    for token in tokens:
        found = text.find(token, cursor)
        require(found >= 0, f"{label} token/order drift: {token}")
        cursor = found + len(token)


def derive() -> dict[str, Any]:
    result = load(RESULT)
    device = load(DEVICE)
    phase_a = load(PHASE_A)
    phase_b = load(PHASE_B)
    link71 = load(LINK71)

    require(result["status"] == "A-PERSISTENT-APPEND-SLOT39-HEADER-NON-OK",
            "historical result identity drift")
    append = result["decision"]["append"]
    require(append["first_non_ok_checkpoint"] == 39
            and append["target_definition_landed"] is False
            and append["phase_owner_after_cleanup"] == "NONE"
            and append["C2J_after_cleanup"] == "CLEAR",
            "historical append result drift")
    require(result["source_oracle"]["R_excluded"] is True
            and result["source_oracle"]["scope"]
            == "last-two-retained-completed-refills-only",
            "retained refill result drift")

    decoded = device["decoded_record"]
    require(decoded["append.complete"] == {"state": "reached", "tag": "0xb2"}
            and decoded["append.first-non-ok-checkpoint"]["value_le"] == 39
            and decoded["append.phase-owner"]["value_le"] == 0,
            "captured append fields drift")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    require(bind(ELF)["sha256"]
            == "3d9e4c4e7e8d0719223561c66578fb4b24058f32e42483642322a88c4884d8d6",
            "Link-82 ELF identity drift")
    plans = {
        "stage": list(symbol_bytes(truth, "lisp65_c2_append_stage_plan")),
        "publish": list(symbol_bytes(
            truth, "lisp65_c2_append_persistent_publish_plan")),
        "rollback": list(symbol_bytes(truth, "lisp65_c2_append_rollback_plan")),
    }
    require(plans == {
        "stage": [30, 39, 33, 34, 35, 36, 0],
        "publish": [37, 38, 39, 40, 0],
        "rollback": [39, 41, 42, 43, 44, 45, 40, 39, 0],
    }, "linked append-plan bytes drift")

    scratch = truth.symbol("lisp65_c2_phase_scratch")
    require(scratch.value == 0xC0C6 and scratch.bytes == 304,
            "phase-scratch identity drift")
    last_slot = scratch.value + 302
    lock_byte = scratch.value + 303
    require((last_slot, lock_byte) == (0xC1F4, 0xC1F5),
            "trace byte geometry drift")

    header = truth.section_bytes(".lisp65_rt_c2append_header")
    rollback = truth.section_bytes(".lisp65_rt_c2append_rollback_unpublish")
    header_stamp = bytes.fromhex("a2278ef4c1")
    lock = bytes.fromhex("adf5c109808df5c1")
    conditional_41 = bytes.fromhex("aef5c13005a2298ef4c1")
    require(header.find(header_stamp) == 0x3B,
            "Slot-39 unconditional linked stamp drift")
    require(rollback.find(lock) == 0x27
            and rollback.find(conditional_41) == 0x2F,
            "rollback lock/conditional-Slot-41 ordering drift")
    header_symbol = truth.symbol("c2_append_header_phase")
    rollback_symbol = truth.symbol("c2_append_rollback_unpublish_phase")
    require(header_symbol.value == 0xC371 and header_symbol.bytes == 857
            and rollback_symbol.value == 0xC356
            and rollback_symbol.bytes == 596,
            "linked append function identity drift")

    runtime = git_blob("src/c2_product_runtime.c").decode("utf-8")
    trace_header = git_blob("src/c2_phase_scratch.h").decode("utf-8")
    phase_scratch = git_blob("src/c2_phase_scratch.c").decode("utf-8")
    ordered(runtime, [
        "const uint8_t lisp65_c2_append_rollback_plan[] = {",
        "LISP65_C2_APPEND_HEADER_SLOT,",
        "LISP65_C2_APPEND_ROLLBACK_UNPUBLISH_SLOT,",
    ], "rollback plan")
    ordered(runtime, [
        "static C2_KERNAL_RESIDENT uint8_t c2_append_run_rollback_plan",
        "C2AW_COMPLETION_MARK(w) = C2_COMPLETION_ROLLBACK_MARK;",
        "C2_APPEND_PLAN_WALK(lisp65_c2_append_rollback_plan, context)",
    ], "rollback runner")
    ordered(runtime, [
        "C2_APPEND_SECTION(\"header\") uint8_t c2_append_header_phase",
        "C2_INSTALL_TRACE_STAMP_SLOT(LISP65_C2_APPEND_HEADER_SLOT);",
    ], "header stamp")
    ordered(runtime, [
        "c2_append_rollback_unpublish_phase",
        "C2_INSTALL_TRACE_LOCK_PRIMARY();",
        "C2_INSTALL_TRACE_STAMP_SLOT_IF_UNLOCKED(",
    ], "rollback lock")
    ordered(runtime, [
        "if (!c2_overlay_call(LISP65_C2_APPEND_JOURNAL_CLEAR_SLOT, &c2aw)",
        "|| !c2_overlay_call(LISP65_C2_APPEND_HEADER_SLOT, &c2aw)",
        "goto v5_fail;",
    ], "successful append tail")
    require("C2_INSTALL_TRACE_STAMP_SLOT(slot)" in trace_header
            and "[LISP65_C2_INSTALL_LAST_SLOT_OFFSET] = (uint8_t)(slot)" in trace_header,
            "unconditional trace macro drift")
    acquire = phase_scratch.split("uint8_t c2_phase_scratch_acquire", 1)[1]
    acquire = acquire.split("uint8_t c2_phase_scratch_release", 1)[0]
    require("LISP65_C2_INSTALL_LAST_SLOT_OFFSET" not in acquire,
            "acquire unexpectedly resets last-slot provenance")

    # Any forward failure entering rollback first writes 39.  If header
    # succeeds, Slot 41 locks that value; if header fails, 39 is still the last
    # byte.  The original forward slot is therefore unrecoverable either way.
    forward_slots = sorted(set(plans["stage"][:-1] + plans["publish"][:-1]))
    alias_rows = [{
        "forward_last_slot": slot,
        "after_rollback_header": 39,
        "if_header_succeeds_then_lock_preserves": 39,
        "if_header_fails_then_plan_stops_with": 39,
    } for slot in forward_slots]
    require(all(row["if_header_succeeds_then_lock_preserves"] == 39
                and row["if_header_fails_then_plan_stops_with"] == 39
                for row in alias_rows),
            "rollback alias model drift")

    require(link71["status"]
            == "accepted-correction-Slot39-was-rollback-provenance-Slot40-publication-remains-open"
            and "the first locked product failure is Session slot 39"
            in link71["supersession"]["retracted_claims"],
            "Link-71 provenance precedent drift")

    generated = [row for row in phase_a["windowed_sequence"]["forms"]
                 if row["kind"] == "persistent-definition"]
    require(len(generated) == 9 and generated[0]["entry"] == "make-point"
            and generated[0]["append"]["before"]["entry"] == 757
            and generated[0]["append"]["after"]["entry"] == 758,
            "host make-point schedule drift")
    require(result["post_require_state"]["next_C2D_entry_757_raw_hex"] == "00" * 10,
            "target entry-757 absence drift")
    require(phase_b["facts"]["decision"]["successful_append_rule"].startswith(
        "ordinary completed appends never set first-non-ok-checkpoint"),
        "Phase-B first-non-OK premise drift")

    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "FIRST-RED-SLOT39-IS-LAST-SLOT-NOT-FIRST-NON-OK",
        "authorities": {
            "historical_full_run_result": bind(RESULT),
            "device_receipt": bind(DEVICE),
            "phase_A_host_reconstruction": bind(PHASE_A),
            "phase_B_partition": bind(PHASE_B),
            "Link71_provenance_precedent": bind(LINK71),
            "Link75_owner_decision": bind(OWNER75),
            "Link82_ELF": bind(ELF),
            "Link82_sources": {
                path: bind_git(path) for path in (
                    "src/c2_product_runtime.c", "src/c2_product_runtime.h",
                    "src/c2_phase_scratch.c", "src/c2_phase_scratch.h")
            },
            "driver": bind(DRIVER),
            "plan": bind(PLAN),
            "gate_wiring": bind(GATES),
        },
        "linked_provenance": {
            "plans": plans,
            "last_slot_address": "0xc1f4",
            "primary_lock_address": "0xc1f5",
            "header_unconditional_stamp": {
                "slot": 39, "function": "c2_append_header_phase",
                "pc": "0xc391", "bytes_hex": header_stamp.hex(),
            },
            "rollback_lock": {
                "function": "c2_append_rollback_unpublish_phase",
                "lock_pc": "0xc37d", "conditional_slot41_pc": "0xc38a",
                "order": "rollback Slot39 stamps first; Slot41 locks second",
            },
            "forward_slot_aliases": alias_rows,
            "residual_trace_possible": True,
            "reason": (
                "phase-scratch acquire does not reset the last-slot byte; a "
                "prior successful append also ends at header Slot39"),
        },
        "supersession": {
            "historical_receipt_preserved": True,
            "classification": "UNRESOLVED-PRE-ROLLBACK-PROVENANCE",
            "retracted_claims": [
                "R/A/I/G selects A",
                "captured 39 is a first-non-OK checkpoint",
                "the target failed inside c2-append-header",
                "the make-point append was attempted",
            ],
            "retained_claims": [
                "the two retained completed refill views are byte-exact against the independent source oracle",
                "the captured first-error record is unset, mem_oom is zero, and D01A is zero",
                "target C2D entry 757 did not land and C2D stayed at the exact post-require geometry",
                "phase owner is NONE and C2J is CLEAR after cleanup",
                "the host model schedules make-point as the first generated persistent definition",
            ],
        },
        "inner_slot39_attribution": {
            "possible": False,
            "why": (
                "the capture does not prove that forward Slot39 ran or failed; "
                "enumerating its internal predicates cannot identify a target divergence"),
            "historical_R_candidates": {
                "R-1": "excluded only as pure interrupt ownership for this run; not promoted into Slot39",
                "R-2": "require succeeded; does not identify the later pre-rollback edge",
                "R-3": "methodology item, not a product mechanism",
            },
        },
        "next_boundary": {
            "owner_halt_required": True,
            "minimum_new_witness": (
                "a true failure-edge record committed before rollback enters its first Slot39 phase, "
                "or a host-only proof that names the pre-rollback edge without target inference"),
            "device_contact_authorized": False,
            "fix_authorized": False,
            "product_link_authorized": False,
        },
        "accounting": {
            "product_bytes_changed": 0, "product_links": 0,
            "device_recontacts": 0, "measured_forms": 0,
        },
        "claim_limit": (
            "This is an attribution First Red and a loud provenance correction. "
            "It does not select another R/A/I/G row, revive F018B membership, "
            "name a product mechanism, authorize a fix, or authorize hardware."),
    }


def audit(value: dict[str, Any]) -> None:
    require(value == derive(), "Slot-39 provenance correction receipt drift")


def check() -> dict[str, Any]:
    recorded = load(OUT); expected = derive()
    historical = deepcopy(expected)
    for name in ("driver", "plan", "gate_wiring"):
        historical["authorities"][name] = recorded["authorities"][name]
    require(recorded == historical,
            "Slot-39 correction evidence drift outside loud rebind")
    rebind = load(REBIND)
    require(rebind == {
        "format": "lisp65-c2.3-v1.6-slot39-provenance-rebind-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: HISTORICAL CORRECTION UNCHANGED; CLOSURE REBOUND",
        "reason": (
            "The accepted correction commissioned and then prepared the "
            "pre-rollback shadow witness. The historical correction remains "
            "byte-for-byte unchanged; only checker, append-only plan and "
            "gate-wiring bindings are rebound for the shadow closure."),
        "historical_receipt": bind(OUT),
        "from": {name: recorded["authorities"][name]
                 for name in ("driver", "plan", "gate_wiring")},
        "to": {name: expected["authorities"][name]
               for name in ("driver", "plan", "gate_wiring")},
        "authorized_bindings": ["driver", "plan", "gate_wiring"],
        "historical_facts_changed": False,
    }, "Slot-39 correction loud rebind drift")
    return expected


def selftest() -> dict[str, Any]:
    base = derive()
    cases: list[tuple[list[Any], Any]] = [
        (["status"], "A-PERSISTENT-APPEND"),
        (["linked_provenance", "plans", "rollback", 0], 41),
        (["linked_provenance", "last_slot_address"], "0xc1f5"),
        (["linked_provenance", "rollback_lock", "order"], "lock first"),
        (["linked_provenance", "residual_trace_possible"], False),
        (["supersession", "classification"], "A"),
        (["supersession", "retracted_claims", 1], "captured 39 is first non-OK"),
        (["supersession", "retained_claims", 0], "all refills are exact"),
        (["inner_slot39_attribution", "possible"], True),
        (["inner_slot39_attribution", "historical_R_candidates", "R-2"], "mechanism"),
        (["next_boundary", "owner_halt_required"], False),
        (["next_boundary", "device_contact_authorized"], True),
        (["next_boundary", "fix_authorized"], True),
        (["accounting", "product_bytes_changed"], 1),
        (["claim_limit"], "F018B member"),
    ]
    rejected: dict[str, str] = {}
    for index, (path, replacement) in enumerate(cases, 1):
        trial = deepcopy(base)
        cursor: Any = trial
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except CorrectionError as error:
            rejected[f"mutation-{index:02d}"] = str(error)
        else:
            raise CorrectionError(f"correction mutation survived: {path}")
    return {
        "status": "SELFTEST PASS", "mutations": len(rejected),
        "classification": base["supersession"]["classification"],
        "rejected": rejected,
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "prepare":
        require(not REBIND.exists(),
                "historical correction is loudly rebound; prepare is disabled")
        value = derive()
        write_json(OUT, value)
        output = {"status": "PREPARED", "classification":
                  value["supersession"]["classification"]}
    elif args.action == "selftest":
        output = selftest()
    else:
        check()
        output = {"status": "PASS", "classification":
                  "UNRESOLVED-PRE-ROLLBACK-PROVENANCE"}
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CorrectionError, ElfTruthError, OSError, ValueError, KeyError,
            IndexError, json.JSONDecodeError) as error:
        print(f"SLOT39 PROVENANCE CORRECTION FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
