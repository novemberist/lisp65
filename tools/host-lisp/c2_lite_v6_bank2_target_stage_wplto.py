#!/usr/bin/env python3
"""Qualify symmetric, target-verified Bank-2 staging with one WPLTO.

This is a non-promotable Class-C probe.  It adds one cold decoder phase after
the already authenticated Shelf CRC pass, proves the real linked copy/readback
edges, runs the Workbench-scratch negative and rebuilds every product gate.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402
import c2_lite_v6_roots_fronts_coresident_wplto as RF  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402


P = RF.P
STAGE = RF.STAGE
OUT = ROOT / "build/c2-lite/v6-bank2-target-stage-wplto-replay2"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / (
    "c2.2-c2-lite-v6-bank2-target-stage-wplto-replay2-receipt.json")
CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
ADDENDUM = ROOT / "docs/planning/c2-lite-execution-contract-addendum.md"
FIRST_RED = EVIDENCE / (
    "c2.2-product-link43-c2-lite-v6-bank2-stage-hardware-first-red.json")
LINK43 = ROOT / (
    "build/c2.2/substitution/"
    "product-link-43-c2-lite-v6-export-symbol-domain/"
    "lisp65-c2-substitution-linked.prg")
DECODER = ROOT / "scripts/c2-stream-decoder.c"
RUNTIME = ROOT / "src/c2_product_runtime.c"
REPL = ROOT / "src/repl.c"
PHASE = ROOT / "scripts/c2-stream-phase-03b.c"
FEATURE = "LISP65_C2_LITE_BANK2_STAGING"
PHASE_ROW = ("03b", "c2_stream_phase_03b")
PHASE_SOURCE = PHASE
CAP = 1792
STATIC_BYTES = 34403
WORKBENCH = ROOT / (
    "build/c2.2/hardware-presmoke-link43-export-symbol-domain/"
    "boot-overlay.raw.bin")


class ProbeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProbeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def protect() -> None:
    for path in OUT.rglob("*") if OUT.exists() else ():
        if path.is_file():
            os.chmod(path, 0o444)
    if RECEIPT.is_file():
        os.chmod(RECEIPT, 0o444)


def authority() -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract["status"] ==
            "class-c-approved-symmetric-bank2-target-stage-wplto-"
            "successor-link-and-line1-presmoke",
            "Bank-2 target-stage Class-C authority absent")
    auth = contract["bank2_target_stage_successor_authorization"]
    require(auth["product_first_red_budget"] == "2/3 consumed; 1 remains"
            and auth["latency_measurement_attempts"] == "0/2 consumed",
            "Bank-2 target-stage budget authority drift")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(first["status"] == "first-red-product-semantic-review-required"
            and "1,731-byte Workbench bootstrap scratch" in first["finding"]
            and "34,403-byte code-plane stage" in first["finding"],
            "Link-43 Bank-2 hardware First Red is not authoritative")
    return {"class_c_contract": bind(CONTRACT),
            "contract_addendum": bind(ADDENDUM),
            "link43_hardware_first_red": bind(FIRST_RED),
            "link43_rollback_product": {**bind(LINK43),
                                         "status": "untouched"},
            "driver": bind(Path(__file__))}


def configure_bank2_stage() -> None:
    require(PHASE_SOURCE not in P.C2_PHASE_SOURCES,
            "Bank-2 stage phase source duplicated")
    phase_at = P.C2_PHASE_SOURCES.index(
        ROOT / "scripts/c2-stream-phase-03.c") + 1
    P.C2_PHASE_SOURCES.insert(phase_at, PHASE_SOURCE)
    require(PHASE_ROW not in P.C2_DECODER_SLICES,
            "Bank-2 stage decoder row duplicated")
    row_at = P.C2_DECODER_SLICES.index(
        ("03", "c2_stream_phase_03")) + 1
    P.C2_DECODER_SLICES.insert(row_at, PHASE_ROW)
    P.BOOT_DECODER_SLICES = P.C2_DECODER_SLICES[:7]
    P.SESSION_DECODER_SLICES = P.C2_DECODER_SLICES[7:]
    # Bank-3 was configured by the predecessor profile before this cut.  Rebuild
    # its manifest once so the new cold phase owns slot 8 and the existing
    # Session-family stage moves deterministically to slot 9.
    P.configure_bank3_staging_slices()
    require(P.BOOT_DECODER_SLICES[-1] == PHASE_ROW
            and P.BOOT_BANK3_STAGE_SLOT == 9
            and P.BOOT_SLICE_SPECS[8].split(":", 1)[0] == "8"
            and P.BOOT_SLICE_SPECS[9].split(":", 1)[0] == "9",
            "Bank-2/Bank-3 cold-stage slot order drift")


def source_gate(decoder_path: Path = DECODER,
                runtime_path: Path = RUNTIME,
                repl_path: Path = REPL, *,
                test_mutations: bool = True) -> dict[str, Any]:
    decoder = decoder_path.read_text(encoding="utf-8")
    runtime = runtime_path.read_text(encoding="utf-8")
    repl = repl_path.read_text(encoding="utf-8")
    phase = V6.c_function_definition(decoder, "c2_stream_phase_03b")
    decode = V6.c_function_definition(runtime, "c2_decode_from")
    boot = V6.c_function_definition(runtime, "c2_product_boot")
    repl_fn = V6.c_function_definition(repl, "repl")
    checks = {
        "source_phase_publishes_cutpoint_only":
            "c->reserved = 0x3bu" in decoder
            and "c->phase = 4" in decoder,
        "target_phase_requires_exact_cutpoint":
            "c->reserved != 0x3bu" in phase,
        "record_bound_source_and_target":
            "source = r24(shelf + 8)" in phase
            and "expected = r32(shelf + 18)" in phase
            and "r24(image_row + 18) != next" in phase,
        "sole_copy_seam": phase.count("c2_product_physical_copy(") == 1,
        "actual_bank2_readback":
            "bank2_crc32(base, length, &actual)" in phase
            and "c2_facade_vm_code_load(2u, at, n, block)" in decoder,
        "bounded_content_convergence":
            "LISP65_RTOV_COMPLETION_TIMEOUT_FRAMES" in phase
            and "actual != expected" in phase
            and "C2_STREAM_ERR_CODE_STAGE" in phase,
        "exact_static_plane": "next != 34403UL" in phase,
        "target_stage_precedes_native_stage_and_select":
            decode.index("LISP65_C2_PHASE_03_SLOT")
            < decode.index("LISP65_C2_PHASE_03B_SLOT")
            < decode.index("LISP65_C2_BANK3_STAGE_SESSION_SLOT")
            < decode.index("c2_facade_select_family"),
        "ready_is_after_complete_decode_and_exports":
            boot.index("c2_decode_from(&c2_runtime, 0u)")
            < boot.index("c2_publish_exports_from(0)")
            < boot.index("c2_ready = 1;"),
        "banner_status_is_consumed":
            "vm_status != VM_OK && vm_status != VM_HALT" in repl_fn
            and repl_fn.index("vm_status_message()")
                < repl_fn.index("emit_str(\"lisp65> \")"),
        "failed_banner_returns_before_prompt":
            repl_fn.index("vm_status_message()")
            < repl_fn.index("return;")
            < repl_fn.index("emit_str(\"lisp65> \")"),
    }
    require(all(checks.values()), "Bank-2 source contract red: " + str(
        [name for name, ok in checks.items() if not ok]))

    if not test_mutations:
        return {"status": "passed-linked-stage-source-contract",
                "checks": checks, "mutations_rejected": {},
                "decoder": bind(decoder_path), "runtime": bind(runtime_path),
                "repl": bind(repl_path), "phase_wrapper": bind(PHASE)}
    mutations = {
        "stage-call-removed": runtime.replace(
            "LISP65_C2_PHASE_03B_SLOT, stream)",
            "LISP65_C2_PHASE_03_SLOT, stream)", 1),
        "target-bank-changed": decoder.replace(
            "c2_facade_vm_code_load(2u, at, n, block)",
            "c2_facade_vm_code_load(3u, at, n, block)", 1),
        "target-crc-bypassed": decoder.replace(
            "if (actual != expected)", "if (0u)", 1),
        "cutpoint-replayed": decoder.replace(
            "c->reserved != 0x3bu", "c->reserved != 0u", 1),
        "banner-status-discarded": repl.replace(
            "if (vm_status != VM_OK && vm_status != VM_HALT)",
            "if (0)", 1),
    }
    rejected: dict[str, str] = {}
    for name, mutation in mutations.items():
        try:
            if name == "stage-call-removed":
                source_gate(decoder_path, _write_mutation(name, mutation),
                            repl_path, test_mutations=False)
            elif name == "banner-status-discarded":
                source_gate(decoder_path, runtime_path,
                            _write_mutation(name, mutation),
                            test_mutations=False)
            else:
                source_gate(_write_mutation(name, mutation), runtime_path,
                            repl_path, test_mutations=False)
        except (ProbeError, ValueError):
            rejected[name] = "rejected"
    require(len(rejected) == len(mutations),
            "Bank-2 source mutation matrix incomplete")
    return {"status": "passed-linked-stage-source-contract",
            "checks": checks, "mutations_rejected": rejected,
            "decoder": bind(decoder_path), "runtime": bind(runtime_path),
            "repl": bind(repl_path), "phase_wrapper": bind(PHASE)}


def _write_mutation(name: str, text: str) -> Path:
    path = OUT / "mutations" / f"{name}.c"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def target_fixture(product: dict[str, Any]) -> dict[str, Any]:
    artifacts = product["host_c2d_v6"]["artifacts"]
    shelf_path = ROOT / artifacts["shelf"]["path"]
    c2d_path = ROOT / artifacts["c2d"]["path"]
    expected_path = ROOT / artifacts["code"]["path"]
    shelf = shelf_path.read_bytes()
    c2d = c2d_path.read_bytes()
    expected_plane = expected_path.read_bytes()
    scratch = WORKBENCH.read_bytes()
    require(len(expected_plane) == STATIC_BYTES and len(scratch) == 1731,
            "Bank-2 fixture artifact geometry drift")
    rows: list[dict[str, Any]] = []
    cursor = 0
    for image in range(6):
        s = shelf[32 + image * 32:64 + image * 32]
        d = c2d[48 + image * 32:80 + image * 32]
        source = int.from_bytes(s[8:11], "little")
        length = int.from_bytes(s[11:13], "little")
        crc = int.from_bytes(s[18:22], "little")
        target = int.from_bytes(d[18:21], "little")
        require(target == cursor and int.from_bytes(d[21:23], "little") == length
                and zlib.crc32(shelf[source:source + length]) & 0xffffffff == crc
                and zlib.crc32(expected_plane[target:target + length])
                    & 0xffffffff == crc,
                f"Bank-2 record {image} source/target binding red")
        rows.append({"image": image, "source": source, "target": target,
                     "bytes": length, "crc32": f"0x{crc:08x}"})
        cursor += length
    require(cursor == STATIC_BYTES, "six Bank-2 records do not close plane")
    scratch_plane = scratch + bytes(STATIC_BYTES - len(scratch))
    scratch_matches = sum(
        (zlib.crc32(scratch_plane[row["target"]:
                                  row["target"] + row["bytes"]])
         & 0xffffffff) == int(row["crc32"], 16)
        for row in rows)
    require(scratch_matches == 0, "Workbench scratch unexpectedly passes a code record")
    return {
        "status": "passed-six-record-target-and-workbench-negative",
        "records": rows, "record_count": len(rows),
        "static_plane_bytes": cursor,
        "expected_plane_all_target_crcs": "passed",
        "workbench_scratch_bytes": len(scratch),
        "workbench_scratch_passing_records": scratch_matches,
        "ready_if_workbench_scratch_remains": False,
        "shelf": bind(shelf_path), "c2d": bind(c2d_path),
        "expected_bank2": bind(expected_path), "workbench": bind(WORKBENCH),
    }


def elf_gate(product: dict[str, Any]) -> dict[str, Any]:
    elf = ROOT / product["artifacts"]["measurement_elf"]["path"]
    truth = ElfTruth.read(elf, llvm_readobj=P.TOOLCHAIN / "llvm-readobj")
    section = truth.section(".lisp65_rt_c2d_03b")
    symbol = truth.symbol("c2_stream_phase_03b")
    copy = truth.symbol("c2_product_physical_copy")
    readback = truth.symbol("c2_facade_vm_code_load")
    require(0 < section.bytes <= CAP
            and symbol.section == section.name and symbol.bytes > 0,
            "Bank-2 stage phase escaped its bounded cold slice")
    disassembly = P.run([str(P.TOOLCHAIN / "llvm-objdump"), "-d", str(elf)],
                        capture=True)
    nodes, _ = P._sectioned_disassembly(disassembly)
    rows = [row for row in nodes.values()
            if "c2_stream_phase_03b" in row["names"]]
    require(len(rows) == 1, "Bank-2 stage ELF node is not unique")
    targets = P._direct_call_targets(rows[0]["lines"])
    require(copy.value in targets and readback.value in targets,
            "Bank-2 stage lacks a real copy or target-readback edge")
    return {
        "status": "passed-real-target-dataflow-and-bounded-cold-slice",
        "phase": {"section": section.name, "bytes": section.bytes,
                  "headroom_bytes": CAP - section.bytes,
                  "address": symbol.value},
        "required_edges": {
            "physical_copy": {"address": copy.value, "present": True},
            "bank2_readback": {"address": readback.value, "present": True}},
        "boot_stage_slot": 8, "bank3_session_stage_slot": 9,
        "elf": bind(elf),
    }


def run_wplto() -> dict[str, Any]:
    old_configure = RF.configure_roots_fronts
    old_features = STAGE.feature_set
    old_out = RF.OUT

    def configure() -> None:
        old_configure()
        configure_bank2_stage()

    def features() -> tuple[str, ...]:
        values = old_features()
        require(FEATURE not in values, "Bank-2 stage feature duplicated")
        return (*values, FEATURE)

    try:
        RF.configure_roots_fronts = configure
        STAGE.feature_set = features
        RF.OUT = OUT
        return RF.run_wplto()
    finally:
        RF.configure_roots_fronts = old_configure
        STAGE.feature_set = old_features
        RF.OUT = old_out


def first_red(error: BaseException) -> None:
    value = {
        "format": "lisp65-c2-lite-v6-bank2-target-stage-wplto-first-red-v1",
        "recorded_on": "2026-07-22",
        "status": "FIRST RED: Bank-2 target-stage WPLTO stopped",
        "failure": {"type": type(error).__name__, "message": str(error)},
        "scope": {"whole_program_lto_probes": int(any(
                      OUT.rglob("c2-lite-v6-full-seed.prg.elf"))),
                  "product_links": 0, "hardware_runs": 0,
                  "promotable": False},
        "evidence": [bind(path) for path in sorted(OUT.rglob("*"))
                     if path.is_file()],
        "rollback_line": {**bind(LINK43), "status": "untouched"},
        "product_first_red_budget": "2/3 consumed; 1 remains",
        "latency_measurement_attempts": "0/2 consumed",
        "next_gate": "First Red: return to Class-C review; no link or hardware",
    }
    write_json(RECEIPT, value)
    protect()


def build() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "Bank-2 target-stage WPLTO is one-shot")
    auth = authority()
    OUT.mkdir(parents=True)
    source = source_gate()
    product = run_wplto()
    aggregate = RF.product_gate(product)
    fixture = target_fixture(product)
    target = elf_gate(product)
    walls = product["capacity"]["walls"]
    require(all(value >= 0 for value in walls.values())
            and walls["e000_headroom_bytes"] >= 115,
            f"Bank-2 target stage crossed a product wall: {walls}")
    value = {
        "format": "lisp65-c2-lite-v6-bank2-target-stage-wplto-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-symmetric-bank2-target-stage-product-shaped-WPLTO",
        "scope": {"whole_program_lto_probes": 1, "product_links": 0,
                  "hardware_runs": 0, "promotable": False},
        "authority": auth, "source_contract": source,
        "target_dataflow_gate": target,
        "workbench_scratch_negative_fixture": fixture,
        "product_shaped_wplto": product,
        "aggregate_recovery": aggregate,
        "product_first_red_budget": "2/3 consumed; 1 remains",
        "latency_measurement_attempts": "0/2 consumed",
        "claim_limit": "Source, linked target dataflow, mutation fixtures and "
                       "one non-promotable WPLTO only; no product link, hardware, "
                       "latency, promotion or acceptance claim.",
        "rollback_line": {**bind(LINK43), "status": "untouched"},
        "next_gate": "The already authorized successor product link",
    }
    report = OUT / "bank2-target-stage-wplto-report.json"
    write_json(report, value)
    value["probe_report"] = bind(report)
    write_json(RECEIPT, value)
    protect()
    return value


def main() -> int:
    try:
        value = build()
    except Exception as error:
        if OUT.exists() and not RECEIPT.exists():
            first_red(error)
        print("c2-lite-v6-bank2-target-stage-wplto: FIRST RED " + str(error))
        return 2
    walls = value["product_shaped_wplto"]["capacity"]["walls"]
    phase = value["target_dataflow_gate"]["phase"]
    aggregate = value["aggregate_recovery"]
    print("c2-lite-v6-bank2-target-stage-wplto: PASS "
          f"phase03b={phase['bytes']}B headroom={phase['headroom_bytes']}B "
          f"session={aggregate['session_family_bytes']}B "
          f"text={walls['bank0_text_headroom_bytes']}B "
          f"e000={walls['e000_headroom_bytes']}B "
          "product-link=0 hardware=0 budget=2/3 latency=0/2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
