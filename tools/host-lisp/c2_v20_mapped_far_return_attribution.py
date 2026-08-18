#!/usr/bin/env python3
"""Attribute the v2.0 D1 mapped-far return contradiction at the desk.

The stopped-state row showed MAPL=$2480 at a BRK in ``nameoff_get``.  This
checker enumerates every terminal return of both linked far-service entries,
binds the shared resident unmap continuation, and then audits the exact media
delivery ranges.  The result is deliberately an attribution, not a repair:
the linked service has no legitimate exit that bypasses the unmap, while the
packed Bank-2 role ends before the service's LMA and therefore cannot deliver
any of its 874 bytes.
"""

from __future__ import annotations

import argparse
import ast
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
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
DEVICE = EVIDENCE / "c2.3-v2.0-building-heap-device-receipt.json"
DEVICE_DRIVER = ROOT / "tools/host-lisp/c2_v20_building_heap_device_result.py"
MEDIA = EVIDENCE / (
    "c2.3-v2.0-crc-carveout-media-liveness-closure-receipt.json")
MANIFEST = ROOT / (
    "build/c2.3/v2.0-crc-carveout-media-liveness/shared-system/"
    "candidate-manifest.json")
PRODUCT_D81 = ROOT / (
    "build/c2.3/v2.0-crc-carveout-media-liveness/shared-system/"
    "lisp65-product.d81")
ELF = ROOT / (
    "build/c2.3/v2.0-crc-carveout-card/final/"
    "lisp65-c2-substitution-linked.prg.elf")
PRG = ROOT / (
    "build/c2.3/v2.0-crc-carveout-card/final/"
    "lisp65-c2-substitution-linked.prg")
BANK2 = ROOT / (
    "build/c2.3/v2.0-crc-carveout-card/final/"
    "fresh-c2-lite-prelink-gates/v6-semantics/bank2-static-code.bin")
CONTRACT = ROOT / "config/c2-stack-overlay-ownership-contract.json"
FACADE = ROOT / "src/c2_mapped_far_service.s"
BODY = ROOT / "src/c2_mapped_far_convergence.s"
SYMBOL = ROOT / "src/symbol.c"
EVAL = ROOT / "src/eval.c"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
RECEIPT = EVIDENCE / (
    "c2.3-v2.0-mapped-far-return-attribution-receipt.json")
DRIVER = Path(__file__).resolve()

FORMAT = "lisp65-c2.3-v20-mapped-far-return-attribution-v1"
RECORDED_ON = "2026-08-12"
COMMISSION_COMMIT = "e306e80b"
SERVICE_SECTION = ".lisp65_c2_mapped_far_service"
BRANCHES = {"beq", "bne", "bcc", "bcs", "bmi", "bpl", "bvc", "bvs"}


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha(raw: bytes) -> str:
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
            "sha256": sha(raw)}


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    require(b"Far-return attribution commissioned" in raw
            and b"No fix, no card, no contact before the exit is named" in raw,
            "owner commission text drift")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def literal_assignment(path: Path, name: str) -> Any:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if (isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == name
                        for target in node.targets)):
            return ast.literal_eval(node.value)
    raise AttributionError(f"literal assignment absent: {name}")


def target(operand: str) -> int | None:
    match = re.search(r"\$([0-9a-fA-F]+)", operand)
    return int(match.group(1), 16) if match else None


