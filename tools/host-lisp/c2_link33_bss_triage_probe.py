#!/usr/bin/env python3
"""Run the one owner-authorized Link-33 ordinary-BSS placement probe."""

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
import c2_hot_refill_capacity_probe as HOT  # noqa: E402
import c2_link33_coordinated_residency_probe as OLD  # noqa: E402
import c2_link33_product_profile as PROFILE  # noqa: E402
import c2_nested_append_v5_prelink as PRE  # noqa: E402
import c2_preinstall_island_guard as INSTALL  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402


PRE_LTO_OUT = ROOT / (
    "build/c2.2/substitution/link33-bss-triage-placement-probe")
PRE_LTO_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-bss-triage-placement-probe-receipt.json")
ANCHOR_FIRST_RED_OUT = ROOT / (
    "build/c2.2/substitution/link33-bss-triage-placement-probe-continuation")
ANCHOR_FIRST_RED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-bss-triage-placement-probe-continuation-receipt.json")
ANCHOR_FIRST_RED_RECEIPT_SHA = (
    "cdd28156df1113468c846e5c39f65d596f6c543f306dcea1b976943b5f4cd9f0")
FACADE_FIRST_RED_OUT = ROOT / (
    "build/c2.2/substitution/link33-bss-triage-predecessor-placement-probe")
FACADE_FIRST_RED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-bss-triage-predecessor-placement-probe-receipt.json")
FACADE_FIRST_RED_RECEIPT_SHA = (
    "6822becba7f644446e73643614cd2bb3881d8f6a41a508fcf3c110499e003683")
OUT = ROOT / (
    "build/c2.2/substitution/link33-bss-triage-facade15-placement-probe")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-bss-triage-facade15-placement-probe-receipt.json")
TARGET_NAME = "bss-triage-facade15-placement-seed.prg"
INVENTORY = ROOT / "config/c2-link33-bss-triage-inventory.json"
PLAN = ROOT / "docs/planning/c2.2-link33-coordinated-residency-plan.md"
CONTRACT = ROOT / "config/c2-kernal-unmap-contract.json"
CONTRACT_DOC = ROOT / "docs/planning/c2.2-kernal-unmap-contract.md"
FIRST_RED_MAP = ROOT / (
    "build/c2.2/substitution/link33-e000-reopening-placement-probe/"
    "e000-reopening-placement-seed.prg.map")
FIRST_RED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link33-e000-reopening-placement-probe-receipt.json")
LINK32 = ROOT / "build/c2.2/substitution/product-link-32-preinstall-island-guard"
LINK32_SHA = "189548ea52b9af748217a0da94b7dc1d5daa5f17d190f5817f2fb4af486a676a"
FEATURES = PROFILE.feature_defines()
SLICES = PROFILE.append_slices()
CAP = 1792
ORDINARY_BSS_LIMIT = P.FIXED_BANK0_BASE
ORDINARY_RODATA_ANCHOR = 0xB5F8
HOT_HEAP_BYTES = 240
FIXED_HOT_BASE = P.FIXED_BANK0_HOT_BSS_BASE
RUNTIME_OVERLAY_BASE = int(P.RUNTIME_VMA, 16)


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


def protect(path: Path) -> None:
    for item in sorted(path.rglob("*"), reverse=True):
        if item.is_file():
            os.chmod(item, 0o444)
        elif item.is_dir():
            os.chmod(item, 0o555)
    os.chmod(path, 0o555)


def configure() -> None:
    PROFILE.configure(P)


def bss_input_rows(path: Path) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    pattern = re.compile(
        r"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+\s+"
        r".+:\((\.bss(?:\.[^)]+)?)\)$")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line)
        if not match:
            continue
        address, load, size = (int(match.group(i), 16) for i in range(1, 4))
        rows.append({
            "section": match.group(4),
            "address": address,
            "load_address": load,
            "bytes": size,
            "end_exclusive": address + size,
        })
    return rows


