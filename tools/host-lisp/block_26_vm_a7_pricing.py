#!/usr/bin/env python3
"""Price the Card-3 A7 fetch-boundary policy without building a product.

The executable baseline is the accepted A3--A6 r2 product.  This tool runs the
live delivered editor route for the single-key and batch populations, consumes
one headless DWX cycle trace over that exact packed baseline, and prices the
already-emitted direct A7 codegen form instruction by instruction.  It does not
invoke a compiler, WPLTO, a product linker, a media producer, or hardware.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_input_service_time_pricing as PRICE  # noqa: E402
import evidence_era as ERA


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
PRODUCT = ARCH / "block-2.6-card3-vm-hardening-product-r2-receipt.json"
DWX = ARCH / "block-2.6-card3-vm-hardening-dwx-r2.json"
PREAMBLE = ARCH / "block-2.6-card3-vm-hardening-preamble.json"
CLOSURE = ARCH / "c2.3-media-builder-closure-enumeration-v20-receipt.json"
BLIND = ROOT / "config/dwx-prefilter-blind-spot-contract.json"
RESPONSIVENESS = ROOT / "config/c2-v160-input-service-hybrid-contract.json"
EDITOR = ROOT / "lib/stdlib-read-line.lisp"
SEXP = ROOT / "lib/sexp-depth.lisp"
FINAL_ELF = ROOT / (
    "build/2.6/card3-vm-hardening-product-r2/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
FINAL_PRG = FINAL_ELF.with_suffix("")
FINAL_MEDIUM = ROOT / (
    "build/2.6/card3-vm-hardening-dwx-r2/media/shared-system/"
    "lisp65-product.d81")
BASELINE_TRACE = ROOT / (
    "build/2.6/card3-vm-a7-pricing/runtime/"
    "run-a7-r2-baseline/cycle-trace.json")
BASELINE_ASM = ROOT / (
    "build/2.6/card3-vm-hardening-preamble-r5/"
    "a3-through-a6/combined-c.s")
DIRECT_ASM = ROOT / (
    "build/2.6/card3-vm-hardening-preamble-r5/"
    "a3-through-a7-direct/combined-c.s")
XEMU = ROOT / "build/dwx/xemu-cycle-probe-r3/build/bin/xmega65.native"
RECEIPT = ARCH / "block-2.6-card3-vm-a7-pricing.json"
REPORT = ROOT / "docs/planning/2.6-card3-vm-a7-pricing-report.md"

AUTHORITY_COMMIT = "1f233541"
AUTHORITY_HEADER = (
    "## Reviewer acceptance — card 3 A3–A6 closed; A7 pricing and card 4 open — 2026-09-04")
FORMAT = "lisp65-block-2.6-card3-vm-a7-pricing-v1"
STATUS = "PASS: A7 THREE-LANE PRICE SELECTS TERMINAL SENTINEL FORMAT CARD"
TEXT_FLOOR = 32
SENTINEL_MINIMUM_OBJECTS = 792
SINGLE_CYCLE_RATIO_LIMIT = 1.02


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": sha(raw)}


def bind_at(commit: str, path: Path) -> dict[str, Any]:
    rel = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    return {"commit": commit, "path": rel, "bytes": len(raw),
            "sha256": sha(raw)}


def authority() -> dict[str, Any]:
    rel = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORITY_COMMIT}:{rel}"],
                         cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode("utf-8")
    require(text.count(AUTHORITY_HEADER) == 1, "A7 commission identity drift")
    section = AUTHORITY_HEADER + text.split(AUTHORITY_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").split())
    for token in ("a7 pricing round", "host-only", "zero wplto/links",
                  "single keystroke", "batch", "emulated cycles",
                  "792-byte sentinel", "no check, documented"):
        require(token in folded, f"A7 commission token absent: {token}")
    payload = section.encode()
    return {"commit": AUTHORITY_COMMIT, "path": rel,
            "header": AUTHORITY_HEADER, "bytes": len(payload),
            "sha256": sha(payload)}


def slim_route(raw: dict[str, Any]) -> dict[str, Any]:
    directory = raw["function_directory_authority"]
    return {
        "characters": raw["characters"],
        "dynamic_vm_steps": raw["dynamic_vm_steps"],
        "vm_steps_per_character": raw["vm_steps_per_character"],
        "screen_cells": raw["screen_cells"],
        "screen_cells_per_character": raw["screen_cells_per_character"],
        "boundary_count": raw["boundary_count"],
        "heap_cells_per_character": raw["heap_cells_per_character"],
        "function_world": raw["function_world"],
        "function_directory_authority": {
            "authority": directory["authority"],
            "derived_function_count": len(directory["derived_functions"]),
            "directory_function_count": len(directory["directory_functions"]),
            "canonical_sha256": sha(canonical(directory)),
            "sources": directory["sources"],
            "owner_suites": directory["owner_suites"],
        },
    }


def dynamic_lanes() -> dict[str, Any]:
    single = PRICE.execute_route(EDITOR, "single", 40, batch_cap=1,
                                 function_world="live-artifacts")
    batch = PRICE.execute_route(EDITOR, "batch", 40, batch_cap=8,
                                function_world="live-artifacts")
    require(single["vm_steps_per_character"] == 790.0,
            "A3-A6 single-key route population drift")
    require(batch["vm_steps_per_character"] == 209.875,
            "A3-A6 batch route population drift")
    require(single["function_directory_authority"]
            == batch["function_directory_authority"],
            "single and batch function worlds diverge")
    return {"single_keystroke": slim_route(single),
            "batch_cap_8": slim_route(batch)}


def ordered(text: str, tokens: list[str], label: str) -> None:
    cursor = 0
    for token in tokens:
        found = text.find(token, cursor)
        require(found >= 0, f"{label} emitted token absent/out of order: {token}")
        cursor = found + len(token)


def direct_emission_price() -> dict[str, Any]:
    baseline = BASELINE_ASM.read_text(encoding="utf-8")
    direct = DIRECT_ASM.read_text(encoding="utf-8")
    guard_tokens = [
        "\tldy\tvmr_win", "\tldx\tvmr_win+1", "\tlda\tvmr_code",
        "\tsta\t__rc6", "\tlda\t__rc20", "\tsec", "\tsbc\tvmr_code",
        "\tsta\t__rc3", "\tlda\t__rc21", "\tsbc\tvmr_code+1",
        "\tsta\t__rc4", "\tsty\t__rc13", "\tsty\t__rc2", "\tclc",
        "\tlda\t__rc3", "\tadc\t__rc2", "\tsta\t__rc3",
        "\tlda\t__rc4", "\tstx\t__rc14", "\tstx\t__rc2",
        "\tadc\t__rc2", "\tldx\tvmr_plen+1", "\tstx\t__rc2",
        "\tldy\tvmr_code+1", "\tsty\t__rc7", "\tldy\tvmr_plen",
        "\tcmp\t__rc2", "\tbne\t.LBB342_46", "\tstx\t__rc8",
        "\tsty\t__rc9", "\tsty\t__rc2", "\tldx\t__rc3",
        "\tcpx\t__rc2", "\tbra\t.LBB342_47", "\ttay",
        "\tbcc\t.LBB342_48",
    ]
    ordered(direct, guard_tokens, "direct guard")
    direct_fetch_tokens = [
        ".LBB342_61:", "\tldx\t__rc20", "\tstx\t__rc2",
        "\tldx\t__rc21", "\tstx\t__rc3", "\tldx\t__rc20",
        "\tstx\t__rc10", "\tldx\t__rc21", "\tstx\t__rc11",
        "\tinw\t__rc10", "\tlda\t__rc2", "\tldy\t#10",
        "\tsta\t(__rc0),y", "\tlda\t__rc3", "\tiny",
        "\tsta\t(__rc0),y", "\tlda\t(__rc20)", "\tcmp\t#66",
        "\tbcc\t.LBB342_62", "\tsta\t__rc2", "\tasl\t__rc2",
        "\tldx\t__rc2", "\tjmp\t(.LJTI342_0,x)",
    ]
    baseline_fetch_tokens = [
        ".LBB342_63:", "\tldx\t__rc2", "\tstx\t__rc10",
        "\tldx\t__rc3", "\tstx\t__rc11", "\tinw\t__rc10",
        "\tlda\t(__rc2)", "\tcmp\t#66", "\tbcc\t.LBB342_64",
        "\tsta\t__rc4", "\tasl\t__rc4", "\tldx\t__rc4",
        "\tjmp\t(.LJTI342_0,x)",
    ]
    ordered(direct, direct_fetch_tokens, "direct non-stream fetch")
    ordered(baseline, baseline_fetch_tokens, "baseline non-stream fetch")
    # 65C02/45GS02 target-cycle model on the emitted successful fast path.
    guard_cycles = [4, 4, 4, 3, 3, 2, 4, 3, 3, 4, 3, 3, 3, 2, 3, 3,
                    3, 3, 3, 3, 3, 4, 3, 4, 3, 4, 3, 2, 3, 3, 3, 3,
                    3, 3, 2, 3]
    direct_fetch_cycles = [3, 3, 3, 3, 3, 3, 3, 3, 6, 3, 2, 6, 3, 2,
                           6, 5, 2, 3, 3, 5, 3, 6]
    baseline_fetch_cycles = [3, 3, 3, 3, 6, 5, 2, 3, 3, 5, 3, 6]
    require(sum(guard_cycles) == 112 and sum(direct_fetch_cycles) == 79
            and sum(baseline_fetch_cycles) == 45,
            "direct emitted cycle ledger drift")
    return {
        "claim_class": (
            "exact instruction price of the already-emitted direct form, applied "
            "to the final-linked A3-A6 successor populations; not A7 qualification"),
        "baseline_assembly": bind(BASELINE_ASM),
        "direct_assembly": bind(DIRECT_ASM),
        "ordinary_text": {
            "isolated_relocatable_delta_bytes": 206,
            "previous_combined_marginal_delta_bytes": 286,
            "final_a3_a6_margin_bytes": 340,
            "floor_bytes": TEXT_FLOOR,
            "remaining_by_isolated_price_bytes": 134,
            "remaining_by_previous_combined_marginal_bytes": 54,
            "final_link_price_available": False,
            "reason": "the pricing authorization forbids a new WPLTO/product link",
        },
        "successful_non_streaming_fetch": {
            "semantic_guard": {"instructions": len(guard_cycles),
                               "cycles_per_fetch": sum(guard_cycles)},
            "register_allocation_and_fetch_prep": {
                "direct_path_cycles": sum(direct_fetch_cycles),
                "baseline_path_cycles": sum(baseline_fetch_cycles),
                "delta_cycles_per_fetch": (sum(direct_fetch_cycles)
                                           - sum(baseline_fetch_cycles))},
            "full_emitted_delta_cycles_per_fetch": (
                sum(guard_cycles) + sum(direct_fetch_cycles)
                - sum(baseline_fetch_cycles)),
            "optimistic_core_only_floor_cycles_per_fetch": sum(guard_cycles),
            "cycle_model": (
                "65C02/45GS02 emitted-instruction path; branch costs use the "
                "successful in-range equal-high-byte path"),
        },
    }


def lane_metrics(route: dict[str, Any], contract: dict[str, Any],
                 added_cycles_per_fetch: int) -> dict[str, Any]:
    steps = route["vm_steps_per_character"]
    base = (steps * contract["calibration_cycles_per_vm_step"]
            / contract["cycles_per_frame"]
            + route["screen_cells_per_character"]
            * contract["screen_cell_cycles"] / contract["cycles_per_frame"]
            + route["heap_cells_per_character"]
            * contract["collection_frames"] / contract["nursery_cells"])
    added = steps * added_cycles_per_fetch / contract["cycles_per_frame"]
    frames = base + added
    rate = 1.0 / frames
    return {"vm_steps_per_character": steps,
            "added_native_cycles_per_character": steps * added_cycles_per_fetch,
            "base_frames_per_character": base,
            "frames_per_character": frames,
            "service_events_per_frame": rate,
            "margin_percent": (rate - 1.0) * 100.0,
            "walls": {
                "maximum_frames_per_character": {
                    "required": contract["maximum_frames_per_character"],
                    "observed": frames,
                    "passed": frames <= contract["maximum_frames_per_character"]},
                "minimum_service_events_per_frame": {
                    "required": contract["minimum_service_events_per_frame"],
                    "observed": rate,
                    "passed": rate >= contract["minimum_service_events_per_frame"]},
                "minimum_margin_percent": {
                    "required": contract["minimum_margin_percent"],
                    "observed": (rate - 1.0) * 100.0,
                    "passed": ((rate - 1.0) * 100.0
                               >= contract["minimum_margin_percent"])}}}


def performance(lanes: dict[str, Any], direct: dict[str, Any]) -> dict[str, Any]:
    contract = load(RESPONSIVENESS)["responsiveness"]
    trace = load(BASELINE_TRACE)
    require(trace["characters"] == 40
            and sum(trace["cycle_deltas"]) == trace["total_cycles"]
            and trace["mean_cycles_per_key"]
            == trace["total_cycles"] / trace["characters"],
            "A3-A6 baseline DWX trace arithmetic drift")
    full = direct["successful_non_streaming_fetch"][
        "full_emitted_delta_cycles_per_fetch"]
    optimistic = direct["successful_non_streaming_fetch"][
        "optimistic_core_only_floor_cycles_per_fetch"]
    single_fetches = lanes["single_keystroke"]["vm_steps_per_character"]
    direct_cycles = trace["mean_cycles_per_key"] + single_fetches * full
    optimistic_cycles = trace["mean_cycles_per_key"] + single_fetches * optimistic
    direct_ratio = direct_cycles / trace["mean_cycles_per_key"]
    optimistic_ratio = optimistic_cycles / trace["mean_cycles_per_key"]
    direct_batch = lane_metrics(lanes["batch_cap_8"], contract, full)
    baseline_batch = lane_metrics(lanes["batch_cap_8"], contract, 0)
    direct_pass = (direct_ratio <= SINGLE_CYCLE_RATIO_LIMIT
                   and all(row["passed"] for row in direct_batch["walls"].values()))
    return {
        "claim_boundary": (
            "baseline DWX cycles are measured on the final A3-A6 packed medium; "
            "direct A7 cycles are an instruction-exact price, not an executed A7 product"),
        "baseline_trace": bind(BASELINE_TRACE),
        "baseline_trace_identity": {
            "characters": trace["characters"],
            "total_cycles": trace["total_cycles"],
            "mean_cycles_per_key": trace["mean_cycles_per_key"],
            "minimum_cycles": trace["minimum_cycles"],
            "maximum_cycles": trace["maximum_cycles"]},
        "single_keystroke": {
            "route": lanes["single_keystroke"],
            "baseline_vm_steps_per_key": single_fetches,
            "direct_vm_steps_per_key": single_fetches,
            "vm_step_ratio": 1.0,
            "baseline_measured_cycles_per_key": trace["mean_cycles_per_key"],
            "direct_priced_cycles_per_key": direct_cycles,
            "direct_cycle_ratio": direct_ratio,
            "wall": {"maximum_ratio_to_baseline": SINGLE_CYCLE_RATIO_LIMIT,
                     "passed": direct_ratio <= SINGLE_CYCLE_RATIO_LIMIT},
            "optimistic_guard_core_only": {
                "priced_cycles_per_key": optimistic_cycles,
                "cycle_ratio": optimistic_ratio,
                "passed": optimistic_ratio <= SINGLE_CYCLE_RATIO_LIMIT}},
        "batch": {"route": lanes["batch_cap_8"],
                  "baseline": baseline_batch, "direct": direct_batch},
        "emulated_cycles": {
            "baseline": {"kind": "headless-DWX-measured-final-A3-A6-medium",
                         "mean_cycles_per_key": trace["mean_cycles_per_key"]},
            "direct": {"kind": "emitted-instruction-exact-price",
                       "added_cycles_per_fetch": full,
                       "fetches_per_key": single_fetches,
                       "added_cycles_per_key": single_fetches * full,
                       "priced_cycles_per_key": direct_cycles,
                       "ratio": direct_ratio,
                       "passed": direct_ratio <= SINGLE_CYCLE_RATIO_LIMIT}},
        "direct_all_three_lanes_green": direct_pass,
    }


def sentinel(product: dict[str, Any], preamble: dict[str, Any]) -> dict[str, Any]:
    old = preamble["dispatch"]["terminal_sentinel"]
    object_count = old["object_count"]
    hole = product["final_product"]["composed_bank2"][
        "largest_contiguous_hole"]["bytes"]
    require(object_count == SENTINEL_MINIMUM_OBJECTS,
            "sealed delivered code-object population drift")
    require(old["required_population"] == [
        "C compiler emitter", "Lisp compiler emitter", "L65M decoder/validator",
        "static-plane packer", "append path", "directory length authority",
        "OBJ_SETUP", "stream-window refill"],
        "sentinel authority population drift")
    return {
        "decision_class": "separate-format-product-card-required",
        "form": old["form"],
        "object_count": object_count,
        "object_count_authority": bind(CLOSURE),
        "minimum_static_freight_bytes": object_count,
        "largest_bank2_hole_before_bytes": hole,
        "largest_bank2_hole_after_minimum_freight_bytes": hole - object_count,
        "required_population": old["required_population"],
        "format_contract": old["runtime_contract"],
        "hot_path": {"per_fetch_comparisons": 0,
                     "single_key_delta": 0, "batch_delta": 0,
                     "emulated_cycle_delta": 0},
        "open_prices": ["OBJ_SETUP/loader emitted bytes",
                        "one-time setup/validation cycles",
                        "full final-link owner remeasurement"],
        "three_lane_price": (
            "hot lanes retain the measured A3-A6 baseline; setup/loader lanes "
            "remain mandatory obligations of the format product card"),
        "reason": old["reason"],
    }


def derive() -> dict[str, Any]:
    product = load(PRODUCT)
    dwx = load(DWX)
    preamble = load(PREAMBLE)
    require(product["final_product"]["status"]
            == "PASS: FINAL CARD-3 RESERVED-LAYOUT A3-A6 PRODUCT CLOSED",
            "A3-A6 final product status drift")
    owners = product["final_product"]["bounded_owners"]
    require(owners["ordinary_text"]["margin_bytes"] == 340
            and owners["ordinary_text"]["floor_bytes"] == TEXT_FLOOR
            and product["final_product"]["composed_bank2"]
            ["largest_contiguous_hole"]["bytes"] == 15240,
            "A3-A6 final capacity world drift")
    accepted = dwx["accepted_pair"]
    require(accepted["ELF"]["sha256"] == bind(FINAL_ELF)["sha256"]
            and accepted["PRG"]["sha256"] == bind(FINAL_PRG)["sha256"],
            "A3-A6 DWX pair and final artifacts diverge")
    require(bind_at(AUTHORITY_COMMIT, EDITOR)["sha256"] == bind(EDITOR)["sha256"]
            and bind_at(AUTHORITY_COMMIT, SEXP)["sha256"] == bind(SEXP)["sha256"],
            "live responsiveness sources moved after A7 commission")
    lanes = dynamic_lanes()
    emitted = direct_emission_price()
    perf = performance(lanes, emitted)
    trailer = sentinel(product, preamble)
    direct_green = perf["direct_all_three_lanes_green"]
    require(not direct_green, "known direct emitted form unexpectedly clears all lanes")
    return {
        "format": FORMAT,
        "recorded_on": "2026-09-04",
        "status": STATUS,
        "authority": authority(),
        "inputs": {
            "product_receipt": bind(PRODUCT), "dwx_receipt": bind(DWX),
            "preamble_receipt": bind(PREAMBLE),
            "final_ELF": bind(FINAL_ELF), "final_PRG": bind(FINAL_PRG),
            "packed_medium": bind(FINAL_MEDIUM),
            "responsiveness_contract": bind(RESPONSIVENESS),
            "blind_spot_contract": bind(BLIND), "qualified_xemu": bind(XEMU),
            "live_editor": bind(EDITOR), "live_sexp": bind(SEXP)},
        "accounting": {"WPLTO": 0, "product_links": 0,
                       "media_builds": 0, "device_contacts": 0,
                       "headless_DWX_cycle_runs": 1,
                       "host_bytecode_route_runs": 2},
        "baseline": {
            "pair": accepted,
            "ordinary_text_margin_bytes": owners["ordinary_text"]["margin_bytes"],
            "ordinary_text_floor_bytes": owners["ordinary_text"]["floor_bytes"],
            "largest_bank2_hole_bytes": product["final_product"]
                ["composed_bank2"]["largest_contiguous_hole"]["bytes"],
            "world": "accepted executable A3-A6 r2 successor"},
        "direct_pc_payload_bound": {
            **emitted, "three_lane_price": perf,
            "decision": "rejected-known-emitted-form-single-cycle-wall-red",
            "reason": (
                "the full emitted form prices at 1.022461x the final A3-A6 "
                "DWX baseline, above the 1.02 single-key cycle wall; its batch "
                "lane remains green")},
        "terminal_sentinel": {
            **trailer, "decision": "recommended-next-product-card",
            "reason_for_recommendation": (
                "it is the only check-bearing option with no per-fetch cycle "
                "delta; its format-wide setup costs must be qualified separately")},
        "no_check_documented": {
            "ordinary_text_delta_bytes": 0, "bank2_delta_bytes": 0,
            "single_key_delta": 0, "batch_delta": 0,
            "emulated_cycle_delta": 0,
            "current_behavior": (
                "no pc<payload_len guard before RD8; malformed code that falls "
                "through without OP_RET may fetch stale or foreign bytes"),
            "decision": "admissible-only-as-documented-open-risk-not-recommended",
            "hardening_delivered": False},
        "recommendation": {
            "selected_for_next_decision": "terminal-sentinel-format-card",
            "product_card_opened": False,
            "owner_touchpoint_required": True,
            "direct_form_may_return_only_after_new_emitted-form-repricing": True,
            "claim": (
                "price result only; no A7 product, media, qualification, or "
                "hardware claim is made")},
    }


def validate(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT and value.get("status") == STATUS,
            "A7 price identity red")
    require(value["accounting"] == {"WPLTO": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0,
            "headless_DWX_cycle_runs": 1, "host_bytecode_route_runs": 2},
            "A7 host-only accounting red")
    direct = value["direct_pc_payload_bound"]
    perf = direct["three_lane_price"]
    require(direct["successful_non_streaming_fetch"]
            ["full_emitted_delta_cycles_per_fetch"] == 146,
            "direct full emitted cycle price red")
    require(perf["single_keystroke"]["route"]["vm_steps_per_character"] == 790.0
            and perf["batch"]["route"]["vm_steps_per_character"] == 209.875,
            "A7 route populations red")
    require(not perf["single_keystroke"]["wall"]["passed"]
            and perf["single_keystroke"]["direct_cycle_ratio"] > 1.02,
            "direct single-cycle red was lost")
    require(all(row["passed"] for row in
                perf["batch"]["direct"]["walls"].values()),
            "direct batch price should remain green")
    sentinel_row = value["terminal_sentinel"]
    require(sentinel_row["minimum_static_freight_bytes"] >= 792
            and sentinel_row["decision"] == "recommended-next-product-card"
            and len(sentinel_row["required_population"]) == 8,
            "sentinel format-card price red")
    require(value["no_check_documented"]["hardening_delivered"] is False
            and value["recommendation"]["product_card_opened"] is False
            and value["recommendation"]["selected_for_next_decision"]
            == "terminal-sentinel-format-card",
            "A7 decision boundary red")


def report(value: dict[str, Any]) -> str:
    direct = value["direct_pc_payload_bound"]
    price = direct["three_lane_price"]
    single = price["single_keystroke"]
    batch = price["batch"]["direct"]
    sent = value["terminal_sentinel"]
    return f"""# Block 2.6 Card 3 A7 pricing report

