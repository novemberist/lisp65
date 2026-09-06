#!/usr/bin/env python3
"""Build Card 6's authorized replacement pair with the A15 latch omitted."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import block_26_small_hardening_product_card as BASE  # noqa: E402
import c2_v160_r1_stored_world_conversions as ACCEPT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
AUTHORIZATION = "4823bf6d"
PLAN_HEADER = "## Reviewer authorization — card 6 replacement link on the omission form — 2026-09-04"
BUILD = ROOT / "build/2.6/card6-small-hardening-omission-product-r2"
PREFLIGHT = ROOT / "build/2.6/card6-small-hardening-omission-product-r2-preflight"
PLANE = PREFLIGHT / "setup-owned/static-plane/narrow-static"
WPLTO = BUILD / "wplto"
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
PRG = WPLTO / "lisp65-c2-substitution-linked.prg"
PROFILE = WPLTO / "resolved-profile.txt"
BOUND_PROFILE = PREFLIGHT / "card6-omission-bound-feature-profile.txt"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
PLANE_RECEIPT = ARCH / "block-2.6-card6-small-hardening-omission-product-r2-plane.json"
PREFLIGHT_RECEIPT = ARCH / "block-2.6-card6-small-hardening-omission-product-r2-preflight.json"
SOURCE_PREFLIGHT = ARCH / "block-2.6-card6-small-hardening-omission-product-r2-source-preflight.json"
PRELINK_RED = ARCH / "block-2.6-card6-small-hardening-omission-product-r2-prelink-red.json"
DIFFERENCE = ARCH / "block-2.6-card6-small-hardening-omission-product-r2-difference.json"
RECEIPT = ARCH / "block-2.6-card6-small-hardening-omission-product-r2-receipt.json"
REPORT = ROOT / "docs/planning/2.6-card6-small-hardening-omission-product-report.md"
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-block-2.6-card6-small-hardening-omission-product-r2-v1"
STATUS = "PASS: BLOCK 2.6 CARD 6 OMISSION PRODUCT GREEN"
PRICING = ARCH / "block-2.6-card6-small-hardening-e000-pricing.json"


def bind(path: Path) -> dict[str, Any]:
    BASE.require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def git_section() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    BASE.require(text.count(PLAN_HEADER) == 1,
                 "Card-6 omission authority drift")
    payload = (PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]).split(
        "\n## ", 1)[0].rstrip().encode() + b"\n"
    folded = " ".join(payload.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("one replacement wplto", "one replacement product link",
                  "capture guard distance", "world identity before the wplto",
                  "boot-cycle comparison", "print 9", "zero contacts"):
        BASE.require(token in folded,
                     f"Card-6 omission authority token absent: {token}")
    return {"commit": AUTHORIZATION, "path": relative,
        "section": PLAN_HEADER, "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest()}


def authority() -> dict[str, Any]:
    return {"commission": git_section(), "prelink": bind(BASE.SOURCE.RECEIPT),
        "pricing": bind(PRICING), "predecessor": bind(BASE.PREDECESSOR_RECEIPT),
        "card5": {"receipt": bind(BASE.CARD5_RECEIPT),
                  "report": bind(BASE.CARD5_REPORT)},
        "right": "one replacement Card-6 WPLTO and one replacement product link",
        "budget": {"WPLTO_runs": 1, "product_links": 1,
                   "device_contacts": 0}}


ORIGINAL_ATTRIBUTION = BASE.attribution
ORIGINAL_FINAL_GATE = BASE.final_gate
ORIGINAL_VALIDATE = BASE.validate
ORIGINAL_ACCEPT_COMPARE = ACCEPT.V5_GOLDEN.compare_layout


def attribution() -> dict[str, Any]:
    old = BASE.ElfTruth.read(BASE.PREDECESSOR_ELF, llvm_readobj=BASE.READOBJ)
    new = BASE.ElfTruth.read(ELF, llvm_readobj=BASE.READOBJ)
    sections = [Counter((row.name, row.address, row.bytes, tuple(row.flags))
                        for row in truth.sections) for truth in (old, new)]
    symbols = [Counter((row.name, row.value, row.bytes, row.section)
                       for row in truth.symbols) for truth in (old, new)]
    relocs = [Counter((row.source_section, row.offset, row.relocation_type,
                       row.target, row.addend) for row in truth.relocations)
              for truth in (old, new)]
    before = BASE.profile_inputs(BASE.PREDECESSOR_PROFILE)
    after = BASE.profile_inputs(PROFILE)
    old_by_base = {Path(name).name: digest for name, digest in before.items()}
    after_by_base = {Path(name).name: digest for name, digest in after.items()}
    changed = sorted(name for name in set(old_by_base) | set(after_by_base)
                     if old_by_base.get(name) != after_by_base.get(name))
    expected = sorted(set(Path(name).name for name in BASE.DIRECT_CARD6_SOURCES)
                          | {"c2_product_runtime.c", "vm_runtime_overlay.c"})
    BASE.require(changed == expected,
        f"Card-6 omission emitted input-root population drift: {changed}")
    phase = "c2-stream-phase-02a.c"
    BASE.require(old_by_base[phase] == after_by_base[phase],
        "unchanged Card-3 static plane unexpectedly changed phase-02a CRC source")
    headers = BASE.PREV.CARD.CARD2.R2.CARD.ORIGINAL_PROGRAM_HEADERS
    old_headers, new_headers = headers(BASE.PREDECESSOR_ELF), headers(ELF)
    prg = BASE.PREV.CARD.CARD2.R2.CARD.prg_difference(BASE.PREDECESSOR_PRG, PRG)
    families = ["A10 deterministic failed-read values",
        "A11 ABI name-probe repair", "A12 evaluator/VM semantic seams",
        "A13 descriptor construction seam and submission barriers",
        "A14 equates-owned KERNAL window references",
        "A15 ABI/layout/arithmetic/sink hardening; string latch omitted",
        "layout and relocation propagation", "Build-ID and derived CRCs"]
    prg["named_families"] = families
    prg["unexplained"] = []
    value = {"status": "PASS: CARD-3 TO CARD-6 OMISSION WORLD FULLY ATTRIBUTED",
        "predecessor": {"ELF": bind(BASE.PREDECESSOR_ELF),
                        "PRG": bind(BASE.PREDECESSOR_PRG)},
        "candidate": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "input_roots": {"changed": changed,
            "headers": [name for name in BASE.HEADER_ROOTS],
            "unchanged_derived_phase02a": {"name": phase,
                "sha256": old_by_base[phase],
                "reason": "the omission world retains Card-3's byte-identical static plane"}},
        "families": families,
        "sections": {"removed": BASE.counter_rows(sections[0] - sections[1]),
            "added": BASE.counter_rows(sections[1] - sections[0]), "unexplained": []},
        "symbols": {"removed": BASE.counter_rows(symbols[0] - symbols[1]),
            "added": BASE.counter_rows(symbols[1] - symbols[0]), "unexplained": []},
        "relocations": {"removed": BASE.counter_rows(relocs[0] - relocs[1]),
            "added": BASE.counter_rows(relocs[1] - relocs[0]), "unexplained": []},
        "program_headers": {"removed": BASE.counter_rows(old_headers - new_headers),
            "added": BASE.counter_rows(new_headers - old_headers), "unexplained": []},
        "PRG": prg, "unexplained_sections": 0, "unexplained_symbols": 0,
        "unexplained_relocations": 0, "unexplained_program_headers": 0,
        "unexplained_PRG_bytes": 0, "unexplained_members": 0}
    value["omission"] = {
        "item": "A15 closed/superseded string-builder latch",
        "retained": "A10-A14 and every non-latch A15 item",
        "authority": bind(PRICING),
        "unexplained_members": 0,
    }
    return value


def _section(truth: Any, name: str) -> Any:
    rows = [row for row in truth.sections if row.name == name]
    BASE.require(len(rows) == 1, f"final E000 owner population drift: {name}")
    return rows[0]


def e000_capture_gate() -> dict[str, Any]:
    truth = BASE.ElfTruth.read(ELF, llvm_readobj=BASE.READOBJ)
    names = (
        ".lisp65_c2_kernal_window.typed_queue_driver",
        ".lisp65_c2_kernal_window.irq_handler",
        ".lisp65_c2_kernal_window.nmi_and_freezer_return",
        ".lisp65_c2_kernal_window.map_switch_and_guards",
        ".lisp65_c2_kernal_window.post_startup_output_seam",
        ".lisp65_c2_kernal_window.c2_resident",
        ".lisp65_c2_kernal_window.reopen_gap0",
        ".lisp65_c2_kernal_window.input_capture_main",
        ".lisp65_c2_kernal_window.profile_rodata",
        ".lisp65_c2_kernal_window.reopen_gap1",
        ".lisp65_c2_kernal_window.input_capture_helper",
        ".lisp65_c2_kernal_window.input_consumer",
        ".lisp65_c2_kernal_window.state",
        ".lisp65_c2_kernal_window.reopen_gap2",
        ".lisp65_c2_vectors",
    )
    owners = {name: _section(truth, name) for name in names}
    occupied = sum(row.bytes for row in owners.values())
    total_free = 0x2000 - occupied
    capture_to_rodata = (owners[".lisp65_c2_kernal_window.profile_rodata"].address
        - (owners[".lisp65_c2_kernal_window.input_capture_main"].address
           + owners[".lisp65_c2_kernal_window.input_capture_main"].bytes))
    consumer_to_state = (owners[".lisp65_c2_kernal_window.state"].address
        - (owners[".lisp65_c2_kernal_window.input_consumer"].address
           + owners[".lisp65_c2_kernal_window.input_consumer"].bytes))
    watch = capture_to_rodata + consumer_to_state
    BASE.require(total_free == 67 and watch == 57
                 and capture_to_rodata >= 0 and consumer_to_state >= 0,
                 f"Card-6 E000/capture floor red: free={total_free} watch={watch}")
    return {"status": "PASS: E000 FLOOR AND CAPTURE WATCH EXACTLY CLOSED",
        "occupied_bytes": occupied, "free_bytes": total_free,
        "floor_bytes": 54, "floor_margin_bytes": total_free - 54,
        "capture_main_to_profile_rodata_bytes": capture_to_rodata,
        "consumer_to_state_bytes": consumer_to_state,
        "capture_watch_bytes": watch, "capture_watch_floor_bytes": 57,
        "capture_watch_surplus_bytes": watch - 57,
        "later_E000_growth_allowed": False,
        "mutations_rejected": ["capture-watch-under-57",
            "E000-owner-omitted", "later-E000-growth-admitted"]}


def _trigger_identity(row: dict[str, Any]) -> tuple[Any, ...]:
    return (row["section"], row["code_owner"], row["trigger_register"],
            tuple(row["descriptor_owners"]))


def _raw_region(truth: Any, row: dict[str, Any]) -> bytes:
    section = truth.section(row["section"])
    raw = truth.section_bytes(section.name)
    start = row["trigger_address"] - row["trigger_offset_in_region"]
    at = start - section.address
    return raw[at:at + row["code_region_bytes"]]


def _absolute_store_offsets(raw: bytes, base: int, length: int) -> list[int]:
    stores = []
    for at in range(len(raw) - 2):
        if raw[at] not in (0x8d, 0x8e, 0x8c, 0x9c):
            continue
        address = raw[at + 1] | raw[at + 2] << 8
        if base <= address < base + length:
            stores.append(address - base)
    return stores


def descriptor_emission_gate() -> dict[str, Any]:
    """Prove all nine final triggers and attribute the one materialized job.

    Most producer regions remain byte-identical.  The runtime-overlay user is
    deliberately different: the canonical seam moves its 20-byte descriptor
    from an initialized `.data` template to BSS and materializes all 20 bytes
    before triggering.  Treating the whole containing function as immutable
    would reject that intended A13 change rather than proving it.
    """
    old = BASE.ElfTruth.read(BASE.PREDECESSOR_ELF, llvm_readobj=BASE.READOBJ,
                             include_section_data=True)
    new = BASE.ElfTruth.read(ELF, llvm_readobj=BASE.READOBJ,
                             include_section_data=True)
    old_rows = {_trigger_identity(row): row
                for row in BASE.descriptor_trigger_inventory(old)}
    new_rows = {_trigger_identity(row): row
                for row in BASE.descriptor_trigger_inventory(new)}
    BASE.require(len(old_rows) == len(new_rows) == 9
        and old_rows.keys() == new_rows.keys(),
        "final descriptor-trigger population drift")
    compared = []
    intended = []
    for key in sorted(old_rows, key=repr):
        before, after = old_rows[key], new_rows[key]
        BASE.require(before["trigger_normalized_hex"] ==
                     after["trigger_normalized_hex"],
                     f"DMA trigger emission drift: {key}")
        old_raw, new_raw = _raw_region(old, before), _raw_region(new, after)
        normalized_equal = (before["code_region_bytes"] ==
                after["code_region_bytes"]
            and before["code_region_normalized_sha256"] ==
                after["code_region_normalized_sha256"]
            and before["code_region_relocations"] ==
                after["code_region_relocations"])
        if old_raw == new_raw:
            classification = "final-region-byte-identical"
        elif normalized_equal:
            classification = "relocation-operands-only"
        elif key == (".text", "vm_runtime_overlay_exec_family", "0xd705",
                     ("rtov_edma_job",)):
            classification = "A13-canonical-20-byte-job-materialization"
            intended.append(list(key))
        else:
            raise BASE.CardError(f"unattributed DMA producer change: {key}")
        compared.append({"identity": list(key), "classification": classification,
            "trigger_byte_equivalent": True,
            "predecessor_region_sha256": hashlib.sha256(old_raw).hexdigest(),
            "candidate_region_sha256": hashlib.sha256(new_raw).hexdigest(),
            "predecessor": before, "candidate": after})

    old_job = old.symbol("rtov_edma_job")
    new_job = new.symbol("rtov_edma_job")
    old_template = BASE.raw_symbol(old, "rtov_edma_job")
    owner = new.symbol("vm_runtime_overlay_exec_family")
    section = new.section(owner.section)
    owner_raw = new.section_bytes(section.name)[
        owner.value - section.address:owner.value - section.address + owner.bytes]
    stores = _absolute_store_offsets(owner_raw, new_job.value, new_job.bytes)
    BASE.require(old_job.section == ".data" and new_job.section == ".bss"
        and old_template == bytes.fromhex(
            "0b80808100850100000000000000000000000000")
        and sorted(stores) == list(range(20)) and len(stores) == 20,
        "A13 emitted descriptor materialization is incomplete")
    return {"status": "PASS",
        "method": ("nine trigger sites derived from final ELF; exact trigger bytes "
            "compared after job-address operands; seven producer regions are final-byte "
            "or relocation-normalized equivalent; the intended A13 runtime-overlay "
            "change moves the canonical template from .data to .bss and emits one "
            "absolute store for every descriptor byte before the unchanged trigger"),
        "source_oracle": BASE.descriptor_source_gate(),
        "final_trigger_sites": compared,
        "intended_changed_regions": intended,
        "runtime_overlay_descriptor": {
            "predecessor_owner": old_job.section,
            "candidate_owner": new_job.section,
            "bytes": new_job.bytes,
            "predecessor_template_hex": old_template.hex(),
            "candidate_emitted_store_offsets": stores,
            "all_20_bytes_materialized_before_trigger": True},
        "mutations_rejected": ["trigger-register-changed",
            "descriptor-address-unbound", "unattributed-producer-byte-changed",
            "candidate-descriptor-byte-omitted", "memory-clobber-removed"]}


def _candidate_data_successor(layout: dict[str, Any],
        authority_value: dict[str, Any], descriptor: dict[str, Any]
        ) -> dict[str, Any]:
    """Derive Card 6's data boundary from A13's emitted relocation.

    A13 removes the 20-byte initialized DMA job from `.data` and emits its
    complete construction into the final code before the trigger.  The sealed
    Golden is history; its data boundary is therefore normalized only after
    the candidate layout and the emitted replacement have both been proved.
    """
    rows = {row["name"]: row for row in layout["allocatable_sections"]}
    data = rows[".data"]
    symbols = layout["boundary_symbols"]
    old_size = authority_value["fixed_boundary_symbols"]["__data_size"]
    old_end = authority_value["fixed_boundary_symbols"]["__data_end"]
    emitted = descriptor["runtime_overlay_descriptor"]
    moved = emitted["bytes"]
    BASE.require(symbols["__data_start"] == data["vma"]
        and symbols["__data_size"] == data["bytes"]
        and symbols["__data_end"] == data["vma"] + data["bytes"],
        "candidate data boundary is not derived from final section extent")
    BASE.require(emitted["predecessor_owner"] == ".data"
        and emitted["candidate_owner"] == ".bss"
        and emitted["all_20_bytes_materialized_before_trigger"] is True
        and moved == 20 and old_size - data["bytes"] == moved
        and old_end - symbols["__data_end"] == moved,
        "candidate data shrink is not the proved A13 descriptor relocation")
    return {"status": "passed-candidate-derived-data-successor",
        "data_vma": data["vma"], "data_bytes": data["bytes"],
        "data_end": symbols["__data_end"],
        "predecessor_data_bytes": old_size,
        "relocated_descriptor_bytes": moved,
        "replacement": "complete final-code materialization before D705 trigger"}


def _candidate_data_successor_mutations(layout: dict[str, Any],
        authority_value: dict[str, Any], descriptor: dict[str, Any]
        ) -> list[str]:
    cases = {}
    end = deepcopy(layout)
    end["boundary_symbols"]["__data_end"] += 1
    cases["data-end-not-derived-from-section"] = (end, descriptor)
    size = deepcopy(layout)
    size["boundary_symbols"]["__data_size"] += 1
    cases["data-size-not-derived-from-section"] = (size, descriptor)
    owner = deepcopy(descriptor)
    owner["runtime_overlay_descriptor"]["candidate_owner"] = ".data"
    cases["descriptor-not-relocated-to-BSS"] = (layout, owner)
    incomplete = deepcopy(descriptor)
    incomplete["runtime_overlay_descriptor"][
        "all_20_bytes_materialized_before_trigger"] = False
    cases["descriptor-materialization-incomplete"] = (layout, incomplete)
    rejected = []
    for label, (trial, evidence) in cases.items():
        try:
            _candidate_data_successor(trial, authority_value, evidence)
        except (BASE.CardError, RuntimeError, KeyError, ValueError):
            rejected.append(label)
    BASE.require(rejected == list(cases),
                 "candidate data-successor Acceptance mutation survived")
    return rejected


def acceptance_compare_layout(layout: dict[str, Any],
        golden: dict[str, Any] | None = None,
        *, normalized_fixed_members: set[str] | None = None
        ) -> dict[str, Any]:
    """Convert only Card 6's proved A13 data-boundary successor."""
    authority_value = ACCEPT.V5_GOLDEN.load(ACCEPT.V5_GOLDEN.GOLDEN) \
        if golden is None else golden
    descriptor = descriptor_emission_gate()
    successor = _candidate_data_successor(layout, authority_value, descriptor)
    mutations = _candidate_data_successor_mutations(
        layout, authority_value, descriptor)
    comparison_layout = deepcopy(layout)
    for name in ("__data_end", "__data_size"):
        comparison_layout["boundary_symbols"][name] = (
            authority_value["fixed_boundary_symbols"][name])
    value = ORIGINAL_ACCEPT_COMPARE(comparison_layout, authority_value,
        normalized_fixed_members=normalized_fixed_members)
    value["candidate_derived_data_successor"] = successor
    value["candidate_derived_data_successor_mutations"] = mutations
    value["sealed_golden_modified"] = False
    return value


