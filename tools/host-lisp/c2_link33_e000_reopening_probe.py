#!/usr/bin/env python3
"""Run the sole owner-authorized Link-33 formal-E000-reopening probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_hot_refill_capacity_probe as HOT  # noqa: E402
import c2_link33_coordinated_residency_probe as OLD  # noqa: E402
import c2_nested_append_v5_prelink as PRE  # noqa: E402
import c2_preinstall_island_guard as INSTALL  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402


OUT = ROOT / "build/c2.2/substitution/link33-e000-reopening-placement-probe"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-e000-reopening-placement-probe-receipt.json")
PLAN = ROOT / "docs/planning/c2.2-link33-coordinated-residency-plan.md"
CONTRACT = ROOT / "config/c2-kernal-unmap-contract.json"
CONTRACT_DOC = ROOT / "docs/planning/c2.2-kernal-unmap-contract.md"
BASELINE_MAP = ROOT / (
    "build/c2.2/substitution/link33-coordinated-residency-probe/"
    "coordinated-residency-seed.prg.map")
BASELINE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-coordinated-residency-placement-probe-receipt.json")
LINK32 = ROOT / "build/c2.2/substitution/product-link-32-preinstall-island-guard"
LINK32_SHA = "189548ea52b9af748217a0da94b7dc1d5daa5f17d190f5817f2fb4af486a676a"
FEATURES = (*OLD.FEATURES, "LISP65_C2_E000_REOPEN")
SLICES = OLD.SLICES
CAP = 1792
TEXT_SYMBOLS = ("c2_abort_driver", "c2_facade_target_c2_dma")
ISLAND_SYMBOLS = (
    "vm_runtime_overlay_transaction_begin",
    "vm_runtime_overlay_transaction_end",
    "vm_runtime_overlay_exec_batch_island",
)
EXPECTED_SYMBOL_SECTIONS = {
    "c2_abort_driver": ".lisp65_c2_kernal_window.reopen_gap1",
    "c2_facade_target_c2_dma": ".lisp65_c2_kernal_window.reopen_gap2",
    "vm_runtime_overlay_transaction_begin": (
        ".lisp65_c2_kernal_window.reopen_gap0"),
    "vm_runtime_overlay_transaction_end": (
        ".lisp65_c2_kernal_window.reopen_gap1"),
    "vm_runtime_overlay_exec_batch_island": (
        ".lisp65_c2_kernal_window.reopen_gap1"),
    "c2_facade_runtime_overlay_exec": ".lisp65_c2_host_facade_extension",
}


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def configure() -> None:
    P.configure_append_slices(SLICES)
    P.configure_session_emitter_state(10)
    P.configure_e000_reopening()
    require(len(P.C2_APPEND_SLICES) == 21,
            "formal-reopening append ABI drift")


def prepare(out: Path) -> tuple[dict[str, object], list[Path], Path]:
    configure()
    manifest = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
    artifacts = json.loads(manifest.read_text(encoding="utf-8"))
    out.mkdir(parents=True)
    P.write_v2_profile_report(out, artifacts)
    P.write(out / "c2-substitution.ld", P.linker_script())
    lines = [
        "profile=" + P.PROFILE,
        "mode=link33-formal-e000-reopening-whole-program-placement-probe",
        "product_candidate=false",
        "hardware_execution=prohibited",
        "product_closure_link_count=0",
        "whole_program_lto_seed_attempt_count=1",
        "whole_program_lto_capacity_measurement=required",
        "object_section_sums=attribution-only-not-capacity-evidence",
        "feature_defines=" + ",".join(FEATURES),
        "append_slice_count=" + str(len(SLICES)),
        "session_emitter_cpu_state_bytes=10",
        "formal_e000_reopening_debit_cap_bytes=450",
        "formal_e000_reopening_third_opening=forbidden",
        "formal_e000_reopening_future_growth=automatic-MUST-SHOULD-triage",
        "link32_rollback_sha256=" + LINK32_SHA,
        "c2_artifacts_sha256=" + sha(manifest),
        "linker_sha256=" + sha(out / "c2-substitution.ld"),
        "plan_sha256=" + sha(PLAN),
        "contract_sha256=" + sha(CONTRACT),
        "contract_doc_sha256=" + sha(CONTRACT_DOC),
    ]
    for source in P.source_list():
        item = Path(source)
        lines.append(
            f"input_sha256={item.relative_to(ROOT)}:{sha(item)}")
    resolved = out / "resolved-profile.txt"
    P.write(resolved, "\n".join(lines) + "\n")

    standard = out / "runtime-overlay.prepare-standard.h"
    runtime = out / "runtime-overlay.prepare.h"
    island = out / "resident-island.prepare.h"
    stage = out / "stage-config.h"
    errors = out / "error-text-table.h"
    window = out / "c2-kernal-window.generated.h"
    P.tool("runtime_overlay_bank.py", "prepare", "--abi-contract", str(resolved),
           "--header", str(standard), "--profile", P.PROFILE)
    P.render_prepared_family_header(standard, runtime)
    P.tool("resident_island.py", "prepare", "--abi-contract", str(resolved),
           "--header", str(island))
    build_id = int(sha(resolved)[:8], 16)
    P.tool("error_text_table.py", "prepare",
           "--spec", str(ROOT / "config/error-texts.json"),
           "--profile", "workbench", "--build-id", hex(build_id),
           "--header", str(errors),
           "--binary", str(out / "error-text-table.bin"))
    P.write(stage, "\n".join([
        "#ifndef LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_BOOT_OVERLAY_STAGE_BANK 0x05u",
        "#define LISP65_BOOT_OVERLAY_STAGE_OFF 0x8500u",
        f"#define LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x{build_id:08x}UL",
        "#endif", "",
    ]))
    P.write(window, P.kernal_header_values(P.KERNAL_CRC_BINDING_SENTINEL,
                                            "0" * 64))
    return artifacts, [stage, runtime, island, errors, window], resolved


def section_headrooms(sections: dict[str, dict[str, int]]) -> dict[str, int]:
    return {
        "bank0_text_headroom_bytes": (
            0xB481 - sections[".text"]["address"] - sections[".text"]["bytes"]),
        "bank0_bss_headroom_bytes": (
            P.FIXED_BANK0_BASE - sections[".bss"]["address"]
            - sections[".bss"]["bytes"]),
        "resident_island_headroom_bytes": (
            2048 - sections[".lisp65_resident_island"]["bytes"]
            - sections[".lisp65_resident_island_annex"]["bytes"]),
        "e000_headroom_bytes": (
            P.KERNAL_WINDOW_BYTES - sum(
                sections.get(name, {}).get("bytes", 0)
                for name in P.KERNAL_SECTIONS)),
    }


def purpose_gate(elf: Path, sections: dict[str, dict[str, int]]) -> dict[str, Any]:
    symbols = HOT.symbol_table(elf)
    homes = HOT.symbol_sections(elf)
    drift = {
        name: {"actual": homes.get(name), "expected": expected}
        for name, expected in EXPECTED_SYMBOL_SECTIONS.items()
        if homes.get(name) != expected
    }
    require(not drift, f"formal reopening symbol-home drift: {drift}")
    sizes = {name: symbols.get(name, {}).get("bytes", 0)
             for name in EXPECTED_SYMBOL_SECTIONS}
    require(all(sizes[name] for name in (*TEXT_SYMBOLS, *ISLAND_SYMBOLS)),
            f"formal reopening function size absent: {sizes}")
    require(sections.get(".lisp65_c2_host_facade_extension", {}).get(
        "bytes") == 3, "formal reopening facade extension is not 3 bytes")
    text_relief = sum(sizes[name] for name in TEXT_SYMBOLS)
    island_relief = sum(sizes[name] for name in ISLAND_SYMBOLS)
    debit = P.e000_reopening_debit(sections)
    require(text_relief >= 167,
            f"purpose-bound text relief {text_relief} < 167")
    require(island_relief >= 228,
            f"purpose-bound Island relief {island_relief} < 228")
    require(debit <= P.E000_REOPEN_DEBIT_CAP,
            f"formal reopening debit {debit} > 450")
    allowed = set(EXPECTED_SYMBOL_SECTIONS)
    section_members: dict[str, list[str]] = {}
    for section in P.e000_reopening_section_names():
        members = sorted(name for name, home in homes.items()
                         if home == section and name in symbols
                         and symbols[name].get("bytes", 0))
        section_members[section] = members
    unexpected = sorted({name for rows in section_members.values()
                         for name in rows} - allowed)
    require(not unexpected,
            f"unrelated formal-reopening freight: {unexpected}")
    return {
        "status": "passed-exact-purpose-bound-freight",
        "symbol_homes": {
            name: {**symbols[name], "section": homes[name]}
            for name in EXPECTED_SYMBOL_SECTIONS
        },
        "section_members": section_members,
        "bank0_text_package_bytes": text_relief,
        "resident_island_package_bytes": island_relief,
        "actual_total_debit_bytes": debit,
        "debit_cap_bytes": P.E000_REOPEN_DEBIT_CAP,
        "cap_headroom_bytes": P.E000_REOPEN_DEBIT_CAP - debit,
    }


def bind_first_red(out: Path) -> dict[str, Any]:
    """Bind the sole WPLTO attempt after its linker First Red; never retry."""
    configure()
    target = out / "e000-reopening-placement-seed.prg"
    link_map = Path(str(target) + ".map")
    stderr = Path(str(target) + ".link.stderr.txt")
    lto = Path(str(target) + ".lto.o")
    require(all(path.is_file() for path in (link_map, stderr, lto)),
            "formal reopening First-Red evidence incomplete")
    require(not target.exists() and not Path(str(target) + ".elf").exists(),
            "formal reopening First Red unexpectedly produced product bytes")
    errors = stderr.read_text(encoding="utf-8", errors="replace")
    required_errors = (
        "ordinary Bank-0 state overlaps fixed C2 state",
        "profile_rodata file range overlaps with .lisp65_c2_host_facade_extension",
        "section .bss virtual address range overlaps with .lisp65_c2_fixed_bank0",
    )
    require(all(item in errors for item in required_errors),
            "formal reopening First-Red diagnostic drift")
    sections, symbols = OLD.map_rows(link_map)
    baseline_sections, _ = OLD.map_rows(BASELINE_MAP)
    current = section_headrooms(sections)
    baseline = section_headrooms(baseline_sections)
    sizes = {name: symbols.get(name, {}).get("bytes", 0)
             for name in (*TEXT_SYMBOLS, *ISLAND_SYMBOLS)}
    text_package = sum(sizes[name] for name in TEXT_SYMBOLS)
    island_package = sum(sizes[name] for name in ISLAND_SYMBOLS)
    debit = P.e000_reopening_debit(sections)
    require(text_package >= 167 and island_package >= 228 and debit <= 450,
            "First-Red map no longer matches the authorized freight arithmetic")
    require(current == {
        "bank0_text_headroom_bytes": 41,
        "bank0_bss_headroom_bytes": -379,
        "resident_island_headroom_bytes": 7,
        "e000_headroom_bytes": 115,
    }, f"formal reopening First-Red wall measurement drift: {current}")
    value = {
        "format": "lisp65-c2-link33-formal-e000-reopening-placement-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: purpose packages fit cap but cannot close anchored ordinary BSS",
        "execution_accounting": {
            "fresh_prelink_target_compiles": 2,
            "whole_program_lto_seed_attempts": 1,
            "successful_seed_links": 0,
            "product_closure_links": 0,
            "hardware_runs": 0,
        },
        "authority": {
            "contract_input": bind(CONTRACT),
            "contract_doc_input": bind(CONTRACT_DOC),
            "plan_input": bind(PLAN),
            "debit_cap_bytes": 450,
            "third_opening": "not-attempted-and-forbidden-without-new-owner-decision",
        },
        "rollback_line": {
            "link32_product_sha256": sha(
                LINK32 / "lisp65-c2-substitution-linked.prg"),
            "expected_sha256": LINK32_SHA,
            "status": "byte-identical-untouched",
        },
        "authorized_freight_measurement": {
            "bank0_text_package": {
                "symbols": {name: sizes[name] for name in TEXT_SYMBOLS},
                "bytes": text_package,
                "minimum_bytes": 167,
                "size_gate": "passed",
            },
            "resident_island_package": {
                "symbols": {name: sizes[name] for name in ISLAND_SYMBOLS},
                "bytes": island_package,
                "minimum_bytes": 228,
                "size_gate": "passed",
            },
            "reopening_sections": {
                name: sections.get(name, {}).get("bytes", 0)
                for name in P.e000_reopening_section_names()
            },
            "actual_total_debit_bytes": debit,
            "debit_cap_bytes": 450,
            "cap_headroom_bytes": 450 - debit,
            "debit_gate": "passed",
        },
        "whole_program_capacity": {
            "baseline_coordinated_first_red": baseline,
            "formal_reopening_attempt": current,
            "headroom_deltas": {name: current[name] - baseline[name]
                                for name in current},
            "gates": {
                "bank0_text": "passed",
                "ordinary_bank0_bss": "FIRST RED",
                "resident_island": "passed",
                "e000_window": "passed-cap-but-not-contractually-bound",
            },
        },
        "root_cause": {
            "corrected_model": (
                "Ordinary BSS does not follow the movable end of .text across "
                "this cut. The handoff, facade and fixed low sections have "
                "absolute VMAs between .text and .rodata/.data/.bss, so text "
                "relief is absorbed before the fixed anchors and cannot close "
                "the independent BSS overlap."),
            "baseline_bss_bytes": baseline_sections[".bss"]["bytes"],
            "attempt_bss_bytes": sections[".bss"]["bytes"],
            "bss_size_delta_bytes": (
                sections[".bss"]["bytes"] - baseline_sections[".bss"]["bytes"]),
            "baseline_bss_headroom_bytes": baseline[
                "bank0_bss_headroom_bytes"],
            "counterfactual_if_downstream_vmas_had_not_drifted_bytes": baseline[
                "bank0_bss_headroom_bytes"],
            "additional_tool_layout_effect": (
                "The new fixed facade output also made lld advance .rodata by "
                "212 bytes and assigned an overlapping load-file range to the "
                "E000 profile data. Fixing that LMA plumbing would not cure "
                "the independent baseline BSS deficit."),
        },
        "first_red_diagnostics": list(required_errors),
        "evidence": {
            "lto_object": bind(lto),
            "map": bind(link_map),
            "link_stderr": bind(stderr),
            "resolved_profile": bind(out / "resolved-profile.txt"),
            "fresh_prelink_runtime_object": bind(
                out / "fresh-v5-prelink-gates/c2-runtime.o"),
            "fresh_prelink_interrupt_object": bind(
                out / "fresh-v5-prelink-gates/interrupt.o"),
        },
        "gate_accounting": {
            "fresh_v2_profile_parity": "passed-before-link",
            "fresh_nested_append_source_mutation_closure_b2": "passed-before-link",
            "link_capacity_and_lma": "FIRST RED",
            "post_link_structural_gates": "not-reached-not-passed",
            "final_floor": "not-bound",
        },
        "next_gate": (
            "Return to owner review. The authorized package cannot satisfy its "
            "BSS condition; no retry, product link, floor binding or hardware "
            "presmoke is permitted from this result."),
        "claim_limit": (
            "One and only owner-authorized product-shaped Whole-Program-LTO "
            "placement attempt, stopped at first linker red. No PRG/ELF, "
            "product identity, hardware, latency, promotion or release claim."),
    }
    require(not RECEIPT.exists(), "formal reopening receipt already exists")
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    protect(out)
    return value


def derived_inventory_gate(elf: Path) -> dict[str, Any]:
    """Pin the probe inventory to declared surfaces, not tool ordering."""
    sections = P.section_table(elf)
    allocated = {
        name for name, row in sections.items()
        if row["bytes"] and row["address"] != 0
    }
    runtime = {spec.split(":")[2]
               for spec in P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS}
    base = {name.strip() for name in P.FINAL_SECTION_INVENTORY_PIN.read_text(
        encoding="utf-8").splitlines()
            if name.strip() and not name.startswith("#")}
    declared_new = runtime | set(P.e000_reopening_section_names())
    unexpected_allocated = sorted(
        allocated - base - declared_new - {".lisp65_c2_host_facade_extension"})
    require(not unexpected_allocated,
            f"probe section inventory has undeclared ALLOC members: {unexpected_allocated}")
    return {
        "status": "passed-declared-allocated-membership-nonproduct-probe",
        "allocated_section_count": len(allocated),
        "declared_runtime_sections": len(runtime),
        "formal_reopening_sections": list(P.e000_reopening_section_names()),
        "unexpected_allocated_sections": [],
        "ordering": "provenance-only",
        "product_final_inventory_pin": "not-mutated-by-placement-probe",
    }


def build(out: Path) -> dict[str, Any]:
    require(out == OUT, f"probe must use {OUT}")
    require(not out.exists() and not RECEIPT.exists(),
            "formal reopening probe is one-shot and already exists")
    require(sha(LINK32 / "lisp65-c2-substitution-linked.prg") == LINK32_SHA,
            "Link-32 rollback identity drift")
    require(all(path.is_file() for path in
                (PLAN, CONTRACT, CONTRACT_DOC, BASELINE_MAP, BASELINE_RECEIPT)),
            "formal reopening prerequisites incomplete")
    baseline_receipt = json.loads(BASELINE_RECEIPT.read_text(encoding="utf-8"))
    require(str(baseline_receipt.get("status", "")).startswith("FIRST RED"),
            "coordinated residency baseline is not First Red")
    artifacts, headers, resolved = prepare(out)
    # Fresh source/target/mutation/closure/B2 checks run before the sole WPLTO
    # measurement.  They do not emit a product closure.
    fresh_prelink = PRE.check(out / "fresh-v5-prelink-gates")
    require(fresh_prelink["status"] == "passed-prelink-product-link-not-run",
            "fresh nested-append prelink is red")

    target = out / "e000-reopening-placement-seed.prg"
    P.compile_link(out, target.name, headers, artifacts,
                   probe_definitions=FEATURES, final_inventory=False)
    elf = Path(str(target) + ".elf")
    sections = P.section_table(elf)
    current = section_headrooms(sections)
    baseline_sections, _ = OLD.map_rows(BASELINE_MAP)
    baseline = section_headrooms(baseline_sections)
    require(all(value >= 0 for value in current.values()),
            f"formal reopening resident wall red: {current}")

    purpose = purpose_gate(elf, sections)
    inventory = derived_inventory_gate(elf)
    slices = {spec.split(":")[2]: sections.get(
        spec.split(":")[2], {}).get("bytes", 0)
        for spec in P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS}
    over = {name: size for name, size in slices.items()
            if size <= 0 or size > CAP}
    require(not over, f"runtime slice cap red: {over}")

    provisional = P.extract_provisional_kernal_window(out, target)
    handoff = P.handoff_z_abi_gate(out, target, "e000-reopening-probe")
    ownership = P.pre_ownership_gate(out, target, "e000-reopening-probe")
    data_refs = P.profile_data_reference_gate(
        out, target, "e000-reopening-probe", ownership)
    facade = P.fixed_facade_gate(out, target, "e000-reopening-probe")
    kernal = P.kernal_freedom_gate(out, target)
    direct = HOT.direct_path_gate(elf)
    installer = INSTALL.static_elf_gate(elf)
    overlay_graph = PRE.relocations(elf)
    overlay_graph = {name: targets for name, targets in overlay_graph.items()
                     if name.startswith(".lisp65_rt_c2append_")}
    overlay_errors = PRE.closure_errors(overlay_graph)
    require(not overlay_errors and len(overlay_graph) == len(SLICES),
            f"final append overlay closure red: {overlay_errors}")
    boot = P.overlay_pack_family(out, target, resolved, "boot", "probe")
    session = P.overlay_pack_family(out, target, resolved, "session", "probe")

    final_floor = current["e000_headroom_bytes"]
    require(final_floor == kernal["capacity"]["actual_future_margin_bytes"],
            "formal reopening floor disagrees with KERNAL gate")
    value = {
        "format": "lisp65-c2-link33-formal-e000-reopening-placement-probe-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-one-whole-program-placement-probe-product-link-not-run",
        "execution_accounting": {
            "whole_program_lto_seed_attempts": 1,
            "successful_seed_links": 1,
            "product_closure_links": 0,
            "hardware_runs": 0,
        },
        "authority": {
            "contract": bind(CONTRACT),
            "contract_doc": bind(CONTRACT_DOC),
            "plan": bind(PLAN),
            "debit_cap_bytes": 450,
            "third_opening": "forbidden",
        },
        "rollback_line": {
            "link32_product_sha256": LINK32_SHA,
            "status": "untouched",
        },
        "purpose_binding": purpose,
        "whole_program_capacity": {
            "baseline_first_red": baseline,
            "probe": current,
            "headroom_deltas": {name: current[name] - baseline[name]
                                for name in current},
            "final_e000_floor_bytes": final_floor,
            "future_resident_demand": "automatic-MUST-SHOULD-freight-triage",
            "third_opening": "forbidden",
            "largest_runtime_slice_bytes": max(slices.values()),
            "minimum_runtime_slice_headroom_bytes": CAP - max(slices.values()),
            "runtime_overlay_bank": {
                "boot_bytes": boot[0].stat().st_size,
                "boot_headroom_bytes": 65536 - boot[0].stat().st_size,
                "session_bytes": session[0].stat().st_size,
                "session_headroom_bytes": 65536 - session[0].stat().st_size,
            },
        },
        "fresh_gates": {
            "v2_profile_parity": "passed-bidirectional",
            "nested_append_target_source_mutation_and_b2": fresh_prelink["status"],
            "runtime_slice_caps": "passed",
            "append_overlay_closure": "passed",
            "derived_nonproduct_section_inventory": inventory,
            "lto_partition_metadata": "passed",
            "handoff_z_and_io": handoff["status"],
            "pre_ownership": ownership["status"],
            "profile_data_references": data_refs["status"],
            "fixed_facade": facade["status"],
            "kernal_freedom": kernal["status"],
            "hot_refill_single_materializer": direct["status"],
            "preinstall_island_closure": installer["status"],
        },
        "provisional_window": provisional,
        "probe_identity": {
            "prg": bind(target),
            "elf": bind(elf),
            "lto_object": bind(Path(str(target) + ".lto.o")),
            "map": bind(Path(str(target) + ".map")),
            "resolved_profile": bind(resolved),
        },
        "next_gate": (
            "The owner-authorized fresh Link-33 successor may run only after "
            "the measured final floor and product inventory pin are bound. "
            "It must rerun every product identity, capacity and structural gate."),
        "claim_limit": (
            "One product-shaped Whole-Program-LTO placement probe. It is not "
            "a product link, hardware acceptance, latency result, promotion or release claim."),
    }
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    return value


def protect(out: Path) -> None:
    for path in sorted(out.rglob("*"), reverse=True):
        if path.is_file():
            os.chmod(path, 0o444)
        elif path.is_dir():
            os.chmod(path, 0o555)
    os.chmod(out, 0o555)
    os.chmod(RECEIPT, 0o444)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "bind-first-red", "check"))
    args = parser.parse_args()
    try:
        if args.action == "write":
            value = build(OUT)
            protect(OUT)
        elif args.action == "bind-first-red":
            value = bind_first_red(OUT)
        else:
            require(RECEIPT.is_file(), "formal reopening receipt absent")
            value = json.loads(RECEIPT.read_text(encoding="utf-8"))
            require(str(value.get("status", "")).startswith((
                "passed-one-whole-program", "FIRST RED")),
                "formal reopening receipt status drift")
        if str(value["status"]).startswith("FIRST RED"):
            cap = value["whole_program_capacity"]["formal_reopening_attempt"]
            debit = value["authorized_freight_measurement"]
            print("c2-link33-e000-reopening-probe: FIRST RED "
                  f"debit={debit['actual_total_debit_bytes']}/450 "
                  f"text={cap['bank0_text_headroom_bytes']} "
                  f"bss={cap['bank0_bss_headroom_bytes']} "
                  f"island={cap['resident_island_headroom_bytes']} "
                  f"e000={cap['e000_headroom_bytes']} product-links=0")
        else:
            cap = value["whole_program_capacity"]
            debit = value["purpose_binding"]
            print("c2-link33-e000-reopening-probe: PASS "
                  f"debit={debit['actual_total_debit_bytes']}/450 "
                  f"floor={cap['final_e000_floor_bytes']} "
                  f"text={cap['probe']['bank0_text_headroom_bytes']} "
                  f"bss={cap['probe']['bank0_bss_headroom_bytes']} "
                  f"island={cap['probe']['resident_island_headroom_bytes']} "
                  "product-links=0 hardware=not-run")
        return 0
    except Exception as exc:
        print(f"c2-link33-e000-reopening-probe: FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
