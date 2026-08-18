#!/usr/bin/env python3
"""Reconstruct the defstruct BRK stack boundary from existing evidence.

The terminal origin row proved a software BRK at $BF71.  This desk gate binds
the exact handler stack geometry, enumerates the terminal append return chain
from the linked diagnostic ELF, and asks whether the already captured files
contain the older hardware-stack bytes needed to identify the corrupt edge.

They do not.  More importantly, an immediate RTS or RTI would have consumed
bytes that the subsequent BRK frame overwrote.  The gate therefore makes no
edge or overwrite claim and specifies one stopped-state low-RAM row that
contains both the surviving caller frames and the live zero-page transfer
state.  It never accesses a device or changes a product artifact.
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
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))
from elf_truth import ElfTruth, ElfTruthError  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
DEVICE = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-irq-origin-contact-device-receipt.json")
PREPARATION = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-irq-origin-contact-preparation-receipt.json")
ORIGIN_DESK = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-irq-origin-desk-attribution-receipt.json")
SISTER = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-terminal-ingress-sister-receipt.json")
ELF = ROOT / (
    "build/c2.3/defstruct-terminal-ingress-sister-link92/artifacts/"
    "diagnostic-terminal-ingress.elf")
RECORD = ROOT / "build/c2.3/defstruct-irq-origin-contact/device/origin-record.bin"
REGISTERS = ROOT / (
    "build/c2.3/defstruct-irq-origin-contact/device/final-registers.json")
RECEIPT = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-brk-stack-forensics-receipt.json")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"

FORMAT = "lisp65-c2.3-post-v1.4-defstruct-brk-stack-forensics-v1"
RECORDED_ON = "2026-08-10"
AUTHORIZATION_COMMIT = "e93db4b1"
AUTHORIZATION_PATH = "docs/planning/post-v1.4.0-direction-plan.md"

HANDLER_SP = 0x8D
PRE_BRK_SP = 0x94
BRK_PC = 0xBF71
BRK_CONTINUATION = 0xBF73
NAME_LENGTHS = 0xBE1C
NAME_LENGTH_BYTES = 0x178
LOW_RAM_BEGIN = 0x0000
LOW_RAM_BYTES = 0x0200


class ForensicsError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ForensicsError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": digest(raw)}


def git_bind(commit: str, path: str) -> dict[str, Any]:
    raw = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout.strip()
    return {"authority": "git-blob", "commit": full, "path": path,
            "bytes": len(raw), "sha256": digest(raw)}


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(canonical(value))
    temporary.replace(path)


def disassembly() -> str:
    return subprocess.run(
        [str(OBJDUMP), "-d", "--no-show-raw-insn", str(ELF)], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=True).stdout


def instruction(text: str, address: int) -> tuple[str, str]:
    match = re.search(
        rf"^[ \t]*{address:x}:[ \t]+([a-z0-9]+)"
        rf"(?:[ \t]+([^;\n]*?))?[ \t]*(?:;.*)?$",
        text, re.MULTILINE)
    require(match is not None, f"instruction absent at ${address:04X}")
    return match.group(1), (match.group(2) or "").strip()


def require_instruction(text: str, address: int, opcode: str,
                        operand_prefix: str = "") -> dict[str, Any]:
    found_opcode, operand = instruction(text, address)
    require(found_opcode == opcode, f"opcode drift at ${address:04X}")
    if operand_prefix:
        require(operand.startswith(operand_prefix),
                f"operand drift at ${address:04X}: {operand}")
    return {"pc": f"0x{address:04X}", "opcode": opcode,
            "operand": operand}


def exact_terminal_transfers(text: str) -> list[dict[str, Any]]:
    """Bind the direct call/return spine around the terminal append."""
    specifications = (
        (0x52B7, "jsr", "$6aa0", "VM dispatcher -> vm_callprim"),
        (0x78FF, "jsr", "$24cb", "vm_callprim -> persistent append"),
        (0x2515, "jsr", "$e7e4", "append wrapper -> c2_append_begin"),
        (0xB5F1, "jmp", "$1870", "plan-walk facade tail transfer"),
        (0x18A0, "jsr", "$e09d", "one plan phase -> overlay call"),
        (0x18B9, "rts", "", "successful plan-walk return"),
        (0x18BE, "rts", "", "failed plan-walk return"),
        (0xE0B7, "jmp", "$b5ca", "overlay facade tail transfer"),
        (0xB5CA, "jmp", "$2473", "overlay target tail transfer"),
        (0x249F, "jsr", "$281f", "mapped overlay execution"),
        (0x24CA, "rts", "", "overlay-call return"),
        (0xE98D, "jsr", "$b5f1", "publish-plan walk"),
        (0xE9A2, "jsr", "$e09d", "terminal overlay call 1"),
        (0xE9B2, "jsr", "$e09d", "terminal overlay call 2"),
        (0xE9BC, "bra", "$e9cd", "phase-owner completion handoff"),
        (0xE9BE, "jsr", "$e9e5", "rollback alternative"),
        (0xE9FF, "jmp", "$b5f1", "rollback-plan tail transfer"),
        (0xE9E4, "rts", "", "c2_append_begin return"),
        (0x251A, "jsr", "$ffd4", "transaction-end handoff"),
        (0x253E, "rts", "", "append-wrapper return"),
        (0x7902, "jmp", "$749f", "vm_callprim result normalization"),
        (0x7BA9, "rts", "", "vm_callprim return"),
    )
    rows = []
    for address, opcode, operand, role in specifications:
        row = require_instruction(text, address, opcode, operand)
        row["role"] = role
        if opcode == "jsr":
            row["legal_return_PC"] = f"0x{address + 3:04X}"
            row["stack_word_before_RTS"] = f"0x{address + 2:04X}"
        rows.append(row)
    return rows


def balanced_temporary_sites(text: str) -> list[dict[str, Any]]:
    """Bind the two explicit hardware-stack save blocks on the append spine."""
    plan_push = [require_instruction(text, address, "pha")
                 for address in (0x188C, 0x188F, 0x1892, 0x1895)]
    plan_pop = [require_instruction(text, address, "pla")
                for address in (0x18A4, 0x18A7, 0x18AA, 0x18AD)]
    wrapper_push = [require_instruction(text, address, "phy")
                    for address in (0x24DC, 0x24DF, 0x24E2)]
    wrapper_pop = [require_instruction(text, address, "plx")
                   for address in (0x2526, 0x2529, 0x252C)]
    return [
        {"owner": "c2_append_plan_walk", "pushes": plan_push,
         "pops": plan_pop, "static_balance": 0,
         "claim": "balanced in the linked ordinary-return path"},
        {"owner": "c2_product_append_staged", "pushes": wrapper_push,
         "pops": wrapper_pop, "static_balance": 0,
         "claim": "balanced in the linked ordinary-return path"},
    ]


def indirect_sites(text: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"^\s*([0-9a-f]+):\s+jmp\s+(\([^\n;]+\))", re.MULTILINE)
    return [{"pc": f"0x{int(pc, 16):04X}", "operand": operand.strip()}
            for pc, operand in pattern.findall(text)]


def stack_geometry(device: dict[str, Any]) -> dict[str, Any]:
    registers = device["register_tuple"]
    require((int(registers["SP"], 16) & 0xFF) == HANDLER_SP
            and int(registers["X"], 16) == HANDLER_SP,
            "handler SP/X tuple drift")
    require(device["terminal_row"]["stacked_P"] == "0x30"
            and device["terminal_row"]["stacked_return_PC"] == "0xBF73",
            "BRK frame authority drift")

    # Hardware BRK pushed three bytes; the handler then pushed A/X/Y/Z.
    require(HANDLER_SP + 7 == PRE_BRK_SP, "stack arithmetic drift")
    frame = [
        {"address": "0x018E", "meaning": "handler-saved Z"},
        {"address": "0x018F", "meaning": "handler-saved Y"},
        {"address": "0x0190", "meaning": "handler-saved X"},
        {"address": "0x0191", "meaning": "handler-saved A"},
        {"address": "0x0192", "meaning": "BRK-stacked P", "value": "0x30"},
        {"address": "0x0193", "meaning": "BRK-stacked continuation low",
         "value": "0x73"},
        {"address": "0x0194", "meaning": "BRK-stacked continuation high",
         "value": "0xBF"},
    ]
    return {
        "handler_SP_after_A_X_Y_Z_pushes": "0x8D",
        "pre_BRK_SP": "0x94",
        "reconstructed_frame": frame,
        "surviving_older_stack_range": "0x0195..0x01FF",
        "immediate_RTS_case": {
            "required_consumed_word": "0xBF70",
            "RTS_effect": "pop $BF70, increment to execution PC $BF71",
            "consumed_addresses": ["0x0193", "0x0194"],
            "post_escape_fate": "both bytes overwritten by BRK PCL/PCH",
        },
        "immediate_RTI_case": {
            "consumed_addresses": ["0x0192", "0x0193", "0x0194"],
            "post_escape_fate": "all three bytes overwritten by BRK P/PCL/PCH",
        },
        "indirect_jump_case": {
            "hardware_stack_consumed": False,
            "needed_state": "live zero-page/table vector and surviving caller frames",
        },
        "recoverability": (
            "the immediate consumed RTS/RTI bytes are unrecoverable after BRK; "
            "older caller frames can still name the enclosing edge"),
    }


def existing_capture_gap(device: dict[str, Any]) -> dict[str, Any]:
    authorities = device["authorities"]
    captured = [ROOT / authorities[name]["path"]
                for name in ("record", "registers")]
    require(captured == [RECORD, REGISTERS], "device authority path drift")
    require(RECORD.stat().st_size == 65, "origin record geometry drift")
    files = [path.name for path in RECORD.parent.iterdir() if path.is_file()]
    page_candidates = [name for name in files
                       if "stack" in name.lower() or "page1" in name.lower()
                       or "lowram" in name.lower()]
    require(not page_candidates, "a stack/low-RAM capture now exists")
    return {
        "captured_record_bytes": RECORD.stat().st_size,
        "captured_register_tuple": True,
        "captured_Page_1_bytes": 0,
        "captured_zero_page_bytes": 0,
        "candidate_stack_files": page_candidates,
        "conclusion": (
            "no byte at or above $0195 is present; the enclosing legal frame "
            "and live indirect-transfer state cannot be reconstructed"),
    }


def name_buffer_binding(truth: ElfTruth, text: str) -> dict[str, Any]:
    symbol = truth.symbol("namelen4")
    require(symbol.section == ".bss" and symbol.value == NAME_LENGTHS
            and symbol.bytes == NAME_LENGTH_BYTES,
            "namelen4 identity drift")
    offset = BRK_PC - symbol.value
    require(offset == 0x155, "BRK offset within namelen4 drift")
    direct = re.findall(
        rf"^\s*[0-9a-f]+:\s+(?:jsr|jmp|bra|b\w+)\s+\${BRK_PC:x}\b",
        text, re.MULTILINE)
    require(not direct, "linked direct control transfer to $BF71 appeared")
    return {
        "object": "namelen4",
        "section": symbol.section,
        "executable": False,
        "start": "0xBE1C",
        "bytes": symbol.bytes,
        "BRK_offset": "0x0155",
        "packed_symbol_indices": [2 * offset, 2 * offset + 1],
        "linked_direct_transfers_to_BF71": 0,
        "legal_writer": {
            "function": "intern",
            "read_address_formation": "0x2E77..0x2E92 via zero page $04/$05",
            "write_address_formation": "0x2FF8..0x3029 via zero page $06/$07",
        },
        "hypothesis_status": "UNPROVED-CORRELATION-ONLY",
        "reason": (
            "$BF71 is the address of packed length entries 682/683, but the "
            "capture has neither live nsym nor a stack/vector byte equal to "
            "$BF70/$BF71; no overwrite provenance is present"),
    }


def missing_row(device: dict[str, Any]) -> dict[str, Any]:
    registers = device["register_tuple"]
    exact_tuple = {key: registers[key]
                   for key in ("PC", "SP", "X", "MAPH", "MAPL")}
    return {
        "name": "stopped-low-RAM-and-hardware-stack-forensics",
        "authorization": "specified-only; not authorized by this desk result",
        "device_actions": 0,
        "reads": 1,
        "range": {"physical_address": "0x00000000", "bytes": LOW_RAM_BYTES,
                  "covers": "zero page $0000..$00FF and Page 1 $0100..$01FF"},
        "view": (
            "physical Bank-0 low RAM, CPU-equivalent under the exact captured "
            "MAPH=$8000/MAPL=$0000 tuple"),
        "precondition": {
            "confirm_same_stopped_tuple_first": exact_tuple,
            "confirm_origin_record_sha256": bind(RECORD)["sha256"],
            "on_mismatch": "abort without a forensic claim or read"},
        "choreography": (
            "no RUN, reset, stop, resume, screen read, I/O read or mapping "
            "change; one contiguous read from the already stopped state"),
        "why_512_bytes_are_minimally_sufficient": [
            "$0195..$01FF retains older legal JSR frames beneath the BRK frame",
            "$0014/$0015 retains the resident unindexed indirect-JMP vector",
            "$0059/$005A supplies live nsym for the namelen4-address correlation",
            "$0089 supplies phase-owner state; $0002/$0003 supplies software SP",
        ],
        "decision_use": {
            "RTS_chain": (
                "resolve surviving little-endian words as JSR return PCs and "
                "identify the innermost legal append/VM frame"),
            "RTI_chain": (
                "test surviving P/PCL/PCH-shaped older frames; the immediate "
                "consumed frame itself remains overwritten"),
            "indirect_jump": (
                "bind live $14/$15 and relevant indexed-dispatch state against "
                "the linked indirect-site inventory"),
            "name_neighbor": (
                "test live nsym and any surviving $70/$BF or $71/$BF word; "
                "absence keeps the neighbor-overwrite hypothesis unproved"),
        },
        "hard_limit": (
            "even this row cannot recover the immediate RTS/RTI bytes overwritten "
            "by BRK; it can name the enclosing corrupt edge or rule transfer "
            "classes down to a later purpose-built witness"),
    }


def derive() -> dict[str, Any]:
    device = load(DEVICE)
    require(device["status"] == "BRK-CONTROL-FLOW-ESCAPE"
            and device["CPU_left_stopped"] is True,
            "BRK device authority drift")
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    text = disassembly()
    transfers = exact_terminal_transfers(text)
    temporaries = balanced_temporary_sites(text)
    indirect = indirect_sites(text)
    require(len(indirect) == 14, "linked indirect-JMP inventory drift")
    gap = existing_capture_gap(device)
    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "EDGE-UNNAMED; ONE-LOW-RAM-ROW-SPECIFIED",
        "authorities": {
            "owner_commission": git_bind(AUTHORIZATION_COMMIT,
                                          AUTHORIZATION_PATH),
            "BRK_device_result": bind(DEVICE),
            "origin_preparation": bind(PREPARATION),
            "origin_desk": bind(ORIGIN_DESK),
            "diagnostic_sister": bind(SISTER),
            "diagnostic_ELF": bind(ELF),
            "origin_record": bind(RECORD),
            "stopped_registers": bind(REGISTERS),
        },
        "stack_reconstruction": stack_geometry(device),
        "existing_capture": gap,
        "terminal_transfer_inventory": {
            "direct_return_spine": transfers,
            "explicit_temporary_save_blocks": temporaries,
            "linked_indirect_JMP_sites": indirect,
            "direct_transfer_to_BF71": False,
            "ordinary_static_balance_result": (
                "the enumerated append wrapper and plan-walk save blocks are "
                "balanced; this does not prove target-time stack integrity"),
        },
        "name_buffer_hypothesis": name_buffer_binding(truth, text),
        "desk_decision": {
            "corrupted_edge": None,
            "RTS_attributed": False,
            "RTI_attributed": False,
            "indirect_jump_attributed": False,
            "name_neighbor_overwrite_attributed": False,
            "reason": (
                "the capture omitted every surviving older hardware-stack byte "
                "and live zero-page transfer state; BRK overwrote the immediate "
                "RTS/RTI slots"),
            "next": "exactly one stopped-state low-RAM row",
            "device_read_authorized": False,
            "fix_authorized": False,
        },
        "required_read_row": missing_row(device),
        "claim_limit": (
            "Host/ELF forensics only. It reconstructs the BRK frame, excludes a "
            "linked direct transfer to $BF71 and proves the current capture cannot "
            "name RTS, RTI, indirect-JMP or overwrite provenance. It specifies but "
            "does not authorize one read; no device, fix, link or product-byte "
            "claim follows."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT and value["status"] ==
            "EDGE-UNNAMED; ONE-LOW-RAM-ROW-SPECIFIED",
            "stack-forensics identity drift")
    stack = value["stack_reconstruction"]
    require(stack["pre_BRK_SP"] == "0x94"
            and stack["surviving_older_stack_range"] == "0x0195..0x01FF"
            and stack["immediate_RTS_case"]["required_consumed_word"] == "0xBF70"
            and stack["immediate_RTS_case"]["consumed_addresses"]
            == ["0x0193", "0x0194"],
            "BRK/RTS stack geometry drift")
    gap = value["existing_capture"]
    require(gap["captured_Page_1_bytes"] == 0
            and gap["captured_zero_page_bytes"] == 0,
            "missing captured state was silently promoted")
    hypothesis = value["name_buffer_hypothesis"]
    require(hypothesis["BRK_offset"] == "0x0155"
            and hypothesis["packed_symbol_indices"] == [682, 683]
            and hypothesis["linked_direct_transfers_to_BF71"] == 0
            and hypothesis["hypothesis_status"] == "UNPROVED-CORRELATION-ONLY",
            "name-buffer correlation was broadened")
    decision = value["desk_decision"]
    require(decision["corrupted_edge"] is None
            and decision["RTS_attributed"] is False
            and decision["RTI_attributed"] is False
            and decision["indirect_jump_attributed"] is False
            and decision["name_neighbor_overwrite_attributed"] is False
            and decision["device_read_authorized"] is False
            and decision["fix_authorized"] is False,
            "desk forensics overclaims an edge, read or fix")
    row = value["required_read_row"]
    require(row["authorization"] ==
            "specified-only; not authorized by this desk result"
            and row["device_actions"] == 0 and row["reads"] == 1
            and row["range"] == {
                "physical_address": "0x00000000", "bytes": 512,
                "covers": "zero page $0000..$00FF and Page 1 $0100..$01FF"}
            and row["precondition"]["on_mismatch"]
            == "abort without a forensic claim or read",
            "single missing read-row boundary drift")


def audit(value: dict[str, Any]) -> None:
    validate(value)
    require(value == derive(), "stack-forensics receipt differs from reconstruction")


def mutate(value: dict[str, Any], path: list[Any], replacement: Any) -> None:
    cursor: Any = value
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = replacement


def selftest() -> dict[str, Any]:
    base = derive()
    cases: list[tuple[str, list[Any], Any]] = [
        ("name-edge", ["desk_decision", "corrupted_edge"], "RTS@c2_append_begin"),
        ("claim-RTS", ["desk_decision", "RTS_attributed"], True),
        ("claim-RTI", ["desk_decision", "RTI_attributed"], True),
        ("claim-indirect", ["desk_decision", "indirect_jump_attributed"], True),
        ("claim-name-overwrite", ["desk_decision",
                                   "name_neighbor_overwrite_attributed"], True),
        ("invent-page1", ["existing_capture", "captured_Page_1_bytes"], 256),
        ("invent-zero-page", ["existing_capture", "captured_zero_page_bytes"], 256),
        ("forget-RTS-overwrite", ["stack_reconstruction", "immediate_RTS_case",
                                  "consumed_addresses"], ["0x0195", "0x0196"]),
        ("make-name-causal", ["name_buffer_hypothesis", "hypothesis_status"],
         "ATTRIBUTED"),
        ("invent-direct-transfer", ["name_buffer_hypothesis",
                                    "linked_direct_transfers_to_BF71"], 1),
        ("authorize-read", ["desk_decision", "device_read_authorized"], True),
        ("authorize-fix", ["desk_decision", "fix_authorized"], True),
        ("two-reads", ["required_read_row", "reads"], 2),
        ("device-action", ["required_read_row", "device_actions"], 1),
        ("page1-only", ["required_read_row", "range", "physical_address"],
         "0x00000100"),
        ("short-row", ["required_read_row", "range", "bytes"], 256),
        ("permit-tuple-mismatch", ["required_read_row", "precondition",
                                   "on_mismatch"], "continue"),
        ("pre-authorize-row", ["required_read_row", "authorization"],
         "authorized"),
    ]
    rejected = []
    for name, path, replacement in cases:
        trial = deepcopy(base)
        mutate(trial, path, replacement)
        try:
            validate(trial)
            require(trial == derive(), "mutated receipt accepted")
        except ForensicsError:
            rejected.append(name)
        else:
            raise ForensicsError(f"mutation survived: {name}")
    require(len(rejected) == len(cases), "mutation accounting drift")
    return {"status": "SELFTEST PASS", "mutations_rejected": len(rejected),
            "cases": rejected, "corrupted_edge": None,
            "next": "one specified stopped-state low-RAM row"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("derive", "record", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "derive":
        value = derive()
    elif args.action == "record":
        value = derive()
        write(RECEIPT, value)
    elif args.action == "selftest":
        value = selftest()
    else:
        audit(load(RECEIPT))
        value = {"status": "PASS", "mutations_rejected": 18,
                 "corrupted_edge": None,
                 "next": "one specified stopped-state low-RAM row"}
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ForensicsError, ElfTruthError, OSError, ValueError, KeyError,
            IndexError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"DEFSTRUCT BRK STACK FORENSICS: {error}", file=sys.stderr)
        raise SystemExit(1)
