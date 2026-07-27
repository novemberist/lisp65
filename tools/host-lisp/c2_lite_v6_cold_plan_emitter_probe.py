#!/usr/bin/env python3
"""Authorized C2-lite cold-plan/one-entry-emitter WPLTO probe.

The probe closes the semantic First Red found after cold eviction.  It proves
the shared C2D-v6 entry-row routine, captures a source-free export plan before
the dynamic header/READY boundary, runs the permanent mutations, and consumes
exactly one nonpromotable Whole-Program-LTO measurement.  It never creates a
product link or runs hardware.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link33_bss_triage_product_link as BASE  # noqa: E402
import c2_lite_v6_cold_eviction_probe as COLD  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402


OUT = ROOT / "build/c2-lite/v6-cold-plan-emitter-wplto-probe"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-cold-plan-emitter-wplto-probe-receipt.json")
SEMANTIC_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-cold-eviction-semantic-first-red-receipt.json")
CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
ADDENDUM = ROOT / "docs/planning/c2-lite-execution-contract-addendum.md"
RUNTIME = ROOT / "src/c2_product_runtime.c"
RUNTIME_HEADER = ROOT / "src/c2_product_runtime.h"
ENTRY_HEADER = ROOT / "src/c2d_v6_entry.h"
ENTRY_WRAPPER = ROOT / "scripts/c2d-v6-entry-host.c"


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def function(source: str, name: str) -> str:
    try:
        return V6.c_function_definition(source, name)
    except RuntimeError as error:
        raise ProbeError(str(error)) from error


def source_contract_gate() -> dict[str, Any]:
    runtime = RUNTIME.read_text(encoding="utf-8")
    header = RUNTIME_HEADER.read_text(encoding="utf-8")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    plan = function(runtime, "c2_append_publish_plan_phase")
    names = function(runtime, "c2_append_publish_names_phase")
    cells = function(runtime, "c2_append_publish_cells_phase")
    boot = function(runtime, "c2_product_boot")
    sliced_append = runtime[runtime.index(
        '#else\n\nC2_APPEND_SECTION("envelope")'):]
    append_start = sliced_append.index(
        "static C2_KERNAL_RESIDENT uint8_t c2_append_begin")
    append_end = sliced_append.index("\nv5_fail:", append_start)
    append = sliced_append[append_start:append_end]
    entries = function(runtime, "c2_append_entries_phase")
    image = function(runtime, "c2_append_image_phase")

    def no_source_after_capture(body: str) -> bool:
        return ("c2_stream_shelf_read" not in body
                and "c2_source_read" not in body
                and "c2_u24(row + 23)" not in body
                and "c2_u24(image + 23)" not in body)

    checks = {
        "contract_names_one_entry_emitter":
            contract["entry_row_emission"]["single_source"]
            == "src/c2d_v6_entry.h::c2d_v6_emit_entry_row",
        "plan_precedes_header_slots":
            "LISP65_C2_APPEND_PUBLISH_PLAN_SLOT 37u" in header
            and "LISP65_C2_APPEND_HEADER_SLOT 38u" in header
            and "LISP65_C2_APPEND_PUBLISH_NAMES_SLOT 39u" in header
            and "LISP65_C2_APPEND_PUBLISH_CELLS_SLOT 40u" in header,
        "cold_plan_reads_verified_source":
            plan.count("c2_stream_shelf_read") >= 3
            and "c2_stream_name_value" in plan,
        "plan_is_source_free_after_capture":
            "c2_record_u16(row, symbol);" in plan
            and "sym_function((obj)symbol)" in plan
            and "c2_record_u16(row + 4" in plan,
        "post_header_names_are_source_free": no_source_after_capture(names),
        "post_header_cells_are_source_free": no_source_after_capture(cells),
        "ready_is_last":
            boot.index("c2_publish_exports_from(0)")
            < boot.index("c2_ready = 1"),
        "dynamic_order_is_plan_header_exports":
            "LISP65_C2_APPEND_PUBLISH_PLAN_SLOT" in append
            and "LISP65_C2_APPEND_PUBLISH_CELLS_SLOT" in append,
        "dynamic_row_uses_shared_emitter_once":
            entries.count("c2d_v6_emit_entry_row") == 1
            and "entry[7]" in entries
            and "C2AW_CHIP_CODE_BASE" in entries,
        "published_image_has_no_source_locator":
            "row[23] = 0u; row[24] = 0u; row[25] = 0u;" in image
            and "row[26] = 0u; row[27] = 0u;" in image,
    }
    require(all(checks.values()), "source contract red: "
            + str([name for name, ok in checks.items() if not ok]))

    # Pin both directions: a post-capture source read and a dynamic row field
    # reconstructed outside the shared emitter must each make the gate red.
    mutated_names = names.replace(
        "return C2_STREAM_OK;",
        "(void)c2_stream_shelf_read(0u, row, 1u); return C2_STREAM_OK;", 1)
    mutated_entries = entries.replace(
        "c2d_v6_emit_entry_row(", "c2d_v6_emit_entry_row_rebuilt(", 1)
    mutated_boot = boot.replace(
        "if (!c2_publish_exports_from(0)) {\n"
        "        c2_ready = 0; return 0;\n"
        "    }",
        "c2_ready = 1;\n"
        "    if (!c2_publish_exports_from(0)) {\n"
        "        c2_ready = 0; return 0;\n"
        "    }",
        1,
    )
    require(mutated_boot != boot, "READY-order mutation did not apply")
    mutations = {
        "forced-post-ready-attic-read-rejected":
            not no_source_after_capture(mutated_names),
        "dynamic-row-reconstruction-rejected":
            mutated_entries.count("c2d_v6_emit_entry_row(") == 0,
        "ready-before-exports-rejected":
            not (mutated_boot.index("c2_publish_exports_from(0)")
                 < mutated_boot.index("c2_ready = 1")),
    }
    require(all(mutations.values()), "source mutation fixture red")
    return {"status": "passed", "checks": checks,
            "negative_fixtures": mutations,
            "entry_emitter": {"header": bind(ENTRY_HEADER),
                              "host_wrapper": bind(ENTRY_WRAPPER)}}


def publication_model_gate() -> dict[str, Any]:
    source_reads = 0
    ready = False
    events: list[str] = []
    plan: list[tuple[int, int, int]] = []
    old = [0x2000 + i * 2 for i in range(32)]
    current = list(old)

    def cold_read() -> None:
        nonlocal source_reads
        require(not ready, "model accepted cold-source read after READY")
        source_reads += 1

    for i in range(19):
        cold_read()
        plan.append((i, current[i], 0xC000 + i))
    events.append("cold-plan-complete")
    events.append("header-published")
    reads_before_exports = source_reads
    for symbol, previous, target in plan:
        require(previous == current[symbol], "captured old value drift")
        current[symbol] = target
    events.append("exports-published")
    ready = True; events.append("READY")
    require(source_reads == reads_before_exports
            and events == ["cold-plan-complete", "header-published",
                           "exports-published", "READY"],
            "publish-last model drift")

    forced_rejected = False
    try:
        cold_read()
    except ProbeError:
        forced_rejected = True
    require(forced_rejected, "forced source read after READY was accepted")
    return {"status": "passed", "events": events,
            "captured_rows": len(plan), "cold_source_reads": source_reads,
            "post_plan_source_reads": source_reads - reads_before_exports,
            "forced_post_ready_source_read_rejected": forced_rejected}


def shared_entry_emitter_gate() -> tuple[dict[str, Any], dict[str, Any]]:
    original_out = V6.OUT
    original_fn = V6._ENTRY_EMITTER
    original_path = V6._ENTRY_EMITTER_PATH
    V6.OUT = OUT / "host-v6"
    V6._ENTRY_EMITTER = None; V6._ENTRY_EMITTER_PATH = None
    try:
        host = V6.host_semantics()
        c2d_path = V6.OUT / "initial.c2d-v6.bin"
        c2d = c2d_path.read_bytes()
        entries = int.from_bytes(c2d[16:18], "little")
        for ordinal in range(entries):
            at = V6.C2D_ENTRIES_OFFSET + ordinal * V6.C2D_ENTRY_BYTES
            row = c2d[at:at + V6.C2D_ENTRY_BYTES]
            rebuilt = V6.entry_v6(
                row[0], row[1], int.from_bytes(row[2:4], "little"),
                int.from_bytes(row[4:6], "little"),
                int.from_bytes(row[6:8], "little"),
                int.from_bytes(row[8:10], "little"))
            require(rebuilt == row,
                    f"static row differs from shared emitter: {ordinal}")
        helper = V6._ENTRY_EMITTER_PATH
        require(helper is not None and helper.is_file(),
                "host entry-emitter artifact absent")
        report = {
            "status": "passed",
            "single_routine": "c2d_v6_emit_entry_row",
            "static_rows_byte_identical": entries,
            "dynamic_target_callsite_count": 1,
            "host_shared_object": bind(helper),
            "static_c2d": bind(c2d_path),
            "negative_rows": ["zero-length", "image-64", "Bank-2-wrap",
                              "resolution-wrap", "zero-generation"],
        }
        return host, report
    finally:
        V6.OUT = original_out
        V6._ENTRY_EMITTER = original_fn
        V6._ENTRY_EMITTER_PATH = original_path


def run_one_wplto() -> tuple[dict[str, Any], Path, Path]:
    original_configure = BASE.configure
    original_features = BASE.FEATURES
    original_out = V6.OUT

    def configure() -> None:
        original_configure()
        COLD.configure_cold_eviction()

    BASE.configure = configure
    BASE.FEATURES = (*original_features, "LISP65_C2_PHASE11_SPLIT",
                     "LISP65_C2_LITE_COLD_EVICTION")
    V6.OUT = OUT
    try:
        result = V6.full_product_wplto()
    finally:
        BASE.configure = original_configure
        BASE.FEATURES = original_features
        V6.OUT = original_out
    target = OUT / "full-product-wplto/c2-lite-v6-full-seed.prg"
    elf = Path(str(target) + ".elf")
    require(target.is_file() and elf.is_file(), "WPLTO artifacts absent")
    return result, target, elf


def post_wplto_semantic_gates(target: Path, elf: Path) -> dict[str, Any]:
    generated = target.parent / "generated-product-sources/c2_product_runtime.c"
    source = generated.read_text(encoding="utf-8")
    names = function(source, "c2_append_publish_names_phase")
    cells = function(source, "c2_append_publish_cells_phase")
    hot = function(source, "c2_product_entry_read")
    checks = {
        "post-header-names-no-source":
            "c2_stream_shelf_read" not in names and "c2_source_read" not in names,
        "post-header-cells-no-source":
            "c2_stream_shelf_read" not in cells and "c2_source_read" not in cells,
        "hot-entry-no-source-or-locator":
            "c2_stream_shelf_read" not in hot and "c2_source_read" not in hot
            and "+ 23" not in hot,
        "shared-emitter-call-survived-projection":
            function(source, "c2_append_entries_phase").count(
                "c2d_v6_emit_entry_row") == 1,
    }
    require(all(checks.values()), "post-WPLTO semantic closure red: "
            + str([name for name, ok in checks.items() if not ok]))
    return {"status": "passed", "checks": checks,
            "generated_runtime": bind(generated), "elf": bind(elf)}


def protect() -> None:
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    if RECEIPT.is_file():
        os.chmod(RECEIPT, 0o444)


def record_first_red(error: BaseException) -> None:
    evidence = []
    if OUT.exists():
        for path in sorted(OUT.rglob("*")):
            if path.is_file():
                evidence.append(bind(path))
    value = {
        "format": "lisp65-c2-lite-v6-cold-plan-emitter-wplto-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: cold-plan/emitter contract or WPLTO probe",
        "failure": str(error),
        "scope": {"whole_program_lto_attempts": int((OUT / "full-product-wplto").exists()),
                  "product_links": 0, "hardware_runs": 0,
                  "promotable": False},
        "evidence": evidence,
        "rollback_line": {"product": "Link 35", "status": "untouched"},
        "next_gate": "Class-C review; no retry or product link",
    }
    write_json(RECEIPT, value); protect()


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "cold-plan/emitter probe is one-shot and already exists")
    require(SEMANTIC_FIRST_RED.is_file(), "semantic First Red authority absent")
    OUT.mkdir(parents=True)
    source = source_contract_gate()
    publication = publication_model_gate()
    host, emitter = shared_entry_emitter_gate()
    write_json(OUT / "source-contract-gate.json", source)
    write_json(OUT / "publication-model-gate.json", publication)
    write_json(OUT / "shared-entry-emitter-gate.json", emitter)

    wplto, target, elf = run_one_wplto()
    structural = COLD.structural_gates(target, elf)
    eviction = COLD.eviction_and_anchor_gate(wplto, elf)
    semantic = post_wplto_semantic_gates(target, elf)
    value = {
        "format": "lisp65-c2-lite-v6-cold-plan-emitter-wplto-probe-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-contract-fixtures-and-one-product-shaped-wplto",
        "scope": {"whole_program_lto_probes": 1, "product_links": 0,
                  "hardware_runs": 0, "promotable": False},
        "authority": {"semantic_first_red": bind(SEMANTIC_FIRST_RED),
                      "contract": bind(CONTRACT), "addendum": bind(ADDENDUM)},
        "source_contract": source,
        "publication_model": publication,
        "shared_entry_emitter": emitter,
        "host_v6_semantics": host,
        "whole_program_lto": wplto,
        "cold_eviction": eviction,
        "fresh_structural_gates": structural,
        "post_wplto_semantic_gates": semantic,
        "artifacts": {"measurement_prg": bind(target),
                      "measurement_elf": bind(elf),
                      "measurement_map": bind(Path(str(target) + ".map"))},
        "claim_limit": (
            "Contract, host semantics and one nonpromotable product-shaped "
            "WPLTO only. No product link, hardware, performance, promotion "
            "or acceptance claim."),
        "rollback_line": {"product": "Link 35", "status": "untouched"},
        "next_gate": "Class-C review before the first C2-lite product link",
    }
    write_json(OUT / "cold-plan-emitter-wplto-probe.json", value)
    value["probe_report"] = bind(OUT / "cold-plan-emitter-wplto-probe.json")
    write_json(RECEIPT, value); protect(); return value


def main() -> int:
    try:
        value = build()
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            RuntimeError) as error:
        if OUT.exists() and not RECEIPT.exists():
            record_first_red(error)
        print("c2-lite-v6-cold-plan-emitter-probe: FIRST RED " + str(error))
        return 2
    walls = value["whole_program_lto"]["walls"]
    print("c2-lite-v6-cold-plan-emitter-probe: PASS "
          f"e000={walls['e000_headroom_bytes']} "
          f"text={walls['bank0_text_headroom_bytes']} "
          f"slices={value['whole_program_lto']['runtime_slices']['count']} "
          "product-link=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