Status: **{value['status']}**

This was a host-only price round over the accepted executable A3--A6 r2
successor (`{value['baseline']['pair']['ELF']['sha256'][:12]}…` /
`{value['baseline']['pair']['PRG']['sha256'][:12]}…`). It consumed zero WPLTOs,
zero product links, zero media builds, and zero device contacts. One headless
DWX cycle trace was taken over the already-packed A3--A6 medium.

## Three-lane result

The living delivered editor route executes **{single['route']['vm_steps_per_character']:.3f}**
VM fetches per physical single key and **{price['batch']['route']['vm_steps_per_character']:.3f}**
per character in the cap-8 batch. The final A3--A6 medium measured
**{single['baseline_measured_cycles_per_key']:,.1f} emulated cycles/key**.

The already-emitted direct `pc < payload_len` form costs **112 cycles/fetch**
for the semantic guard plus **34 cycles/fetch** of register-allocation/fetch
fallout, **146 cycles/fetch** total. Applied to the final successor population,
the single-key lane prices at **{single['direct_priced_cycles_per_key']:,.1f}
cycles/key**, ratio **{single['direct_cycle_ratio']:.6f}** against the 1.02 wall:
**red**. Even the optimistic guard-only floor is
{single['optimistic_guard_core_only']['cycle_ratio']:.6f}; the known emitted
form loses on its spill/fetch fallout. The batch lane remains green at
**{batch['frames_per_character']:.6f} frames/character**,
**{batch['service_events_per_frame']:.6f} events/frame**, and
**{batch['margin_percent']:.3f}% margin**. Native C instructions do not change
the bytecode VM-step count, demonstrating why the DWX cycle lane is decisive.

