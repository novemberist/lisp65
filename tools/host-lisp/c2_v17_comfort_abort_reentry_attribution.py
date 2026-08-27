#!/usr/bin/env python3
"""Attribute the v1.7 Comfort abort-to-reentry E29 from the raw capture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))
from elf_truth import ElfTruth  # noqa: E402


ELF = ROOT / (
    "build/c2.3/v1.7-comfort-phase1b-acceptance-media-r1/"
    "canonical-product/final/lisp65-c2-substitution-linked.prg.elf")
CAPTURE = ROOT / (
    "build/c2.3/v1.7-comfort-phase1b-acceptance-media-r1/device-session/"
    "abort-reentry-first-red-20260825/capture.json")
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
RUNTIME = ROOT / "src/c2_product_runtime.c"
OVERLAY = ROOT / "src/vm_runtime_overlay.c"
INTERRUPT = ROOT / "src/interrupt.c"
REPL = ROOT / "src/repl.c"
OUT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-comfort-abort-reentry-attribution.json")
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def u16(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset:offset + 2], "little")


def source_function(source: str, name: str) -> str:
    match = re.search(
        rf"^[^#\n]*\b{re.escape(name)}\s*\([^;{{]*?\)\s*\{{",
        source, re.MULTILINE | re.DOTALL)
    require(match is not None, f"source function absent: {name}")
    depth = 0
    for offset, char in enumerate(source[match.start():]):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():match.start() + offset + 1]
    raise AttributionError(f"source function unterminated: {name}")


def derive() -> dict[str, Any]:
    capture = json.loads(CAPTURE.read_text(encoding="utf-8"))
    rows = {row["name"]: bytes.fromhex(row["observed_hex"])
            for row in capture["reads"]}
    require(set(rows) == {
        "bank0-runtime-status", "pending-error-detail",
        "runtime-overlay-lifecycle", "c2-runtime",
        "abort-record-and-meta", "c2d-header", "c2d-high-row63",
        "c2d-comfort-rows353-356", "c2j"},
        "capture range set drift")

    bank0 = rows["bank0-runtime-status"]
    zp = lambda address, size=1: bank0[address - 0x20:address - 0x20 + size]
    ready = zp(0x8C)[0]
    phase_owner = zp(0x89)[0]
    rtov_busy = zp(0x78)[0]
    rtov_loaded_len = u16(bank0, 0x79 - 0x20)
    runtime_lifecycle = rows["runtime-overlay-lifecycle"]
    rtov_fault = runtime_lifecycle[7]
    rtov_family = runtime_lifecycle[8]
    rtov_generation = u16(runtime_lifecycle, 9)
    abort = rows["abort-record-and-meta"]
    front_depth = abort[0]
    journal_result = abort[31]
    abort_state, abort_start, abort_end, abort_done = abort[32:36]
    header = rows["c2d-header"]
    runtime = rows["c2-runtime"]

    require(ready == 0, "post-E29 READY was not cleared")
    require(phase_owner == 2, "post-E29 phase owner is not APPEND")
    require((rtov_busy, rtov_loaded_len) == (0, 0),
            "runtime overlay remained active after abort")
    require((rtov_fault, rtov_family, rtov_generation) == (14, 2, 1),
            "runtime overlay fault/family/generation drift")
    require((abort_state, abort_start, abort_end, abort_done)
            == (1, 31, 32, 0),
            "abort progression no longer stops on validate/reconstruct range")
    require(journal_result == 0 and rows["c2j"] == bytes(64),
            "C2J is not clean at the First Red")
    require(rows["c2d-high-row63"] == bytes(32),
            "a transient high-row record survived the abort")
    require(header[:5] == b"C2D\0\x06"
            and u16(header, 8) == 4096 and u16(header, 10) == 1,
            "live C2D header identity drift")
    require(runtime[8:10] == header[36:38]
            and runtime[10:14] == header[10:14]
            and runtime[14:16] == header[16:18]
            and runtime[16:18] == header[20:22]
            and runtime[18:26] == header[28:36]
            and runtime[26:28] == header[24:26],
            "resident runtime counts differ from live C2D")
    comfort_rows = rows["c2d-comfort-rows353-356"]
    require(all(comfort_rows[i * 10:(i + 1) * 10] != bytes(10)
                for i in range(4)),
            "published Comfort entry row disappeared")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    overlay_start = truth.symbol("__lisp65_workbench_overlay_start")
    overlay_limit = truth.symbol("__lisp65_workbench_runtime_overlay_limit")
    require((overlay_start.value, overlay_limit.value) == (0xC356, 0xCA56),
            "runtime-overlay execution window drift")
    mapped = [section for section in truth.sections
              if section.name.startswith(".lisp65_rt_")]
    require(mapped and max(section.bytes for section in mapped) <= 1792
            and all(section.address >= overlay_start.value
                    and section.address + section.bytes <= overlay_limit.value
                    for section in mapped),
            "linked overlay sections violate static stack-window bounds")

    overlay_source = OVERLAY.read_text(encoding="utf-8")
    exec_body = source_function(overlay_source, "vm_runtime_overlay_exec_family")
    require("RTOV_SOFT_SP() <= RTOV_LIMIT" in exec_body
            and "VM_RUNTIME_OVERLAY_ERR_STACK" in exec_body,
            "dynamic soft-stack refusal seam drift")
    interrupt_source = INTERRUPT.read_text(encoding="utf-8")
    abort_jump = source_function(interrupt_source, "lisp_abort_jump")
    require(abort_jump.index("c2_product_abort_cleanup()")
            < abort_jump.index("longjmp(lisp_toplevel, 1)"),
            "cleanup is no longer attempted before stack-restoring longjmp")
    repl_source = REPL.read_text(encoding="utf-8")
    require("if (setjmp(lisp_toplevel))" in repl_source,
            "top-level restored-stack landing drift")

    # The other three ERR_STACK predicates are candidate constants and are
    # proved false by the linked start/limit and section extents above.  The
    # captured 14 can therefore only be the live soft-stack predicate.
    alternatives = {
        "stale_C2J": rows["c2j"] != bytes(64),
        "transient_record": rows["c2d-high-row63"] != bytes(32),
        "static_overlay_extent": any(
            section.address + section.bytes > overlay_limit.value
            for section in mapped),
    }
    require(not alternatives["stale_C2J"]
            and not alternatives["transient_record"]
            and not alternatives["static_overlay_extent"],
            "excluded alternative unexpectedly live")

    return {
        "format": "lisp65-c2-v17-comfort-abort-reentry-attribution-v1",
        "recorded_on": "2026-08-25",
        "status": "ATTRIBUTED: PRE-LONGJMP SOFT-STACK OVERLAY REFUSAL",
        "authority": {
            "plan": bind(PLAN), "candidate_ELF": bind(ELF),
            "raw_capture": bind(CAPTURE),
        },
        "inputs": {
            "product_runtime": bind(RUNTIME),
            "runtime_overlay": bind(OVERLAY),
            "abort_landing": bind(INTERRUPT), "native_repl": bind(REPL),
        },
        "device": {
            "tuple": capture["tuple"],
            "c2_ready": ready,
            "phase_owner": {"value": phase_owner, "name": "APPEND"},
            "rtov": {"busy": rtov_busy, "loaded_len": rtov_loaded_len,
                     "fault": {"value": rtov_fault, "name": "ERR_STACK"},
                     "family": {"value": rtov_family, "name": "SESSION"},
                     "generation": rtov_generation},
            "abort": {"state": abort_state, "start_slot": abort_start,
                      "end_slot": abort_end, "done": abort_done,
                      "front_depth_scratch": {
                          "value": front_depth,
                          "causal": False,
                          "reason": "fronts phase was never reached",
                      },
                      "journal_result": journal_result},
            "c2j": {"bytes": 64, "all_zero": True},
            "high_row63_all_zero": True,
            "comfort_rows_353_356_present": True,
        },
        "mechanism": {
            "name": "abort cleanup executes transported C2J phases before longjmp restores the soft stack",
            "sequence": [
                "Comfort evaluation raises the intentional type error",
                "lisp_abort_jump invokes c2_product_abort_cleanup on the still-deep Comfort soft stack",
                "journal validate/reconstruct is the first transported abort range",
                "vm_runtime_overlay_exec_family rejects RTOV_SOFT_SP <= 0xca56 with ERR_STACK",
                "c2_abort_driver clears c2_ready and cannot release the APPEND owner after the latched transport fault",
                "longjmp returns to the native prompt; the next persistent BCODE lookup has zero visible length and reports E29",
            ],
            "linked_window": {"start": "0xc356", "limit": "0xca56",
                              "bytes": 1792},
            "excluded": [
                "stale C2J (64 zero bytes)",
                "surviving transient record (row 63 is zero)",
                "lost Comfort publication (all four entry rows remain present)",
                "static overlay overflow (all linked sections fit the window)",
                "runtime-overlay busy or unwiped payload (busy=0, loaded_len=0)",
            ],
        },
        "repair_boundary": {
            "required_property": (
                "transported C2J cleanup runs after the top-level longjmp has "
                "restored the soft stack and before error rendering or new evaluation"),
            "pre_longjmp_work_retained": (
                "overlay retirement/transaction invalidation and continuation "
                "sanitization remain before control leaves the failing stack"),
            "one_round_only": True,
            "not_a_ready_rearm": True,
        },
        "claim_limit": (
            "Names the post-E26 E29 mechanism from one stopped-state capture "
            "and the accepted final ELF. No fix, link, medium or acceptance claim."),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"write", "check"},
            "usage: write|check")
    raw = canonical(derive())
    if sys.argv[1] == "write":
        OUT.write_bytes(raw)
    else:
        require(OUT.is_file() and OUT.read_bytes() == raw,
                "Comfort abort-reentry attribution receipt drift")
    print("v1.7 Comfort abort reentry: ATTRIBUTED ERR_STACK before longjmp")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError) as error:
        print(f"v1.7-comfort-abort-reentry-attribution: FAIL: {error}",
              file=sys.stderr)
        raise SystemExit(1)
