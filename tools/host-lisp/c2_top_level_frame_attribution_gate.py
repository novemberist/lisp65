#!/usr/bin/env python3
"""Source and contract gate for the nonpromotable top-level frame probe."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import elf_truth as ELF  # noqa: E402
CONTRACT = ROOT / "config/c2-top-level-frame-attribution-contract.json"
HEADER = ROOT / "src/c2_phase_scratch.h"
EMITTER = ROOT / "src/c2_session_emitter.c"
RUNTIME = ROOT / "src/c2_product_runtime.c"
DECODER = ROOT / "scripts/c2-stream-decoder.c"
DECODER_V2 = ROOT / "scripts/c2-stream-v2-decoder.c"
PROFILE = ROOT / "config/c2-l-full-product-profile.json"


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


STATIONS = (
    ("EMIT_FINAL_CRC", "c2_session_emit_final_crc_phase", "emitter"),
    ("APPEND_ENVELOPE", "c2_append_envelope_phase", "runtime"),
    ("RESERVE_TRANSIENT_BOUNDS",
     "c2_append_reserve_transient_bounds_phase", "runtime"),
    ("STAGE_COPY", "c2_append_stage_copy_phase", "runtime"),
    ("STAGE_PLANE", "c2_append_stage_plane_phase", "runtime"),
    ("DECODE_04", "c2_stream_phase_04", "decoder"),
    ("DECODE_06A", "c2_stream_phase_06a", "decoder"),
    ("DECODE_09", "c2_stream_phase_09", "decoder_v2"),
    ("DECODE_12", "c2_stream_phase_12", "decoder_v2"),
    ("APPEND_HEADER", "c2_append_header_phase", "runtime"),
    ("INNER_VM", "c2_product_install", "runtime"),
    ("ROLLBACK_PREPARE", "c2_append_rollback_prepare_phase", "runtime"),
    ("ROLLBACK_UNPUBLISH", "c2_append_rollback_unpublish_phase", "runtime"),
    ("ROLLBACK_FINALIZE", "c2_append_rollback_finalize_phase", "runtime"),
    ("JOURNAL_CLEAR", "c2_append_journal_clear_phase", "runtime"),
)


def source_bundle() -> dict[str, Any]:
    return {
        "contract": json.loads(CONTRACT.read_text(encoding="utf-8")),
        "header": HEADER.read_text(encoding="utf-8"),
        "emitter": EMITTER.read_text(encoding="utf-8"),
        "runtime": RUNTIME.read_text(encoding="utf-8"),
        "decoder": DECODER.read_text(encoding="utf-8"),
        "decoder_v2": DECODER_V2.read_text(encoding="utf-8"),
        "profile": PROFILE.read_text(encoding="utf-8"),
    }


def validate(bundle: dict[str, Any]) -> dict[str, Any]:
    contract = bundle["contract"]
    storage = contract["storage"]
    require(
        contract["format"]
            == "lisp65-c2-top-level-frame-attribution-contract-v1"
        and contract["scope"]["promotable"] is False
        and contract["scope"]["latency_attempts_consumed"] == 0,
        "frame-attribution contract scope drift",
    )
    require(
        (storage["scratch_bytes"], storage["offset"],
         storage["result_bytes"], storage["end_exclusive"],
         storage["installer_trace_offset"])
        == (304, 287, 15, 302, 302),
        "frame-attribution scratch geometry drift",
    )
    clock = contract["clock"]
    require(
        clock["low_address"] == "0xff83"
        and clock["stored_width_bytes"] == 1
        and clock["delta"] == "(next-current)&0xff"
        and "below 256 frames" in clock["admissibility"],
        "frame attribution does not have an exact low-byte clock contract",
    )
    header = bundle["header"]
    required_header = (
        "#define LISP65_C2_FRAME_ATTRIBUTION_OFFSET 287u",
        "#define LISP65_C2_FRAME_ATTRIBUTION_BYTES 15u",
        "*(volatile const uint8_t *)(uintptr_t)LISP65_C2_FRAME_LO_ADDRESS",
        "+ LISP65_C2_FRAME_ATTRIBUTION_BYTES",
        "== LISP65_C2_INSTALL_TRACE_OFFSET",
    )
    require(all(row in header for row in required_header),
            "frame-attribution header geometry/dataflow drift")
    require(
        "sizeof(c2_append_state) <= LISP65_C2_FRAME_ATTRIBUTION_OFFSET"
            in bundle["runtime"],
        "live append scratch owner is not bounded before attribution results",
    )
    require(
        re.search(
            r"c2e\.active\s*=\s*0;\s*"
            r"C2_FRAME_ATTRIBUTION_STAMP\("
            r"LISP65_C2_FRAME_ATTR_EMIT_FINAL_CRC\);\s*"
            r"return C2_STREAM_OK;",
            bundle["emitter"],
        ) is not None,
        "first timestamp is not after the final emitter-state read",
    )
    require("LISP65_C2_FRAME_ATTRIBUTION_DIAGNOSTIC"
            not in bundle["profile"],
            "nonpromotable frame probe leaked into canonical product profile")

    rows = contract["stations"]
    require(
        len(rows) == len(STATIONS)
        and [row["index"] for row in rows] == list(range(len(STATIONS)))
        and len({row["symbol"] for row in rows}) == len(STATIONS),
        "frame-attribution station inventory/index drift",
    )
    observed: list[dict[str, Any]] = []
    for index, (token, symbol, source_name) in enumerate(STATIONS):
        row = rows[index]
        require(row["symbol"] == symbol,
                f"contract symbol drift at station {index}")
        call = (
            "C2_FRAME_ATTRIBUTION_STAMP("
            f"LISP65_C2_FRAME_ATTR_{token})")
        source = re.sub(r"\s+", "", bundle[source_name])
        compact_call = re.sub(r"\s+", "", call)
        require(source.count(compact_call) == 1,
                f"station marker absent or duplicated: {symbol}")
        require(
            re.search(
                rf"\b{re.escape(symbol)}\s*\([^)]*\)\s*\{{",
                bundle[source_name],
            ) is not None,
            f"station function absent: {symbol}",
        )
        enum = re.search(
            rf"LISP65_C2_FRAME_ATTR_{token}\s*=\s*(\d+)u", header)
        require(enum is not None and int(enum.group(1)) == index,
                f"station enum drift: {token}")
        observed.append({
            "index": index, "id": row["id"], "symbol": symbol,
            "source": source_name,
        })
    return {
        "status": "passed-nonpromotable-source-and-lifetime-contract",
        "stations": observed,
        "frame_low_address": clock["low_address"],
        "scratch_result_span": [287, 302],
        "installer_trace_span": [302, 304],
        "new_bss_bytes": 0,
        "latency_attempts_consumed": 0,
    }


def mutation_tests(bundle: dict[str, Any]) -> int:
    mutations: list[dict[str, Any]] = []

    def changed(path: tuple[str, ...], value: Any) -> dict[str, Any]:
        item = copy.deepcopy(bundle)
        cursor: Any = item
        for name in path[:-1]:
            cursor = cursor[name]
        cursor[path[-1]] = value
        return item

    mutations.extend([
        changed(("contract", "clock", "low_address"), "0xff84"),
        changed(("contract", "storage", "offset"), 240),
        changed(("contract", "storage", "end_exclusive"), 303),
        changed(("contract", "clock", "delta"), "next-current"),
    ])
    missing = copy.deepcopy(bundle)
    missing["contract"]["stations"].pop()
    mutations.append(missing)
    duplicate = copy.deepcopy(bundle)
    duplicate["contract"]["stations"][14]["index"] = 13
    mutations.append(duplicate)
    swapped = copy.deepcopy(bundle)
    swapped["contract"]["stations"][3], swapped["contract"]["stations"][4] = (
        swapped["contract"]["stations"][4],
        swapped["contract"]["stations"][3],
    )
    mutations.append(swapped)
    leaked = copy.deepcopy(bundle)
    leaked["profile"] += "\nLISP65_C2_FRAME_ATTRIBUTION_DIAGNOSTIC\n"
    mutations.append(leaked)
    for index, item in enumerate(mutations):
        try:
            validate(item)
        except GateError:
            continue
        raise GateError(f"frame-attribution mutation accepted: {index}")
    return len(mutations)


def linked_gate(elf: Path, llvm_readobj: Path) -> dict[str, Any]:
    """Bind every station to its section-qualified function and store byte.

    The final ELF has no relocation left for the fixed frame cell.  We still
    avoid rendered disassembly: elf_truth supplies section identity, bounded
    function intervals and raw section bytes; the gate recognizes the six
    actual MOS bytes for one same-register absolute load/store pair.
    """
    truth = ELF.ElfTruth.read(
        elf, llvm_readobj=llvm_readobj, include_section_data=True)
    scratch = truth.symbol("lisp65_c2_phase_scratch")
    require(
        scratch.symbol_type == "Object" and scratch.bytes == 304
        and scratch.value + 287 == 0xC1E5,
        "linked phase scratch identity/geometry drift",
    )
    pairs = ((0xAD, 0x8D, "A"), (0xAE, 0x8E, "X"),
             (0xAC, 0x8C, "Y"))
    rows: list[dict[str, Any]] = []
    for index, (_, symbol_name, _) in enumerate(STATIONS):
        symbol = truth.symbol(symbol_name)
        require(
            symbol.symbol_type == "Function" and symbol.bytes > 0
            and symbol.section not in ("Absolute", "Undefined"),
            f"attribution station is not a sized ELF function: {symbol_name}",
        )
        section = truth.section(symbol.section)
        data = truth.section_bytes(symbol.section)
        begin = symbol.value - section.address
        end = begin + symbol.bytes
        require(0 <= begin < end <= len(data),
                f"station interval outside its section: {symbol_name}")
        target = scratch.value + 287 + index
        found: list[tuple[int, str]] = []
        for load, store, register in pairs:
            pattern = bytes((
                load, 0x83, 0xFF, store,
                target & 0xFF, target >> 8,
            ))
            at = data.find(pattern, begin, end)
            while at >= 0:
                found.append((section.address + at, register))
                at = data.find(pattern, at + 1, end)
        require(len(found) == 1,
                f"station has no unique ff83-to-result dataflow: "
                f"{symbol_name} found={found}")
        rows.append({
            "index": index,
            "symbol": symbol_name,
            "section": symbol.section,
            "function_start": symbol.value,
            "function_bytes": symbol.bytes,
            "instruction_address": found[0][0],
            "register": found[0][1],
            "frame_source": 0xFF83,
            "result_address": target,
        })
    require(
        [row["result_address"] for row in rows]
        == list(range(0xC1E5, 0xC1F4))
        and len({row["section"] for row in rows}) == len(rows),
        "linked attribution result span or overlay identity collapsed",
    )
    return {
        "status":
            "passed-15-section-qualified-ff83-to-scratch-dataflows",
        "scratch": {
            "section": scratch.section,
            "address": scratch.value,
            "bytes": scratch.bytes,
            "result_address_span": [0xC1E5, 0xC1F4],
            "installer_trace_address_span": [0xC1F4, 0xC1F6],
        },
        "stations": rows,
        "overlay_sections_unique": len(rows),
    }


def main() -> int:
    bundle = source_bundle()
    value = validate(bundle)
    value["mutations_rejected"] = mutation_tests(bundle)
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"c2-top-level-frame-attribution-gate: FIRST RED: {error}")
        raise SystemExit(2)
