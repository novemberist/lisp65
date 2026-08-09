#!/usr/bin/env python3
"""Prepare and capture the durable v1.6 boot-progress appointment.

The diagnostic is derived from the already proved Link-82 sibling by changing
only the two address bytes of its entry-stamp store: $C07A becomes the owned
$B5C3 slot.  The appointment runs no Lisp form.  It samples PC, the durable
entry byte, freelist, the monotonic ``gc_runs`` generation and volatile GC
context at three separated instants, leaving the CPU stopped after the last.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402
import c2_defstruct_link71_slot39_failure_hold as SERIAL  # noqa: E402


READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
PLAN = ROOT / "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
DEPLOY = ROOT / "build/c2.3/v1.6-defstruct-phase-c/deployment.json"
ELF = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/diagnostic-link82.elf"
BASE_PRG = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/diagnostic-link82.prg"
DURABLE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-boot-order-durable-witness-receipt.json")
OUT = ROOT / (
    "build/c2.3/v1.6-defstruct-closing-session/"
    "d2-durable-progress-appointment")
PATCHED_PRG = OUT / "diagnostic-link82-durable-b5c3.prg"
SENTINEL = OUT / "durable-witness-reset.bin"
PREP_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-durable-progress-preparation-receipt.json")
DEVICE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-durable-progress-device-receipt.json")
DRIVER = Path(__file__).resolve()
RUNNER = ROOT / "scripts/c2-v16-defstruct-durable-progress-hw.sh"

ENTRY_HOOK = 0x202C
ENTRY_HOOK_BYTES = bytes.fromhex("203fc0eaea")
ENTRY_ROUTINE = 0xC03F
BASE_ROUTINE = bytes.fromhex("a2448e30d08e7ac060")
PATCHED_ROUTINE = bytes.fromhex("a2448e30d08ec3b560")
WITNESS = 0xB5C3
RESET = 0xD7
STAMP = 0x44
FREELIST = 0x003D
GC_RUNS = 0xB9F0
GC_CONTEXT = 0x0016
GC_CONTEXT_BYTES = 10
SAMPLES = 3
SPACING_SECONDS = 5.0


class DurableProgressError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise DurableProgressError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw), "sha256": sha_bytes(raw),
    }


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def prg_offset(raw: bytes, address: int) -> int:
    require(len(raw) >= 2, "PRG has no load address")
    offset = 2 + address - int.from_bytes(raw[:2], "little")
    require(2 <= offset < len(raw), f"PRG address absent: 0x{address:04x}")
    return offset


def prg_slice(raw: bytes, address: int, size: int) -> bytes:
    offset = prg_offset(raw, address)
    require(offset + size <= len(raw), f"PRG slice absent: 0x{address:04x}")
    return raw[offset:offset + size]


def symbol_bytes(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    data = truth.section_bytes(symbol.section)
    offset = symbol.value - section.address
    require(symbol.bytes > 0 and 0 <= offset <= len(data) - symbol.bytes,
            f"sized symbol outside section: {name}")
    return data[offset:offset + symbol.bytes]


def derived_prg() -> tuple[bytes, list[dict[str, Any]]]:
    base = BASE_PRG.read_bytes()
    require(prg_slice(base, ENTRY_HOOK, len(ENTRY_HOOK_BYTES)) == ENTRY_HOOK_BYTES,
            "base diagnostic is not the proved $202C hook identity")
    require(prg_slice(base, ENTRY_ROUTINE, len(BASE_ROUTINE)) == BASE_ROUTINE,
            "base entry routine drift")
    require(prg_slice(base, WITNESS, 1) == b"\x00",
            "owned witness byte is not zero in the base image")
    value = bytearray(base)
    at = prg_offset(base, ENTRY_ROUTINE)
    value[at:at + len(PATCHED_ROUTINE)] = PATCHED_ROUTINE
    rows = []
    for index, (old, new) in enumerate(zip(base, value)):
        if old != new:
            address = int.from_bytes(base[:2], "little") + index - 2
            rows.append({"address": f"0x{address:04x}",
                         "before": f"0x{old:02x}", "after": f"0x{new:02x}"})
    require(rows == [
        {"address": "0xc045", "before": "0x7a", "after": "0xc3"},
        {"address": "0xc046", "before": "0xc0", "after": "0xb5"},
    ], f"durable identity diff drift: {rows}")
    return bytes(value), rows


def materialize() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    value, _ = derived_prg()
    PATCHED_PRG.write_bytes(value)
    SENTINEL.write_bytes(bytes([RESET]))


def exact_facts() -> dict[str, Any]:
    plan = PLAN.read_text(encoding="utf-8")
    require("Contact authorized — 2026-08-05" in plan
            and "Physical RUN of the hook-armed diagnostic" in plan
            and "CPU stays stopped after the final read" in plan,
            "durable progress contact authority absent")
    durable = load(DURABLE)
    require(durable["facts"]["durable_witness"]["address"] == "0xb5c3"
            and durable["facts"]["durable_witness"]["prelaunch_reset"] == "0xd7"
            and durable["facts"]["durable_witness"]["entry_stamp"] == "0x44"
            and durable["facts"]["durable_witness"]
            ["active_owner_ranges_rejected"] == 30,
            "durable witness authority drift")
    deployment = load(DEPLOY)
    require(deployment["promotable"] is False
            and deployment["diagnostic"]["prg"]["sha256"] ==
            sha_bytes(BASE_PRG.read_bytes()),
            "base non-promotable identity drift")
    patched, changes = derived_prg()
    require(PATCHED_PRG.is_file() and PATCHED_PRG.read_bytes() == patched,
            "durable diagnostic identity absent or drifted")
    require(SENTINEL.is_file() and SENTINEL.read_bytes() == bytes([RESET]),
            "durable reset sentinel absent or drifted")
    runner = RUNNER.read_text(encoding="utf-8")
    load_at = runner.index('run_m65 -H "$PRODUCT"')
    preload_at = runner.index("jq -c '.diagnostic.preloads[]'", load_at)
    reset_at = runner.index(
        'run_m65 -H -@ "$SENTINEL@0x0000b5c3"', preload_at)
    reset_read_at = runner.index(
        'readback 0x0000b5c3 1 "$OUT/witness-before-resume.bin"', reset_at)
    resume_at = runner.index('run_m65 -r', reset_read_at)
    ready_at = runner.index('screen launch-ready', resume_at)
    final_read_at = runner.index(
        'readback 0x0000b5c3 1 "$OUT/witness-before-run.bin"', ready_at)
    final_resume_at = runner.index('run_m65 -r', final_read_at)
    require(load_at < preload_at < reset_at < reset_read_at < resume_at
            < ready_at < final_read_at < final_resume_at,
            "prelaunch durable-witness choreography drift")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    freelist = truth.symbol("freelist")
    gc_runs = truth.symbol("gc_runs")
    gc_collect = truth.symbol("gc_collect")
    root_scan = truth.symbol("c2_product_gc_mark_roots")
    require((freelist.value, freelist.bytes, freelist.symbol_type) ==
            (FREELIST, 2, "Object"), "freelist ELF identity drift")
    require((gc_runs.value, gc_runs.bytes, gc_runs.symbol_type) ==
            (GC_RUNS, 2, "Object"), "gc_runs ELF identity drift")
    require((gc_collect.value, gc_collect.bytes) == (0x38F7, 1483)
            and (root_scan.value, root_scan.bytes) == (0xE0BA, 547),
            "collection interval drift")
    collect_bytes = symbol_bytes(truth, "gc_collect")
    require(collect_bytes[0x43:0x4B] == bytes.fromhex("eef0b9d003eef1b9"),
            "gc_runs is not incremented monotonically at gc_collect entry")

    return {
        "identity": {
            "base_PRG": bind(BASE_PRG), "durable_PRG": bind(PATCHED_PRG),
            "ELF": bind(ELF), "changes": changes,
            "promotable": False, "product_bytes_changed": 0,
            "diagnostic_bytes_changed": 2,
            "entry_hook": "0x202c", "entry_routine": "0xc03f",
            "entry_routine_bytes": PATCHED_ROUTINE.hex(),
        },
        "witness": {
            "address": "0xb5c3", "bytes": 1,
            "prelaunch_reset": "0xd7", "entry_stamp": "0x44",
            "reset_file": bind(SENTINEL),
            "prelaunch_CPU_readback_required": True,
            "owner_collision_mutations": 30,
        },
        "progress": {
            "freelist": {"address": "0x003d", "bytes": 2},
            "collection_generation": {
                "symbol": "gc_runs", "address": "0xb9f0", "bytes": 2,
                "semantics": "monotonic increment at each gc_collect entry",
            },
            "auxiliary_GC_context": {
                "address": "0x0016", "bytes": GC_CONTEXT_BYTES,
                "claim": "context only; never a standalone monotonic oracle",
            },
            "intervals": [
                {"name": "gc_collect", "start": "0x38f7",
                 "end_exclusive": "0x3ec2"},
                {"name": "c2_product_gc_mark_roots", "start": "0xe0ba",
                 "end_exclusive": "0xe2dd"},
            ],
        },
        "appointment": {
            "physical_RUN": True, "samples": SAMPLES,
            "spacing_seconds": SPACING_SECONDS,
            "CPU_side_reads": ["PC", "$B5C3", "$003D..$003E",
                               "$B9F0..$B9F1", "$0016..$001F"],
            "measured_forms": 0, "R_A_I_G_claimed": False,
            "leave_CPU_stopped_after_final_sample": True,
        },
        "choreography": {
            "diagnostic_loaded_before_preloads": True,
            "sentinel_written_after_all_loads": True,
            "sentinel_read_back_before_physical_RUN": True,
            "runner": bind(RUNNER),
        },
        "decision_table": {
            "reset_durable_slot_after_entry":
                "BOOT-ENTRY-IDENTITY-OR-VIEW-FIRST-RED",
            "stable_single_collection_state": "STALLED-IN-SINGLE-COLLECTION",
            "increasing_gc_runs_with_zero_freelist":
                "ALLOCATION-GC-REENTRY-LOOP",
            "changing_collection_state": "TEMPORALLY-OBSERVED-PROGRESS",
            "stable_post_entry_non_GC_state": "POST-ENTRY-HANG-SITE",
            "other": "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM",
        },
    }


def audit(facts: dict[str, Any]) -> None:
    identity = facts["identity"]
    witness = facts["witness"]
    progress = facts["progress"]
    appointment = facts["appointment"]
    table = facts["decision_table"]
    choreography = facts["choreography"]
    require(identity["promotable"] is False
            and identity["product_bytes_changed"] == 0
            and identity["diagnostic_bytes_changed"] == 2
            and identity["entry_routine_bytes"] == PATCHED_ROUTINE.hex()
            and len(identity["changes"]) == 2,
            "diagnostic identity boundary drift")
    require(witness["address"] == "0xb5c3"
            and witness["prelaunch_reset"] == "0xd7"
            and witness["entry_stamp"] == "0x44"
            and witness["prelaunch_CPU_readback_required"]
            and witness["owner_collision_mutations"] == 30,
            "durable witness drift")
    require(progress["collection_generation"] == {
        "symbol": "gc_runs", "address": "0xb9f0", "bytes": 2,
        "semantics": "monotonic increment at each gc_collect entry",
    } and progress["auxiliary_GC_context"]["claim"] ==
            "context only; never a standalone monotonic oracle",
            "collection progress oracle drift")
    require(appointment == {
        "physical_RUN": True, "samples": 3, "spacing_seconds": 5.0,
        "CPU_side_reads": ["PC", "$B5C3", "$003D..$003E",
                           "$B9F0..$B9F1", "$0016..$001F"],
        "measured_forms": 0, "R_A_I_G_claimed": False,
        "leave_CPU_stopped_after_final_sample": True,
    }, "appointment boundary drift")
    require(choreography["diagnostic_loaded_before_preloads"]
            and choreography["sentinel_written_after_all_loads"]
            and choreography["sentinel_read_back_before_physical_RUN"],
            "prelaunch choreography claim drift")
    require(table["reset_durable_slot_after_entry"] ==
            "BOOT-ENTRY-IDENTITY-OR-VIEW-FIRST-RED"
            and table["other"] == "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM",
            "decision table drift")


def expected_preparation() -> dict[str, Any]:
    facts = exact_facts()
    audit(facts)
    return {
        "format": "lisp65-c2.3-v1.6-defstruct-D2-durable-progress-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "HOST-GREEN; ONE DURABLE-WITNESS CONTACT AUTHORIZED",
        "authorities": {
            "owner_commission": bind(PLAN), "durable_witness": bind(DURABLE),
            "phase_C_deployment": bind(DEPLOY), "driver": bind(DRIVER),
            "hardware_runner": bind(RUNNER),
        },
        "facts": facts,
        "execution_witnesses": [
            "the derived identity differs only at $C045/$C046",
            "the changed operand redirects STX from $C07A to owned $B5C3",
            "the prelaunch sentinel is read back before physical RUN",
            "ELF binds gc_runs as a two-byte monotonic collection generation",
            "the linked entry sequence increments gc_runs with 16-bit carry",
            "volatile $16..$1F is auxiliary context, never the sole oracle",
            "all table rows run zero measured Lisp forms",
        ],
        "rejected_mutations": [
            "third-diagnostic-byte", "old-C07A-target", "promotable",
            "product-byte-claim", "witness-address", "sentinel-zero",
            "stamp-equals-reset", "skip-prelaunch-readback", "gc-runs-address",
            "gc-context-as-oracle", "measured-form", "resume-after-final-read",
            "drop-fourth-row", "skip-prelaunch-order",
        ],
        "claim_limit": (
            "One physical RUN and one read-only durable progress row for the "
            "non-promotable Link-82 diagnostic sibling. No require, defstruct, "
            "R/A/I/G result, product defect, fix, link or release is claimed."),
    }


def selftest() -> dict[str, Any]:
    base = exact_facts()
    cases: dict[str, tuple[list[str], Any]] = {
        "third-diagnostic-byte": (["identity", "diagnostic_bytes_changed"], 3),
        "old-C07A-target": (["identity", "entry_routine_bytes"], BASE_ROUTINE.hex()),
        "promotable": (["identity", "promotable"], True),
        "product-byte-claim": (["identity", "product_bytes_changed"], 1),
        "witness-address": (["witness", "address"], "0xc07a"),
        "sentinel-zero": (["witness", "prelaunch_reset"], "0x00"),
        "stamp-equals-reset": (["witness", "entry_stamp"], "0xd7"),
        "skip-prelaunch-readback":
            (["witness", "prelaunch_CPU_readback_required"], False),
        "gc-runs-address":
            (["progress", "collection_generation", "address"], "0xb9f1"),
        "gc-context-as-oracle":
            (["progress", "auxiliary_GC_context", "claim"], "monotonic oracle"),
        "measured-form": (["appointment", "measured_forms"], 1),
        "resume-after-final-read":
            (["appointment", "leave_CPU_stopped_after_final_sample"], False),
        "drop-fourth-row":
            (["decision_table", "reset_durable_slot_after_entry"], "HANG"),
        "skip-prelaunch-order":
            (["choreography", "sentinel_written_after_all_loads"], False),
    }
    rejected = []
    for name, (path, replacement) in cases.items():
        trial = deepcopy(base)
        cursor: Any = trial
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except DurableProgressError:
            rejected.append(name)
        else:
            raise DurableProgressError(f"mutation survived: {name}")
    require(len(rejected) == len(cases), "mutation count drift")
    return {"status": "SELFTEST PASS", "mutations": len(rejected)}


def command(fd: int, value: bytes, wait: float = 0.04) -> bytes:
    SERIAL.slow_write(fd, value + b"\r")
    time.sleep(wait)
    return SERIAL.serial_read(fd, 0.4)


def read_registers(fd: int) -> dict[str, Any]:
    import re
    raw = command(fd, b"r", 0.05)
    match = re.search(
        rb"(?:^|\n)([0-9A-Fa-f]{4})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{2})"
        rb"\s+([0-9A-Fa-f]{2})\s+([0-9A-Fa-f]{4})", raw)
    require(match is not None, f"monitor register row absent: {raw!r}")
    names = ("PC", "A", "X", "Y", "Z", "B", "SP")
    widths = (4, 2, 2, 2, 2, 2, 4)
    return {name: f"0x{int(match.group(index), 16):0{width}x}"
            for index, (name, width) in enumerate(zip(names, widths), 1)}


def read_block(fd: int, address: int, size: int) -> tuple[bytes, str]:
    import re
    raw = command(fd, f"m{address:08x}".encode())
    match = re.search(fr":{address:08X}:([0-9A-Fa-f]{{32}})".encode(), raw)
    require(match is not None,
            f"monitor memory row absent at 0x{address:08x}: {raw!r}")
    return bytes.fromhex(match.group(1).decode())[:size], raw.hex()


def in_gc(pc: int, facts: dict[str, Any]) -> bool:
    return any(int(row["start"], 16) <= pc < int(row["end_exclusive"], 16)
               for row in facts["progress"]["intervals"])


def classify(samples: list[dict[str, Any]], facts: dict[str, Any]) -> str:
    stamps = [int(row["durable_witness"], 16) for row in samples]
    if any(value != STAMP for value in stamps):
        return "BOOT-ENTRY-IDENTITY-OR-VIEW-FIRST-RED"
    pcs = [int(row["PC"], 16) for row in samples]
    runs = [row["gc_runs"] for row in samples]
    heads = [int(row["freelist_head"], 16) for row in samples]
    contexts = [row["GC_context"] for row in samples]
    all_gc = all(in_gc(pc, facts) for pc in pcs)
    if (all_gc and all(left <= right for left, right in zip(runs, runs[1:]))
            and any(left < right for left, right in zip(runs, runs[1:]))
            and all(head == 0 for head in heads)):
        return "ALLOCATION-GC-REENTRY-LOOP"
    if all_gc and len(set(pcs)) == len(set(runs)) == len(set(heads)) == 1 \
            and len(set(contexts)) == 1:
        return "STALLED-IN-SINGLE-COLLECTION"
    if len(set(pcs)) == len(set(runs)) == len(set(heads)) == 1 \
            and len(set(contexts)) == 1:
        return "POST-ENTRY-HANG-SITE"
    if (len(set(pcs)) > 1 or len(set(runs)) > 1 or len(set(heads)) > 1
            or len(set(contexts)) > 1):
        return "TEMPORALLY-OBSERVED-PROGRESS"
    return "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM"


def capture(device: str) -> dict[str, Any]:
    expected = expected_preparation()
    require(PREP_RECEIPT.is_file() and load(PREP_RECEIPT) == expected,
            "preparation receipt drift")
    require(not DEVICE_RECEIPT.exists(), "durable progress contact is one-shot")
    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    samples: list[dict[str, Any]] = []
    try:
        SERIAL.configure_serial(fd)
        for index in range(SAMPLES):
            SERIAL.monitor_sync(fd, f"#c2v16durable{index}\r".encode())
            command(fd, b"t1", 0.05)
            registers = read_registers(fd)
            witness, witness_raw = read_block(fd, WITNESS, 1)
            freelist, freelist_raw = read_block(fd, FREELIST, 2)
            gc_runs, gc_runs_raw = read_block(fd, GC_RUNS, 2)
            context, context_raw = read_block(fd, GC_CONTEXT, GC_CONTEXT_BYTES)
            samples.append({
                "sample": index + 1,
                "captured_at_utc": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "PC": registers["PC"], "registers": registers,
                "durable_witness": f"0x{witness[0]:02x}",
                "freelist_head": f"0x{int.from_bytes(freelist, 'little'):04x}",
                "gc_runs": int.from_bytes(gc_runs, "little"),
                "GC_context": context.hex(),
                "raw": {"witness": witness_raw, "freelist": freelist_raw,
                        "gc_runs": gc_runs_raw, "GC_context": context_raw},
            })
            if index + 1 < SAMPLES:
                command(fd, b"t0", 0.03)
                time.sleep(SPACING_SECONDS)
        # Deliberately leave the final sample stopped for owner review.
    finally:
        os.close(fd)

    result = classify(samples, expected["facts"])
    receipt = {
        "format": "lisp65-c2.3-v1.6-defstruct-D2-durable-progress-device-v1",
        "recorded_on": date.today().isoformat(), "status": result,
        "device": device,
        "authorities": {"preparation": bind(PREP_RECEIPT),
                        "driver": bind(DRIVER)},
        "samples": samples,
        "result": {"classification": result, "CPU_left_stopped": True,
                   "measured_forms_run": 0, "R_A_I_G_claimed": False},
        "claim_limit": expected["claim_limit"],
    }
    write_json(DEVICE_RECEIPT, receipt)
    print(json.dumps(receipt, sort_keys=True))
    if result.startswith("FIRST-RED") or result.startswith("BOOT-ENTRY"):
        raise DurableProgressError(f"contact selected fail-closed row: {result}")
    return receipt


def prepare() -> dict[str, Any]:
    materialize()
    value = expected_preparation()
    write_json(PREP_RECEIPT, value)
    return value


def check() -> dict[str, Any]:
    materialize()
    expected = expected_preparation()
    require(PREP_RECEIPT.is_file() and load(PREP_RECEIPT) == expected,
            "durable progress preparation receipt drift")
    return {"status": "PASS", "samples": SAMPLES,
            "spacing_seconds": SPACING_SECONDS,
            "device_result_present": DEVICE_RECEIPT.exists()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "check", "selftest", "capture"))
    parser.add_argument("--device", default=SERIAL.DEVICE)
    args = parser.parse_args()
    if args.action == "prepare":
        value = prepare()
    elif args.action == "check":
        value = check()
    elif args.action == "selftest":
        materialize()
        value = selftest()
    else:
        capture(args.device)
        return 0
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DurableProgressError, ElfTruthError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-v1.6-durable-progress: FIRST RED: " + str(error), file=sys.stderr)
        raise SystemExit(2)
