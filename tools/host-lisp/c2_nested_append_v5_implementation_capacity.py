#!/usr/bin/env python3
"""Bind the first capacity red of the authorized C2D-v5 implementation cut.

This deliberately compiles relocatable target objects only.  It may not build
or mutate a product candidate after a hard runtime-slice overflow is observed.
"""

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
PRODUCT_RUNTIME_HEADER = ROOT / "src/c2_product_runtime.h"
INTERRUPT_SOURCE = ROOT / "src/interrupt.c"
STREAM_DECODER = ROOT / "scripts/c2-stream-decoder.c"
STREAM_V2_DECODER = ROOT / "scripts/c2-stream-v2-decoder.c"
PRODUCT_DECODER = ROOT / "src/c2_product_decoder.c"
HOT_LITERAL = ROOT / "src/c2_hot_literal.c"
HANDLE_CONTRACT = ROOT / "config/c2-transient-handle-contract.json"
HANDLE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-transient-handle-contract-probe-receipt.json")
NESTED_CONTRACT = ROOT / "config/c2-nested-append-unwind-contract.json"
NESTED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-nested-append-unwind-contract-probe-receipt.json")
QUICK_PASS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-cross-invariant-prelink-quick-pass-receipt.json")
MATRIX = ROOT / "docs/planning/c2.2-cross-invariant-matrix.md"
DECISION_NOTE = ROOT / (
    "docs/planning/c2.2-nested-append-v5-implementation-capacity-first-red.md")
PRESMOKE = ROOT / "config/c2-hot-refill-hardware-presmoke.json"
ARTIFACTS = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
LINK32 = ROOT / "build/c2.2/substitution/product-link-32-preinstall-island-guard"
LINK32_PRODUCT = LINK32 / "lisp65-c2-substitution-linked.prg"
LINK32_MANIFEST = LINK32 / "runtime-overlays-session-final.json"
DEFAULT_OUT = ROOT / "build/c2.2/nested-append-v5-implementation-capacity-first-red"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-nested-append-v5-implementation-capacity-first-red-receipt.json")

EXPECTED_PRODUCT_SHA = (
    "189548ea52b9af748217a0da94b7dc1d5daa5f17d190f5817f2fb4af486a676a")
SLICE_CAP = 1792
LINK32_FEATURES = (
    "LISP65_C2_DIRECT_HOT_REFILL",
    "LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH",
    "LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND",
    "LISP65_C2_TRANSACTION_AUTH",
    "LISP65_C2_TRANSACTION_AUTH_NOINLINE",
)
SECTIONS = (
    ".lisp65_rt_c2append_envelope",
    ".lisp65_rt_c2append_crc",
    ".lisp65_rt_c2append_metadata",
    ".lisp65_rt_c2append_capacity",
    ".lisp65_rt_c2append_stage",
    ".lisp65_rt_c2append_image",
    ".lisp65_rt_c2append_entries",
    ".lisp65_rt_c2append_header",
    ".lisp65_rt_c2append_publish_names",
    ".lisp65_rt_c2append_publish_cells",
    ".lisp65_rt_c2append_rollback",
)