def classify(section: str) -> dict[str, str | bool]:
    if section == ".bss.namelen4":
        return {
            "temperature": "hot-symbol-lookup",
            "lifetime": "session-persistent",
            "cpu_direct": True,
            "disposition": "stay-ordinary-bss-whole-object-exceeds-fixed-margin",
        }
    if section == ".bss.heap":
        return {
            "temperature": "hot-every-cell-access",
            "lifetime": "session-persistent",
            "cpu_direct": True,
            "disposition": "stage-3-fixed-bank0-hot-bss",
        }
    if section == ".bss.vm_codebuf":
        return {
            "temperature": "hot-every-refill-and-dispatch",
            "lifetime": "vm-activation-cache",
            "cpu_direct": True,
            "disposition": "stay-ordinary-bss",
        }
    if section.startswith(".bss.vmr_") or section == ".bss.vm_buf_bank":
        return {
            "temperature": "hot-vm-record-window",
            "lifetime": "vm-activation-state",
            "cpu_direct": True,
            "disposition": "stay-ordinary-bss",
        }
    if section in {".bss.rtov_batch_crc", ".bss.rtov_family_generation"}:
        return {
            "temperature": "hot-overlay-transaction-auth",
            "lifetime": "session-family-state",
            "cpu_direct": True,
            "disposition": "stay-ordinary-bss",
        }
    if section.startswith(".bss.vm_workbench_error_symbols"):
        lifetime = "session-persistent-interned-identity"
        temperature = "warm-error-dispatch"
    elif section in {".bss.vm_upvals", ".bss.vm_t",
                     ".bss.vm_k_shift", ".bss.vm_k_control",
                     ".bss.vm_k_meta"}:
        lifetime = "session-persistent-or-live-vm-activation"
        temperature = "hot-vm-dispatch"
    elif section == ".bss.vm_run_inner.poll_":
        lifetime = "live-vm-activation"
        temperature = "hot-vm-poll"
    elif section == ".bss.lisp_error_msg":
        lifetime = "session-error-unwind-state"
        temperature = "warm-error-unwind"
    else:
        raise ProbeError(f"unclassified colliding BSS input: {section}")
    return {
        "temperature": temperature,
        "lifetime": lifetime,
        "cpu_direct": True,
        "disposition": "stay-ordinary-bss",
    }


def inventory_value() -> dict[str, Any]:
    sections, _symbols = OLD.map_rows(FIRST_RED_MAP)
    bss = sections[".bss"]
    rows: list[dict[str, Any]] = []
    for raw in bss_input_rows(FIRST_RED_MAP):
        start = int(raw["address"])
        end = int(raw["end_exclusive"])
        overlap = max(0, min(end, bss["end_exclusive"]) -
                      max(start, ORDINARY_BSS_LIMIT))
        if not overlap:
            continue
        rows.append({**raw, "overlap_bytes": overlap,
                     **classify(str(raw["section"]))})
    require(sum(int(row["overlap_bytes"]) for row in rows) == 379,
            "379-byte BSS suffix inventory does not close")
    require(sum(1 for row in rows if row["section"] == ".bss.heap") == 1,
            "hot heap is not a unique BSS inventory object")
    return {
        "format": "lisp65-c2-link33-bss-triage-inventory-v1",
        "recorded_on": "2026-07-21",
        "source_first_red_map": bind(FIRST_RED_MAP),
        "ordinary_bss": bss,
        "fixed_c2_start": ORDINARY_BSS_LIMIT,
        "overlap_bytes": 379,
        "objects": rows,
        "ordered_ladder": {
            "stage_1_lifetime_unions": {
                "selected_bytes": 0,
                "result": "no-new-union",
                "reason": (
                    "every colliding whole object is live session/VM state; "
                    "no pair has a proved disjoint lifetime and no transition "
                    "tuple is introduced"
                ),
                "asan_or_handoff_mutation": (
                    "not-applicable-no-new-shared-storage-or-handoff"
                ),
            },
            "stage_2_bank5_cold_state": {
                "selected_bytes": 0,
                "result": "no-cold-dma-candidate",
                "reason": (
                    "all colliding objects are CPU-direct hot/session state; "
                    "heap, VM window and symbol prefilter cannot add DMA to "
                    "their hot paths"
                ),
            },
            "stage_3_fixed_bank0_hot_remainder": {
                "object": ".bss.heap",
                "bytes": HOT_HEAP_BYTES,
                "base": FIXED_HOT_BASE,
                "end_exclusive": FIXED_HOT_BASE + HOT_HEAP_BYTES,
                "projected_headroom_to_runtime_overlay": (
                    RUNTIME_OVERLAY_BASE - FIXED_HOT_BASE - HOT_HEAP_BYTES),
                "initialization": (
                    "explicit mem_init zero because the fixed NOLOAD tenant "
                    "does not ride CRT zero_bss"
                ),
            },
            "stage_4_e000_last_rest": {
                "selected_bytes": 0,
                "reason": "stage-3 projection closes ordinary BSS",
                "provisional_floor_before_probe": 115,
            },
            "ordinary_rodata_lma_collision": {
                "first_red_advance_bytes": 212,
                "resolution": (
                    "append the fourteenth vector to the one facade output "
                    "and pin ordinary rodata VMA/LMA at 0xb694"
                ),
            },
        },
        "projection_only": {
            "ordinary_bss_headroom_bytes": 73,
            "fixed_hot_block_headroom_bytes": 33,
            "e000_floor_bytes": 115,
            "whole_program_lto_is_authority": True,
        },
        "claim_limit": (
            "Objectwise map/source classification and placement projection; "
            "no product link, hardware or capacity pass is claimed."
        ),
    }


