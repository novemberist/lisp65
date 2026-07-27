#!/usr/bin/env python3
"""Permanent gate for the five phase-06a read cutpoints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from elf_truth import ElfTruth


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-phase06a-cutpoint-contract.json"
SOURCES = {
    "header": ROOT / "scripts/c2-stream-decoder.h",
    "decoder": ROOT / "scripts/c2-stream-decoder.c",
    "v2_decoder": ROOT / "scripts/c2-stream-v2-decoder.c",
}
CUTPOINTS = (
    ("IMAGE_RECORD", 0x61, "c2_image_read(c,image,im)"),
    ("METADATA_HEADER", 0x62,
     "c2_stream_shelf_read(meta,h,sizeof(h))"),
    ("ENTRY_RECORD", 0x63,
     "c2_stream_shelf_read(meta+eo+(uint32_t)local*16u,e,sizeof(e))"),
    ("CODE_HEADER", 0x64,
     "c2_stream_shelf_read(code+at,co,sizeof(co))"),
    ("LITERAL_BLOCK", 0x65,
     "c2_stream_shelf_read(code+at+7u+done,zeros,n)"),
)


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def function_body(text: str, signature: str) -> str:
    start = text.find(signature)
    require(start >= 0, f"function absent: {signature}")
    brace = text.find("{", start)
    require(brace >= 0, f"function body absent: {signature}")
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise GateError(f"unterminated function: {signature}")


def sources() -> dict[str, str]:
    return {name: path.read_text(encoding="utf-8")
            for name, path in SOURCES.items()}


def compact(text: str) -> str:
    return "".join(text.split())


def fixture() -> dict[str, Any]:
    cases = {}
    for name, value, _read in CUTPOINTS:
        cases[name.lower()] = {
            "injected_read_failure": True,
            "reserved_after_failure": value,
            "phase06b_accepts": False,
        }
    cases["success"] = {
        "injected_read_failure": False,
        "reserved_after_phase06a": 0x6a,
        "phase06b_accepts": True,
    }
    require(len(cases) == 6
            and len({row["reserved_after_failure"] for row in cases.values()
                     if "reserved_after_failure" in row}) == 5
            and all(not row["phase06b_accepts"] for row in cases.values()
                    if row is not cases["success"]),
            "phase-06a cutpoint fixture drift")
    return {
        "status": "passed-five-failure-cutpoints-plus-success-handoff",
        "cases": cases,
        "cases_passed": len(cases),
    }


def source_gate(parts: dict[str, str] | None = None,
                *, mutations: bool = False) -> dict[str, Any]:
    text = parts or sources()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract["schema"] == "lisp65.c2.phase06a-read-cutpoint.v1"
            and contract["storage"]["object"] ==
                "c2_stream_context.reserved"
            and contract["storage"]["existing_bytes_reused"] == 1
            and contract["storage"]["new_bss_bytes"] == 0
            and contract["storage"]["new_gc_roots"] == 0
            and [row["value"] for row in contract["cutpoints"]] ==
                [value for _name, value, _read in CUTPOINTS]
            and contract["storage"]["success_handoff_value"] == 0x6a,
            "phase-06a cutpoint contract drift")

    header = text["header"]
    for name, value, _read in CUTPOINTS:
        require(f"#define LISP65_C2_PHASE_06A_CUT_{name} 0x{value:02x}u"
                in header, f"phase-06a marker definition drift: {name}")
    require("#define LISP65_C2_PHASE_06A_COMPLETE 0x6au" in header,
            "phase-06a completion marker drift")

    phase06a = compact(function_body(
        text["decoder"], "C2_SLICE(06a) uint8_t c2_stream_phase_06a("))
    phase06b = compact(function_body(
        text["decoder"], "C2_SLICE(06b) uint8_t c2_stream_phase_06b("))
    require("c->phase!=6u||c->error||c->reserved" in phase06a,
            "phase-06a initial reserved guard drift")
    positions = []
    for name, _value, read in CUTPOINTS:
        marker = f"c->reserved=LISP65_C2_PHASE_06A_CUT_{name};"
        require(phase06a.count(marker) == 1,
                f"phase-06a marker absent or duplicated: {name}")
        require(phase06a.count(read) == 1,
                f"phase-06a read anchor absent or duplicated: {name}")
        marker_at = phase06a.index(marker)
        read_at = phase06a.index(read)
        require(marker_at < read_at,
                f"phase-06a marker occurs after its read: {name}")
        positions.append((marker_at, read_at))
    require(all(positions[index][1] < positions[index + 1][0]
                for index in range(len(positions) - 1)),
            "phase-06a cutpoint/read order drift")
    require(phase06a.count("c->reserved=") == 6
            and phase06a.endswith(
                "c->reserved=LISP65_C2_PHASE_06A_COMPLETE;"
                "returnC2_STREAM_OK;}")
            and "c->reserved=0u" not in phase06a,
            "phase-06a success or failure preservation drift")
    require("c->reserved!=LISP65_C2_PHASE_06A_COMPLETE" in phase06b
            and all(f"LISP65_C2_PHASE_06A_CUT_{name}" not in phase06b
                    for name, _value, _read in CUTPOINTS),
            "phase-06b accepts an intermediate cutpoint")
    require(all(f"LISP65_C2_PHASE_06A_CUT_{name}" not in text["v2_decoder"]
                for name, _value, _read in CUTPOINTS),
            "hot phase-13 path writes a cold phase-06a cutpoint")

    rejected: dict[str, str] = {}
    if mutations:
        trials: dict[str, dict[str, str]] = {}

        def replace(name: str, owner: str, old: str, new: str) -> None:
            require(old in text[owner], f"mutation anchor absent: {name}")
            trial = dict(text)
            trial[owner] = trial[owner].replace(old, new, 1)
            trials[name] = trial

        for label, _value, _read in CUTPOINTS:
            replace(f"missing-{label.lower().replace('_', '-')}-marker",
                    "decoder",
                    f"c->reserved = LISP65_C2_PHASE_06A_CUT_{label};", "")
        replace("marker-after-its-read", "decoder",
                "c->reserved = LISP65_C2_PHASE_06A_CUT_IMAGE_RECORD;\n"
                "        if (!c2_image_read(c, image, im))\n"
                "            return fail(c, C2_STREAM_ERR_IO);",
                "if (!c2_image_read(c, image, im))\n"
                "            return fail(c, C2_STREAM_ERR_IO);\n"
                "        c->reserved = LISP65_C2_PHASE_06A_CUT_IMAGE_RECORD;")
        replace("duplicate-marker-value", "header",
                "#define LISP65_C2_PHASE_06A_CUT_METADATA_HEADER 0x62u",
                "#define LISP65_C2_PHASE_06A_CUT_METADATA_HEADER 0x61u")
        replace("completion-marker-drift", "header",
                "#define LISP65_C2_PHASE_06A_COMPLETE 0x6au",
                "#define LISP65_C2_PHASE_06A_COMPLETE 0x66u")
        replace("phase06b-accepts-intermediate-marker", "decoder",
                "c->reserved != LISP65_C2_PHASE_06A_COMPLETE",
                "c->reserved != LISP65_C2_PHASE_06A_CUT_LITERAL_BLOCK")
        replace("initial-reserved-guard-removed", "decoder",
                "if (!c || c->phase != 6u || c->error || c->reserved)",
                "if (!c || c->phase != 6u || c->error)")
        replace("failure-clears-marker", "decoder",
                "c->reserved = LISP65_C2_PHASE_06A_CUT_IMAGE_RECORD;\n"
                "        if (!c2_image_read(c, image, im))\n"
                "            return fail(c, C2_STREAM_ERR_IO);",
                "c->reserved = LISP65_C2_PHASE_06A_CUT_IMAGE_RECORD;\n"
                "        if (!c2_image_read(c, image, im))\n"
                "            { c->reserved = 0u; return fail(c, C2_STREAM_ERR_IO); }")
        replace("hot-phase13-writes-cutpoint", "v2_decoder",
                "C2_V2_SLICE(13) uint8_t c2_stream_phase_13(void *opaque) {",
                "C2_V2_SLICE(13) uint8_t c2_stream_phase_13(void *opaque) {\n"
                "    ((c2_stream_context *)opaque)->reserved = "
                "LISP65_C2_PHASE_06A_CUT_IMAGE_RECORD;")
        replace("cutpoint-count-drift", "decoder",
                "c->reserved = LISP65_C2_PHASE_06A_COMPLETE;",
                "c->reserved = LISP65_C2_PHASE_06A_CUT_LITERAL_BLOCK;\n"
                "    c->reserved = LISP65_C2_PHASE_06A_COMPLETE;")

        for name, trial in trials.items():
            try:
                source_gate(trial, mutations=False)
            except (GateError, KeyError, ValueError):
                rejected[name] = "rejected"
            else:
                raise GateError(f"phase-06a mutation accepted: {name}")
        expected = {name.replace("_", "-")
                    for name in contract["required_mutations"]}
        require(set(rejected) == expected,
                "phase-06a mutation inventory drift")

    return {
        "status": "passed-phase06a-five-read-cutpoint-contract",
        "storage": contract["storage"],
        "cutpoints": contract["cutpoints"],
        "fixture": fixture(),
        "negative_mutations": rejected,
        "hot_path_delta_bytes": 0,
        "new_state_bytes": 0,
    }


def linked_gate(elf: Path, llvm_readobj: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=llvm_readobj)
    phase06a = truth.symbol("c2_stream_phase_06a")
    phase06b = truth.symbol("c2_stream_phase_06b")
    require(phase06a.symbol_type == "Function" and phase06a.bytes > 0
            and phase06a.bytes <= 1792
            and phase06a.section == ".lisp65_rt_c2d_06a",
            "linked phase-06a cutpoint carrier drift")
    require(phase06b.symbol_type == "Function" and phase06b.bytes > 0
            and phase06b.bytes <= 1792
            and phase06b.section == ".lisp65_rt_c2d_06b",
            "linked phase-06b handoff consumer drift")
    scratch = truth.symbol("lisp65_c2_phase_scratch")
    require(scratch.symbol_type == "Object" and scratch.bytes == 304,
            "phase-06a cutpoint introduced or resized scratch state")
    return {
        "status": "passed-linked-phase06a-cutpoint-carrier",
        "phase06a": {"section": phase06a.section,
                     "address": phase06a.value, "bytes": phase06a.bytes,
                     "headroom_bytes": 1792 - phase06a.bytes},
        "phase06b": {"section": phase06b.section,
                     "address": phase06b.value, "bytes": phase06b.bytes,
                     "headroom_bytes": 1792 - phase06b.bytes},
        "scratch": {"address": scratch.value, "bytes": scratch.bytes},
        "new_state_objects": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check-source", "check-elf"))
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--llvm-readobj", type=Path,
                        default=ROOT / "tools/llvm-mos/bin/llvm-readobj")
    args = parser.parse_args()
    try:
        if args.command == "check-elf":
            require(args.elf is not None, "--elf is required")
        value = (source_gate(mutations=True) if args.command == "check-source"
                 else linked_gate(args.elf, args.llvm_readobj))
    except (GateError, OSError, ValueError, KeyError, TypeError,
            json.JSONDecodeError) as error:
        print(f"c2-phase06a-cutpoint: FAIL: {error}", file=sys.stderr)
        return 1
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
