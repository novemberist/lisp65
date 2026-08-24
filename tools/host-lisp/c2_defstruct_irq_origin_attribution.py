#!/usr/bin/env python3
"""Bind the defstruct source-less IRQ origin as far as desk evidence permits.

The terminal-ingress record contains an IRQ-stack return PC, not an execution
sample.  This gate binds that value to the exact Link-92 diagnostic sibling,
the captured MAP state, the strict interrupt-ownership cut and the tested-core
BRK/IRQ stack semantics.  It deliberately stops at the one missing bit that
separates software BRK ingress from a hardware IRQ: stacked processor status
bit B.  The output specifies one terminal-only CPU-side capture row that also
closes the remaining non-VIC source register gap.

No device is accessed and no product or diagnostic artifact is modified.
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
import c2_interrupt_ownership_gate as IRQ  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RESULT = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-terminal-ingress-result-receipt.json")
DEVICE = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-terminal-ingress-device-receipt.json")
SISTER = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-terminal-ingress-sister-receipt.json")
POLICY = ROOT / "config/c2-interrupt-ownership-policy.json"
MAP_SOURCE = ROOT / "src/c2_kernal_map.s"
RUNTIME = ROOT / "src/c2_kernal_runtime.c"
WINDOW = ROOT / "src/c2_kernal_window.s"
PHASE_C = ROOT / "tools/host-lisp/c2_v16_defstruct_phase_c.py"
CONTROL_ELF = ROOT / (
    "build/c2.3/defstruct-terminal-ingress-sister-link92/artifacts/"
    "control-link92-r5.elf")
DIAGNOSTIC_ELF = ROOT / (
    "build/c2.3/defstruct-terminal-ingress-sister-link92/artifacts/"
    "diagnostic-terminal-ingress.elf")
DIAGNOSTIC_PRG = ROOT / (
    "build/c2.3/defstruct-terminal-ingress-sister-link92/artifacts/"
    "diagnostic-terminal-ingress.prg")
RECEIPT = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-irq-origin-desk-attribution-receipt.json")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"

FORMAT = "lisp65-c2.3-post-v1.4-defstruct-irq-origin-desk-attribution-v1"
RECORDED_ON = "2026-08-10"
AUTHORIZATION_COMMIT = "abf8140c"
AUTHORIZATION_PATH = "docs/planning/post-v1.4.0-direction-plan.md"
RETURN_PC = 0xBF73
BRK_CANDIDATE_PC = RETURN_PC - 2
PRG_LOAD = 0x2001
TESTED_CORE_COMMIT = "03b24c6b9d0e456f762fdca0d2dd66ec3c3e1fc6"
TESTED_CORE_FILE_SHA = "d44ae3906e1b0a826ca8e511c73ef1f50223b7de507a3ed349082fdefe58034e"
CORE_BASE = (
    "https://github.com/MEGA65/mega65-core/blob/"
    f"{TESTED_CORE_COMMIT}/src/vhdl/gs4510.vhdl")


class OriginError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise OriginError(message)


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


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(canonical(value))
    temporary.replace(path)


def git_bind(commit: str, path: str) -> dict[str, Any]:
    raw = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, check=True).stdout.strip()
    return {"authority": "git-blob", "commit": full, "path": path,
            "bytes": len(raw), "sha256": digest(raw)}


def historical_bind(path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION_COMMIT}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    return {"path": name, "bytes": len(raw), "sha256": digest(raw)}


def disassembly(elf: Path) -> str:
    return subprocess.run(
        [str(OBJDUMP), "-d", "--no-show-raw-insn", str(elf)],
        cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=True).stdout


def direct_mmio_rows(text: str, address: int) -> list[dict[str, Any]]:
    pattern = re.compile(
        rf"^\s*([0-9a-f]+):\s+([a-z0-9]+)\s+\${address:04x}\b",
        re.MULTILINE)
    return [{"pc": f"0x{int(pc, 16):04x}", "opcode": opcode}
            for pc, opcode in pattern.findall(text)]


def core_authority(policy: dict[str, Any]) -> dict[str, Any]:
    tested = policy["authorities"]["tested_core_sources"]
    require(tested["commit"] == TESTED_CORE_COMMIT,
            "tested-core commit drift")
    require(tested["files"]["gs4510.vhdl"] == TESTED_CORE_FILE_SHA,
            "tested-core CPU source SHA drift")
    return {
        "repository": tested["repository"],
        "commit": TESTED_CORE_COMMIT,
        "file": "src/vhdl/gs4510.vhdl",
        "sha256": TESTED_CORE_FILE_SHA,
        "opcode_00_is_BRK": CORE_BASE + "#L1031-L1034",
        "hardware_IRQ_clears_stacked_B": CORE_BASE + "#L5468-L5488",
        "hardware_IRQ_preserves_resume_PC": CORE_BASE + "#L6680-L6689",
        "BRK_advances_over_opcode_and_signature_byte":
            CORE_BASE + "#L6714-L6760",
        "BRK_enters_interrupt_state": CORE_BASE + "#L8370-L8379",
        "stack_push_order_PCH_PCL_P": CORE_BASE + "#L9418-L9436",
        "semantic_result": (
            "hardware IRQ stacks B=0 and the resume PC; BRK stacks B=1 "
            "and the PC two bytes after opcode $00"),
    }


def artifact_pc_binding(truth: ElfTruth, sister: dict[str, Any],
                        result: dict[str, Any]) -> dict[str, Any]:
    require(result["I"]["interrupted_return_PC"] == RETURN_PC,
            "captured return PC drift")
    owners = [row for row in truth.sections_at_vma(RETURN_PC)
              if "SHF_ALLOC" in row.flags]
    require(len(owners) == 1 and owners[0].name == ".bss",
            "return PC no longer has unique BSS ownership")
    bss = owners[0]
    require("SHF_EXECINSTR" not in bss.flags
            and bss.section_type == "SHT_NOBITS",
            "return-PC section unexpectedly executable or initialized")
    nlen = truth.symbol("namelen4")
    require(nlen.section == ".bss" and nlen.value <= RETURN_PC
            < nlen.value + nlen.bytes and nlen.bytes == 0x178,
            "return PC no longer lies in namelen4")
    function_owners = [row for row in truth.sized_intervals()
                       if row.start <= RETURN_PC < row.end_exclusive]
    require(not function_owners, "return PC unexpectedly acquired a function owner")
    requires = [row for row in truth.relocations
                if truth.relocation_target_identity(row)["resolved_value"]
                == RETURN_PC]
    require(not requires, "return PC unexpectedly acquired a relocation edge")
    require(sister["identity"]["diagnostic_ELF"]["sha256"]
            == bind(DIAGNOSTIC_ELF)["sha256"],
            "diagnostic ELF differs from sister authority")
    prg = DIAGNOSTIC_PRG.read_bytes()
    at = 2 + BRK_CANDIDATE_PC - PRG_LOAD
    require(prg[at:at + 4] == bytes(4),
            "linked BSS initialization around return PC drift")
    return {
        "raw_stack_value": "$BF73",
        "meaning": "interrupted return PC; not an execution sample",
        "captured_mapping": {"MAPH": "$8000", "MAPL": "$0000"},
        "mapping_effect": (
            "only CPU block 7 ($E000-$FFFF) is remapped; $BF73 remains "
            "ordinary Bank-0 RAM"),
        "section": {"name": bss.name, "start": f"0x{bss.address:04x}",
                    "bytes": bss.bytes, "type": bss.section_type,
                    "executable": False},
        "object": {"name": nlen.name, "start": f"0x{nlen.value:04x}",
                   "bytes": nlen.bytes, "offset": RETURN_PC - nlen.value,
                   "symbol_indices_encoded": [
                       2 * (RETURN_PC - nlen.value),
                       2 * (RETURN_PC - nlen.value) + 1]},
        "function_owner": None,
        "relocation_edges_to_value": len(requires),
        "interrupt_window_seam": False,
        "linked_initial_bytes_BF71_BF74": prg[at:at + 4].hex(),
        "runtime_bytes_known": False,
        "runtime_note": (
            "namelen4 is populated after boot; linked zero initialization is "
            "not a live-byte oracle"),
    }


def map_and_stack_contract(device: dict[str, Any]) -> dict[str, Any]:
    registers = device["register_tuple"]
    require(registers["MAPH"].lower() == "0x8000"
            and registers["MAPL"].lower() == "0x0000",
            "captured mapping tuple drift")
    map_source = MAP_SOURCE.read_text(encoding="utf-8")
    phase_c = PHASE_C.read_text(encoding="utf-8")
    require("Own only block 7 ($e000-$ffff)" in map_source
            and "ldz #$80\n\tmap\n\teom" in map_source,
            "block-7-only MAP contract drift")
    require("code.lda_stack_x(6)" in phase_c
            and "code.lda_stack_x(7)" in phase_c
            and "code.lda_stack_x(5)" not in phase_c,
            "terminal IRQ stack capture shape drift")
    window_disassembly = disassembly(DIAGNOSTIC_ELF)
    handler = re.search(
        r"<c2_kernal_irq_handler>:(.*?)(?=\n[0-9a-f]{8} <)",
        window_disassembly, re.DOTALL)
    require(handler is not None and not re.search(r"^\s*[0-9a-f]+:\s+map\b",
                                                  handler.group(1), re.MULTILINE),
            "IRQ/fail path changes mapping after stack capture")
    return {
        "capture_stack_rule": (
            "after hardware frame plus PHA/PHX/PHY/PHZ, TSX-relative "
            "$0105,X=P, $0106,X=PCL, $0107,X=PCH"),
        "captured_fields": ["$0106,X", "$0107,X"],
        "missing_discriminator": "$0105,X stacked processor status bit B",
        "mapping_stable_through_terminal_path": True,
    }


def ownership_binding(policy: dict[str, Any]) -> dict[str, Any]:
    runtime = RUNTIME.read_text(encoding="utf-8")
    text = disassembly(DIAGNOSTIC_ELF)
    exact = IRQ.audit(elf=DIAGNOSTIC_ELF)
    require(exact["status"] == "passed-strict-internal-interrupt-ownership",
            "exact sister interrupt-ownership gate is not green")
    expected = {
        "$DC0D": (0xDC0D, ["stx", "ldy"]),
        "$DD0D": (0xDD0D, ["stx", "ldx", "lda"]),
        "$D6E1": (0xD6E1, ["stz", "ldx"]),
        "$D697": (0xD697, ["stx", "lda"]),
        "$D713": (0xD713, ["stz", "lda"]),
    }
    rows: dict[str, list[dict[str, Any]]] = {}
    for name, (address, opcodes) in expected.items():
        found = direct_mmio_rows(text, address)
        require([row["opcode"] for row in found] == opcodes,
                f"exact MMIO edge set drift: {name}: {found}")
        rows[name] = found
    require(runtime.count("CIA1_ICR = 0x7fu; (void)CIA1_ICR;") == 1
            and runtime.count("CIA2_ICR = 0x7fu; (void)CIA2_ICR;") == 1,
            "CIA ownership source drift")
    inventory = {row["id"]: row for row in policy["inventory"]}
    require(inventory["cia1"]["vector"] == "IRQ"
            and inventory["cia2"]["vector"] == "NMI"
            and inventory["brk"]["vector"] == "IRQ vector ingress",
            "IRQ/NMI/BRK inventory classification drift")
    return {
        "exact_artifact_gate": {
            "status": exact["status"],
            "elf": exact["final_ELF"]["elf"],
            "mutations": exact["mutations"],
        },
        "direct_MMIO_edges": rows,
        "desk_exclusions": {
            "VIC": "captured $D019=0 with raster-only enablement",
            "CIA1_inherited_enable": (
                "$DC0D receives $7F and is read under SEI; exact product "
                "contains no later direct mask write"),
            "CIA2_as_IRQ": "CIA2 routes to NMI, not IRQ",
            "ethernet_autoIEC_audioDMA_inherited_enable": (
                "all three are disabled and read back before window publish/CLI"),
            "board_IRQ": "structurally inactive on the bound R6 core",
            "F011_and_ordinary_DMA": "no edge into the bound IRQ cone",
        },
        "not_target_excluded": [
            "BRK software ingress or wild execution",
            "Freezer/hypervisor deferred IRQ replay",
            "interrupt-generating cartridge outside the supported profile",
            "target-only source-state corruption or restoration after ownership",
        ],
        "CIA_registers_present_in_current_capture": False,
        "stacked_status_present_in_current_capture": False,
        "live_resume_neighborhood_present_in_current_capture": False,
    }


def capture_row() -> dict[str, Any]:
    return {
        "name": "terminal-source-less-IRQ-origin",
        "authorization": "not-authorized-by-this-desk-result",
        "contacts": 1,
        "product_bytes_changed": 0,
        "identity": "non-promotable diagnostic sibling only",
        "timing": (
            "capture at the already-terminal second source-less entry, before "
            "the hold loop; CPU remains stopped after the sole postcondition read"),
        "mapping_rule": (
            "capture MAPH/MAPL first; code bytes use CPU view, ordinary RAM "
            "uses physical translation, I/O uses a CPU-side read"),
        "fields": [
            {"name": "stacked-P", "source": "$0105,X", "bytes": 1,
             "rule": "tag raw before any later X change; bit 4 is B"},
            {"name": "stacked-return-PC", "source": "$0106,X/$0107,X",
             "bytes": 2, "rule": "existing field, recaptured in the same row"},
            {"name": "resume-neighborhood", "source": "CPU-view PC-2..PC+1",
             "bytes": 4, "rule": "read once after the tagged PC is known"},
            {"name": "CIA1-ICR", "source": "$DC0D", "bytes": 1,
             "rule": "exactly one terminal-only CPU read; read-to-clear is declared"},
            {"name": "CIA2-ICR", "source": "$DD0D", "bytes": 1,
             "rule": "context only; CIA2 is an NMI source"},
            {"name": "Ethernet-IRQ", "source": "$D6E1", "bytes": 1,
             "rule": "raw enable and sticky status bits"},
            {"name": "AutoIEC-IRQ", "source": "$D697", "bytes": 1,
             "rule": "raw enable and event bits"},
            {"name": "AudioDMA-IRQ", "source": "$D713", "bytes": 1,
             "rule": "raw enable and event bits"},
            {"name": "existing-IRQ-context",
             "source": "$FF86/$FF89/$D01A", "bytes": 3,
             "rule": "latch, D019 witness and D01A recaptured atomically"},
        ],
        "decision_table": {
            "BRK": (
                "stacked B=1 and CPU-view byte at return-PC-2 is $00; "
                "the stacked PC is the BRK continuation, not a routine"),
            "CIA1": (
                "stacked B=0 and CIA1 ICR bit 7 plus at least one source bit "
                "0..4 is set"),
            "internal_peripheral": (
                "stacked B=0 and a corresponding enable/status pair is active "
                "in $D6E1, $D697 or $D713"),
            "deferred_or_external_remainder": (
                "stacked B=0 with all software-readable internal sources clean; "
                "the supported-profile cartridge witness is then required before "
                "calling this Freezer/hypervisor replay"),
            "instrument_red": (
                "missing tag, repeated CIA read, absent mapping tuple, non-CPU "
                "I/O view or live-byte read from linked BSS initialization"),
        },
        "side_effect_boundary": (
            "CIA ICR reads acknowledge flags, so they occur once only after the "
            "guard has already selected its terminal path; no resume follows"),
    }


def derive() -> dict[str, Any]:
    result = load(RESULT)
    device = load(DEVICE)
    sister = load(SISTER)
    policy = load(POLICY)
    require(result["status"] == "I-SOURCELESS-IRQ-TERMINAL-INGRESS"
            and result["decision"]["R_A_I_G"] == "I",
            "I result authority drift")
    require(sister["identity"]["control_ELF"]["path"].endswith(
                "control-link92-r5.elf"),
            "defstruct capture is no longer Link-92-r5 based")
    truth = ElfTruth.read(DIAGNOSTIC_ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    pc = artifact_pc_binding(truth, sister, result)
    stack = map_and_stack_contract(device)
    ownership = ownership_binding(policy)
    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "DESK-EXHAUSTED; ONE-ROW-ORIGIN-CAPTURE-SPECIFIED",
        "authorities": {
            "owner_commission": git_bind(AUTHORIZATION_COMMIT,
                                          AUTHORIZATION_PATH),
            "I_result": bind(RESULT),
            "device_capture": bind(DEVICE),
            "diagnostic_sister": bind(SISTER),
            "interrupt_policy": bind(POLICY),
            "map_source": bind(MAP_SOURCE),
            "runtime_source": bind(RUNTIME),
            "window_source": historical_bind(WINDOW),
            "phase_C_capture_source": bind(PHASE_C),
            "tested_core_CPU": core_authority(policy),
        },
        "code_authority_correction": {
            "commission_wording": "delivered Link-95 image",
            "actual_defstruct_capture_authority": "Link-92-r5 diagnostic sibling",
            "reason": (
                "Link-95 is the separately accepted trace product; the defstruct "
                "sister receipt explicitly derives from Link-92-r5"),
        },
        "return_PC_binding": pc,
        "stack_and_mapping": stack,
        "BRK_hypothesis": {
            "status": "live discriminator missing; not attributed",
            "candidate_opcode_address": f"0x{BRK_CANDIDATE_PC:04x}",
            "candidate_continuation": f"0x{RETURN_PC:04x}",
            "structural_consistency": (
                "the tested core would stack $BF73 for BRK at $BF71"),
            "live_byte_consistency": "unknown",
            "required_discriminator": "stacked P bit B plus live CPU-view byte $BF71",
        },
        "interrupt_ownership": ownership,
        "desk_decision": {
            "named_origin": None,
            "interrupt_window_at_BF73": False,
            "inherited_CIA_timer_or_TOD_attributed": False,
            "reason": (
                "$BF73 is data and the current record omitted stacked B, live "
                "resume bytes and CIA/internal source registers"),
            "next": "exactly one terminal-only CPU-side origin row",
            "device_recontact_authorized": False,
            "fix_authorized": False,
        },
        "required_capture_row": capture_row(),
        "claim_limit": (
            "Host/ELF/RTL attribution only. It corrects $BF73 from a presumed "
            "routine to a stacked return PC inside namelen4 and proves no "
            "interrupt-window seam there. It does not choose BRK, CIA, a "
            "peripheral, Freezer/hypervisor or cartridge origin; authorize a "
            "fix; alter product bytes; or authorize the specified contact."),
    }


def validate_shape(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT and value["status"] ==
            "DESK-EXHAUSTED; ONE-ROW-ORIGIN-CAPTURE-SPECIFIED",
            "origin receipt identity drift")
    pc = value["return_PC_binding"]
    require(pc["raw_stack_value"] == "$BF73" and pc["section"]["name"] == ".bss"
            and pc["object"]["name"] == "namelen4"
            and pc["object"]["offset"] == 343
            and pc["function_owner"] is None
            and pc["interrupt_window_seam"] is False
            and pc["runtime_bytes_known"] is False,
            "return-PC claim broadened")
    stack = value["stack_and_mapping"]
    require(stack["captured_fields"] == ["$0106,X", "$0107,X"]
            and stack["missing_discriminator"]
            == "$0105,X stacked processor status bit B",
            "stack discriminator drift")
    ownership = value["interrupt_ownership"]
    require(ownership["CIA_registers_present_in_current_capture"] is False
            and ownership["stacked_status_present_in_current_capture"] is False
            and ownership["live_resume_neighborhood_present_in_current_capture"]
            is False,
            "missing evidence was silently promoted")
    decision = value["desk_decision"]
    require(decision["named_origin"] is None
            and decision["interrupt_window_at_BF73"] is False
            and decision["inherited_CIA_timer_or_TOD_attributed"] is False
            and decision["device_recontact_authorized"] is False
            and decision["fix_authorized"] is False,
            "desk result overclaims an origin, contact or fix")
    row = value["required_capture_row"]
    require(row["contacts"] == 1 and row["product_bytes_changed"] == 0
            and row["authorization"] == "not-authorized-by-this-desk-result",
            "capture-row boundary drift")
    names = [field["name"] for field in row["fields"]]
    require(names == [
        "stacked-P", "stacked-return-PC", "resume-neighborhood",
        "CIA1-ICR", "CIA2-ICR", "Ethernet-IRQ", "AutoIEC-IRQ",
        "AudioDMA-IRQ", "existing-IRQ-context"],
        "capture-row field closure drift")
    require(set(row["decision_table"]) == {
        "BRK", "CIA1", "internal_peripheral",
        "deferred_or_external_remainder", "instrument_red"},
        "capture-row decision closure drift")


def audit(value: dict[str, Any]) -> None:
    validate_shape(value)
    require(value == derive(), "origin receipt differs from desk reconstruction")


def mutate(value: dict[str, Any], path: list[Any], replacement: Any) -> None:
    cursor: Any = value
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = replacement


def selftest() -> dict[str, Any]:
    base = derive()
    cases: list[tuple[str, list[Any], Any]] = [
        ("claim-BF73-function", ["return_PC_binding", "function_owner"],
         "terminal_publish"),
        ("claim-BF73-executable", ["return_PC_binding", "section", "executable"],
         True),
        ("claim-interrupt-window", ["return_PC_binding", "interrupt_window_seam"],
         True),
        ("treat-linked-zero-as-live", ["return_PC_binding", "runtime_bytes_known"],
         True),
        ("erase-stacked-P-gap", ["stack_and_mapping", "missing_discriminator"],
         "none"),
        ("claim-CIA-captured", ["interrupt_ownership",
                                "CIA_registers_present_in_current_capture"], True),
        ("claim-live-bytes-captured", ["interrupt_ownership",
                                       "live_resume_neighborhood_present_in_current_capture"], True),
        ("claim-BRK-origin", ["desk_decision", "named_origin"], "BRK"),
        ("claim-CIA-origin", ["desk_decision", "named_origin"], "CIA1-TOD"),
        ("claim-CIA-inheritance", ["desk_decision",
                                   "inherited_CIA_timer_or_TOD_attributed"], True),
        ("authorize-contact", ["desk_decision", "device_recontact_authorized"], True),
        ("authorize-fix", ["desk_decision", "fix_authorized"], True),
        ("drop-stacked-P", ["required_capture_row", "fields", 0, "name"],
         "omitted"),
        ("drop-CIA1", ["required_capture_row", "fields", 3, "name"], "omitted"),
        ("drop-live-neighborhood", ["required_capture_row", "fields", 2, "name"],
         "omitted"),
        ("pre-authorize-row", ["required_capture_row", "authorization"],
         "authorized"),
        ("permit-two-contacts", ["required_capture_row", "contacts"], 2),
        ("erase-instrument-red", ["required_capture_row", "decision_table",
                                  "instrument_red"], "accept"),
    ]
    rejected: list[str] = []
    for name, path, replacement in cases:
        trial = deepcopy(base)
        mutate(trial, path, replacement)
        try:
            validate_shape(trial)
            require(trial == derive(), "mutated receipt accepted")
        except OriginError:
            rejected.append(name)
        else:
            raise OriginError(f"mutation survived: {name}")
    require(len(rejected) == len(cases), "mutation accounting drift")
    return {"status": "SELFTEST PASS", "mutations_rejected": len(rejected),
            "cases": rejected, "named_origin": None,
            "next": "one terminal-only CPU-side origin row"}


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
                 "named_origin": None,
                 "next": "one terminal-only CPU-side origin row"}
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OriginError, ElfTruthError, OSError, ValueError, KeyError,
            IndexError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"DEFSTRUCT IRQ ORIGIN ATTRIBUTION: {error}", file=sys.stderr)
        raise SystemExit(1)
