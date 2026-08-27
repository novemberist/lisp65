#!/usr/bin/env python3
"""Qualify the approved phase-02b Bank-2 target-coordinate close."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import c2_lite_v6_bank2_target_stage_followup_wplto as F


B = F.B
ROOT = B.ROOT
OUT = ROOT / "build/c2-lite/v6-bank2-target-stage-phase02b-wplto"
RECEIPT = B.EVIDENCE / (
    "c2.2-c2-lite-v6-bank2-target-stage-phase02b-wplto-receipt.json")
DIAGNOSIS = B.EVIDENCE / (
    "c2.2-c2-lite-v6-bank2-target-stage-followup-wplto-first-red-diagnosis.json")

B.OUT = OUT
B.RECEIPT = RECEIPT
_base_authority = F.authority


def authority() -> dict[str, Any]:
    value = _base_authority()
    contract = json.loads(B.CONTRACT.read_text(encoding="utf-8"))
    approved = contract["bank2_target_stage_successor_authorization"][
        "approved_followup_wplto_first_red"]
    B.require(approved["phase02a_over_cap_bytes"] == 131
              and approved["phase02b_headroom_bytes"] == 1549
              and "one full WPLTO" in approved["disposition"],
              "phase-02b WPLTO authority absent")
    diagnosis = json.loads(DIAGNOSIS.read_text(encoding="utf-8"))
    B.require(diagnosis["status"].startswith("FIRST RED:")
              and diagnosis["first_red"]["over_cap_bytes"] == 131
              and diagnosis["scope"]["product_links"] == 0,
              "phase-02a WPLTO First Red is not authoritative")
    value["phase02b_driver"] = B.bind(Path(__file__))
    value["approved_phase02a_first_red"] = B.bind(DIAGNOSIS)
    return value


def source_gate(decoder_path: Path = B.DECODER,
                runtime_path: Path = B.RUNTIME,
                repl_path: Path = B.REPL, *,
                test_mutations: bool = True) -> dict[str, Any]:
    decoder = decoder_path.read_text(encoding="utf-8")
    runtime = runtime_path.read_text(encoding="utf-8")
    repl = repl_path.read_text(encoding="utf-8")
    phase02a = B.V6.c_function_definition(decoder, "c2_stream_phase_02a")
    phase02b = B.V6.c_function_definition(decoder, "c2_stream_phase_02b")
    phase03 = B.V6.c_function_definition(decoder, "c2_stream_phase_03")
    phase03b = B.V6.c_function_definition(decoder, "c2_stream_phase_03b")
    decode = B.V6.c_function_definition(runtime, "c2_decode_from")
    boot = B.V6.c_function_definition(runtime, "c2_product_boot")
    repl_fn = B.V6.c_function_definition(repl, "repl")
    banner_at = repl_fn.index("if (vm_status != VM_OK && vm_status != VM_HALT)")
    prompt_at = repl_fn.index('emit_str("lisp65> ")')
    banner = repl_fn[banner_at:prompt_at]

    checks = {
        "phase02a_has_no_target_close_copy":
            "code_target" not in phase02a
            and "i * 32u + 18u" not in phase02a,
        "phase02a_publishes_exact_record_marker":
            "c->reserved = 0x2au" in phase02a,
        "phase02b_requires_record_marker":
            "c->reserved != 0x2au" in phase02b,
        "phase02b_owns_target_coordinate_close":
            "code_target = 0u" in phase02b
            and "i * 32u + 18u" in phase02b
            and "length = r16(target + 3)" in phase02b
            and "r24(target) != code_target" in phase02b
            and "code_target += length" in phase02b
            and "code_target != LISP65_C2_LITE_STATIC_CODE_BYTES"
                in phase02b
            and '#include "c2_lite_static_plane.h"' in decoder,
        "target_close_precedes_phase03_publication":
            phase02b.index(
                "code_target != LISP65_C2_LITE_STATIC_CODE_BYTES")
            < phase02b.index("c->reserved = 0")
            < phase02b.index("c->phase = 3"),
        "source_phase_publishes_cutpoint_only":
            phase03.index("#ifdef LISP65_C2_LITE_BANK2_STAGING")
            < phase03.index("c->reserved = 0x3bu")
            < phase03.index("#else")
            < phase03.index("c->phase = 4"),
        "target_phase_requires_exact_cutpoint":
            "c->reserved != 0x3bu" in phase03b,
        "target_phase_consumes_bound_plan":
            "image_row" not in phase03b
            and "c2_stream_c2d_read(" not in phase03b
            and "source = r24(shelf + 8)" in phase03b
            and "expected = r32(shelf + 18)" in phase03b,
        "sole_copy_seam": phase03b.count("c2_product_physical_copy(") == 1,
        "actual_bank2_readback":
            "bank2_crc32(base, length, &actual)" in phase03b
            and "c2_facade_vm_code_load(2u, at, n, block)" in decoder,
        "bounded_content_convergence":
            "LISP65_RTOV_COMPLETION_TIMEOUT_FRAMES" in phase03b
            and "actual != expected" in phase03b
            and "C2_STREAM_ERR_CODE_STAGE" in phase03b,
        "exact_static_plane_rechecked":
            "next != LISP65_C2_LITE_STATIC_CODE_BYTES" in phase03b,
        "target_stage_precedes_native_stage_and_select":
            decode.index("LISP65_C2_PHASE_03_SLOT")
            < decode.index("LISP65_C2_PHASE_03B_SLOT")
            < decode.index("LISP65_C2_BANK3_STAGE_SESSION_SLOT")
            < decode.index("c2_facade_select_family"),
        "ready_is_after_complete_decode_and_exports":
            boot.index("c2_decode_from(&c2_runtime, 0u)")
            < boot.index("c2_publish_exports_from(0)")
            < boot.index("c2_ready = 1;"),
        "banner_uses_single_numeric_error_truth":
            "lisp_abort_code(vm_status_error_code(vm_status));" in banner
            and "emit_str(vm_status_message())" not in banner
            and "lisp65_error_render_code(" not in banner,
        "failed_banner_recovers_before_prompt":
            repl_fn.index("lisp_toplevel_active = 1;") < banner_at
            and banner.index(
                "lisp_abort_code(vm_status_error_code(vm_status));")
                < len(banner),
    }
    B.require(all(checks.values()), "phase-02b source contract red: "
              + str([name for name, ok in checks.items() if not ok]))

    if not test_mutations:
        return {"status": "passed-phase02b-target-close-source-contract",
                "checks": checks, "mutations_rejected": {},
                "decoder": B.bind(decoder_path),
                "runtime": B.bind(runtime_path), "repl": B.bind(repl_path),
                "phase_wrapper": B.bind(B.PHASE)}

    mutations = {
        "stage-call-removed": ("runtime", runtime.replace(
            "LISP65_C2_PHASE_03B_SLOT, stream)",
            "LISP65_C2_PHASE_03_SLOT, stream)", 1)),
        "target-bank-changed": ("decoder", decoder.replace(
            "c2_facade_vm_code_load(2u, at, n, block)",
            "c2_facade_vm_code_load(3u, at, n, block)", 1)),
        "target-crc-bypassed": ("decoder", decoder.replace(
            "if (actual != expected)", "if (0u)", 1)),
        "record-cutpoint-replayed": ("decoder", decoder.replace(
            "c->reserved != 0x2au", "c->reserved != 0u", 1)),
        "stage-cutpoint-replayed": ("decoder", decoder.replace(
            "c->reserved != 0x3bu", "c->reserved != 0u", 1)),
        "target-cross-binding-bypassed": ("decoder", decoder.replace(
            "r24(target) != code_target", "0u", 1)),
        "static-plane-close-bypassed": ("decoder", decoder.replace(
            "if (code_target != LISP65_C2_LITE_STATIC_CODE_BYTES)",
            "if (0u)", 1)),
        "banner-status-discarded": ("repl", repl.replace(
            "if (vm_status != VM_OK && vm_status != VM_HALT)",
            "if (0)", 1)),
        "banner-text-truth-reintroduced": ("repl", repl.replace(
            "lisp_abort_code(vm_status_error_code(vm_status));",
            "emit_str(vm_status_message());", 1)),
        "banner-recovery-removed": ("repl", repl.replace(
            "lisp_abort_code(vm_status_error_code(vm_status));",
            "(void)vm_status_error_code(vm_status);", 1)),
    }
    rejected: dict[str, str] = {}
    for name, (kind, mutation) in mutations.items():
        path = B._write_mutation(name, mutation)
        try:
            source_gate(path if kind == "decoder" else decoder_path,
                        path if kind == "runtime" else runtime_path,
                        path if kind == "repl" else repl_path,
                        test_mutations=False)
        except (B.ProbeError, ValueError):
            rejected[name] = "rejected"
    B.require(len(rejected) == len(mutations),
              "phase-02b mutation matrix incomplete")
    return {"status": "passed-phase02b-target-close-source-contract",
            "checks": checks, "mutations_rejected": rejected,
            "decoder": B.bind(decoder_path),
            "runtime": B.bind(runtime_path), "repl": B.bind(repl_path),
            "phase_wrapper": B.bind(B.PHASE)}


B.authority = authority
B.source_gate = source_gate


if __name__ == "__main__":
    raise SystemExit(B.main())