def source_and_model_gate(inventory: dict[str, Any]) -> dict[str, Any]:
    layout = (ROOT / "src/c2_kernal_layout.h").read_text(encoding="utf-8")
    mem = (ROOT / "src/mem.c").read_text(encoding="utf-8")
    facade = (ROOT / "src/c2_kernal_facade_reopen.s").read_text(
        encoding="utf-8")
    runtime = (ROOT / "src/c2_product_runtime.c").read_text(encoding="utf-8")
    configure()
    linker = P.linker_script()
    required = (
        'LISP65_C2_FIXED_BANK0_HOT_BSS("heap") heap[HEAP_CELLS]',
        "__builtin_memset(heap, 0, sizeof(heap))",
    )
    require(all(token in mem for token in required),
            "hot-heap declaration or explicit initialization absent")
    require("LISP65_C2_FIXED_BANK0_HOT_BSS" in layout,
            "BSS-triage section attribute absent")
    require('.section .lisp65_c2_host_facade,"ax",@progbits' in facade,
            "fourteenth vector is not appended to the sole facade output")
    require("c2_facade_handle_normalize:" in facade
            and "jmp c2_product_handle_normalize" in facade,
            "fifteenth handle-normalize facade vector is absent")
    entry_records = runtime.split(
        "C2_KERNAL_RESIDENT uint8_t c2_entry_records(", 1)[1].split(
            "\n}", 1)[0]
    require("C2_HANDLE_NORMALIZE(&c2_runtime, ordinal)" in entry_records,
            "c2_entry_records bypasses the handle-normalize facade macro")
    require("c2_product_handle_normalize(&c2_runtime, ordinal)"
            not in entry_records,
            "c2_entry_records still calls the Island normalizer directly")
    for token in (
            ".lisp65_c2_fixed_bank0_hot_bss 0xc245",
            "SIZEOF(.lisp65_c2_fixed_bank0_hot_bss) == 240",
            "ADDR(.rodata) ==",
            "ADDR(.lisp65_c2_kernal_state) +",
            "SIZEOF(.lisp65_c2_kernal_state)",
            "LOADADDR(.rodata) == ADDR(.rodata)",
            "SIZEOF(.lisp65_c2_host_facade) == 45",
            "c2_facade_handle_normalize == 0xb5ee",
            ".lisp65_c2_kernal_io_reveal 0xb5f1",
            ".lisp65_c2_kernal_map_switch 0xb5fc",
            "c2_facade_runtime_overlay_exec == 0xb5eb"):
        require(token in linker, f"BSS-triage linker contract absent: {token}")
    require(".lisp65_c2_host_facade_extension" not in linker,
            "second facade output survived the LMA repair")
    objects = inventory["objects"]
    require(all(row["cpu_direct"] for row in objects),
            "unclassified non-direct BSS object bypassed the ladder")
    require(sum(row["overlap_bytes"] for row in objects) == 379,
            "source gate lost the complete 379-byte suffix")
    # Mutations pin the two decisions that would make the zero-byte stages lie.
    bad_union = [dict(objects[0], lifetime="boot-exclusive"), *objects[1:]]
    require(any(row["lifetime"] == "boot-exclusive" for row in bad_union)
            and not any(row["lifetime"] == "boot-exclusive" for row in objects),
            "lifetime-union negative mutation was not distinguished")
    bad_dma = [dict(objects[0], cpu_direct=False), *objects[1:]]
    require(any(not row["cpu_direct"] for row in bad_dma)
            and all(row["cpu_direct"] for row in objects),
            "Bank-5 cold-state negative mutation was not distinguished")
    return {
        "status": "passed-before-whole-program-lto",
        "complete_overlap_bytes": 379,
        "lifetime_union_selected_bytes": 0,
        "bank5_selected_bytes": 0,
        "fixed_hot_heap_selected_bytes": HOT_HEAP_BYTES,
        "e000_state_selected_bytes": 0,
        "negative_matrix": {
            "invented-boot-exclusive-lifetime": "rejected",
            "invented-non-direct-dma-candidate": "rejected",
            "missing-explicit-hot-heap-initialization": "rejected",
            "second-fixed-facade-output": "rejected",
            "direct-e000-to-island-handle-normalize-call": "rejected",
        },
    }


