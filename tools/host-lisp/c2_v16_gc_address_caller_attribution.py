#!/usr/bin/env python3
"""Close the v1.6 GC address/caller desk commission.

The consumed contact left the CPU stopped and captured three PCs in
``gc_collect`` together with the mapping state and physical Bank-0 data.
This checker lets the linked instructions and the primary core resolver
decide whether those physical reads targeted the right storage, then narrows
the linked legal entry edge under the captured allocator state.  It never
contacts or resumes the device and changes no product artifact.
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


READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
ELF = ROOT / (
    "build/c2.3/v1.6-defstruct-bootstrap-romc-repair/artifacts/"
    "diagnostic-link82-romc-safe.elf")
DEVICE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mapping-aware-full-ladder-device-receipt.json")
VIEW = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mapping-aware-data-boot-gc-receipt.json")
CONTROL = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-launch-boundary-control-device-receipt.json")
REPAIR = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-bootstrap-romc-repair-receipt.json")
ROM_CONTRACT = ROOT / "config/r3-g3-g6-contract.json"
CORE = ROOT / "build/upstream-verification/mega65-core"
CORE_CPU = CORE / "src/vhdl/gs4510.vhdl"
CORE_MONITOR = CORE / "src/monitor/monitor.a65"
CORE_MACHINE = CORE / "src/vhdl/machine_container.vhdl"
SOURCE = ROOT / "build/c2.3/v1.6-defstruct-phase-c/source/src"
SRC_MEM = SOURCE / "mem.c"
SRC_MAIN = SOURCE / "main.c"
SRC_OVERLAY = SOURCE / "vm_boot_overlay.c"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-gc-address-caller-attribution-receipt.json")
DRIVER = Path(__file__).resolve()

COMMISSION_COMMIT = "9c7276e1"
COMMISSION_PATH = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
CONFIGURED_ROM_SHA = (
    "af3c447f791a2fdc48cb21e1bd3fab015e32641228d9d30d21259b9e878c6fa0")
SAMPLE_PCS = (0x3B19, 0x3B0D, 0x3A8E)
GC = 0x38F7
GC_RUNS = 0xB9F0
ALLOC_EMPTY_CALL = 0x3717


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    resolved = path.resolve()
    try:
        label = resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        label = str(resolved)
    return {"path": label, "bytes": len(raw), "sha256": sha_bytes(raw)}


def git_blob(commit: str, path: str) -> tuple[bytes, dict[str, Any]]:
    process = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(process.returncode == 0, f"git authority absent: {commit}:{path}")
    raw = process.stdout
    return raw, {"authority": "git-blob", "commit": commit, "path": path,
                 "bytes": len(raw), "sha256": sha_bytes(raw)}


def configured_rom() -> Path:
    contract = load(ROM_CONTRACT)
    candidates: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str) and value.endswith("MEGA65.ROM"):
            candidates.append(value)

    walk(contract)
    require(len(set(candidates)) == 1, "one configured MEGA65.ROM required")
    return Path(candidates[0]).expanduser()


def function(source: str, signature: str) -> str:
    start = source.find(signature)
    require(start >= 0, f"function absent: {signature}")
    brace = source.find("{", start)
    require(brace >= 0, f"function body absent: {signature}")
    depth = 0
    for at in range(brace, len(source)):
        if source[at] == "{":
            depth += 1
        elif source[at] == "}":
            depth -= 1
            if depth == 0:
                return source[start:at + 1]
    raise AttributionError(f"unterminated function: {signature}")


def symbol_bytes(truth: ElfTruth, name: str) -> tuple[int, bytes]:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    data = truth.section_bytes(symbol.section)
    offset = symbol.value - section.address
    require(symbol.bytes > 0 and 0 <= offset <= len(data) - symbol.bytes,
            f"symbol outside section: {name}")
    return symbol.value, data[offset:offset + symbol.bytes]


def bytes_at(truth: ElfTruth, section_name: str, address: int,
             count: int) -> bytes:
    section = truth.section(section_name)
    data = truth.section_bytes(section_name)
    offset = address - section.address
    require(0 <= offset <= len(data) - count,
            f"address outside {section_name}: 0x{address:04x}")
    return data[offset:offset + count]


def callsites(data: bytes, base: int, opcode: bytes) -> list[int]:
    return [base + at for at in range(len(data) - len(opcode) + 1)
            if data[at:at + len(opcode)] == opcode]


def monitor_payload(row: dict[str, Any]) -> bytes:
    text = bytes.fromhex(row["raw_hex"]).decode("ascii")
    match = re.search(r":[0-9A-Fa-f]+:([0-9A-Fa-f]{32})", text)
    require(match is not None, "monitor memory line absent")
    return bytes.fromhex(match.group(1))


def exact_facts() -> tuple[dict[str, Any], dict[str, Any]]:
    commission_raw, commission_binding = git_blob(
        COMMISSION_COMMIT, COMMISSION_PATH)
    require(b"Uninitialized-heap contradiction" in commission_raw
            and b"Let the GC's own stores name their targets" in commission_raw,
            "owner desk commission drift")
    device = load(DEVICE)
    view = load(VIEW)
    control = load(CONTROL)
    repair = load(REPAIR)
    require(device["status"] == "TEMPORAL-PROGRESS-WITHOUT-VISIBLE-PROMPT"
            and device["result"] == {
                "CPU_left_stopped": True, "R_A_I_G": None,
                "classification": "TEMPORAL-PROGRESS-WITHOUT-VISIBLE-PROMPT",
                "measured_forms_run": 0},
            "consumed contact boundary drift")
    samples = device["samples"]
    require([int(row["PC"], 16) for row in samples] == list(SAMPLE_PCS)
            and [row["mapping"]["MAPH"] for row in samples] == ["0x8000"] * 3
            and [row["mapping"]["MAPL"] for row in samples] == ["0x0000"] * 3
            and [row["mapping"]["raw_tail"].endswith("..c..lhc")
                 for row in samples] == [True] * 3,
            "sample/mapping tuple drift")
    require(view["facts"]["mapping_aware_read_protocol"]["mapping_snapshot"]
            ["CPU_port"] == {"CHAREN": True, "HIRAM": True, "LORAM": True},
            "decoded CPU-port authority drift")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    gc_start, gc = symbol_bytes(truth, "gc_collect")
    require((gc_start, len(gc)) == (GC, 1483), "gc_collect geometry drift")
    instructions = {
        0x3A8E: ("STA $05", bytes.fromhex("8505"), "$0005", "ZP"),
        0x3B0D: ("STY $06", bytes.fromhex("8406"), "$0006", "ZP"),
        0x3B19: ("LDA $18", bytes.fromhex("a518"), "$0018", "ZP"),
    }
    instruction_rows = []
    for pc in SAMPLE_PCS:
        mnemonic, expected, target, mode = instructions[pc]
        observed = bytes_at(truth, ".text", pc, len(expected))
        require(observed == expected, f"sample instruction drift: 0x{pc:04x}")
        instruction_rows.append({
            "PC": f"0x{pc:04x}", "instruction": mnemonic,
            "bytes": observed.hex(), "addressing": mode,
            "state_target": target,
            "physical_target_under_captured_mapping": "0x0000" + target[1:],
        })

    # Entry increment is the non-obvious RMW case: reads and writes resolve
    # separately.  With BASIC visible, the read byte is ROM $ff; the write
    # still lands in the Bank-0 RAM underlay as $00.
    require(bytes_at(truth, ".text", 0x393A, 8) ==
            bytes.fromhex("eef0b9d003eef1b9"), "gc_runs increment sequence drift")
    rom = configured_rom()
    rom_raw = rom.read_bytes()
    require(len(rom_raw) == 0x20000 and sha_bytes(rom_raw) == CONFIGURED_ROM_SHA,
            "configured MEGA65 ROM drift")
    basic_rom_offset = 0x10000 + GC_RUNS
    require(rom_raw[basic_rom_offset:basic_rom_offset + 2] == b"\xff\xff",
            "configured BASIC-ROM gc_runs bytes drift")

    cpu = CORE_CPU.read_text(encoding="utf-8")
    machine = CORE_MACHINE.read_text(encoding="utf-8")
    monitor = CORE_MONITOR.read_text(encoding="utf-8")
    for token in (
        "if reg_map_high(blocknum)='1'",
        "if reg_map_low(blocknum)='1'",
        "if (blocknum=11) and (lhc(0)='1') and (lhc(1)='1') then",
        'temp_address(27 downto 12) := x"002B"',
        "if memory_access_write='1' then",
        "resolve_address_to_long(memory_access_address(15 downto 0),true)",
        "resolve_address_to_long(memory_access_address(15 downto 0),false)",
        "when I_INC => is_rmw <= '1'",
    ):
        require(token in cpu, f"primary core mapping/RMW token absent: {token}")
    require('monitor_roms(2 downto 0) <= monitor_cpuport' in machine
            and '.byte       "reca8lhc"' in monitor,
            "monitor CPU-port field authority drift")

    first = samples[0]["physical_data_reads"]
    alloc_block = monitor_payload(first["alloc_high"][0])
    require(len(alloc_block) == 16, "allocator block length drift")
    observed_state = {
        "alloc_high": int.from_bytes(alloc_block[0:2], "little"),
        "gc_frozen": int.from_bytes(alloc_block[2:4], "little"),
        "freelist": int.from_bytes(alloc_block[4:6], "little"),
        "gc_badobj": int.from_bytes(alloc_block[6:8], "little"),
        "allocs_since_gc": int.from_bytes(alloc_block[8:10], "little"),
        "str_top": int.from_bytes(alloc_block[14:16], "little"),
    }
    require(observed_state == {
        "alloc_high": 0, "gc_frozen": 0, "freelist": 0,
        "gc_badobj": 0x5302, "allocs_since_gc": 0, "str_top": 0},
        f"captured allocator state drift: {observed_state}")
    require(all(row["gc_runs"] == 0 and row["freelist_head"] == "0x0000"
                and row["alloc_high"] == 0 and row["gc_frozen"] == 0
                and row["EXT_occupancy"] == 0 for row in samples),
            "decoded sample state drift")

    text_section = truth.section(".text")
    text = truth.section_bytes(".text")
    direct = callsites(text, text_section.address, bytes.fromhex("20f738"))
    require(direct == [0x3705, 0x3717, 0x957C, 0x9663],
            f"resident direct gc_collect callsites drift: {direct}")
    buffer_section = truth.section(".lisp65_rt_buffer_alloc")
    buffer_calls = callsites(
        truth.section_bytes(buffer_section.name), buffer_section.address,
        bytes.fromhex("20f738"))
    require(buffer_calls == [0xC474], "buffer-overlay GC callsite drift")
    require(callsites(truth.section_bytes(".lisp65_workbench_overlay"),
                      truth.section(".lisp65_workbench_overlay").address,
                      bytes.fromhex("20f738")) == [],
            "active workbench overlay gained direct GC call")
    facade_section = truth.section(".lisp65_c2_host_facade")
    require(callsites(truth.section_bytes(facade_section.name),
                      facade_section.address, bytes.fromhex("4cf738")) == [0xB5D9],
            "GC facade edge drift")
    # The final linked image has no active call to the facade.  The facade is
    # retained as an ABI citizen, not a dynamic caller in this composition.
    require(bytes.fromhex("20d9b5") not in text,
            "resident call to c2_facade_gc_collect appeared")

    mem = SRC_MEM.read_text(encoding="utf-8")
    alloc_fn = function(mem, "obj alloc(uint8_t type)")
    str_open_fn = function(mem, "obj str_open(void)")
    str_putc_fn = function(mem, "uint8_t str_putc")
    mem_init_fn = function(mem, "void mem_init(void)")
    require("if (freelist == NIL) {\n        gc_collect();" in alloc_fn
            and "if (gc_frozen && freelist != NIL" in alloc_fn,
            "allocator collection guards drift")
    require("if (str_top > STR_MAX_BYTES)" in str_open_fn
            and "GC_PUSH(o); gc_collect();" in str_open_fn
            and "if (str_top >= STR_ARENA_SIZE)" in str_putc_fn,
            "string-arena collection guards drift")
    require("freelist = NIL;" in mem_init_fn
            and "for (i = MAX_CELLS - 1; i >= HEAP_CELLS; i--)" in mem_init_fn
            and "freelist = (obj)(i << 1);" in mem_init_fn,
            "mem_init EXT freelist construction drift")
    require(bytes_at(truth, ".text", 0x36DC, 74).find(
                bytes.fromhex("20f738")) >= 0
            and bytes_at(truth, ".text", ALLOC_EMPTY_CALL, 3) ==
                bytes.fromhex("20f738"),
            "alloc empty-freelist edge drift")

    exclusions = [
        {"callsite": "0x3705", "owner": "alloc nursery edge",
         "excluded_by": "gc_frozen == 0"},
        {"callsite": "0x957c", "owner": "str_open arena-overflow edge",
         "excluded_by": "str_top == 0 < STR_MAX_BYTES"},
        {"callsite": "0x9663", "owner": "str_putc arena-full edge",
         "excluded_by": "str_top == 0 < STR_ARENA_SIZE"},
        {"callsite": "0xc474", "owner": ".lisp65_rt_buffer_alloc overlay",
         "excluded_by": "inactive overlapping overlay; active workbench overlay has no edge"},
        {"callsite": "0xb5d9", "owner": "c2_facade_gc_collect ABI tail",
         "excluded_by": "no linked active caller"},
    ]

    # The exact contact did not read Page 1.  Name the unique *legal* linked
    # entry consistent with every captured state value, but do not invent a
    # dynamic return address or rule out an illegal/wild transfer.
    stack_reads = [
        read for row in samples
        for group in row["physical_data_reads"].values()
        for read in group
        if int(read["physical_RAM_address"], 16) >> 8 == 1]
    require(stack_reads == [], "unexpected stopped hardware-stack capture appeared")

    healthy = view["facts"]["static_boot_GC"]
    require(healthy["healthy_control_before_first_prompt"] == {
        "classification": "NO-PRE-PROMPT-COLLECTION",
        "gc_collect_reachable": False, "gc_runs_delta": 0},
        "healthy boot schedule authority drift")
    require(control["status"] == "CONTROL-PHYSICAL-BOOT-PASS"
            and control["control_identity"]["screen_result"]["visible_REPL"],
            "physical control authority drift")
    identity = repair["facts"]["identity"]
    require(identity["control_byteidentical_outside_enumerated_delta"]
            and identity["bootstrap_semantic_equivalence"]
                ["all_other_end_state_equal"]
            and identity["bootstrap_semantic_equivalence"]
                ["only_added_side_effect"] == "$B5C3=$44",
            "diagnostic/control identity authority drift")
    main = SRC_MAIN.read_text(encoding="utf-8")
    overlay = SRC_OVERLAY.read_text(encoding="utf-8")
    require(main.find("vm_install_staged_boot_overlay()") <
            main.find("c2_product_prepare_boot()") < main.find("c2_product_boot()"),
            "main boot order drift")
    require("void vm_workbench_boot_overlay_entry(void) {\n    eval_init();\n}"
            in overlay, "workbench overlay/eval_init edge drift")

    facts = {
        "address_arbiter": {
            "captured_mapping": {"MAPH": "0x8000", "MAPL": "0x0000",
                                 "CPU_port_LHC": "111", "B": "0x00"},
            "sample_instructions": instruction_rows,
            "ZP_translation": (
                "MAPL selects no low block and B=0; $0005/$0006/$0018 and "
                "$0039..$0048 resolve to physical Bank-0 at the same address"),
            "translation_authority_result": "CORRECT-NO-REPAIR",
        },
        "gc_runs_RMW": {
            "instruction": "$393A: INC $B9F0",
            "read_view": "BASIC ROM physical $002B9F0",
            "configured_ROM_read_byte": "0xff",
            "write_view": "Bank-0 RAM physical $0000B9F0",
            "written_byte": "0x00",
            "conclusion": (
                "physical gc_runs==0 is the expected post-increment underlay "
                "value; it does not contradict a real gc_collect entry"),
        },
        "captured_allocator_state": {
            **{key: (f"0x{value:04x}" if isinstance(value, int) else value)
               for key, value in observed_state.items()},
            "classification": "UNINITIALIZED-OR-CORRUPTED-ALLOCATOR-STATE",
            "why": (
                "freelist, alloc_high, gc_frozen, allocs_since_gc and str_top "
                "are zero while gc_badobj is already $5302; this cannot be the "
                "healthy post-mem_init 341-allocation state"),
        },
        "linked_caller_partition": {
            "resident_direct_calls": [f"0x{x:04x}" for x in direct],
            "excluded_edges": exclusions,
            "unique_legal_edge_under_captured_state": {
                "callsite": "0x3717", "symbol": "alloc+0x59",
                "predicate": "freelist == NIL",
                "callee": "gc_collect",
            },
            "dynamic_return_address_captured": False,
            "dynamic_claim_limit": (
                "The packet omitted Page-1 stack bytes. The result names the "
                "unique linked legal edge consistent with the captured state; "
                "it does not claim a sampled return address or exclude an "
                "illegal/wild transfer."),
        },
        "boot_delta_reconciliation": {
            "healthy_control": "physical lisp65> with 341 allocations and no GC",
            "diagnostic": (
                "entry witness executed; later, an allocation reached alloc+0x59 "
                "with no surviving evidence of the healthy mem_init state"),
            "diagnostic_delta_allocates": False,
            "bootstrap_end_state_except_witness": "byte/semantic equivalent",
            "first_observed_semantic_boundary": (
                "at the sampled allocator entry, the diagnostic run reaches a "
                "consumer with freelist NIL and the healthy EXT-freelist effects absent"),
            "upstream_cause_named": False,
            "remaining_boundary": (
                "whether vm_workbench_boot_overlay_entry/eval_init failed to establish "
                "the freelist or later target state/timing corrupted it; the enumerated "
                "diagnostic source delta does not explain the split"),
        },
        "scope": {
            "hardware_contacts": 0, "device_actions": 0,
            "product_bytes": 0, "measured_forms": 0,
            "R_A_I_G": None, "fix": None, "link": None,
            "contact_authorized": False,
        },
    }
    audit(facts)
    authorities = {
        "owner_commission": commission_binding, "device": bind(DEVICE),
        "prior_view_gate": bind(VIEW), "healthy_control": bind(CONTROL),
        "bootstrap_repair": bind(REPAIR), "diagnostic_ELF": bind(ELF),
        "source_mem": bind(SRC_MEM), "source_main": bind(SRC_MAIN),
        "source_overlay": bind(SRC_OVERLAY), "configured_ROM": bind(rom),
        "ROM_contract": bind(ROM_CONTRACT), "primary_core_CPU": bind(CORE_CPU),
        "primary_core_machine": bind(CORE_MACHINE),
        "primary_core_monitor": bind(CORE_MONITOR), "driver": bind(DRIVER),
    }
    return facts, authorities


def audit(facts: dict[str, Any]) -> None:
    address = facts["address_arbiter"]
    require(address["translation_authority_result"] == "CORRECT-NO-REPAIR"
            and len(address["sample_instructions"]) == 3
            and all(row["addressing"] == "ZP"
                    for row in address["sample_instructions"])
            and address["captured_mapping"] == {
                "MAPH": "0x8000", "MAPL": "0x0000",
                "CPU_port_LHC": "111", "B": "0x00"}
            and [row["physical_target_under_captured_mapping"]
                 for row in address["sample_instructions"]] ==
                ["0x00000018", "0x00000006", "0x00000005"],
            "address-arbiter conclusion drift")
    rmw = facts["gc_runs_RMW"]
    require(rmw["instruction"] == "$393A: INC $B9F0"
            and rmw["read_view"] == "BASIC ROM physical $002B9F0"
            and rmw["configured_ROM_read_byte"] == "0xff"
            and rmw["written_byte"] == "0x00"
            and "does not contradict" in rmw["conclusion"],
            "gc_runs RMW conclusion drift")
    state = facts["captured_allocator_state"]
    require(state["alloc_high"] == "0x0000"
            and state["gc_frozen"] == "0x0000"
            and state["freelist"] == "0x0000"
            and state["allocs_since_gc"] == "0x0000"
            and state["str_top"] == "0x0000"
            and state["gc_badobj"] == "0x5302"
            and state["classification"] ==
                "UNINITIALIZED-OR-CORRUPTED-ALLOCATOR-STATE",
            "captured allocator tuple drift")
    callers = facts["linked_caller_partition"]
    require(callers["resident_direct_calls"] ==
            ["0x3705", "0x3717", "0x957c", "0x9663"]
            and len(callers["excluded_edges"]) == 5
            and callers["unique_legal_edge_under_captured_state"] == {
                "callsite": "0x3717", "symbol": "alloc+0x59",
                "predicate": "freelist == NIL", "callee": "gc_collect"}
            and not callers["dynamic_return_address_captured"]
            and "omitted Page-1" in callers["dynamic_claim_limit"],
            "caller partition drift")
    require(callers["excluded_edges"][0]["excluded_by"] == "gc_frozen == 0"
            and callers["excluded_edges"][1]["excluded_by"] ==
                "str_top == 0 < STR_MAX_BYTES"
            and callers["excluded_edges"][2]["excluded_by"] ==
                "str_top == 0 < STR_ARENA_SIZE"
            and callers["excluded_edges"][3]["excluded_by"].startswith(
                "inactive overlapping overlay")
            and callers["excluded_edges"][4]["excluded_by"] ==
                "no linked active caller",
            "caller exclusion reason drift")
    delta = facts["boot_delta_reconciliation"]
    require(not delta["diagnostic_delta_allocates"]
            and delta["bootstrap_end_state_except_witness"] ==
                "byte/semantic equivalent"
            and not delta["upstream_cause_named"]
            and "later target state/timing" in delta["remaining_boundary"],
            "boot-delta claim boundary drift")
    require(facts["scope"] == {
        "hardware_contacts": 0, "device_actions": 0, "product_bytes": 0,
        "measured_forms": 0, "R_A_I_G": None, "fix": None, "link": None,
        "contact_authorized": False}, "desk scope drift")


def expected() -> dict[str, Any]:
    facts, authorities = exact_facts()
    return {
        "format": "lisp65-c2.3-v1.6-gc-address-caller-attribution-v1",
        "recorded_on": date.today().isoformat(),
        "status": (
            "HOST-GREEN; ADDRESS-VIEW-CORRECT; UNIQUE-LEGAL-CALLER-ALLOC+0x59; "
            "UPSTREAM-BOOT-CAUSE-OPEN"),
        "authorities": authorities,
        "facts": facts,
        "execution_witnesses": [
            "three sampled opcodes bind only ZP state targets under MAPL=0/B=0",
            "configured BASIC ROM contains $FF at logical $B9F0",
            "primary core resolves RMW read through BASIC ROM and write to RAM",
            "INC $B9F0 therefore writes the observed $00 underlay value",
            "active resident text has exactly four direct GC calls",
            "captured gc_frozen/str_top state excludes three of those calls",
            "the inactive buffer overlay and uncalled facade cannot own this entry",
            "alloc+$59 is the sole linked legal entry consistent with the packet",
            "healthy control and diagnostic bootstrap equivalence exclude an allocating delta",
        ],
        "rejected_mutations": [
            "map-ZP-through-high-window", "nonzero-B-register",
            "treat-gc-runs-as-plain-store", "read-gc-runs-from-RAM",
            "change-BASIC-ROM-byte", "claim-gc-runs-zero-means-no-entry",
            "drop-alloc-empty-edge", "select-nursery-edge",
            "select-str-open-edge", "select-str-putc-edge",
            "activate-buffer-overlay", "invent-facade-caller",
            "claim-dynamic-return-address", "claim-healthy-post-mem-init-state",
            "claim-diagnostic-delta-allocates", "name-upstream-boot-cause",
            "claim-R-A-I-G", "authorize-contact",
        ],
        "claim_limit": (
            "Desk-only address-mode and linked-caller attribution. It proves the "
            "physical ZP reads correct, explains gc_runs==0 as BASIC-ROM-backed "
            "RMW, and names alloc+$59 as the unique legal linked entry under the "
            "captured state. Page-1 return bytes were not captured, and the cause "
            "of the missing mem_init effects remains open. No device action, "
            "R/A/I/G result, product defect, fix, product byte, link or recontact "
            "is claimed."),
    }


def selftest() -> dict[str, Any]:
    facts, _ = exact_facts()
    cases: dict[str, tuple[list[Any], Any]] = {
        "map-ZP-through-high-window":
            (["address_arbiter", "sample_instructions", 0,
              "physical_target_under_captured_mapping"], "0x00010005"),
        "nonzero-B-register":
            (["address_arbiter", "captured_mapping", "B"], "0x01"),
        "treat-gc-runs-as-plain-store":
            (["gc_runs_RMW", "instruction"], "$393A: STA $B9F0"),
        "read-gc-runs-from-RAM":
            (["gc_runs_RMW", "read_view"], "Bank-0 RAM physical $0000B9F0"),
        "change-BASIC-ROM-byte":
            (["gc_runs_RMW", "configured_ROM_read_byte"], "0x00"),
        "claim-gc-runs-zero-means-no-entry":
            (["gc_runs_RMW", "conclusion"], "zero proves no entry"),
        "drop-alloc-empty-edge":
            (["linked_caller_partition", "unique_legal_edge_under_captured_state",
              "callsite"], "0x3705"),
        "select-nursery-edge":
            (["captured_allocator_state", "gc_frozen"], "0x0001"),
        "select-str-open-edge":
            (["captured_allocator_state", "str_top"], "0x4001"),
        "select-str-putc-edge":
            (["linked_caller_partition", "resident_direct_calls"],
             ["0x3705", "0x3717", "0x957c"]),
        "activate-buffer-overlay":
            (["linked_caller_partition", "excluded_edges", 3, "excluded_by"],
             "active overlay"),
        "invent-facade-caller":
            (["linked_caller_partition", "excluded_edges", 4, "excluded_by"],
             "active caller"),
        "claim-dynamic-return-address":
            (["linked_caller_partition", "dynamic_return_address_captured"], True),
        "claim-healthy-post-mem-init-state":
            (["captured_allocator_state", "classification"], "HEALTHY"),
        "claim-diagnostic-delta-allocates":
            (["boot_delta_reconciliation", "diagnostic_delta_allocates"], True),
        "name-upstream-boot-cause":
            (["boot_delta_reconciliation", "upstream_cause_named"], True),
        "claim-R-A-I-G": (["scope", "R_A_I_G"], "R"),
        "authorize-contact": (["scope", "contact_authorized"], True),
    }
    rejected = []
    for name, (path, replacement) in cases.items():
        trial = deepcopy(facts)
        cursor: Any = trial
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except AttributionError:
            rejected.append(name)
        else:
            raise AttributionError(f"mutation survived: {name}")
    require(len(rejected) == len(cases), "mutation count drift")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "sample_opcodes": len(facts["address_arbiter"]["sample_instructions"]),
            "direct_calls": len(facts["linked_caller_partition"]
                                ["resident_direct_calls"]),
            "caller": facts["linked_caller_partition"]
                ["unique_legal_edge_under_captured_state"]["symbol"]}


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("selftest", "write", "check"))
    args = parser.parse_args()
    try:
        if args.command == "selftest":
            result = selftest()
            print("GC ADDRESS/CALLER SELFTEST PASS "
                  f"mutations={result['mutations']} "
                  f"opcodes={result['sample_opcodes']} "
                  f"calls={result['direct_calls']} caller={result['caller']}")
            return 0
        value = expected()
        if args.command == "write":
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_bytes(canonical(value))
            print("GC ADDRESS/CALLER WRITE PASS "
                  "view=correct rmw=ff-to-00 caller=alloc+0x59 contact=closed")
            return 0
        require(RECEIPT.is_file() and RECEIPT.read_bytes() == canonical(value),
                "GC address/caller receipt drift; run write deliberately")
        print("GC ADDRESS/CALLER PASS "
              "view=correct rmw=ff-to-00 caller=alloc+0x59 contact=closed")
        return 0
    except (AttributionError, KeyError, ValueError, TypeError) as exc:
        print(f"GC ADDRESS/CALLER FIRST RED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
