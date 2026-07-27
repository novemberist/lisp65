#!/usr/bin/env python3
"""Bind the capacity first red of the authorized three-way C2J split."""

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
    "c2.2-nested-append-v5-reslice-capacity-first-red-receipt.json")
NOTE = ROOT / "docs/planning/c2.2-c2j-three-way-split-capacity-first-red.md"
DEFAULT_OUT = ROOT / "build/c2.2/c2j-three-way-capacity-first-red"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2j-three-way-capacity-first-red-receipt.json")

EXPECTED_PRODUCT_SHA = (
    "189548ea52b9af748217a0da94b7dc1d5daa5f17d190f5817f2fb4af486a676a")
EXPECTED_PREVIOUS_SHA = (
    "371c3ae7335bce3e56c3957163b5d0f0e46271873d56ed0160ad4b328df0a553")
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
    ".lisp65_rt_c2append_envelope": 1473,
    ".lisp65_rt_c2append_crc": 1075,
    ".lisp65_rt_c2append_metadata": 663,
    ".lisp65_rt_c2append_roots": 371,
    ".lisp65_rt_c2append_fronts": 1328,
    ".lisp65_rt_c2append_reserve_transient": 1606,
    ".lisp65_rt_c2append_reserve_persistent": 1273,
    ".lisp65_rt_c2append_journal_write": 882,
    ".lisp65_rt_c2append_journal_load": 1862,
    ".lisp65_rt_c2append_journal_clear": 224,
    ".lisp65_rt_c2append_stage": 1420,
    ".lisp65_rt_c2append_image": 834,
    ".lisp65_rt_c2append_entries": 1348,
    ".lisp65_rt_c2append_header": 624,
    ".lisp65_rt_c2append_publish_names": 1157,
    ".lisp65_rt_c2append_publish_cells": 1730,
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
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


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
    inputs = (SOURCE, HEADER, PRODUCT_PRG, MANIFEST, ARTIFACTS, PREVIOUS, NOTE)
    for path in inputs:
        require(path.is_file(), f"required input absent: {path}")
    require(sha(PRODUCT_PRG) == EXPECTED_PRODUCT_SHA,
            "Link-32 rollback identity drift")
    require(sha(PREVIOUS) == EXPECTED_PREVIOUS_SHA,
            "authorized predecessor receipt drift")

    artifacts = json.loads(ARTIFACTS.read_text())
    definitions = [*PRODUCT.definitions(artifacts), *FEATURES]
    DEFAULT_OUT.mkdir(parents=True)
    obj = DEFAULT_OUT / "c2-c2j-three-way.o"
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
            f"three-way C2J measurement drift: {measured}")

    journal_names = (
        ".lisp65_rt_c2append_journal_write",
        ".lisp65_rt_c2append_journal_load",
        ".lisp65_rt_c2append_journal_clear",
    )
    table = {
        name: {
            "bytes": EXPECTED[name],
            "cap_bytes": CAP,
            "headroom_bytes": CAP - EXPECTED[name],
            "status": "passed" if EXPECTED[name] <= CAP else "first-red",
        }
        for name in journal_names
    }
    require(table[journal_names[0]]["status"] == "passed"
            and table[journal_names[2]]["status"] == "passed",
            "write or clear did not fit")
    require(table[journal_names[1]]["headroom_bytes"] == -70,
            "expected load/validate/reconstruct first red did not fire")
    require(all(value <= CAP for name, value in EXPECTED.items()
                if name != journal_names[1]),
            "unexpected second overflowing phase")

    manifest = json.loads(MANIFEST.read_text())
    old = {item["section"]: item["file_size"] for item in manifest["slices"]}
    old_pair = (align(old[".lisp65_rt_c2append_capacity"])
                + align(old[".lisp65_rt_c2append_rollback"]))
    new_group_names = (
        ".lisp65_rt_c2append_roots",
        ".lisp65_rt_c2append_fronts",
        ".lisp65_rt_c2append_reserve_transient",
        ".lisp65_rt_c2append_reserve_persistent",
        *journal_names,
        ".lisp65_rt_c2append_rollback_unpublish",
        ".lisp65_rt_c2append_rollback_finalize",
    )
    new_group = sum(align(EXPECTED[name]) for name in new_group_names)
    other_v5_quantum_delta = 768
    projected = (manifest["storage"]["size"] + new_group - old_pair
                 + other_v5_quantum_delta)
    require(projected == 57758, "aggregate projection drift")

    report = {
        "format": "lisp65-c2-c2j-three-way-capacity-first-red-v1",
        "recorded_on": "2026-07-20",
        "status": "first-red-c2j-load-write-and-clear-green",
        "scope": {
            "target_relocatable_compiles": 1,
            "product_closure_links": 0,
            "hardware_runs": 0,
            "serial_driver_wiring": "not run",
            "overlay_closure_gate": "not run",
            "b2_run_stop_fixture": "not run",
        },
        "c2j_three_way_measurement": table,
        "first_red": {
            "section": journal_names[1],
            "operation": "load + identity/range/CRC validation + reconstruction",
            "bytes": EXPECTED[journal_names[1]],
            "cap_bytes": CAP,
            "over_cap_bytes": 70,
            "stop": "before driver wiring, B2, closure gate and product link",
        },
        "all_measured_append_sections": {
            name: {"bytes": value, "headroom_bytes": CAP - value}
            for name, value in EXPECTED.items()
        },
        "aggregate_projection_not_authorization": {
            "link32_session_bytes": manifest["storage"]["size"],
            "old_capacity_and_rollback_quanta_bytes": old_pair,
            "new_group_quanta_bytes": new_group,
            "other_v5_quantum_delta_bytes": other_v5_quantum_delta,
            "projected_session_bytes": projected,
            "projected_headroom_bytes": 65536 - projected,
            "projected_slice_count": len(manifest["slices"]) - 2 + 9,
            "claim": "aggregate fits; hard load/validate/reconstruct slice is red",
        },
        "preferred_review_option_not_authorized": {
            "split": ["journal_validate", "journal_reconstruct"],
            "transition": (
                "retain the exact validated 64-byte snapshot in the existing "
                "exclusive 304-byte append scratch; reconstruction consumes it "
                "before header storage is reused"),
            "resident_tuple_delta_bytes": 0,
            "bank5_reread_between_validation_and_reconstruction": False,
            "required_order": "validate then reconstruct; otherwise fail closed",
            "overlay_to_overlay_calls": "forbidden",
        },
        "bindings": {path.relative_to(ROOT).as_posix(): bind(path)
                     for path in inputs} | {
            "candidate_target_object": bind(obj),
            "target_compiler": bind(TOOLCHAIN / "mos-mega65-clang"),
        },
        "compiler": {
            "mode": "llvm-mos target relocatable, -Oz, no LTO",
            "command": command,
        },
        "claim_limit": (
            "Capacity first-red only. No C2J behavior, B2 cleanup, overlay "
            "closure, product identity, hardware or latency is claimed."),
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for path in (obj, RECEIPT):
        os.chmod(path, 0o444)
    print("c2-c2j-three-way-capacity: FIRST RED "
          "write=882/1792 load=1862/1792 clear=224/1792 "
          "projected-headroom=7778 product-links=0")


if __name__ == "__main__":
    main()