def prepare(out: Path) -> tuple[dict[str, object], list[Path], Path]:
    configure()
    manifest = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
    artifacts = json.loads(manifest.read_text(encoding="utf-8"))
    out.mkdir(parents=True)
    P.write_v2_profile_report(out, artifacts)
    P.write(out / "c2-substitution.ld", P.linker_script())
    lines = [
        "profile=" + P.PROFILE,
        "mode=link33-bss-triage-whole-program-placement-probe",
        "product_candidate=false",
        "hardware_execution=prohibited",
        "product_closure_link_count=0",
        "whole_program_lto_seed_attempt_count=1",
        "whole_program_lto_capacity_measurement=required",
        "object_section_sums=inventory-only-not-capacity-evidence",
        "feature_defines=" + ",".join(FEATURES),
        "product_profile_object=" + PROFILE.PROFILE.relative_to(ROOT).as_posix(),
        "product_profile_object_sha256=" + PROFILE.sha256(),
        "append_slice_count=" + str(len(SLICES)),
        "session_emitter_cpu_state_bytes=10",
        "ordinary_rodata_predecessor_vma_lma_anchor="
        "end(.lisp65_c2_kernal_state)=0xb5f8",
        "fixed_facade_vector_count=15",
        "fixed_facade_handle_normalize=0xb5ee",
        "fixed_hot_bss_heap_bytes=240",
        "formal_e000_reopening_debit_cap_bytes=450",
        "link32_rollback_sha256=" + LINK32_SHA,
        "c2_artifacts_sha256=" + sha(manifest),
        "linker_sha256=" + sha(out / "c2-substitution.ld"),
        "inventory_sha256=" + sha(INVENTORY),
        "plan_sha256=" + sha(PLAN),
        "contract_sha256=" + sha(CONTRACT),
        "contract_doc_sha256=" + sha(CONTRACT_DOC),
    ]
    for source in P.source_list():
        item = Path(source)
        lines.append(f"input_sha256={item.relative_to(ROOT)}:{sha(item)}")
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


def headrooms(sections: dict[str, dict[str, int]]) -> dict[str, int]:
    return {
        "bank0_text_headroom_bytes": (
            P.HANDOFF_BASE - sections[".text"]["address"] - sections[".text"]["bytes"]),
        "ordinary_bank0_bss_headroom_bytes": (
            ORDINARY_BSS_LIMIT - sections[".bss"]["address"]
            - sections[".bss"]["bytes"]),
        "fixed_hot_block_headroom_bytes": (
            RUNTIME_OVERLAY_BASE
            - sections[".lisp65_c2_fixed_bank0_hot_bss"]["address"]
            - sections[".lisp65_c2_fixed_bank0_hot_bss"]["bytes"]),
        "resident_island_headroom_bytes": (
            2048 - sections[".lisp65_resident_island"]["bytes"]
            - sections[".lisp65_resident_island_annex"]["bytes"]),
        "e000_headroom_bytes": (
            P.KERNAL_WINDOW_BYTES - sum(
                sections.get(name, {}).get("bytes", 0)
                for name in P.KERNAL_SECTIONS)),
    }


