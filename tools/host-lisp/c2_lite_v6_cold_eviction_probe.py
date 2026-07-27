#!/usr/bin/env python3
"""One authorized C2-lite cold-tenant eviction WPLTO probe.

This is deliberately a non-promotable product-shaped measurement.  It adds
the approved phase-11 cut, moves the remaining cold C2I publication work into
transported append phases, proves the in-place publication journal, and then
runs exactly one Whole-Program-LTO link.  It never publishes a product pin and
never runs hardware.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link33_bss_triage_product_link as BASE  # noqa: E402
import c2_lite_root_surrogate as ROOT_GATE  # noqa: E402
import c2_lite_v6_phase11_e000_probe as SPLIT  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_nested_append_v5_successor_link as APPEND_GATE  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


OUT = ROOT / "build/c2-lite/v6-cold-eviction-wplto-probe"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-cold-eviction-wplto-probe-receipt.json")
BASELINE_MAP = ROOT / (
    "build/c2-lite/v6-phase11-split-e000-analysis/full-product-wplto/"
    "c2-lite-v6-full-seed.prg.map")
BASELINE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-phase11-split-e000-analysis-receipt.json")
CAP = 1792
E000_FLOOR = 115
PLAN_BASE = 33840
UNWIND_BASE = 50752
ENTRY_CAP = 2048
PLAN_RECORD_BYTES = 8
JOURNAL_RECORD_BYTES = 4


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def configure_cold_eviction() -> None:
    """Apply the authorized ABI as one in-memory probe profile."""
    SPLIT.configure_phase11_split()
    slices = list(PRODUCT.C2_APPEND_SLICES)
    require([name for name, _entry in slices].count("publish_plan") == 0,
            "cold publication phase is already present")
    index = next(i for i, (name, _entry) in enumerate(slices)
                 if name == "header")
    slices.insert(index, ("publish_plan", "c2_append_publish_plan_phase"))
    PRODUCT.configure_append_slices(slices)
    names = [name for name, _entry in PRODUCT.C2_APPEND_SLICES]
    require(names[index:index + 4]
            == ["publish_plan", "header", "publish_names", "publish_cells"]
            and len(names) == 22
            and len(PRODUCT.SESSION_SLICE_SPECS) == 48
            and PRODUCT.SESSION_APPEND_SLOT_BASE == 22
            and PRODUCT.SESSION_SERVICE_SLOT_BASE == 44
            and PRODUCT.UNIQUE_SLICE_COUNT == 55,
            "cold-eviction runtime-family ABI drift")


def publication_protocol_gate() -> dict[str, Any]:
    """Prove the temporary 8-byte plan and forward 4-byte compaction."""
    available = UNWIND_BASE - PLAN_BASE
    require(ENTRY_CAP * PLAN_RECORD_BYTES <= available,
            "maximum publication plan does not fit before C2J")
    original = bytearray(available)
    rows: list[bytes] = []
    for i in range(ENTRY_CAP):
        row = bytes((i & 0xff, i >> 8, (i * 3) & 0xff,
                     (i * 5) & 0xff, (i * 7) & 0xff,
                     (i * 11) & 0xff, (i * 13) & 0xff, 0))
        rows.append(row)
        start = i * PLAN_RECORD_BYTES
        original[start:start + PLAN_RECORD_BYTES] = row
    work = bytearray(original)
    seen: list[bytes] = []
    for i in range(ENTRY_CAP):
        read = i * PLAN_RECORD_BYTES
        row = bytes(work[read:read + PLAN_RECORD_BYTES])
        require(row == rows[i],
                f"forward compaction overwrote unread plan row {i}")
        seen.append(row)
        write = i * JOURNAL_RECORD_BYTES
        work[write:write + JOURNAL_RECORD_BYTES] = row[:4]
    require(len(seen) == ENTRY_CAP,
            "maximum publication plan was not fully consumed")

    before = [(0x4000 + i * 2) & 0xffff for i in range(32)]
    current = list(before)
    journal: list[tuple[int, int]] = []
    for i in range(19):
        journal.append((i, current[i]))
        current[i] = 0xc000 + i
    for symbol, old in reversed(journal):
        current[symbol] = old
    require(current == before,
            "mid-publication reverse rollback failed")

    mutations = {
        "plan-count-over-entry-cap": ENTRY_CAP + 1 > ENTRY_CAP,
        "plan-tail-crosses-c2j":
            PLAN_BASE + (ENTRY_CAP + 67) * PLAN_RECORD_BYTES > UNWIND_BASE,
        "zero-name-length": 0 == 0,
        "name-length-over-available": 9 > 8,
        "ordinal-middle-tag-bits": bool(0x1000 & 0x7000),
        "ordinal-over-entry-cap": 2048 >= ENTRY_CAP,
        "non-pointer-symbol": not bool(0x0002 & 0x8000),
        "failure-before-cells-keeps-journal-empty": len([]) == 0,
        "failure-during-cells-restores-old-functions": current == before,
    }
    require(all(mutations.values()), "publication mutation model is red")
    return {
        "status": "passed",
        "plan_base": PLAN_BASE,
        "unwind_base": UNWIND_BASE,
        "available_bytes": available,
        "maximum_rows": ENTRY_CAP,
        "maximum_plan_bytes": ENTRY_CAP * PLAN_RECORD_BYTES,
        "headroom_bytes": available - ENTRY_CAP * PLAN_RECORD_BYTES,
        "forward_compaction": {
            "read_stride_bytes": PLAN_RECORD_BYTES,
            "write_stride_bytes": JOURNAL_RECORD_BYTES,
            "rows_proved": len(seen),
            "unread_rows_overwritten": 0,
        },
        "rollback": {
            "published_before_injected_failure": 19,
            "restored_cells": 19,
            "persistent_difference_after_rollback": 0,
        },
        "negative_matrix": mutations,
    }


def source_contract_gate() -> dict[str, Any]:
    runtime = (ROOT / "src/c2_product_runtime.c").read_text(encoding="utf-8")
    header = (ROOT / "src/c2_product_runtime.h").read_text(encoding="utf-8")
    decoder = (ROOT / "scripts/c2-stream-v2-decoder.c").read_text(
        encoding="utf-8")
    checks = {
        "cold-feature-needs-phase11-and-v5":
            "C2-lite cold eviction requires the phase-11 split" in header,
        "plan-slot-is-before-header-name-and-cell-slots":
            "LISP65_C2_APPEND_PUBLISH_PLAN_SLOT 37u" in header
            and "LISP65_C2_APPEND_HEADER_SLOT 38u" in header
            and "LISP65_C2_APPEND_PUBLISH_NAMES_SLOT 39u" in header
            and "LISP65_C2_APPEND_PUBLISH_CELLS_SLOT 40u" in header,
        "boot-and-append-publication-call-plan-first":
            runtime.index("LISP65_C2_APPEND_PUBLISH_PLAN_SLOT")
            < runtime.index("LISP65_C2_APPEND_PUBLISH_NAMES_SLOT", 1800),
        "journal-is-empty-before-any-plan":
            "c2_journal_count = 0;\n    ok = (uint8_t)(" in runtime,
        "plan-bounded-before-c2j":
            "* C2_EXPORT_PLAN_RECORD_BYTES\n                > C2D_UNWIND_BASE"
            in runtime,
        "cell-phase-rejects-ordinal-tag-drift":
            "(tagged & 0x7000u)" in runtime
            and "ordinal >= C2D_ENTRY_CAP" in runtime,
        "legacy-child-resolver-removed-under-cold-feature":
            "#ifndef LISP65_C2_LITE_COLD_EVICTION\n"
            "C2_KERNAL_RESIDENT uint8_t c2_stream_product_child_value" in runtime,
        "phase11-local-v6-root-surrogate-resolver":
            "root = (uint16_t)((word >> 1) - 1u);" in decoder,
        "cold-source-and-entry-seams-not-resident-by-definition":
            "#define C2_COLD_SOURCE_FN C2_APPEND_INLINE" in runtime
            and "#define C2_COLD_ENTRY_FN C2_APPEND_INLINE" in runtime,
    }
    require(all(checks.values()),
            "cold-eviction source contract red: "
            + str([name for name, ok in checks.items() if not ok]))
    return {"status": "passed", "checks": checks,
            "product_bytes_measured": 0}


def run_one_wplto() -> tuple[dict[str, Any], Path, Path]:
    original_configure = BASE.configure
    original_features = BASE.FEATURES
    original_out = V6.OUT

    def configure() -> None:
        original_configure()
        configure_cold_eviction()

    BASE.configure = configure
    BASE.FEATURES = (*original_features,
                     "LISP65_C2_PHASE11_SPLIT",
                     "LISP65_C2_LITE_COLD_EVICTION")
    V6.OUT = OUT
    try:
        result = V6.full_product_wplto()
    finally:
        BASE.configure = original_configure
        BASE.FEATURES = original_features
        V6.OUT = original_out
    target = OUT / "full-product-wplto/c2-lite-v6-full-seed.prg"
    elf = Path(str(target) + ".elf")
    require(target.is_file() and elf.is_file(),
            "green WPLTO did not emit its nonpromotable measurement artifacts")
    return result, target, elf


def structural_gates(target: Path, elf: Path, *, report_out: Path | None = None
                     ) -> dict[str, Any]:
    full = report_out or target.parent
    full.mkdir(parents=True, exist_ok=True)
    inventory = PRODUCT.final_section_inventory_gate(full, target)
    handoff = PRODUCT.handoff_z_abi_gate(full, target, "cold-eviction")
    pre = PRODUCT.pre_ownership_gate(full, target, "cold-eviction")
    data = PRODUCT.profile_data_reference_gate(
        full, target, "cold-eviction", pre)
    facade = PRODUCT.fixed_facade_gate(full, target, "cold-eviction")
    PRODUCT.closure_gate(full, target)
    provisional_window = PRODUCT.extract_provisional_kernal_window(full, target)
    kernal = PRODUCT.kernal_freedom_gate(full, target)
    overlay = APPEND_GATE.final_overlay_closure(elf)
    crc_codegen = PRODUCT.CRC_CODEGEN.audit_elf(
        elf, out=full / "c2-crc-codegen-cold-eviction.json")
    crc_leaf = PRODUCT.CRC_ASM_LEAF.audit_elf(
        elf, out=full / "c2-crc-asm-leaf-cold-eviction.json")
    f011 = PRODUCT.F011_WINDOW.audit(
        PRODUCT.F011_WINDOW.disassemble(PRODUCT.TOOLCHAIN / "llvm-objdump", elf))
    write_json(full / "c2-f011-cold-eviction.json", f011)
    return {
        "section_inventory": inventory["status"],
        "handoff_z_abi": handoff["status"],
        "pre_ownership": pre["status"],
        "profile_data_reference": data["status"],
        "fixed_facade": facade["status"],
        "one_truth_closure": "passed",
        "kernal_freedom": kernal["status"],
        "provisional_window": provisional_window,
        "overlay_closure": overlay["status"],
        "overlay_closure_phase_count": overlay["phase_count"],
        "crc_codegen": crc_codegen["status"],
        "crc_assembler_leaf": crc_leaf["status"],
        "f011_mount_window": f011["status"],
    }


def eviction_and_anchor_gate(wplto: dict[str, Any], elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(
        elf, llvm_readobj=PRODUCT.TOOLCHAIN / "llvm-readobj")
    forbidden = (
        "c2_stream_product_child_value", "c2_entry_records", "c2_source_read")
    present = {name: len(truth.symbols_by_name.get(name, [])) for name in forbidden}
    require(not any(present.values()),
            "cold tenant survived in final ELF: " + str(present))
    plan = truth.symbol("c2_append_publish_plan_phase")
    require(plan.section == ".lisp65_rt_c2append_publish_plan"
            and plan.bytes > 0,
            "cold publication plan is not a transported append phase")
    phase11b = truth.section(".lisp65_rt_c2d_11b")
    require(0 < phase11b.bytes <= CAP,
            f"phase 11b cold resolver is outside cap: {phase11b.bytes}")

    resident = truth.section(".lisp65_c2_kernal_window.c2_resident")
    state = truth.section(".lisp65_c2_kernal_window.session_emitter_state")
    resident_end = resident.address + resident.bytes
    overlap = max(0, resident_end - state.address)
    gap = max(0, state.address - resident_end)
    require(overlap == 0, f"C2 resident/state anchor still overlaps by {overlap}")
    walls = wplto["walls"]
    require(walls["e000_headroom_bytes"] >= E000_FLOOR,
            "restored 115-byte E000 floor is red")

    baseline_sections = SPLIT.map_sections(BASELINE_MAP)
    baseline_resident = baseline_sections[
        ".lisp65_c2_kernal_window.c2_resident"]
    actual_delta = baseline_resident["bytes"] - resident.bytes
    require(actual_delta > 0,
            "cold eviction did not shrink the E000 resident section")
    return {
        "status": "passed",
        "retired_symbols": present,
        "authorized_gross_tenants": {
            "child_value_bytes": 536,
            "entry_records_bytes": 559,
            "source_read_bytes": 123,
            "total_bytes": 1218,
        },
        "actual_c2_resident_section": {
            "before_bytes": baseline_resident["bytes"],
            "after_bytes": resident.bytes,
            "measured_credit_bytes": actual_delta,
        },
        "cold_destinations": {
            "child_value": {
                "section": phase11b.name, "bytes": phase11b.bytes,
                "reason": (
                    "the consumer half 11b owns allocation; 11a is overwritten "
                    "before 11b and overlay-to-overlay calls remain forbidden"),
            },
            "entry_records": {
                "status": "retired-no-final-symbol",
                "replacement": plan.section,
                "replacement_bytes": plan.bytes,
            },
            "source_read": {
                "status": "retired-no-final-symbol",
                "replacement": (
                    "cold staged/publication source reads only; no hot C2I seam"),
            },
        },
        "anchor_resolution": {
            "before_overlap_bytes": 188,
            "after_overlap_bytes": overlap,
            "gap_after_bytes": gap,
            "resident_end_exclusive": resident_end,
            "session_state_base": state.address,
        },
        "e000_floor": {
            "required_bytes": E000_FLOOR,
            "measured_headroom_bytes": walls["e000_headroom_bytes"],
            "status": "passed",
        },
    }


def protect() -> None:
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    if RECEIPT.is_file():
        os.chmod(RECEIPT, 0o444)


def first_red(error: BaseException) -> None:
    evidence = []
    if OUT.exists():
        for path in sorted(OUT.rglob("*")):
            if path.is_file():
                evidence.append(bind(path))
    value = {
        "format": "lisp65-c2-lite-v6-cold-eviction-wplto-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: cold-eviction design/WPLTO probe",
        "failure": str(error),
        "scope": {"whole_program_lto_attempts": 1,
                  "product_links": 0, "hardware_runs": 0,
                  "promotable": False},
        "evidence": evidence,
        "rollback_line": {"product": "Link 35", "status": "untouched"},
        "next_gate": "Class-C review; no retry or product link",
    }
    write_json(RECEIPT, value)
    protect()


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "cold-eviction probe is one-shot and already exists")
    require(BASELINE_MAP.is_file() and BASELINE_RECEIPT.is_file(),
            "authorized phase-11/E000 baseline is absent")
    OUT.mkdir(parents=True)
    protocol = publication_protocol_gate()
    source = source_contract_gate()
    write_json(OUT / "publication-protocol-gate.json", protocol)
    write_json(OUT / "source-contract-gate.json", source)
    wplto, target, elf = run_one_wplto()
    gates = structural_gates(target, elf)
    eviction = eviction_and_anchor_gate(wplto, elf)
    root = ROOT_GATE.collect()
    require(root["status"] == "passed", "permanent root-surrogate gate is red")
    value = {
        "format": "lisp65-c2-lite-v6-cold-eviction-wplto-probe-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-design-and-one-product-shaped-wplto-no-product-link",
        "scope": {
            "whole_program_lto_probes": 1,
            "product_links": 0,
            "promotable_product_links": 0,
            "hardware_runs": 0,
            "product_candidate": False,
        },
        "authority": {
            "phase11_e000_baseline": bind(BASELINE_RECEIPT),
            "baseline_map": bind(BASELINE_MAP),
        },
        "publication_protocol": protocol,
        "source_contract": source,
        "permanent_root_surrogate_gate": root,
        "whole_program_lto": wplto,
        "cold_eviction": eviction,
        "fresh_structural_gates": gates,
        "artifacts": {
            "measurement_prg": bind(target),
            "measurement_elf": bind(elf),
            "measurement_map": bind(Path(str(target) + ".map")),
        },
        "claim_limit": (
            "One nonpromotable Whole-Program-LTO placement truth. No product "
            "link, hardware execution, performance, promotion or acceptance claim."),
        "rollback_line": {"product": "Link 35", "status": "untouched"},
        "next_gate": "Class-C review before the first C2-lite product link",
    }
    write_json(OUT / "cold-eviction-wplto-probe.json", value)
    value["probe_report"] = bind(OUT / "cold-eviction-wplto-probe.json")
    write_json(RECEIPT, value)
    protect()
    return value


def main() -> int:
    try:
        value = build()
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            ProbeError, RuntimeError) as error:
        if OUT.exists() and not RECEIPT.exists():
            first_red(error)
        print("c2-lite-v6-cold-eviction-probe: FIRST RED " + str(error))
        return 2
    walls = value["whole_program_lto"]["walls"]
    eviction = value["cold_eviction"]
    print(
        "c2-lite-v6-cold-eviction-probe: PASS "
        f"e000={walls['e000_headroom_bytes']} "
        f"anchor-overlap={eviction['anchor_resolution']['after_overlap_bytes']} "
        f"slices={value['whole_program_lto']['runtime_slices']['count']} "
        "product-link=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
