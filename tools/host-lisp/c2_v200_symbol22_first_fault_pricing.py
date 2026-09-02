#!/usr/bin/env python3
"""Price the v2.0 `$22` first-fault latch against the v1.9 release.

This is a host-only pricing and instrument-law gate.  It compiles a target
assembly micro-object, but never invokes the product WPLTO/link, media tools,
or a device.  The proposed helper replaces only the already failing `$22`
call edge; the successful ``intern`` path remains an implementation-time
byte-identity obligation on the final ELF.
"""

from __future__ import annotations

import copy
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
from evidence_era import era_bind, era_blob  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
ATTRIBUTION = ROOT / "docs/planning/v1.7.0-block3-left-first-red-attribution.md"
HOST_REPLAY = ROOT / "docs/planning/v1.8.0-block1-symbol22-host-reproduction.md"
REPORT = ROOT / "docs/planning/v2.0.0-symbol22-first-fault-pricing-report.md"
RECEIPT = ARCH / "c2.3-v2.0-symbol22-first-fault-pricing-receipt.json"
ELF = ROOT / (
    "build/c2.3/v1.9.0-release-card-r1/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
PRG = ROOT / (
    "build/c2.3/v1.9.0-release-card-r1/wplto/"
    "lisp65-c2-substitution-linked.prg")
SYMBOL_SOURCE = ROOT / "src/symbol.c"
REPL_SOURCE = ROOT / "src/repl.c"
TERMINAL_GUARD_SOURCE = ROOT / "src/c2_product_runtime.c"
BUILD = ROOT / "build/phase0-symbol22-first-fault-pricing"
ASM = BUILD / "symbol22-first-fault-latch.s"
OBJ = BUILD / "symbol22-first-fault-latch.o"
ALIAS_C = BUILD / "repl-buffer-alias.c"
ALIAS_O = BUILD / "repl-buffer-alias.o"
ALIAS_PRG = BUILD / "repl-buffer-alias.prg"
ALIAS_ELF = Path(str(ALIAS_PRG) + ".elf")
RETURN_C = BUILD / "return-address-probe.c"
CC = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
PLAN_COMMIT = "3606904fc64daf867d16a110fb679dc0f10f6c64"
SEAL_ERA = "1eafd616ed631c34ed7e12fd5edbf18fba538f5a"
FORMAT = "lisp65-c2.3-v200-symbol22-first-fault-pricing-v1"
STATUS = "PASS: FIRST-FAULT LATCH PRICED; PRODUCT CARD REQUIRED"
RECORDED_ON = "2026-08-31"
SECTION = ".lisp65_symbol22_first_fault_latch"
TAG = 0xA5
ERROR = 0x22
PAYLOAD_BYTES = 34


ASM_SOURCE = '''\
\t.section .lisp65_symbol22_first_fault_latch,"ax",@progbits
\t.globl lisp65_symbol22_latch_state
\t.globl lisp65_symbol22_latch_and_abort
\t.globl c2_symbol22_repl_buf
\t.globl lisp_abort_code

\t.type lisp65_symbol22_latch_state,@object
lisp65_symbol22_latch_state:
\t.byte 0, 0, 0, 0, 0
\t.size lisp65_symbol22_latch_state, .-lisp65_symbol22_latch_state

\t.type lisp65_symbol22_latch_and_abort,@function
lisp65_symbol22_latch_and_abort:
\tlda lisp65_symbol22_latch_state
\tbne .Llatch_abort
\ttsx
\tlda $0107,x
\tsta lisp65_symbol22_latch_state+1
\tlda $0108,x
\tsta lisp65_symbol22_latch_state+2
\tlda $16
\tsta lisp65_symbol22_latch_state+3
\tlda $17
\tsta lisp65_symbol22_latch_state+4
\tldy #0
.Llatch_copy:
\tlda ($16),y
\tsta c2_symbol22_repl_buf,y
\tbeq .Llatch_commit
\tiny
\tcpy #$22
\tbne .Llatch_copy
.Llatch_commit:
\tlda #$a5
\tsta lisp65_symbol22_latch_state
.Llatch_abort:
\tlda #$22
\tjmp lisp_abort_code
\t.size lisp65_symbol22_latch_and_abort, .-lisp65_symbol22_latch_and_abort
'''


ALIAS_SOURCE = r'''\
#include <stdint.h>

void repl(void) {
    static char buf[192] __attribute__((used));
    buf[191] = 0;
}

__asm__(".globl c2_symbol22_repl_buf\n"
        ".set c2_symbol22_repl_buf, repl.buf\n");
extern char c2_symbol22_repl_buf[];

void lisp_abort_code(uint8_t code) { c2_symbol22_repl_buf[191] = (char)code; }
int main(void) { repl(); return 0; }
'''


RETURN_SOURCE = r'''\
void *probe_return_address(void) { return __builtin_return_address(0); }
int main(void) { return probe_return_address() != 0; }
'''


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


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
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(argv: list[str], label: str) -> str:
    result = subprocess.run(argv, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def write_build_inputs() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    ASM.write_text(ASM_SOURCE, encoding="utf-8")
    ALIAS_C.write_text(ALIAS_SOURCE, encoding="utf-8")
    RETURN_C.write_text(RETURN_SOURCE, encoding="utf-8")


def parse_instructions(text: str, start: int, end: int) -> dict[int, tuple[str, str]]:
    pattern = re.compile(r"^\s*([0-9a-fA-F]+):\s+\t([a-z][a-z0-9]*)\s*(.*)$")
    rows: dict[int, tuple[str, str]] = {}
    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            address = int(match.group(1), 16)
            if start <= address < end:
                operand = match.group(3).split(";", 1)[0].strip()
                rows[address] = (match.group(2).lower(), operand)
    require(rows, "instruction range empty")
    return rows


def branch_target(operand: str) -> int | None:
    match = re.search(r"\$([0-9a-fA-F]+)", operand)
    return int(match.group(1), 16) if match else None


def stack_depths_at(rows: dict[int, tuple[str, str]], entry: int,
                    target: int) -> list[int]:
    addresses = sorted(rows)
    successor = {address: addresses[index + 1]
                 for index, address in enumerate(addresses[:-1])}
    conditional = {"beq", "bne", "bcc", "bcs", "bmi", "bpl", "bvc", "bvs"}
    pushes = {"pha", "phx", "phy"}
    pulls = {"pla", "plx", "ply"}
    pending = [(entry, 0)]
    visited: set[tuple[int, int]] = set()
    found: set[int] = set()
    while pending:
        address, depth = pending.pop()
        if (address, depth) in visited:
            continue
        visited.add((address, depth))
        require(-1 <= depth <= 32, "unbounded or invalid stack-depth walk")
        if address == target:
            found.add(depth)
            continue
        mnemonic, operand = rows[address]
        after = depth + (1 if mnemonic in pushes else -1 if mnemonic in pulls else 0)
        next_addresses: list[int] = []
        if mnemonic in conditional:
            destination = branch_target(operand)
            if destination in rows:
                next_addresses.append(destination)
            if address in successor:
                next_addresses.append(successor[address])
        elif mnemonic in {"bra", "jmp"}:
            destination = branch_target(operand)
            if destination in rows:
                next_addresses.append(destination)
        elif mnemonic not in {"rts", "rti", "brk"} and address in successor:
            next_addresses.append(successor[address])
        pending.extend((next_address, after) for next_address in next_addresses)
    require(found, "fault edge unreachable in stack-depth model")
    return sorted(found)


def release_world() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    handoff = truth.section(".lisp65_c2_kernal_handoff")
    facade = truth.section(".lisp65_c2_host_facade")
    gap_start = handoff.address + handoff.bytes
    gap_end = facade.address
    gap_bytes = gap_end - gap_start
    owners = []
    for section in truth.sections:
        if section.bytes <= 0 or "SHF_ALLOC" not in section.flags:
            continue
        lo, hi = section.address, section.address + section.bytes
        if max(lo, gap_start) < min(hi, gap_end):
            owners.append(section.name)
    require((gap_start, gap_end, gap_bytes) == (0xB582, 0xB5C4, 66),
            "candidate-derived handoff/facade gap drift")
    require(not owners, f"owner-free gap already occupied: {owners}")
    raw = PRG.read_bytes()
    load_address = int.from_bytes(raw[:2], "little")
    gap_payload = raw[2 + gap_start - load_address:2 + gap_end - load_address]
    require(len(gap_payload) == gap_bytes and gap_payload == bytes(gap_bytes),
            "packed release gap is not 66 initialized zero bytes")
    repl = truth.symbol("repl.buf")
    nsym = truth.symbol("nsym")
    npool = truth.symbol("npool")
    scratch = truth.symbol("sym_name_scratch")
    require(repl.bytes == 192 and scratch.bytes == PAYLOAD_BYTES,
            "release scratch geometry drift")
    source = TERMINAL_GUARD_SOURCE.read_text(encoding="utf-8")
    require("$B582..$B591" in source and "LISP65_C2_TERMINAL_RETURN_GUARD" in source,
            "historical diagnostic-gap claimant drift")
    return {
        "ELF": bind(ELF), "PRG": bind(PRG),
        "derived_gap": {"start": gap_start, "end_exclusive": gap_end,
                        "bytes": gap_bytes, "active_owners": owners,
                        "packed_initial_value": "00" * gap_bytes},
        "scratch": {"repl.buf": {"address": repl.value, "bytes": repl.bytes},
                    "sym_name_scratch": {"address": scratch.value,
                                         "bytes": scratch.bytes},
                    "nsym": {"address": nsym.value, "bytes": nsym.bytes},
                    "npool": {"address": npool.value, "bytes": npool.bytes}},
        "conflict_rule": {
            "historical_claimant": "LISP65_C2_TERMINAL_RETURN_GUARD",
            "active_in_release": False,
            "requirement": ("the composed final ELF permits exactly one gap owner; "
                            "retaining the latch requires future repricing")},
    }


def predecessor_abi() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    intern = truth.symbol("intern")
    text = run([str(OBJDUMP), "-d", "--no-show-raw-insn", str(ELF)],
               "release intern disassembly")
    rows = parse_instructions(text, intern.value, intern.value + intern.bytes)
    ordered = sorted(rows)
    fault_calls = []
    for index, address in enumerate(ordered):
        mnemonic, operand = rows[address]
        if mnemonic == "jsr" and "<lisp_abort_code>" in operand and index:
            prior = rows[ordered[index - 1]]
            if prior == ("lda", "#$22"):
                fault_calls.append(address)
    require(len(fault_calls) == 1, f"expected one emitted $22 fault edge: {fault_calls}")
    fault_call = fault_calls[0]
    depths = stack_depths_at(rows, intern.value, fault_call)
    require(depths == [4], f"intern hardware-frame depth drift: {depths}")
    pointer_setup = [("ldx", "$4"), ("stx", "$16"),
                     ("ldx", "$5"), ("stx", "$17")]
    sequence = [rows[address] for address in ordered]
    start = next((index for index in range(len(sequence) - 3)
                  if sequence[index:index + 4] == pointer_setup), None)
    require(start is not None, "intern input pointer is not materialized in rc20/rc21")
    setup_end_address = ordered[start + 3]
    forbidden = {"sta", "stx", "sty", "stz"}
    clobbers = [(address, rows[address]) for address in ordered
                if setup_end_address < address < fault_call
                and rows[address][0] in forbidden
                and rows[address][1] in {"$16", "$17"}]
    require(not clobbers, f"intern name pointer clobbered before $22 edge: {clobbers}")
    require(any(address < fault_call and rows[address] == ("lda", "($16),y")
                for address in ordered),
            "failure predicate does not consume the retained name pointer")
    low_offset = depths[0] + 3
    high_offset = depths[0] + 4
    require((low_offset, high_offset) == (7, 8), "derived caller offsets drift")
    return {
        "intern": {"address": intern.value, "bytes": intern.bytes,
                   "section": intern.section},
        "fault_call": {"address": fault_call, "target": "lisp_abort_code",
                       "predecessor": "lda #$22"},
        "hardware_stack": {"persistent_frame_bytes": depths[0],
                           "helper_return_bytes": 2,
                           "caller_return_low_offset_from_post_jsr_sp": low_offset,
                           "caller_return_high_offset_from_post_jsr_sp": high_offset,
                           "all_reaching_depths": depths},
        "name_pointer": {"argument_pair": ["__rc2", "__rc3"],
                         "retained_pair": ["__rc20", "__rc21"],
                         "setup_end_address": setup_end_address,
                         "clobbers_before_fault": clobbers,
                         "consumed_by_failure_scan": True},
    }


def compile_candidate() -> dict[str, Any]:
    write_build_inputs()
    run([str(CC), "-c", "-mcpu=mos45gs02", str(ASM), "-o", str(OBJ)],
        "target latch assembly")
    truth = ElfTruth.read(OBJ, llvm_readobj=READOBJ)
    section = truth.section(SECTION)
    state = truth.symbol("lisp65_symbol22_latch_state")
    helper = truth.symbol("lisp65_symbol22_latch_and_abort")
    require((section.bytes, state.bytes, helper.bytes) == (57, 5, 52),
            "target micro-object size drift")
    targets = sorted({row.target for row in truth.relocations})
    require(set(targets) == {"c2_symbol22_repl_buf", "lisp65_symbol22_latch_state",
                             "lisp_abort_code"},
            f"unexpected target-micro relocations: {targets}")
    disassembly = run([str(OBJDUMP), "-dr", str(OBJ)], "target latch disassembly")
    for token in ("lda\t$107,x", "lda\t$108,x", "lda\t$16",
                  "lda\t($16),y", "cpy\t#$22", "lda\t#$a5", "lda\t#$22",
                  "R_MOS_ADDR16\tc2_symbol22_repl_buf",
                  "R_MOS_ADDR16\tlisp_abort_code"):
        require(token in disassembly, f"target latch instruction absent: {token}")
    commit_load = disassembly.index("lda\t#$a5")
    copy_store = disassembly.index("R_MOS_ADDR16\tc2_symbol22_repl_buf")
    abort_load = disassembly.index("lda\t#$22")
    require(copy_store < commit_load < abort_load, "tag-last/abort ordering drift")
    return {
        "section": SECTION, "bytes": section.bytes,
        "state_bytes": state.bytes, "helper_bytes": helper.bytes,
        "gap_residual_bytes": 66 - section.bytes,
        "relocation_targets": targets,
        "state_layout": ["commit_tag", "caller_JSR_return_low",
                         "caller_JSR_return_high",
                         "name_pointer_low", "name_pointer_high"],
        "payload": {"owner": "repl.buf", "offset": 0,
                    "bytes": PAYLOAD_BYTES,
                    "copy_rule": "through first NUL or 34 bytes, whichever comes first"},
        "commit": {"initial": 0, "committed": TAG, "written_last": True,
                   "subsequent_fault_overwrites": False},
        "abort": {"error": ERROR, "tail_target": "lisp_abort_code"},
        "object": bind(OBJ),
    }


def alias_probe() -> dict[str, Any]:
    run([str(CC), "-c", "-Os", "-mcpu=mos45gs02", "-flto", str(ALIAS_C),
         "-o", str(ALIAS_O)], "repl-buffer alias compile")
    run([str(CC), "-Os", "-mcpu=mos45gs02", "-flto", str(ALIAS_O), str(OBJ),
         "-o", str(ALIAS_PRG)], "repl-buffer alias link")
    truth = ElfTruth.read(ALIAS_ELF, llvm_readobj=READOBJ)
    local = truth.symbol("repl.buf")
    alias = truth.symbol("c2_symbol22_repl_buf")
    bss = truth.section(".bss")
    require(local.value == alias.value and local.bytes == alias.bytes == 192,
            "repl.buf alias has a distinct address or size")
    require(bss.bytes == 192, "alias micro allocated additional BSS")
    return {"local_symbol": "repl.buf", "alias_symbol": alias.name,
            "address_identical": True, "bytes": alias.bytes,
            "total_bss_bytes": bss.bytes, "additional_allocation_bytes": 0,
            "micro_ELF": bind(ALIAS_ELF)}


def rejected_builtin_probe() -> dict[str, Any]:
    return_object = BUILD / "return-address-probe.o"
    compile_result = subprocess.run(
        [str(CC), "-c", "-Os", "-mcpu=mos45gs02", str(RETURN_C), "-o",
         str(return_object)], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(compile_result.returncode == 0,
            f"return-address IR probe did not compile:\n{compile_result.stdout}")
    result = subprocess.run(
        [str(CC), "-Os", "-mcpu=mos45gs02", str(return_object), "-o",
         str(BUILD / "return-address-probe.prg")], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = result.stdout
    require(result.returncode != 0 and "llvm.returnaddress" in output
            and "unable to legalize instruction" in output,
            "return-address builtin unexpectedly became a valid target mechanism")
    return {"candidate": "__builtin_return_address(0)", "selected": False,
            "compiler_exit": result.returncode,
            "reason": "MOS backend cannot legalize llvm.returnaddress",
            "output_sha256": sha(output.encode())}


def instrument_model() -> dict[str, Any]:
    def fire(state: list[int], payload: list[int], caller: int, pointer: int,
             name: bytes) -> tuple[list[int], list[int], list[str]]:
        result_state = list(state)
        result_payload = list(payload)
        trace: list[str] = []
        if result_state[0] != TAG:
            result_state[1:5] = [caller & 0xff, caller >> 8,
                                 pointer & 0xff, pointer >> 8]
            trace.append("state-with-tag-zero")
            for index in range(PAYLOAD_BYTES):
                byte = name[index] if index < len(name) else 0
                result_payload[index] = byte
                trace.append(f"payload[{index}]")
                if byte == 0:
                    break
            result_state[0] = TAG
            trace.append("commit-tag")
        trace.append("abort-22")
        return result_state, result_payload, trace

    empty_state = [0] * 5
    empty_payload = [0] * PAYLOAD_BYTES
    first = fire(empty_state, empty_payload, 0x4567, 0x89AB,
                 b"abcdefghijklmnopqrstuvwxyzabcdefgh")
    second = fire(first[0], first[1], 0x1111, 0x2222, b"different\0")
    short = fire(empty_state, empty_payload, 0x1234, 0x5678, b"abc\0poison")
    require(first[0] == [TAG, 0x67, 0x45, 0xAB, 0x89]
            and bytes(first[1]) == b"abcdefghijklmnopqrstuvwxyzabcdefgh",
            "unterminated 34-byte model capture drift")
    require(second[0] == first[0] and second[1] == first[1],
            "second fault overwrote first-fault evidence")
    require(bytes(short[1][:4]) == b"abc\0" and short[2][-2:] == [
        "commit-tag", "abort-22"], "NUL-bounded capture or tag order drift")
    return {"atomic_origin": "five zero bytes materialized in the packed image",
            "first_fault_state": first[0], "first_fault_payload_sha256":
                sha(bytes(first[1])),
            "second_fault_preserves_first": True,
            "short_name_stops_at_NUL": True,
            "commit_is_last_evidence_write": True,
            "every_path_ends_at_error": ERROR}


def validate(value: dict[str, Any]) -> None:
    release = value["release_world"]
    candidate = value["candidate"]
    abi = value["predecessor_abi"]
    law = value["instrument_law"]
    rejected = value["rejected_candidate"]
    require(release["derived_gap"]["bytes"] == 66
            and release["derived_gap"]["active_owners"] == [],
            "candidate gap is not owner-free")
    require(candidate["bytes"] == 57 and candidate["gap_residual_bytes"] == 9,
            "candidate does not fit the derived gap")
    require(candidate["state_bytes"] == 5 and candidate["helper_bytes"] == 52,
            "candidate component size drift")
    require(abi["hardware_stack"]["all_reaching_depths"] == [4]
            and abi["hardware_stack"]["caller_return_low_offset_from_post_jsr_sp"] == 7
            and abi["hardware_stack"]["caller_return_high_offset_from_post_jsr_sp"] == 8,
            "caller capture is not derived from the final predecessor")
    require(abi["name_pointer"]["retained_pair"] == ["__rc20", "__rc21"]
            and not abi["name_pointer"]["clobbers_before_fault"],
            "fault name pointer is not live at the seam")
    require(candidate["payload"]["bytes"] == 34
            and candidate["commit"]["written_last"]
            and not candidate["commit"]["subsequent_fault_overwrites"],
            "first-fault atomicity/capture drift")
    require(value["alias_probe"]["address_identical"]
            and value["alias_probe"]["additional_allocation_bytes"] == 0,
            "scratch alias is not zero-allocation")
    require(rejected["selected"] is False
            and "cannot legalize" in rejected["reason"],
            "unsupported return-address route selected")
    require(law["successful_path_final_ELF_byte_identity"] == "mandatory-card-gate"
            and law["diagnostic_removal_default"] is True
            and law["ordinary_text_floor_may_not_move"] is True,
            "instrument-law boundary weakened")
    require(release["conflict_rule"]["requirement"].startswith(
        "the composed final ELF permits exactly one gap owner"),
        "shared-gap ownership conflict was hidden")
    require(value["verification"] == {"WPLTO_runs": 0, "product_links": 0,
                                      "media_builds": 0, "device_contacts": 0,
                                      "product_sources_changed": 0},
            "pricing crossed its host-only claim")


def mutations(value: dict[str, Any]) -> list[str]:
    cases = {
        "section-overflows-derived-gap": lambda x: x["candidate"].update(bytes=67),
        "caller-low-offset-is-guessed": lambda x: x["predecessor_abi"][
            "hardware_stack"].update(caller_return_low_offset_from_post_jsr_sp=6),
        "name-pointer-pair-is-not-live": lambda x: x["predecessor_abi"][
            "name_pointer"].update(clobbers_before_fault=[[0x3200, ["stx", "$16"]]]),
        "payload-captures-only-33-bytes": lambda x: x["candidate"][
            "payload"].update(bytes=33),
        "commit-precedes-payload": lambda x: x["candidate"][
            "commit"].update(written_last=False),
        "second-fault-overwrites-first": lambda x: x["candidate"][
            "commit"].update(subsequent_fault_overwrites=True),
        "scratch-alias-allocates-state": lambda x: x["alias_probe"].update(
            additional_allocation_bytes=1),
        "builtin-return-address-selected": lambda x: x["rejected_candidate"].update(
            selected=True),
        "successful-path-byte-gate-removed": lambda x: x["instrument_law"].update(
            successful_path_final_ELF_byte_identity="assumed"),
        "second-gap-owner-admitted": lambda x: x["release_world"][
            "derived_gap"].update(active_owners=["historical-progress-ring"]),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        changed = copy.deepcopy(value)
        mutate(changed)
        try:
            validate(changed)
        except PricingError:
            rejected.append(name)
    require(rejected == list(cases), "first-fault pricing mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    release = release_world()
    abi = predecessor_abi()
    candidate = compile_candidate()
    alias = alias_probe()
    rejected = rejected_builtin_probe()
    model = instrument_model()
    source = era_blob(SEAL_ERA,
        SYMBOL_SOURCE.relative_to(ROOT).as_posix()).decode()
    repl_source = era_blob(SEAL_ERA,
        REPL_SOURCE.relative_to(ROOT).as_posix()).decode()
    require("static obj new_symbol(const char *name)" in source
            and "lisp_abort_static(LISP65_ERR_TOO_MANY_SYMBOLS" in source,
            "source fault seam drift")
    require(repl_source.count("static char buf[BUF_MAX];") == 1,
            "repl.buf owner seam drift")
    value = {
        "format": FORMAT, "recorded_on": RECORDED_ON, "status": STATUS,
        "authority": {"phase0_plan": git_bind(PLAN_COMMIT, PLAN),
                      "first_red_attribution": era_bind(SEAL_ERA, ATTRIBUTION),
                      "target_faithful_nonreproduction": era_bind(
                          SEAL_ERA, HOST_REPLAY)},
        "inputs": {"symbol_source": era_bind(SEAL_ERA, SYMBOL_SOURCE),
                   "repl_source": era_bind(SEAL_ERA, REPL_SOURCE),
                   "terminal_guard_source": era_bind(
                       SEAL_ERA, TERMINAL_GUARD_SOURCE),
                   "pricing_driver": era_bind(
                       SEAL_ERA, Path(__file__).resolve())},
        "historical_question": {
            "error": ERROR, "exclusive_writer": "new_symbol()",
            "missing_fact": "dynamic C name pointer and caller at first fault",
            "host_replay": ("positive control raises $22; complete 198-CALLPRIM "
                            "mixed-world replay does not reproduce")},
        "release_world": release,
        "predecessor_abi": abi,
        "candidate": candidate,
        "alias_probe": alias,
        "rejected_candidate": rejected,
        "instrument_model": model,
        "instrument_law": {
            "bound_atomic_origin": "packed tag byte is zero; tag A5 commits last",
            "successful_path_source_change": "none outside the existing $22 edge",
            "successful_path_final_ELF_byte_identity": "mandatory-card-gate",
            "failure_path": "capture then existing lisp_abort_code($22)",
            "ordinary_text_projection_bytes": -2,
            "ordinary_text_floor_may_not_move": True,
            "diagnostic_removal_default": True,
            "retention_requires_owner_argument": True,
            "read_choreography": ("on recurrence, type nothing further; stop and read "
                                  "five latch bytes plus repl.buf[0..33], nsym and npool")},
        "implementation_card": {
            "required": True, "projected_product_links": 1,
            "product_WPLTO_authorized_by_pricing": False,
            "mandatory_final_ELF_gates": [
                "candidate section fits wholly in the derived B582..B5C4 gap",
                "the composed owner map admits no second claimant of that gap",
                "all paths reaching the helper have one derived hardware-stack depth",
                "the emitted helper offsets equal depth+3/depth+4",
                "the dynamic name pointer is live in the emitted ABI pair at the helper edge",
                "repl.buf alias is address-identical and allocates zero bytes",
                "copy ends at first NUL or byte 34 and commit tag is written last",
                "the packed PRG initializes the five state bytes to zero",
                "the successful intern path is byte-identical to the predecessor ELF",
                "the ordinary-text floor and every standing composition gate remain green"],
            "device_contact_authority": "owner only after product-card review"},
        "verification": {"WPLTO_runs": 0, "product_links": 0,
                         "media_builds": 0, "device_contacts": 0,
                         "product_sources_changed": 0},
        "claim_limit": ("Host pricing of one bounded first-fault instrument. No product "
                        "implementation, final-LTO byte claim, media, device contact, "
                        "Comfort reopening, or Block-3 reopening."),
    }
    validate(value)
    value["verification"]["mutations_rejected"] = mutations(value)
    return value


def report(value: dict[str, Any]) -> str:
    gap = value["release_world"]["derived_gap"]
    candidate = value["candidate"]
    abi = value["predecessor_abi"]
    return f'''# v2.0 Phase 0 — `$22` first-fault latch pricing

Recorded: {RECORDED_ON}
Receipt: `c2.3-v2.0-symbol22-first-fault-pricing-receipt.json`

## Outcome

The first-fault latch has one exact host-priced form.  It occupies **{candidate['bytes']}
bytes** in the candidate-derived, owner-free `$B582..$B5C4` interval
({gap['bytes']} bytes), leaving **{candidate['gap_residual_bytes']} bytes**.  It adds no
BSS, no public name and no ordinary successful-path work.  A product card and
one final link are still required; this pricing authorizes neither.

The earlier wrapper design is rejected.  The current final ELF already leaves
the dynamic caller under the `intern` frame at the fault edge.  All paths to
the sole emitted `$22` call carry exactly
{abi['hardware_stack']['persistent_frame_bytes']} saved bytes, so after the helper's JSR the
caller return word is derived at stack offsets +{abi['hardware_stack']['caller_return_low_offset_from_post_jsr_sp']}/+{abi['hardware_stack']['caller_return_high_offset_from_post_jsr_sp']}.
Reading it only on the existing failure edge is both smaller and stronger:
the successful `intern` path can remain byte-for-byte unchanged.

## Exact freight

| Component | Bytes |
|---|---:|
| Atomic state (`tag`, caller, name pointer) | {candidate['state_bytes']} |
| Fault-only capture-and-abort helper | {candidate['helper_bytes']} |
| **Total** | **{candidate['bytes']}** |
| Derived gap | {gap['bytes']} |
| **Residual** | **{candidate['gap_residual_bytes']}** |

The target micro-object is compiled with the pinned MOS toolchain.  Its helper
records the caller's hardware JSR return pair (the resume address minus one)
and the passed C pointer, copies through the
first NUL or at most 34 bytes into the existing 192-byte `repl.buf`, writes
commit tag `$A5` **last**, then tail-jumps to the existing
`lisp_abort_code($22)`.  A second `$22` cannot overwrite the first record.
The `repl.buf` alias is address-identical and adds zero allocation.  On a
recurrence the contact must stop before any further input and read the five
state bytes, `repl.buf[0..33]`, `nsym` and `npool`.

The copy's NUL stop matters: `$22` also represents table/pool exhaustion.  A
short valid name is never read for 34 bytes merely because capacity failed;
an unterminated/overlong name still yields the full discriminating 34 bytes.

## ABI and rejected alternative

The release ELF materializes the input pointer from `__rc2/__rc3` into
`__rc20/__rc21`, does not clobber that pair before the fault edge, and consumes
it in the failing scan.  These are predecessor facts, not permission to pin
the ABI: the implementation card must derive and re-prove the pair and stack
depth from its own final ELF.

`__builtin_return_address(0)` is not a viable smaller C form.  The pinned MOS
backend cannot legalize `llvm.returnaddress`; the failed compiler probe is
recorded as a rejected candidate rather than silently replaced by an
architecture guess.

## Instrument law and product-card boundary

The five state bytes start as zero in the packed image.  Caller, pointer and
payload are written while the tag remains zero; `$A5` is the atomic commit.
The existing successful path is not instrumented.  The projected call-site
change is five bytes (`LDA #$22; JSR abort`) to a three-byte helper call, but
that **−2-byte text value is only a projection**: final LTO must prove success-
path byte identity and may not spend the 32-byte ordinary-text floor.

The gap has an inactive historical claimant, the terminal-return diagnostic.
The composed final-ELF gate therefore permits exactly one owner.  If the latch
is retained after diagnosis rather than removed, future use of this interval
must be repriced; removal remains the default.

Ten sharp mutations fall, including guessed stack offsets, 33-byte capture,
tag-first commit, second-fault overwrite, an allocating alias, a second gap
owner and removal of the final-ELF neutrality gate.

No product source, WPLTO, product link, medium or device was touched.  The next
touchpoint is review of this price and authorization of the product card; the
device contact remains owner-only after that card is green.
'''


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    require(action in {"record", "check", "selftest"},
            "usage: record|check|selftest")
    value = derive()
    if action == "record":
        RECEIPT.write_bytes(canonical(value))
        REPORT.write_text(report(value), encoding="utf-8")
    elif action == "check":
        require(load(RECEIPT) == value, "first-fault pricing receipt stale")
        require(REPORT.read_text(encoding="utf-8") == report(value),
                "first-fault pricing report stale")
    else:
        require(len(value["verification"]["mutations_rejected"]) == 10,
                "first-fault pricing mutation count drift")
    print("v2.0 symbol22 first-fault pricing: PASS bytes=57 gap=66 residual=9 "
          "WPLTO=0 link=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PricingError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"v2.0 symbol22 first-fault pricing: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
