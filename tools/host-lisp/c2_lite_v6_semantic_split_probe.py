#!/usr/bin/env python3
"""One authorized bundled C2-lite v6 semantic-split WPLTO probe.

Five previously over-cap phases are divided at marker-only ownership
boundaries.  The probe runs their transition mutations, one product-shaped
Whole-Program-LTO measurement, the complete structural gate set and the full
Bank-3 family packing.  It never creates a product link or runs hardware.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link33_bss_triage_product_link as BASE  # noqa: E402
import c2_lite_root_surrogate as ROOT_GATE  # noqa: E402
import c2_lite_v6_cold_eviction_probe as COLD  # noqa: E402
import c2_lite_v6_cold_plan_emitter_probe as PLAN  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


OUT = ROOT / "build/c2-lite/v6-semantic-splits-wplto-probe-class-a-replay"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-semantic-splits-wplto-class-a-replay-receipt.json")
CAPACITY_AUTHORITY = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-cold-plan-emitter-wplto-probe-receipt.json")
HARNESS_FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-semantic-splits-wplto-probe-receipt.json")
CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
ADDENDUM = ROOT / "docs/planning/c2-lite-execution-contract-addendum.md"
RUNTIME = ROOT / "src/c2_product_runtime.c"
HEADER = ROOT / "src/c2_product_runtime.h"
DECODER = ROOT / "scripts/c2-stream-decoder.c"
CUTPOINT = ROOT / "scripts/c2-lite-v6-semantic-split-cutpoints-main.c"
CAP = 1792
E000_FLOOR = 115


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


def replace_slice(rows: list[tuple[str, str]], old: str,
                  replacements: tuple[tuple[str, str], ...]) -> None:
    indices = [i for i, (name, _entry) in enumerate(rows) if name == old]
    require(len(indices) == 1, f"slice replacement anchor drift: {old}")
    at = indices[0]
    rows[at:at + 1] = replacements


def configure_semantic_splits() -> None:
    """Apply the five cuts as one in-memory product profile."""
    COLD.configure_cold_eviction()

    old_source = ROOT / "scripts/c2-stream-phase-05.c"
    index = PRODUCT.C2_PHASE_SOURCES.index(old_source)
    PRODUCT.C2_PHASE_SOURCES[index:index + 1] = [
        ROOT / "scripts/c2-stream-phase-05a.c",
        ROOT / "scripts/c2-stream-phase-05b.c",
    ]
    decoder = list(PRODUCT.C2_DECODER_SLICES)
    replace_slice(decoder, "05", (
        ("05a", "c2_stream_phase_05a"),
        ("05b", "c2_stream_phase_05b"),
    ))
    PRODUCT.C2_DECODER_SLICES = decoder
    PRODUCT.BOOT_DECODER_SLICES = decoder[:6]
    PRODUCT.SESSION_DECODER_SLICES = decoder[6:]
    PRODUCT.SESSION_EMITTER_SLOT_BASE = 2 + len(
        PRODUCT.SESSION_DECODER_SLICES)
    PRODUCT.SESSION_APPEND_SLOT_BASE = (
        PRODUCT.SESSION_EMITTER_SLOT_BASE + len(PRODUCT.C2_EMITTER_SLICES))

    append = list(PRODUCT.C2_APPEND_SLICES)
    replace_slice(append, "reserve_transient", (
        ("reserve_transient_bounds",
         "c2_append_reserve_transient_bounds_phase"),
        ("reserve_transient_code",
         "c2_append_reserve_transient_code_phase"),
    ))
    replace_slice(append, "reserve_persistent", (
        ("reserve_persistent_bounds",
         "c2_append_reserve_persistent_bounds_phase"),
        ("reserve_persistent_code",
         "c2_append_reserve_persistent_code_phase"),
    ))
    replace_slice(append, "stage", (
        ("stage_copy", "c2_append_stage_copy_phase"),
        ("stage_plane", "c2_append_stage_plane_phase"),
    ))
    replace_slice(append, "publish_plan", (
        ("publish_plan_scan", "c2_append_publish_plan_scan_phase"),
        ("publish_plan_resolve", "c2_append_publish_plan_resolve_phase"),
    ))
    PRODUCT.configure_append_slices(append)

    require(len(PRODUCT.C2_DECODER_SLICES) == 19
            and len(PRODUCT.SESSION_DECODER_SLICES) == 13
            and len(PRODUCT.C2_APPEND_SLICES) == 26
            and PRODUCT.SESSION_EMITTER_SLOT_BASE == 15
            and PRODUCT.SESSION_APPEND_SLOT_BASE == 23
            and PRODUCT.SESSION_SERVICE_SLOT_BASE == 49
            and len(PRODUCT.SESSION_SLICE_SPECS) == 53
            and PRODUCT.UNIQUE_SLICE_COUNT == 60,
            "semantic-split runtime-family ABI drift")


def source_contract_gate() -> dict[str, Any]:
    runtime = RUNTIME.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")
    decoder = DECODER.read_text(encoding="utf-8")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    functions = (
        "c2_append_reserve_transient_bounds_phase",
        "c2_append_reserve_transient_code_phase",
        "c2_append_reserve_persistent_bounds_phase",
        "c2_append_reserve_persistent_code_phase",
        "c2_append_stage_copy_phase",
        "c2_append_stage_plane_phase",
        "c2_append_publish_plan_scan_phase",
        "c2_append_publish_plan_resolve_phase",
    )
    bodies = {name: V6.c_function_definition(runtime, name)
              for name in functions}
    checks = {
        "contract_cap_unchanged":
            contract["semantic_slice_splits"]["runtime_slice_cap_bytes"] == CAP
            and contract["semantic_slice_splits"]["cap_change_authorized"] is False,
        "decoder_marker_only_handoff":
            "c->reserved = 0x5au" in decoder
            and "c->reserved != 0x5au" in decoder
            and "c->reserved = 0u; c->phase = 6u" in decoder,
        "append_marker_only_handoffs":
            all(token in runtime for token in (
                "C2AW_RESERVE_MARK(w)", "C2AW_STAGE_MARK(w)",
                "C2AW_PLAN_MARK(w)", "C2_EXPORT_SCAN_MARK")),
        "no_split_phase_calls_overlay":
            all("c2_overlay_call" not in body for body in bodies.values()),
        "serial_driver_calls_complete_ranges":
            "LISP65_C2_APPEND_RESERVE_TRANSIENT_BOUNDS_SLOT" in runtime
            and "LISP65_C2_APPEND_RESERVE_TRANSIENT_CODE_SLOT" in runtime
            and "LISP65_C2_APPEND_RESERVE_PERSISTENT_BOUNDS_SLOT" in runtime
            and "LISP65_C2_APPEND_RESERVE_PERSISTENT_CODE_SLOT" in runtime
            and "LISP65_C2_APPEND_PUBLISH_PLAN_SCAN_SLOT" in runtime,
        "slot_abi_is_complete":
            all(token in header for token in (
                "LISP65_C2_PHASE_05A_SLOT 3u",
                "LISP65_C2_PHASE_05B_SLOT 4u",
                "LISP65_C2_EMIT_PREPARE_SLOT 15u",
                "LISP65_C2_APPEND_ENVELOPE_SLOT 23u",
                "LISP65_C2_APPEND_RESERVE_TRANSIENT_BOUNDS_SLOT 28u",
                "LISP65_C2_APPEND_RESERVE_PERSISTENT_CODE_SLOT 31u",
                "LISP65_C2_APPEND_STAGE_COPY_SLOT 37u",
                "LISP65_C2_APPEND_STAGE_PLANE_SLOT 38u",
                "LISP65_C2_APPEND_PUBLISH_PLAN_SCAN_SLOT 41u",
                "LISP65_C2_APPEND_PUBLISH_PLAN_RESOLVE_SLOT 42u",
                "LISP65_C2_APPEND_ABORT_CONTROL_SLOT 48u")),
        "zero_added_handoff_fields":
            "uint8_t record[32];" in runtime
            and "uint8_t meta[24];" in runtime
            and "record[20]" in runtime and "record[21]" in runtime
            and "record[22]" in runtime,
    }
    require(all(checks.values()), "semantic-split source contract red: "
            + str([name for name, ok in checks.items() if not ok]))
    return {"status": "passed", "checks": checks,
            "split_function_count": len(functions),
            "handoff_added_bytes": 0, "handoff_pointer_count": 0}


def cutpoint_gate() -> dict[str, Any]:
    binary = OUT / "c2-lite-v6-semantic-split-cutpoints"
    command = ["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
               "-fsanitize=address,undefined", str(CUTPOINT), "-o", str(binary)]
    subprocess.run(command, cwd=ROOT, check=True)
    run = subprocess.run([str(binary)], cwd=ROOT, check=True,
                         capture_output=True, text=True)
    expected = ("c2-lite-v6-semantic-split-cutpoints: PASS chains=5 "
                "negatives=15 handoff-bytes=0 handoff-pointers=0")
    require(run.stdout.strip() == expected, "cutpoint fixture output drift")
    stdout = OUT / "semantic-split-cutpoints.stdout.txt"
    stdout.write_text(run.stdout, encoding="utf-8")
    return {"status": "passed", "chains": 5, "negative_mutations": 15,
            "asan": "passed", "ubsan": "passed",
            "handoff_added_bytes": 0, "handoff_pointer_count": 0,
            "binary": bind(binary), "stdout": bind(stdout)}


def shared_semantics_gate() -> dict[str, Any]:
    original = PLAN.OUT
    PLAN.OUT = OUT / "shared-semantics"
    try:
        publication = PLAN.publication_model_gate()
        host, emitter = PLAN.shared_entry_emitter_gate()
    finally:
        PLAN.OUT = original
    protocol = COLD.publication_protocol_gate()
    return {"status": "passed", "publication": publication,
            "entry_emitter": emitter, "host_v6": host,
            "maximum_plan_protocol": protocol}


def run_one_wplto() -> tuple[dict[str, Any], Path, Path]:
    original_configure = BASE.configure
    original_features = BASE.FEATURES
    original_out = V6.OUT

    def configure() -> None:
        original_configure()
        configure_semantic_splits()

    BASE.configure = configure
    BASE.FEATURES = (*original_features,
                     "LISP65_C2_PHASE11_SPLIT",
                     "LISP65_C2_LITE_COLD_EVICTION",
                     "LISP65_C2_LITE_V6_SEMANTIC_SPLITS")
    V6.OUT = OUT
    try:
        result = V6.full_product_wplto()
    finally:
        BASE.configure = original_configure
        BASE.FEATURES = original_features
        V6.OUT = original_out
    target = OUT / "full-product-wplto/c2-lite-v6-full-seed.prg"
    elf = Path(str(target) + ".elf")
    require(target.is_file() and elf.is_file(), "green WPLTO artifacts absent")
    return result, target, elf


def split_capacity_gate(wplto: dict[str, Any], elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=PRODUCT.TOOLCHAIN / "llvm-readobj")
    expected = (
        ".lisp65_rt_c2d_05a", ".lisp65_rt_c2d_05b",
        ".lisp65_rt_c2append_reserve_transient_bounds",
        ".lisp65_rt_c2append_reserve_transient_code",
        ".lisp65_rt_c2append_reserve_persistent_bounds",
        ".lisp65_rt_c2append_reserve_persistent_code",
        ".lisp65_rt_c2append_stage_copy",
        ".lisp65_rt_c2append_stage_plane",
        ".lisp65_rt_c2append_publish_plan_scan",
        ".lisp65_rt_c2append_publish_plan_resolve",
    )
    sizes = {name: truth.section(name).bytes for name in expected}
    require(all(0 < size <= CAP for size in sizes.values()),
            "semantic successor outside cap: "
            + str({name: size for name, size in sizes.items()
                   if size <= 0 or size > CAP}))
    retired = (
        ".lisp65_rt_c2d_05",
        ".lisp65_rt_c2append_reserve_transient",
        ".lisp65_rt_c2append_reserve_persistent",
        ".lisp65_rt_c2append_stage",
        ".lisp65_rt_c2append_publish_plan",
    )
    present = {name: name in truth.sections_by_name for name in retired}
    require(not any(present.values()), "unsplit predecessor survived: " + str(present))
    session = wplto["successor_bank3_pack"]["session"]
    require(wplto["runtime_slices"]["count"] == 60
            and session["headroom_bytes"] >= 0,
            "split aggregate accounting red")
    return {
        "status": "passed", "cap_bytes": CAP,
        "successor_sizes": sizes,
        "minimum_successor_headroom_bytes": CAP - max(sizes.values()),
        "retired_sections_present": present,
        "transported_slice_count_before": 55,
        "transported_slice_count_after": 60,
        "added_catalog_records": 5,
        "session_family_bytes": session["bytes"],
        "session_family_headroom_bytes": session["headroom_bytes"],
    }


def cold_and_semantic_gate(wplto: dict[str, Any], target: Path,
                           elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=PRODUCT.TOOLCHAIN / "llvm-readobj")
    forbidden = ("c2_stream_product_child_value", "c2_entry_records",
                 "c2_source_read")
    present = {name: len(truth.symbols_by_name.get(name, []))
               for name in forbidden}
    require(not any(present.values()), "cold tenant survived: " + str(present))
    scan = truth.symbol("c2_append_publish_plan_scan_phase")
    resolve = truth.symbol("c2_append_publish_plan_resolve_phase")
    require(scan.section == ".lisp65_rt_c2append_publish_plan_scan"
            and resolve.section == ".lisp65_rt_c2append_publish_plan_resolve",
            "split Cold-Plan symbols are not transported")
    walls = wplto["walls"]
    require(walls["e000_headroom_bytes"] >= E000_FLOOR,
            "restored E000 floor red")
    generated = target.parent / "generated-product-sources/c2_product_runtime.c"
    source = generated.read_text(encoding="utf-8")
    names = V6.c_function_definition(source, "c2_append_publish_names_phase")
    cells = V6.c_function_definition(source, "c2_append_publish_cells_phase")
    hot = V6.c_function_definition(source, "c2_product_entry_read")
    checks = {
        "post_header_names_source_free":
            "c2_stream_shelf_read" not in names and "c2_source_read" not in names,
        "post_header_cells_source_free":
            "c2_stream_shelf_read" not in cells and "c2_source_read" not in cells,
        "hot_entry_source_and_locator_free":
            "c2_stream_shelf_read" not in hot and "c2_source_read" not in hot
            and "+ 23" not in hot,
        "shared_entry_emitter_present":
            V6.c_function_definition(source, "c2_append_entries_phase").count(
                "c2d_v6_emit_entry_row") == 1,
    }
    require(all(checks.values()), "post-WPLTO semantic gate red: "
            + str([name for name, ok in checks.items() if not ok]))
    return {"status": "passed", "retired_cold_symbols": present,
            "cold_plan_scan_bytes": scan.bytes,
            "cold_plan_resolve_bytes": resolve.bytes,
            "post_ready_checks": checks, "generated_runtime": bind(generated)}


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
        "format": "lisp65-c2-lite-v6-semantic-splits-wplto-first-red-v1",
        "recorded_on": "2026-07-21",
        "status": "FIRST RED: semantic-split contract or WPLTO probe",
        "failure": str(error),
        "scope": {
            "whole_program_lto_attempts": int(
                (OUT / "full-product-wplto").exists()),
            "product_links": 0, "hardware_runs": 0, "promotable": False,
        },
        "evidence": evidence,
        "rollback_line": {"product": "Link 35", "status": "untouched"},
        "next_gate": "Class-C review; no retry or product link",
    }
    write_json(RECEIPT, value); protect()


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "semantic-split probe is one-shot and already exists")
    require(CAPACITY_AUTHORITY.is_file(), "Cold-Plan capacity First Red absent")
    require(HARNESS_FIRST_RED.is_file(), "Class-A source-projector First Red absent")
    OUT.mkdir(parents=True)
    source = source_contract_gate()
    cutpoints = cutpoint_gate()
    semantics = shared_semantics_gate()
    write_json(OUT / "source-contract-gate.json", source)
    write_json(OUT / "cutpoint-gate.json", cutpoints)
    write_json(OUT / "shared-semantics-gate.json", semantics)

    wplto, target, elf = run_one_wplto()
    structural = COLD.structural_gates(target, elf)
    capacity = split_capacity_gate(wplto, elf)
    semantic = cold_and_semantic_gate(wplto, target, elf)
    root = ROOT_GATE.collect()
    require(root["status"] == "passed", "permanent root-surrogate gate red")
    value = {
        "format": "lisp65-c2-lite-v6-semantic-splits-wplto-probe-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-five-semantic-splits-and-one-product-shaped-wplto",
        "scope": {"whole_program_lto_probes": 1, "product_links": 0,
                  "hardware_runs": 0, "promotable": False},
        "authority": {"capacity_first_red": bind(CAPACITY_AUTHORITY),
                      "class_a_source_projector_first_red": bind(HARNESS_FIRST_RED),
                      "contract": bind(CONTRACT), "addendum": bind(ADDENDUM)},
        "class_a_correction": {
            "failure": "phase-05 textual transform matched legacy 05 and new 05b",
            "fix": "scope the v6 reconstruction transform to the legacy phase-05 block",
            "compiler_runs_before_fix": 0,
            "linker_runs_before_fix": 0,
            "product_bytes_before_fix": 0,
        },
        "source_contract": source,
        "cutpoint_fixtures": cutpoints,
        "shared_semantics": semantics,
        "whole_program_lto": wplto,
        "semantic_split_capacity": capacity,
        "cold_plan_and_post_ready": semantic,
        "permanent_root_surrogate_gate": root,
        "fresh_structural_gates": structural,
        "artifacts": {"measurement_prg": bind(target),
                      "measurement_elf": bind(elf),
                      "measurement_map": bind(Path(str(target) + ".map"))},
        "claim_limit": (
            "Five semantic cuts and one nonpromotable product-shaped WPLTO. "
            "No product link, hardware, performance, promotion or acceptance claim."),
        "rollback_line": {"product": "Link 35", "status": "untouched"},
        "next_gate": "Class-C review before the first C2-lite product link",
    }
    write_json(OUT / "semantic-splits-wplto-probe.json", value)
    value["probe_report"] = bind(OUT / "semantic-splits-wplto-probe.json")
    write_json(RECEIPT, value); protect(); return value


def main() -> int:
    try:
        value = build()
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.CalledProcessError, RuntimeError) as error:
        if OUT.exists() and not RECEIPT.exists():
            record_first_red(error)
        print("c2-lite-v6-semantic-splits: FIRST RED " + str(error))
        return 2
    wplto = value["whole_program_lto"]
    pack = value["semantic_split_capacity"]
    print("c2-lite-v6-semantic-splits: PASS "
          f"slices={wplto['runtime_slices']['count']} "
          f"largest={wplto['runtime_slices']['largest_bytes']} "
          f"session-headroom={pack['session_family_headroom_bytes']} "
          f"e000={wplto['walls']['e000_headroom_bytes']} "
          "product-link=0 hardware=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
