#!/usr/bin/env python3
"""Prepare and capture the v1.6 physical boot progress witness.

This appointment runs no Lisp form.  It samples the fully instrumented Link-82
diagnostic identity at three separated instants and reads only CPU-visible
state: PC, the RAM entry stamp, and the two-byte ``freelist`` head.  The latter
is an independent progress witness for the 4,096-job EXT freelist build.
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
PRG = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/diagnostic-link82.prg"
DELTA = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-physical-delta-desk-attribution-receipt.json")
PREP_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-progress-witness-preparation-receipt.json")
DEVICE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-progress-witness-device-receipt.json")
OUT = ROOT / (
    "build/c2.3/v1.6-defstruct-closing-session/"
    "d2-progress-witness-appointment")
DRIVER = Path(__file__).resolve()

FREELIST = 0x003D
BOOT_WITNESS = 0xC07A
BOOT_RESET = 0x6B
BOOT_STAMP = 0x44
ENTRY_HOOK = 0x202C
ENTRY_HOOK_BYTES = bytes.fromhex("203fc0eaea")
EXT_CELLS = 4096
HOT_CELLS = 48
FIRST_HEAD = ((HOT_CELLS + EXT_CELLS - 1) << 1)
FINAL_HEAD = HOT_CELLS << 1
SAMPLES = 3
SPACING_SECONDS = 2.0


class ProgressError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProgressError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    row: dict[str, Any] = {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha_bytes(path.read_bytes()),
    }
    if address is not None:
        row["address"] = f"0x{address:08x}"
    return row


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def symbol_bytes(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    data = truth.section_bytes(symbol.section)
    offset = symbol.value - section.address
    require(symbol.bytes > 0 and 0 <= offset <= len(data) - symbol.bytes,
            f"sized symbol outside section: {name}")
    return data[offset:offset + symbol.bytes]


def prg_slice(address: int, size: int) -> bytes:
    raw = PRG.read_bytes()
    load_address = int.from_bytes(raw[:2], "little")
    offset = address - load_address + 2
    require(2 <= offset <= len(raw) - size,
            f"PRG slice outside image: 0x{address:04x}")
    return raw[offset:offset + size]


def job_index(head: int) -> int | None:
    """Translate the source-defined descending freelist head to jobs done."""
    if head == 0:
        return 0
    if head & 1 or not FINAL_HEAD <= head <= FIRST_HEAD:
        return None
    return (FIRST_HEAD + 2 - head) // 2


def exact_facts() -> dict[str, Any]:
    plan = PLAN.read_text(encoding="utf-8")
    require("Progress-witness appointment authorized" in plan
            and "one appointment, one row" in plan.lower(),
            "owner progress-witness authority absent")
    deployment = load(DEPLOY)
    delta = load(DELTA)
    require(delta["decision"]["physical_no-prompt_observation"] ==
            "still-real-but-mechanism-unattributed",
            "delta-attribution reopening condition drift")
    require("two time-separated CPU-side" in
            delta["decision"]["required_next_evidence_if_reopened"],
            "time-separated reopening authority absent")
    require(deployment["diagnostic"]["prg"]["sha256"] == sha_bytes(PRG.read_bytes())
            and deployment["entry_witness"]["hook"] == ENTRY_HOOK
            and deployment["entry_witness"]["stamp_address"] == BOOT_WITNESS
            and deployment["entry_witness"]["stamp_initial"] == BOOT_RESET
            and deployment["entry_witness"]["stamp_value"] == BOOT_STAMP,
            "full diagnostic identity or entry witness drift")
    require(prg_slice(ENTRY_HOOK, len(ENTRY_HOOK_BYTES)) == ENTRY_HOOK_BYTES,
            "the authorized diagnostic identity is not the $202C-hook variant")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    freelist = truth.symbol("freelist")
    ext_dma = truth.symbol("ext_dma")
    cell_set_a = truth.symbol("cell_set_a")
    ext_set_a = truth.symbol("ext_set_a")
    eval_init = truth.symbol("eval_init")
    require(freelist.value == FREELIST and freelist.bytes == 2
            and freelist.symbol_type == "Object",
            "ELF freelist identity drift")
    require((ext_dma.value, ext_dma.bytes) == (0x3287, 68)
            and (cell_set_a.value, cell_set_a.bytes) == (0x3521, 79)
            and (ext_set_a.value, ext_set_a.bytes) == (0x3570, 55)
            and (eval_init.value, eval_init.bytes) == (0xC3FD, 1117),
            "ELF early-boot interval drift")
    eval_bytes = symbol_bytes(truth, "eval_init")
    at = lambda address, size: eval_bytes[
        address - eval_init.value:address - eval_init.value + size]
    require(at(0xC433, 4) == bytes.fromhex("643d643e"),
            "freelist reset instruction drift")
    require(at(0xC483, 3) == bytes.fromhex("202135"),
            "cell_set_a loop call drift")
    require(at(0xC48A, 6) == bytes.fromhex("863da61a863e"),
            "freelist progress-store instruction drift")

    return {
        "identity": {
            "diagnostic_PRG": bind(PRG),
            "diagnostic_ELF": bind(ELF),
            "entry_hook": f"0x{ENTRY_HOOK:04x}",
            "entry_hook_bytes": ENTRY_HOOK_BYTES.hex(),
            "boot_witness": f"0x{BOOT_WITNESS:04x}",
            "boot_reset": f"0x{BOOT_RESET:02x}",
            "boot_stamp": f"0x{BOOT_STAMP:02x}",
        },
        "progress_oracle": {
            "symbol": "freelist",
            "address": f"0x{FREELIST:04x}",
            "bytes": 2,
            "source_semantics": (
                "after each completed EXT cell write, freelist=(i<<1) while "
                "i descends from MAX_CELLS-1 to HEAP_CELLS"),
            "first_nonzero_head": f"0x{FIRST_HEAD:04x}",
            "final_head": f"0x{FINAL_HEAD:04x}",
            "derived_job_index": (
                "head==0 ? 0 : (0x2060-head)/2; range 0..4096"),
            "jobs": EXT_CELLS,
            "independent_of_DMA_submit_metadata": True,
            "store_after_cell_set_a": "0xc48a: STX freelist; 0xc48e: STX freelist+1",
        },
        "early_boot_intervals": [
            {"symbol": row.name, "start": f"0x{row.value:04x}",
             "end_exclusive": f"0x{row.value + row.bytes:04x}"}
            for row in (ext_dma, cell_set_a, ext_set_a)
        ] + [{"symbol": "eval_init/freelist-loop",
              "start": "0xc45c", "end_exclusive": "0xc4bd"}],
        "appointment": {
            "samples": SAMPLES,
            "spacing_seconds": SPACING_SECONDS,
            "physical_RUN": True,
            "CPU_side_reads": ["PC", "$C07A", "$003D..$003E"],
            "measured_forms": 0,
            "R_A_I_G_claimed": False,
            "leave_CPU_stopped_after_final_sample": True,
        },
        "decision_table": {
            "identical_early_boot_samples": "STALLED-IN-FREELIST-BUILD",
            "increasing_job_indices": "SLOW-EARLY-BOOT-PROGRESS",
            "boot_stamp_and_later_stable_PC": "POST-ENTRY-HANG-SITE",
            "other": "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM",
        },
    }


def audit(facts: dict[str, Any]) -> None:
    identity = facts["identity"]
    oracle = facts["progress_oracle"]
    appointment = facts["appointment"]
    table = facts["decision_table"]
    require(identity["entry_hook"] == "0x202c"
            and identity["entry_hook_bytes"] == "203fc0eaea"
            and identity["boot_witness"] == "0xc07a",
            "hook-armed diagnostic identity claim drift")
    require(oracle["address"] == "0x003d" and oracle["bytes"] == 2
            and oracle["jobs"] == 4096
            and oracle["first_nonzero_head"] == "0x205e"
            and oracle["final_head"] == "0x0060"
            and oracle["derived_job_index"] ==
            "head==0 ? 0 : (0x2060-head)/2; range 0..4096"
            and oracle["store_after_cell_set_a"] ==
            "0xc48a: STX freelist; 0xc48e: STX freelist+1"
            and oracle["independent_of_DMA_submit_metadata"],
            "freelist oracle claim drift")
    require(job_index(0) == 0 and job_index(FIRST_HEAD) == 1
            and job_index(FINAL_HEAD) == 4096
            and job_index(FINAL_HEAD - 2) is None,
            "freelist progress transform drift")
    require(appointment == {
        "samples": 3,
        "spacing_seconds": 2.0,
        "physical_RUN": True,
        "CPU_side_reads": ["PC", "$C07A", "$003D..$003E"],
        "measured_forms": 0,
        "R_A_I_G_claimed": False,
        "leave_CPU_stopped_after_final_sample": True,
    }, "appointment boundary drift")
    require(table == {
        "identical_early_boot_samples": "STALLED-IN-FREELIST-BUILD",
        "increasing_job_indices": "SLOW-EARLY-BOOT-PROGRESS",
        "boot_stamp_and_later_stable_PC": "POST-ENTRY-HANG-SITE",
        "other": "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM",
    }, "pre-bound decision table drift")


def expected_preparation() -> dict[str, Any]:
    facts = exact_facts()
    audit(facts)
    return {
        "format": "lisp65-c2.3-v1.6-defstruct-D2-progress-witness-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "HOST-GREEN; ONE PHYSICAL PROGRESS ROW AUTHORIZED",
        "authorities": {
            "owner_commission": bind(PLAN),
            "phase_C_deployment": bind(DEPLOY),
            "delta_attribution": bind(DELTA),
            "driver": bind(DRIVER),
        },
        "facts": facts,
        "execution_witnesses": [
            "structured ELF names two-byte freelist at $003D",
            "linked eval_init clears freelist before the EXT loop",
            "linked loop stores freelist only after cell_set_a returns",
            "source-defined head transform maps first/final writes to jobs 1/4096",
            "full diagnostic PRG contains the $202C RAM-entry hook",
            "appointment runs zero measured Lisp forms",
        ],
        "rejected_mutations": [
            "freelist-address", "freelist-width", "head-direction",
            "one-sample-PC", "unspaced-samples", "hook-free-identity",
            "measured-form", "R-A-I-G-overclaim", "metadata-as-oracle",
            "decision-table",
        ],
        "claim_limit": (
            "One physical RUN and one read-only progress row for the fully "
            "proved non-promotable Link-82 diagnostic identity. No require, "
            "defstruct, product fix, link, release or R/A/I/G result."),
    }


def selftest() -> dict[str, Any]:
    base = exact_facts()
    cases = {
        "freelist-address": (["progress_oracle", "address"], "0x003e"),
        "freelist-width": (["progress_oracle", "bytes"], 1),
        "head-direction": (
            ["progress_oracle", "derived_job_index"],
            "head==0 ? 0 : (head-0x0060)/2; range 0..4096"),
        "one-sample-PC": (["appointment", "samples"], 1),
        "unspaced-samples": (["appointment", "spacing_seconds"], 0.0),
        "hook-free-identity": (["identity", "entry_hook_bytes"], "a2448e30d0"),
        "measured-form": (["appointment", "measured_forms"], 1),
        "R-A-I-G-overclaim": (["appointment", "R_A_I_G_claimed"], True),
        "metadata-as-oracle": (
            ["progress_oracle", "independent_of_DMA_submit_metadata"], False),
        "decision-table": (
            ["decision_table", "identical_early_boot_samples"], "HEALTHY"),
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
        except ProgressError:
            rejected.append(name)
        else:
            raise ProgressError(f"progress-witness mutation survived: {name}")
    require(len(rejected) == 10, "progress-witness mutation count drift")
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


def in_interval(pc: int, row: dict[str, str]) -> bool:
    return int(row["start"], 16) <= pc < int(row["end_exclusive"], 16)


def classify(samples: list[dict[str, Any]], facts: dict[str, Any]) -> str:
    pcs = [int(row["PC"], 16) for row in samples]
    jobs = [row["freelist_jobs_completed"] for row in samples]
    early = [any(in_interval(pc, interval)
                 for interval in facts["early_boot_intervals"])
             for pc in pcs]
    stamps = [int(row["boot_witness"], 16) for row in samples]
    if all(early) and len(set(pcs)) == 1 and len(set(jobs)) == 1:
        return "STALLED-IN-FREELIST-BUILD"
    if all(job is not None for job in jobs) \
            and all(left <= right for left, right in zip(jobs, jobs[1:])) \
            and any(left < right for left, right in zip(jobs, jobs[1:])):
        return "SLOW-EARLY-BOOT-PROGRESS"
    if all(stamp == BOOT_STAMP for stamp in stamps) \
            and len(set(pcs)) == 1 and not any(early):
        return "POST-ENTRY-HANG-SITE"
    return "FIRST-RED-UNCLASSIFIED-NO-OVERCLAIM"


def capture(device: str) -> dict[str, Any]:
    require(PREP_RECEIPT.is_file(), "preparation receipt absent")
    prep = load(PREP_RECEIPT)
    expected = expected_preparation()
    require(prep == expected, "preparation receipt drift")
    require(not DEVICE_RECEIPT.exists(), "progress appointment is one-shot")
    OUT.mkdir(parents=True, exist_ok=True)
    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    samples: list[dict[str, Any]] = []
    try:
        SERIAL.configure_serial(fd)
        for index in range(SAMPLES):
            SERIAL.monitor_sync(fd, f"#c2v16progress{index}\r".encode())
            command(fd, b"t1", 0.05)
            registers = read_registers(fd)
            boot, boot_raw = read_block(fd, BOOT_WITNESS, 1)
            head_raw, freelist_raw = read_block(fd, FREELIST, 2)
            head = int.from_bytes(head_raw, "little")
            sample = {
                "sample": index + 1,
                "captured_at_utc": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "PC": registers["PC"],
                "registers": registers,
                "boot_witness": f"0x{boot[0]:02x}",
                "freelist_head": f"0x{head:04x}",
                "freelist_jobs_completed": job_index(head),
                "raw": {"boot": boot_raw, "freelist": freelist_raw},
            }
            samples.append(sample)
            if index + 1 < SAMPLES:
                command(fd, b"t0", 0.03)
                time.sleep(SPACING_SECONDS)
        # The final sample remains stopped so review cannot race a live state.
    finally:
        os.close(fd)

    result = classify(samples, prep["facts"])
    receipt = {
        "format": "lisp65-c2.3-v1.6-defstruct-D2-progress-witness-device-v1",
        "recorded_on": date.today().isoformat(),
        "status": result,
        "device": device,
        "authorities": {
            "preparation": bind(PREP_RECEIPT),
            "driver": bind(DRIVER),
        },
        "samples": samples,
        "result": {
            "classification": result,
            "CPU_left_stopped": True,
            "measured_forms_run": 0,
            "R_A_I_G_claimed": False,
        },
        "claim_limit": prep["claim_limit"],
    }
    write(DEVICE_RECEIPT, receipt)
    print(json.dumps(receipt, sort_keys=True))
    if result.startswith("FIRST-RED"):
        raise ProgressError("spaced readings did not match a pre-bound row")
    return receipt


def prepare() -> dict[str, Any]:
    value = expected_preparation()
    write(PREP_RECEIPT, value)
    return value


def check() -> dict[str, Any]:
    expected = expected_preparation()
    require(PREP_RECEIPT.is_file() and load(PREP_RECEIPT) == expected,
            "progress-witness preparation receipt drift")
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
        value = selftest()
    else:
        capture(args.device)
        return 0
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProgressError, ElfTruthError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-v1.6-boot-progress: FIRST RED: " + str(error), file=sys.stderr)
        raise SystemExit(2)
