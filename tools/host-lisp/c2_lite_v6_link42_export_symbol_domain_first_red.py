#!/usr/bin/env python3
"""Bind Link 42's C2-lite export-symbol-domain hardware First Red.

This is a read-only diagnosis.  It consumes the SHA-bound Link-42 product and
the captures taken at the fail-closed hardware stop; it does not compile,
link, patch, deploy, reset or otherwise alter product or device state.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / (
    "build/c2.2/substitution/"
    "product-link-42-c2-lite-v6-final-island-identity-replay")
PRESMOKE = ROOT / "build/c2.2/hardware-presmoke-link42-final-island"
CAPTURE = PRESMOKE / "first-red-profiled-preload"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
STRUCTURAL = EVIDENCE / (
    "c2.2-product-link42-c2-lite-v6-final-island-identity-replay-"
    "structural-receipt.json")
RECEIPT = EVIDENCE / (
    "c2.2-product-link42-c2-lite-v6-export-symbol-domain-"
    "hardware-first-red.json")

PRODUCT = CANDIDATE / "lisp65-c2-substitution-linked.prg"
ELF = Path(str(PRODUCT) + ".elf")
DEPLOYMENT = PRESMOKE / "deployment.json"
SESSION = CANDIDATE / "runtime-overlays-session-final.bin"
INITIAL_C2D = (CANDIDATE / "fresh-c2-lite-prelink-gates/v6-semantics/"
               "initial.c2d-v6.bin")
RUNTIME_SOURCE = CANDIDATE / "generated-product-sources/c2_product_runtime.c"
LOW = CAPTURE / "low-0000-ffff.bin"
BANK2 = CAPTURE / "bank2.bin"
BANK3 = CAPTURE / "bank3.bin"
LIVE_C2D = CAPTURE / "c2d-v6.bin"
EXPORT_PLAN = CAPTURE / "export-plan-journal.bin"

EXPECTED_SHA256 = {
    PRODUCT: "0fa2ae3310d631ae5cebfb8634602d72c68928b8cbb575d98f604feba3a2ecb0",
    ELF: "19deda1e45d686019d501843fbb060183bb8da28a1edecd454308149f297c9c3",
    STRUCTURAL: "e9ba8bc2eecc96dfe190d74abcf95371bcdd05b96184d38405019f39b040698c",
    DEPLOYMENT: "75a134b3edf2894db2cb2b3211140c15a6104687ea2170c8b3453fba37111f97",
    SESSION: "c7ba318c2b26d7fc75d0ff9671ef2d55a119e41441d872f3fc1c9d8e5e1ff67c",
    INITIAL_C2D: "1b924a1d33a7ce4d56ed4cf02c76db047d75b44adee99d315620d52224a05e7d",
    LOW: "ffc7b53b5f55360e17ed05a6830b118b4b735f0d3ef9677ab459d67faaabf04d",
    BANK2: "f2ed21fa97873a163195dfbd87da4717c2cc5fcdd38527b749e9c29bd8b8b339",
    BANK3: "722080b634b425e73703b6c523148b17464c92f7ec83ca9328c6a423b68bd6da",
    LIVE_C2D: "ff4e9643e3886d6dc3ae4a7dc26ec3daae105f0f338889708430de28306c2f25",
    EXPORT_PLAN: "06cb0990bc1eeacabef2d95432d64d93cc0f431a4179527a2b66c071cee9769d",
}


class DiagnosisError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DiagnosisError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, object]:
    require(path.is_file(), f"evidence absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def u16(data: bytes, offset: int = 0) -> int:
    return int.from_bytes(data[offset:offset + 2], "little")


def u32(data: bytes, offset: int = 0) -> int:
    return int.from_bytes(data[offset:offset + 4], "little")


def is_symi(value: int) -> bool:
    return value >= 0xe000 and (value & 1) == 0


def is_ptr(value: int) -> bool:
    signed = value if value < 0x8000 else value - 0x10000
    return signed > 0 and (value & 1) == 0


def main() -> None:
    require(not RECEIPT.exists(), "Link-42 export-domain receipt already exists")
    for path, expected in EXPECTED_SHA256.items():
        require(sha(path) == expected, f"bound evidence drift: {path}")

    deployment = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    structural = json.loads(STRUCTURAL.read_text(encoding="utf-8"))
    require(deployment["product"]["sha256"] == EXPECTED_SHA256[PRODUCT]
            and deployment["status"] == "ready-receipt-less",
            "deployment does not bind the accepted Link-42 product")
    require(structural["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run",
            "Link-42 structural prerequisite is not accepted")

    low = LOW.read_bytes()
    bank3 = BANK3.read_bytes()
    session = SESSION.read_bytes()
    live_c2d = LIVE_C2D.read_bytes()
    initial_c2d = INITIAL_C2D.read_bytes()
    plan = EXPORT_PLAN.read_bytes()
    require(len(low) == 65536 and len(bank3) == 65536
            and len(live_c2d) == len(initial_c2d) == 33840
            and len(plan) == 353 * 8,
            "hardware capture geometry drift")
    require(bank3[:len(session)] == session,
            "live Session Bank-3 family differs from Link-42 authority")

    # Link-42 fixed-state geometry is bound by its ELF/map gates.  The runtime
    # state proves that island install and all thirteen decode phases finished;
    # only the final source-free export publication remained before READY.
    context = low[0xc084:0xc084 + 46]
    runtime = {
        "shelf_bytes": u32(context, 0),
        "catalog_crc32": f"0x{u32(context, 4):08x}",
        "c2d_bytes": u16(context, 8),
        "generation": u16(context, 10),
        "image_count": u16(context, 12),
        "entry_count": u16(context, 14),
        "resolution_count": u16(context, 16),
        "root_count": u16(context, 26),
        "resolution_cursor": u16(context, 30),
        "root_cursor": u16(context, 32),
        "phase": context[42],
        "finished": context[43],
        "error": context[44],
    }
    require(runtime == {
        "shelf_bytes": 70897,
        "catalog_crc32": "0x3d6302f3",
        "c2d_bytes": 33840,
        "generation": 1,
        "image_count": 6,
        "entry_count": 588,
        "resolution_count": 2264,
        "root_count": 283,
        "resolution_cursor": 2264,
        "root_cursor": 283,
        "phase": 13,
        "finished": 1,
        "error": 0,
    }, f"unexpected live decoder state: {runtime}")

    fixed_state = {
        "pending_error": low[0x0038],
        "rtov_busy": low[0x0077],
        "rtov_fault": low[0x0078],
        "rtov_family": low[0x0079],
        "rtov_island_state": low[0x007a],
        "pending_roots": u16(low, 0x008a),
        "ready": low[0x008c],
        "mem_oom": low[0x008f],
        "family_generation": u16(low, 0xc028),
        "committed_roots": u16(low, 0xc080),
        "journal_count_after_rollback": u16(low, 0x002e),
    }
    require(fixed_state == {
        "pending_error": 37,
        "rtov_busy": 0,
        "rtov_fault": 0,
        "rtov_family": 2,
        "rtov_island_state": 2,
        "pending_roots": 283,
        "ready": 0,
        "mem_oom": 0,
        "family_generation": 1,
        "committed_roots": 283,
        "journal_count_after_rollback": 0,
    }, f"unexpected fail-closed fixed state: {fixed_state}")

    # c2_append_state begins at the phase scratch base.  The live bytes retain
    # the completed plan count even after the owner was released and rollback
    # returned the journal count to zero.
    scratch = low[0xc0c6:0xc0c6 + 304]
    plan_count = u16(scratch, 236)  # meta[22]
    committed = scratch[239]
    plan_mark = scratch[204]        # record[22]
    require((plan_count, committed, plan_mark) == (353, 1, 0),
            "cold-plan cutpoint state does not identify final publication")

    rows: list[dict[str, object]] = []
    for ordinal in range(plan_count):
        row = plan[ordinal * 8:(ordinal + 1) * 8]
        symbol = u16(row)
        tagged = u16(row, 4)
        require(is_symi(symbol),
                f"row {ordinal} does not carry canonical SYMI: 0x{symbol:04x}")
        require(not is_ptr(symbol),
                f"row {ordinal} unexpectedly satisfies heap IS_PTR")
        require((tagged & 0x7000) == 0
                and (tagged & 0x0fff) < 2048
                and row[6:] == b"\0\0",
                f"row {ordinal} has invalid target/reserved fields")
        rows.append({
            "row": ordinal,
            "symbol": f"0x{symbol:04x}",
            "target": tagged & 0x0fff,
            "macro": bool(tagged & 0x8000),
        })

    runtime_source = RUNTIME_SOURCE.read_text(encoding="utf-8")
    require("!IS_PTR((obj)c2_u16(row))" in runtime_source,
            "failing heap-pointer predicate absent from bound product source")
    require("c2_stream_name_value(8u, at + 2u, length, &symbol)" in runtime_source
            and "*value = (uint16_t)c2_facade_intern(sym_name_scratch);"
                in runtime_source,
            "canonical interned-symbol producer absent from bound product source")

    changed = [i for i, (before, after) in
               enumerate(zip(initial_c2d, live_c2d)) if before != after]
    require(changed and changed[0] == 9,
            "live C2D does not carry the expected completed decode mutation")

    receipt = {
        "format": "lisp65-c2-lite-v6-export-symbol-domain-hardware-first-red-v1",
        "recorded_on": "2026-07-22",
        "status": "first-red-product-semantic-review-required",
        "classification": "Class C: product publication predicate contradicts the canonical symbol representation",
        "observed": "red frame; stdlib: invalid profiled preload",
        "finding": (
            "The complete cold export plan contains 353 canonical interned SYMI "
            "objects. The active publish_exports validation requires IS_PTR for "
            "the same field, so every valid row is rejected; row 0 is the first "
            "failure. Decode, transport, generation and plan production completed."),
        "root_cause": {
            "producer": "c2_stream_name_value(kind=8) -> c2_facade_intern -> MK_SYMI",
            "consumer": "c2_append_publish_exports_phase first-pass validation",
            "wrong_predicate": "IS_PTR((obj)c2_u16(row))",
            "contract_field": "cold_export_plan.record.interned symbol u16",
            "live_rows": plan_count,
            "rows_satisfying_symi": sum(is_symi(u16(plan, i * 8))
                                         for i in range(plan_count)),
            "rows_satisfying_is_ptr": sum(is_ptr(u16(plan, i * 8))
                                           for i in range(plan_count)),
            "first_row": rows[0],
        },
        "hardware_state": {
            "runtime": runtime,
            "fixed_state": fixed_state,
            "phase_scratch": {
                "export_plan_count": plan_count,
                "committed": committed,
                "plan_marker_after_resolve": plan_mark,
            },
            "session_bank3": {
                "active_bytes": len(session),
                "byteidentical_to_link42": True,
                "sha256": hashlib.sha256(bank3[:len(session)]).hexdigest(),
            },
            "c2d_changed_bytes_from_initial": len(changed),
        },
        "fail_closed": {
            "ready_zero": True,
            "runtime_transport_fault_zero": True,
            "mem_oom_zero": True,
            "journal_rolled_back": True,
            "latency_attempts_consumed": "0/2",
        },
        "claim_limit": (
            "Read-only diagnosis of the Link-42 line-1 hardware First Red. "
            "It does not authorize or claim a product fix, new link, retry, "
            "latency result, promotion or acceptance."),
        "recommended_class_c_cut": {
            "predicate": "validate the plan field as canonical IS_SYMI, not heap IS_PTR",
            "scope": (
                "the active co-resident publish path and the mutually exclusive "
                "legacy C2-lite publication branch; no change to the producer or record width"),
            "permanent_fixtures": [
                "all emitted export-plan symbols are legal SYMI values",
                "SYMI is accepted and a heap pointer is rejected in this interned-only field",
                "Fixnum, BCODE, NIL and odd/corrupt SYMI mutations are rejected",
                "the 353-row Link-42 plan reaches publication in the product-shaped host fixture",
            ],
            "capacity": "unknown until a product-shaped WPLTO probe; no credit is prebooked",
        },
        "artifacts": [bind(path) for path in (
            PRODUCT, ELF, STRUCTURAL, DEPLOYMENT, SESSION, INITIAL_C2D,
            RUNTIME_SOURCE, LOW, BANK2, BANK3, LIVE_C2D, EXPORT_PLAN)],
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    print(f"c2-lite-v6-link42-export-symbol-domain-first-red: PASS "
          f"rows={plan_count} symi={plan_count} is_ptr=0 ready=0")
    print(f"receipt={RECEIPT.relative_to(ROOT)} sha256={sha(RECEIPT)}")


if __name__ == "__main__":
    main()