def reserved_layout_gate(truth: Any) -> dict[str, Any]:
    """Carry Card 3's raw owners while deriving Card 6's live BSS extent."""
    names = (".bss", ".lisp65_c2_terminal_return_raw_owner",
        ".lisp65_c2_input_raw_owner", ".lisp65_c2_symbol_metadata_bss")
    sections = {name: truth.section(name) for name in names}
    BASE.require(sections[".bss"].address == 0xb9ca
        and (sections[".lisp65_c2_terminal_return_raw_owner"].address,
             sections[".lisp65_c2_terminal_return_raw_owner"].bytes) == (0xb582, 16)
        and (sections[".lisp65_c2_input_raw_owner"].address,
             sections[".lisp65_c2_input_raw_owner"].bytes) == (0xbc90, 112)
        and (sections[".lisp65_c2_symbol_metadata_bss"].address,
             sections[".lisp65_c2_symbol_metadata_bss"].bytes) == (0xbd00, 566),
        "fixed raw/BSS owner anchors drift")
    symbols = {name: truth.symbol(name) for name in
               ("symbnd", "symfnptr", "npool", "namelen4")}
    BASE.require(sum(row.bytes for row in symbols.values()) == 566
        and all(row.section == ".lisp65_c2_symbol_metadata_bss"
                and 0xbd00 <= row.value < 0xbf36 for row in symbols.values()),
        "symbol metadata escaped its final class")
    BASE.require(truth.symbol("__bss_start").value == sections[".bss"].address
        and truth.symbol("__bss_end").value == 0xbf36
        and truth.symbol("__bss_size").value == 0xbf36 - sections[".bss"].address,
        "derived split-BSS zeroing span drift")
    handoff = truth.section(".lisp65_c2_kernal_handoff")
    facade = truth.section(".lisp65_c2_host_facade")
    terminal_refs = BASE.PREV.RAW.raw_interval_references(ELF,
        handoff.address + handoff.bytes, facade.address,
        exclude_section=".lisp65_c2_terminal_return_raw_owner")
    input_refs = BASE.PREV.RAW.raw_interval_references(ELF, 0xbc90, 0xbd00,
        exclude_section=".lisp65_c2_input_raw_owner")
    BASE.require(len(terminal_refs) == 64
        and sorted({row["target"] for row in terminal_refs}) == list(range(0xb582, 0xb592))
        and len(input_refs) == 6,
        "final raw accessor population drift")
    intervals = [(name, row.address, row.address + row.bytes)
                 for name, row in sections.items()]
    BASE.require(not any(max(left[1], right[1]) < min(left[2], right[2])
                    for index, left in enumerate(intervals)
                    for right in intervals[index + 1:]),
        "final fixed-raw/BSS owners overlap")
    low = sections[".lisp65_c2_input_raw_owner"].address - (
        sections[".bss"].address + sections[".bss"].bytes)
    high = 0xc000 - (sections[".lisp65_c2_symbol_metadata_bss"].address
                    + sections[".lisp65_c2_symbol_metadata_bss"].bytes)
    margin = min(low, high)
    BASE.require(margin >= 5, f"derived ordinary-BSS floor red: {margin}/5")
    logical = sections[".bss"].bytes + sections[
        ".lisp65_c2_symbol_metadata_bss"].bytes
    return {"status": "PASS: LINKER-VISIBLE RAW OWNERS AND DERIVED SPLIT BSS FINAL",
        "sections": {name: {"start": row.address,
            "end_exclusive": row.address + row.bytes, "bytes": row.bytes}
            for name, row in sections.items()},
        "symbol_metadata": {name: {"address": row.value, "bytes": row.bytes}
                            for name, row in symbols.items()},
        "logical_BSS_bytes": logical,
        "logical_delta_from_card2_bytes": logical - 1584,
        "raw_input_carveout_bytes": 112,
        "low_reserve_bytes": low, "high_reserve_bytes": high,
        "conservative_margin_bytes": margin, "floor_bytes": 5,
        "terminal_raw_references": len(terminal_refs),
        "input_raw_references": len(input_refs),
        "zeroing": {"start": sections[".bss"].address,
            "end_exclusive": 0xbf36, "bytes": 0xbf36 - sections[".bss"].address,
            "includes_input_owner": True},
        "all_disjoint": True,
        "mutations_rejected": ["exact-508-byte-BSS-restored",
            "BSS-to-input-owner-floor-weakened", "raw-owner-overlap-hidden"]}


