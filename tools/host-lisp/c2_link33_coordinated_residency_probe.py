#!/usr/bin/env python3
"""Run the one authorized Link-33 coordinated residency placement probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_product_substitution_link as P  # noqa: E402


DEFAULT_OUT = ROOT / "build/c2.2/substitution/link33-coordinated-residency-probe"
DEFAULT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-coordinated-residency-placement-probe-receipt.json")
LINK32 = ROOT / "build/c2.2/substitution/product-link-32-preinstall-island-guard"
LINK33_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link33-seed-capacity-first-red-receipt.json")
LINK33_FIRST_RED_MAP = ROOT / (
    "build/c2.2/substitution/product-link-33-nested-append-v5/"
    "resident-island-seed.prg.map")
PLAN = ROOT / "docs/planning/c2.2-link33-coordinated-residency-plan.md"
LINK32_PRODUCT_SHA = "189548ea52b9af748217a0da94b7dc1d5daa5f17d190f5817f2fb4af486a676a"
LINK33_FIRST_RED_SHA = "efc6746c4914097ec76ca2516c59581508f9cbf71450f215d213b4bbad711480"
FEATURES = (
    "LISP65_C2_DIRECT_HOT_REFILL",
    "LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH",
    "LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND",
    "LISP65_C2_TRANSACTION_AUTH",
    "LISP65_C2_TRANSACTION_AUTH_NOINLINE",
    "LISP65_C2_NESTED_APPEND_V5",
    "LISP65_C2_RESIDENCY_TRIAGE",
)
SLICES = P.C2_APPEND_V5_SLICES + [
    ("abort_control", "c2_append_abort_control_phase")]
CAP = 1792


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


def map_rows(path: Path) -> tuple[dict[str, dict[str, int]],
                                  dict[str, dict[str, int]]]:
    sections: dict[str, dict[str, int]] = {}
    symbols: dict[str, dict[str, int]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(
            r"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+"
            r"([^\s].*)$", line)
        if not match:
            continue
        address, load, size = (int(match.group(i), 16) for i in range(1, 4))
        name = match.group(4).strip()
        row = {"address": address, "load_address": load, "bytes": size,
               "end_exclusive": address + size}
        if name.startswith(".") and ":(" not in name and " " not in name:
            sections.setdefault(name, row)
        elif re.fullmatch(r"[A-Za-z_.$][A-Za-z0-9_.$]*", name):
            symbols.setdefault(name, row)
    return sections, symbols


def align256(value: int) -> int:
    return (value + 255) & ~255


def projected_family_image_bytes(
        specs: list[str], sections: dict[str, dict[str, int]]) -> int:
    """Apply the L65R-v1 pack geometry to one Whole-Program map.

    This deliberately does not pack an image: a failed placement seed has no
    product ELF.  It does, however, contain every final-LTO slice size needed
    for the exact catalog/payload-alignment arithmetic.
    """
    parsed = sorted((int(spec.split(":", 1)[0]), spec.split(":")[2])
                    for spec in specs)
    cursor = align256(32 + len(parsed) * 32)
    for _slot, section in parsed:
        require(section in sections,
                f"Whole-Program map lacks runtime slice {section}")
        cursor = align256(cursor)
        cursor += sections[section]["bytes"]
    return cursor


def resident_wall_snapshot(
        sections: dict[str, dict[str, int]]) -> dict[str, int]:
    text = sections[".text"]
    bss = sections[".bss"]
    island = sections[".lisp65_resident_island"]
    annex = sections[".lisp65_resident_island_annex"]
    e000_bytes = sum(sections.get(name, {}).get("bytes", 0)
                     for name in P.KERNAL_SECTIONS)
    return {
        "bank0_text_headroom_bytes": P.HANDOFF_BASE - text["end_exclusive"],
        "bank0_bss_headroom_bytes": P.FIXED_BANK0_BASE - bss["end_exclusive"],
        "resident_island_headroom_bytes": (
            2048 - island["bytes"] - annex["bytes"]),
        "e000_headroom_bytes": P.KERNAL_WINDOW_BYTES - e000_bytes,
    }


def protect(path: Path) -> None:
    for item in sorted(path.rglob("*"), reverse=True):
        if item.is_file():
            os.chmod(item, 0o444)
        elif item.is_dir():
            os.chmod(item, 0o555)
    os.chmod(path, 0o555)


def prepare(out: Path) -> tuple[dict[str, object], list[Path], Path]:
    manifest_path = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
    artifacts = json.loads(manifest_path.read_text(encoding="utf-8"))
    P.configure_append_slices(SLICES)
    P.configure_session_emitter_state(10)
    out.mkdir(parents=True)
    P.write_v2_profile_report(out, artifacts)
    P.write(out / "c2-substitution.ld", P.linker_script())
    contract_lines = [
        "profile=" + P.PROFILE,
        "mode=link33-coordinated-residency-whole-program-seed",
        "product_candidate=false",
        "hardware_execution=prohibited",
        "product_closure_link_count=0",
        "resident_island_seed_link_attempt_count=1",
        "whole_program_lto_capacity_measurement=required",
        "object_section_sums=attribution-only-not-capacity-evidence",
        "feature_defines=" + ",".join(FEATURES),
        "append_slice_count=" + str(len(SLICES)),
        "session_emitter_cpu_state_bytes=10",
        "session_emitter_bank5_root_bytes=336",
        "c2_artifacts_sha256=" + sha(manifest_path),
        "linker_sha256=" + sha(out / "c2-substitution.ld"),
        "plan_sha256=" + sha(PLAN),
    ]
    for source in P.source_list():
        item = Path(source)
        contract_lines.append(
            f"input_sha256={item.relative_to(ROOT)}:{sha(item)}")
    contract = out / "resolved-profile.txt"
    P.write(contract, "\n".join(contract_lines) + "\n")

    runtime_standard = out / "runtime-overlay.prepare-standard.h"
    runtime_prepared = out / "runtime-overlay.prepare.h"
    island_prepared = out / "resident-island.prepare.h"
    stage = out / "stage-config.h"
    error_header = out / "error-text-table.h"
    kernal_header = out / "c2-kernal-window.generated.h"
    P.tool("runtime_overlay_bank.py", "prepare", "--abi-contract", str(contract),
           "--header", str(runtime_standard), "--profile", P.PROFILE)
    P.render_prepared_family_header(runtime_standard, runtime_prepared)
    P.tool("resident_island.py", "prepare", "--abi-contract", str(contract),
           "--header", str(island_prepared))
    build_id = int(sha(contract)[:8], 16)
    P.tool("error_text_table.py", "prepare",
           "--spec", str(ROOT / "config/error-texts.json"),
           "--profile", "workbench", "--build-id", hex(build_id),
           "--header", str(error_header),
           "--binary", str(out / "error-text-table.bin"))
    P.write(stage, "\n".join([
        "#ifndef LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_WORKBENCH_OVERLAY_STAGE_H",
        "#define LISP65_BOOT_OVERLAY_STAGE_BANK 0x05u",
        "#define LISP65_BOOT_OVERLAY_STAGE_OFF 0x8500u",
        f"#define LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x{build_id:08x}UL",
        "#endif", "",
    ]))
    P.write(kernal_header, P.kernal_header_values(
        P.KERNAL_CRC_BINDING_SENTINEL, "0" * 64))
    return artifacts, [stage, runtime_prepared, island_prepared, error_header,
                       kernal_header], contract


def resume_setup(out: Path) -> tuple[dict[str, object], list[Path], Path]:
    """Resume only the pre-LTO missing-header setup failure."""
    target = out / "coordinated-residency-seed.prg"
    stderr = Path(str(target) + ".link.stderr.txt")
    require(stderr.is_file()
            and "c2-kernal-window.generated.h' file not found"
                in stderr.read_text(encoding="utf-8", errors="replace"),
            "resume is not the exact pre-LTO generated-header setup failure")
    require(not Path(str(target) + ".lto.o").exists()
            and not Path(str(target) + ".map").exists(),
            "resume refuses an attempt that reached Whole-Program LTO")
    manifest_path = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
    artifacts = json.loads(manifest_path.read_text(encoding="utf-8"))
    P.configure_append_slices(SLICES)
    P.configure_session_emitter_state(10)
    kernal_header = out / "c2-kernal-window.generated.h"
    P.write(kernal_header, P.kernal_header_values(
        P.KERNAL_CRC_BINDING_SENTINEL, "0" * 64))
    headers = [out / name for name in (
        "stage-config.h", "runtime-overlay.prepare.h",
        "resident-island.prepare.h", "error-text-table.h",
        "c2-kernal-window.generated.h")]
    require(all(path.is_file() for path in headers),
            "resume setup header inventory incomplete")
    contract = out / "resolved-profile.txt"
    require(contract.is_file(), "resume setup contract absent")
    return artifacts, headers, contract


def bind_existing_setup(out: Path) -> tuple[dict[str, object], list[Path], Path]:
    """Bind the exact failed Whole-Program attempt without another link."""
    P.configure_append_slices(SLICES)
    P.configure_session_emitter_state(10)
    manifest_path = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
    artifacts = json.loads(manifest_path.read_text(encoding="utf-8"))
    target = out / "coordinated-residency-seed.prg"
    required = [Path(str(target) + suffix) for suffix in (
        ".lto.o", ".map", ".link.stderr.txt", ".link.stdout.txt")]
    require(all(path.is_file() for path in required),
            "existing Whole-Program First-Red evidence incomplete")
    errors = required[2].read_text(encoding="utf-8", errors="replace")
    require("rootstack annex exceeds the fixed $2000 island limit" in errors
            and "ordinary Bank-0 state overlaps fixed C2 state" in errors,
            "existing attempt is not the coordinated-residency First Red")
    require(not target.exists() and not Path(str(target) + ".elf").exists(),
            "existing failed attempt unexpectedly produced a linked image")
    headers = [out / name for name in (
        "stage-config.h", "runtime-overlay.prepare.h",
        "resident-island.prepare.h", "error-text-table.h",
        "c2-kernal-window.generated.h")]
    contract = out / "resolved-profile.txt"
    require(all(path.is_file() for path in headers) and contract.is_file(),
            "existing Whole-Program input binding incomplete")
    return artifacts, headers, contract


def build(out: Path, receipt: Path, *, resume_pre_lto_setup: bool = False,
          bind_existing_first_red: bool = False) -> dict[str, Any]:
    require(resume_pre_lto_setup or bind_existing_first_red or not out.exists(),
            f"probe output already exists: {out}")
    require(PLAN.is_file(), "coordinated residency plan absent")
    require(sha(LINK32 / "lisp65-c2-substitution-linked.prg") == LINK32_PRODUCT_SHA,
            "Link-32 rollback identity drift")
    require(sha(LINK33_FIRST_RED) == LINK33_FIRST_RED_SHA,
            "Link-33 First-Red binding drift")
    if bind_existing_first_red:
        artifacts, headers, contract = bind_existing_setup(out)
    elif resume_pre_lto_setup:
        artifacts, headers, contract = resume_setup(out)
    else:
        artifacts, headers, contract = prepare(out)
    target = out / "coordinated-residency-seed.prg"
    completed = False
    if not bind_existing_first_red:
        try:
            P.compile_link(out, target.name, headers, artifacts,
                           probe_definitions=FEATURES, final_inventory=False)
            completed = True
        except (subprocess.CalledProcessError, RuntimeError):
            pass

    link_map = Path(str(target) + ".map")
    stderr = Path(str(target) + ".link.stderr.txt")
    lto = Path(str(target) + ".lto.o")
    require(all(path.is_file() for path in (link_map, stderr, lto)),
            "whole-program First-Red evidence incomplete")
    sections, symbols = map_rows(link_map)
    baseline_sections, _baseline_symbols = map_rows(LINK33_FIRST_RED_MAP)
    required = (".text", ".bss", ".lisp65_resident_island",
                ".lisp65_resident_island_annex",
                ".lisp65_c2_kernal_window.c2_resident",
                ".lisp65_c2_kernal_window.session_emitter_state",
                ".lisp65_c2_kernal_window.profile_rodata",
                ".lisp65_rt_c2append_abort_control")
    require(all(name in sections for name in required),
            "whole-program map lacks required placement rows")
    text = sections[".text"]
    bss = sections[".bss"]
    island = sections[".lisp65_resident_island"]
    annex = sections[".lisp65_resident_island_annex"]
    text_room = P.HANDOFF_BASE - text["end_exclusive"]
    bss_room = P.FIXED_BANK0_BASE - bss["end_exclusive"]
    island_room = 2048 - island["bytes"] - annex["bytes"]
    e000_bytes = sum(sections.get(name, {}).get("bytes", 0)
                     for name in P.KERNAL_SECTIONS)
    e000_room = P.KERNAL_WINDOW_BYTES - e000_bytes
    baseline_walls = resident_wall_snapshot(baseline_sections)
    current_walls = resident_wall_snapshot(sections)
    wall_deltas = {
        name: current_walls[name] - baseline_walls[name]
        for name in current_walls
    }
    boot_image_bytes = projected_family_image_bytes(P.BOOT_SLICE_SPECS,
                                                     sections)
    session_image_bytes = projected_family_image_bytes(P.SESSION_SLICE_SPECS,
                                                        sections)
    append_sizes = {
        name: sections.get(f".lisp65_rt_c2append_{name}", {}).get("bytes", 0)
        for name, _entry in SLICES
    }
    slice_red = {name: size for name, size in append_sizes.items()
                 if size <= 0 or size > CAP}
    wall_red = {
        name: value for name, value in {
            "bank0_text_headroom_bytes": text_room,
            "bank0_bss_headroom_bytes": bss_room,
            "resident_island_headroom_bytes": island_room,
            "e000_headroom_bytes": e000_room,
        }.items() if value < 0
    }
    # .bss follows .text in the same Bank-0 load domain.  A text evacuation
    # large enough to close the larger of those two deficits would move both
    # ends; adding the deficits would double-count that positional effect.
    coupled_text_move = max(0, -text_room, -bss_room)
    island_move = max(0, -island_room)
    coupled_e000_move = coupled_text_move + island_move
    errors = stderr.read_text(encoding="utf-8", errors="replace")
    status = ("passed-product-shaped-whole-program-placement-probe-only"
              if completed and not wall_red and not slice_red else
              "FIRST RED: coordinated residency still violates resident walls")
    value = {
        "format": "lisp65-c2-link33-coordinated-residency-placement-probe-v1",
        "recorded_on": "2026-07-20",
        "status": status,
        "scope": {
            "whole_program_lto_seed_attempts": 1,
            "successful_seed_links": int(completed),
            "product_closure_links": 0,
            "hardware_runs": 0,
            "promotion": "blocked",
        },
        "plan": bind(PLAN),
        "baseline": {
            "link32_product_sha256": LINK32_PRODUCT_SHA,
            "link33_first_red": bind(LINK33_FIRST_RED),
            "link33_first_red_map": bind(LINK33_FIRST_RED_MAP),
            "link33_first_red_wall_headrooms": baseline_walls,
        },
        "temperature_placement": {
            "c2j_abort_control": {
                "temperature": "cold-abort-only",
                "home": "new-session-overlay-plus-resident-serial-executor",
                "overlay_bytes": append_sizes["abort_control"],
                "resident_driver_bytes": symbols.get("c2_abort_driver", {}).get("bytes"),
            },
            "handle_normalization": {
                "temperature": "hot-every-dynamic-entry-lookup",
                "home": "resident-Island-unchanged",
                "bytes": symbols.get("c2_product_handle_normalize", {}).get("bytes"),
            },
            "entry_materializer": {
                "temperature": "hot-every-refill",
                "home": "resident-Island-unchanged",
                "bytes": symbols.get("c2_stream_product_materialize_entry", {}).get("bytes"),
            },
            "emitter_roots": {
                "temperature": "cold-emission-only",
                "home": "Bank-5-fixed-DMA-region",
                "base": 50416,
                "bytes": 336,
                "end_exclusive": 50752,
                "maximum_export_journal_end_exclusive": 42032,
                "c2j_base": 50752,
                "disjoint": True,
            },
            "resident_island_installer": {
                "temperature": "boot-only-root-with-shared-transport-closure",
                "boot_slice_bytes": sections.get(".lisp65_rt_island_00", {}).get("bytes"),
                "resident_anchor_bytes": symbols.get("vm_runtime_overlay_install_island", {}).get("bytes"),
                "additional_evacuation_bytes": 0,
                "finding": "payload already in Boot family; shared closure and same-VMA self-overwrite forbid moving the resident anchor",
            },
        },
        "capacity": {
            "bank0_text": {"bytes": text["bytes"], "headroom_bytes": text_room},
            "bank0_ordinary_bss": {"bytes": bss["bytes"], "headroom_bytes": bss_room},
            "resident_island": {"base_bytes": island["bytes"],
                                "annex_bytes": annex["bytes"],
                                "headroom_bytes": island_room},
            "e000": {"occupied_bytes": e000_bytes, "headroom_bytes": e000_room,
                      "growth_policy": "closed; no new tenant authorized"},
            "append_slices": {"cap_bytes": CAP, "sizes": append_sizes,
                              "over_cap_or_missing": slice_red},
            "bank5_fixed_regions": {
                "c2d_bytes": 33840,
                "maximum_export_journal_end_exclusive": 42032,
                "emitter_roots": [50416, 50752],
                "c2j": [50752, 50816],
                "unallocated_between_journal_and_roots_bytes": 8384,
            },
            "runtime_overlay_bank_projection_from_whole_program_map": {
                "claim": "exact L65R-v1 geometry over final-LTO section sizes; no image packed because the placement seed failed",
                "boot_image_bytes": boot_image_bytes,
                "boot_headroom_bytes": 65536 - boot_image_bytes,
                "session_image_bytes": session_image_bytes,
                "session_headroom_bytes": 65536 - session_image_bytes,
            },
            "headroom_delta_from_link33_first_red_bytes": wall_deltas,
            "formal_e000_reopening_lower_bound": {
                "status": "arithmetic-only; owner decision and placement proof required",
                "bank0_text_move_closing_text_and_positional_bss_bytes": coupled_text_move,
                "resident_island_move_bytes": island_move,
                "combined_move_bytes": coupled_e000_move,
                "theoretical_e000_headroom_after_move_bytes": (
                    e000_room - coupled_e000_move),
                "caveat": (
                    "Excludes alignment, facade/vector and closure effects; "
                    "no tenant or lower floor is authorized."),
            },
        },
        "first_red": {"wall_deficits": wall_red,
                      "slice_deficits": slice_red,
                      "linker_diagnostics": errors.splitlines()},
        "evidence": {"lto_object": bind(lto), "link_map": bind(link_map),
                     "link_stderr": bind(stderr), "resolved_profile": bind(contract),
                     "linker_script": bind(out / "c2-substitution.ld")},
        "process_rule": (
            "Future prelink capacity receipts require one Whole-Program-LTO dry "
            "measurement; object-section sums are attribution only."),
        "claim_limit": (
            "One owner-authorized product-shaped Whole-Program-LTO placement "
            "probe only. No product link, final Island materialization, runtime "
            "packing, publish-last binding, hardware execution or promotion."),
        "next_gate": (
            "Any remaining red returns to owner/review. Formal E000 reopening or "
            "another resident-domain change requires a new decision."),
    }
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    protect(out)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--resume-pre-lto-setup", action="store_true")
    parser.add_argument("--bind-existing-first-red", action="store_true")
    args = parser.parse_args()
    value = build(args.out.resolve(), args.receipt.resolve(),
                  resume_pre_lto_setup=args.resume_pre_lto_setup,
                  bind_existing_first_red=args.bind_existing_first_red)
    cap = value["capacity"]
    print("c2-link33-coordinated-residency-probe: " + value["status"])
    print("text={:+d} bss={:+d} island={:+d} e000={:+d}".format(
        cap["bank0_text"]["headroom_bytes"],
        cap["bank0_ordinary_bss"]["headroom_bytes"],
        cap["resident_island"]["headroom_bytes"],
        cap["e000"]["headroom_bytes"]))
    print("receipt-sha256=" + sha(args.receipt.resolve()))
    return 0 if value["status"].startswith("passed-") else 2


if __name__ == "__main__":
    raise SystemExit(main())
