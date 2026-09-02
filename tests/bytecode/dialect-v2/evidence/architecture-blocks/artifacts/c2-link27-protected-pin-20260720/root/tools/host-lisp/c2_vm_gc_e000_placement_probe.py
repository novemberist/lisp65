#!/usr/bin/env python3
"""Bounded non-product placement probe for the Link-26 VM/GC corrections."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
LINK_TOOL = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
SPEC = importlib.util.spec_from_file_location("c2_link", LINK_TOOL)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load C2 product-link implementation")
c2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c2)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def symbol_sizes(elf: Path) -> dict[str, dict[str, int]]:
    output = c2.run([
        str(c2.TOOLCHAIN / "llvm-nm"), "--print-size", "--size-sort", str(elf)
    ], capture=True)
    result: dict[str, dict[str, int]] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 4:
            result[fields[-1]] = {
                "address": int(fields[0], 16), "bytes": int(fields[1], 16)
            }
    return result


def map_section(path: Path, section: str) -> dict[str, int]:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(
            r"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+"
            + re.escape(section) + r"$", line)
        if match:
            address = int(match.group(1), 16)
            size = int(match.group(3), 16)
            return {"address": address, "bytes": size,
                    "end_exclusive": address + size}
    raise RuntimeError(f"section absent from map {path}: {section}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--resume-existing", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()
    if not args.resume_existing and out.exists() and any(out.iterdir()):
        raise RuntimeError(f"placement probe output is not empty: {out}")
    out.mkdir(parents=True, exist_ok=True)

    manifest_path = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
    artifacts = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_window_pin = c2.kernal_window_identity_pin()
    old_window_source = c2.verify_kernal_window_pin_source(out, old_window_pin)
    contract = out / "resolved-profile.txt"
    seed = out / "placement-seed.prg"
    probe = out / "vm-gc-e000-placement-probe.prg"
    if args.resume_existing:
        required = [
            contract, seed, Path(str(seed) + ".elf"),
            probe, Path(str(probe) + ".elf"), Path(str(probe) + ".map"),
            out / "c2-product-kernal-window.bin",
        ]
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise RuntimeError(f"placement replay inputs absent: {missing}")
    else:
        c2.write(out / "c2-substitution.ld", c2.linker_script())
    if not args.resume_existing:
        contract_lines = [
            "profile=" + c2.PROFILE,
            "mode=link27-vm-gc-e000-placement-probe",
            "hardware_execution=prohibited-unpinned-window",
            "promotion=not-authorized",
            "product_candidate=false",
            "c2_artifacts_sha256=" + sha(manifest_path),
            "linker_sha256=" + sha(out / "c2-substitution.ld"),
            "slice_count_unique=" + str(c2.UNIQUE_SLICE_COUNT),
            "boot_family_slice_count=" + str(len(c2.BOOT_SLICE_SPECS)),
            "session_family_slice_count=" + str(len(c2.SESSION_SLICE_SPECS)),
            "baseline_kernal_window_identity_sha256=" + str(old_window_pin["sha256"]),
            "baseline_kernal_window_identity_crc16=" + str(old_window_pin["crc16"]),
            "product_closure_link_count=0",
            "placement_probe_link_count=1",
            "resident_island_seed_link_count=1",
        ]
        for item_name in c2.source_list():
            item = Path(item_name)
            contract_lines.append(
                f"input_sha256={item.relative_to(ROOT)}:{sha(item)}")
        c2.write(contract, "\n".join(contract_lines) + "\n")

    runtime_standard = out / "runtime-overlay.prepare-standard.h"
    runtime_prepared = out / "runtime-overlay.prepare.h"
    island_prepared = out / "resident-island.prepare.h"
    island_header = out / "resident-island.h"
    stage_header = out / "stage-config.h"
    error_header = out / "error-text-table.h"
    kernal_header = out / "c2-kernal-window.generated.h"
    if not args.resume_existing:
        c2.write(kernal_header, c2.kernal_header_values(
            int(str(old_window_pin["crc16"]), 16), str(old_window_pin["sha256"])))
        c2.tool("runtime_overlay_bank.py", "prepare", "--abi-contract", str(contract),
                "--header", str(runtime_standard), "--profile", c2.PROFILE)
        c2.render_prepared_family_header(runtime_standard, runtime_prepared)
        c2.tool("resident_island.py", "prepare", "--abi-contract", str(contract),
                "--header", str(island_prepared))
        build_id = int(hashlib.sha256(contract.read_bytes()).hexdigest()[:8], 16)
        c2.tool("error_text_table.py", "prepare",
                "--spec", str(ROOT / "config/error-texts.json"),
                "--profile", "workbench", "--build-id", hex(build_id),
                "--header", str(error_header),
                "--binary", str(out / "error-text-table.bin"))
        c2.write(stage_header, "\n".join([
            "#ifndef LISP65_WORKBENCH_OVERLAY_STAGE_H",
            "#define LISP65_WORKBENCH_OVERLAY_STAGE_H",
            "#define LISP65_BOOT_OVERLAY_STAGE_BANK 0x05u",
            "#define LISP65_BOOT_OVERLAY_STAGE_OFF 0x8500u",
            f"#define LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x{build_id:08x}UL",
            "#endif", "",
        ]))

        common = [stage_header, runtime_prepared, island_prepared, error_header]
        seed = c2.compile_link(out, "placement-seed.prg", common, artifacts)
        c2.tool("resident_island.py", "materialize", "--elf", str(seed) + ".elf",
                "--nm", str(c2.TOOLCHAIN / "llvm-nm"),
                "--objcopy", str(c2.TOOLCHAIN / "llvm-objcopy"),
                "--abi-contract", str(contract), "--header", str(island_header))
        probe = c2.compile_link(
            out, "vm-gc-e000-placement-probe.prg",
            [stage_header, runtime_prepared, island_header, error_header,
             kernal_header], artifacts)
    provisional_window = c2.extract_provisional_kernal_window(out, probe)
    handoff = c2.handoff_z_abi_gate(out, probe, "placement-probe")
    pre = c2.pre_ownership_gate(out, probe, "placement-probe")
    facade = c2.fixed_facade_gate(out, probe, "placement-probe")
    kernal = c2.kernal_freedom_gate(out, probe)

    sections = c2.section_table(Path(str(probe) + ".elf"))
    symbols = symbol_sizes(Path(str(probe) + ".elf"))
    resident = sections[".lisp65_c2_kernal_window.c2_resident"]
    baseline_elf = (
        ROOT / "build/c2.2/substitution/product-link-25-coarse-phase/"
        "lisp65-c2-substitution-linked.prg.elf")
    baseline_symbols = symbol_sizes(baseline_elf)
    baseline_sections = c2.section_table(baseline_elf)
    e000_resident_delta = (
        resident["bytes"]
        - baseline_sections[".lisp65_c2_kernal_window.c2_resident"]["bytes"])
    baseline_seed_text = map_section(
        ROOT / "build/c2.2/substitution/product-link-25-coarse-phase/"
        "resident-island-seed.prg.map", ".text")
    baseline_final_text = map_section(
        ROOT / "build/c2.2/substitution/product-link-25-coarse-phase/"
        "lisp65-c2-substitution-linked.prg.map", ".text")
    probe_seed_text = map_section(Path(str(seed) + ".map"), ".text")
    probe_final_text = map_section(Path(str(probe) + ".map"), ".text")
    named = (
        "vm_run_inner", "vm_logical_relative_target", "gc_collect",
        "c2_product_gc_mark_roots")
    measured = {name: symbols.get(name) for name in named}
    if any(value is None for value in measured.values()):
        raise RuntimeError(f"placement probe symbol absent: {measured}")
    for name in ("vm_logical_relative_target", "c2_product_gc_mark_roots"):
        address = measured[name]["address"]
        if not resident["address"] <= address < resident["address"] + resident["bytes"]:
            raise RuntimeError(f"placement probe helper escaped E000: {name}")

    current_margin = kernal["capacity"]["actual_future_margin_bytes"]
    report = {
        "format": "lisp65-c2-link27-vm-gc-e000-placement-probe-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-non-product-placement-probe-only",
        "scope": {
            "resident_island_seed_links": 1,
            "placement_probe_links": 1,
            "product_closure_links": 0,
            "link27": "not-created",
            "hardware_execution": "prohibited",
            "promotion": "not-authorized",
        },
        "identity": {
            "probe_prg": str(probe.relative_to(ROOT)),
            "probe_prg_sha256": sha(probe),
            "probe_elf_sha256": sha(Path(str(probe) + ".elf")),
            "resolved_profile_sha256": sha(contract),
            "baseline_window_pin": old_window_pin,
            "baseline_window_pin_source": old_window_source,
            "provisional_window": provisional_window,
            "identity_claim": "none; Link 27 must bind a separately pinned window",
        },
        "placement": {
            "owned_resident_section": resident,
            "symbols": measured,
            "facade_vector_count": len(c2.HOST_FACADE_SYMBOLS),
            "facade_bytes": len(c2.HOST_FACADE_SYMBOLS) * c2.HOST_FACADE_STRIDE,
            "gc_mark_vector": facade["vector_contract"]["symbols"]["c2_facade_gc_mark"],
        },
        "bank0_attribution_against_link25": {
            "ordinary_text": {
                "seed_before_bytes": baseline_seed_text["bytes"],
                "seed_probe_bytes": probe_seed_text["bytes"],
                "seed_delta_bytes": (
                    probe_seed_text["bytes"] - baseline_seed_text["bytes"]),
                "seed_headroom_to_handoff_bytes": (
                    0xb481 - probe_seed_text["end_exclusive"]),
                "final_before_bytes": baseline_final_text["bytes"],
                "final_probe_bytes": probe_final_text["bytes"],
                "final_delta_bytes": (
                    probe_final_text["bytes"] - baseline_final_text["bytes"]),
                "final_headroom_to_handoff_bytes": (
                    0xb481 - probe_final_text["end_exclusive"]),
            },
            "vm_run_inner_before_bytes": baseline_symbols["vm_run_inner"]["bytes"],
            "vm_run_inner_probe_bytes": measured["vm_run_inner"]["bytes"],
            "vm_run_inner_delta_bytes": (
                measured["vm_run_inner"]["bytes"]
                - baseline_symbols["vm_run_inner"]["bytes"]),
            "gc_collect_before_bytes": baseline_symbols["gc_collect"]["bytes"],
            "gc_collect_probe_bytes": measured["gc_collect"]["bytes"],
            "gc_collect_delta_bytes": (
                measured["gc_collect"]["bytes"]
                - baseline_symbols["gc_collect"]["bytes"]),
            "e000_vm_helper_bytes": measured["vm_logical_relative_target"]["bytes"],
            "e000_root_walker_bytes": measured["c2_product_gc_mark_roots"]["bytes"],
            "link26_first_red_reference": {
                "vm_run_inner_delta_bytes": 599,
                "gc_collect_delta_bytes": 136,
                "other_lto_delta_bytes": -2,
                "total_bytes": 733,
            },
            "deduplication_and_placement": {
                "vm_link26_resident_delta_bytes": 599,
                "vm_probe_bank0_delta_bytes": (
                    measured["vm_run_inner"]["bytes"]
                    - baseline_symbols["vm_run_inner"]["bytes"]),
                "vm_probe_e000_helper_bytes": measured["vm_logical_relative_target"]["bytes"],
                "vm_total_probe_delta_bytes": (
                    measured["vm_run_inner"]["bytes"]
                    - baseline_symbols["vm_run_inner"]["bytes"]
                    + measured["vm_logical_relative_target"]["bytes"]),
                "vm_bytes_recovered_by_shared_emission": (
                    599 - (measured["vm_run_inner"]["bytes"]
                           - baseline_symbols["vm_run_inner"]["bytes"]
                           + measured["vm_logical_relative_target"]["bytes"])),
                "gc_link26_resident_delta_bytes": 136,
                "gc_probe_bank0_delta_bytes": (
                    measured["gc_collect"]["bytes"]
                    - baseline_symbols["gc_collect"]["bytes"]),
                "gc_probe_e000_root_walker_bytes": measured["c2_product_gc_mark_roots"]["bytes"],
                "gc_checkpoint_e000_delta_bytes": -3,
                "gc_total_probe_delta_bytes": (
                    measured["gc_collect"]["bytes"]
                    - baseline_symbols["gc_collect"]["bytes"]
                    + measured["c2_product_gc_mark_roots"]["bytes"] - 3),
                "combined_ordinary_text_delta_bytes": (
                    probe_final_text["bytes"] - baseline_final_text["bytes"]),
                "combined_e000_resident_delta_bytes": e000_resident_delta,
                "facade_delta_bytes": 3,
                "combined_total_placed_delta_bytes": (
                    probe_final_text["bytes"] - baseline_final_text["bytes"]
                    + e000_resident_delta + 3),
                "combined_bytes_recovered_against_link26": (
                    733 - (probe_final_text["bytes"]
                           - baseline_final_text["bytes"]
                           + e000_resident_delta + 3)),
            },
        },
        "window_margin_trend": {
            "link19_bytes": 3417,
            "link25_bytes": 1404,
            "placement_probe_bytes": current_margin,
            "link25_to_probe_delta_bytes": current_margin - 1404,
        },
        "pre_ownership": {
            "status": pre["status"],
            "source_order": pre["source_order"],
            "helpers": pre["post_handoff_only_helpers"],
            "pre_handoff_consumer_count": pre["pre_handoff_fixed_domain"]["consumer_count"],
            "negative_matrix": pre["negative_matrix"],
        },
        "fresh_probe_gates": {
            "logical_pc_source_and_mutations": "passed-before-placement-probe",
            "gc_operational_binding_and_mutations": "passed-before-placement-probe",
            "handoff_z_and_io": handoff["status"],
            "pre_ownership": pre["status"],
            "fixed_facade_13_vectors": facade["status"],
            "owned_window_control_flow": (
                "passed" if not kernal["control_flow_ownership"]["violations"]
                else "failed"),
            "kernal_freedom": kernal["status"],
            "capacity": "passed",
        },
        "next_gate": "At most one separately authorized Link 27 with all structural, identity, capacity and closure gates fresh.",
        "claim_limit": "Owner-authorized non-product placement and capacity probe only. The provisional window is unpinned and may not be staged. It proves no product, hardware, promotion or release claim.",
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        "c2-vm-gc-e000-placement-probe: PASS "
        f"vm-bank0={report['bank0_attribution_against_link25']['vm_run_inner_delta_bytes']:+d} "
        f"gc-bank0={report['bank0_attribution_against_link25']['gc_collect_delta_bytes']:+d} "
        f"e000-helpers={measured['vm_logical_relative_target']['bytes']}+"
        f"{measured['c2_product_gc_mark_roots']['bytes']} "
        f"e000-margin={current_margin} vectors={len(c2.HOST_FACADE_SYMBOLS)} "
        "product-links=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