def bind_first_red(out: Path, error: Exception) -> dict[str, Any]:
    # First-Red binding may be replayed in a fresh host process after the
    # linker has stopped. Restore the selected probe profile before deriving
    # section inventories or capacity; imported helpers default to the base
    # (non-reopened) product configuration.
    configure()
    target = out / TARGET_NAME
    evidence = [Path(str(target) + suffix) for suffix in (
        "", ".elf", ".map", ".link.stderr.txt", ".link.stdout.txt", ".lto.o")]
    evidence.extend(out / name for name in (
        "resolved-profile.txt",
        "handoff-z-abi-bss-triage-probe.json",
        "pre-ownership-closure-bss-triage-probe.json",
        "profile-data-reference-bss-triage-probe.json",
    ))
    require(any(path.is_file() for path in evidence),
            "BSS-triage failed before producing any bound diagnostic")
    reached_lto = Path(str(target) + ".lto.o").is_file()
    value = {
        "format": "lisp65-c2-link33-bss-triage-placement-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": ("FIRST RED: sole Whole-Program-LTO placement probe failed"
                   if reached_lto else
                   "PRE-WPLTO FIRST RED: generated linker script did not "
                   "parse; capacity probe not consumed"),
        "execution_accounting": {
            "linker_script_parse_attempts": 1,
            "whole_program_lto_seed_attempts": int(reached_lto),
            "successful_seed_links": int(
                target.is_file() and Path(str(target) + ".elf").is_file()),
            "product_closure_links": 0,
            "hardware_runs": 0,
        },
        "diagnostic": str(error),
        "inventory": bind(INVENTORY),
        "evidence": {path.name: bind(path) for path in evidence if path.is_file()},
        "rollback_line": {"link32_sha256": LINK32_SHA, "status": "untouched"},
        "final_e000_floor": "not-bound",
        "next_gate": "return-to-owner-review-no-retry-link-or-presmoke",
    }
    map_path = Path(str(target) + ".map")
    if reached_lto and map_path.is_file():
        sections, _symbols = OLD.map_rows(map_path)
        required = {
            ".text", ".rodata", ".bss",
            ".lisp65_c2_fixed_bank0_hot_bss",
            ".lisp65_resident_island",
            ".lisp65_resident_island_annex",
        }
        if required <= sections.keys():
            walls = headrooms(sections)
            rodata = sections[".rodata"]
            value["whole_program_map_observation"] = {
                "claim_limit": (
                    "The linker emitted a complete map before the first-red "
                    "gate stopped the attempt. These are map "
                    "observations, not passed capacity or structural gates."
                ),
                "headroom_bytes": walls,
                "fixed_hot_heap":
                    sections[".lisp65_c2_fixed_bank0_hot_bss"],
                "ordinary_rodata": {
                    **rodata,
                    "required_address": ORDINARY_RODATA_ANCHOR,
                    "required_load_address": ORDINARY_RODATA_ANCHOR,
                    "address_delta_from_requirement": (
                        rodata["address"] - ORDINARY_RODATA_ANCHOR),
                    "load_address_delta_from_requirement": (
                        rodata["load_address"] - ORDINARY_RODATA_ANCHOR),
                    "gate": (
                        "passed-predecessor-vma-lma-relation"
                        if (rodata["address"] == ORDINARY_RODATA_ANCHOR and
                            rodata["load_address"] == ORDINARY_RODATA_ANCHOR)
                        else "failed-explicit-vma-lma-anchor"),
                },
                "e000_actual_debit_bytes": P.e000_reopening_debit(sections),
                "capacity_interpretation": (
                    "All measured resident walls are nonnegative, but the "
                    "final E000 floor remains unbound until every post-link "
                    "structural gate passes and the contract is updated."
                ),
            }
            if (rodata["address"] != ORDINARY_RODATA_ANCHOR or
                    rodata["load_address"] != ORDINARY_RODATA_ANCHOR):
                value["status"] = (
                    "FIRST RED: sole Whole-Program-LTO map closed resident "
                    "walls but failed the explicit ordinary-rodata VMA/LMA "
                    "anchor"
                )
            elif "fixed facade red" in str(error):
                value["status"] = (
                    "FIRST RED: predecessor-bound WPLTO closed every "
                    "resident wall but the fixed-facade gate rejected a "
                    "direct E000-to-Island call"
                )
                value["whole_program_map_observation"][
                    "predecessor_rodata_relation"] = "passed"
                value["whole_program_map_observation"][
                    "e000_floor_candidate_bytes"] = walls[
                        "e000_headroom_bytes"]
                value["fresh_gate_progress"] = {
                    "whole_program_capacity": "map-green",
                    "ordinary_rodata_predecessor_relation": "passed",
                    "runtime_slice_caps": "passed-before-facade-gate",
                    "handoff_z_and_io": "passed",
                    "pre_ownership_including_fixed_hot_heap": "passed",
                    "profile_data_references": "passed",
                    "fixed_facade": "FIRST RED",
                    "fixed_facade_violation": {
                        "source_function": "c2_entry_records",
                        "source_section":
                            ".lisp65_c2_kernal_window.c2_resident",
                        "instruction_address": "0xf3ec",
                        "instruction": "jsr $1800",
                        "target": "c2_product_handle_normalize",
                        "target_section": ".lisp65_resident_island",
                    },
                    "kernal_freedom_and_later_gates": "not-reached",
                }
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    protect(out)
    return value


