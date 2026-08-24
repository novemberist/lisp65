#!/usr/bin/env python3
"""Attribute the recovery-sanitization pre-card active-frame Red."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
SOURCE = ROOT / "src/optional/c2_mapped_far_service_liveness_v4.s"
GATE = ROOT / "tools/host-lisp/c2_v160_active_frame_liveness.py"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
OUT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
              "c2.3-v1.6-recovery-sanitization-preflight-red-attribution.json")
CLANG = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORIZATION = "66ff6c73"

import sys
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))
from elf_truth import ElfTruth  # noqa: E402


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def body(truth: ElfTruth, name: str) -> bytes:
    symbol = truth.symbol(name)
    section = truth.section(symbol.section)
    raw = truth.section_bytes(symbol.section)
    offset = symbol.value - section.address
    return raw[offset:offset + symbol.bytes]


def derive() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="c2-v160-recovery-red-") as raw:
        obj = Path(raw) / "liveness.o"
        subprocess.run([str(CLANG), "-c", "-Isrc", str(SOURCE), "-o", str(obj)],
                       cwd=ROOT, check=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
        truth = ElfTruth.read(obj, llvm_readobj=READOBJ, include_section_data=True)
        section = truth.section(".lisp65_c2_mapped_far_service.liveness")
        walker = truth.symbol("c2_rtov_retire_continuations")
        shared = truth.symbol("c2_rtov_sanitize_saved_csrs")
        recovery = truth.symbol("c2_rtov_sanitize_recovery")
        walker_body = body(truth, walker.name)
        patterns = {
            "read_stack_return_low": walker_body.count(bytes.fromhex("b90701")),
            "read_stack_return_high": walker_body.count(bytes.fromhex("b90801")),
            "write_stack_return_low": walker_body.count(bytes.fromhex("990701")),
            "write_stack_return_high": walker_body.count(bytes.fromhex("990801")),
        }
        observed = {"far_liveness_section_bytes": section.bytes,
            "active_frame_walker_bytes": walker.bytes,
            "shared_saved_CSR_walker_bytes": shared.bytes,
            "ordinary_recovery_entry_bytes": recovery.bytes,
            "active_frame_stack_access_counts": patterns}
    expected = {"far_liveness_section_bytes": 80,
        "active_frame_walker_bytes": 80,
        "shared_saved_CSR_walker": "absent in predecessor world",
        "active_frame_stack_access_counts": {
            "read_stack_return_low": 1, "read_stack_return_high": 1,
            "write_stack_return_low": 1, "write_stack_return_high": 1}}
    require(observed["far_liveness_section_bytes"] == 84
            and observed["active_frame_walker_bytes"] == 41
            and observed["shared_saved_CSR_walker_bytes"] == 43
            and observed["ordinary_recovery_entry_bytes"] == 9
            and patterns == expected["active_frame_stack_access_counts"],
            "pre-card Red attribution does not match emitted object")
    process_roots = [
        ROOT / "build/c2.3/v1.6-execution-boundary-recovery-sanitization-process",
        ROOT / ("build/c2.3/v1.6-execution-boundary-recovery-sanitization-"
                "process-first-preflight-partial-20260824"),
    ]
    require(all(path.is_dir() for path in process_roots),
            "preserved preflight process evidence absent")
    return {"format": "lisp65-c2.3-v1.6-recovery-sanitization-preflight-red-attribution-v1",
        "recorded_on": "2026-08-24",
        "status": "ATTRIBUTED: ACTIVE-FRAME GATE PINS PRE-SPLIT OWNER SHAPE",
        "authority": {"commit": commit, "review_plan": bind(PLAN)},
        "inputs": {"candidate_liveness_source": bind(SOURCE),
            "active_frame_gate": bind(GATE)},
        "drift": {"expected_pre_split_world": expected,
            "observed_recovery_sanitization_world": observed,
            "difference": {
                "section_bytes": "+4 (80 -> 84)",
                "active_frame_owner_bytes": "-39 (80 -> 41)",
                "new_shared_saved_CSR_owner_bytes": 43,
                "active_frame_semantic_access_delta": 0}},
        "decision": {"class": "stored-world owner projection",
            "product_defect": False,
            "reason": ("the authorized split moved the seven-pair saved-CSR scan "
                       "to one shared owner; the active-frame body retains all four "
                       "stack access/write witnesses exactly once"),
            "required_successor": ("convert the active-frame gate from section == "
                                   "walker == 80 to component ownership: the active-"
                                   "frame walker proves its stack semantics while the "
                                   "shared sanitizer and its two consumers prove the "
                                   "recovery contract")},
        "attempt_accounting": {"preflight_invocations": 2,
            "why_second": "first background console did not return its terminal Red",
            "preserved_process_roots": [path.relative_to(ROOT).as_posix()
                                         for path in process_roots],
            "cards_consumed": 0, "product_WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0},
        "claim_limit": ("Host-only attribution of the pre-card gate Red. No gate "
                        "conversion, successor card, WPLTO, link, medium or device "
                        "contact is authorized by this result.")}


def main() -> int:
    value = derive()
    OUT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    print(f"recovery-sanitization preflight Red: {value['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
