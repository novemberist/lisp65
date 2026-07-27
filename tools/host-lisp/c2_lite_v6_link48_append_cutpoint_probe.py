#!/usr/bin/env python3
"""Bind Link 48's two append findings and strengthen the zero-literal seam.

This is a read-only Class-C contract/fixture probe.  It consumes the immutable
Link-48 product and hardware captures, proves the independent rollback-order
defect in the current product source, and prices the smallest honest primary
cutpoint diagnostic.  It does not edit product sources, compile, link, deploy,
or touch hardware.

The exact 119-byte hardware image is also driven through a byte-exact model of
the public Emit -> Append -> Publish -> Install -> Call boundary.  The model's
success witness is paired with source gates for the real serial phase plan and
rollback plan; a model alone is deliberately not accepted as end-to-end proof.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import struct
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
FIRST_RED = EVIDENCE / (
    "c2.2-product-link48-zero-literal-append-hardware-first-red.json")
SESSION = ROOT / (
    "build/c2.2/hardware-presmoke-link48-zero-literal/first-red/"
    "session-emission-119.bin")
LIVE_REGION = ROOT / (
    "build/c2.2/hardware-presmoke-link48-zero-literal/first-red/"
    "bank5-c2d-region-live.bin")
CANDIDATE = ROOT / (
    "build/c2.2/substitution/"
    "product-link-48-c2-lite-v6-zero-literal-execution")
INITIAL_C2D = CANDIDATE / (
    "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
STATIC_CODE = CANDIDATE / (
    "fresh-c2-lite-prelink-gates/v6-semantics/bank2-static-code.bin")

RUNTIME_C = ROOT / "src/c2_product_runtime.c"
RUNTIME_H = ROOT / "src/c2_product_runtime.h"
EVAL_C = ROOT / "src/eval.c"
ERROR_C = ROOT / "src/error_overlay.c"
ERROR_ASM = ROOT / "src/l65e_bcode_ordinal.s"
ZERO_GATE = ROOT / "tools/host-lisp/c2_zero_literal_execution_gate.py"

CUTPOINT_RECEIPT = EVIDENCE / (
    "c2.2-product-link48-append-primary-cutpoint-contract-probe.json")
ROLLBACK_RECEIPT = EVIDENCE / (
    "c2.2-product-link48-append-rollback-order-first-red.json")
E2E_RECEIPT = EVIDENCE / (
    "c2.2-product-link48-zero-literal-end-to-end-fixture-first-red.json")

EXPECTED = {
    FIRST_RED: "f9f17db39694c973968581ac657c1d70fda95c4dd63fc5a81f89b0088864b3a6",
    SESSION: "176de02000b6d29914175c2303216f7530b5a73f0b8bf6cc7f190ab643602531",
    LIVE_REGION: "72aad9da265fb26a472a8eaa19f75e3e8935c0cb6210e519f3697226001545bf",
    INITIAL_C2D: "1b924a1d33a7ce4d56ed4cf02c76db047d75b44adee99d315620d52224a05e7d",
    STATIC_CODE: "5b0fcfca7cb63967e36e603276bbccae8f359086b734fcfb8ad85d1da610a2ac",
}

C2D_BYTES = 33840
C2D_REGION_BYTES = 50816
IMAGES_OFFSET = 48
ENTRIES_OFFSET = 2096
RESOLUTIONS_OFFSET = 22576
ROOTS_OFFSET = 30768
IMAGE_BYTES = 32
ENTRY_BYTES = 10
UNWIND_OFFSET = 50752
STATIC_CODE_BYTES = 34403


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"bound input absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write_receipt(path: Path, value: dict[str, Any]) -> None:
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if path.exists():
        require(path.read_bytes() == encoded, f"sealed receipt drift: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    os.chmod(path, 0o444)


def u16(data: bytes | bytearray, at: int) -> int:
    return struct.unpack_from("<H", data, at)[0]


def u24(data: bytes | bytearray, at: int) -> int:
    return data[at] | data[at + 1] << 8 | data[at + 2] << 16


def u32(data: bytes | bytearray, at: int) -> int:
    return struct.unpack_from("<I", data, at)[0]


def p16(data: bytearray, at: int, value: int) -> None:
    struct.pack_into("<H", data, at, value)


def p32(data: bytearray, at: int, value: int) -> None:
    struct.pack_into("<I", data, at, value)


def function_body(source: str, name: str, *, last: bool = False,
                  marker: str | None = None) -> str:
    needle = marker or (name + "(")
    begin = (source.rfind if last else source.find)(needle)
    require(begin >= 0, f"function absent: {name}")
    brace = source.find("{", begin)
    require(brace >= 0, f"function body absent: {name}")
    depth = 0
    for end in range(brace, len(source)):
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
            if depth == 0:
                return source[begin:end + 1]
    raise ProbeError(f"unterminated function: {name}")


def line_of(source: str, token: str, *, after: int = 0) -> int:
    at = source.find(token, after)
    require(at >= 0, f"source token absent: {token}")
    return source.count("\n", 0, at) + 1


def prerequisites() -> dict[str, Any]:
    for path, digest in EXPECTED.items():
        require(path.is_file() and sha(path) == digest,
                f"Link-48 evidence drift: {path}")
    first_red = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(first_red["status"] == "first-red-product-semantics-review-required"
            and first_red["accounting"]["line_1_status"] == "passed"
            and first_red["accounting"]["line_1_product_first_red_budget"] ==
                "2/3 unchanged"
            and first_red["accounting"]["completed_latency_measurements"] ==
                "0/2 unchanged",
            "Link-48 First Red or accounting drift")
    return {
        "link48_hardware_first_red": bind(FIRST_RED),
        "hardware_session_image": bind(SESSION),
        "hardware_c2d_region": bind(LIVE_REGION),
        "link48_initial_c2d": bind(INITIAL_C2D),
        "link48_static_code": bind(STATIC_CODE),
        "runtime_source": bind(RUNTIME_C),
        "runtime_slot_contract": bind(RUNTIME_H),
        "existing_zero_literal_gate": bind(ZERO_GATE),
        "probe": bind(Path(__file__)),
    }


def effective_slots(header: str) -> dict[str, int]:
    marker = "#ifdef LISP65_C2_LITE_V6_ROOTS_FRONTS_CORESIDENT"
    at = header.rfind(marker)
    require(at >= 0, "final roots/fronts slot block absent")
    tail = header[at:]
    names = {
        "journal_clear": "LISP65_C2_APPEND_JOURNAL_CLEAR_SLOT",
        "journal_write": "LISP65_C2_APPEND_JOURNAL_WRITE_SLOT",
        "journal_validate": "LISP65_C2_APPEND_JOURNAL_VALIDATE_SLOT",
        "journal_reconstruct": "LISP65_C2_APPEND_JOURNAL_RECONSTRUCT_SLOT",
        "rollback_prepare": "LISP65_C2_APPEND_ROLLBACK_PREPARE_SLOT",
        "rollback_unpublish": "LISP65_C2_APPEND_ROLLBACK_UNPUBLISH_SLOT",
        "rollback_finalize": "LISP65_C2_APPEND_ROLLBACK_FINALIZE_SLOT",
        "abort_control": "LISP65_C2_APPEND_ABORT_CONTROL_SLOT",
    }
    result: dict[str, int] = {}
    for label, macro in names.items():
        match = re.search(r"^#define\s+" + re.escape(macro)
                          + r"\s+(\d+)u\s*$", tail, re.MULTILINE)
        require(match is not None, f"effective slot absent: {macro}")
        result[label] = int(match.group(1))
    require(result == {
        "journal_clear": 30, "journal_write": 31,
        "journal_validate": 32, "journal_reconstruct": 33,
        "rollback_prepare": 34, "rollback_unpublish": 43,
        "rollback_finalize": 44, "abort_control": 45,
    }, f"effective Link-48 slot plan drift: {result}")
    return result


def ascending_range(first: int, last: int) -> list[int]:
    result: list[int] = []
    while first <= last:
        result.append(first)
        first += 1
    return result


def rollback_finding(authority: dict[str, Any]) -> dict[str, Any]:
    source = RUNTIME_C.read_text(encoding="utf-8")
    header = RUNTIME_H.read_text(encoding="utf-8")
    slots = effective_slots(header)
    begin_at = source.rfind(
        "static C2_KERNAL_RESIDENT uint8_t c2_append_begin(")
    rollback_at = source.find(
        "static uint8_t c2_append_rollback(", begin_at)
    require(begin_at >= 0 and rollback_at > begin_at,
            "sliced append-begin source interval absent")
    begin = source[begin_at:rollback_at]
    explicit = function_body(source, "c2_append_rollback")
    control = function_body(source, "c2_append_abort_control_phase")
    driver = function_body(source, "c2_abort_driver")
    require("c2_append_run_rollback_plan(&c2aw)" in begin,
            "append failure named rollback-plan call drift")
    require("c2_append_run_rollback_plan(&c2aw)" in explicit,
            "explicit named rollback-plan call drift")
    require("C2AW_ABORT_START(w) = LISP65_C2_APPEND_ROLLBACK_UNPUBLISH_SLOT;"
            in control
            and "C2AW_ABORT_END(w) = LISP65_C2_APPEND_ROLLBACK_FINALIZE_SLOT;"
            in control
            and "C2AW_ABORT_START(w) = LISP65_C2_APPEND_JOURNAL_CLEAR_SLOT;"
            in control
            and "C2AW_ABORT_END(w) = LISP65_C2_APPEND_JOURNAL_CLEAR_SLOT;"
            in control,
            "abort-control rollback plan drift")
    require("C2AW_ABORT_START(&c2aw) > C2AW_ABORT_END(&c2aw)" in driver,
            "abort driver no longer rejects descending plans")

    actual = ascending_range(slots["rollback_unpublish"],
                             slots["journal_clear"])
    require(actual == [], "descending range unexpectedly executed slots")
    expected = [slots["rollback_unpublish"],
                slots["rollback_finalize"], slots["journal_clear"]]

    region = LIVE_REGION.read_bytes()
    journal = region[UNWIND_OFFSET:UNWIND_OFFSET + 64]
    require(len(region) == C2D_REGION_BYTES and journal[:4] == b"C2J\0"
            and journal[4:7] == bytes((1, 1, 0))
            and u32(journal, 60) == (zlib.crc32(journal[:60]) & 0xffffffff),
            "hardware ACTIVE C2J witness drift")
    old_counts = tuple(u16(journal, at) for at in (10, 12, 14, 16))
    new_counts = tuple(u16(journal, at) for at in (18, 20, 22, 24))
    require(old_counts == (6, 588, 2264, 283)
            and new_counts == (7, 589, 2264, 283),
            "hardware journal count witness drift")

    return {
        "format": "lisp65-c2-lite-v6-link48-rollback-order-first-red-v1",
        "recorded_on": "2026-07-22",
        "status": "FIRST RED: rollback phase order is not representable by the ascending range helper",
        "classification": "independent-product-contract-breach",
        "authority": authority,
        "effective_session_slots": slots,
        "source_proof": {
            "range_helper_semantics": "ascending inclusive; first > last executes zero phases and returns success",
            "required_rollback_sequence": expected,
            "actual_requested_range": [slots["rollback_unpublish"],
                                       slots["journal_clear"]],
            "actual_executed_slots": actual,
            "affected_paths": [
                {"function": "c2_append_begin/v5_fail",
                 "line": line_of(source, "v5_fail:\n")},
                {"function": "c2_append_rollback",
                 "line": line_of(source, "static uint8_t c2_append_rollback(")},
                {"function": "c2_append_abort_control_phase",
                 "line": line_of(source, "uint8_t c2_append_abort_control_phase(")},
            ],
            "abort_driver_behavior": "rejects 43 > 30 and sets c2_ready=0",
        },
        "hardware_correlation": {
            "published_header_counts_restored": list(old_counts),
            "unreachable_suffix_counts": list(new_counts),
            "journal_state": "ACTIVE",
            "journal_crc32": f"0x{u32(journal, 60):08x}",
            "explanation": (
                "Header visibility was restored by the fail-closed landing, but "
                "rollback_unpublish, rollback_finalize and journal_clear never "
                "ran in their required order.  The ACTIVE C2J and staged suffix "
                "are the exact hardware signature of that empty/rejected plan."),
        },
        "required_fixture": {
            "positive": "43,44,30 each execute exactly once in that order",
            "negatives": [
                "unpublish omitted", "finalize omitted", "clear omitted",
                "clear before finalize", "descending range delegated to generic helper",
            ],
            "postcondition": (
                "C2D header, suffix, export journal and C2J are byte-identical "
                "to the pre-append snapshot after every injected abort."),
        },
        "claim_limit": (
            "This receipt proves the rollback root cause and its match to the "
            "Link-48 hardware state.  It does not identify the earlier primary "
            "append/decode failure and does not authorize or implement a fix."),
        "next_gate": "Class-C product fix must replace the impossible range with an explicit ordered rollback plan",
        "accounting": {"line1": "passed", "line1_budget": "2/3 unchanged",
                       "latency": "0/2 unchanged", "hardware_runs": 0,
                       "product_links": 0},
    }


def cutpoint_contract(authority: dict[str, Any], slots: dict[str, int]) -> dict[str, Any]:
    runtime = RUNTIME_C.read_text(encoding="utf-8")
    evaluation = EVAL_C.read_text(encoding="utf-8")
    renderer = ERROR_C.read_text(encoding="utf-8")
    assembly = ERROR_ASM.read_text(encoding="utf-8")
    facade = function_body(runtime, "c2_facade_target_overlay_call_family")
    check = function_body(evaluation, "vm_check_status")
    host_entry = function_body(renderer, "lisp65_error_overlay_entry")
    require("== VM_RUNTIME_OVERLAY_OK && status == C2_STREAM_OK" in facade,
            "facade no longer collapses exact phase status to boolean")
    require("code == LISP65_ERR_VM_UNDEFINED_FUNCTION && IS_BCODE(detail)" in check
            and "lisp_abort_code(code);" in check,
            "existing status/detail seam changed")
    require("context->code == LISP65_ERR_VM_UNDEFINED_FUNCTION" in host_entry
            and "cpx\t#41" in assembly and "cpx\t#43" not in assembly,
            "closed L65E BCODE-detail union changed")

    max_slot = max(slots.values())
    max_entry_status = 10
    encoded_max = (max_slot << 6) | max_entry_status
    require(encoded_max < 4096, "slot/status cutpoint does not fit BCODE ordinal")
    return {
        "format": "lisp65-c2-lite-v6-link48-primary-cutpoint-contract-probe-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-contract-probe-existing-seam-insufficient-product-extension-required",
        "promotable": False,
        "authority": authority,
        "existing_seam_result": {
            "facade": "keeps transport and entry status locally, then collapses both to one boolean",
            "vm_check_status": "forwards detail only for VM_DIRMISS",
            "l65e_renderer": "accepts BCODE only for error code 41 (undefined function)",
            "vm_badopcode": "error code 43 is rendered without detail",
            "conclusion": "the exact failing phase/status cannot reach the screen today",
        },
        "minimal_contract": {
            "capture_location": "c2_facade_target_overlay_call_family before boolean collapse",
            "capture_scope": ["context == &c2aw", "context == &c2aw.append"],
            "storage": "two bytes inside the existing 304-byte exclusive append scratch; no resident cell/root",
            "first_failure_wins": True,
            "fields": {"slot": "0..63", "status": "entry 1..10 or 0x20|transport"},
            "screen_encoding": "BCODE ordinal = (slot << 6) | status",
            "maximum_encoded_ordinal": encoded_max,
            "renderer_extension": "error code 43 may carry BCODE; SYMI/NIL behavior and code 41 remain unchanged",
            "example": {"phase_04_slot": 2,
                        "entry_status_3": "#083"},
        },
        "required_mutations": [
            "wrong slot", "wrong entry status", "transport status misclassified",
            "second failure overwrites first", "non-append overlay captured",
            "BADOPCODE BCODE rejected by renderer", "BADOPCODE SYMI accepted",
        ],
        "capacity_rule": (
            "WPLTO must show every wall nonnegative and the restored $E000 "
            "floor >=115 before a diagnostic product link can be reviewed."),
        "claim_limit": (
            "Contract and source-gap proof only. No product bytes, WPLTO, "
            "product link or hardware run were produced."),
        "accounting": {"line1": "passed", "line1_budget": "2/3 unchanged",
                       "latency": "0/2 unchanged", "hardware_runs": 0,
                       "product_links": 0},
    }


def model_exact_session() -> dict[str, Any]:
    image = SESSION.read_bytes()
    initial = INITIAL_C2D.read_bytes()
    static = STATIC_CODE.read_bytes()
    require(len(image) == 119 and len(initial) == C2D_BYTES
            and len(static) == STATIC_CODE_BYTES,
            "exact fixture input geometry drift")
    require(image[:8] == b"L65S\x04\x20\x20\x01"
            and u16(image, 8) == 32 and u24(image, 10) == 64
            and u24(image, 13) == len(image)
            and (zlib.crc32(image[32:64]) & 0xffffffff) == u32(image, 18),
            "exact L65S-v4 envelope/catalog invalid")
    code_off, code_len = u24(image, 40), u16(image, 43)
    meta_off, meta_len = u24(image, 45), u16(image, 48)
    code, metadata = image[code_off:code_off + code_len], image[meta_off:]
    require((code_off, code_len, meta_off, meta_len) == (64, 9, 73, 46)
            and code == bytes.fromhex("b5 00 00 02 02 00 00 2c 05")
            and metadata[:8] == b"C2I\0\x02\x18\x10\x08"
            and u16(metadata, 10) == 1 and u16(metadata, 12) == 0
            and metadata[-6:] == b"\x04\x00%c2h",
            "exact zero-literal image payload drift")
    require((zlib.crc32(code) & 0xffffffff) == u32(image, 50)
            and (zlib.crc32(metadata) & 0xffffffff) == u32(image, 54)
            and (zlib.crc32(code + metadata) & 0xffffffff) == u32(image, 58),
            "exact image CRC drift")
    require(initial[:5] == b"C2D\0\x06"
            and tuple(u16(initial, at) for at in (12, 16, 20, 24)) ==
                (6, 588, 2264, 283),
            "Link-48 initial C2D census drift")

    bank2 = bytearray(65536)
    bank2[:len(static)] = static
    bank2[STATIC_CODE_BYTES:STATIC_CODE_BYTES + code_len] = code
    c2d = bytearray(initial)
    combined = zlib.crc32(code + metadata) & 0xffffffff
    image_row = bytearray(32)
    image_row[0] = 1
    p16(image_row, 4, 1)
    p16(image_row, 6, 588)
    p16(image_row, 8, 1)
    p16(image_row, 10, 2264)
    p16(image_row, 12, 0)
    p16(image_row, 14, 283)
    p16(image_row, 16, 0)
    image_row[18:21] = bytes((STATIC_CODE_BYTES & 0xff,
                              STATIC_CODE_BYTES >> 8, 0))
    p16(image_row, 21, code_len)
    p32(image_row, 28, combined)
    c2d[IMAGES_OFFSET + 6 * IMAGE_BYTES:
        IMAGES_OFFSET + 7 * IMAGE_BYTES] = image_row
    entry_row = bytearray(10)
    entry_row[0] = 6
    entry_row[1] = 0
    p16(entry_row, 2, STATIC_CODE_BYTES)
    p16(entry_row, 4, code_len)
    p16(entry_row, 6, 2264)
    p16(entry_row, 8, 1)
    c2d[ENTRIES_OFFSET + 588 * ENTRY_BYTES:
        ENTRIES_OFFSET + 589 * ENTRY_BYTES] = entry_row
    for at, value in zip((12, 16, 20, 24), (7, 589, 2264, 283)):
        p16(c2d, at, value)

    # Install resolves the one exported name to persistent handle 588.  The
    # actual code object then executes PUSHT, RET with no literal-table read.
    exported_handle = 588
    row = c2d[ENTRIES_OFFSET + exported_handle * ENTRY_BYTES:
              ENTRIES_OFFSET + (exported_handle + 1) * ENTRY_BYTES]
    require(row == entry_row and row[1] == 0 and u16(row, 4) == 9,
            "modeled installed zero-literal row invalid")
    object_bytes = bytes(bank2[u16(row, 2):u16(row, 2) + u16(row, 4)])
    require(object_bytes == code and object_bytes[6] == 0
            and object_bytes[7:] == bytes((0x2c, 0x05)),
            "modeled installed call is not PUSHT/RET")
    return {
        "status": "passed-byte-exact-success-oracle",
        "input": {"length": len(image), "entries": 1, "literals": 0,
                  "code_hex": code.hex(), "export": "%c2h"},
        "append": {"old_counts": [6, 588, 2264, 283],
                   "new_counts": [7, 589, 2264, 283],
                   "image_slot": 6, "entry_ordinal": exported_handle,
                   "entry_row_hex": bytes(entry_row).hex(),
                   "image_row_hex": bytes(image_row).hex()},
        "publish_install": {"symbol": "%c2h", "handle": exported_handle},
        "call": {"literal_reads": 0, "opcodes": ["PUSHT", "RET"],
                 "result": "T"},
    }


def e2e_finding(authority: dict[str, Any], rollback: dict[str, Any]) -> dict[str, Any]:
    oracle = model_exact_session()
    old_gate = ZERO_GATE.read_text(encoding="utf-8")
    require("def execution_length(" in old_gate
            and "def linked_gate(" in old_gate
            and "c2_append_begin" not in old_gate
            and "c2_product_install" not in old_gate,
            "old fixture gap classification drift")
    return {
        "format": "lisp65-c2-lite-v6-link48-zero-literal-end-to-end-fixture-first-red-v1",
        "recorded_on": "2026-07-22",
        "status": "FIRST RED: exact success oracle passes but real product rollback plan is structurally invalid",
        "authority": authority,
        "old_fixture_gap": {
            "covered": ["entry reader", "entry length", "vm_run_dir ELF edge"],
            "missing": ["dynamic emission", "append phases", "publication",
                        "installation", "actual call", "abort restoration"],
        },
        "exact_hardware_image_success_oracle": oracle,
        "required_product_end_to_end_fixture": {
            "positive_chain": [
                "emit exact 119-byte zero-literal image",
                "append through every real Session-family phase",
                "publish %c2h last",
                "install persistent handle 588",
                "call exact PUSHT/RET code and observe T",
            ],
            "cutpoints": (
                "inject before and after every actual overlay call; after each "
                "abort compare C2D header, suffix, export cells, Bank-2 suffix "
                "and C2J with the pre-append snapshot"),
            "source_gate": (
                "the real phase driver may not delegate a semantic rollback "
                "sequence to a numerically ascending slot range"),
            "current_blocker": rollback["source_proof"],
        },
        "why_red_is_required": (
            "The byte oracle proves that zero literals and the emitted code are "
            "valid.  It is not permitted to turn that oracle green while the "
            "real product can skip all three rollback phases; that would repeat "
            "the model/product split exposed by hardware."),
        "claim_limit": (
            "The exact success oracle is not a product execution result.  The "
            "fixture remains red until it drives the real phase plan and proves "
            "byte-identical restoration at every cutpoint."),
        "accounting": {"line1": "passed", "line1_budget": "2/3 unchanged",
                       "latency": "0/2 unchanged", "hardware_runs": 0,
                       "product_links": 0},
    }


def main() -> int:
    authority = prerequisites()
    rollback = rollback_finding(authority)
    slots = rollback["effective_session_slots"]
    cutpoint = cutpoint_contract(authority, slots)
    e2e = e2e_finding(authority, rollback)
    write_receipt(ROLLBACK_RECEIPT, rollback)
    write_receipt(CUTPOINT_RECEIPT, cutpoint)
    write_receipt(E2E_RECEIPT, e2e)
    print("c2-lite-v6-link48-append-cutpoint-probe: FIRST RED "
          "rollback=43,44,30 actual=empty cutpoint-seam=extension-required "
          "exact-e2e-oracle=pass product-fixture=red")
    print("c2-lite-v6-link48-append-cutpoint-probe: "
          f"rollback_receipt_sha256={sha(ROLLBACK_RECEIPT)}")
    print("c2-lite-v6-link48-append-cutpoint-probe: "
          f"cutpoint_receipt_sha256={sha(CUTPOINT_RECEIPT)}")
    print("c2-lite-v6-link48-append-cutpoint-probe: "
          f"e2e_receipt_sha256={sha(E2E_RECEIPT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
