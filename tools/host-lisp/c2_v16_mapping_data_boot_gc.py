#!/usr/bin/env python3
"""Close the stopped-data view and Link-82 pre-prompt GC questions.

This is a desk-only evidence builder.  It never contacts the MEGA65.  It
separates instruction identity (CPU-resolved view) from stopped-state data
identity (physical RAM below any active mapping), and binds the exact Link-82
boot allocation schedule far enough to decide whether a healthy control can
enter ``gc_collect`` before its first prompt.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
DEVICE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-romc-repaired-launch-failure-device-receipt.json")
DESK = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-romc-repaired-launch-failure-desk-closure-receipt.json")
BOOT_ORDER = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-boot-order-durable-witness-receipt.json")
PHASE_A = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-phase-a-host-reconstruction-receipt.json")
CONTROL_BOOT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-launch-boundary-control-device-receipt.json")
SUBSTITUTION = ROOT / (
    "build/c2.2/v1.2.5-candidate-product-link82/static-plane/narrow-static/"
    "product/substitution-artifacts.json")
C2D = ROOT / (
    "build/c2.2/v1.2.5-candidate-product-link82/static-plane/narrow-static/"
    "product/initial.c2d-v3.bin")
SHELF = ROOT / (
    "build/c2.2/v1.2.5-candidate-product-link82/static-plane/narrow-static/"
    "product/product-shelf-v4-direct.bin")
SOURCE = ROOT / "build/c2.3/v1.6-defstruct-phase-c/source"
SRC_MAIN = SOURCE / "src/main.c"
SRC_MEM = SOURCE / "src/mem.c"
SRC_SYMBOL = SOURCE / "src/symbol.c"
SRC_RUNTIME = SOURCE / "src/c2_product_runtime.c"
SRC_REPL = SOURCE / "src/repl.c"
SRC_DECODER = SOURCE / "scripts/c2-stream-v2-decoder.c"
SRC_HOST_MODEL = SOURCE / "scripts/c2-stream-v2-host-main.c"
RUNTIME_CORE = SOURCE / "mk/runtime-core.mk"
RUNTIME_PROFILE = SOURCE / "config/runtime-core.mk"
BANNER_SOURCE = SOURCE / "lib/repl-banner.lisp"
CORE_CPU = ROOT / "build/upstream-verification/mega65-core/src/vhdl/gs4510.vhdl"
CORE_MACHINE = ROOT / (
    "build/upstream-verification/mega65-core/src/vhdl/machine_container.vhdl")
CORE_MONITOR = ROOT / (
    "build/upstream-verification/mega65-core/src/monitor/monitor.a65")
CORE_VIC = ROOT / "build/upstream-verification/mega65-core/src/vhdl/viciv.vhdl"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-mapping-aware-data-boot-gc-receipt.json")
DRIVER = Path(__file__).resolve()

EXPECTED_MANIFEST_COUNTS = [379, 157, 32, 39, 7, 111]
EXPECTED_ENTRIES = 725
EXPECTED_ROOTS = 340
EXPECTED_MACROS = 1
EXT_BOOT_CELLS = 1024
EXPECTED_PREPROMPT_ALLOCATIONS = EXPECTED_ROOTS + EXPECTED_MACROS
EXPECTED_HEADROOM = EXT_BOOT_CELLS - EXPECTED_PREPROMPT_ALLOCATIONS


class ClosureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ClosureError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    payload = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(payload),
        "sha256": sha_bytes(payload),
    }


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
    raise ClosureError(f"unterminated function: {signature}")


def ordered(source: str, tokens: list[str], label: str) -> None:
    plain = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.DOTALL)
    positions = [plain.find(token) for token in tokens]
    require(all(at >= 0 for at in positions) and positions == sorted(positions),
            f"{label} order drift: {positions}")


def u16(data: bytes, offset: int) -> int:
    require(0 <= offset <= len(data) - 2, "u16 outside artifact")
    return data[offset] | data[offset + 1] << 8


def u24(data: bytes, offset: int) -> int:
    require(0 <= offset <= len(data) - 3, "u24 outside artifact")
    return data[offset] | data[offset + 1] << 8 | data[offset + 2] << 16


def exact_product_census(substitution: dict[str, Any]) -> dict[str, Any]:
    """Read counts and export flags from the immutable C2D/shelf pair.

    The first manifest pathname has since been regenerated in the worktree.
    It is therefore deliberately *not* treated as Link-82 content authority.
    The substitution receipt's SHA-bound C2D and shelf are the delivered
    product truth and contain the resolved image/directory/entry records.
    """
    c2d = C2D.read_bytes()
    shelf = SHELF.read_bytes()
    for key, path, payload in (("initial_c2d", C2D, c2d), ("shelf", SHELF, shelf)):
        row = substitution["artifacts"][key]
        actual = bind(path)
        require(actual["bytes"] == row["bytes"] and actual["sha256"] == row["sha256"],
                f"exact Link-82 {key} binding drift")
    require(c2d[:8] == b"C2D\0\x03\x30\x20\x0a" and shelf[:5] == b"L65S\x04",
            "Link-82 C2D/shelf format drift")
    generation, images, entries = u16(c2d, 10), u16(c2d, 12), u16(c2d, 16)
    resolutions, roots = u16(c2d, 20), u16(c2d, 24)
    images_offset, entries_offset = u16(c2d, 28), u16(c2d, 30)
    require((generation, images, entries, resolutions, roots) ==
            (1, 6, EXPECTED_ENTRIES, 2842, EXPECTED_ROOTS),
            "exact Link-82 header census drift")
    image_counts = []
    descriptor_kinds: dict[int, int] = {}
    for image in range(images):
        at = images_offset + image * 32
        require(c2d[at] == 0 and c2d[at + 2] == image
                and u16(c2d, at + 4) == generation,
                f"static image binding drift: {image}")
        image_counts.append(u16(c2d, at + 8))
        metadata = u24(c2d, at + 23)
        literal_count = u16(shelf, metadata + 12)
        literals_offset = u16(shelf, metadata + 16)
        for local in range(literal_count):
            kind = shelf[metadata + literals_offset + local * 8]
            descriptor_kinds[kind] = descriptor_kinds.get(kind, 0) + 1
    require(image_counts == EXPECTED_MANIFEST_COUNTS
            and sum(image_counts) == EXPECTED_ENTRIES,
            f"exact image entry census drift: {image_counts}")

    macro_names: list[str] = []
    banner: dict[str, Any] | None = None
    for ordinal in range(entries):
        d = entries_offset + ordinal * 10
        image, local = c2d[d], u16(c2d, d + 2)
        require(image < images, f"directory image outside table: {ordinal}")
        im = images_offset + image * 32
        require(local < u16(c2d, im + 8), f"directory local outside image: {ordinal}")
        metadata = u24(c2d, im + 23)
        require(metadata + 24 <= len(shelf), f"metadata outside shelf: {ordinal}")
        entry_at = metadata + u16(shelf, metadata + 14) + local * 16
        require(entry_at + 16 <= len(shelf), f"entry outside shelf: {ordinal}")
        name_offset = u16(shelf, entry_at + 8)
        name = None
        if name_offset != 0xFFFF:
            name_at = metadata + u16(shelf, metadata + 18) + name_offset
            length = u16(shelf, name_at)
            require(name_at + 2 + length <= len(shelf), f"name outside shelf: {ordinal}")
            name = shelf[name_at + 2:name_at + 2 + length].decode("ascii")
        if shelf[entry_at + 11] & 1:
            require(name is not None, f"anonymous macro export: {ordinal}")
            macro_names.append(name)
        if name == "%repl-banner":
            banner = {"ordinal": ordinal, "length": u16(shelf, entry_at + 3),
                      "image": image, "local": local}
    require(macro_names == ["time"], f"exact macro census drift: {macro_names}")
    require(banner is not None, "exact %repl-banner entry absent")
    require(descriptor_kinds.get(3) == 116 and descriptor_kinds.get(7) == 224
            and descriptor_kinds[3] + descriptor_kinds[7] == EXPECTED_ROOTS,
            f"heap-root descriptor census drift: {descriptor_kinds}")
    return {"image_entry_counts": image_counts, "macro_names": macro_names,
            "root_descriptor_counts": {
                "kind_3_strings": descriptor_kinds[3],
                "kind_7_pairs": descriptor_kinds[7],
            },
            "banner_entry": banner, "C2D": bind(C2D), "shelf": bind(SHELF),
            "declared_manifest_bindings": substitution["manifests"]}


def mapping_facts() -> dict[str, Any]:
    device = load(DEVICE)
    desk = load(DESK)
    require(device["mapping"] == {
        "MAPH": "0x8000", "MAPL": "0x0000",
        "raw_tail": "A643    00     62 .VE...Z. ...P 15 -  00 - ..c..lhc",
    }, "stopped mapping authority drift")
    stopped = desk["facts"]["stopped_view"]
    require(stopped["CPU_port_bits_2_1_0"] == "111"
            and stopped["ROMC"] and stopped["LORAM"] and stopped["HIRAM"],
            "decoded ROM/port authority drift")

    cpu = CORE_CPU.read_text(encoding="utf-8")
    machine = CORE_MACHINE.read_text(encoding="utf-8")
    monitor = CORE_MONITOR.read_text(encoding="utf-8")
    vic = CORE_VIC.read_text(encoding="utf-8")
    for token in (
        "if reg_map_high(blocknum)='1'", "if reg_map_low(blocknum)='1'",
        "takes precedence over $01 CPU port when MAP bit is set",
        "temp_address(27 downto 12) := x\"002B\"",
        "if (blocknum=12) and (rom_at_c000='1')",
        "temp_address(27 downto 12) := x\"002C\"",
    ):
        require(token in cpu, f"core mapping token absent: {token}")
    require('monitor_roms(5) <= rom_at_c000' in machine
            and 'monitor_roms(2 downto 0) <= monitor_cpuport' in machine
            and '.byte       "reca8lhc"' in monitor
            and '$D030.5 VIC-III:ROMC Map C65 ROM @ $C000' in vic,
            "monitor ROM/port field authority drift")

    snapshot = {
        "id": "launch-failure-stop-2026-08-05",
        "captured_at_same_stop": True,
        "complete_for_current_B_C_underlay_translation": True,
        "MAPH": "0x8000", "MAPL": "0x0000",
        "map_selected_8k_blocks": ["0xe000-0xffff"],
        "ROM_flags_raw": "..c..lhc",
        "ROMC": True, "ROMA": False, "ROM8": False, "ROME": False,
        "CPU_port": {"LORAM": True, "HIRAM": True, "CHAREN": True},
        "mapped_block_rule": (
            "MAP takes precedence; a selected block requires captured MB/offset "
            "resolution and otherwise fails closed"),
    }
    rows = [
        ("phase-owner", 0x0089, 1, "RAM-visible", "none"),
        ("boot-witness", 0xB5C3, 1, "BASIC-ROM", "C64 LORAM+HIRAM"),
        ("gc-runs", 0xB9F0, 2, "BASIC-ROM", "C64 LORAM+HIRAM"),
        ("record", 0xC03F, 65, "C65-ROM", "ROMC"),
        ("phase-scratch", 0xC0C6, 304, "C65-ROM", "ROMC"),
        ("first-error", 0xC1F4, 2, "C65-ROM", "ROMC"),
    ]
    plan = []
    raw_rows = device["CPU_view_captures"]
    for name, logical, size, owner, overlay in rows:
        raw = raw_rows[name]
        require(int(raw["logical_address"], 0) == logical and raw["bytes"] == size
                and raw["view"] == "CPU-resolved-0x0777xxxx",
                f"raw CPU-view row drift: {name}")
        plan.append({
            "name": name,
            "kind": "data",
            "logical_address": f"0x{logical:04x}",
            "bytes": size,
            "mapping_snapshot_id": snapshot["id"],
            "map_selected": False,
            "raw_CPU_view_owner": owner,
            "active_overlay": overlay,
            "raw_CPU_view_is_data_authority": owner == "RAM-visible",
            "translation_required": owner != "RAM-visible",
            "translation_applied": True,
            "physical_RAM_address": f"0x{logical:08x}",
            "physical_monitor_command": f"m0000{logical:04x}",
            "evidence_view": "physical-bank0-RAM-underlay",
        })
    return {
        "mapping_snapshot": snapshot,
        "view_protocol": {
            "code": (
                "Read in CPU-resolved m0777xxxx view, bind the active owner, then "
                "interpret symbols; a physical underlay is not instruction identity."),
            "data": (
                "Capture mapping first, translate the logical data address, and read "
                "physical RAM; a raw CPU view through active ROM is corroboration only."),
            "same_stop_requirement": True,
            "mapped_block_fail_closed": True,
        },
        "read_plan": plan,
        "raw_CPU_capture_status": (
            "immutable input retained; overlaid B/C bytes remain non-authoritative for data"),
        "spaced_sample_ladder_changed": False,
        "durable_witness_changed": False,
    }


def boot_gc_facts() -> tuple[dict[str, Any], dict[str, Any]]:
    substitution = load(SUBSTITUTION)
    phase_a = load(PHASE_A)
    control = load(CONTROL_BOOT)
    boot_order = load(BOOT_ORDER)
    require(substitution["entries"] == EXPECTED_ENTRIES
            and substitution["roots"] == EXPECTED_ROOTS
            and substitution["images"] == 6
            and substitution["resolutions"] == 2842,
            "Link-82 substitution geometry drift")
    require(phase_a["base"]["link"] == 82
            and phase_a["base"]["geometry"]["roots"] == EXPECTED_ROOTS,
            "Phase-A Link-82 base drift")
    require(control["status"] == "CONTROL-PHYSICAL-BOOT-PASS"
            and control["control_identity"]["screen_result"]["visible_REPL"],
            "healthy control prompt authority drift")
    require(boot_order["facts"]["boot_order"]["classification"] ==
            "SHARED-POST-MEM-INIT-COLLECTION-ROOT-SCAN",
            "prior boot-order authority drift")

    product_census = exact_product_census(substitution)
    counts = product_census["image_entry_counts"]
    macro_names = product_census["macro_names"]

    main = SRC_MAIN.read_text(encoding="utf-8")
    mem = SRC_MEM.read_text(encoding="utf-8")
    symbol = SRC_SYMBOL.read_text(encoding="utf-8")
    runtime = SRC_RUNTIME.read_text(encoding="utf-8")
    repl = SRC_REPL.read_text(encoding="utf-8")
    decoder = SRC_DECODER.read_text(encoding="utf-8")
    host_model = SRC_HOST_MODEL.read_text(encoding="utf-8")
    runtime_core = RUNTIME_CORE.read_text(encoding="utf-8")
    runtime_profile = RUNTIME_PROFILE.read_text(encoding="utf-8")
    banner = BANNER_SOURCE.read_text(encoding="utf-8")

    main_fn = function(main, "int main(void)")
    mem_init = function(mem, "void mem_init(void)")
    alloc = function(mem, "obj alloc(uint8_t type)")
    name_value = function(runtime, "uint8_t c2_stream_name_value")
    pair_value = function(runtime, "uint8_t c2_stream_pair_value")
    checkpoint = function(runtime, "uint8_t c2_stream_gc_checkpoint")
    publish = function(runtime, "static uint8_t c2_publish_exports_from(uint16_t first) {")
    boot = function(runtime, "uint8_t c2_product_boot(void)")
    new_symbol = function(symbol, "static obj new_symbol")
    repl_fn = function(repl, "void repl(void)")

    ordered(main_fn, ["vm_install_staged_boot_overlay()", "c2_product_prepare_boot()",
                      "c2_product_boot()", "repl()"], "Link-82 main")
    ordered(mem_init, ["freelist = NIL", "for (i = MAX_CELLS - 1",
                       "freelist = (obj)(i << 1)"], "EXT-first freelist")
    ordered(boot, ["c2_stream_init", "c2_decode_from",
                   "c2_pending_roots = c2_runtime",
                   "c2_committed_roots = c2_runtime",
                   "c2_publish_exports_from"], "C2 boot")
    require("pair = cons(" in pair_value and "obj string = c2_facade_str_open()" in name_value,
            "one-cell root materialization semantics drift")
    require("allocated_count != EXPECTED_ROOTS" in host_model
            and "gc_checkpoints != EXPECTED_ROOTS" in host_model,
            "independent stream allocation census oracle absent")
    require("return MK_SYMI(nsym++)" in new_symbol
            and "Immediate: keine Heap-Zelle" in new_symbol,
            "symbol-immediate rule drift")
    require("published = alloc(T_MACRO)" in publish
            and "if (entry[11] & 1u)" in publish,
            "macro publication allocation drift")
    require("gc_collect();" not in checkpoint,
            "product checkpoint again performs collection")
    require("if (gc_frozen && freelist != NIL" in alloc
            and "if (freelist == NIL)" in alloc,
            "allocator collection guards drift")
    require("-DHEAP_CELLS=48" in runtime_core
            and "-DEXT_CELLS=1024" in runtime_core
            and "-DEXT_CELLS=1024" in runtime_profile
            and "-DLISP65_NURSERY_HYSTERESIS=192" in runtime_profile,
            "Link-82 heap geometry defines drift")

    require(product_census["banner_entry"]["length"] > 0,
            "exact banner entry is empty")
    require("vm_run_dir(LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY" in repl_fn
            and repl_fn.find("vm_run_dir(LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY") <
                repl_fn.find('emit_str("lisp65> ")'),
            "banner/prompt order drift")
    repl_before_prompt = repl_fn[:repl_fn.find('emit_str("lisp65> ")')]
    require("gc_collect(" not in main_fn and "gc_collect(" not in boot
            and "gc_collect(" not in publish and "gc_collect(" not in repl_before_prompt,
            "direct pre-prompt collection call appeared")
    forbidden_banner = ("cons", "alloc", "make-string", "string-append", "gensym")
    require(not any(re.search(rf"\({re.escape(token)}(?:\s|\))", banner)
                    for token in forbidden_banner),
            "banner gained a heap constructor")

    # The exact decoder publishes one heap value for every root: kind 3 uses
    # str_open/alloc(T_STR), kind 7 uses cons/alloc(T_PAIR); symbols are
    # immediates.  The exact host model independently requires allocation and
    # checkpoint counts to equal EXPECTED_ROOTS.  Export publication adds only
    # the single manifest macro wrapper.
    require(EXPECTED_PREPROMPT_ALLOCATIONS < EXT_BOOT_CELLS,
            "pre-prompt boot allocation capacity exhausted")
    return ({
        "healthy_control_before_first_prompt": {
            "gc_collect_reachable": False,
            "gc_runs_delta": 0,
            "classification": "NO-PRE-PROMPT-COLLECTION",
        },
        "allocation_census": {
            "C2_materialized_roots": EXPECTED_ROOTS,
            "root_descriptor_counts": product_census["root_descriptor_counts"],
            "root_allocation_oracle": (
                "exact decoder callbacks plus independent allocated_count==EXPECTED_ROOTS"),
            "heap_allocating_export_macros": EXPECTED_MACROS,
            "macro_names": macro_names,
            "symbols_are_heap_cells": False,
            "banner_heap_allocations": 0,
            "total_before_first_prompt": EXPECTED_PREPROMPT_ALLOCATIONS,
            "EXT_first_capacity": EXT_BOOT_CELLS,
            "remaining_cells": EXPECTED_HEADROOM,
        },
        "collection_exclusion": {
            "gc_frozen_during_C2_boot": 0,
            "nursery_branch_enabled": False,
            "freelist_exhausted": False,
            "checkpoint_calls_gc_collect": False,
            "direct_boot_or_banner_gc_call": False,
        },
        "snapshot_0x3b0d": {
            "symbol": "gc_collect+0x216",
            "normal_healthy_pre_prompt_progress": False,
            "classification": "SUSPICIOUS-OUTSIDE-HEALTHY-PRE-PROMPT-SCHEDULE",
            "hang_loop_slow_progress_or_culprit_claim": False,
            "reason": (
                "The healthy schedule has gc_runs delta zero before the first prompt; "
                "one stopped PC still proves neither liveness nor cause."),
        },
        "manifest_entry_counts": counts,
        "limits": {
            "hardware_contacts": 0, "device_actions": 0,
            "product_bytes": 0, "measured_forms": 0,
            "R_A_I_G": None, "contact_authorized": False,
        },
    }, product_census)


def exact_facts() -> tuple[dict[str, Any], dict[str, Any]]:
    mapping = mapping_facts()
    boot_gc, manifests = boot_gc_facts()
    facts = {"mapping_aware_read_protocol": mapping, "static_boot_GC": boot_gc}
    audit(facts)
    return facts, manifests


def audit(facts: dict[str, Any]) -> None:
    mapping = facts["mapping_aware_read_protocol"]
    snapshot = mapping["mapping_snapshot"]
    require(snapshot["captured_at_same_stop"]
            and snapshot["complete_for_current_B_C_underlay_translation"]
            and snapshot["MAPH"] == "0x8000" and snapshot["MAPL"] == "0x0000"
            and snapshot["ROMC"] and snapshot["CPU_port"] == {
                "LORAM": True, "HIRAM": True, "CHAREN": True},
            "mapping snapshot incomplete")
    require(mapping["view_protocol"]["same_stop_requirement"]
            and mapping["view_protocol"]["mapped_block_fail_closed"]
            and mapping["view_protocol"]["code"].startswith(
                "Read in CPU-resolved m0777xxxx view")
            and mapping["view_protocol"]["data"].startswith(
                "Capture mapping first")
            and not mapping["spaced_sample_ladder_changed"]
            and not mapping["durable_witness_changed"],
            "read-protocol boundary drift")
    require(len(mapping["read_plan"]) == 6, "data read-plan count drift")
    for row in mapping["read_plan"]:
        logical = int(row["logical_address"], 0)
        require(row["kind"] == "data"
                and row["mapping_snapshot_id"] == snapshot["id"]
                and not row["map_selected"]
                and row["translation_applied"]
                and int(row["physical_RAM_address"], 0) == logical
                and row["physical_monitor_command"] == f"m0000{logical:04x}"
                and row["evidence_view"] == "physical-bank0-RAM-underlay",
                f"untranslated or unbound data row: {row['name']}")
        if row["active_overlay"] != "none":
            require(row["translation_required"]
                    and not row["raw_CPU_view_is_data_authority"],
                    f"overlaid raw CPU data promoted: {row['name']}")

    gc = facts["static_boot_GC"]
    healthy = gc["healthy_control_before_first_prompt"]
    census = gc["allocation_census"]
    exclusion = gc["collection_exclusion"]
    snapshot_pc = gc["snapshot_0x3b0d"]
    require(healthy == {"gc_collect_reachable": False, "gc_runs_delta": 0,
                        "classification": "NO-PRE-PROMPT-COLLECTION"},
            "healthy pre-prompt GC conclusion drift")
    require(census["C2_materialized_roots"] == EXPECTED_ROOTS
            and census["heap_allocating_export_macros"] == EXPECTED_MACROS
            and census["root_descriptor_counts"] == {
                "kind_3_strings": 116, "kind_7_pairs": 224}
            and census["macro_names"] == ["time"]
            and not census["symbols_are_heap_cells"]
            and census["banner_heap_allocations"] == 0
            and census["total_before_first_prompt"] == EXPECTED_PREPROMPT_ALLOCATIONS
            and census["EXT_first_capacity"] == EXT_BOOT_CELLS
            and census["remaining_cells"] == EXPECTED_HEADROOM,
            "boot allocation census drift")
    require(exclusion == {
        "gc_frozen_during_C2_boot": 0,
        "nursery_branch_enabled": False,
        "freelist_exhausted": False,
        "checkpoint_calls_gc_collect": False,
        "direct_boot_or_banner_gc_call": False,
    }, "collection-exclusion chain drift")
    require(not snapshot_pc["normal_healthy_pre_prompt_progress"]
            and snapshot_pc["classification"] ==
                "SUSPICIOUS-OUTSIDE-HEALTHY-PRE-PROMPT-SCHEDULE"
            and not snapshot_pc["hang_loop_slow_progress_or_culprit_claim"],
            "single-PC claim hygiene drift")
    require(gc["limits"] == {
        "hardware_contacts": 0, "device_actions": 0, "product_bytes": 0,
        "measured_forms": 0, "R_A_I_G": None, "contact_authorized": False,
    }, "desk/contact boundary drift")


def expected() -> dict[str, Any]:
    facts, product_census = exact_facts()
    authorities = {
        "owner_commission": bind(PLAN), "raw_device_packet": bind(DEVICE),
        "prior_desk_closure": bind(DESK), "boot_order": bind(BOOT_ORDER),
        "phase_A": bind(PHASE_A), "healthy_control_boot": bind(CONTROL_BOOT),
        "Link82_substitution": bind(SUBSTITUTION), "source_main": bind(SRC_MAIN),
        "source_mem": bind(SRC_MEM), "source_symbol": bind(SRC_SYMBOL),
        "source_runtime": bind(SRC_RUNTIME), "source_repl": bind(SRC_REPL),
        "decoder": bind(SRC_DECODER), "independent_host_model": bind(SRC_HOST_MODEL),
        "runtime_core_build": bind(RUNTIME_CORE),
        "runtime_core_profile": bind(RUNTIME_PROFILE),
        "banner_source": bind(BANNER_SOURCE),
        "Link82_C2D": product_census["C2D"],
        "Link82_shelf": product_census["shelf"],
        "core_CPU_mapping": bind(CORE_CPU),
        "core_machine_flags": bind(CORE_MACHINE), "core_monitor_flags": bind(CORE_MONITOR),
        "core_ROMC": bind(CORE_VIC), "driver": bind(DRIVER),
    }
    authorities["six_declared_manifest_bindings"] = product_census[
        "declared_manifest_bindings"]
    return {
        "format": "lisp65-c2.3-v1.6-mapping-aware-data-boot-gc-v1",
        "recorded_on": date.today().isoformat(),
        "status": "HOST-GREEN; DATA-VIEW-CLOSED; PRE-PROMPT-GC-EXCLUDED",
        "authorities": authorities,
        "facts": facts,
        "execution_witnesses": [
            "MAPH/MAPL and reca8lhc are captured in one stopped register row",
            "primary core resolver gives MAP precedence and maps active BASIC/ROMC reads away from RAM",
            "all six stopped data rows now name physical Bank-0 underlay commands",
            "the SHA-bound C2D/shelf pair closes six images, 725 entries, 340 roots and one macro export",
            "exact allocator source starts with 1,024 EXT cells and cannot collect at 341 allocations",
            "exact REPL executes a heap-allocation-free banner before the first prompt",
            "the healthy physical control reaches lisp65> through this bound schedule",
        ],
        "rejected_mutations": [
            "data-through-active-ROM-without-translation",
            "translation-without-mapping-capture",
            "wrong-physical-bank", "code-identity-through-physical-underlay",
            "missing-ROMC-field", "mapped-block-without-resolution",
            "promote-raw-ROM-byte-to-data", "change-root-count",
            "change-macro-count", "treat-symbol-as-heap-cell",
            "add-banner-allocation", "exhaust-EXT-capacity",
            "make-checkpoint-collect", "classify-3B0D-normal",
            "promote-3B0D-to-hang", "authorize-contact",
        ],
        "contact_authorized": False,
        "claim_limit": (
            "Desk-only mapping/data protocol and static healthy-control boot schedule. "
            "No device contact, reset/resume, measured form, R/A/I/G result, product "
            "liveness/culprit claim, product byte, fix, link or recontact is claimed."),
    }


def selftest() -> dict[str, Any]:
    facts, _ = exact_facts()
    cases: dict[str, tuple[list[Any], Any]] = {
        "data-through-active-ROM-without-translation":
            (["mapping_aware_read_protocol", "read_plan", 1, "translation_applied"], False),
        "translation-without-mapping-capture":
            (["mapping_aware_read_protocol", "mapping_snapshot", "captured_at_same_stop"], False),
        "wrong-physical-bank":
            (["mapping_aware_read_protocol", "read_plan", 2, "physical_RAM_address"], "0x0001b9f0"),
        "code-identity-through-physical-underlay":
            (["mapping_aware_read_protocol", "view_protocol", "code"],
             "Use physical underlay as instruction identity."),
        "missing-ROMC-field":
            (["mapping_aware_read_protocol", "mapping_snapshot", "ROMC"], False),
        "mapped-block-without-resolution":
            (["mapping_aware_read_protocol", "read_plan", 3, "map_selected"], True),
        "promote-raw-ROM-byte-to-data":
            (["mapping_aware_read_protocol", "read_plan", 4,
              "raw_CPU_view_is_data_authority"], True),
        "change-root-count":
            (["static_boot_GC", "allocation_census", "C2_materialized_roots"], 339),
        "change-macro-count":
            (["static_boot_GC", "allocation_census", "heap_allocating_export_macros"], 0),
        "treat-symbol-as-heap-cell":
            (["static_boot_GC", "allocation_census", "symbols_are_heap_cells"], True),
        "add-banner-allocation":
            (["static_boot_GC", "allocation_census", "banner_heap_allocations"], 1),
        "exhaust-EXT-capacity":
            (["static_boot_GC", "allocation_census", "remaining_cells"], 0),
        "make-checkpoint-collect":
            (["static_boot_GC", "collection_exclusion", "checkpoint_calls_gc_collect"], True),
        "classify-3B0D-normal":
            (["static_boot_GC", "snapshot_0x3b0d", "normal_healthy_pre_prompt_progress"], True),
        "promote-3B0D-to-hang":
            (["static_boot_GC", "snapshot_0x3b0d",
              "hang_loop_slow_progress_or_culprit_claim"], True),
        "authorize-contact":
            (["static_boot_GC", "limits", "contact_authorized"], True),
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
        except ClosureError:
            rejected.append(name)
        else:
            raise ClosureError(f"mutation survived: {name}")
    require(len(rejected) == len(cases), "mutation count drift")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "data_rows": len(facts["mapping_aware_read_protocol"]["read_plan"]),
            "preprompt_allocations": EXPECTED_PREPROMPT_ALLOCATIONS,
            "headroom": EXPECTED_HEADROOM}


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("selftest", "write", "check"))
    args = parser.parse_args()
    try:
        if args.command == "selftest":
            result = selftest()
            print("MAPPING DATA/BOOT GC SELFTEST PASS "
                  f"mutations={result['mutations']} data={result['data_rows']} "
                  f"alloc={result['preprompt_allocations']} headroom={result['headroom']}")
            return 0
        value = expected()
        if args.command == "write":
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_bytes(canonical(value))
            print("MAPPING DATA/BOOT GC WRITE PASS "
                  "data=physical-underlay preprompt-gc=excluded contact=closed")
            return 0
        require(RECEIPT.is_file() and RECEIPT.read_bytes() == canonical(value),
                "mapping-data/boot-GC receipt drift; run write deliberately")
        print("MAPPING DATA/BOOT GC PASS "
              "data=physical-underlay preprompt-gc=excluded contact=closed")
        return 0
    except (ClosureError, KeyError, ValueError, TypeError) as exc:
        print(f"MAPPING DATA/BOOT GC FIRST RED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
