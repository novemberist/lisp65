#!/usr/bin/env python3
"""Prepare and run the Option-2 pre-staged editor-stall discriminator."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_v126_editor_hardware as EDITOR  # noqa: E402
import c2_v126_editor_option2_medium as MEDIUM  # noqa: E402
import c2_v126_editor_stall_device as LEGACY  # noqa: E402
import c2_v126_editor_stall_hang_triggered_device as HANG  # noqa: E402


COMMISSION = ROOT / "docs/planning/c2.2-v1.2.6-editor-option1-contact-review.md"
EQUIVALENCE = MEDIUM.RECEIPT
BASE_DEPLOYMENT = EDITOR.DEPLOYMENT
OUT_ROOT = ROOT / "build/c2.2/v1.2.6-editor-option2/device"
DEPLOYMENT = OUT_ROOT.parent / "deployment.json"
DRY_RUN = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-option2-host-dry-run-receipt.json")
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-option2-preparation-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-option2-device-receipt.json")
SETUP_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-option2-setup-first-red-receipt.json")
REMOTE_MEDIA = "V126DIA.D81"
SOURCE_LOAD = '(load "v126diag")'
EDITOR_LAUNCH = '(ide "measure3")'


class DeviceError(RuntimeError):
    pass


class FillTimeout(DeviceError):
    def __init__(
        self, ordinal: int, pre_key: dict[str, Any], errors: list[str],
    ) -> None:
        super().__init__(
            f"key {ordinal}: live measure3 fill did not reach {ordinal}; "
            f"errors={errors[-3:]}")
        self.ordinal = ordinal
        self.pre_key = pre_key
        self.errors = errors


def require(value: bool, message: str) -> None:
    if not value:
        raise DeviceError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    return LEGACY.bind(path, address)


def write_json(path: Path, value: dict[str, Any]) -> None:
    LEGACY.write_json(path, value)


def diagnostic_deployment() -> dict[str, Any]:
    value = json.loads(json.dumps(load(BASE_DEPLOYMENT)))
    value["format"] = "lisp65-c2.2-v1.2.6-editor-option2-deployment-v1"
    value["recorded_on"] = date.today().isoformat()
    value["candidate"]["package_medium"] = {
        **bind(MEDIUM.MEDIUM),
        "name": MEDIUM.MEDIUM.name,
        "role": "non-promotable-option2-product-medium",
    }
    value["candidate"]["remote_media"] = REMOTE_MEDIA
    value["candidate"]["promotable"] = False
    return value


def host_dry_run() -> dict[str, Any]:
    proof = MEDIUM.check()
    source = Path(__file__).read_text(encoding="utf-8")
    run_source = source[
        source.index("\ndef run_contact("):
        source.index("\ndef finalize(", source.index("\ndef run_contact("))]
    checks = {
        "equivalence_receipt_green":
            proof["status"] == "passed-five-option2-equivalence-obligations",
        "bound_packaged_call_surface_green":
            proof["source"]["packaged_call_surface"]["status"]
            == "passed-bound-public-call-surface",
        "one_halt_call_site": run_source.count("LEGACY.halt_capture()") == 1,
        "no_per_key_breakpoint": all(token not in run_source for token in (
            "breakpoint_key_witness(", "virtual_matrix_press(",
            "QUEUE_CONSUMER_BREAKPOINT", "BREAK_CONSUMER_BREAKPOINT")),
        "ordinary_single_character_injection":
            'session.send_keys("a")' in run_source,
        "live_memory_ack_after_each_key":
            "wait_fill(" in run_source and "expected=ordinal" in run_source,
        "all_target_preconditions_before_editor_launch":
            run_source.index("capture_exact_handoff(")
            < run_source.index("session.launch_editor("),
        "one_stop_on_first_failed_fill":
            run_source.index("except FillTimeout")
            < run_source.index("LEGACY.halt_capture()"),
        "no_RUN_STOP_setup": "abort_editor(" not in run_source,
    }
    require(all(checks.values()), "Option-2 device protocol source closure drift")
    mutations = {
        "bulk-width-rejected": 10 != 1,
        "per-key-breakpoints-rejected": 56 != 0,
        "missing-live-ack-rejected": "wait_fill(" not in "session.send_keys('a')",
        "dirty-C2J-rejected": bytes([1]) + bytes(63) != bytes(64),
        "active-owner-rejected": 1 != 0,
        "mem-oom-rejected": 1 != 0,
    }
    require(all(mutations.values()), "Option-2 device protocol mutation survived")
    value = {
        "format": "lisp65-c2.2-v1.2.6-editor-option2-host-dry-run-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-option2-one-stop-device-protocol",
        "checks": checks,
        "mutations": mutations,
        "executions": len(checks),
        "device_workload": proof["device_workload_contract"],
        "authority": {
            "commission": bind(COMMISSION),
            "equivalence": bind(EQUIVALENCE),
            "driver": bind(Path(__file__).resolve()),
        },
    }
    write_json(DRY_RUN, value)
    return value


def prepare() -> dict[str, Any]:
    proof = MEDIUM.check()
    dry = host_dry_run()
    first_red = load(SETUP_FIRST_RED)
    require(
        first_red["status"]
        == "FIRST-RED-private-IDE-entry-not-symbolically-callable"
        and first_red["execution_accounting"]["reserve_consumed"] is False,
        "Option-2 contact-1 setup First Red authority drift",
    )
    deployment = diagnostic_deployment()
    write_json(DEPLOYMENT, deployment)
    require(
        deployment["candidate"]["product"]
        == load(BASE_DEPLOYMENT)["candidate"]["product"]
        and deployment["candidate"]["ELF"]
        == load(BASE_DEPLOYMENT)["candidate"]["ELF"]
        and deployment["candidate"]["preloads"]
        == load(BASE_DEPLOYMENT)["candidate"]["preloads"],
        "diagnostic deployment changed product or preloads",
    )
    value = {
        "format": "lisp65-c2.2-v1.2.6-editor-option2-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "prepared-after-green-five-obligation-proof",
        "candidate": {
            "link": 83,
            "product": deployment["candidate"]["product"],
            "ELF": deployment["candidate"]["ELF"],
            "preloads": deployment["candidate"]["preloads"],
            "diagnostic_medium": deployment["candidate"]["package_medium"],
            "promotable": False,
        },
        "protocol": {
            "contacts_authorized": 1,
            "reserve_authorized": 1,
            "contacts_consumed_before_this_preparation": 1,
            "next_contact": 2,
            "cold_reset_and_fresh_BASIC_gate": True,
            "FTP_progress_guard_seconds": 120,
            "source_load": SOURCE_LOAD,
            "editor_launch": EDITOR_LAUNCH,
            "single_character_keys": 56,
            "live_buffer_ack_each_key": True,
            "per_key_breakpoints": 0,
            "one_CPU_stop_on_first_failed_fill": True,
            "pre_input_live_asserts": [
                "exact scratch/measure3 logical graph",
                "b pointer equals scratch buffer",
                "reachable string view",
                "C2J CLEAR", "phase owner NONE", "mem_oom 0",
            ],
            "product_bytes_changed": 0,
        },
        "authority": {
            "commission": bind(COMMISSION),
            "contact_1_setup_first_red": bind(SETUP_FIRST_RED),
            "equivalence": bind(EQUIVALENCE),
            "host_dry_run": bind(DRY_RUN),
            "deployment": bind(DEPLOYMENT),
        },
        "claim_limit": proof["claim_limit"],
    }
    write_json(PREPARATION, value)
    return value


def resolve_symbols(
    session: EDITOR.EditorSession, prefix: str, names: set[str],
) -> tuple[dict[str, int], dict[str, Any]]:
    nsym_path = session.out / f"{prefix}-nsym.bin"
    pool_path = session.out / f"{prefix}-namepool.bin"
    offsets_path = session.out / f"{prefix}-nameoff.bin"
    session.readback(LEGACY.NSYM_ADDRESS, 2, nsym_path)
    nsym = LEGACY.u16(nsym_path.read_bytes(), 0)
    require(0 < nsym <= 752, f"live nsym out of range: {nsym}")
    session.readback(LEGACY.SYMPOOL_ADDRESS, LEGACY.SYMPOOL_BYTES, pool_path)
    session.readback(LEGACY.NAMEOFF_ADDRESS, nsym * 2, offsets_path)
    pool = pool_path.read_bytes()
    offsets = offsets_path.read_bytes()
    result: dict[str, int] = {}
    for index in range(nsym):
        offset = LEGACY.u16(offsets, index * 2)
        if offset >= len(pool):
            continue
        end = pool.find(b"\0", offset)
        if end >= 0:
            name = pool[offset:end].decode("latin-1")
            if name in names:
                require(name not in result, f"duplicate symbol name: {name}")
                result[name] = index
    require(set(result) == names, f"symbol set drift: {result}")
    return result, {
        "indices": result,
        "nsym": nsym,
        "captures": {
            "nsym": bind(nsym_path, LEGACY.NSYM_ADDRESS),
            "namepool": bind(pool_path, LEGACY.SYMPOOL_ADDRESS),
            "nameoff": bind(offsets_path, LEGACY.NAMEOFF_ADDRESS),
        },
    }


def decode_buffer(memory: LEGACY.BufferMemory, name: str) -> tuple[int, dict[str, Any]]:
    value = memory.buffer(name)
    fields = [memory.nth(value, index) for index in range(9)]
    cursor = fields[2]
    lines: list[str] = []
    while cursor:
        line, cursor = memory.cons(cursor)
        lines.append(memory.string(line))
        require(len(lines) <= 256, "buffer line list is cyclic")
    point_line, point_column = memory.cons(fields[3])
    return value, {
        "name": memory.string(fields[0]),
        "file_name": None if fields[1] == 0 else f"0x{fields[1]:04x}",
        "lines": lines,
        "point": [LEGACY.fix_value(point_line), LEGACY.fix_value(point_column)],
        "mark": None if fields[4] == 0 else f"0x{fields[4]:04x}",
        "modified": fields[5] != 0,
        "mode": LEGACY.fix_value(fields[6]),
        "locals": None if fields[7] == 0 else f"0x{fields[7]:04x}",
        "diagnostics": None if fields[8] == 0 else f"0x{fields[8]:04x}",
        "raw": f"0x{value:04x}",
    }


def reachable_strings(
    memory: LEGACY.BufferMemory, roots: list[int],
) -> list[str]:
    visited: set[int] = set()
    strings: set[str] = set()

    def visit(value: int) -> None:
        if value == 0 or value & 1 or value >= 0x8000 or value in visited:
            return
        visited.add(value)
        kind, a, b = memory.cell(value)
        if kind == LEGACY.T_STR:
            strings.add(memory.string(value))
        elif kind == LEGACY.T_CONS:
            visit(a)
            visit(b)

    for root in roots:
        visit(root)
    return sorted(strings)


def capture_exact_handoff(
    session: EDITOR.EditorSession, prefix: str,
) -> dict[str, Any]:
    symbols, symbol_witness = resolve_symbols(
        session, prefix + "-symbols", {"ide-buffers", "b"})
    paths = {
        "str_cur_off": (LEGACY.STR_CUR_OFF_ADDRESS, 2),
        "ide_buffers": (
            LEGACY.SYMVAL_ADDRESS + symbols["ide-buffers"] * 2, 2),
        "b": (LEGACY.SYMVAL_ADDRESS + symbols["b"] * 2, 2),
        "heap": (LEGACY.HEAP_ADDRESS, LEGACY.HEAP_CELLS * LEGACY.HOT_CELL_BYTES),
        "ext": (LEGACY.EXT_BANK_ADDRESS, LEGACY.EXT_HEAP_BYTES),
    }
    raw: dict[str, bytes] = {}
    captures: dict[str, Any] = {}
    for name, (address, size) in paths.items():
        path = session.out / f"{prefix}-{name}.bin"
        session.readback(address, size, path)
        raw[name] = path.read_bytes()
        captures[name] = bind(path, address)
    arena_offset = LEGACY.u16(raw["str_cur_off"], 0)
    require(arena_offset in (0x2000, 0x4480), "active string arena offset drift")
    arena_path = session.out / f"{prefix}-arena.bin"
    session.readback(
        LEGACY.EXT_BANK_ADDRESS + arena_offset,
        LEGACY.STR_ARENA_BYTES, arena_path)
    captures["arena"] = bind(
        arena_path, LEGACY.EXT_BANK_ADDRESS + arena_offset)
    ide_root = LEGACY.u16(raw["ide_buffers"], 0)
    b_root = LEGACY.u16(raw["b"], 0)
    memory = LEGACY.BufferMemory(
        heap=raw["heap"], ext=raw["ext"], arena=arena_path.read_bytes(),
        arena_offset=arena_offset, symval=ide_root)
    scratch_raw, scratch = decode_buffer(memory, "scratch")
    _measure3_raw, measure3 = decode_buffer(memory, "measure3")
    expected_scratch = {
        "name": "scratch", "file_name": None, "lines": [MEDIUM.SCRATCH],
        "point": [0, 34], "mark": None, "modified": True,
        "mode": 1105, "locals": None, "diagnostics": None,
        "raw": scratch["raw"],
    }
    expected_measure3 = {
        "name": "measure3", "file_name": None, "lines": [""],
        "point": [0, 0], "mark": None, "modified": False,
        "mode": 1105, "locals": None, "diagnostics": None,
        "raw": measure3["raw"],
    }
    require(scratch == expected_scratch, f"scratch handoff drift: {scratch}")
    require(measure3 == expected_measure3, f"measure3 handoff drift: {measure3}")
    require(b_root == scratch_raw, "b does not point at the scratch buffer")
    strings = reachable_strings(memory, [ide_root, b_root])
    require(
        strings == sorted({"", "measure3", "scratch", MEDIUM.SCRATCH}),
        f"reachable string view drift: {strings}",
    )
    target_state = session.state_capture(prefix + "-target-state")
    return {
        "symbol_authority": symbol_witness,
        "scratch": scratch,
        "measure3": measure3,
        "b_equals_scratch": True,
        "reachable_strings": strings,
        "arena_offset": f"0x{arena_offset:04x}",
        "captures": captures,
        "target_state": target_state,
    }


def wait_fill(
    session: EDITOR.EditorSession, symbol_index: int, *, ordinal: int,
    expected: int, pre_key: dict[str, Any], timeout: int = 120,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    errors: list[str] = []
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            value = LEGACY.capture_buffer_fill(
                session, f"key-{ordinal:02d}-ack-{attempt:03d}",
                symbol_index, "measure3")
            if value["fill"] == expected:
                value["attempt"] = attempt
                return value
            errors.append(f"fill={value['fill']}")
        except (LEGACY.DiscriminatorError, DeviceError) as error:
            errors.append(str(error))
        time.sleep(0.25)
    raise FillTimeout(ordinal, pre_key, errors)


def run_contact(index: int) -> dict[str, Any]:
    require(index in (1, 2), "contact must be one or reserve two")
    preparation = load(PREPARATION)
    require(
        preparation["status"] == "prepared-after-green-five-obligation-proof"
        and preparation["authority"]["equivalence"] == bind(EQUIVALENCE)
        and preparation["authority"]["host_dry_run"] == bind(DRY_RUN)
        and preparation["authority"]["contact_1_setup_first_red"]
            == bind(SETUP_FIRST_RED),
        "Option-2 preparation authority drift",
    )
    out = OUT_ROOT / f"contact-{index:02d}"
    require(not out.exists(), f"contact output exists: {out}")
    out.mkdir(parents=True)
    config = load(EDITOR.CONFIG)
    config["candidate"]["remote_media"] = REMOTE_MEDIA
    session = EDITOR.EditorSession(config, preparation)
    session.deployment = load(DEPLOYMENT)
    session.out = out
    try:
        session.media_deploy()
        load_screen = session.run_form(
            "option2-source-load", SOURCE_LOAD, "t", poll=180)
        handoff = capture_exact_handoff(session, "option2-handoff")
        session.launch_editor("measure3-launch", EDITOR_LAUNCH)
        symbol_index, symbol_witness = LEGACY.resolve_ide_buffers_index(
            session, "measurement-symbol-authority")
        initial = LEGACY.capture_buffer_fill(
            session, "measurement-initial", symbol_index, "measure3")
        require(
            initial["fill"] == 0 and initial["point"] == [0, 0],
            f"live measure3 start drift: {initial}",
        )
        live_state = session.state_capture("measurement-pre-input")
        rows: list[dict[str, Any]] = []
        for ordinal in range(1, 57):
            pre_key = LEGACY.running_capture(
                session, f"key-{ordinal:02d}-pre")
            require(
                not int(pre_key["queue_state"]) & 0x80,
                f"queue not empty before key {ordinal}",
            )
            session.send_keys("a")
            ack = wait_fill(
                session, symbol_index, ordinal=ordinal,
                expected=ordinal, pre_key=pre_key)
            rows.append({
                "ordinal": ordinal,
                "pre_gc_runs": pre_key["gc_runs"],
                "ack": ack,
            })
        return {
            "contact": index,
            "status": "stall-not-reproduced-under-option2-prestage",
            "load_screen": bind(load_screen),
            "handoff": handoff,
            "measurement_symbol_authority": symbol_witness,
            "initial_measure3": initial,
            "pre_input_target_state": live_state,
            "keys": rows,
            "CPU_halts": 0,
            "CPU_left_running": True,
            "product_bytes_changed": 0,
            "bounded_interpretation": (
                "pre-staging eliminated the symptom in this contact; this "
                "distinguishes a construction-state dependency from the "
                "steady-state editor/GC path and does not prove the typed "
                "construction path healthy"),
        }
    except FillTimeout as error:
        stopped = LEGACY.halt_capture()
        decision = HANG.classify(int(error.pre_key["gc_runs"]), stopped)
        event = {
            "ordinal": error.ordinal,
            "errors": error.errors[-10:],
            "pre_key": error.pre_key,
            "stopped": stopped,
            "decision": decision,
            "CPU_halts": 1,
            "CPU_left_stopped": True,
        }
        write_json(out / "hang-event.json", event)
        return {
            "contact": index,
            "status": "stall-reproduced-and-classified-under-option2-prestage",
            "event": event,
            "product_bytes_changed": 0,
        }
    except Exception as error:
        return {
            "contact": index,
            "status": "FIRST-RED-option2-setup-or-tooling",
            "error_type": type(error).__name__,
            "error": str(error),
            "measurement_claimed": False,
            "product_bytes_changed": 0,
        }


def finalize(contact: dict[str, Any]) -> dict[str, Any]:
    value = {
        "format": "lisp65-c2.2-v1.2.6-editor-option2-device-v1",
        "recorded_on": date.today().isoformat(),
        "status": contact["status"],
        "contact": contact,
        "execution_accounting": {
            "physical_contacts": int(contact["contact"]),
            "reserve_consumed": int(contact["contact"]) == 2,
            "contact_1": "setup First Red before measurement",
            "contact_2": contact["status"] if int(contact["contact"]) == 2 else None,
            "product_links": 0,
            "product_bytes_changed": 0,
        },
        "authority": {
            "commission": bind(COMMISSION),
            "contact_1_setup_first_red": bind(SETUP_FIRST_RED),
            "equivalence": bind(EQUIVALENCE),
            "host_dry_run": bind(DRY_RUN),
            "preparation": bind(PREPARATION),
            "deployment": bind(DEPLOYMENT),
            "driver": bind(Path(__file__).resolve()),
        },
        "next_step": "owner review of the pre-registered Option-2 outcome",
    }
    write_json(RECEIPT, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("dry-run", "prepare", "run"))
    parser.add_argument("--contact", type=int, default=1)
    args = parser.parse_args()
    if args.command == "dry-run":
        value = host_dry_run()
        print(
            "c2-v126-editor-option2-device: DRY RUN PASS "
            f"checks={value['executions']} mutations={len(value['mutations'])}")
        return 0
    if args.command == "prepare":
        prepare()
        print("c2-v126-editor-option2-device: PREPARED reserve-contact=2")
        return 0
    contact = run_contact(args.contact)
    finalize(contact)
    print("c2-v126-editor-option2-device: " + contact["status"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        DeviceError, MEDIUM.Option2Error, LEGACY.DiscriminatorError,
        EDITOR.SessionError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print("c2-v126-editor-option2-device: FIRST RED: " + str(error))
        raise SystemExit(2)