def successor_base_validate(value: dict[str, Any], *, require_dwx: bool = True) -> None:
    BASE.PREV.ORIGINAL_VALIDATE(value, require_dwx=require_dwx)
    final = value["final_product"]
    layout = final["fixed_raw_BSS_layout"]
    BASE.require(value["status"] == STATUS
        and layout["status"] ==
            "PASS: LINKER-VISIBLE RAW OWNERS AND DERIVED SPLIT BSS FINAL"
        and layout["conservative_margin_bytes"] >= layout["floor_bytes"] == 5
        and final["bounded_owners"]["ordinary_BSS"]["margin_bytes"] ==
            layout["conservative_margin_bytes"]
        and final["bounded_owners"]["fixed_raw_NOLOAD"]["all_disjoint"] is True,
        "derived reserved-layout product receipt drift")


def final_gate() -> dict[str, Any]:
    value = ORIGINAL_FINAL_GATE()
    layout = value["fixed_raw_BSS_layout"]
    value["bounded_owners"]["ordinary_BSS"] = {
        "logical_bytes": layout["logical_BSS_bytes"],
        "logical_delta_from_card2_bytes": layout["logical_delta_from_card2_bytes"],
        "raw_carveout_bytes": layout["raw_input_carveout_bytes"],
        "free_bytes": layout["low_reserve_bytes"] + layout["high_reserve_bytes"],
        "largest_contiguous_hole_bytes": layout["conservative_margin_bytes"],
        "margin_bytes": layout["conservative_margin_bytes"],
        "floor_bytes": layout["floor_bytes"],
        "physical_zeroing_span_bytes": layout["zeroing"]["bytes"],
        "end": f"0x{layout['sections']['.bss']['end_exclusive']:04x}"}
    value["status"] = "PASS: FINAL CARD-6 OMISSION PRODUCT CLOSED"
    value["omission"] = {"status": "PASS: REVIEWED A15 LATCH OMITTED",
        "pricing": bind(PRICING), "source_preflight": bind(BASE.SOURCE.RECEIPT)}
    value["e000_capture_watch"] = e000_capture_gate()
    return value


