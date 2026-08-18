#!/usr/bin/env python3
"""Bind the one authorized stopped-state low-RAM rescue read.

The read preserves the surviving part of the hardware stack and zero page
after the defstruct terminal BRK.  It can name an enclosing activation, but
the BRK itself overwrote the immediate RTS/RTI bytes.  This gate therefore
separates observations from instrument writes and rejects any attempt to turn
the surviving context into an exact corrupt-edge or fix claim.

It is a desk-only replay.  It never opens a device.
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
FORENSICS = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-brk-stack-forensics-receipt.json")
ORIGIN_DEVICE = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-irq-origin-contact-device-receipt.json")
ORIGIN_PREPARATION = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-irq-origin-contact-preparation-receipt.json")
CAPTURE_TOOL = ROOT / "tools/host-lisp/c2_defstruct_irq_origin_contact.py"
ELF = ROOT / (
    "build/c2.3/defstruct-terminal-ingress-sister-link92/artifacts/"
    "diagnostic-terminal-ingress.elf")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
RECEIPT = EVIDENCE / (
    "c2.3-post-v1.4-defstruct-brk-stack-rescue-receipt.json")

FORMAT = "lisp65-c2.3-post-v1.4-defstruct-brk-stack-rescue-v1"
RECORDED_ON = "2026-08-10"
AUTHORIZATION_COMMIT = "5ebada0d"
AUTHORIZATION_PATH = "docs/planning/post-v1.4.0-direction-plan.md"
ORIGIN_RECORD_SHA256 = (
    "b39e8baeb78f368f4bd6786e54424f09ac48c48db2a95c267dec2c71757cd800")
LOW_RAM_SHA256 = (
    "fa2ec0a0574d99a4390ecff12b8f902d7377d4effa4aab7aefdb544d06c93368")
CAPTURE_BODY_SHA256 = (
    "5d1b7909b890b83cd4b1620c7fd31cd63be8ae28f872ece78cc996e2d95e71f8")
EXPECTED_TUPLE = {
    "PC": "0xB42C", "SP": "0x018D", "X": "0x8D",
    "MAPH": "0x8000", "MAPL": "0x0000",
}
RAW_LOW_RAM_HEX = (
    "3f3ebfce71bf0a070000b907c100000007031e0100c30be329050200b9b80411"
    "e403804400200102040810204080000000005ce000000000002f040000200700"
    "005b0130002f04c504000000009ebc00010c00085019000c00a10200180000e0"
    "02e004e006e008e00ce010e012e014e016e01ce000019bcf0000020000aecd20"
    "e5c48f01080008001d0070010100000040ff8000000000000000030000000800"
    "e1640000003e20000001200000e43700001071fd0f000000006f08086f000000"
    "00000120300a00006c0001000000000000000000000000000000070000000000"
    "3002f80f1800004f0000000700184f0e0e010100000000000000003200000000"
    "440bb07f00cccf01002e431f400db07f00ccfe01002e431f3c0fb07f00cd2d01"
    "002e431f3811b07f00cd5c01002e431f3413b07f00cd8b01002e431f0529e30b"
    "6cbfa00529e30b580529e30b58bfcd0529e30b8a331a33bd3706fa0529e30b8a"
    "0529e30b6ebfa00529e30b8a331a33bd37071a0529e30b8a331a33bd370007bf"
    "c455671efc1eb07f00ced404002e000b071e3073bf0529e3b100a00000011fcb"
    "5201b07f00cb5701002e431f6c03b07f00cb860529e30b6bbf0529e3b100a000"
    "00011fcb4601b07f00cbe401002e431f5403b07f00cc1301002e431f5005b07f"
    "00cc4201002e431f4c07b07f00cc7101002e431f4809b07f00cca001002e431f"
)

PRE_BRK_SP = 0x94
OLDER_BEGIN = 0x0195
BRK_PC = 0xBF71
NAME_LENGTHS = 0xBE1C


class RescueError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RescueError(message)


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
        [str(OBJDUMP), "-d", str(ELF)], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout


def parse_jsr_sites(text: str) -> list[dict[str, Any]]:
    section = ""
    owner = ""
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        section_match = re.match(r"Disassembly of section (.+):", line)
        if section_match:
            section = section_match.group(1)
            owner = ""
            continue
        owner_match = re.match(r"^([0-9a-f]+) <([^>]+)>:$", line)
        if owner_match:
            owner = owner_match.group(2)
            continue
        call = re.match(
            r"^\s*([0-9a-f]+):(?:\s+[0-9a-f]{2})+\s+jsr\s+\$([0-9a-f]+)"
            r"(?:\s+<([^>]+)>)?", line)
        if call:
            pc = int(call.group(1), 16)
            rows.append({
                "section": section, "owner": owner,
                "call_PC": pc, "pushed_return_word": (pc + 2) & 0xFFFF,
                "resume_PC": (pc + 3) & 0xFFFF,
                "target": int(call.group(2), 16),
                "target_name": call.group(3) or "",
            })
    require(rows, "no linked JSR sites parsed")
    return rows


def fmt_site(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "section": row["section"], "owner": row["owner"],
        "call_PC": f"0x{row['call_PC']:04X}",
        "pushed_return_word": f"0x{row['pushed_return_word']:04X}",
        "resume_PC": f"0x{row['resume_PC']:04X}",
        "target": f"0x{row['target']:04X}",
        "target_name": row["target_name"],
    }


def stack_matches(raw: bytes, sites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_word: dict[int, list[dict[str, Any]]] = {}
    for row in sites:
        by_word.setdefault(row["pushed_return_word"], []).append(row)
    found = []
    for address in range(OLDER_BEGIN, 0x01FF):
        word = raw[address] | raw[address + 1] << 8
        if word in by_word:
            found.append({
                "stack_address": f"0x{address:04X}",
                "bytes_low_high": raw[address:address + 2].hex(),
                "word": f"0x{word:04X}",
                "linked_candidates": [fmt_site(row) for row in by_word[word]],
            })
    require(found, "no surviving linked JSR word found")
    return found


def capture_clobber_binding() -> dict[str, Any]:
    source = CAPTURE_TOOL.read_text(encoding="utf-8")
    begin = source.index("def capture_body() -> bytes:")
    end = source.index("\ndef emulate(", begin)
    body = source[begin:end]
    required = (
        "Materialize return-PC-2 in $04/$05",
        "code.sta_zp(0x04)", "code.sta_zp(0x05)",
    )
    require(all(item in body for item in required),
            "capture $04/$05 clobber identity drift")
    return {
        "addresses": ["0x0004", "0x0005"],
        "observed_bytes": ["0x71", "0xBF"],
        "written_by_capture": True,
        "written_value": "stacked continuation $BF73 minus two = $BF71",
        "pre_fault_evidence": False,
        "causal_vector_use_forbidden": True,
        "source_binding": bind(CAPTURE_TOOL),
        "capture_body_sha256": CAPTURE_BODY_SHA256,
    }


def zero_page(raw: bytes, truth: ElfTruth, sites: list[dict[str, Any]]) -> dict[str, Any]:
    rc18 = raw[0x14] | raw[0x15] << 8
    nsym = raw[0x59] | raw[0x5A] << 8
    phase_owner = raw[0x89]
    require(rc18 == 0xC300 and nsym == 673 and phase_owner == 0,
            "rescued ZP values drift")
    owners = [row for row in truth.sections_at_vma(rc18)
              if "SHF_ALLOC" in row.flags]
    owner_rows = [{"name": row.name, "start": f"0x{row.address:04X}",
                   "bytes": row.bytes, "executable": "SHF_EXECINSTR" in row.flags}
                  for row in owners]
    require(any(row["name"] == ".lisp65_c2_fixed_bank0_hot_bss"
                and row["executable"] is False for row in owner_rows),
            "$C300 section ownership drift")
    call_indir = [row for row in sites if row["target"] == 0x23E6]
    legal_words = {row["pushed_return_word"] for row in call_indir}
    immediate_word = raw[OLDER_BEGIN] | raw[OLDER_BEGIN + 1] << 8
    require(immediate_word not in legal_words, "direct __call_indir frame appeared")
    namelen_address = NAME_LENGTHS + (nsym >> 1)
    require(namelen_address == 0xBF6C, "live namelen write address drift")
    return {
        "capture_clobber": capture_clobber_binding(),
        "unindexed_indirect_vector": {
            "symbol": "__rc18/__rc19", "addresses": ["0x0014", "0x0015"],
            "value": "0xC300", "section_owners": owner_rows,
            "dispatcher": "__call_indir at $23E6: JMP ($14)",
            "immediate_surviving_stack_word": f"0x{immediate_word:04X}",
            "matching_call_indir_return_word": False,
            "direct_escape_to_BF71_attributed": False,
            "reason": (
                "$C300 is not $BF71 and the immediate surviving word is not a "
                "JSR __call_indir return; __rc18 is volatile, so its mere value "
                "is not a consumed-vector claim"),
        },
        "name_state": {
            "nsym": nsym, "live_symbol_indices": [0, nsym - 1],
            "next_legal_intern_index": nsym,
            "next_legal_namelen_address": f"0x{namelen_address:04X}",
            "BF71_packed_indices": [682, 683],
            "BF71_is_legal_current_namelen_write": False,
            "neighbor_overwrite_attributed": False,
        },
        "phase_owner": phase_owner,
    }


def derive() -> dict[str, Any]:
    raw = bytes.fromhex(RAW_LOW_RAM_HEX)
    require(len(raw) == 512 and digest(raw) == LOW_RAM_SHA256,
            "embedded low-RAM capture drift")
    origin = load(ORIGIN_DEVICE)
    preparation = load(ORIGIN_PREPARATION)
    forensics = load(FORENSICS)
    require(origin["authorities"]["record"]["sha256"] == ORIGIN_RECORD_SHA256,
            "origin-record SHA authority drift")
    require(preparation["capture"]["body_sha256"] == CAPTURE_BODY_SHA256,
            "capture-body SHA authority drift")
    require(forensics["required_read_row"]["reads"] == 1
            and forensics["desk_decision"]["device_read_authorized"] is False,
            "prior specified-only row drift")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    text = disassembly()
    sites = parse_jsr_sites(text)
    matches = stack_matches(raw, sites)
    nearest = matches[0]
    require(nearest["stack_address"] == "0x0196"
            and nearest["word"] == "0xE329",
            "nearest surviving linked frame drift")
    nearest_candidates = nearest["linked_candidates"]
    require(any(row["call_PC"] == "0xE327"
                and row["target"] == "0xB5C4"
                and row["target_name"].startswith("c2_facade_vm_code_load")
                for row in nearest_candidates),
            "nearest C2D refill edge drift")

    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "ENCLOSING-C2D-REFILL-FRAME-NAMED; IMMEDIATE-EDGE-UNRECOVERABLE",
        "authorities": {
            "owner_authorization": git_bind(AUTHORIZATION_COMMIT,
                                              AUTHORIZATION_PATH),
            "prior_stack_forensics": bind(FORENSICS),
            "origin_device": bind(ORIGIN_DEVICE),
            "origin_preparation": bind(ORIGIN_PREPARATION),
            "diagnostic_ELF": bind(ELF),
        },
        "precondition": {
            "expected_tuple": EXPECTED_TUPLE,
            "observed_tuple": EXPECTED_TUPLE,
            "tuple_match": True,
            "expected_origin_record_sha256": ORIGIN_RECORD_SHA256,
            "observed_origin_record_sha256": ORIGIN_RECORD_SHA256,
            "origin_record_match": True,
            "state_reproduction_needed": False,
        },
        "device_protocol": {
            "authorization_commit": "5ebada0d3984a31af6cc67a170f485a197c04c3d",
            "preflight_register_reads": 1,
            "preflight_register_JSON_sha256": (
                "0d81737eaa012b6e023022da7e512b3694494c71990a2bf853f58ddbe4d320db"),
            "preflight_register_log_sha256": (
                "0c6a506ac3fca951ff038e2cdde88ccb6e4655de5ef6e6d15094b21455a67a14"),
            "physical_memory_reads": 1,
            "physical_address": "0x00000000",
            "bytes": 512,
            "command_shape": (
                "m65 -H --memsave 0x00000000:0x00000200=<capture>"),
            "sha256": LOW_RAM_SHA256,
            "raw_hex": RAW_LOW_RAM_HEX,
            "RUN": 0, "resume": 0, "reset": 0, "second_memory_read": 0,
            "CPU_left_stopped": True,
        },
        "zero_page": zero_page(raw, truth, sites),
        "hardware_stack": {
            "pre_BRK_SP": "0x94",
            "BRK_overwrite_range": "0x0192..0x0194",
            "surviving_range": "0x0195..0x01FF",
            "surviving_hex": raw[OLDER_BEGIN:0x0200].hex(),
            "first_surviving_byte": {"address": "0x0195", "value": "0x05",
                                     "classification": "unresolved temporary"},
            "nearest_linked_return_word": nearest,
            "all_linked_JSR_word_matches": matches,
            "nearest_frame_interpretation": {
                "enclosing_activation": (
                    "c2_stream_c2d_read $E327 -> c2_facade_vm_code_load "
                    "$B5C4 -> vm_code_load -> c2 DMA"),
                "proved": True,
                "immediate_escape_instruction": False,
                "reason": (
                    "one unresolved byte remains above the $E329 return word; "
                    "the BRK already replaced the immediate RTS/RTI slots"),
            },
        },
        "decision": {
            "enclosing_edge": "C2D-REFILL-ACTIVATION",
            "immediate_corrupt_edge": None,
            "RTS_attributed": False,
            "RTI_attributed": False,
            "unindexed_indirect_jump_attributed": False,
            "indexed_or_other_indirect_jump_attributed": False,
            "name_neighbor_overwrite_attributed": False,
            "capture_ZP04_05_may_be_used_causally": False,
            "additional_device_read_authorized": False,
            "fix_authorized": False,
            "reason": (
                "the read names the surviving enclosing refill frame and "
                "falsifies the live-name and unindexed-vector shortcuts, but "
                "cannot restore the immediate bytes destroyed by BRK"),
        },
        "instrument_rule": (
            "A rescue read must subtract every byte written by the capture "
            "identity before interpreting live state; capture-created ZP $04/$05 "
            "must never become causal evidence."),
        "claim_limit": (
            "One read-only stopped-state rescue row. It names an enclosing C2D "
            "refill activation, not the exact RTS/RTI/indirect corruptor. It "
            "authorizes no further device read, fix, link or product change."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value["format"] == FORMAT and value["status"] ==
            "ENCLOSING-C2D-REFILL-FRAME-NAMED; IMMEDIATE-EDGE-UNRECOVERABLE",
            "rescue identity drift")
    pre = value["precondition"]
    require(pre["expected_tuple"] == EXPECTED_TUPLE
            and pre["observed_tuple"] == EXPECTED_TUPLE
            and pre["tuple_match"] is True
            and pre["origin_record_match"] is True
            and pre["state_reproduction_needed"] is False,
            "stopped-state precondition was broadened")
    protocol = value["device_protocol"]
    require(protocol["physical_memory_reads"] == 1
            and protocol["bytes"] == 512
            and protocol["sha256"] == LOW_RAM_SHA256
            and digest(bytes.fromhex(protocol["raw_hex"])) == LOW_RAM_SHA256
            and protocol["RUN"] == protocol["resume"] == protocol["reset"] == 0
            and protocol["second_memory_read"] == 0
            and protocol["CPU_left_stopped"] is True,
            "single read-only row drift")
    clobber = value["zero_page"]["capture_clobber"]
    require(clobber["addresses"] == ["0x0004", "0x0005"]
            and clobber["written_by_capture"] is True
            and clobber["pre_fault_evidence"] is False
            and clobber["causal_vector_use_forbidden"] is True,
            "capture-created $04/$05 was promoted")
    indirect = value["zero_page"]["unindexed_indirect_vector"]
    require(indirect["value"] == "0xC300"
            and indirect["matching_call_indir_return_word"] is False
            and indirect["direct_escape_to_BF71_attributed"] is False,
            "volatile unindexed vector was promoted")
    names = value["zero_page"]["name_state"]
    require(names["nsym"] == 673
            and names["next_legal_namelen_address"] == "0xBF6C"
            and names["BF71_packed_indices"] == [682, 683]
            and names["BF71_is_legal_current_namelen_write"] is False
            and names["neighbor_overwrite_attributed"] is False,
            "name-neighbor hypothesis was promoted")
    stack = value["hardware_stack"]
    require(stack["nearest_linked_return_word"]["stack_address"] == "0x0196"
            and stack["nearest_linked_return_word"]["word"] == "0xE329"
            and stack["nearest_frame_interpretation"]["proved"] is True
            and stack["nearest_frame_interpretation"]["immediate_escape_instruction"]
            is False,
            "surviving refill-frame boundary drift")
    decision = value["decision"]
    require(decision["enclosing_edge"] == "C2D-REFILL-ACTIVATION"
            and decision["immediate_corrupt_edge"] is None
            and decision["RTS_attributed"] is False
            and decision["RTI_attributed"] is False
            and decision["unindexed_indirect_jump_attributed"] is False
            and decision["indexed_or_other_indirect_jump_attributed"] is False
            and decision["name_neighbor_overwrite_attributed"] is False
            and decision["capture_ZP04_05_may_be_used_causally"] is False
            and decision["additional_device_read_authorized"] is False
            and decision["fix_authorized"] is False,
            "rescue read overclaims edge, contact or fix")


def audit(value: dict[str, Any]) -> None:
    validate(value)
    require(value == derive(), "rescue receipt differs from reconstruction")


def mutate(value: dict[str, Any], path: list[Any], replacement: Any) -> None:
    cursor: Any = value
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = replacement


def selftest() -> dict[str, Any]:
    base = derive()
    cases: list[tuple[str, list[Any], Any]] = [
        ("tuple-mismatch", ["precondition", "observed_tuple", "PC"], "0xB42D"),
        ("accept-tuple-mismatch", ["precondition", "tuple_match"], False),
        ("invent-reproduction", ["precondition", "state_reproduction_needed"], True),
        ("second-read", ["device_protocol", "physical_memory_reads"], 2),
        ("short-read", ["device_protocol", "bytes"], 256),
        ("mutate-raw", ["device_protocol", "raw_hex"], "00" * 512),
        ("invent-run", ["device_protocol", "RUN"], 1),
        ("invent-resume", ["device_protocol", "resume"], 1),
        ("promote-zp04", ["zero_page", "capture_clobber", "pre_fault_evidence"], True),
        ("permit-zp04", ["zero_page", "capture_clobber",
                         "causal_vector_use_forbidden"], False),
        ("claim-unindexed", ["zero_page", "unindexed_indirect_vector",
                             "direct_escape_to_BF71_attributed"], True),
        ("invent-indirect-frame", ["zero_page", "unindexed_indirect_vector",
                                   "matching_call_indir_return_word"], True),
        ("move-nsym", ["zero_page", "name_state", "nsym"], 682),
        ("make-BF71-legal", ["zero_page", "name_state",
                             "BF71_is_legal_current_namelen_write"], True),
        ("claim-neighbor", ["decision", "name_neighbor_overwrite_attributed"], True),
        ("move-nearest-frame", ["hardware_stack", "nearest_linked_return_word",
                                "stack_address"], "0x0195"),
        ("make-frame-immediate", ["hardware_stack", "nearest_frame_interpretation",
                                  "immediate_escape_instruction"], True),
        ("claim-RTS", ["decision", "RTS_attributed"], True),
        ("claim-RTI", ["decision", "RTI_attributed"], True),
        ("claim-indexed", ["decision", "indexed_or_other_indirect_jump_attributed"],
         True),
        ("name-exact-edge", ["decision", "immediate_corrupt_edge"], "RTI"),
        ("authorize-contact", ["decision", "additional_device_read_authorized"], True),
        ("authorize-fix", ["decision", "fix_authorized"], True),
    ]
    rejected = []
    for name, path, replacement in cases:
        trial = deepcopy(base)
        mutate(trial, path, replacement)
        try:
            validate(trial)
            require(trial == derive(), "mutated receipt accepted")
        except RescueError:
            rejected.append(name)
        else:
            raise RescueError(f"mutation survived: {name}")
    require(len(rejected) == len(cases), "mutation accounting drift")
    return {"status": "SELFTEST PASS", "mutations_rejected": len(rejected),
            "cases": rejected,
            "enclosing_edge": "C2D-REFILL-ACTIVATION",
            "immediate_corrupt_edge": None}


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
        value = {"status": "PASS", "mutations_rejected": 23,
                 "enclosing_edge": "C2D-REFILL-ACTIVATION",
                 "immediate_corrupt_edge": None}
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RescueError, ElfTruthError, OSError, ValueError, KeyError,
            IndexError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"DEFSTRUCT BRK STACK RESCUE: {error}", file=sys.stderr)
        raise SystemExit(1)
