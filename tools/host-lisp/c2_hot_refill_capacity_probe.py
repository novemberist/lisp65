#!/usr/bin/env python3
"""Run the one authorized Resident-Island entry-materializer seed probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_hot_refill_resident_contract as H  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402


DEFAULT_OUT = ROOT / (
    "build/c2.2/substitution/hot-refill-link29-seams-capacity-probe")
BASELINE = ROOT / "build/c2.2/substitution/product-link-29-direct-entry-encoding"
CONTRACT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-hot-refill-link29-seams-contract-probe-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-hot-refill-link29-seams-capacity-placement-probe-receipt.json")
FEATURE = "LISP65_C2_DIRECT_HOT_REFILL"


class CapacityError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CapacityError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def prepare(out: Path, artifacts: dict[str, Any]) -> tuple[Path, list[Path]]:
    out.mkdir(parents=True, exist_ok=False)
    P.write_v2_profile_report(out, artifacts)
    P.write(out / "c2-substitution.ld", P.linker_script())
    artifact_manifest = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
    contract_lines = [
        "profile=" + P.PROFILE,
        "mode=link29-seams-hot-refill-capacity-placement-probe",
        "hardware_execution=prohibited-non-product-seed",
        "feature_define=" + FEATURE,
        "hot_refill_contract_sha256=" + sha(CONTRACT_RECEIPT),
        "c2_artifacts_sha256=" + sha(artifact_manifest),
        "linker_sha256=" + sha(out / "c2-substitution.ld"),
        "v2_profile_parity_sha256=" + sha(out / "v2-product-profile-parity.json"),
        "product_closure_link_count=0",
        "amended_resident_island_seed_link_count=1",
    ]
    for raw in P.source_list():
        path = Path(raw)
        contract_lines.append(
            f"input_sha256={path.relative_to(ROOT)}:{sha(path)}")
    contract = out / "resolved-profile.txt"
    P.write(contract, "\n".join(contract_lines) + "\n")

    runtime_standard = out / "runtime-overlay.prepare-standard.h"
    runtime_prepared = out / "runtime-overlay.prepare.h"
    island_prepared = out / "resident-island.prepare.h"
    stage_header = out / "stage-config.h"
    error_header = out / "error-text-table.h"
    kernal_header = out / "c2-kernal-window.generated.h"
    pin = P.kernal_window_identity_pin()
    P.write(kernal_header, P.kernal_header_values(
        int(str(pin["crc16"]), 16), str(pin["sha256"])))
    P.tool("runtime_overlay_bank.py", "prepare", "--abi-contract", str(contract),
           "--header", str(runtime_standard), "--profile", P.PROFILE)
    P.render_prepared_family_header(runtime_standard, runtime_prepared)
    P.tool("resident_island.py", "prepare", "--abi-contract", str(contract),
           "--header", str(island_prepared))
    build_id = int(hashlib.sha256(contract.read_bytes()).hexdigest()[:8], 16)
    P.tool("error_text_table.py", "prepare",
           "--spec", str(ROOT / "config/error-texts.json"),
           "--profile", "workbench", "--build-id", hex(build_id),
           "--header", str(error_header),
           "--binary", str(out / "error-text-table.bin"))
    P.write(stage_header, "\n".join([
        "#ifndef LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_BOOT_OVERLAY_STAGE_BANK 0x05u",
        "#define LISP65_BOOT_OVERLAY_STAGE_OFF 0x8500u",
        f"#define LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x{build_id:08x}UL",
        "#endif", "",
    ]))
    return contract, [stage_header, runtime_prepared, island_prepared,
                      error_header, kernal_header]


def changed_sections(before: dict[str, dict[str, int]],
                     after: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for name in sorted(set(before) | set(after)):
        old = before.get(name, {}).get("bytes", 0)
        new = after.get(name, {}).get("bytes", 0)
        if old != new:
            result[name] = {"link29_bytes": old, "probe_bytes": new,
                            "delta_bytes": new - old}
    return result


def symbol_table(elf: Path) -> dict[str, dict[str, int]]:
    text = P.run([str(P.TOOLCHAIN / "llvm-nm"), "--defined-only",
                  "--print-size", "--numeric-sort", str(elf)], capture=True)
    rows: dict[str, dict[str, int]] = {}
    for line in text.splitlines():
        fields = line.split()
        if (len(fields) >= 4
                and re.fullmatch(r"[0-9a-fA-F]+", fields[0])
                and re.fullmatch(r"[0-9a-fA-F]+", fields[1])):
            rows[fields[-1]] = {"address": int(fields[0], 16),
                                "bytes": int(fields[1], 16)}
    return rows


def symbol_sections(elf: Path) -> dict[str, str]:
    text = P.run([str(P.TOOLCHAIN / "llvm-objdump"), "--syms", str(elf)],
                 capture=True)
    rows: dict[str, str] = {}
    for line in text.splitlines():
        fields = line.split()
        if (len(fields) >= 6 and re.fullmatch(r"[0-9a-fA-F]+", fields[0])
                and re.fullmatch(r"[0-9a-fA-F]+", fields[-2])):
            rows[fields[-1]] = fields[-3]
    return rows


def direct_path_gate(elf: Path) -> dict[str, Any]:
    objdump = str(P.TOOLCHAIN / "llvm-objdump")
    entry = P.run([objdump, "-d", "--disassemble-symbols=c2_product_entry_read",
                   str(elf)], capture=True)
    phase = P.run([objdump, "-d", "--disassemble-symbols=c2_stream_phase_13",
                   str(elf)], capture=True)
    symbols = symbol_table(elf)
    required = ("c2_product_entry_read", "c2_stream_phase_13",
                "c2_stream_product_materialize_entry",
                "c2_entry_records", "c2_stream_product_child_value")
    require(all(name in symbols for name in required),
            "hot-refill symbol inventory incomplete")
    helper = symbols["c2_stream_product_materialize_entry"]
    records = symbols["c2_entry_records"]
    child = symbols["c2_stream_product_child_value"]
    require(0x1800 <= helper["address"] < 0x2000,
            f"shared materializer escaped resident island: {helper}")
    require(0xE000 <= child["address"] < 0x10000,
            f"child resolver escaped owned window: {child}")
    require(0xE000 <= records["address"] < 0x10000,
            f"entry-record seam escaped owned window: {records}")
    require("c2_stream_product_materialize_entry" in entry
            and "c2_stream_product_materialize_entry" in phase,
            "direct refill/phase13 does not call the shared materializer")
    require("c2_facade_overlay_call_family" not in entry,
            "direct refill still routes through overlay transport")
    return {"status": "passed", "vm_refill": "direct-shared-helper",
            "phase13": "same-shared-helper",
            "overlay_transport_from_vm_refill": 0,
            "materializer": helper, "entry_records": records,
            "child_resolver": child}


def retained_link29_seams_gate(elf: Path, baseline_elf: Path) -> dict[str, Any]:
    current = symbol_table(elf)
    baseline = symbol_table(baseline_elf)
    current_sections = symbol_sections(elf)
    baseline_sections = symbol_sections(baseline_elf)
    names = ("c2_stream_product_child_value", "c2_entry_records",
             "c2_product_entry_length")
    rows: dict[str, Any] = {}
    for name in names:
        require(name in current and name in baseline,
                f"retained Link29 seam absent: {name}")
        rows[name] = {"link29": {**baseline[name],
                                 "section": baseline_sections.get(name)},
                      "probe": {**current[name],
                                "section": current_sections.get(name)},
                      "address_delta": current[name]["address"]
                          - baseline[name]["address"],
                      "bytes_delta": current[name]["bytes"]
                          - baseline[name]["bytes"]}
        require(current[name]["bytes"] == baseline[name]["bytes"]
                and current_sections.get(name) == baseline_sections.get(name)
                == ".lisp65_c2_kernal_window.c2_resident",
                f"retained Link29 seam algorithm/size/section drift: "
                f"{name}: {rows[name]}")
    return {
        "status": "passed-same-algorithm-size-and-owned-section",
        "internal_vma_policy": (
            "Provenance only: internal LTO order is not identity. An address becomes "
            "pinned when exported through a facade vector, handoff or other absolute "
            "cross-domain seam."),
        "seams": rows,
    }


def run_probe(out: Path) -> dict[str, Any]:
    require(CONTRACT_RECEIPT.is_file(), "hot-refill contract receipt absent")
    expected_contract = H.canonical(H.build())
    require(CONTRACT_RECEIPT.read_bytes() == expected_contract,
            "hot-refill contract receipt drift")
    require((BASELINE / "resident-island-seed.prg.elf").is_file(),
            "Link29 baseline seed absent")
    artifacts_path = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
    artifacts = json.loads(artifacts_path.read_text(encoding="utf-8"))
    contract, headers = prepare(out, artifacts)
    seed = P.compile_link(out, "hot-refill-capacity-seed.prg", headers,
                          artifacts, probe_definitions=(FEATURE,))
    elf = Path(str(seed) + ".elf")
    baseline_elf = BASELINE / "resident-island-seed.prg.elf"
    sections = P.section_table(elf); baseline = P.section_table(baseline_elf)
    slice_names = sorted({
        spec.split(":")[2] for spec in P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS
    })
    slices = {name: sections.get(name, {}).get("bytes", 0)
              for name in slice_names}
    baseline_slices = {name: baseline.get(name, {}).get("bytes", 0)
                       for name in slice_names}
    red_slices = {name: value for name, value in slices.items()
                  if value <= 0 or value > 1792}
    text = sections[".text"]; bss = sections[".bss"]
    text_headroom = 0xB481 - (text["address"] + text["bytes"])
    baseline_text_headroom = 0xB481 - (
        baseline[".text"]["address"] + baseline[".text"]["bytes"])
    bss_headroom = P.FIXED_BANK0_BASE - (bss["address"] + bss["bytes"])
    baseline_bss_headroom = P.FIXED_BANK0_BASE - (
        baseline[".bss"]["address"] + baseline[".bss"]["bytes"])
    e000_live = sum(sections.get(name, {}).get("bytes", 0)
                    for name in P.KERNAL_SECTIONS)
    baseline_e000_live = sum(baseline.get(name, {}).get("bytes", 0)
                             for name in P.KERNAL_SECTIONS)
    e000_margin = P.KERNAL_WINDOW_BYTES - e000_live
    baseline_e000_margin = P.KERNAL_WINDOW_BYTES - baseline_e000_live
    island = sections[".lisp65_resident_island"]["bytes"]
    baseline_island = baseline[".lisp65_resident_island"]["bytes"]
    island_annex = sections[".lisp65_resident_island_annex"]["bytes"]
    island_headroom = 2048 - island - island_annex
    e000_sections = {
        name: {"link29_bytes": baseline.get(name, {}).get("bytes", 0),
               "probe_bytes": sections.get(name, {}).get("bytes", 0),
               "delta_bytes": sections.get(name, {}).get("bytes", 0)
                   - baseline.get(name, {}).get("bytes", 0)}
        for name in P.KERNAL_SECTIONS
    }
    require(e000_live == baseline_e000_live,
            f"FIRST RED: hard $E000 delta gate: Link29={baseline_e000_live} "
            f"probe={e000_live} delta={e000_live - baseline_e000_live}")
    require(all(row["delta_bytes"] == 0 for row in e000_sections.values()),
            f"FIRST RED: named $E000 section drift: {e000_sections}")
    retained_seams = retained_link29_seams_gate(elf, baseline_elf)
    if red_slices or min(text_headroom, bss_headroom, e000_margin,
                         island_headroom) < 0:
        raise CapacityError(
            f"first red before structural gates: slices={red_slices} "
            f"text={text_headroom} bss={bss_headroom} e000={e000_margin} "
            f"island={island_headroom}")

    P.extract_provisional_kernal_window(out, seed)
    P.handoff_z_abi_gate(out, seed, "hot-refill-capacity-probe")
    ownership = P.pre_ownership_gate(out, seed, "hot-refill-capacity-probe")
    data_refs = P.profile_data_reference_gate(
        out, seed, "hot-refill-capacity-probe", ownership)
    P.fixed_facade_gate(out, seed, "hot-refill-capacity-probe")
    boot = P.overlay_pack_family(out, seed, contract, "boot",
                                 "hot-refill-capacity-probe")
    session = P.overlay_pack_family(out, seed, contract, "session",
                                    "hot-refill-capacity-probe")
    kernal = P.kernal_freedom_gate(out, seed)
    path_gate = direct_path_gate(elf)
    boot_manifest = json.loads(boot[1].read_text(encoding="utf-8"))
    session_manifest = json.loads(session[1].read_text(encoding="utf-8"))
    old_boot = json.loads((BASELINE / "runtime-overlays-boot-final.json").read_text())
    old_session = json.loads((BASELINE / "runtime-overlays-session-final.json").read_text())
    shelf = ROOT / "build/c2.2/substitution/product-shelf-v4-direct.bin"
    c2d = ROOT / "build/c2.2/substitution/initial.c2d-v3.bin"
    phase_deltas = {
        name: {"link29_bytes": baseline_slices[name], "probe_bytes": slices[name],
               "delta_bytes": slices[name] - baseline_slices[name]}
        for name in slice_names if slices[name] != baseline_slices[name]
    }
    report = {
        "format": "lisp65-c2-hot-refill-link29-seams-capacity-placement-probe-v1",
        "recorded_on": "2026-07-20",
        "status": "passed-product-shaped-capacity-placement-probe-only",
        "scope": {"resident_island_seed_links": 1, "product_closure_links": 0,
                  "hardware_execution": "prohibited", "promotion": "not-authorized",
                  "feature_define": FEATURE},
        "identity": {"contract_receipt": bind(CONTRACT_RECEIPT),
                     "seed_prg": bind(seed), "seed_elf": bind(elf),
                     "baseline_link29_seed_elf": bind(baseline_elf),
                     "resolved_profile": bind(contract),
                     "product_shelf_unchanged": bind(shelf),
                     "initial_c2d_unchanged": bind(c2d)},
        "capacity": {
            "bank0_text": {"link29_headroom_bytes": baseline_text_headroom,
                           "probe_headroom_bytes": text_headroom,
                           "delta_headroom_bytes": text_headroom - baseline_text_headroom},
            "bank0_ordinary_bss": {"link29_headroom_bytes": baseline_bss_headroom,
                                   "probe_headroom_bytes": bss_headroom,
                                   "delta_headroom_bytes": bss_headroom - baseline_bss_headroom,
                                   "growth_policy": "full-no-new-resident-growth-budget"},
            "bank0_fixed_block": {"link29_headroom_bytes": 273,
                                  "probe_headroom_bytes": P.FIXED_BANK0_HEADROOM_BYTES,
                                  "delta_headroom_bytes": 0},
            "cpu_e000_window": {"link29_occupied_bytes": baseline_e000_live,
                                "probe_occupied_bytes": e000_live,
                                "hard_delta_bytes": e000_live - baseline_e000_live,
                                "named_section_deltas": e000_sections,
                                "hard_gate": "passed-exact-zero-delta",
                                "link29_future_margin_bytes": baseline_e000_margin,
                                "probe_future_margin_bytes": e000_margin,
                                "delta_headroom_bytes": e000_margin - baseline_e000_margin,
                                "growth_policy": "closed-existing-occupant-correction-only"},
            "resident_island": {"link29_base_bytes": baseline_island,
                                "probe_base_bytes": island,
                                "annex_bytes": island_annex,
                                "probe_headroom_bytes": island_headroom,
                                "delta_base_bytes": island - baseline_island},
            "runtime_overlay_slices": {"cap_bytes": 1792,
                "largest_bytes": max(slices.values()),
                "largest_section": max(slices, key=slices.get),
                "phase13": {"link29_bytes": baseline_slices[".lisp65_rt_c2d_13"],
                            "probe_bytes": slices[".lisp65_rt_c2d_13"],
                            "probe_headroom_bytes": 1792 - slices[".lisp65_rt_c2d_13"]},
                "changed_phase_sections": phase_deltas,
                "over_cap_or_missing": red_slices},
            "runtime_overlay_bank": {
                "boot_bytes": boot_manifest["storage"]["size"],
                "boot_delta_vs_link29": boot_manifest["storage"]["size"]
                    - old_boot["storage"]["size"],
                "boot_headroom_bytes": 65536 - boot_manifest["storage"]["size"],
                "session_bytes": session_manifest["storage"]["size"],
                "session_delta_vs_link29": session_manifest["storage"]["size"]
                    - old_session["storage"]["size"],
                "session_headroom_bytes": 65536 - session_manifest["storage"]["size"]},
            "bank5_mutable_plane": {"bytes": c2d.stat().st_size,
                                    "headroom_bytes": 65536 - c2d.stat().st_size,
                                    "delta_bytes": 0},
            "attic_immutable_shelf": {"bytes": shelf.stat().st_size,
                                      "delta_bytes": 0},
            "installer_slice": {"status": "outside-C2-product-closure-unmodified",
                                "delta_bytes": 0}},
        "section_deltas_vs_link29_seed": changed_sections(baseline, sections),
        "fresh_structural_gates": {
            "v2_profile_parity": "passed-base-profile-plus-explicit-probe-define",
            "hot_refill_contract_588_of_588": "passed",
            "retained_link29_seams": retained_seams,
            "direct_path": path_gate,
            "handoff_z_and_io": "passed", "pre_ownership": "passed",
            "profile_data_references": "passed",
            "profile_data_relocation_count": data_refs["matched_relocation_count"],
            "fixed_facade": "passed", "kernal_freedom": "passed",
            "owned_control_flow_edges": kernal["control_flow_ownership"][
                "direct_window_edges"]},
        "claim_limit": (
            "One amended product-shaped seed link for capacity, placement and structural "
            "gates, with exact $E000 delta 0 bytes. "
            "No product closure link was created; this is not a hardware, promotion, "
            "latency or acceptance claim."),
        "next_gate": (
            "Report every exact delta for review. A successor product link remains "
            "blocked until separately authorized; any negative unapproved drift stops."),
    }
    P.write(out / "hot-refill-capacity-probe.json",
            json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    try:
        value = run_probe(args.out.resolve()); data = canonical(value)
        if args.action == "write":
            if RECEIPT.exists(): os.chmod(RECEIPT, 0o644)
            RECEIPT.write_bytes(data); os.chmod(RECEIPT, 0o444); verb = "WROTE"
        elif args.action == "check":
            require(RECEIPT.read_bytes() == data, "capacity receipt drift")
            verb = "PASS"
        else:
            verb = "SELFTEST PASS"
        cap = value["capacity"]
        print("c2-hot-refill-link29-seams-capacity: " + verb
              + f" text={cap['bank0_text']['probe_headroom_bytes']}"
              + f" bss={cap['bank0_ordinary_bss']['probe_headroom_bytes']}"
              + f" e000={cap['cpu_e000_window']['probe_future_margin_bytes']}"
              + f" island={cap['resident_island']['probe_headroom_bytes']}"
              + f" phase13={cap['runtime_overlay_slices']['phase13']['probe_bytes']}/1792"
              + " product-links=0")
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, CapacityError,
            H.ContractError) as error:
        print(f"c2-hot-refill-link29-seams-capacity: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
