#!/usr/bin/env python3
"""Attribute the corrected v1.6 D2 entry-witness First Red at the desk."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

from elf_truth import ElfTruth, ElfTruthError  # noqa: E402


READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
PLAN = ROOT / "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
DEVICE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-closing-d2-arm-order-device-first-red-receipt.json")
ELF = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/diagnostic-link82.elf"
PRG = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/diagnostic-link82.prg"
DRIVER = Path(__file__).resolve()
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-D2-transport-desk-attribution-receipt.json")

OBSERVED_PC = 0x754A
ENTRY_PC = 0x2023
ENTRY_STOP_PC = 0x2024
FIRST_DIAGNOSTIC_DELTA = 0x47C5
EXPECTED_ELF_SHA256 = "fdb8de75a95027f9fdd0813fbe9a2d47a2d36f63ae1b1f7cd0ba661700608d96"
EXPECTED_PRG_SHA256 = "405549c882d18faf61949037cfcc2d0c2435d97b52a95ae4b94e2d6bd4251706"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_bytes(canonical(value))


def linked_truth() -> dict[str, Any]:
    require(sha256(ELF) == EXPECTED_ELF_SHA256, "diagnostic ELF identity drift")
    require(sha256(PRG) == EXPECTED_PRG_SHA256, "diagnostic PRG identity drift")
    device = load(DEVICE)
    require(device["entry_witness"]["observed_PC"] == "0x754a",
            "stopped PC authority drift")
    require(device["entry_witness"]["expected_post_instruction_PC"] == "0x2024",
            "entry-stop authority drift")
    require(device["result"]["measured_forms_started"] == 0,
            "device receipt entered a measured form")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    start = truth.symbol("_start")
    callprim = truth.symbol("vm_callprim")
    require(start.value == ENTRY_PC, "Link-82 entry drift")
    require(callprim.value <= OBSERVED_PC < callprim.value + callprim.bytes,
            "stopped PC is not inside vm_callprim")
    section = truth.section(callprim.section)
    body = truth.section_bytes(callprim.section)
    section_offset = OBSERVED_PC - section.address
    require(0 <= section_offset <= len(body) - 2,
            "stopped PC outside linked section bytes")
    opcode = body[section_offset:section_offset + 2]
    require(opcode == bytes.fromhex("a505"), "stopped opcode drift")

    payload = PRG.read_bytes()
    require(len(payload) >= 2, "diagnostic PRG truncated")
    load_address = int.from_bytes(payload[:2], "little")
    file_offset = 2 + OBSERVED_PC - load_address
    require(load_address == 0x2001 and payload[file_offset:file_offset + 2] == opcode,
            "PRG/ELF stopped-byte mismatch")
    require(OBSERVED_PC > FIRST_DIAGNOSTIC_DELTA > ENTRY_STOP_PC,
            "stopped PC did not prove execution beyond entry")

    return {
        "observed_PC": "0x754a",
        "entry_PC": "0x2023",
        "entry_post_instruction_PC": "0x2024",
        "first_diagnostic_delta": "0x47c5",
        "PC_after_entry_and_first_diagnostic_delta": True,
        "symbol": "vm_callprim",
        "symbol_start": f"0x{callprim.value:04x}",
        "symbol_bytes": callprim.bytes,
        "symbol_offset": OBSERVED_PC - callprim.value,
        "section": callprim.section,
        "linked_bytes": opcode.hex(),
        "instruction": "LDA $05",
        "PRG_and_ELF_bytes_agree": True,
    }


def audit(facts: dict[str, Any]) -> None:
    linked = facts["linked_truth"]
    transport = facts["transport_decision"]
    require(linked["observed_PC"] == "0x754a"
            and linked["symbol"] == "vm_callprim"
            and linked["symbol_offset"] == 0xAAA
            and linked["linked_bytes"] == "a505"
            and linked["PC_after_entry_and_first_diagnostic_delta"]
            and linked["PRG_and_ELF_bytes_agree"],
            "stopped-PC linkage drift")
    require(transport == {
        "virtual_RETURN_arrival": "proved-by-execution-beyond-_start",
        "BASIC_command_consumed": True,
        "entry_breakpoint_effective_at_crossing": False,
        "named_mechanism": (
            "monitor entry breakpoint was not effective through the "
            "virtual-matrix start sequence"),
        "decision": "breakpoint-loss-not-RETURN-loss",
        "Stage_2_device_discriminator_required": False,
    }, "transport decision drift")


def mutations(base: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[list[str], Any]] = {
        "put-PC-before-entry": (
            ["linked_truth", "PC_after_entry_and_first_diagnostic_delta"], False),
        "move-PC-outside-symbol": (["linked_truth", "symbol"], "basic_idle"),
        "change-linked-opcode": (["linked_truth", "linked_bytes"], "0000"),
        "claim-return-loss": (
            ["transport_decision", "decision"], "RETURN-loss"),
        "claim-effective-breakpoint": (
            ["transport_decision", "entry_breakpoint_effective_at_crossing"], True),
    }
    rejected: dict[str, str] = {}
    for name, (path, replacement) in cases.items():
        trial = deepcopy(base)
        target: Any = trial
        for component in path[:-1]:
            target = target[component]
        target[path[-1]] = replacement
        try:
            audit(trial)
        except AttributionError as error:
            rejected[name] = str(error)
        else:
            raise AttributionError(f"transport mutation survived: {name}")
    return rejected


def expected() -> dict[str, Any]:
    facts = {
        "linked_truth": linked_truth(),
        "transport_decision": {
            "virtual_RETURN_arrival": "proved-by-execution-beyond-_start",
            "BASIC_command_consumed": True,
            "entry_breakpoint_effective_at_crossing": False,
            "named_mechanism": (
                "monitor entry breakpoint was not effective through the "
                "virtual-matrix start sequence"),
            "decision": "breakpoint-loss-not-RETURN-loss",
            "Stage_2_device_discriminator_required": False,
        },
    }
    audit(facts)
    rejected = mutations(facts)
    return {
        "format": "lisp65-c2.3-v1.6-D2-transport-desk-attribution-v1",
        "recorded_on": date.today().isoformat(),
        "status": "attributed-breakpoint-loss-not-RETURN-loss",
        "authorities": {
            "owner_commission": bind(PLAN),
            "device_first_red": bind(DEVICE),
            "diagnostic_ELF": bind(ELF),
            "diagnostic_PRG": bind(PRG),
            "driver": bind(DRIVER),
        },
        "facts": facts,
        "mutations_rejected": rejected,
        "execution_witnesses": 1 + len(rejected),
        "next_gate": (
            "No virtual D2 rerun until its closure rejects this exact "
            "breakpoint-retention failure and uses a witness that survives the "
            "chosen launch transport; physical RETURN remains an owner fallback."),
        "claim_limit": (
            "Desk/ELF attribution only. The result names the failed harness "
            "boundary, not which low-level monitor command discarded or failed "
            "to install the breakpoint. No new device contact, product byte, "
            "require, defstruct, R/A/I/G row, fix or rerun is claimed."),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "write", "check"))
    args = parser.parse_args()
    value = expected()
    if args.action == "selftest":
        print("c2-v16-D2-transport-attribution: SELFTEST PASS mutations=5")
        return 0
    if args.action == "write":
        write_json(RECEIPT, value)
    else:
        require(RECEIPT.is_file() and RECEIPT.read_bytes() == canonical(value),
                "transport attribution receipt drift")
    print("c2-v16-D2-transport-attribution: PASS "
          "PC=0x754a symbol=vm_callprim outcome=breakpoint-loss")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, ElfTruthError, OSError, KeyError, ValueError,
            json.JSONDecodeError) as error:
        print(f"c2-v16-D2-transport-attribution: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(1)
