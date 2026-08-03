#!/usr/bin/env python3
"""Run the commissioned hang-triggered Link-83 editor discriminator."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_v126_editor_hardware as EDITOR  # noqa: E402
import c2_v126_editor_stall_device as LEGACY  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


COMMISSION = ROOT / "docs/planning/c2.2-v1.2.6-editor-jtag-method-review.md"
PREDECESSOR = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-stall-observed-device-receipt.json")
DRY_RUN = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-stall-hang-triggered-host-dry-run-receipt.json")
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-stall-hang-triggered-preparation-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-stall-hang-triggered-device-receipt.json")
OUT_ROOT = ROOT / "build/c2.2/v1.2.6-editor-stall-hang-triggered"
EXPECTED_QUEUE_A = 0x41


class RunnerError(RuntimeError):
    pass


class BufferTimeout(RunnerError):
    def __init__(
        self, phase: str, name: str, expected: int, attempts: int,
        errors: list[str], pre_key: dict[str, Any],
    ):
        super().__init__(
            f"{phase}: buffer {name!r} did not reach fill {expected}; "
            f"attempts={attempts} errors={errors[-3:]}")
        self.phase = phase
        self.name = name
        self.expected = expected
        self.attempts = attempts
        self.errors = errors
        self.pre_key = pre_key


def require(value: bool, message: str) -> None:
    if not value:
        raise RunnerError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing JSON authority: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    return LEGACY.bind(path, address)


def write_json(path: Path, value: dict[str, Any]) -> None:
    LEGACY.write_json(path, value)


def classify(pre_gc: int, stalled: dict[str, Any]) -> dict[str, Any]:
    """Apply the registered a/b/c split to the one stopped hang."""
    queue_state = int(stalled["queue_state"])
    queue_code = int(stalled["queue_code"])
    after_gc = int(stalled["gc_runs"])
    pc = int(stalled["registers"]["PC"], 16)
    delta = (after_gc - pre_gc) & 0xFFFF
    if queue_state & 0x80:
        require(
            queue_code == EXPECTED_QUEUE_A,
            f"stalled queue code is 0x{queue_code:02x}, not folded a=0x41")
        outcome = "a-input-irq-key-queued-not-consumed"
    elif delta == 0:
        outcome = "a-input-irq-key-not-observed-before-collection"
    elif LEGACY.GC_FIRST <= pc < LEGACY.GC_LAST_EXCLUSIVE:
        outcome = "b-target-only-gc-hang"
    else:
        outcome = "c-post-gc-or-gc-callee-pc-needs-symbol-reading"
    return {
        "outcome": outcome,
        "queue_present": bool(queue_state & 0x80),
        "queue_code": f"0x{queue_code:02x}",
        "expected_queue_code": "0x41",
        "gc_runs_before": pre_gc,
        "gc_runs_stalled": after_gc,
        "gc_runs_delta": delta,
        "PC": f"0x{pc:04x}",
        "PC_symbol": LEGACY.nearest_symbol(pc),
        "PC_in_gc_collect_body": (
            LEGACY.GC_FIRST <= pc < LEGACY.GC_LAST_EXCLUSIVE),
    }


def wait_buffer(
    session: EDITOR.EditorSession, symbol_index: int, *, phase: str,
    name: str, expected: int, pre_key: dict[str, Any], timeout: int = 120,
) -> dict[str, Any]:
    """Wait only on live buffer memory; never consume rendered status truth."""
    deadline = time.monotonic() + timeout
    attempt = 0
    errors: list[str] = []
    while time.monotonic() < deadline:
        attempt += 1
        try:
            value = LEGACY.capture_buffer_fill(
                session, f"{phase}-{attempt:03d}", symbol_index, name)
            if int(value["fill"]) == expected:
                value["attempt"] = attempt
                return value
            errors.append(f"fill={value['fill']}")
        except Exception as error:
            errors.append(f"{type(error).__name__}: {error}")
        time.sleep(0.25)
    raise BufferTimeout(
        phase, name, expected, attempt, errors, pre_key)


def planned_input() -> dict[str, Any]:
    return {
        "editor_launch": "(edit)",
        "scratch_text": LEGACY.ORIGINAL_SCRATCH_TEXT,
        "scratch_chunk_width": 10,
        "editor_abort": "~C",
        "forms": [
            ["context-helper-legacy", LEGACY.ORIGINAL_HELPER, "%ib"],
            ["context-helper-corrected", LEGACY.CORRECTED_HELPER, "%ib"],
            ["context-scratch-bind", LEGACY.SCRATCH_BIND, "t"],
        ],
        "measurement_launch": '(ide"measure3")',
        "measurement_keys": 56,
        "measurement_character": "a",
    }


def host_dry_run() -> dict[str, Any]:
    source = Path(__file__).read_text(encoding="utf-8")
    run_start = source.index("\ndef run_contact(")
    run_source = source[
        run_start:source.index("\ndef finalize(", run_start)]
    forbidden = [
        "breakpoint_key_witness(", "virtual_matrix_press(",
        "QUEUE_CONSUMER_BREAKPOINT", "BREAK_CONSUMER_BREAKPOINT",
    ]
    require(all(token not in run_source for token in forbidden),
            "retired per-key classifier leaked into hang-triggered runner")
    require(run_source.count("LEGACY.halt_capture()") == 1,
            "runner must have exactly one CPU-halt call site")
    require("wait_buffer(" in run_source,
            "live buffer-memory postcondition absent")
    require("session.abort_editor(" in run_source,
            "RUN/STOP product-postcondition path absent")
    require("visible_line(" not in run_source and "630/752" not in run_source,
            "cached renderer/status truth leaked into runner")

    plan = planned_input()
    require(
        plan["scratch_text"] == "a" * 32 + "bc"
        and plan["measurement_keys"] == 56,
        "historical state/workload transcript drift")
    require(LEGACY.key_code("a") == EXPECTED_QUEUE_A,
            "measured PETSCII fold authority drift")
    cases = [
        (0x80, EXPECTED_QUEUE_A, 7, 7, 0x8299,
         "a-input-irq-key-queued-not-consumed"),
        (0x00, 0x00, 7, 7, 0x8299,
         "a-input-irq-key-not-observed-before-collection"),
        (0x00, 0x00, 7, 8, LEGACY.GC_FIRST,
         "b-target-only-gc-hang"),
        (0x00, 0x00, 7, 8, 0x8299,
         "c-post-gc-or-gc-callee-pc-needs-symbol-reading"),
    ]
    results: list[str] = []
    for state, code, before, after, pc, expected in cases:
        stalled = {
            "queue_state": state, "queue_code": code, "gc_runs": after,
            "registers": {"PC": f"0x{pc:04x}"},
        }
        result = classify(before, stalled)["outcome"]
        require(result == expected, f"a/b/c case drift: {result} != {expected}")
        results.append(result)
    mutation_rejected = False
    try:
        classify(7, {
            "queue_state": 0x80, "queue_code": 0x61, "gc_runs": 7,
            "registers": {"PC": "0x8299"},
        })
    except RunnerError:
        mutation_rejected = True
    require(mutation_rejected, "ASCII-lowercase queue mutation survived")

    commission = COMMISSION.read_text(encoding="utf-8")
    require(
        "Option 1 commissioned" in commission
        and "per-key JTAG classification is retired" in commission
        and "One contact plus one reserve" in commission,
        "Option-1 commission absent")
    predecessor = load(PREDECESSOR)
    require(
        predecessor["status"] == "FIRST-RED-observed-transport-tooling"
        and predecessor["execution_accounting"]["reserve_consumed"] is True,
        "retired method closure absent")
    value = {
        "format": "lisp65-c2.2-v1.2.6-editor-stall-hang-triggered-dry-run-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-option1-hang-triggered-runner",
        "plan": plan,
        "proof": {
            "per_key_breakpoints": 0,
            "CPU_halt_call_sites": 1,
            "context_truth": "live ide-buffers memory",
            "RUN_STOP_truth": "recovered live REPL product postcondition",
            "hang_trigger": "buffer-fill timeout at any typed position",
            "a_b_c_cases": results,
        },
        "mutations": {
            "ASCII-0x61-instead-of-folded-0x41-rejected": mutation_rejected,
            "cached-status-token-absent": "630/752" not in run_source,
            "per-key-breakpoint-call-absent":
                "breakpoint_key_witness(" not in run_source,
        },
        "executions": len(cases) + 5,
        "device_commands": 0,
        "product_bytes_changed": 0,
        "authority": {
            "commission": bind(COMMISSION),
            "predecessor": bind(PREDECESSOR),
            "driver": bind(Path(__file__).resolve()),
            "candidate_deployment": bind(EDITOR.DEPLOYMENT),
        },
    }
    write_json(DRY_RUN, value)
    return value


def prepare() -> dict[str, Any]:
    dry = load(DRY_RUN)
    require(dry["status"] == "passed-option1-hang-triggered-runner",
            "green Option-1 dry-run absent")
    require(dry["device_commands"] == 0 and dry["product_bytes_changed"] == 0,
            "dry-run scope drift")
    previous = load(LEGACY.OBSERVED_PREPARATION)
    require(previous["candidate"]["link"] == 83, "Link-83 candidate drift")
    require(previous["candidate"]["deployment"]["sha256"]
            == LEGACY.sha256(EDITOR.DEPLOYMENT), "deployment authority drift")
    value = {
        "format": "lisp65-c2.2-v1.2.6-editor-stall-hang-triggered-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "prepared-option1-one-contact-plus-one-reserve",
        "candidate": previous["candidate"],
        "addresses": {
            "queue_state": "0x0000d60a",
            "queue_code": "0x0000d619",
            "gc_runs": "0x0000b9f0",
            "gc_collect": "0x38f7..0x3ec1",
        },
        "protocol": {
            "cold_reset_and_asserted_BASIC": True,
            "package_upload_readback": True,
            "normal_input_no_per_key_breakpoints": True,
            "setup_postconditions": "live buffer memory",
            "RUN_STOP_postcondition": "recovered live REPL",
            "one_CPU_halt_only_on_buffer_timeout": True,
            "hang_reads": ["D60A", "D619", "gc_runs", "PC"],
            "contact": 1,
            "reserve": 1,
            "no_further_contact_on_setup_failure_or_nonreproduction": True,
            "product_bytes_changed": 0,
        },
        "authority": {
            "commission": bind(COMMISSION),
            "commission_commit": "299c9fba",
            "driver": bind(Path(__file__).resolve()),
            "host_dry_run": bind(DRY_RUN),
            "predecessor": bind(PREDECESSOR),
            "candidate_deployment": bind(EDITOR.DEPLOYMENT),
        },
    }
    write_json(PREPARATION, value)
    return value


def live_gc(session: EDITOR.EditorSession, prefix: str) -> dict[str, Any]:
    return LEGACY.running_capture(session, prefix)


def run_contact(index: int) -> dict[str, Any]:
    require(index in (1, 2), "contact must be one or reserve two")
    out = OUT_ROOT / f"contact-{index:02d}"
    require(not out.exists(), f"contact output exists: {out}")
    out.mkdir(parents=True)
    preparation = load(PREPARATION)
    require(
        preparation["status"] == "prepared-option1-one-contact-plus-one-reserve"
        and preparation["authority"]["driver"]["sha256"]
        == LEGACY.sha256(Path(__file__).resolve())
        and preparation["authority"]["host_dry_run"]["sha256"]
        == LEGACY.sha256(DRY_RUN),
        "bound Option-1 preparation drift")
    session = EDITOR.EditorSession(load(EDITOR.CONFIG), preparation)
    session.out = out
    plan = planned_input()
    event: dict[str, Any] | None = None
    try:
        session.media_deploy()
        symbol_index, symbol_witness = LEGACY.resolve_ide_buffers_index(
            session, "buffer-authority")

        session.launch_editor("context-scratch-launch", plan["editor_launch"])
        initial_scratch = wait_buffer(
            session, symbol_index, phase="context-scratch-initial",
            name="scratch", expected=0,
            pre_key=live_gc(session, "context-scratch-initial-pre"), timeout=30)
        scratch_pre = live_gc(session, "context-scratch-text-pre")
        session.send_chunks(
            str(plan["scratch_text"]), int(plan["scratch_chunk_width"]))
        scratch = wait_buffer(
            session, symbol_index, phase="context-scratch-text",
            name="scratch", expected=len(str(plan["scratch_text"])),
            pre_key=scratch_pre)

        session.abort_editor("context-scratch-abort")
        scratch_after_abort = wait_buffer(
            session, symbol_index, phase="context-scratch-after-abort",
            name="scratch", expected=len(str(plan["scratch_text"])),
            pre_key=live_gc(session, "context-scratch-abort-post"), timeout=30)

        form_receipts: list[dict[str, Any]] = []
        for phase, form, expected in plan["forms"]:
            screen = session.run_form(str(phase), str(form), str(expected))
            memory = wait_buffer(
                session, symbol_index, phase=f"{phase}-scratch-memory",
                name="scratch", expected=len(str(plan["scratch_text"])),
                pre_key=live_gc(session, f"{phase}-post"), timeout=30)
            form_receipts.append({
                "phase": phase, "form": form, "expected": expected,
                "screen": bind(screen), "scratch_memory": memory,
            })

        session.launch_editor("measure3-launch", plan["measurement_launch"])
        initial_measure3 = wait_buffer(
            session, symbol_index, phase="measure3-initial",
            name="measure3", expected=0,
            pre_key=live_gc(session, "measure3-initial-pre"), timeout=30)

        key_rows: list[dict[str, Any]] = []
        for ordinal in range(1, int(plan["measurement_keys"]) + 1):
            pre_key = live_gc(session, f"measure3-key-{ordinal:02d}-pre")
            session.send_keys(str(plan["measurement_character"]))
            memory = wait_buffer(
                session, symbol_index, phase=f"measure3-key-{ordinal:02d}",
                name="measure3", expected=ordinal, pre_key=pre_key)
            key_rows.append({
                "ordinal": ordinal,
                "pre_gc_runs": pre_key["gc_runs"],
                "memory": memory,
            })

        session.abort_editor("measure3-no-stall-abort")
        after_abort = wait_buffer(
            session, symbol_index, phase="measure3-no-stall-after-abort",
            name="measure3", expected=int(plan["measurement_keys"]),
            pre_key=live_gc(session, "measure3-no-stall-abort-post"), timeout=30)
        value = {
            "contact": index,
            "status": "stall-not-reproduced-under-normal-input",
            "symbol_authority": symbol_witness,
            "initial_scratch": initial_scratch,
            "scratch": scratch,
            "scratch_after_RUN_STOP": scratch_after_abort,
            "forms": form_receipts,
            "initial_measure3": initial_measure3,
            "keys": key_rows,
            "after_RUN_STOP": after_abort,
            "CPU_halts": 0,
            "product_bytes_changed": 0,
        }
    except BufferTimeout as error:
        stopped = LEGACY.halt_capture()
        decision = classify(int(error.pre_key["gc_runs"]), stopped)
        event = {
            "phase": error.phase,
            "buffer": error.name,
            "expected_fill": error.expected,
            "attempts": error.attempts,
            "last_errors": error.errors[-10:],
            "pre_key": error.pre_key,
            "stopped": stopped,
            "decision": decision,
            "CPU_halts": 1,
            "CPU_left_stopped": True,
        }
        write_json(out / "hang-event.json", event)
        value = {
            "contact": index,
            "status": "hang-reproduced-and-classified",
            "event": event,
            "product_bytes_changed": 0,
        }
    except Exception as error:
        value = {
            "contact": index,
            "status": "FIRST-RED-option1-setup-or-tooling",
            "error_type": type(error).__name__,
            "error": str(error),
            "measurement_claimed": False,
            "CPU_halts": 0,
            "product_bytes_changed": 0,
        }
    write_json(out / "contact.json", value)
    return value


def finalize(contact: dict[str, Any]) -> dict[str, Any]:
    value = {
        "format": "lisp65-c2.2-v1.2.6-editor-stall-hang-triggered-device-v1",
        "recorded_on": date.today().isoformat(),
        "status": contact["status"],
        "contact": contact,
        "execution_accounting": {
            "physical_contacts": int(contact["contact"]),
            "reserve_consumed": int(contact["contact"]) == 2,
            "product_links": 0,
            "product_bytes_changed": 0,
        },
        "authority": {
            "commission": bind(COMMISSION),
            "preparation": bind(PREPARATION),
            "host_dry_run": bind(DRY_RUN),
            "driver": bind(Path(__file__).resolve()),
        },
        "next_step": (
            "owner review of measured a/b/c outcome"
            if contact["status"] == "hang-reproduced-and-classified"
            else "Option-2 pre-staged diagnostic-medium commission; no retry"),
    }
    write_json(RECEIPT, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("dry-run", "prepare", "run"))
    parser.add_argument("--contact", type=int, default=1)
    args = parser.parse_args()
    if args.command == "dry-run":
        value = host_dry_run()
        print(
            "c2-v126-editor-stall-hang-triggered: DRY RUN PASS "
            f"executions={value['executions']} mutations={len(value['mutations'])}")
        return 0
    if args.command == "prepare":
        prepare()
        print("c2-v126-editor-stall-hang-triggered: PREPARED contact=1 reserve=1")
        return 0
    contact = run_contact(args.contact)
    finalize(contact)
    print("c2-v126-editor-stall-hang-triggered: " + contact["status"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        RunnerError, LEGACY.DiscriminatorError, EDITOR.SessionError,
        OSError, ValueError, KeyError, json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as error:
        print("c2-v126-editor-stall-hang-triggered: FIRST RED: " + str(error))
        raise SystemExit(2)
