#!/usr/bin/env python3
"""Bind the semantic append-reslice result and the following C2J first red."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_product_substitution_link as PRODUCT  # noqa: E402

TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
SOURCE = ROOT / "src/c2_product_runtime.c"
HEADER = ROOT / "src/c2_product_runtime.h"
LINK32 = ROOT / "build/c2.2/substitution/product-link-32-preinstall-island-guard"
PRODUCT_PRG = LINK32 / "lisp65-c2-substitution-linked.prg"
MANIFEST = LINK32 / "runtime-overlays-session-final.json"
ARTIFACTS = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
PREVIOUS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-nested-append-v5-implementation-capacity-first-red-receipt.json")
HANDLE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-transient-handle-contract-probe-receipt.json")
NOTE = ROOT / "docs/planning/c2.2-nested-append-v5-reslice-capacity-first-red.md"
DEFAULT_OUT = ROOT / "build/c2.2/nested-append-v5-reslice-capacity-first-red"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-nested-append-v5-reslice-capacity-first-red-receipt.json")

EXPECTED_PRODUCT_SHA = (
    "189548ea52b9af748217a0da94b7dc1d5daa5f17d190f5817f2fb4af486a676a")
EXPECTED_PREVIOUS_SHA = (
    "2767feb19cc70de7a5492614743cc98b6efb874756a2fd8f3107eea57d96abda")
CAP = 1792
FEATURES = (
    "LISP65_C2_DIRECT_HOT_REFILL",
    "LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH",
    "LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND",
    "LISP65_C2_TRANSACTION_AUTH",
    "LISP65_C2_TRANSACTION_AUTH_NOINLINE",
    "LISP65_C2_NESTED_APPEND_V5",
)
EXPECTED = {
    ".lisp65_rt_c2append_roots": 371,
    ".lisp65_rt_c2append_fronts": 1328,
    ".lisp65_rt_c2append_reserve_transient": 1606,
    ".lisp65_rt_c2append_reserve_persistent": 1273,
    ".lisp65_rt_c2append_journal": 2749,
    ".lisp65_rt_c2append_rollback_unpublish": 739,
    ".lisp65_rt_c2append_rollback_finalize": 1682,
}


class ProbeError(RuntimeError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def run(command: list[str]) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise ProbeError("command failed: " + " ".join(command)
                         + "\n" + result.stdout + result.stderr)
    return result.stdout


def sizes(obj: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in run([str(TOOLCHAIN / "llvm-size"), "-A", str(obj)]).splitlines():
        match = re.match(r"^(\.\S+)\s+(\d+)\s+\d+\s*$", line)
        if match:
            result[match.group(1)] = int(match.group(2))
    return result


def align(value: int) -> int:
    return (value + 255) & ~255


def main() -> None:
    require(not DEFAULT_OUT.exists(), f"output already exists: {DEFAULT_OUT}")
    require(not RECEIPT.exists(), f"receipt already exists: {RECEIPT}")
    inputs = (SOURCE, HEADER, PRODUCT_PRG, MANIFEST, ARTIFACTS, PREVIOUS,
              HANDLE_RECEIPT, NOTE)
    for path in inputs:
        require(path.is_file(), f"required input absent: {path}")
    require(sha(PRODUCT_PRG) == EXPECTED_PRODUCT_SHA,
            "Link-32 rollback identity drift")
    require(sha(PREVIOUS) == EXPECTED_PREVIOUS_SHA,
            "previous first-red receipt drift")

    artifacts = json.loads(ARTIFACTS.read_text())
    definitions = [*PRODUCT.definitions(artifacts), *FEATURES]
    DEFAULT_OUT.mkdir(parents=True)
    obj = DEFAULT_OUT / "c2-nested-append-v5-reslice.o"
    command = [
        str(TOOLCHAIN / "mos-mega65-clang"), "-Oz", "-Wall", "-Wextra",
        "-fno-lto", "-ffunction-sections", "-fdata-sections",
        *(f"-D{item}" for item in definitions),
        "-I", str(ROOT / "src"), "-I", str(ROOT / "scripts"),
        "-I", str(ROOT / "build/c2.2/substitution"),
        "-I", str(LINK32), "-I", str(ROOT / "build/bytecode"),
        "-c", str(SOURCE), "-o", str(obj),
    ]
    run(command)
    measured = sizes(obj)
    require(all(measured.get(name) == value for name, value in EXPECTED.items()),
            f"reslice measurement drift: {measured}")
    passed = {name: {"bytes": value, "headroom_bytes": CAP - value}
              for name, value in EXPECTED.items() if name != ".lisp65_rt_c2append_journal"}
    require(all(item["headroom_bytes"] >= 0 for item in passed.values()),
            "authorized semantic reslice still exceeds the cap")
    journal = EXPECTED[".lisp65_rt_c2append_journal"]
    require(journal > CAP, "expected C2J first red did not fire")

    manifest = json.loads(MANIFEST.read_text())
    old = {item["section"]: item["file_size"] for item in manifest["slices"]}
    old_pair = align(old[".lisp65_rt_c2append_capacity"]) + align(
        old[".lisp65_rt_c2append_rollback"])
    new_group = sum(align(value) for value in EXPECTED.values())
    other_quantum_delta = 768
    projected = (manifest["storage"]["size"] + new_group - old_pair
                 + other_quantum_delta)

    report = {
        "format": "lisp65-c2-nested-append-v5-reslice-capacity-first-red-v1",
        "recorded_on": "2026-07-20",
        "status": "first-red-c2j-slice-append-and-rollback-reslice-green",
        "scope": {
            "target_relocatable_compiles": 1,
            "product_closure_links": 0,
            "hardware_runs": 0,
            "driver_wiring_after_first_red": "not run",
            "b2_fixture": "not run",
        },
        "semantic_reslice": {
            "status": "passed-per-section-capacity",
            "phases": passed,
            "transition_tuple": {
                "storage": "existing exclusive 304-byte append scratch",
                "resident_text_delta_bytes": 0,
                "resident_island_delta_bytes": 0,
                "ordinary_bss_delta_bytes": 0,
            },
            "overlay_to_overlay_rule": (
                "Serial resident driver is the sole loader; phase closures may "
                "not name another phase or overlay transport. Structural gate "
                "remains required after capacity is green."),
        },
        "first_red": {
            "section": ".lisp65_rt_c2append_journal",
            "bytes": journal,
            "cap_bytes": CAP,
            "over_cap_bytes": journal - CAP,
            "combined_actions": [
                "prepare/write/readback",
                "load/identity/range/CRC validation and scratch reconstruction",
                "clear/readback",
            ],
            "stop": "before serial-driver wiring, B2 proof and product link",
        },
        "aggregate_projection_not_authorization": {
            "link32_session_bytes": manifest["storage"]["size"],
            "old_capacity_and_rollback_quanta_bytes": old_pair,
            "new_group_quanta_including_invalid_journal_bytes": new_group,
            "other_v5_quantum_delta_bytes": other_quantum_delta,
            "projected_session_bytes": projected,
            "projected_headroom_bytes": 65536 - projected,
            "projected_slice_count": len(manifest["slices"]) - 2 + len(EXPECTED),
            "claim": "aggregate fits; hard per-slice gate is red",
        },
        "preferred_review_option": (
            "Split C2J into serial write, validated-load and clear actions; "
            "retain the no-overlay-calls-overlay invariant and remeasure all walls."),
        "bindings": {path.relative_to(ROOT).as_posix(): bind(path)
                     for path in inputs} | {
            "candidate_target_object": bind(obj),
            "target_compiler": bind(TOOLCHAIN / "mos-mega65-clang"),
        },
        "compiler": {"mode": "llvm-mos target relocatable, -Oz, no LTO",
                     "command": command},
        "claim_limit": (
            "Capacity first-red only. No C2J product behavior, B2 rollback, "
            "overlay-closure gate, product identity, hardware or latency is claimed."),
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for path in (obj, RECEIPT):
        os.chmod(path, 0o444)
    print("c2-v5-reslice-capacity: FIRST RED "
          f"journal={journal}/{CAP} passed-reslice-phases={len(passed)} "
          "product-links=0")


if __name__ == "__main__":
    main()
