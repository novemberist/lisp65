#!/usr/bin/env python3
"""Bind Link 49's read-only hardware First Red after the facade-16 cut.

The binder consumes the immutable product, screen captures, and memory dumps
taken after the sole dynamic definition failed.  It does not compile, link,
patch, deploy, reset, or write device memory.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import zlib


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CANDIDATE = ROOT / (
    "build/c2.2/substitution/"
    "product-link-49-c2-lite-v6-append-final-hybrid-facade16")
PRESMOKE = ROOT / "build/c2.2/hardware-presmoke-link49-facade16"
CAPTURE = PRESMOKE / "first-red"
PRODUCT = CANDIDATE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
MAP = Path(str(PRODUCT) + ".map")
STRUCTURAL = EVIDENCE / (
    "c2.2-product-link49-c2-lite-v6-append-final-hybrid-facade16-"
    "artifact-replay2-structural-receipt.json")
DEPLOYMENT = PRESMOKE / "deployment.json"
LINE1 = PRESMOKE / "line1/screen.png"
TRANSCRIPT = PRESMOKE / "definition/definition_setup.txt"
ERROR_SCREEN = PRESMOKE / "definition/definition_setup.png"
LOW = CAPTURE / "low64k.bin"
BANK2 = CAPTURE / "bank2-static-code.bin"
C2D_REGION = CAPTURE / "bank5-c2d-region-live.bin"
BANK2_AUTHORITY = CANDIDATE / (
    "fresh-c2-lite-prelink-gates/v6-semantics/bank2-static-code.bin")
RUNTIME = ROOT / "src/c2_product_runtime.c"
RECEIPT = EVIDENCE / (
    "c2.2-product-link49-facade16-missing-persistent-header-"
    "hardware-first-red.json")

EXPECTED = {
    PRODUCT: "115c8996bb5c4cf0059c5cd088b0190d486d83734a332251f55cc9ccc9da2e34",
    ELF: "73d23101529d9ba54d0e26d0b12f89615f0a13839de1e8ceaec2fc70a54ded53",
    MAP: "6ca693f2f2fa314977c3e1f8efde4f0d8827d87c0a4631b9ea7ff3c4c76806bb",
    STRUCTURAL: "4d0426393755013c93222fb2f7515e108f57a20dac43c7e85867a0c64f8e2673",
    DEPLOYMENT: "8607a8956a4644b75c4b54220121fd27c619d251b78cdd8c486007a055baaf2c",
    LINE1: "7bc0ff2468c8dcbd089f000422dc62f4f607f2e7394ae04790f06ef4d3725e6c",
    TRANSCRIPT: "1fd6f363ea2096be9e0634675c87205f131cbce56ee71deb4fda8fae9e1c5b70",
    ERROR_SCREEN: "4d8fc02fed2ca4c6ae1b92993a3701f13a199885dfa70111f2bcf019349d2a3c",
    LOW: "505f56e262b018f8b88d9043fc976466b32f3ccaf9b1a0560dfb395be44edfff",
    BANK2: "5b0fcfca7cb63967e36e603276bbccae8f359086b734fcfb8ad85d1da610a2ac",
    C2D_REGION: "5329bab293e51de6c0d6588efcecb5489378259e2e5be5d6cd4e5348b9b4e5a3",
    BANK2_AUTHORITY: "5b0fcfca7cb63967e36e603276bbccae8f359086b734fcfb8ad85d1da610a2ac",
}


class FirstRedError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FirstRedError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, object]:
    require(path.is_file(), f"evidence absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 2], "little")


def u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 4], "little")


def body(source: str, signature: str, start: int = 0) -> str:
    begin = source.find(signature, start)
    require(begin >= 0, f"source function absent: {signature}")
    brace = source.find("{", begin)
    require(brace >= 0, f"source body absent: {signature}")
    depth = 0
    for end in range(brace, len(source)):
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
            if depth == 0:
                return source[begin:end + 1]
    raise FirstRedError(f"unterminated source function: {signature}")


def main() -> None:
    require(not RECEIPT.exists(), "Link-49 hardware First-Red receipt exists")
    for path, expected in EXPECTED.items():
        require(sha(path) == expected, f"bound evidence drift: {path}")

    structural = json.loads(STRUCTURAL.read_text(encoding="utf-8"))
    deployment = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    require(structural.get("status") ==
            "passed-new-c2-lite-facade16-identity-hardware-not-run",
            "Link-49 structural prerequisite is not green")
    require(deployment.get("status") == "ready-receipt-less",
            "Link-49 deployment is not the verified receipt-less stage")
    require(deployment["product"]["sha256"] == EXPECTED[PRODUCT],
            "deployment product identity drift")
    transcript = TRANSCRIPT.read_text(encoding="utf-8")
    require("WORKBENCH - DIALECT V2" in transcript
            and "(defun %c2h()(quote t))" in transcript
            and "*** vm: bad bytecode" in transcript,
            "captured hardware deviation drift")

    low = LOW.read_bytes()
    bank2 = BANK2.read_bytes()
    region = C2D_REGION.read_bytes()
    require(len(low) == 65536 and len(bank2) == 34403
            and len(region) == 50816, "capture geometry drift")
    require(bank2 == BANK2_AUTHORITY.read_bytes(),
            "hardware Bank-2 code differs from Link-49 authority")
    c2d, journal = region[:50752], region[50752:]

    runtime = low[0xc084:0xc0b2]
    runtime_state = {
        "shelf_bytes": u32(runtime, 0),
        "catalog_crc32": f"0x{u32(runtime, 4):08x}",
        "c2d_bytes": u16(runtime, 8),
        "generation": u16(runtime, 10),
        "image_count": u16(runtime, 12),
        "entry_count": u16(runtime, 14),
        "resolution_count": u16(runtime, 16),
        "root_count": u16(runtime, 26),
        "phase": runtime[42],
        "finished": runtime[43],
        "error": runtime[44],
    }
    expected_runtime = {
        "shelf_bytes": 70897,
        "catalog_crc32": "0x3d6302f3",
        "c2d_bytes": 33840,
        "generation": 1,
        "image_count": 6,
        "entry_count": 588,
        "resolution_count": 2264,
        "root_count": 283,
        "phase": 13,
        "finished": 1,
        "error": 0,
    }
    require(runtime_state == expected_runtime,
            f"restored runtime drift: {runtime_state}")

    scratch = low[0xc0c6:0xc0c6 + 304]
    append = scratch[4:50]
    append_context = {
        "image_count": u16(append, 12),
        "entry_count": u16(append, 14),
        "resolution_count": u16(append, 16),
        "root_count": u16(append, 26),
        "image_first": u16(append, 34),
        "entry_first": u16(append, 36),
        "resolution_first": u16(append, 38),
        "root_first": u16(append, 40),
        "phase": append[42],
        "finished": append[43],
        "error": append[44],
    }
    require(append_context == {
        "image_count": 7, "entry_count": 589,
        "resolution_count": 2264, "root_count": 283,
        "image_first": 6, "entry_first": 588,
        "resolution_first": 2264, "root_first": 283,
        "phase": 13, "finished": 1, "error": 0,
    }, f"append decoder context drift: {append_context}")
    append_state = {
        "length": u16(scratch, 50),
        "entries": u16(scratch, 60),
        "literals": u16(scratch, 62),
        "roots": u16(scratch, 64),
        "old_counts": [u16(scratch, at) for at in (66, 68, 70, 72)],
        "new_counts": [u16(scratch, at) for at in (74, 76, 78, 80)],
        "staged": scratch[238],
        "committed": scratch[239],
        "flags": scratch[240],
    }
    require(append_state == {
        "length": 119, "entries": 1, "literals": 0, "roots": 0,
        "old_counts": [6, 588, 2264, 283],
        "new_counts": [7, 589, 2264, 283],
        "staged": 1, "committed": 0, "flags": 0,
    }, f"append transaction state drift: {append_state}")

    require(low[0x008c] == 1 and low[0x005d] == 0
            and u16(low, 0x002e) == 0,
            "public fail-closed boundary was not restored")
    require(journal == bytes(64), "C2J was not completely cleared")
    require(c2d[48 + 6 * 32:48 + 7 * 32] == bytes(32)
            and c2d[2096 + 588 * 10:2096 + 589 * 10] == bytes(10),
            "unreachable appended suffix was not wiped")
    require(c2d[:4] == b"C2D\0" and c2d[4] == 6
            and u16(c2d, 12) == 6 and u16(c2d, 16) == 588
            and u16(c2d, 20) == 2264 and u16(c2d, 24) == 283,
            "published C2D counts were not restored")

    source = RUNTIME.read_text(encoding="utf-8")
    sliced = source.rfind(
        "static C2_KERNAL_RESIDENT uint8_t c2_append_begin(")
    require(sliced >= 0, "sliced append entry absent")
    rollback = source.find("static uint8_t c2_append_rollback(", sliced)
    require(rollback > sliced, "sliced append terminator absent")
    begin = source[sliced:rollback]
    header = body(source, "uint8_t c2_append_header_phase(")
    publish = body(source, "uint8_t c2_append_publish_exports_phase(")
    require("!c2_decode_from(&c2aw.append, 4u)" in begin
            and "LISP65_C2_APPEND_PUBLISH_PLAN_SCAN_SLOT" in begin
            and "LISP65_C2_APPEND_PUBLISH_PLAN_RESOLVE_SLOT" in begin
            and "LISP65_C2_APPEND_PUBLISH_EXPORTS_SLOT" in begin,
            "persistent post-decode path drift")
    persistent_arm = (
        ": (!c2_overlay_call_range(\n"
        "                    LISP65_C2_APPEND_PUBLISH_PLAN_SCAN_SLOT,\n"
        "                    LISP65_C2_APPEND_PUBLISH_PLAN_RESOLVE_SLOT, &c2aw)\n"
        "                || (C2AW_PUBLISH_CLEAR_MARK(&c2aw) =\n"
        "                        C2_PUBLISH_REQUEST_MARK,\n"
        "                    !c2_overlay_call(\n"
        "                        LISP65_C2_APPEND_PUBLISH_EXPORTS_SLOT, &c2aw)))"
    )
    require(persistent_arm in begin,
            "persistent scan/resolve/publish arm drift")
    require("w->committed = 1" in header,
            "header phase no longer owns commit publication")
    require("!w->committed" in publish,
            "export publication no longer rejects an uncommitted append")
    linked_plan = list(low[0xb708:0xb70e])
    require(linked_plan == [30, 34, 35, 36, 37, 0]
            and 40 not in linked_plan,
            f"linked forward plan drift: {linked_plan}")

    receipt = {
        "format": "lisp65-c2-lite-v6-link49-missing-persistent-header-hardware-first-red-v1",
        "recorded_on": "2026-07-22",
        "status": "first-red-product-semantics-review-required",
        "classification": (
            "Class C: persistent append omits the header/commit phase before "
            "export publication; rollback is complete"),
        "candidate": {
            "link": 49, "product": bind(PRODUCT), "elf": bind(ELF),
            "map": bind(MAP), "structural_receipt": bind(STRUCTURAL),
            "deployment": bind(DEPLOYMENT),
        },
        "hardware_result": {
            "line_1": {"status": "passed", "screen": bind(LINE1)},
            "definition": {
                "form": "(defun %c2h()(quote t))",
                "status": "first-red-before-completed-latency-measurement",
                "observed": "*** vm: bad bytecode",
                "transcript": bind(TRANSCRIPT), "screen": bind(ERROR_SCREEN),
            },
        },
        "read_only_localization": {
            "captures": {
                "low64k": bind(LOW), "bank2": bind(BANK2),
                "c2d_plus_journal": bind(C2D_REGION),
                "bank2_authority": bind(BANK2_AUTHORITY),
            },
            "decoder": {
                "status": "passed-through-phase-13",
                "append_context": append_context,
            },
            "append": append_state,
            "linked_forward_plan": linked_plan,
            "source_dataflow_proof": {
                "persistent_sequence": [
                    "decoder phases 4..13", "publish-plan scan",
                    "publish-plan resolve", "publish exports"],
                "missing_phase": {
                    "slot": 40, "symbol": "c2_append_header_phase"},
                "header_is_only_commit_writer": True,
                "publish_exports_requires_committed": True,
                "deterministic_failure": (
                    "publish exports observes committed=0 and returns "
                    "C2_STREAM_ERR_STATE"),
            },
            "rollback": {
                "status": "passed-complete-on-hardware",
                "ready": low[0x008c], "resident_journal_count": u16(low, 0x002e),
                "c2j_zero_bytes": len(journal), "suffix_image_zero": True,
                "suffix_entry_zero": True, "restored_runtime": runtime_state,
            },
        },
        "finding": (
            "The new facade vector and plan-walker ABI are not the hardware "
            "failure. The walker completed the named stage plan, and the real "
            "decoder completed phase 13. The persistent post-decode sequence "
            "then skips slot 40, while the next phase requires the commit bit "
            "that only slot 40 sets. The exact hardware signature is staged=1, "
            "committed=0, followed by a fully successful rollback."),
        "claim_boundary": {
            "proved": [
                "Link 49 passes hardware line 1 with banner and REPL",
                "Bank 2 remains byte-identical to the Link-49 authority",
                "the dynamic zero-literal append decoder completes phase 13",
                "the persistent forward path deterministically omits header slot 40",
                "the corrected rollback plan clears C2J and wipes the suffix",
            ],
            "not_proved": [
                "a product fix for the missing header phase",
                "a completed definition", "any cold or warm latency value",
                "promotion or acceptance"],
        },
        "accounting": {
            "line_1_status": "passed",
            "line_1_product_first_red_budget": "2/3 unchanged",
            "completed_latency_measurements": "0/2 unchanged",
            "additional_hardware_inputs_after_first_deviation": 0,
            "compiler_runs_during_read_only_diagnosis": 0,
            "linker_runs_during_read_only_diagnosis": 0,
            "product_bytes_changed_during_read_only_diagnosis": 0,
        },
        "next_action": (
            "Class-C review. No source fix, product link, replay, further "
            "hardware input, promotion, or acceptance is authorized here."),
        "value_string": (
            "link49=115c8996bb5c4cf0059c5cd088b0190d486d83734a332251f55cc9ccc9da2e34 "
            "line1=pass definition=FIRST-RED-VM_BADOPCODE decoder=phase13/finished1/error0 "
            "append=staged1/committed0 missing-header-slot=40 publish=state-reject "
            "rollback=complete ready=1 c2j=zero suffix=zero line1-budget=2/3 "
            "latency=0/2 acceptance=blocked"),
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    for path in CAPTURE.iterdir():
        if path.is_file():
            os.chmod(path, 0o444)
    print(f"PASS: {RECEIPT.relative_to(ROOT)}")
    print(f"receipt_sha256={sha(RECEIPT)}")
    print(receipt["value_string"])


if __name__ == "__main__":
    main()
