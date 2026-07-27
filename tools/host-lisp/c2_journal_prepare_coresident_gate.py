#!/usr/bin/env python3
"""Permanent one-record gate for rollback-prepare/journal-write co-residence."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_product_substitution_link as PRODUCT  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


FEATURE = "LISP65_C2_LITE_V6_JOURNAL_PREPARE_CORESIDENT"
CONTRACT = ROOT / "config/c2-append-cutpoint-contract.json"
RUNTIME = ROOT / "src/c2_product_runtime.c"
HEADER = ROOT / "src/c2_product_runtime.h"
SELECTOR = ROOT / "src/c2_journal_prepare_select.s"
FIXTURE = ROOT / "scripts/c2-lite-v6-journal-prepare-cutpoints-main.c"
CAP = 1792
SELECTOR_CAP = 82
PACK_QUANTUM = 256


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def configure() -> None:
    PRODUCT.configure_journal_prepare_co_residence()
    names = [name for name, _entry in PRODUCT.C2_APPEND_SLICES]
    require(names.count("journal_prepare") == 1
            and "journal_write" not in names
            and "rollback_prepare" not in names
            and len(PRODUCT.C2_APPEND_SLICES) == 21
            and PRODUCT.SESSION_APPEND_SLOT_BASE == 23
            and PRODUCT.SESSION_SERVICE_SLOT_BASE == 44
            and len(PRODUCT.SESSION_SLICE_SPECS) == 48
            and PRODUCT.UNIQUE_SLICE_COUNT == 55,
            "journal/prepare physical profile drift")
    row = [row for row in PRODUCT.SESSION_SLICE_SPECS
           if ":c2-append-journal-prepare:" in row]
    require(len(row) == 1 and row[0].startswith(
                "30:c2-append-journal-prepare:")
            and row[0].endswith(":c2_append_journal_prepare_phase"),
            "journal/prepare public record drift")


def fixture(out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    binary = out / "c2-lite-v6-journal-prepare-cutpoints"
    command = ["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
               "-fsanitize=address,undefined", str(FIXTURE), "-o", str(binary)]
    subprocess.run(command, cwd=ROOT, check=True)
    run = subprocess.run([str(binary)], cwd=ROOT, check=True,
                         text=True, capture_output=True)
    expected = ("c2-lite-v6-journal-prepare-cutpoints: PASS slice=1 "
                "entries=2 normal=1 rollback=2 negatives=6 "
                "markers=512 accepted=3 rejected=509 "
                "added-state-bytes=0 added-pointers=0")
    require(run.stdout.strip() == expected, "journal/prepare fixture drift")
    return {
        "status": "passed-normal-rollback-skip-replay-cutpoints",
        "normal_calls": 1,
        "rollback_calls": 2,
        "negative_mutations": 6,
        "marker_domain_cases": 512,
        "marker_domain_accepted": 3,
        "marker_domain_rejected": 509,
        "asan": "passed", "ubsan": "passed",
        "added_state_bytes": 0, "added_pointers": 0,
    }


def source_gate(out: Path) -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    runtime = RUNTIME.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")
    selector = SELECTOR.read_text(encoding="utf-8")
    c = contract["journal_prepare_co_residence"]
    checks = {
        "current_contract_v8": contract["schema"] ==
            "lisp65.c2.append-cutpoint-contract.v8",
        "one_record_contract": c["slot"] == 30
            and c["catalog_records_before"] == 49
            and c["catalog_records_after"] == 48
            and "all 256 marker bytes" in c["selector_totality"],
        "zero_byte_handoff": c["new_resident_cells"] == 0
            and c["new_bss_bytes"] == 0 and c["new_gc_roots"] == 0,
        "tri_state_cutpoint": all(token in runtime for token in (
            "#define C2J_RESULT_PREPARED 2u",
            "C2AW_JOURNAL_RESULT(w) = C2J_RESULT_PREPARED;",
            "C2AW_JOURNAL_RESULT(&c2aw) !=\n#ifdef "
            "LISP65_C2_LITE_V6_JOURNAL_PREPARE_CORESIDENT\n"
            "            C2J_RESULT_PREPARED"))
            and all(token in selector for token in (
                "cmp\t#2", "beq\t.Lwrite", "beq\t.Lprepare")),
        "C_dispatcher_retired": "uint8_t c2_append_journal_prepare_phase("
            not in runtime,
        "one_selector": all(token in selector for token in (
            ".globl\tc2_append_journal_prepare_phase",
            ".type\tc2_append_journal_prepare_phase,@function",
            ".size\tc2_append_journal_prepare_phase,",
            "ldz\t#2",
            "ldz\t#213",
            "jmp\tc2_append_journal_write_phase",
            "jmp\tc2_append_rollback_prepare_phase")),
        "tail_C_ABI_Z0": selector.count(
            "ldz\t#0\n\tjmp\tc2_append_") == 2
            and "Z=0" in c["tail_abi"],
        "target_ABI_asserted": all(token in runtime for token in (
            "offsetof(c2_append_state, main_ordinal) == 2u",
            "offsetof(c2_append_state, record) + 31u == 213u")),
        "no_overlay_to_overlay": "c2_overlay_call" not in selector,
        "slot_aliases": all(token in header for token in (
            "#define LISP65_C2_APPEND_JOURNAL_PREPARE_SLOT 30u",
            "LISP65_C2_APPEND_JOURNAL_WRITE_SLOT \\",
            "LISP65_C2_APPEND_ROLLBACK_PREPARE_SLOT \\",
            "#define LISP65_C2_APPEND_STAGE_COPY_SLOT 33u",
            "#define LISP65_C2_APPEND_ABORT_CONTROL_SLOT 43u")),
    }
    require(all(checks.values()), "journal/prepare source gate red: " +
            str([name for name, ok in checks.items() if not ok]))
    return {
        "status": "passed-one-record-journal-prepare-source-contract",
        "checks": checks,
        "fixture": fixture(out),
        "physical_slot": 30,
        "logical_entries": ["rollback_prepare", "journal_write"],
        "handoff": "record[31] NONE/PREPARED/ACTIVE",
        "selector": {
            "source": SELECTOR.relative_to(ROOT).as_posix(),
            "maximum_bytes": SELECTOR_CAP,
            "context_ABI": "__rc2/__rc3",
            "tail_targets": [
                "c2_append_rollback_prepare_phase",
                "c2_append_journal_write_phase"],
        },
    }


def linked_gate(elf: Path, llvm_readobj: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=llvm_readobj,
                          include_section_data=True)
    section = ".lisp65_rt_c2append_journal_prepare"
    names = ("c2_append_journal_prepare_phase",
             "c2_append_journal_write_phase",
             "c2_append_rollback_prepare_phase")
    symbols = {name: truth.symbol(name) for name in names}
    require(all(symbol.symbol_type == "Function" and symbol.bytes > 0
                and symbol.section == section for symbol in symbols.values()),
            "journal/prepare linked citizens escaped fused section")
    physical = truth.section(section)
    selector = symbols["c2_append_journal_prepare_phase"]
    require(0 < physical.bytes <= CAP
            and 0 < selector.bytes <= SELECTOR_CAP
            and ".lisp65_rt_c2append_journal_write"
                not in truth.sections_by_name
            and ".lisp65_rt_c2append_rollback_prepare"
                not in truth.sections_by_name,
            "journal/prepare predecessor section survived or cap crossed")
    for name in names:
        symbol = symbols[name]
        edges = [row for row in truth.relocations
                 if row.source_section_index == symbol.section_index
                 and symbol.value <= row.offset < symbol.value + symbol.bytes
                 and row.target.startswith("c2_append_")
                 and row.target not in names]
        require(not edges, f"overlay edge escaped fused slice: {name}")
    return {
        "status": "passed-linked-one-record-journal-prepare-cutpoint",
        "section": section,
        "bytes": physical.bytes,
        "headroom_bytes": CAP - physical.bytes,
        "packed_bytes": (physical.bytes + 255) & ~255,
        "packed_before_bytes": 2048,
        "packed_recovered_bytes": 2048 - ((physical.bytes + 255) & ~255),
        "functions": {name: {"address": symbol.value,
                              "bytes": symbol.bytes,
                              "section": symbol.section}
                      for name, symbol in symbols.items()},
        "selector_cap_bytes": SELECTOR_CAP,
        "retired_sections": [
            ".lisp65_rt_c2append_journal_write",
            ".lisp65_rt_c2append_rollback_prepare"],
        "new_state_bytes": 0,
    }


def main() -> int:
    print(json.dumps(source_gate(ROOT / "build/c2-journal-prepare-gate"),
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
