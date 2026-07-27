#!/usr/bin/env python3
"""Permanent C2D-v5 append/abort prelink gate and one-shot receipt emitter.

This gate deliberately stops at target relocatables.  It proves the serial
driver shape, the no-overlay-calls-overlay closure, the shared RUN/STOP C2J
landing and every current runtime-slice cap without creating a product link.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_nested_append_unwind_probe as MODEL  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402

TOOLCHAIN = ROOT / "tools/llvm-mos/bin"
SOURCE = ROOT / "src/c2_product_runtime.c"
HEADER = ROOT / "src/c2_product_runtime.h"
INTERRUPT = ROOT / "src/interrupt.c"
CONTRACT = ROOT / "config/c2-nested-append-unwind-contract.json"
HANDLE_CONTRACT = ROOT / "config/c2-transient-handle-contract.json"
CONTRACT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-nested-append-unwind-contract-probe-receipt.json")
HANDLE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-transient-handle-contract-probe-receipt.json")
PREVIOUS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2j-three-way-capacity-first-red-receipt.json")
MATRIX = ROOT / "docs/planning/c2.2-cross-invariant-matrix.md"
NOTE = ROOT / "docs/planning/c2.2-nested-append-v5-prelink.md"
ARTIFACTS = ROOT / "build/c2.2/substitution/substitution-artifacts.json"
LINK32 = ROOT / "build/c2.2/substitution/product-link-32-preinstall-island-guard"
PRODUCT_PRG = LINK32 / "lisp65-c2-substitution-linked.prg"
MANIFEST = LINK32 / "runtime-overlays-session-final.json"
OUT = ROOT / "build/c2.2/nested-append-v5-prelink"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-nested-append-v5-prelink-receipt.json")

EXPECTED_PRODUCT_SHA = (
    "189548ea52b9af748217a0da94b7dc1d5daa5f17d190f5817f2fb4af486a676a")
EXPECTED_PREVIOUS_SHA = (
    "1bb495c6486ef786a9a1a4a496727ce158480080b30686b57f5eb22d18d19e2c")
EXPECTED_CONTRACT_RECEIPT_SHA = (
    "bd2a0ebbc3ac08c07108c238a33426bd65c0e6e9e33563d024e6a751b36a0381")
EXPECTED_HANDLE_RECEIPT_SHA = (
    "d337afdd0ff5d0b1d382005d7427cf6ee33563378cc5dcc65828d828db023a37")
CAP = 1792
FEATURES = (
    "LISP65_C2_DIRECT_HOT_REFILL",
    "LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH",
    "LISP65_RUNTIME_OVERLAY_TRANSACTION_AUTH_ISLAND",
    "LISP65_C2_TRANSACTION_AUTH",
    "LISP65_C2_TRANSACTION_AUTH_NOINLINE",
    "LISP65_C2_NESTED_APPEND_V5",
)
PHASES = (
    "envelope", "crc", "metadata", "roots", "fronts",
    "reserve_transient", "reserve_persistent", "journal_clear",
    "journal_write", "journal_validate", "journal_reconstruct",
    "rollback_prepare", "stage", "image", "entries", "header",
    "publish_names", "publish_cells", "rollback_unpublish",
    "rollback_finalize",
)
EXPECTED_SIZES = {
    "envelope": 1473,
    "crc": 1075,
    "metadata": 663,
    "roots": 371,
    "fronts": 1328,
    "reserve_transient": 1606,
    "reserve_persistent": 1273,
    "journal_clear": 239,
    "journal_write": 882,
    "journal_validate": 970,
    "journal_reconstruct": 1176,
    "rollback_prepare": 1080,
    "stage": 1420,
    "image": 834,
    "entries": 1348,
    "header": 624,
    "publish_names": 1157,
    "publish_cells": 1730,
    "rollback_unpublish": 739,
    "rollback_finalize": 1682,
}
EXPECTED_RUNTIME = {
    # The internal BADOPCODE scaffold is retired.  The remaining seven-byte
    # E000 change is the one shared rollback-plan setup seam; Bank-0 install
    # and abort code recover the duplicated policy below.
    ".lisp65_c2_kernal_window.c2_resident": 6562,
    ".text.c2_product_abort_cleanup": 14,
    ".text.c2_abort_driver": 200,
    ".text.c2_product_append_staged": 116,
    ".text.c2_product_install": 571,
    ".bss.c2_journal_count": 2,
}


class GateError(RuntimeError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def run(command: list[str]) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise GateError("command failed: " + " ".join(command)
                        + "\n" + result.stdout + result.stderr)
    return result.stdout


def align(value: int) -> int:
    return (value + 255) & ~255


def function_body(source: str, name: str) -> str:
    matches = list(re.finditer(
        r"^[^\n;{}]*\b(?:uint8_t|uint16_t|void|obj)\s+"
        + re.escape(name) + r"\s*\([^;]*?\)\s*\{", source,
        re.DOTALL | re.MULTILINE))
    require(matches, f"function absent: {name}")
    # Some source-only fallback implementations use the same private name
    # under an earlier preprocessor branch.  The active sliced implementation
    # is the final definition in this translation unit.
    match = matches[-1]
    start = source.find("{", match.start())
    depth = 0
    for at in range(start, len(source)):
        if source[at] == "{":
            depth += 1
        elif source[at] == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1:at]
    raise GateError(f"unterminated function: {name}")


def compile_objects(out: Path) -> tuple[Path, Path, list[list[str]]]:
    artifacts = json.loads(ARTIFACTS.read_text(encoding="utf-8"))
    definitions = [*PRODUCT.definitions(artifacts), *FEATURES]
    common = [
        str(TOOLCHAIN / "mos-mega65-clang"), "-Oz", "-Wall", "-Wextra",
        "-fno-lto", "-ffunction-sections", "-fdata-sections",
        *(f"-D{item}" for item in definitions),
        "-I", str(ROOT / "src"), "-I", str(ROOT / "scripts"),
        "-I", str(ROOT / "build/c2.2/substitution"),
        "-I", str(LINK32), "-I", str(ROOT / "build/bytecode"),
    ]
    out.mkdir(parents=True, exist_ok=True)
    commands: list[list[str]] = []
    objects = []
    for source, name in ((SOURCE, "c2-runtime.o"), (INTERRUPT, "interrupt.o")):
        target = out / name
        command = [*common, "-c", str(source), "-o", str(target)]
        run(command)
        commands.append(command)
        objects.append(target)
    return objects[0], objects[1], commands


def preprocess_runtime() -> str:
    artifacts = json.loads(ARTIFACTS.read_text(encoding="utf-8"))
    definitions = [*PRODUCT.definitions(artifacts), *FEATURES]
    return run([
        str(TOOLCHAIN / "mos-mega65-clang"), "-E",
        *(f"-D{item}" for item in definitions),
        "-I", str(ROOT / "src"), "-I", str(ROOT / "scripts"),
        "-I", str(ROOT / "build/c2.2/substitution"),
        "-I", str(LINK32), "-I", str(ROOT / "build/bytecode"),
        str(SOURCE),
    ])


def section_sizes(obj: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in run([str(TOOLCHAIN / "llvm-size"), "-A", str(obj)]).splitlines():
        match = re.match(r"^(\.\S+)\s+(\d+)\s+\d+\s*$", line)
        if match:
            result[match.group(1)] = int(match.group(2))
    return result


def relocations(obj: Path) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    current: str | None = None
    header = re.compile(r"^RELOCATION RECORDS FOR \[(.+)\]:$")
    row = re.compile(r"^[0-9a-fA-F]+\s+\S+\s+(.+?)\s*$")
    for line in run([str(TOOLCHAIN / "llvm-objdump"), "-r", str(obj)]).splitlines():
        match = header.match(line)
        if match:
            current = match.group(1)
            result.setdefault(current, [])
            continue
        match = row.match(line)
        if current is not None and match:
            result[current].append(match.group(1))
    return result


def target_base(value: str) -> str:
    return value.split("+", 1)[0]


def closure_errors(graph: dict[str, list[str]]) -> list[str]:
    errors: list[str] = []
    transports = (
        "c2_overlay_call", "c2_overlay_call_range",
        "c2_facade_overlay_call_family", "vm_runtime_overlay_exec",
        "vm_runtime_overlay_exec_family", "vm_runtime_overlay_transaction_begin",
        "vm_runtime_overlay_transaction_end",
    )
    for source, targets in graph.items():
        if not source.startswith(".lisp65_rt_"):
            continue
        for value in targets:
            target = target_base(value)
            if target.startswith(".lisp65_rt_") and target != source:
                errors.append(f"overlay-to-overlay:{source}->{target}")
            if any(target == name or target.startswith(name + ".")
                   for name in transports):
                errors.append(f"overlay-to-transport:{source}->{target}")
    return sorted(errors)


def closure_selftest() -> dict[str, str]:
    good = {
        ".lisp65_rt_a": [".lisp65_rt_a+0x10", "plain_helper"],
        ".text.driver": [".lisp65_rt_a", "c2_overlay_call"],
    }
    require(not closure_errors(good), "valid closure rejected")
    mutations = {
        "phase-calls-phase": {".lisp65_rt_a": [".lisp65_rt_b"]},
        "phase-calls-single-transport": {".lisp65_rt_a": ["c2_overlay_call"]},
        "phase-calls-range-transport": {".lisp65_rt_a": ["c2_overlay_call_range"]},
        "phase-calls-runtime-transport": {
            ".lisp65_rt_a": ["vm_runtime_overlay_exec_family"]},
    }
    for name, graph in mutations.items():
        require(closure_errors(graph), f"closure mutation accepted: {name}")
    return {name: "rejected" for name in mutations} | {
        "same-section-local-edge": "accepted",
        "resident-driver-to-overlay": "accepted",
    }


def driver_gate() -> dict[str, Any]:
    source = SOURCE.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")
    validate_start = source.index('C2_APPEND_SECTION("journal_validate")')
    reconstruct_start = source.index('C2_APPEND_SECTION("journal_reconstruct")',
                                     validate_start)
    prepare_start = source.index('C2_APPEND_SECTION("rollback_prepare")',
                                 reconstruct_start)
    validate = source[validate_start:reconstruct_start]
    reconstruct = source[reconstruct_start:prepare_start]
    begin_start = source.rfind(
        "static C2_KERNAL_RESIDENT uint8_t c2_append_begin")
    rollback_start = source.index("static uint8_t c2_append_rollback", begin_start)
    abort_start = source.index(
        "static __attribute__((noinline)) uint8_t c2_abort_driver", rollback_start)
    cleanup_start = source.index("uint8_t c2_product_abort_cleanup", abort_start)
    begin = source[begin_start:rollback_start]
    rollback = source[rollback_start:abort_start]
    abort = source[abort_start:cleanup_start]
    rows = {
        "single_snapshot_read": (
            validate.count("c2_stream_c2d_read(C2D_UNWIND_BASE") == 1),
        "reconstruct_has_no_bank5_reread": "c2_stream_c2d_read" not in reconstruct,
        "snapshot_is_phase_scratch_union": all(token in source for token in (
            "uint8_t journal_snapshot[96]", "b = w->journal_snapshot")),
        "validate_marker_precedes_reconstruct": all(token in abort for token in (
            "LISP65_C2_APPEND_JOURNAL_VALIDATE_SLOT",
            "LISP65_C2_APPEND_JOURNAL_RECONSTRUCT_SLOT")),
        "success_clears_journal_last": (
            "c2_overlay_call(LISP65_C2_APPEND_JOURNAL_CLEAR_SLOT" in begin),
        "failure_uses_named_rollback_without_diagnostic_terminal": (
            "v5_fail:" in begin
            and "if (!c2_append_run_rollback_plan(&c2aw))" in begin
            and "C2AW_FAILURE" not in begin),
        "normal_pop_front_prepare_write_rollback": all(token in rollback for token in (
            "LISP65_C2_APPEND_FRONTS_SLOT",
            "LISP65_C2_APPEND_ROLLBACK_PREPARE_SLOT",
            "LISP65_C2_APPEND_JOURNAL_WRITE_SLOT",
            "LISP65_C2_APPEND_ROLLBACK_UNPUBLISH_SLOT")),
        "abort_restores_active_journal_then_all_transients": (
            "for (;;)" in abort and "C2AW_JOURNAL_RESULT(&c2aw)" in abort),
        "resident_range_driver_is_only_phase_iterator": (
            source.count("static C2_KERNAL_RESIDENT uint8_t c2_overlay_call_range") == 1),
    }
    slot_pairs = (
        ("JOURNAL_WRITE", "STAGE"), ("ROLLBACK_UNPUBLISH", "ROLLBACK_FINALIZE"),
        ("ROLLBACK_FINALIZE", "JOURNAL_CLEAR"),
        ("JOURNAL_VALIDATE", "JOURNAL_RECONSTRUCT"),
    )
    for left, right in slot_pairs:
        l = re.search(rf"LISP65_C2_APPEND_{left}_SLOT\s+(\d+)u", header)
        r = re.search(rf"LISP65_C2_APPEND_{right}_SLOT\s+(\d+)u", header)
        rows[f"slot_order_{left.lower()}_{right.lower()}"] = bool(
            l and r and int(l.group(1)) + 1 == int(r.group(1)))
    failed = sorted(name for name, passed in rows.items() if not passed)
    require(not failed, f"serial driver gate red: {failed}")
    return {"status": "passed", "checks": rows}


def b2_source_gate(interrupt_obj: Path, runtime_obj: Path) -> dict[str, Any]:
    source = INTERRUPT.read_text(encoding="utf-8")
    runtime = SOURCE.read_text(encoding="utf-8")
    jump = function_body(source, "lisp_abort_jump")
    poll = function_body(source, "lisp_poll")
    irel = relocations(interrupt_obj)
    rrel = relocations(runtime_obj)
    jump_targets = irel.get(".text.lisp_abort_jump", [])
    cleanup_targets = rrel.get(".text.c2_product_abort_cleanup", [])
    rows = {
        "one_central_cleanup_before_longjmp": (
            jump.count("c2_product_abort_cleanup()") == 1
            and jump.find("c2_product_abort_cleanup()") < jump.find("longjmp(")),
        "run_stop_uses_common_abort_surface": (
            poll.count("lisp_abort_static(LISP65_ERR_STOPPED") >= 1),
        "compiled_jump_names_cleanup_once": (
            sum(target_base(value) == "c2_product_abort_cleanup"
                for value in jump_targets) == 1),
        "compiled_jump_names_longjmp_once": (
            sum(target_base(value) == "longjmp" for value in jump_targets) == 1),
        "cleanup_first_closes_overlay_transaction": (
            "vm_runtime_overlay_abort_cleanup()" in
            function_body(runtime, "c2_product_abort_cleanup")),
        "cleanup_then_runs_single_c2j_driver": (
            "return c2_abort_driver();" in
            function_body(runtime, "c2_product_abort_cleanup")),
        "compiled_cleanup_names_abort_cleanup": any(
            target_base(value) == "vm_runtime_overlay_abort_cleanup"
            for value in cleanup_targets),
    }
    failed = sorted(name for name, passed in rows.items() if not passed)
    require(not failed, f"B2 source gate red: {failed}")
    return {"status": "passed", "checks": rows,
            "jump_relocations": jump_targets,
            "cleanup_relocations": cleanup_targets}


def expect_injected(action: Callable[[], Any]) -> None:
    try:
        action()
    except MODEL.InjectedAbort:
        return
    raise GateError("expected injected RUN/STOP cutpoint")


def b2_model_gate() -> dict[str, Any]:
    seed = MODEL.Plane(MODEL.INITIAL.read_bytes())
    seed.validate()
    outer = MODEL.Spec("b2-outer", resolutions=3, roots=1)
    definition = MODEL.Spec(
        "b2-definition", resolutions=5, roots=2, export_symbol=1)
    cases: list[dict[str, str]] = []

    def passed(name: str, detail: str) -> None:
        cases.append({"name": name, "trigger": "RUN/STOP",
                      "status": "passed", "detail": detail})

    def cleanup_exact(p: MODEL.Plane, expected: MODEL.Plane,
                      name: str, detail: str) -> None:
        require(p.transaction_active, f"{name}: cutpoint did not leave transaction active")
        p.abort_cleanup()
        p.validate()
        MODEL.same(p, expected, f"{name}: C2D/Attic/export drift after RUN/STOP")
        passed(name, detail)

    for cut in ("after_journal", "after_attic", "after_records",
                "after_publish", "after_export"):
        p = seed.clone()
        expect_injected(lambda cut=cut: p.persistent_append(definition, fail_at=cut))
        cleanup_exact(p, seed, f"persistent-{cut}",
                      "in-flight persistent mutation restored byte-identically")
    for cut in ("after_journal", "after_attic", "after_records",
                "after_publish", "after_export"):
        p = seed.clone()
        p.transient_push(outer)
        expect_injected(lambda cut=cut: p.persistent_append(definition, fail_at=cut))
        cleanup_exact(p, seed, f"nested-persistent-{cut}",
                      "pending low-prefix mutation and dynamic wrapper both removed")
    for cut in ("after_journal", "after_attic", "after_records", "after_publish"):
        p = seed.clone()
        expect_injected(lambda cut=cut: p.transient_push(outer, fail_at=cut))
        cleanup_exact(p, seed, f"transient-push-{cut}",
                      "partially published wrapper fully removed")
    for cut in ("after_journal", "after_unpublish", "after_wipe"):
        p = seed.clone()
        p.transient_push(outer)
        expect_injected(lambda cut=cut: p.transient_pop(fail_at=cut))
        cleanup_exact(p, seed, f"transient-pop-{cut}",
                      "unpublish-first cleanup remains idempotent")

    reference = seed.clone()
    reference.persistent_append(definition)
    p = seed.clone()
    p.transient_push(outer)
    p.persistent_append(definition)
    p.abort_cleanup()
    p.validate()
    MODEL.same(p, reference,
               "RUN/STOP removed a committed descendant or retained its wrapper")
    passed("quiescent-wrapper-break", "wrapper removed; committed descendant preserved")

    require(len(cases) == 18 and all(case["status"] == "passed" for case in cases),
            f"B2 fixture closure drift: {len(cases)}")
    return {"status": "passed", "cases": len(cases), "rows": cases,
            "assertion": (
                "Every RUN/STOP cutpoint uses the same C2J semantic cleanup as "
                "ordinary error longjmp; C2D counts, bytes, Attic and exports "
                "are exact, while committed descendants survive.")}


def check(out: Path) -> dict[str, Any]:
    required = (SOURCE, HEADER, INTERRUPT, CONTRACT, HANDLE_CONTRACT,
                CONTRACT_RECEIPT, HANDLE_RECEIPT, PREVIOUS, MATRIX, NOTE,
                ARTIFACTS, PRODUCT_PRG, MANIFEST, MODEL.INITIAL)
    for path in required:
        require(path.is_file(), f"required input absent: {path}")
    require(sha(PRODUCT_PRG) == EXPECTED_PRODUCT_SHA, "Link-32 identity drift")
    require(sha(PREVIOUS) == EXPECTED_PREVIOUS_SHA, "authorized C2J first red drift")
    require(sha(CONTRACT_RECEIPT) == EXPECTED_CONTRACT_RECEIPT_SHA,
            "nested contract receipt drift")
    require(sha(HANDLE_RECEIPT) == EXPECTED_HANDLE_RECEIPT_SHA,
            "transient-handle receipt drift")

    runtime_obj, interrupt_obj, commands = compile_objects(out)
    sizes = section_sizes(runtime_obj)
    measured = {name: sizes.get(f".lisp65_rt_c2append_{name}") for name in PHASES}
    require(all(isinstance(value, int) and 0 < value <= CAP
                for value in measured.values()),
            "runtime-slice cap red")
    for name in EXPECTED_RUNTIME:
        require(isinstance(sizes.get(name), int) and sizes[name] > 0,
                f"required resident/source-object section absent: {name}")

    graph = relocations(runtime_obj)
    overlay_graph = {section: targets for section, targets in graph.items()
                     if section.startswith(".lisp65_rt_c2append_")}
    require(set(overlay_graph) == {
        f".lisp65_rt_c2append_{name}" for name in PHASES},
        "overlay relocation inventory drift")
    errors = closure_errors(overlay_graph)
    require(not errors, f"overlay closure red: {errors}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    old = {item["section"]: item["file_size"] for item in manifest["slices"]}
    old_pair = (align(old[".lisp65_rt_c2append_capacity"])
                + align(old[".lisp65_rt_c2append_rollback"]))
    projected_names = (
        "roots", "fronts", "reserve_transient", "reserve_persistent",
        "journal_write", "journal_validate", "journal_reconstruct",
        "rollback_prepare", "journal_clear", "rollback_unpublish",
        "rollback_finalize",
    )
    new_group = sum(align(measured[name]) for name in projected_names)
    projected = manifest["storage"]["size"] + new_group - old_pair + 768
    require(projected <= 65536,
            f"historical-profile session-store projection red: {projected}")

    predecessor_sizes = section_sizes(
        ROOT / "build/c2.2/c2j-three-way-capacity-first-red/c2-c2j-three-way.o")
    resident_delta = (sizes[".lisp65_c2_kernal_window.c2_resident"]
                      - predecessor_sizes[".lisp65_c2_kernal_window.c2_resident"])
    bank0_object_delta = (
        sizes[".text.c2_product_install"]
        + sizes[".text.c2_product_abort_cleanup"]
        + sizes[".text.c2_abort_driver"]
        - predecessor_sizes[".text.c2_product_install"])
    return {
        "status": "passed-prelink-product-link-not-run",
        "runtime_object": runtime_obj,
        "interrupt_object": interrupt_obj,
        "commands": commands,
        "sizes": sizes,
        "slices": {name: {"bytes": measured[name],
                           "headroom_bytes": CAP - measured[name]}
                   for name in PHASES},
        "driver": driver_gate(),
        "overlay_closure": {
            "status": "passed", "phases": len(overlay_graph),
            "forbidden_edges": errors,
            "mutation_matrix": closure_selftest(),
            "graph": overlay_graph,
        },
        "b2_source": b2_source_gate(interrupt_obj, runtime_obj),
        "b2_model": b2_model_gate(),
        "capacity": {
            "historical_exact_size_snapshot_matches":
                measured == EXPECTED_SIZES,
            "session_store_projected_bytes": projected,
            "session_store_projected_headroom_bytes": 65536 - projected,
            "session_slice_count_projected": len(manifest["slices"]) - 2 + 11,
            "e000_target_object_delta_bytes": resident_delta,
            "bank0_target_object_delta_bytes": bank0_object_delta,
            "declared_bss_delta_bytes": 0,
            "compiler_static_stack_source_object_bytes": sizes.get(
                ".noinit..Lstatic_stack", 0),
            "compiler_static_stack_claim": (
                "diagnostic only; llvm-mos LTO assigns the whole-program static "
                "stack. The product link must measure the actual BSS wall."),
            "resident_island_delta_bytes": 0,
            "e000_policy": "closed; measured source-object credit, no new tenant",
            "qualification_scope": (
                "Current source under the historical Link-32 profile is "
                "checked for section presence, slice cap, closure and B2 "
                "semantics. Historical exact byte expectations remain sealed "
                "in the original receipt; current product walls are owned by "
                "the Whole-Program-LTO gate."),
        },
    }


def emit(result: dict[str, Any]) -> None:
    replacing = os.environ.get("LISP65_REPLACE_UNSEALED_PROBE") == "1"
    require(not RECEIPT.exists() or replacing,
            f"receipt already exists: {RECEIPT}")
    bindings = (SOURCE, HEADER, INTERRUPT, CONTRACT, HANDLE_CONTRACT,
                CONTRACT_RECEIPT, HANDLE_RECEIPT, PREVIOUS, MATRIX, NOTE,
                ARTIFACTS, PRODUCT_PRG, MANIFEST, MODEL.INITIAL, Path(__file__))
    generated = {
        "section-sizes.json": result["slices"],
        "overlay-closure.json": result["overlay_closure"],
        "b2-run-stop-fixture.json": result["b2_model"],
        "serial-driver-gate.json": result["driver"],
    }
    artifacts: dict[str, Any] = {}
    for name, value in generated.items():
        path = OUT / name
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
        artifacts[name] = bind(path)
    report = {
        "format": "lisp65-c2-nested-append-v5-prelink-receipt-v1",
        "recorded_on": "2026-07-20",
        "status": result["status"],
        "scope": {"target_relocatable_compiles": 2,
                  "product_closure_links": 0, "hardware_runs": 0,
                  "rollback_product_modified": False},
        "slice_capacity": result["slices"],
        "serial_driver": result["driver"],
        "overlay_closure": result["overlay_closure"],
        "b2_run_stop_source": result["b2_source"],
        "b2_run_stop_fixture": result["b2_model"],
        "capacity_projection_not_product_authorization": result["capacity"],
        "bindings": {path.relative_to(ROOT).as_posix(): bind(path)
                     for path in bindings} | {
                         "target_runtime_object": bind(result["runtime_object"]),
                         "target_interrupt_object": bind(result["interrupt_object"]),
                         "target_compiler": bind(TOOLCHAIN / "mos-mega65-clang"),
                     },
        "generated_artifacts": artifacts,
        "compiler_commands": result["commands"],
        "next_gate": (
            "A separately authorized successor product link must rerun every "
            "structural/capacity gate and measure actual whole-program BSS."),
        "claim_limit": (
            "Prelink target-object, static-closure and host state-machine proof "
            "only. No successor product identity, hardware behavior, latency, "
            "promotion or C2.2 acceptance is claimed."),
    }
    RECEIPT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    for path in (result["runtime_object"], result["interrupt_object"],
                 *[OUT / name for name in generated], RECEIPT):
        os.chmod(path, 0o444)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        closure_selftest()
        result = b2_model_gate()
        print(f"c2-nested-append-v5 selftest: PASS b2={result['cases']}/18")
        return 0
    if args.emit_receipt:
        replacing = os.environ.get("LISP65_REPLACE_UNSEALED_PROBE") == "1"
        require(not OUT.exists() or replacing, f"output already exists: {OUT}")
        if replacing and OUT.exists():
            for path in OUT.iterdir():
                if path.is_file():
                    os.chmod(path, 0o644)
            if RECEIPT.exists():
                os.chmod(RECEIPT, 0o644)
        OUT.mkdir(parents=True, exist_ok=replacing)
        try:
            result = check(OUT)
            emit(result)
        except Exception:
            if not replacing:
                shutil.rmtree(OUT, ignore_errors=True)
            raise
        print("c2-nested-append-v5 prelink: PASS slices=20/20 "
              "closure=20/20 b2=18/18 product-links=0")
        print(f"c2-nested-append-v5 prelink: receipt_sha256={sha(RECEIPT)}")
        return 0
    with tempfile.TemporaryDirectory(prefix="lisp65-c2-v5-prelink-") as tmp:
        result = check(Path(tmp))
    print("c2-nested-append-v5 check: PASS slices=20/20 "
          f"b2={result['b2_model']['cases']}/18 product-links=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