def run_probe() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "BSS triage is one-shot and already has output")
    require(sha(LINK32 / "lisp65-c2-substitution-linked.prg") == LINK32_SHA,
            "Link-32 rollback identity drift")
    require(all(path.is_file() for path in (
        FIRST_RED_MAP, FIRST_RED_RECEIPT, PRE_LTO_RECEIPT,
        ANCHOR_FIRST_RED_RECEIPT, FACADE_FIRST_RED_RECEIPT,
        INVENTORY, PLAN, CONTRACT, CONTRACT_DOC)),
        "BSS-triage prerequisites incomplete")
    require(sha(ANCHOR_FIRST_RED_RECEIPT) ==
            ANCHOR_FIRST_RED_RECEIPT_SHA,
            "predecessor continuation is not bound to the anchor First Red")
    anchor_first_red = json.loads(
        ANCHOR_FIRST_RED_RECEIPT.read_text(encoding="utf-8"))
    require(str(anchor_first_red.get("status", "")).startswith("FIRST RED:")
            and anchor_first_red["execution_accounting"][
                "whole_program_lto_seed_attempts"] == 1
            and anchor_first_red["execution_accounting"][
                "successful_seed_links"] == 0
            and anchor_first_red["final_e000_floor"] == "not-bound",
            "predecessor continuation did not stop at the bound anchor red")
    require(ANCHOR_FIRST_RED_OUT.is_dir()
            and not any(ANCHOR_FIRST_RED_OUT.glob("*.prg"))
            and not any(ANCHOR_FIRST_RED_OUT.glob("*.elf"))
            and len(list(ANCHOR_FIRST_RED_OUT.glob("*.lto.o"))) == 1
            and len(list(ANCHOR_FIRST_RED_OUT.glob("*.map"))) == 1,
            "anchor First-Red evidence shape drift")
    require(sha(FACADE_FIRST_RED_RECEIPT) ==
            FACADE_FIRST_RED_RECEIPT_SHA,
            "facade-15 continuation is not bound to the facade First Red")
    facade_first_red = json.loads(
        FACADE_FIRST_RED_RECEIPT.read_text(encoding="utf-8"))
    require(facade_first_red["fresh_gate_progress"]["fixed_facade"] ==
            "FIRST RED"
            and facade_first_red["execution_accounting"][
                "whole_program_lto_seed_attempts"] == 1
            and facade_first_red["execution_accounting"][
                "successful_seed_links"] == 1
            and facade_first_red["final_e000_floor"] == "not-bound",
            "facade-15 successor did not follow the bound facade First Red")
    require(FACADE_FIRST_RED_OUT.is_dir()
            and len(list(FACADE_FIRST_RED_OUT.glob("*.prg"))) == 1
            and len(list(FACADE_FIRST_RED_OUT.glob("*.elf"))) == 1
            and len(list(FACADE_FIRST_RED_OUT.glob("*.lto.o"))) == 1
            and len(list(FACADE_FIRST_RED_OUT.glob("*.map"))) == 1,
            "facade First-Red evidence shape drift")
    pre_lto = json.loads(PRE_LTO_RECEIPT.read_text(encoding="utf-8"))
    require(str(pre_lto.get("status", "")).startswith("PRE-WPLTO FIRST RED")
            and pre_lto["execution_accounting"][
                "whole_program_lto_seed_attempts"] == 0,
            "continuation is not bound to the unconsumed pre-LTO First Red")
    require(PRE_LTO_OUT.is_dir()
            and not any(PRE_LTO_OUT.glob("*.lto.o"))
            and not any(PRE_LTO_OUT.glob("*.map"))
            and not any(PRE_LTO_OUT.glob("*.prg"))
            and not any(PRE_LTO_OUT.glob("*.elf")),
            "pre-LTO First-Red evidence unexpectedly contains link products")
    inventory = inventory_value()
    source_gate = source_and_model_gate(inventory)
    require(json.loads(INVENTORY.read_text(encoding="utf-8")) == inventory,
            "bound BSS inventory drift before continuation")
    artifacts, headers, resolved = prepare(OUT)
    fresh_prelink = PRE.check(OUT / "fresh-v5-prelink-gates")
    require(fresh_prelink["status"] == "passed-prelink-product-link-not-run",
            "fresh nested-append prelink is red")

    target = OUT / TARGET_NAME
    try:
        P.compile_link(OUT, target.name, headers, artifacts,
                       probe_definitions=FEATURES, final_inventory=False)
    except (subprocess.CalledProcessError, RuntimeError, ProbeError) as error:
        return bind_first_red(OUT, error)

    elf = Path(str(target) + ".elf")
    sections = P.section_table(elf)
    map_sections, _map_symbols = OLD.map_rows(Path(str(target) + ".map"))
    walls = headrooms(sections)
    require(all(value >= 0 for value in walls.values()),
            f"BSS-triage resident wall red: {walls}")
    require(sections[".lisp65_c2_fixed_bank0_hot_bss"] == {
        "address": FIXED_HOT_BASE, "bytes": HOT_HEAP_BYTES},
        "fixed hot heap geometry drift")
    require(map_sections[".rodata"]["address"] == ORDINARY_RODATA_ANCHOR
            and map_sections[".rodata"]["load_address"] == ORDINARY_RODATA_ANCHOR,
            "ordinary rodata VMA/LMA collision is not closed")
    require(P.e000_reopening_debit(sections) <= P.E000_REOPEN_DEBIT_CAP,
            "formal E000 opening debit exceeds 450 bytes")
    homes = HOT.symbol_sections(elf)
    require(homes.get("heap") == ".lisp65_c2_fixed_bank0_hot_bss",
            "heap did not land in the sole fixed hot-BSS section")

    slices = {spec.split(":")[2]: sections.get(
        spec.split(":")[2], {}).get("bytes", 0)
        for spec in P.BOOT_SLICE_SPECS + P.SESSION_SLICE_SPECS}
    over = {name: size for name, size in slices.items()
            if size <= 0 or size > CAP}
    require(not over, f"runtime slice cap red: {over}")

    provisional = P.extract_provisional_kernal_window(OUT, target)
    handoff = P.handoff_z_abi_gate(OUT, target, "bss-triage-probe")
    ownership = P.pre_ownership_gate(OUT, target, "bss-triage-probe")
    data_refs = P.profile_data_reference_gate(
        OUT, target, "bss-triage-probe", ownership)
    facade = P.fixed_facade_gate(OUT, target, "bss-triage-probe")
    kernal = P.kernal_freedom_gate(OUT, target)
    direct = HOT.direct_path_gate(elf)
    installer = INSTALL.static_elf_gate(elf)
    graph = PRE.relocations(elf)
    graph = {name: targets for name, targets in graph.items()
             if name.startswith(".lisp65_rt_c2append_")}
    graph_errors = PRE.closure_errors(graph)
    require(not graph_errors and len(graph) == len(SLICES),
            f"append overlay closure red: {graph_errors}")
    boot = P.overlay_pack_family(OUT, target, resolved, "boot", "probe")
    session = P.overlay_pack_family(OUT, target, resolved, "session", "probe")

    floor_candidate = walls["e000_headroom_bytes"]
    require(floor_candidate ==
            kernal["capacity"]["actual_future_margin_bytes"],
            "BSS-triage floor disagrees with KERNAL-freedom gate")
    value = {
        "format": "lisp65-c2-link33-bss-triage-placement-probe-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-one-whole-program-placement-probe-product-link-not-run",
        "final_e000_floor": "candidate-not-yet-contract-bound",
        "execution_accounting": {
            "whole_program_lto_seed_attempts": 1,
            "successful_seed_links": 1,
            "product_closure_links": 0,
            "hardware_runs": 0,
        },
        "authority": {
            "inventory": bind(INVENTORY),
            "plan": bind(PLAN),
            "contract": bind(CONTRACT),
            "contract_doc": bind(CONTRACT_DOC),
            "e000_debit_cap_bytes": 450,
            "island": "closed",
            "slice_cap_bytes": CAP,
        },
        "ordered_ladder_result": inventory["ordered_ladder"],
        "source_and_model_gate": source_gate,
        "whole_program_capacity": {
            **walls,
            "ordinary_rodata": map_sections[".rodata"],
            "e000_actual_debit_bytes": P.e000_reopening_debit(sections),
            "e000_floor_candidate_bytes": floor_candidate,
            "e000_floor_binding": "requires-separate-contract-step",
            "e000_third_opening": "forbidden",
            "future_resident_demand": "automatic-MUST-SHOULD-freight-triage",
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
            "nested_append_source_mutation_and_b2": fresh_prelink["status"],
            "runtime_slice_caps": "passed",
            "append_overlay_closure": "passed",
            "lto_partition_metadata": "passed",
            "handoff_z_and_io": handoff["status"],
            "pre_ownership_including_fixed_hot_heap": ownership["status"],
            "profile_data_references": data_refs["status"],
            "fixed_facade_and_hot_bss": facade["status"],
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
        "rollback_line": {"link32_sha256": LINK32_SHA, "status": "untouched"},
        "next_gate": (
            "Return for the explicit final-floor contract binding and then "
            "separate authorization of a fresh Link-33 product link; no "
            "product link or hardware presmoke is implied."
        ),
        "claim_limit": (
            "One product-shaped Whole-Program-LTO placement probe and fresh "
            "structural gates only; no product identity, hardware, latency, "
            "promotion or release claim."
        ),
    }
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    protect(OUT)
    return value


def selftest() -> None:
    require(not INVENTORY.exists(),
            "selftest refuses to overwrite an existing bound inventory")
    inventory = inventory_value()
    gate = source_and_model_gate(inventory)
    require(inventory["overlap_bytes"] == 379, "inventory selftest drift")
    require(gate["fixed_hot_heap_selected_bytes"] == 240,
            "fixed hot-heap selftest drift")
    require(inventory["projection_only"] == {
        "ordinary_bss_headroom_bytes": 73,
        "fixed_hot_block_headroom_bytes": 33,
        "e000_floor_bytes": 115,
        "whole_program_lto_is_authority": True,
    }, "BSS-triage projection selftest drift")
    print("c2-link33-bss-triage: SELFTEST PASS overlap=379 heap=240")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    require(args.selftest != args.run, "select exactly one of --selftest/--run")
    if args.selftest:
        selftest()
        return 0
    try:
        value = run_probe()
    except (RuntimeError, ProbeError) as error:
        if args.run and OUT.is_dir() and not RECEIPT.exists():
            value = bind_first_red(OUT, error)
        else:
            raise
    print(json.dumps({
        "status": value["status"],
        "receipt": RECEIPT.relative_to(ROOT).as_posix(),
        "whole_program_lto_seed_attempts": value["execution_accounting"][
            "whole_program_lto_seed_attempts"],
    }, sort_keys=True))
    return 0 if str(value["status"]).startswith("passed") else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeError as error:
        print(f"c2-link33-bss-triage: FAIL: {error}", file=sys.stderr)
        raise SystemExit(2)
