#!/usr/bin/env python3
"""Close the ROMC-repaired D2 launch-failure capture at the desk.

The device packet contains one useful instruction-owner sample, but its
diagnostic-state reads crossed active ROM windows.  This checker binds the
launch handoff that *is* proven and rejects semantic use of the obscured
record, witness and counters.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402

PLAN = ROOT / "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
DEVICE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-romc-repaired-launch-failure-device-receipt.json")
DURABLE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-boot-order-durable-witness-receipt.json")
REPAIR = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-bootstrap-romc-repair-receipt.json")
ELF = ROOT / (
    "build/c2.3/v1.6-defstruct-bootstrap-romc-repair/artifacts/"
    "diagnostic-link82-romc-safe.elf")
CPU = ROOT / "build/upstream-verification/mega65-core/src/vhdl/gs4510.vhdl"
VICIV = ROOT / "build/upstream-verification/mega65-core/src/vhdl/viciv.vhdl"
MACHINE = ROOT / (
    "build/upstream-verification/mega65-core/src/vhdl/machine_container.vhdl")
MONITOR = ROOT / (
    "build/upstream-verification/mega65-core/src/monitor/monitor.a65")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
RESULT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-romc-repaired-launch-failure-desk-closure-receipt.json")
DRIVER = Path(__file__).resolve()


class ClosureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ClosureError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": digest(raw),
    }


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(args: list[str]) -> bytes:
    result = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    require(result.returncode == 0,
            f"command failed ({' '.join(args)}): "
            f"{result.stderr.decode(errors='replace')}")
    return result.stdout


def symbols() -> dict[str, int]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    return {name: truth.symbol(name).value for name in (
        "gc_collect", "gc_runs", "lisp65_c2_phase_scratch")}


def capture_bytes(device: dict[str, Any], name: str) -> bytes:
    row = device["CPU_view_captures"][name]
    path = ROOT / row["path"]
    raw = path.read_bytes()
    require(len(raw) == row["bytes"] and digest(raw) == row["sha256"],
            f"capture binding drift: {name}")
    return raw


def decode_flags(tail: str) -> dict[str, bool]:
    token = tail.split()[-1]
    require(len(token) == 8, f"ROM/port field width drift: {token!r}")
    return {f"{index}:{label}": token[index] != "."
            for index, label in enumerate("reca8lhc")}


def exact_facts() -> dict[str, Any]:
    plan = PLAN.read_text(encoding="utf-8")
    require("ROMC-repaired launch-failure desk closure — 2026-08-05" in plan,
            "desk closure absent from plan")
    device = load(DEVICE)
    durable = load(DURABLE)
    repair = load(REPAIR)
    require(device["status"] ==
            "LAUNCH FAILED BEFORE VISIBLE PROMPT; STOPPED CAPTURE BOUND"
            and device["summary"]["CPU_left_stopped"]
            and device["summary"]["measured_forms"] == 0
            and device["summary"]["R_A_I_G"] is None,
            "device launch-failure boundary drift")
    require(repair["status"] ==
            "HOST-GREEN DIAGNOSTIC-ONLY ROMC BOOTSTRAP REPAIR",
            "ROMC repair authority drift")

    pc = int(device["PC"], 16)
    owner = device["code_owner"]
    require(pc == 0x3B0D and owner["unique"]
            and owner["selected_owner"] == "ROMC-repaired-diagnostic-PRG"
            and owner["observed"] == "8406a44486048405a4068516a518c505",
            "stopped PC/code-owner binding drift")
    names = symbols()
    require(names["gc_collect"] == 0x38F7
            and names["gc_runs"] == 0xB9F0
            and names["lisp65_c2_phase_scratch"] == 0xC0C6,
            "diagnostic ELF symbol drift")
    disassembly = run([
        str(OBJDUMP), "-d", "--start-address=0x3b0b",
        "--stop-address=0x3b13", str(ELF)]).decode()
    require(re.search(r"3b0d:\s+84 06\s+sty\s+\$6", disassembly),
            "stopped instruction drift")

    mapping = device["mapping"]
    require(mapping["MAPH"] == "0x8000" and mapping["MAPL"] == "0x0000",
            "stopped MAP state drift")
    flags = decode_flags(mapping["raw_tail"])
    require(flags["2:c"] and flags["5:l"] and flags["6:h"] and flags["7:c"],
            "captured ROMC/LORAM/HIRAM state drift")
    maph = int(mapping["MAPH"], 16)
    high_enables = (maph >> 12) & 0xF
    require(high_enables == 0x8
            and not (high_enables & (1 << ((0xB5C3 >> 13) & 3)))
            and not (high_enables & (1 << ((0xC03F >> 13) & 3))),
            "MAPH no longer leaves B000/C000 to ROM resolution")

    cpu_text = CPU.read_text(encoding="utf-8")
    viciv_text = VICIV.read_text(encoding="utf-8")
    machine_text = MACHINE.read_text(encoding="utf-8")
    monitor_text = MONITOR.read_text(encoding="utf-8")
    require('.byte       "reca8lhc"' in monitor_text
            and "monitor_roms(5) <= rom_at_c000;" in machine_text
            and "monitor_roms(2 downto 0) <= monitor_cpuport;" in machine_text,
            "monitor ROM/CPU-port display authority drift")
    require("if (blocknum=11) and (lhc(0)='1') and (lhc(1)='1') then"
            in cpu_text
            and 'temp_address(27 downto 12) := x"002B";' in cpu_text,
            "B000 BASIC-ROM read mapping drift")
    require("if (blocknum=12) and (rom_at_c000='1') then" in cpu_text
            and 'temp_address(27 downto 12) := x"002C";' in cpu_text
            and "$D030.5 VIC-III:ROMC Map C65 ROM @ $C000" in viciv_text,
            "C000 ROMC read mapping drift")

    witness = capture_bytes(device, "boot-witness")
    record = capture_bytes(device, "record")
    phase = capture_bytes(device, "phase-scratch")
    first_error = capture_bytes(device, "first-error")
    phase_owner = capture_bytes(device, "phase-owner")
    gc_runs = capture_bytes(device, "gc-runs")
    require(witness == b"\x22" and record == b"\xff" * 65
            and phase == b"\xff" * 304 and first_error == b"\xff\xff"
            and phase_owner == b"\x00" and gc_runs == b"\x03\x4c",
            "raw stopped-state packet drift")
    require(durable["facts"]["durable_witness"]["address"] == "0xb5c3"
            and durable["facts"]["durable_witness"]["entry_stamp"] == "0x44",
            "historical witness contract drift")

    return {
        "launch": {
            "visible_prompt": False,
            "product_handover_proven": True,
            "PC": "0x3b0d",
            "instruction_owner": "ROMC-repaired-diagnostic-PRG",
            "symbol": "gc_collect",
            "symbol_start": "0x38f7",
            "symbol_offset": "0x0216",
            "instruction": "STY $06",
            "single_PC_semantics": "snapshot-only; no hang, loop or progress claim",
        },
        "stopped_view": {
            "MAPH": "0x8000",
            "MAPL": "0x0000",
            "ROM_port_field": mapping["raw_tail"].split()[-1],
            "ROMC": True,
            "LORAM": True,
            "HIRAM": True,
            "CPU_port_bits_2_1_0": "111",
            "B000_reads": "C64 BASIC ROM at physical $002Bxxxx",
            "C000_reads": "C65 ROMC at physical $002Cxxxx",
            "PC_read": "ordinary low RAM; unique diagnostic owner",
        },
        "capture_classification": {
            "boot_witness_0x22": "BASIC-ROM byte, not $B5C3 RAM",
            "gc_runs_raw_0x4c03": "BASIC-ROM bytes, not gc_runs",
            "record_all_ff": "ROMC bytes, not the diagnostic record",
            "phase_all_ff": "ROMC bytes, not phase scratch",
            "first_error_ffff": "ROMC bytes, not first-error state",
            "phase_owner_00": "visible low-RAM byte but no form was armed or run",
            "durable_witness_lifetime": "not evaluated by this capture",
            "record_armed": "not observable through the captured C000 CPU view",
        },
        "decision": {
            "measured_forms": 0,
            "R_A_I_G_result": None,
            "product_hang_claim": False,
            "GC_loop_claim": False,
            "slow_progress_claim": False,
            "boot_witness_overwrite_claim": False,
            "new_contact_authorized": False,
            "device_action_authorized": False,
            "CPU_left_stopped": True,
            "next_desk_question": (
                "design a stopped-state observation whose record/witness slots "
                "remain visible in the executing CPU world, or prove a separate "
                "under-ROM read authority, before any new contact question"),
        },
    }


def audit(facts: dict[str, Any]) -> None:
    launch = facts["launch"]
    view = facts["stopped_view"]
    captures = facts["capture_classification"]
    decision = facts["decision"]
    require(not launch["visible_prompt"] and launch["product_handover_proven"]
            and launch["PC"] == "0x3b0d"
            and launch["instruction_owner"] ==
            "ROMC-repaired-diagnostic-PRG"
            and launch["symbol"] == "gc_collect"
            and launch["single_PC_semantics"] ==
            "snapshot-only; no hang, loop or progress claim",
            "launch claim drift")
    require(view["ROMC"] and view["LORAM"] and view["HIRAM"]
            and view["B000_reads"] ==
            "C64 BASIC ROM at physical $002Bxxxx"
            and view["C000_reads"] ==
            "C65 ROMC at physical $002Cxxxx",
            "stopped-view classification drift")
    require(captures["durable_witness_lifetime"] ==
            "not evaluated by this capture"
            and captures["record_armed"] ==
            "not observable through the captured C000 CPU view"
            and "not gc_runs" in captures["gc_runs_raw_0x4c03"]
            and "not first-error" in captures["first_error_ffff"],
            "obscured-state claim drift")
    require(decision["measured_forms"] == 0
            and decision["R_A_I_G_result"] is None
            and not decision["product_hang_claim"]
            and not decision["GC_loop_claim"]
            and not decision["slow_progress_claim"]
            and not decision["boot_witness_overwrite_claim"]
            and not decision["new_contact_authorized"]
            and not decision["device_action_authorized"]
            and decision["CPU_left_stopped"],
            "decision/claim boundary drift")


def expected() -> dict[str, Any]:
    facts = exact_facts()
    audit(facts)
    return {
        "format": "lisp65-c2.3-v1.6-romc-launch-failure-desk-closure-v1",
        "recorded_on": date.today().isoformat(),
        "status": "PRODUCT HANDOVER PROVEN; DIAGNOSTIC STATE HIDDEN BY ROM WINDOWS",
        "authorities": {
            "plan": bind(PLAN),
            "device": bind(DEVICE),
            "durable_witness_contract": bind(DURABLE),
            "ROMC_repair": bind(REPAIR),
            "diagnostic_ELF": bind(ELF),
            "CPU_mapping": bind(CPU),
            "VIC_registers": bind(VICIV),
            "monitor_ROM_fields": bind(MONITOR),
            "monitor_ROM_wiring": bind(MACHINE),
            "driver": bind(DRIVER),
        },
        "facts": facts,
        "execution_witnesses": [
            "the stopped $3B0D bytes uniquely match the diagnostic product image",
            "$3B0D resolves to gc_collect+$216 / STY $06 in the bound ELF",
            "MAPH=$8000 leaves the B000 and C000 blocks to ROM resolution",
            "active LORAM+HIRAM map B000 reads to BASIC ROM",
            "active ROMC maps C000 reads to C65 ROM",
            "raw witness/counter/record bytes match the obscured-view packet",
            "no measured form ran and the CPU remains stopped",
        ],
        "mutations_rejected": [
            "claim-no-product-handover", "claim-product-hang",
            "claim-GC-loop", "claim-slow-progress", "claim-gc-runs-19459",
            "claim-first-error-ffff", "claim-record-reset",
            "claim-witness-overwrite", "claim-R-A-I-G", "claim-new-contact",
            "claim-device-action", "claim-CPU-resumed", "drop-ROMC",
            "drop-BASIC-ROM", "drop-code-owner",
        ],
        "claim_limit": (
            "Desk closure of the consumed launch-failure capture only. Product "
            "handover is proven; liveness and obscured diagnostic state are not. "
            "No product hang, GC behavior, witness lifetime, first-error, R/A/I/G "
            "result, new contact, reset or resume is claimed."),
    }


def mutate(base: dict[str, Any], path: list[str], value: Any) -> dict[str, Any]:
    trial = deepcopy(base)
    cursor: Any = trial
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
    return trial


def selftest() -> dict[str, Any]:
    base = exact_facts()
    cases: dict[str, tuple[list[str], Any]] = {
        "claim-no-product-handover":
            (["launch", "product_handover_proven"], False),
        "claim-product-hang": (["decision", "product_hang_claim"], True),
        "claim-GC-loop": (["decision", "GC_loop_claim"], True),
        "claim-slow-progress": (["decision", "slow_progress_claim"], True),
        "claim-gc-runs-19459":
            (["capture_classification", "gc_runs_raw_0x4c03"],
             "gc_runs=19459"),
        "claim-first-error-ffff":
            (["capture_classification", "first_error_ffff"],
             "first-error=ffff"),
        "claim-record-reset":
            (["capture_classification", "record_armed"], False),
        "claim-witness-overwrite":
            (["decision", "boot_witness_overwrite_claim"], True),
        "claim-R-A-I-G": (["decision", "R_A_I_G_result"], "R"),
        "claim-new-contact": (["decision", "new_contact_authorized"], True),
        "claim-device-action":
            (["decision", "device_action_authorized"], True),
        "claim-CPU-resumed": (["decision", "CPU_left_stopped"], False),
        "drop-ROMC": (["stopped_view", "ROMC"], False),
        "drop-BASIC-ROM":
            (["stopped_view", "B000_reads"], "ordinary RAM"),
        "drop-code-owner":
            (["launch", "instruction_owner"], "unbound"),
    }
    rejected: list[str] = []
    for name, (path, value) in cases.items():
        try:
            audit(mutate(base, path, value))
        except ClosureError:
            rejected.append(name)
        else:
            raise ClosureError(f"mutation survived: {name}")
    require(set(rejected) == set(cases), "desk-closure mutation count drift")
    return {"status": "SELFTEST PASS", "mutations": len(rejected)}


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        value = selftest()
    else:
        value = expected()
        if args.action == "write":
            RESULT.write_bytes(canonical(value))
        else:
            require(RESULT.is_file() and RESULT.read_bytes() == canonical(value),
                    "ROMC launch-failure desk closure receipt drift")
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ClosureError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-v1.6-romc-launch-failure-desk-closure: FIRST RED: " + str(error))
        raise SystemExit(2)