class ProbeError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
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
    proc = subprocess.run(command, cwd=ROOT, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode:
        raise ProbeError("command failed: " + " ".join(command)
                         + "\n" + proc.stdout + proc.stderr)
    return proc.stdout


def section_sizes(obj: Path) -> dict[str, int]:
    text = run([str(TOOLCHAIN / "llvm-size"), "-A", str(obj)])
    result: dict[str, int] = {}
    for line in text.splitlines():
        match = re.match(r"^(\.\S+)\s+(\d+)\s+\d+\s*$", line)
        if match:
            result[match.group(1)] = int(match.group(2))
    return result


def compile_object(out: Path, artifacts: dict[str, Any], *, v5: bool
                   ) -> tuple[Path, list[str]]:
    name = "candidate-v5.o" if v5 else "link32-source-baseline.o"
    target = out / name
    definitions = [*PRODUCT.definitions(artifacts), *LINK32_FEATURES]
    if v5:
        definitions.append("LISP65_C2_NESTED_APPEND_V5")
    command = [
        str(TOOLCHAIN / "mos-mega65-clang"), "-Oz", "-Wall", "-Wextra",
        "-fno-lto", "-ffunction-sections", "-fdata-sections",
        *(f"-D{item}" for item in definitions),
        "-I", str(ROOT / "src"),
        "-I", str(ROOT / "scripts"),
        "-I", str(ROOT / "build/c2.2/substitution"),
        "-I", str(LINK32),
        "-I", str(ROOT / "build/bytecode"),
        "-c", str(SOURCE), "-o", str(target),
    ]
    run(command)
    return target, command


def main() -> None:
    out = DEFAULT_OUT
    require(not out.exists(), f"output already exists: {out}")
    require(not RECEIPT.exists(), f"receipt already exists: {RECEIPT}")
    inputs = (
        SOURCE, PRODUCT_RUNTIME_HEADER, INTERRUPT_SOURCE, STREAM_DECODER,
        STREAM_V2_DECODER, PRODUCT_DECODER, HOT_LITERAL, HANDLE_CONTRACT,
        HANDLE_RECEIPT, NESTED_CONTRACT, NESTED_RECEIPT, QUICK_PASS, MATRIX,
        DECISION_NOTE, PRESMOKE, ARTIFACTS, LINK32_PRODUCT, LINK32_MANIFEST,
    )
    for path in inputs:
        require(path.is_file(), f"required input absent: {path}")
    require(sha(LINK32_PRODUCT) == EXPECTED_PRODUCT_SHA,
            "Link-32 rollback identity drift")
    require(json.loads(HANDLE_RECEIPT.read_text())["status"]
            == "passed-contract-and-capacity-probe-product-work-not-authorized",
            "transient-handle prerequisite is not green")
    require(json.loads(NESTED_RECEIPT.read_text())["status"]
            == "passed-host-contract-probe-product-work-not-authorized",
            "nested semantic prerequisite is not green")

    artifacts = json.loads(ARTIFACTS.read_text())
    out.mkdir(parents=True)
    baseline_obj, baseline_command = compile_object(out, artifacts, v5=False)
    candidate_obj, candidate_command = compile_object(out, artifacts, v5=True)
    baseline = section_sizes(baseline_obj)
    candidate = section_sizes(candidate_obj)
    require(all(name in baseline and name in candidate for name in SECTIONS),
            "append section inventory incomplete")

    manifest = json.loads(LINK32_MANIFEST.read_text())
    linked = {item["section"]: item["file_size"] for item in manifest["slices"]}
    require(baseline[".lisp65_rt_c2append_capacity"]
            == linked[".lisp65_rt_c2append_capacity"] == 1398,
            "first-red baseline does not calibrate to Link 32")
    first = candidate[".lisp65_rt_c2append_capacity"] - SLICE_CAP
    rollback = candidate[".lisp65_rt_c2append_rollback"] - SLICE_CAP
    require(candidate[".lisp65_rt_c2append_capacity"] == 3950
            and first == 2158, "capacity first-red measurement drift")
    require(candidate[".lisp65_rt_c2append_rollback"] == 2235
            and rollback == 443, "rollback diagnostic measurement drift")

    table: dict[str, Any] = {}
    for name in SECTIONS:
        table[name] = {
            "link32_source_baseline_bytes": baseline[name],
            "link32_lto_manifest_bytes": linked.get(name),
            "candidate_v5_bytes": candidate[name],
            "candidate_delta_vs_source_baseline_bytes": (
                candidate[name] - baseline[name]),
            "candidate_headroom_under_1792_bytes": SLICE_CAP - candidate[name],
        }

    report = {
        "format": "lisp65-c2-nested-append-v5-implementation-capacity-first-red-v1",
        "recorded_on": "2026-07-20",
        "status": "first-red-runtime-slice-cap-product-link-not-run",
        "scope": {
            "target_relocatable_compiles": 2,
            "product_closure_links": 0,
            "hardware_runs": 0,
            "link32_product_modified": False,
            "feature_gate": "LISP65_C2_NESTED_APPEND_V5",
        },
        "first_red": {
            "section": ".lisp65_rt_c2append_capacity",
            "cap_bytes": SLICE_CAP,
            "baseline_bytes": baseline[".lisp65_rt_c2append_capacity"],
            "candidate_bytes": candidate[".lisp65_rt_c2append_capacity"],
            "over_cap_bytes": first,
            "decision": "stop before B2/C2J implementation and every product link",
        },
        "same_object_diagnostic_only": {
            "section": ".lisp65_rt_c2append_rollback",
            "cap_bytes": SLICE_CAP,
            "baseline_target_object_bytes": baseline[
                ".lisp65_rt_c2append_rollback"],
            "baseline_link32_lto_bytes": linked[
                ".lisp65_rt_c2append_rollback"],
            "candidate_bytes": candidate[".lisp65_rt_c2append_rollback"],
            "over_cap_bytes": rollback,
            "claim": "not a second gate traversal; observed in the same first-red object",
        },
        "section_measurements": table,
        "frozen_walls": {
            "runtime_slice_cap_bytes": SLICE_CAP,
            "link32_session_runtime_bank_bytes": manifest["storage"]["size"],
            "link32_session_runtime_bank_headroom_bytes": (
                65536 - manifest["storage"]["size"]),
            "bank0_text_headroom_bytes": 10,
            "bank0_bss_headroom_bytes": 19,
            "resident_island_projected_headroom_after_handle_probe_bytes": 16,
            "e000_policy": "closed-to-new-tenants",
            "measurement_boundary": (
                "Only the hard per-slice red was reached. No successor layout "
                "or aggregate runtime-bank debit is claimed."),
        },
        "b2_and_c2_disposition": {
            "b2": (
                "Owner-authorized shared C2J cleanup plus RUN/STOP fixture; "
                "implementation not reached because capacity stopped first."),
            "c2": (
                "Permanently added to every hardware presmoke as current-identity "
                "$e000 byte-identity plus resumed Lisp call."),
        },
        "required_architecture_review": {
            "preferred_direction": "semantic session-slice split",
            "capacity_split": (
                "front discovery/reservation and metadata-root counting become "
                "serial phases driven outside an active overlay"),
            "rollback_split": (
                "publish-first invalidation, record/Attic wipe and C2J completion "
                "become serial phases driven outside an active overlay"),
            "rejected_without_new_owner_decision": [
                "relax the 1792-byte cap",
                "place new code in the closed E000 window",
                "consume the 16-byte Island remainder",
                "start a product link despite the first red",
            ],
        },
        "bindings": {
            path.relative_to(ROOT).as_posix(): bind(path) for path in inputs
        } | {
            "baseline_target_object": bind(baseline_obj),
            "candidate_target_object": bind(candidate_obj),
            "target_compiler": bind(TOOLCHAIN / "mos-mega65-clang"),
        },
        "compiler": {
            "mode": "llvm-mos target relocatable, -Oz, no LTO",
            "baseline_command": baseline_command,
            "candidate_command": candidate_command,
        },
        "claim_limit": (
            "First-red implementation-capacity evidence only. C2J/B2 product "
            "cleanup, nested semantics in target code, aggregate placement, "
            "product identity, hardware behavior, latency and promotion are not claimed."),
    }
    encoded = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_bytes(encoded)
    for path in (baseline_obj, candidate_obj, RECEIPT):
        os.chmod(path, 0o444)
    print("c2-nested-append-v5-capacity: FIRST RED "
          f"capacity={candidate['.lisp65_rt_c2append_capacity']}/{SLICE_CAP} "
          f"rollback={candidate['.lisp65_rt_c2append_rollback']}/{SLICE_CAP} "
          "product-links=0")


if __name__ == "__main__":
    main()
