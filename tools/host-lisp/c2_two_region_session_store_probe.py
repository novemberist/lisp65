#!/usr/bin/env python3
"""Contract-only probe for the proposed two-region Session L65R store.

The probe deliberately does not modify the L65R emitter, decoder, product
sources or linker inputs.  It answers three narrower questions:

* whether the current Bank-5 map contains a bounded region without colliding
  with C2D, emitter roots, C2J or the external symbol arena;
* whether a width-neutral, region-qualified successor record can be made
  fail-closed; and
* whether the measured Session aggregate has a numerically complete placement
  construction once rollback-finalize is split.

The current strict L65R-v3 decoder has no region identity.  Consequently this
probe is expected to finish as a format First Red even when the geometry and
the proposed strict-v4 model are green.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-two-region-session-store-contract-probe.json"
DOCUMENT = ROOT / "docs/planning/c2.2-two-region-session-store-contract-probe.md"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-two-region-session-store-contract-probe-first-red.json")
BASELINE_MANIFEST = ROOT / (
    "build/c2.2/substitution/"
    "link59-c1-freezer-irq-episode-recovery-wplto/"
    "runtime-overlays-session-unbound.json")
ATTRIBUTION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-cpu-chip-write-completion-rollback-finalize-attribution-first-red.json")
C2D = ROOT / (
    "build/c2.2/substitution/"
    "link59-c1-freezer-irq-episode-recovery-wplto/"
    "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
L65R_TOOL = ROOT / "tools/host-lisp/runtime_overlay_bank.py"
L65R_TARGET = ROOT / "src/vm_runtime_overlay.c"
C2_RUNTIME = ROOT / "src/c2_product_runtime.c"
C2_HEADER = ROOT / "src/c2_product_runtime.h"
EMITTER = ROOT / "src/c2_session_emitter.c"
WORKBENCH = ROOT / "config/workbench.mk"

ENTRY = struct.Struct("<HHHHHHHHIHHII")
ENTRY_BYTES = 32
RECORD_CRC_OFFSET = 22
REGION_OFFSET = 24
PAYLOAD_ALIGN = 256
CRC16_INIT = 0xFFFF
CRC16_POLY = 0x1021


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing authority: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def crc16(data: bytes | bytearray) -> int:
    value = CRC16_INIT
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ CRC16_POLY) & 0xFFFF \
                if value & 0x8000 else (value << 1) & 0xFFFF
    return value


def align(value: int) -> int:
    return (value + PAYLOAD_ALIGN - 1) & ~(PAYLOAD_ALIGN - 1)


def macro(text: str, name: str) -> int:
    match = re.search(
        rf"^#define\s+{re.escape(name)}\s+(0x[0-9a-fA-F]+|\d+)u?",
        text, re.MULTILINE)
    if match is None:
        match = re.search(
            rf"(?:^|\s)-D{re.escape(name)}=(0x[0-9a-fA-F]+|\d+)"
            rf"(?:\s|$)", text, re.MULTILINE)
    require(match is not None, f"macro absent: {name}")
    return int(match.group(1), 0)


def proposed_record(*, slot: int, region: int, file_offset: int,
                    file_size: int, build_id: int = 0x5A17C2D4) -> bytes:
    record = bytearray(ENTRY.pack(
        slot, 0x0006, file_offset, file_size, 0xC356, file_size,
        0, 1, build_id, 0xA55A, 0, region, 0))
    seal = crc16(record)
    require(seal != 0, "model emitted forbidden zero record CRC")
    struct.pack_into("<H", record, RECORD_CRC_OFFSET, seal)
    return bytes(record)


def validate_v4_record(record: bytes, *, main_payload_offset: int,
                       main_limit: int, overflow_limit: int) -> None:
    require(len(record) == ENTRY_BYTES, "record width")
    raw = bytearray(record)
    expected = struct.unpack_from("<H", raw, RECORD_CRC_OFFSET)[0]
    require(expected != 0, "record CRC zero")
    raw[RECORD_CRC_OFFSET:RECORD_CRC_OFFSET + 2] = b"\x00\x00"
    require(crc16(raw) == expected, "record CRC mismatch")
    region = record[REGION_OFFSET]
    require(region in (0, 1), "unknown region")
    require(not any(record[REGION_OFFSET + 1:]), "region reserved bytes")
    file_offset, file_size = struct.unpack_from("<HH", record, 4)
    require(file_size != 0 and file_size <= 1792, "slice size")
    require((file_offset & (PAYLOAD_ALIGN - 1)) == 0, "payload alignment")
    if region == 0:
        require(file_offset >= main_payload_offset, "main payload floor")
        require(file_offset + file_size <= main_limit, "main region bounds")
    else:
        require(file_offset + file_size <= overflow_limit,
                "overflow region bounds")


def mutation(name: str, base: bytes, change: Callable[[bytearray], None],
             *, main_payload_offset: int, main_limit: int,
             overflow_limit: int, reseal: bool = False) -> dict[str, Any]:
    data = bytearray(base)
    change(data)
    if reseal:
        data[RECORD_CRC_OFFSET:RECORD_CRC_OFFSET + 2] = b"\x00\x00"
        struct.pack_into("<H", data, RECORD_CRC_OFFSET, crc16(data))
    rejected = False
    detail = ""
    try:
        validate_v4_record(
            bytes(data), main_payload_offset=main_payload_offset,
            main_limit=main_limit, overflow_limit=overflow_limit)
    except ProbeError as error:
        rejected = True
        detail = str(error)
    require(rejected, f"mutation survived: {name}")
    return {"name": name, "rejected": True, "reason": detail}


def main() -> int:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    manifest = json.loads(BASELINE_MANIFEST.read_text(encoding="utf-8"))
    attribution = json.loads(ATTRIBUTION.read_text(encoding="utf-8"))
    target = L65R_TARGET.read_text(encoding="utf-8")
    tool = L65R_TOOL.read_text(encoding="utf-8")
    runtime = C2_RUNTIME.read_text(encoding="utf-8")
    header = C2_HEADER.read_text(encoding="utf-8")
    emitter = EMITTER.read_text(encoding="utf-8")
    workbench = WORKBENCH.read_text(encoding="utf-8")

    geometry = contract["geometry"]
    c2d_bytes = macro(header, "LISP65_C2D_BYTES")
    c2d_region_bytes = macro(header, "LISP65_C2D_REGION_BYTES")
    c2j_base = macro(runtime, "C2D_UNWIND_BASE")
    c2j_bytes = macro(runtime, "C2D_UNWIND_BYTES")
    plan_bytes = macro(runtime, "C2_EXPORT_PLAN_RECORD_BYTES")
    entry_cap = macro(runtime, "C2D_ENTRY_CAP")
    root_cap = macro(runtime, "C2D_ROOT_CAP")
    root_count = struct.unpack_from("<H", C2D.read_bytes(), 24)[0]
    entry_count = struct.unpack_from("<H", C2D.read_bytes(), 16)[0]
    root_state_bytes = 48 * 7
    root_state_base = c2j_base - root_state_bytes
    sympool = macro(workbench, "SYMPOOL_EXT_OFF")

    overflow_base = int(geometry["overflow_base"], 0)
    overflow_end = int(geometry["overflow_end"], 0)
    overflow_bytes = overflow_end - overflow_base
    growth_floor = overflow_base - c2d_bytes
    export_rows = growth_floor // plan_bytes
    export_growth = export_rows - entry_count
    root_growth = root_cap - root_count

    require(len(C2D.read_bytes()) == c2d_bytes, "C2D byte authority drift")
    require(c2d_region_bytes == c2j_base + c2j_bytes,
            "C2D region/C2J end drift")
    require(root_state_base == overflow_end,
            "overflow does not end at emitter-root base")
    require(overflow_end <= c2j_base, "overflow overlaps C2J")
    require(c2d_region_bytes == sympool,
            "C2D region no longer ends at the external symbol arena")
    require(overflow_base % PAYLOAD_ALIGN == 0,
            "overflow physical base is not 256-byte aligned")
    require(overflow_bytes == int(geometry["overflow_bytes"]),
            "overflow byte cap drift")
    require(growth_floor == int(geometry["c2d_growth_floor_bytes"]),
            "C2D growth floor drift")

    current_format = {
        "catalog_version": manifest["catalog"]["version"],
        "entry_bytes": manifest["catalog"]["entry_size"],
        "all_capability_masks_zero": all(
            row["capability_mask"] == 0 for row in manifest["slices"]),
        "target_rejects_bytes_24_through_31": (
            "record[24] || record[25] || record[26] || record[27] ||"
            in target and
            "record[28] || record[29] || record[30] || record[31]"
            in target),
        "host_versions": [
            int(value) for value in re.findall(
                r"^VERSION(?:_V\d)?\s*=\s*(\d+)\s*$", tool,
                re.MULTILINE)],
        "region_field": False,
        "verdict": (
            "FIRST RED: strict L65R-v3 binds one family-wide storage base; "
            "bytes 24..31 are required zero by the product decoder"),
    }
    require(current_format["catalog_version"] == 3, "baseline is not v3")
    require(current_format["entry_bytes"] == ENTRY_BYTES, "entry width drift")
    require(current_format["all_capability_masks_zero"],
            "baseline already contains a nonzero capability")
    require(current_format["target_rejects_bytes_24_through_31"],
            "strict-v3 reserved-byte proof drift")
    require(4 not in current_format["host_versions"],
            "v4 already exists; contract probe premise changed")

    main_payload_offset = manifest["catalog"]["payload_offset"]
    main_limit = 0x10000
    overflow_limit = overflow_bytes
    unpublish = proposed_record(
        slot=41, region=1, file_offset=0, file_size=758)
    wipes = proposed_record(
        slot=42, region=1, file_offset=768, file_size=919)
    validate_v4_record(
        unpublish, main_payload_offset=main_payload_offset,
        main_limit=main_limit, overflow_limit=overflow_limit)
    validate_v4_record(
        wipes, main_payload_offset=main_payload_offset,
        main_limit=main_limit, overflow_limit=overflow_limit)

    mutations = [
        mutation("region-bit-without-record-reseal", unpublish,
                 lambda b: b.__setitem__(REGION_OFFSET, 0),
                 main_payload_offset=main_payload_offset,
                 main_limit=main_limit, overflow_limit=overflow_limit),
        mutation("unknown-region-2", unpublish,
                 lambda b: b.__setitem__(REGION_OFFSET, 2),
                 main_payload_offset=main_payload_offset,
                 main_limit=main_limit, overflow_limit=overflow_limit,
                 reseal=True),
        mutation("reserved-region-byte", unpublish,
                 lambda b: b.__setitem__(REGION_OFFSET + 1, 1),
                 main_payload_offset=main_payload_offset,
                 main_limit=main_limit, overflow_limit=overflow_limit,
                 reseal=True),
        mutation("unaligned-overflow-offset", unpublish,
                 lambda b: struct.pack_into("<H", b, 4, 1),
                 main_payload_offset=main_payload_offset,
                 main_limit=main_limit, overflow_limit=overflow_limit,
                 reseal=True),
        mutation("overflow-end-plus-one", wipes,
                 lambda b: struct.pack_into("<H", b, 6,
                                            overflow_limit - 768 + 1),
                 main_payload_offset=main_payload_offset,
                 main_limit=main_limit, overflow_limit=overflow_limit,
                 reseal=True),
        mutation("slice-over-1792", unpublish,
                 lambda b: struct.pack_into("<H", b, 6, 1793),
                 main_payload_offset=main_payload_offset,
                 main_limit=main_limit, overflow_limit=overflow_limit,
                 reseal=True),
        mutation("main-offset-below-catalog-payload", proposed_record(
                     slot=41, region=0, file_offset=main_payload_offset,
                     file_size=758),
                 lambda b: struct.pack_into("<H", b, 4,
                                            main_payload_offset - 256),
                 main_payload_offset=main_payload_offset,
                 main_limit=main_limit, overflow_limit=overflow_limit,
                 reseal=True),
        mutation("main-end-plus-one", proposed_record(
                     slot=41, region=0, file_offset=0xFF00,
                     file_size=0x100),
                 lambda b: struct.pack_into("<H", b, 6, 0x101),
                 main_payload_offset=main_payload_offset,
                 main_limit=main_limit, overflow_limit=overflow_limit,
                 reseal=True),
        mutation("zero-file-size", unpublish,
                 lambda b: struct.pack_into("<H", b, 6, 0),
                 main_payload_offset=main_payload_offset,
                 main_limit=main_limit, overflow_limit=overflow_limit,
                 reseal=True),
    ]

    aggregate = attribution["session_aggregate_feasibility"]
    projected = aggregate["seal_probe_projected_bytes"]
    split_quantum_debit = 256
    moved_packed = align(758) + align(919)
    main_after = projected + split_quantum_debit - moved_packed
    overflow_span = align(758) + 919
    require(manifest["storage"]["size"] == 65438,
            "Link-59 Session aggregate drift")
    require(main_after == 65438, "two-region placement arithmetic drift")
    require(overflow_span <= overflow_bytes, "overflow payload does not fit")

    dma = {
        "class": "Chip-Bank-5 to Bank-0 overlay VMA",
        "existing_read_seam": "c2_stream_c2d_read -> c2_facade_vm_code_load",
        "source_bank": 5,
        "source_interval": [
            f"0x{overflow_base:04x}", f"0x{overflow_end:04x}"],
        "same_transport_primitive_as_c2d": (
            "c2_facade_vm_code_load(LISP65_C2D_BANK" in runtime),
        "new_hardware_assumption": False,
        "proof_limit": (
            "The transport class is already product/hardware exercised. "
            "A successor product gate must still prove that every region-1 "
            "record selects this seam and no Attic fallback remains."),
    }
    require(dma["same_transport_primitive_as_c2d"],
            "Bank-5 read seam no longer uses the canonical facade")

    value = {
        "format": "lisp65-c2-two-region-session-store-contract-probe-v1",
        "recorded_on": "2026-07-24",
        "status": (
            "FIRST RED: geometry and a strict width-neutral v4 model are "
            "feasible, but the current strict L65R-v3 product format has no "
            "region identity"),
        "promotable": False,
        "authority": {
            "contract": bind(CONTRACT),
            "contract_document": bind(DOCUMENT),
            "probe": bind(Path(__file__).resolve()),
            "baseline_session_manifest": bind(BASELINE_MANIFEST),
            "rollback_attribution": bind(ATTRIBUTION),
            "initial_c2d_v6": bind(C2D),
            "l65r_host_tool": bind(L65R_TOOL),
            "l65r_target_decoder": bind(L65R_TARGET),
            "c2_runtime": bind(C2_RUNTIME),
            "c2_runtime_header": bind(C2_HEADER),
            "emitter": bind(EMITTER),
            "workbench_map": bind(WORKBENCH),
        },
        "bank5_geometry": {
            "canonical_c2d": [0, c2d_bytes],
            "old_zero_suffix": [c2d_bytes, c2d_region_bytes],
            "export_plan_record_bytes": plan_bytes,
            "overflow_region": {
                "bank": 5,
                "base": overflow_base,
                "end_exclusive": overflow_end,
                "bytes": overflow_bytes,
                "alignment": PAYLOAD_ALIGN,
                "cap": "hard; no third region",
            },
            "emitter_roots": [root_state_base, c2j_base],
            "c2j": [c2j_base, c2d_region_bytes],
            "external_symbol_arena_start": sympool,
            "c2d_growth_floor_bytes": growth_floor,
            "export_plan_rows": export_rows,
            "current_entry_count": entry_count,
            "worst_case_dynamic_export_rows": export_growth,
            "remaining_root_ordinals": root_growth,
            "effective_worst_case_composition_delta": (
                export_growth - root_growth),
                "explanation": (
                    "Only 192 bytes of the old suffix were uncommitted at the "
                    "full 2048-row export-plan cap. The region therefore consumes "
                    "1840 bytes of potential export scratch. Under one exported "
                "row and one root per appended entry, the practical ceiling "
                "falls by 25 entries because roots previously bound first."),
            "verdict": "green with the explicit 14544-byte growth floor",
        },
        "current_l65r_v3": current_format,
        "proposed_strict_l65r_v4": {
            "status": "model green; Class-C format decision required",
            "header_bytes": 32,
            "entry_bytes": 32,
            "dual_decoder": False,
            "v3_input": "rejected",
            "record_region": {
                "offset": REGION_OFFSET,
                "bytes": 1,
                "values": {"0": "Bank-3 main Session store",
                           "1": "Bank-5 overflow region"},
                "reserved_zero": [25, 32],
                "record_crc_covers_region": True,
            },
            "offset_semantics": "u16 relative to the selected region",
            "header_reserved_u32_proposal": (
                "bind the used byte span of region 1; base and hard cap remain "
                "generated contract constants"),
            "mutations": mutations,
            "mutation_count": len(mutations),
        },
        "aggregate_construction": {
            "status": "arithmetically feasible; not yet a WPLTO claim",
            "seal_probe_session_bytes": projected,
            "finalize_semantic_split_quantum_debit": split_quantum_debit,
            "proposed_region1_members": [
                {"name": "rollback-unpublish", "raw_bytes": 758,
                 "packed_bytes": align(758), "temperature": "abort-only"},
                {"name": "rollback-wipes", "raw_model_bytes": 919,
                 "packed_bytes": align(919), "temperature": "abort-only",
                 "qualification": (
                     "sum of the three measured wipe bodies; the real split "
                     "must remeasure its phase wrapper under WPLTO")},
            ],
            "moved_packed_bytes": moved_packed,
            "region1_used_span_bytes": overflow_span,
            "region1_cap_bytes": overflow_bytes,
            "region1_next_aligned_headroom_bytes": (
                overflow_bytes - align(overflow_span)),
            "projected_main_region_bytes": main_after,
            "main_region_headroom_bytes": 65536 - main_after,
            "rule": (
                "The serial resident driver loads both region-1 phases. "
                "Neither overlay calls another overlay. Exact split sizes and "
                "the 98-byte main reserve require the later product WPLTO."),
        },
        "dma_transport": dma,
        "separate_walls": {
            "ordinary_text": {
                "deficit_after_vm_ext_write_candidate_bytes": 17,
                "status": "OPEN; no second named fund was found in this probe",
            },
            "e000": {
                "deficit_bytes": 28,
                "coldest_candidate": {
                    "symbol": "c2_append_run_rollback_plan",
                    "bytes": 29,
                    "temperature": "abort-only",
                    "disposition": "not presently relocatable",
                    "reason": (
                        "It is the resident serial overlay driver. Moving it "
                        "into either Session region would make an overlay call "
                        "overlays; moving it to ordinary text transfers 29 "
                        "bytes into an already-red currency."),
                },
                "other_candidates": [
                    {"symbol": "c2_session_emit_reset", "bytes": 47,
                     "temperature": "interactive-compile cold",
                     "reason_rejected": (
                         "shared resident emitter-state owner; moving it into "
                         "an emitter phase creates an overlay-to-overlay edge "
                         "for existing callers")},
                    {"symbol": "c2_append_begin", "bytes": 513,
                     "temperature": "append cold",
                     "reason_rejected": (
                         "transaction owner and multi-phase serial driver; not "
                         "a leaf-shaped window tenant")},
                ],
                "verdict": (
                    "No legal 28-byte evacuation exists under the present "
                    "walls and no-overlay-calls-overlay invariant."),
            },
        },
        "decision": {
            "product_sources_changed": False,
            "format_implemented": False,
            "split_implemented": False,
            "WPLTO_runs": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "next_review": (
                "Explicit Class-C choice: authorize strict L65R-v4 with the "
                "same 32-byte header/record widths and region byte at offset "
                "24, or reject the two-region Session store."),
        },
        "claim_limit": (
            "Contract geometry, format impossibility and host model only. "
            "No product format, packing, closure, capacity or hardware claim."),
        "rollback_line": "Link 59 remains untouched.",
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(json.dumps({
        "status": value["status"],
        "receipt": RECEIPT.relative_to(ROOT).as_posix(),
        "geometry": value["bank5_geometry"]["verdict"],
        "v4_mutations": f"{len(mutations)}/{len(mutations)}",
        "main_region_bytes": main_after,
        "overflow_span_bytes": overflow_span,
    }, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