The byte price is affordable but not decisive: isolated relocatable codegen is
**+206 ordinary-text bytes**, leaving 134/32; the earlier combined marginal was
**+286**, leaving 54/32. Neither number is promoted to a final-link A7 claim,
because this round was forbidden to link a product.

## Alternatives

The terminal-sentinel format adds at least one byte to each of the
**{sent['object_count']} delivered code objects**, minimum **{sent['minimum_static_freight_bytes']}
Bank-2 bytes**, leaving **{sent['largest_bank2_hole_after_minimum_freight_bytes']:,} bytes**
in the largest hole. It has zero per-fetch comparison and therefore retains the
baseline hot-path lanes. It is not a local patch: all eight authorities
({', '.join(sent['required_population'])}) must move together, and setup/loader
bytes and cycles remain obligations of a separate format product card.

The honest no-check option costs zero, but leaves malformed fallthrough able to
fetch stale or foreign bytes and delivers no A7 hardening.

## Recommendation

**Open the terminal-sentinel format card.** It is the only check-bearing option
whose hot path stays green. Reject this known emitted direct form; it may return
only after a genuinely different emitted form is repriced. The no-check option
remains an explicit documented-risk fallback, not the recommendation. No
product card is opened by this report.
"""


@ERA.in_host_source_world("520352a6")
def check() -> None:
    actual = load(RECEIPT)
    validate(actual)
    expected = derive()
    # The blind-spot contract is a living DWX authority.  This sealed price
    # records the version it consumed; successor additions do not reprice A7.
    expected["inputs"]["blind_spot_contract"] = actual["inputs"][
        "blind_spot_contract"]
    require(actual == expected, "A7 pricing inputs or derivation drift")
    require(REPORT.read_text(encoding="utf-8") == report(actual),
            "A7 pricing report drift")
    print("Block 2.6 Card 3 A7 pricing: CHECK PASS direct=red sentinel=recommended")


def selftest() -> None:
    original = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "hidden-product-link": lambda row: row["accounting"].update({"product_links": 1}),
        "direct-cycle-price-weakened": lambda row: row["direct_pc_payload_bound"]
            ["successful_non_streaming_fetch"].update(
                {"full_emitted_delta_cycles_per_fetch": 112}),
        "direct-red-called-green": lambda row: row["direct_pc_payload_bound"]
            ["three_lane_price"]["single_keystroke"]["wall"].update({"passed": True}),
        "stale-single-route": lambda row: row["direct_pc_payload_bound"]
            ["three_lane_price"]["single_keystroke"]["route"].update(
                {"vm_steps_per_character": 902.0}),
        "sentinel-object-omitted": lambda row: row["terminal_sentinel"].update(
            {"minimum_static_freight_bytes": 791}),
        "sentinel-localized": lambda row: row["terminal_sentinel"].update(
            {"decision": "local-vm-patch"}),
        "sentinel-authority-omitted": lambda row: row["terminal_sentinel"]
            ["required_population"].pop(),
        "no-check-claims-hardening": lambda row: row["no_check_documented"].update(
            {"hardening_delivered": True}),
        "product-card-opened-silently": lambda row: row["recommendation"].update(
            {"product_card_opened": True}),
        "recommend-direct": lambda row: row["recommendation"].update(
            {"selected_for_next_decision": "direct-pc-bound"}),
    }
    rejected = []
    for name, mutate in cases.items():
        candidate = deepcopy(original)
        mutate(candidate)
        try:
            validate(candidate)
        except PricingError:
            rejected.append(name)
    require(rejected == list(cases), f"A7 pricing mutations escaped: {rejected}")
    print(f"Block 2.6 Card 3 A7 pricing: SELFTEST PASS mutations={len(rejected)}")


def build() -> None:
    require(not RECEIPT.exists() and not REPORT.exists(),
            "A7 pricing outputs already exist")
    value = derive()
    validate(value)
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    print("Block 2.6 Card 3 A7 pricing: BUILD PASS WPLTO=0 link=0 device=0")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check", "selftest"))
    args = parser.parse_args()
    {"build": build, "check": check, "selftest": selftest}[args.action]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