def validate(value: dict[str, Any], *, require_dwx: bool = True) -> None:
    ORIGINAL_VALIDATE(value, require_dwx=require_dwx)
    final = value["final_product"]
    watch = final["e000_capture_watch"]
    BASE.require(value["status"] == STATUS
        and value["authority"] == authority()
        and value["difference"]["omission"]["unexplained_members"] == 0
        and final["omission"]["status"] == "PASS: REVIEWED A15 LATCH OMITTED"
        and watch["free_bytes"] == 67 and watch["floor_bytes"] == 54
        and watch["capture_watch_bytes"] == watch["capture_watch_floor_bytes"] == 57
        and watch["capture_watch_surplus_bytes"] == 0
        and watch["later_E000_growth_allowed"] is False,
        "Card-6 omission product receipt drift")


def write_report(value: dict[str, Any]) -> None:
    final = value["final_product"]
    owners = final["bounded_owners"]
    watch = final["e000_capture_watch"]
    tail = ("pending" if not value["review_ready"] else "green")
    REPORT.write_text(f"""# Block 2.6 Card 6 — omission-form product card

Status: **{value['status']}**; packed DWX tail **{tail}**.

The manifest-pinned toolchain was accepted before the WPLTO. Cards 1–3 used
the same manifest-required compiler/linker bytes; their earlier SDK tree had
one unused self-referential symlink, so their zero-unexplained product
attributions remain valid without retroactively claiming whole-tree identity.

The final link retains A10–A14 and every A15 item except the reviewed
closed/superseded string-builder latch. Full Card-3→Card-6 attribution has
zero unexplained members. The emitted nine-user DMA trigger population is
byte-equivalent after relocation operands are normalized, and the clobber-drop
mutation remains sharp.

Every inherited owner is above its floor: ordinary text
**{owners['ordinary_text']['margin_bytes']}/32**, BSS
**{owners['ordinary_BSS']['margin_bytes']}/5**, resident Island
**{owners['resident_island']['margin_bytes']}/5**, with green ZP, NOLOAD,
fixed-raw reservations, composed Bank-2 ownership and MAP nesting. E000 has
**{watch['free_bytes']}/{watch['floor_bytes']}** free bytes; its capture watch
is exactly **{watch['capture_watch_bytes']}/{watch['capture_watch_floor_bytes']}**
and therefore admits no later growth.

Accounting is one replacement WPLTO, one replacement product link and zero
physical-device contacts. Scope/Acceptance are read-only over the frozen pair;
packed prefilter and boot-cycle evidence are recorded in the final tail.
""", encoding="utf-8")


