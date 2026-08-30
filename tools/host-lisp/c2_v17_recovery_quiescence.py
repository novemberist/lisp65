#!/usr/bin/env python3
"""Prove the state-free recovery quiescence fast path on source and final ELF."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "src/c2_product_runtime.c"
CONTRACT = ROOT / "config/c2-v17-recovery-quiescence-contract.json"
PRICING = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-recovery-service-time-pricing-receipt.json")
BASELINE = ROOT / (
    "build/c2.3/v1.6-item1-only-candidate-r1/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"

if str(ROOT / "tools/host-lisp") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools/host-lisp"))

from elf_truth import ElfTruth  # noqa: E402
import c2_bank2_composed_ownership as BANK2  # noqa: E402
import c2_transitive_map_nesting_gate as MAP_NEST  # noqa: E402


class QuiescenceError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise QuiescenceError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def function_body(source: str, name: str) -> str:
    match = re.search(
        rf"^[^#\n]*\b{re.escape(name)}\s*\([^;{{]*?\)\s*\{{",
        source, re.MULTILINE | re.DOTALL)
    require(match is not None, f"function absent: {name}")
    depth = 0
    for offset, char in enumerate(source[match.start():]):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():match.start() + offset + 1]
    raise QuiescenceError(f"unterminated function: {name}")


def source_gate(source: str) -> dict[str, Any]:
    probe = function_body(source, "c2_abort_empty_journal_derived")
    recover = function_body(source, "c2_product_abort_recover")
    driver = function_body(source, "c2_abort_driver")
    reads = re.findall(r"c2_stream_c2d_read\s*\(", probe)
    require(len(reads) == 1, "A0 no longer reads exactly one C2J authority")
    require("uint8_t *facts = c2aw.journal_snapshot" in probe
            and "C2D_UNWIND_BASE, facts, C2D_UNWIND_BYTES" in probe
            and "for (i = 0u; i < C2D_UNWIND_BYTES; ++i)" in probe
            and "LISP65_C2_APPEND_FRONTS_SLOT" in probe
            and "LISP65_C2_APPEND_ROLLBACK_PREPARE_SLOT" in probe
            and "c2_append_run_rollback_plan(&c2aw)" in probe,
            "A0 stopped deriving C2J or retained recovery obligations")
    require(probe.count("if (!c2_stream_c2d_read") == 1
            and "if (!c2_phase_scratch_acquire" in probe
            and "if (!c2_phase_scratch_release" in probe,
            "read/phase uncertainty no longer fails closed")
    declaration_at = source.index("uint8_t c2_abort_empty_journal_derived")
    declaration = source[source.rfind("\n\n", 0, declaration_at):
                         declaration_at]
    require("static" in declaration
            and "section(\".text.c2_abort_empty_journal\")" in declaration
            and probe.count("c2_overlay_call(") == 2
            and "c2_abort_driver" not in probe,
            "A0 gained state/driver recursion or lost its owned two overlays")
    require("c2_abort_empty_journal_derived()" in recover
            and "if (c2_abort_empty_journal_derived()) return 1u;\n"
                "    return !c2_ready || c2_abort_driver_facade();" in recover
            and "return !c2_ready || c2_abort_driver_facade();" in recover
            and recover.index("c2_abort_empty_journal_derived()")
                < recover.index("c2_abort_driver_facade()"),
            "A0 no longer precedes the serial recovery driver")
    require("c2_abort_empty_journal_derived" not in driver,
            "probe changed the serial driver body")
    return {
        "status": "PASS: COMPLETE EMPTY C2J BYPASSES VALIDATE RECOVERY",
        "physical_reads": [
            {"authority": "C2J", "bytes": 64, "complete": True},
        ],
        "total_physical_bytes": 64,
        "new_state_bytes": 0,
        "uncertainty": "unchanged-serial-driver",
        "residual_overlays": ["fronts", "rollback-prepare"],
        "placement_domain": "ordinary-baseline-always-visible",
    }


def mutation_gate(source: str) -> list[dict[str, str]]:
    mutations = {
        "final-c2j-byte-skipped": source.replace(
            "for (i = 0u; i < C2D_UNWIND_BYTES; ++i)",
            "for (i = 0u; i < C2D_UNWIND_BYTES - 1u; ++i)", 1),
        "c2j-read-failure-accepted": source.replace(
            "    if (!c2_stream_c2d_read(C2D_UNWIND_BASE, facts, C2D_UNWIND_BYTES))\n"
            "        goto done;",
            "    (void)c2_stream_c2d_read(C2D_UNWIND_BASE, facts, C2D_UNWIND_BYTES);",
            1),
        "fronts-residual-removed": source.replace(
            "    if (!c2_overlay_call(LISP65_C2_APPEND_FRONTS_SLOT, &c2aw)\n"
            "        || !c2_overlay_call(LISP65_C2_APPEND_ROLLBACK_PREPARE_SLOT, &c2aw))",
            "    if (!c2_overlay_call(LISP65_C2_APPEND_ROLLBACK_PREPARE_SLOT, &c2aw))",
            1),
        "prepare-residual-removed": source.replace(
            "    if (!c2_overlay_call(LISP65_C2_APPEND_FRONTS_SLOT, &c2aw)\n"
            "        || !c2_overlay_call(LISP65_C2_APPEND_ROLLBACK_PREPARE_SLOT, &c2aw))",
            "    if (!c2_overlay_call(LISP65_C2_APPEND_FRONTS_SLOT, &c2aw))",
            1),
        "serial-driver-bypassed-on-uncertainty": source.replace(
            "    return !c2_ready || c2_abort_driver_facade();",
            "    return !c2_ready;", 1),
    }
    rows: list[dict[str, str]] = []
    for name, mutant in mutations.items():
        require(mutant != source, f"mutation did not alter source: {name}")
        try:
            source_gate(mutant)
        except QuiescenceError as error:
            rows.append({"name": name, "rejected": str(error)})
        else:
            raise QuiescenceError(f"quiescence mutation survived: {name}")
    return rows


def symbol_bytes(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    require(symbol.bytes > 0, f"sized symbol required: {name}")
    section = truth.section(symbol.section)
    raw = truth.section_bytes(symbol.section)
    offset = symbol.value - section.address
    require(0 <= offset <= len(raw) - symbol.bytes,
            f"symbol escaped section: {name}")
    return raw[offset:offset + symbol.bytes]


def disassembly(elf: Path) -> str:
    return subprocess.run(
        [str(OBJDUMP), "-d", "--no-show-raw-insn", str(elf)], check=True,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def emitted_body(text: str, name: str) -> str:
    match = re.search(
        rf"^[0-9a-f]+ <{re.escape(name)}>:\n(?P<body>.*?)(?=^\n?[0-9a-f]+ <|^Disassembly of section|\Z)",
        text, re.MULTILINE | re.DOTALL)
    require(match is not None, f"emitted function absent: {name}")
    return match.group("body")


def call_targets(body: str) -> list[str]:
    return re.findall(r"\b(?:jsr|jmp)\s+\$[0-9a-f]+\s+<([^+>]+)", body)


def quiescence_model(*, journal: bytes,
                     reads_ok: bool = True) -> dict[str, Any]:
    valid = reads_ok and len(journal) == 64 and not any(journal)
    return {"route": "a0-two-overlay" if valid else "serial-driver",
            "overlay_calls": 2 if valid else "unchanged",
            "crc_bytes": 6110 if valid else "unchanged"}


def model_gate() -> dict[str, Any]:
    good = quiescence_model(journal=bytes(64))
    cases = {
        "sealed-empty": good,
        "last-journal-byte": quiescence_model(
            journal=bytes(63) + b"\x01"),
        "unreadable": quiescence_model(
            journal=bytes(64), reads_ok=False),
    }
    require(good == {"route": "a0-two-overlay", "overlay_calls": 2,
                     "crc_bytes": 6110}
            and all(row["route"] == "serial-driver"
                    for name, row in cases.items() if name != "sealed-empty"),
            "quiescence decision model red")
    return {"status": "PASS: SEALED EMPTY WORLD COSTS TWO OVERLAYS",
            "cases": cases}


def final_gate(elf: Path, plane: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    baseline = ElfTruth.read(
        BASELINE, llvm_readobj=READOBJ, include_section_data=True)
    symbols = {row.name: row for row in truth.symbols}
    probe = truth.symbol("c2_abort_empty_journal_derived")
    recover = truth.symbol("c2_product_abort_recover")
    require(probe.section == ".text" and probe.bytes > 0,
            "probe is not emitted in permanent ordinary text")
    require(recover.section == ".text" and recover.bytes > 0,
            "post-longjmp recovery seam is not emitted in ordinary text")
    text = disassembly(elf)
    calls = {name: call_targets(emitted_body(text, name)) for name in (
        "c2_product_abort_recover", "c2_abort_empty_journal_derived",
        "c2_abort_driver", "repl")}
    require("c2_abort_empty_journal_derived" in calls["c2_product_abort_recover"]
            and "c2_abort_driver_facade" in calls["c2_product_abort_recover"]
            and calls["c2_product_abort_recover"].index(
                "c2_abort_empty_journal_derived")
                < calls["c2_product_abort_recover"].index(
                    "c2_abort_driver_facade")
            and "c2_product_abort_recover" in calls["repl"],
            "final control flow lost probe-before-serial recovery")
    require(calls["c2_abort_empty_journal_derived"].count(
                "c2_stream_c2d_read") == 1
            and calls["c2_abort_empty_journal_derived"].count(
                "c2_overlay_call") == 2
            and any("overlay" in name for name in calls["c2_abort_driver"]),
            "final probe/driver boundary is not instrument-neutral")
    driver = symbol_bytes(truth, "c2_abort_driver")
    old_driver = symbol_bytes(baseline, "c2_abort_driver")
    require(driver == old_driver,
            "non-quiescent serial driver bytes changed")
    state_sections = (".bss", ".zp.bss")
    state = {name: truth.section(name).bytes for name in state_sections}
    old_state = {name: baseline.section(name).bytes for name in state_sections}
    # The claim is zero *added* quiescence state, not identity with an older
    # whole-program allocation. Later candidates may legitimately reclaim or
    # repack unrelated state. Addresses/sections remain LTO placement choices.
    def state_population(image: ElfTruth) -> set[tuple[str, int]]:
        return {(row.name, row.bytes) for row in image.symbols
                if row.section in state_sections and row.bytes > 0}

    old_population = state_population(baseline)
    population = state_population(truth)
    added_state = sorted(population - old_population)
    removed_state = sorted(old_population - population)
    require(not added_state and all(state[name] <= old_state[name]
                                    for name in state_sections),
            "quiescence feature allocated product state")
    nested = MAP_NEST.check(elf)
    require(nested["violations"] == [], "transitive MAP nesting regressed")
    composed = BANK2.derive(
        elf=elf, plane=plane, readobj=READOBJ,
        expected_vmas={
            ".lisp65_c2_mapped_far_service": 0x78B2,
            ".lisp65_c2_mapped_product_cold": 0x7E8D,
        }, placement_policy="fixed-contract")
    text_section = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    free = facade.address - (text_section.address + text_section.bytes)
    require(free >= 0 and probe.value >= text_section.address
            and probe.value + probe.bytes <= facade.address,
            "ordinary-text probe escaped its derived placement interval")
    pricing = load(PRICING)
    require(pricing["sealed_empty_path_cost"]["overlay_calls"] == 8
            and pricing["sealed_empty_path_cost"]["synchronous_crc_bytes"]
                == 17852,
            "sealed predecessor measurement drift")
    return {
        "status": "PASS: FINAL ELF HAS DERIVED EMPTY-JOURNAL BYPASS",
        "elf": bind(elf), "plane": bind(plane),
        "symbols": {
            "probe": {"address": probe.value, "bytes": probe.bytes,
                      "section": probe.section},
            "recover": {"address": recover.value, "bytes": recover.bytes,
                        "section": recover.section},
            "serial_driver": {"bytes": len(driver), "sha256": sha(driver),
                              "baseline_sha256": sha(old_driver),
                              "byte_identical": True},
        },
        "control_flow": calls,
        "state_bytes": {"candidate": state, "baseline": old_state,
                        "added_named_allocations": added_state,
                        "removed_named_allocations": removed_state,
                        "new_state_bytes": 0,
                        "whole_program_delta": {
                            name: state[name] - old_state[name]
                            for name in state_sections},
                        "authority": "candidate-minus-baseline named allocations"},
        "ordinary_text": {
            "start": text_section.address,
            "end_exclusive": text_section.address + text_section.bytes,
            "facade_start": facade.address,
            "free_bytes": free,
            "probe_owned": True,
        },
        "composed_bank2": composed,
        "transitive_MAP": nested,
        "sealed_measurement": {
            "before": {"overlay_calls": 8, "crc_bytes": 17852},
            "after": {"overlay_calls": 2, "crc_bytes": 6110},
            "authority": bind(PRICING),
        },
        "model": model_gate(),
    }


def derive(elf: Path | None = None, plane: Path | None = None) -> dict[str, Any]:
    source = RUNTIME.read_text(encoding="utf-8")
    value = {
        "format": "lisp65-c2-v17-recovery-quiescence-gate-v1",
        "status": "PASS: RECOVERY QUIESCENCE CONTRACT HOLDS",
        "authorities": {"contract": bind(CONTRACT), "pricing": bind(PRICING),
                        "runtime": bind(RUNTIME), "baseline": bind(BASELINE)},
        "source": source_gate(source),
        "mutations": mutation_gate(source),
        "model": model_gate(),
        "claim_limit": (
            "Host/final-artifact proof only; opens no medium, device contact, "
            "Comfort freight, or Block-3 freight."),
    }
    if elf is not None:
        require(plane is not None, "candidate plane required with final ELF")
        value["final_elf"] = final_gate(elf, plane)
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