def disassembly() -> dict[int, tuple[str, str]]:
    text = subprocess.run(
        [str(OBJDUMP), "-d", "--no-show-raw-insn",
         f"--section={SERVICE_SECTION}", str(ELF)],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout
    result: dict[int, tuple[str, str]] = {}
    pattern = re.compile(
        r"^\s*([0-9a-fA-F]+):\s+\t([a-z][a-z0-9]*)\s*(.*)$")
    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            result[int(match.group(1), 16)] = (
                match.group(2).lower(), match.group(3).strip())
    require(result, "far-service disassembly empty")
    return result


def terminal_returns(instructions: dict[int, tuple[str, str]], start: int,
                     section_start: int, section_end: int) -> list[int]:
    """Explore direct control flow while modelling local JSR/RTS nesting."""
    addresses = sorted(instructions)
    following = {
        address: addresses[index + 1] if index + 1 < len(addresses) else None
        for index, address in enumerate(addresses)
    }
    pending: list[tuple[int, tuple[int, ...]]] = [(start, ())]
    visited: set[tuple[int, tuple[int, ...]]] = set()
    exits: set[int] = set()
    while pending:
        pc, stack = pending.pop()
        state = (pc, stack)
        if state in visited:
            continue
        visited.add(state)
        require(pc in instructions, f"control flow escaped instruction map: {pc:#x}")
        require(len(stack) <= 16, "unexpected recursive far-service control flow")
        mnemonic, operand = instructions[pc]
        next_pc = following[pc]
        if mnemonic == "jsr":
            callee = target(operand)
            require(callee is not None
                    and section_start <= callee < section_end,
                    f"far service gained an external call at {pc:#x}")
            require(next_pc is not None, "JSR lacks continuation")
            pending.append((callee, stack + (next_pc,)))
        elif mnemonic == "rts":
            if stack:
                pending.append((stack[-1], stack[:-1]))
            else:
                exits.add(pc)
        elif mnemonic in {"jmp", "bra"}:
            edge = target(operand)
            require(edge is not None and section_start <= edge < section_end,
                    f"far service gained an external transfer at {pc:#x}")
            pending.append((edge, stack))
        elif mnemonic in BRANCHES:
            edge = target(operand)
            require(edge is not None and next_pc is not None,
                    f"branch lacks direct target at {pc:#x}")
            pending.extend(((edge, stack), (next_pc, stack)))
        else:
            require(mnemonic not in {"brk", "rti"} and next_pc is not None,
                    f"unexpected terminal opcode at {pc:#x}: {mnemonic}")
            pending.append((next_pc, stack))
    return sorted(exits)


def linked_exit_facts(truth: ElfTruth) -> dict[str, Any]:
    section = truth.section(SERVICE_SECTION)
    vm = truth.symbol("c2_mapped_far_vm_code_load_converged")
    physical = truth.symbol("c2_mapped_far_physical_read_converged")
    facade = truth.symbol("vm_code_load_converged")
    enter = truth.symbol("c2_mapped_far_enter")
    leave = truth.symbol("c2_mapped_far_leave")
    require((section.address, section.bytes) == (0x78B2, 874),
            "far-service linked VMA/size drift")
    require((vm.value, physical.value) == (0x79DC, 0x7BBA),
            "far-service entry identity drift")
    code = disassembly()
    vm_exits = terminal_returns(
        code, vm.value, section.address, section.address + section.bytes)
    physical_exits = terminal_returns(
        code, physical.value, section.address, section.address + section.bytes)
    require(vm_exits == [0x79D3, 0x79DB, 0x7A32, 0x7A38],
            f"VM exit inventory drift: {vm_exits}")
    require(physical_exits == [0x7BB1, 0x7BB9, 0x7C18, 0x7C1B],
            f"physical exit inventory drift: {physical_exits}")
    require((facade.value, facade.bytes, enter.value, enter.bytes,
             leave.value, leave.bytes)
            == (0xB3B0, 9, 0xB3C2, 19, 0xB3D5, 15),
            "resident facade identity drift")
    facade_bytes = truth.section_bytes(facade.section)
    base = truth.section(facade.section).address
    linked = facade_bytes[facade.value - base:facade.value - base + facade.bytes]
    leave_bytes = facade_bytes[leave.value - base:leave.value - base + leave.bytes]
    require(linked == bytes.fromhex("20c2b320dc794cd5b3")
            and leave_bytes == bytes.fromhex(
                "48a900a200a000a3805cea68a30060"),
            "shared linked unmap continuation drift")
    return {
        "section": {"VMA_start": "0x78B2", "VMA_end": "0x7C1C",
                    "bytes": 874},
        "entries": {
            "vm_code_load": {
                "entry": "0x79DC",
                "terminal_RTS": [f"0x{value:04X}" for value in vm_exits],
                "outcomes": ["primary-success", "primary-timeout",
                             "already-converged", "input-or-probe-failure"],
            },
            "physical_read": {
                "entry": "0x7BBA",
                "terminal_RTS": [
                    f"0x{value:04X}" for value in physical_exits],
                "outcomes": ["primary-success", "primary-timeout",
                             "input-or-probe-failure", "already-converged"],
            },
        },
        "terminal_exit_count": len(vm_exits) + len(physical_exits),
        "common_return_PC": "0xB3B6",
        "common_return_instruction": "JMP $B3D5",
        "unmap_entry": "0xB3D5",
        "unmap_result": "MAPL=0x0000",
        "legitimate_exit_without_unmap": False,
        "fail_closed_handoff_inside_service": False,
    }


def delivery_facts(truth: ElfTruth) -> dict[str, Any]:
    manifest = load(MANIFEST)
    media = load(MEDIA)
    artifacts = manifest["artifacts"]
    bank_rows = [row for row in artifacts
                 if row.get("role") == "c2-bank2-static-code-plane"]
    require(len(bank_rows) == 1, "unique Bank-2 media role absent")
    bank = bank_rows[0]
    require(bank == {"bytes": 46043, "name": "bank2-static-code.bin",
                     "path": BANK2.relative_to(ROOT).as_posix(),
                     "role": "c2-bank2-static-code-plane",
                     "sha256": sha(BANK2.read_bytes())},
            "Bank-2 manifest binding drift")
    records = manifest["descriptor"]["records"]
    role = [row for row in records if row["role_id"] == 1]
    require(len(role) == 1 and role[0]["name"] == "code.bin"
            and role[0]["destination"] == 0x20000
            and role[0]["bytes"] == len(BANK2.read_bytes()),
            "Bank-2 descriptor delivery binding drift")
    service_start = truth.symbol(
        "__lisp65_c2_mapped_far_service_load_start").value
    service_end = truth.symbol(
        "__lisp65_c2_mapped_far_service_load_end").value
    delivered_start = role[0]["destination"]
    delivered_end = delivered_start + role[0]["bytes"]
    require((service_start, service_end, delivered_end)
            == (0x2B8B2, 0x2BC1C, 0x2B3DB),
            "far-service delivery extent drift")
    covering = [row for row in records
                if row["destination"] <= service_start
                and service_end <= row["destination"] + row["bytes"]]
    service_bytes = truth.section_bytes(SERVICE_SECTION)
    require(len(service_bytes) == 874
            and not covering
            and BANK2.read_bytes().find(service_bytes) < 0
            and PRG.read_bytes().find(service_bytes) < 0
            and PRODUCT_D81.read_bytes().find(service_bytes) < 0,
            "far-service bytes unexpectedly delivered")
    require(media["shared_system"]["product_D81"] == bind(PRODUCT_D81)
            and media["shared_system"]["readback"] == "passed",
            "physical-contact media identity/readback drift")
    return {
        "bank2_role": {
            "media_name": "code.bin", "role_id": 1,
            "destination_start": "0x00020000",
            "destination_end_exclusive": "0x0002B3DB",
            "bytes": role[0]["bytes"], "sha256": bank["sha256"],
        },
        "linked_far_service": {
            "LMA_start": "0x0002B8B2", "LMA_end_exclusive": "0x0002BC1C",
            "bytes": len(service_bytes), "sha256": sha(service_bytes),
        },
        "gap_before_service_bytes": service_start - delivered_end,
        "delivery_shortfall_through_service_end": service_end - delivered_end,
        "descriptor_roles_covering_full_service": len(covering),
        "exact_service_bytes_present": {
            "bank2_static_role": False,
            "resident_PRG": False,
            "raw_D81_supplemental_only": False,
        },
        "service_payload_delivered": False,
        "violated_contract": (
            "append native far-service bytes to the canonical Bank-2 static "
            "artifact before media staging"),
    }


def caller_facts(truth: ElfTruth) -> dict[str, Any]:
    stack_hex = literal_assignment(DEVICE_DRIVER, "STACK_HEX")
    stack = bytes.fromhex(stack_hex)
    require(len(stack) == 256 and stack[0xD1:0xD5] == bytes.fromhex("b803bb2e"),
            "surviving Page-1 caller bytes drift")
    intern = truth.symbol("intern")
    nameoff = truth.symbol("nameoff_get")
    require((intern.value, nameoff.value) == (0x2DFF, 0x3143),
            "intern/nameoff identity drift")
    intern_bytes = truth.section_bytes(intern.section)
    base = truth.section(intern.section).address
    require(intern_bytes[0x2EB9 - base:0x2EBC - base]
            == bytes.fromhex("204331"),
            "intern to nameoff_get call edge drift")
    symbol_source = SYMBOL.read_text(encoding="utf-8")
    eval_source = EVAL.read_text(encoding="utf-8")
    require("if (sympool_streq(NOFF(i), name))" in symbol_source
            and "mem_init();" in eval_source,
            "boot intern source context drift")
    return {
        "active_reader": "nameoff_get",
        "active_reader_entry": "0x3143",
        "caller": "intern",
        "caller_edge": "JSR $3143 at $2EB9; normal continuation $2EBC",
        "surviving_stack": {
            "$01D1-$01D2": "saved nameoff_get rc20/rc21 = $03B8",
            "$01D3-$01D4": "JSR return word $2EBB => continuation $2EBC",
        },
        "boot_context": (
            "eval_init after mem_init, in intern's length-prefiltered existing-"
            "symbol comparison"),
        "exact_symbol_or_index": "not captured",
        "freelist_cell_read": False,
    }


def device_consistency() -> dict[str, Any]:
    device = load(DEVICE)
    state = device["device"]["physical_state"]
    require(device["status"] == (
        "D1-HEAP-RED; MAPPED-FAR-RETURN-INSTRUCTION-IDENTITY-CONTRADICTION")
        and device["device"]["mapping"]["captured"]["MAPL"] == "0x2480"
        and state["convergence-state"]["raw_hex"] == "00" * 66
        and state["ownership-and-convergence-zp"]["raw_hex"].startswith("02"),
        "device contradiction authority drift")
    return {
        "captured_MAPL": "0x2480",
        "required_normal_return_MAPL": "0x0000",
        "descriptor_state_all_zero": True,
        "verify_done_observed": "0x02",
        "verify_done_protocol_values": {"CLEAR": "0x5A", "COMMITTED": "0xA5"},
        "verify_done_is_stage_encoding": False,
        "first_linked_source_probe_would_write": [
            "c2_dma_verify_list[0]=0x04", "c2_dma_verify_done=0x5A"],
        "interpretation": (
            "the captured $02 is invalid residue, not proof that the linked "
            "service was mid-operation; the linked descriptor writes never occurred"),
    }


def validate(value: dict[str, Any]) -> None:
    exits = value["linked_exit_enumeration"]
    delivery = value["delivery_extent"]
    caller = value["caller_context"]
    device = value["device_consistency"]
    disposition = value["disposition"]
    require(exits["terminal_exit_count"] == 8
            and exits["legitimate_exit_without_unmap"] is False
            and exits["common_return_instruction"] == "JMP $B3D5"
            and exits["unmap_result"] == "MAPL=0x0000",
            "linked exit enumeration no longer closes")
    require(delivery["service_payload_delivered"] is False
            and delivery["descriptor_roles_covering_full_service"] == 0
            and delivery["gap_before_service_bytes"] == 1239
            and delivery["linked_far_service"]["bytes"] == 874,
            "missing far-service delivery is not proved")
    require(caller["active_reader"] == "nameoff_get"
            and caller["caller"] == "intern"
            and caller["freelist_cell_read"] is False,
            "caller context overclaim")
    require(device["descriptor_state_all_zero"] is True
            and device["verify_done_is_stage_encoding"] is False,
            "invalid $02 promoted to a service stage")
    require(value["mechanism"] == "MAPPED-FAR-SERVICE-PAYLOAD-UNDELIVERED"
            and value["root_cause_named"] is True,
            "mechanism not named")
    require(disposition == {"fix_authorized": False, "card_authorized": False,
                            "device_contact_authorized": False,
                            "D2_D5_open": False},
            "attribution widened into implementation or contact")


def derive() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    contract = load(CONTRACT)
    require(contract["mapped_far_service"]["bootstrap"]["service_packaging"]
            == "append native far-service bytes to the canonical Bank-2 static "
               "artifact before media staging",
            "bootstrap packaging contract drift")
    value = {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "PASS: mapped far return mechanism named at delivery extent",
        "mechanism": "MAPPED-FAR-SERVICE-PAYLOAD-UNDELIVERED",
        "root_cause_named": True,
        "linked_exit_enumeration": linked_exit_facts(truth),
        "delivery_extent": delivery_facts(truth),
        "caller_context": caller_facts(truth),
        "device_consistency": device_consistency(),
        "claim_limit": (
            "Host/ELF/media attribution only. The exact target bytes that occupied "
            "$02B8B2-$02BC1B were not captured, so their accidental control path is "
            "not reconstructed. No fix, card, device contact, D2-D5 or release claim."),
        "disposition": {"fix_authorized": False, "card_authorized": False,
                        "device_contact_authorized": False, "D2_D5_open": False},
        "next": (
            "owner disposition over regular-pipeline delivery of the exact linked "
            "far-service LMA range plus a media-closure extent/identity gate"),
        "authorities": {
            "owner_commission": git_bind(COMMISSION_COMMIT, PLAN),
            "device_result": bind(DEVICE),
            "device_result_driver": bind(DEVICE_DRIVER),
            "media_closure": bind(MEDIA),
            "media_manifest": bind(MANIFEST),
            "product_D81": bind(PRODUCT_D81),
            "candidate_ELF": bind(ELF),
            "resident_PRG": bind(PRG),
            "bank2_static_role": bind(BANK2),
            "mapped_far_contract": bind(CONTRACT),
            "facade_source": bind(FACADE),
            "far_body_source": bind(BODY),
            "symbol_source": bind(SYMBOL),
            "eval_source": bind(EVAL),
            "driver": bind(DRIVER),
        },
    }
    validate(value)
    return value


def mutations(value: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, Any] = {}
    for address in ("0x79D3", "0x79DB", "0x7A32", "0x7A38"):
        mutated = deepcopy(value)
        mutated["linked_exit_enumeration"]["entries"]["vm_code_load"][
            "terminal_RTS"].remove(address)
        mutated["linked_exit_enumeration"]["terminal_exit_count"] -= 1
        cases[f"omit-vm-exit-{address}"] = mutated
    for address in ("0x7BB1", "0x7BB9", "0x7C18", "0x7C1B"):
        mutated = deepcopy(value)
        mutated["linked_exit_enumeration"]["entries"]["physical_read"][
            "terminal_RTS"].remove(address)
        mutated["linked_exit_enumeration"]["terminal_exit_count"] -= 1
        cases[f"omit-physical-exit-{address}"] = mutated
    missing_unmap = deepcopy(value)
    missing_unmap["linked_exit_enumeration"]["legitimate_exit_without_unmap"] = True
    cases["permit-linked-exit-without-unmap"] = missing_unmap
    delivered = deepcopy(value)
    delivered["delivery_extent"]["service_payload_delivered"] = True
    cases["source-presence-is-delivery"] = delivered
    covering = deepcopy(value)
    covering["delivery_extent"]["descriptor_roles_covering_full_service"] = 1
    cases["invent-covering-media-role"] = covering
    active = deepcopy(value)
    active["device_consistency"]["verify_done_is_stage_encoding"] = True
    cases["promote-invalid-02-to-stage"] = active
    heap = deepcopy(value)
    heap["caller_context"]["freelist_cell_read"] = True
    cases["rename-intern-read-as-freelist-read"] = heap
    for key in ("fix_authorized", "card_authorized",
                "device_contact_authorized", "D2_D5_open"):
        mutated = deepcopy(value)
        mutated["disposition"][key] = True
        cases[f"preauthorize-{key}"] = mutated
    rejected: dict[str, str] = {}
    for name, candidate in cases.items():
        try:
            validate(candidate)
        except AttributionError as error:
            rejected[name] = str(error)
        else:
            raise AttributionError(f"attribution mutation survived: {name}")
    return rejected


def build() -> dict[str, Any]:
    value = derive()
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    return value


def check() -> dict[str, Any]:
    expected = derive()
    recorded = load(RECEIPT)
    rejected = recorded.pop("mutations_rejected", None)
    require(recorded == expected, "mapped-far attribution receipt stale")
    require(rejected == mutations(expected), "attribution mutation receipt drift")
    return expected


def selftest() -> None:
    value = derive()
    rejected = mutations(value)
    require(len(rejected) == 17, "attribution mutation count drift")
    print("v2.0 mapped-far return attribution: SELFTEST PASS "
          "exits=8 delivery=0/874 mutations=17")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check", "selftest"))
    args = parser.parse_args()
    try:
        if args.action == "build":
            value = build()
            print("v2.0 mapped-far return attribution: PASS "
                  f"mechanism={value['mechanism']} exits=8 delivery=0/874")
        elif args.action == "check":
            value = check()
            print("v2.0 mapped-far return attribution: CHECK PASS "
                  f"mechanism={value['mechanism']}")
        else:
            selftest()
        return 0
    except (AttributionError, KeyError, ValueError, OSError,
            subprocess.SubprocessError) as error:
        print(f"v2.0 mapped-far return attribution: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