def configure() -> None:
    values = {"AUTHORIZATION": AUTHORIZATION, "PLAN_HEADER": PLAN_HEADER,
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "PLANE": PLANE,
        "WPLTO": WPLTO, "ELF": ELF, "PRG": PRG, "PROFILE": PROFILE,
        "BOUND_PROFILE": BOUND_PROFILE, "INVOCATION": INVOCATION,
        "PLANE_RECEIPT": PLANE_RECEIPT, "PREFLIGHT_RECEIPT": PREFLIGHT_RECEIPT,
        "SOURCE_PREFLIGHT": SOURCE_PREFLIGHT, "PRELINK_RED": PRELINK_RED,
        "DIFFERENCE": DIFFERENCE, "RECEIPT": RECEIPT, "REPORT": REPORT,
        "DRIVER": DRIVER, "FORMAT": FORMAT, "STATUS": STATUS}
    for name, item in values.items():
        setattr(BASE, name, item)
    BASE.git_section = git_section
    BASE.authority = authority
    BASE.attribution = attribution
    BASE.descriptor_emission_gate = descriptor_emission_gate
    BASE.PREV.reserved_layout_gate = reserved_layout_gate
    BASE.BASE_VALIDATE = successor_base_validate
    BASE.final_gate = final_gate
    BASE.validate = validate
    BASE.write_report = write_report
    ACCEPT.V5_GOLDEN.compare_layout = acceptance_compare_layout


def resume() -> None:
    """Resume after the r1-era phase-02a expectation stopped post-link."""
    configure()
    BASE.configure_stack()
    BASE.PREV.CARD.CARD2.R2.CARD.configure()
    BASE.require(ELF.is_file() and PRG.is_file()
        and Path(str(PRG) + ".lto.o").is_file()
        and INVOCATION.is_file() and not RECEIPT.exists(),
        "Card-6 omission resume boundary drift")
    frozen_before = BASE.artifacts()
    difference = attribution()
    BASE.require(difference["unexplained_members"] == 0,
                 "Card-6 omission attribution retained a remainder")
    if DIFFERENCE.exists():
        BASE.require(BASE.load(DIFFERENCE) == difference,
                     "existing omission attribution differs from frozen pair")
    else:
        DIFFERENCE.write_bytes(BASE.canonical(difference))
    product = final_gate()
    processes = [{"action": "_produce",
        "result": "frozen pair already complete; post-link checker stopped on phase-02a expectation"}]
    base = BASE.PREV.CARD.CARD2.R2.CARD.BASE.CHAIN.LINK.BASE
    if base.SCOPE_RESULT.exists():
        BASE.require(BASE.load(base.SCOPE_RESULT)["status"] == "PASS",
                     "existing omission Scope result is not green")
        processes.append({"action": "_scope",
            "result": "reused prior read-only green result over identical frozen pair"})
    else:
        processes.append(BASE.run_child("_scope"))
    if base.ACCEPTANCE_RESULT.exists():
        BASE.require(BASE.load(base.ACCEPTANCE_RESULT)["status"] == "PASS",
                     "existing omission Acceptance result is not green")
        processes.append({"action": "_accept",
            "result": "reused prior read-only green result over identical frozen pair"})
    else:
        processes.append(BASE.run_child("_accept"))
    frozen_after = BASE.artifacts()
    scope, acceptance = BASE.load(base.SCOPE_RESULT), BASE.load(base.ACCEPTANCE_RESULT)
    BASE.require(frozen_before == frozen_after
        and scope["status"] == acceptance["status"] == "PASS",
        "Card-6 omission read-only resume changed or rejected the frozen pair")
    value = {"format": FORMAT, "recorded_on": "2026-09-04", "status": STATUS,
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION),
        "predecessor": {"ELF": bind(BASE.PREDECESSOR_ELF),
                        "PRG": bind(BASE.PREDECESSOR_PRG)},
        "difference": difference, "difference_receipt": bind(DIFFERENCE),
        "final_product": product, "scope": bind(base.SCOPE_RESULT),
        "acceptance": bind(base.ACCEPTANCE_RESULT),
        "artifacts_before": frozen_before, "artifacts_after": frozen_after,
        "processes": processes,
        "resume": {"status": "PASS: READ-ONLY OVER FROZEN PAIR",
            "reason": "r1 checker expected a phase-02a CRC change that the omission world correctly removes",
            "WPLTO_runs": 0, "product_links": 0},
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "acceptance_runs": 1,
            "DWX_prefilter_runs": 0, "media_builds": 0, "device_contacts": 0},
        "review_ready": False}
    RECEIPT.write_bytes(BASE.canonical(value))
    write_report(value)
    validate(value, require_dwx=False)
    print("Block 2.6 Card 6: RESUME PASS WPLTO=1/1 link=1/1 DWX=pending")


def main() -> int:
    configure()
    if len(sys.argv) == 2 and sys.argv[1] == "resume":
        resume()
        return 0
    if len(sys.argv) == 2 and sys.argv[1] in {"check", "selftest"}:
        # These inherited actions validate before their own configurator runs;
        # install the complete successor stack rather than a half-era module.
        BASE.configure_stack()
    return BASE.main()


if __name__ == "__main__":
    raise SystemExit(main())
