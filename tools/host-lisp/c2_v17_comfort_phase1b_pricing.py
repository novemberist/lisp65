#!/usr/bin/env python3
"""Price the two v1.7 Comfort primitive-closure variants host-only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as COMPILER  # noqa: E402
import bytecode_p0_stdlib as P0  # noqa: E402
import c2_product_callprim_delivery_gate as DELIVERY  # noqa: E402
import c2_v160_display_ownership as DISPLAY  # noqa: E402
import c2_v160_input_service_hybrid_final_world as FINAL  # noqa: E402
import c2_v160_input_service_time_pricing as TIMING  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
ELF = ROOT / ("build/c2.3/v1.6-clean-product-operand-root-fix/wplto/"
              "lisp65-c2-substitution-linked.prg.elf")
COMFORT = ROOT / "lib/repl-comfort.lisp"
EDITOR = ROOT / "lib/stdlib-read-line.lisp"
VM = ROOT / "src/vm.c"
EVAL = ROOT / "src/eval.c"
PROFILE = ROOT / "config/v11-surface-delivery-parity.json"
HYBRID_CONTRACT = ROOT / "config/c2-v160-input-service-hybrid-contract.json"
CAPACITY = ARCH / "c2.3-v1.6-display-ownership-replacement-card-receipt.json"
OBSERVATION = ARCH / (
    "artifacts/c2.3-v1.7-comfort-phase1b-paired-link-observation.txt")
OUT = ARCH / "c2.3-v1.7-comfort-phase1b-pricing-receipt.json"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
FORMAT = "lisp65-c2-v17-comfort-phase1b-pricing-v1"
PROMPT = "l65> "
CALLPRIM_ID = 12
PRICING_COMMIT = "e91a526a"
IMPLEMENTATION = ROOT / "config/c2-v17-comfort-phase1b-implementation-contract.json"


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def bind_raw(path: Path, raw: bytes) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def era_blob(commit: str, path: Path) -> bytes:
    process = subprocess.run(
        ["git", "show", f"{commit}:{path.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    require(process.returncode == 0,
            f"pricing-era input absent: {commit}:{path.relative_to(ROOT)}")
    return process.stdout


def parse_observation() -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in OBSERVATION.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        require(separator == "=" and key and key not in rows,
                "paired-link observation is not a unique key/value ledger")
        rows[key] = value
    required = {
        "format", "common_world", "only_variant_difference",
        "baseline_text_address", "baseline_text_bytes",
        "variant_a_text_address", "variant_a_text_bytes",
        "variant_a_link_result", "variant_a_link_error",
        "baseline_bss_bytes", "variant_a_bss_bytes",
        "baseline_rodata_bytes", "variant_a_rodata_bytes",
        "baseline_far_service_bytes", "variant_a_far_service_bytes",
        "baseline_facade_bytes", "variant_a_facade_bytes",
        "variant_a_automatic_wbuf_bytes", "price_wplto_attempts",
        "successful_price_links", "capacity_rejected_price_links",
        "product_cards", "media_builds", "device_contacts",
    }
    require(required <= rows.keys(), "paired-link observation is incomplete")
    require(rows["only_variant_difference"] == "LISP65_SCREEN_WRITE_STRING",
            "paired-link variant is not single-variable")
    require(rows["variant_a_link_result"] == "REJECTED"
            and rows["variant_a_link_error"]
            == "ordinary text displaced the mapped far facade",
            "Variant A capacity rejection changed")
    return rows


def fallback_source(source: str) -> str:
    old = '                  (screen-write-string 0 row "l65> "))'
    require(source.count(old) == 1, "Comfort bulk prompt site drift")
    source = source.replace(old, "                  (%repl-prompt row))", 1)
    helper = '''
(defun %repl-prompt (row)
  (if (screen-bulk-p)
      (screen-write-string 0 row "l65> ")
      (progn
        (screen-put-char 0 row 108 1)
        (screen-put-char 1 row 54 1)
        (screen-put-char 2 row 53 1)
        (screen-put-char 3 row 62 1)
        (screen-put-char 4 row 32 1))))

'''
    marker = "(defun %repl-step"
    require(source.count(marker) == 1, "Comfort step definition drift")
    return source.replace(marker, helper + marker, 1)


def compile_sizes(source: str) -> dict[str, int]:
    forms = [form for form in COMPILER.parse_all(source)
             if isinstance(form, list) and len(form) > 1
             and form[0] == "defun"]
    heap = COMPILER.prepare_heap([form[1] for form in forms])
    sizes: dict[str, int] = {}
    for form in forms:
        name, code, helpers = COMPILER.compile_top_form_with_helpers(
            form, heap, strict_arity=True, abi_profile="dialect-v2",
            prebuilt_primitives=True)
        require(not helpers, f"unexpected compiler helper in {name}")
        sizes[name] = len(code.encode())
    require(max(sizes.values()) <= 255, "fallback exceeds code-object ceiling")
    return sizes


def suite_for(label: str, source: str,
              delivered: list[int], editor: str | None = None) -> dict[str, Any]:
    suite = DISPLAY.mutated_suite(label, comfort=source, editor=editor)
    suite = dict(suite)
    functions = [name for name in suite.get("functions", [])
                 if name != "%repl-prompt"]
    if "%repl-prompt" in source:
        functions.append("%repl-prompt")
    suite["functions"] = functions
    suite["delivered_callprims"] = list(delivered)
    return suite


def product_profile_gate(source: str, candidate: str,
                         profile: dict[str, Any],
                         editor: str | None = None) -> dict[str, Any]:
    delivered = profile["delivered_ids"]
    qualified = P0.check_suite(
        "v1.7-comfort-phase1b-product-fallback",
        suite_for("phase1b-product-fallback", candidate, delivered, editor))
    require(qualified["cases"] == 9 and qualified["functions"] == 4,
            "product-profile fallback suite coverage drift")

    try:
        P0.check_suite(
            "v1.7-comfort-phase1b-tombstone",
            suite_for("phase1b-product-tombstone", source, delivered, editor))
    except B.VMError as error:
        require(error.status == "BadOpcode"
                and "product-profile tombstone Prim-ID 12" in str(error),
                f"wrong product-profile rejection: {error}")
        tombstone_rejection = str(error)
    else:
        raise PricingError("tombstoned CALLPRIM 12 survived product qualification")

    unrestricted = DISPLAY.mutated_suite(
        "phase1b-unrestricted-host-mutation", comfort=source, editor=editor)
    unrestricted = dict(unrestricted)
    unrestricted["functions"] = [
        name for name in unrestricted.get("functions", [])
        if name != "%repl-prompt"
    ]
    false_green = P0.check_suite(
        "v1.7-comfort-phase1b-unrestricted-host-mutation", unrestricted)
    require(false_green["cases"] == 9,
            "unrestricted-host mutation no longer demonstrates the blind spot")

    invented = list(delivered) + [CALLPRIM_ID]
    invented_green = P0.check_suite(
        "v1.7-comfort-phase1b-invented-delivery-mutation",
        suite_for("phase1b-invented-delivery-mutation", source, invented, editor))
    require(invented_green["cases"] == 9,
            "invented-delivery mutation no longer demonstrates false green")
    return {
        "fallback_cases": qualified["cases"],
        "fallback_functions": qualified["functions"],
        "fallback_steps": qualified["steps"],
        "tombstone_rejection": tombstone_rejection,
        "unrestricted_host_false_green_cases": false_green["cases"],
        "invented_delivery_false_green_cases": invented_green["cases"],
        "mutation_rule": ("product-destined suites consume the final ELF "
                          "CALLPRIM table, tombstones included"),
    }


def product_profile_claim(value: dict[str, Any]) -> dict[str, Any]:
    """Return the enduring claim, excluding the sealed price-era step witness.

    ``fallback_steps`` measured scheduling in the resident library world of the
    Phase-1b price.  Later resident freight legitimately changes lookup and
    qualification bookkeeping even while every delivered-primitive claim stays
    identical.  The historical number remains sealed in the receipt; it is not
    a live equality over successor library worlds.
    """
    return {key: item for key, item in value.items()
            if key != "fallback_steps"}


def full_route(label: str, source: str,
               delivered: list[int] | None) -> dict[str, Any]:
    events = [97] * 40 + [13]
    suite = DISPLAY.mutated_suite(label, comfort=source)
    suite = dict(suite)
    functions = [name for name in suite.get("functions", [])
                 if name != "%repl-prompt"]
    if "%repl-prompt" in source:
        functions.append("%repl-prompt")
    suite["functions"] = functions
    suite["cases"] = [{"name": label, "expr": "(repl)", "expect": "nil",
                       "key_events": events, "max_steps": 1_000_000}]
    if delivered is not None:
        suite["delivered_callprims"] = list(delivered)
    (heap, _names, _code, entry_flags, resident_flags, _bundle, directory,
     _cases, entries, _inliner) = P0._compile_suite(suite)
    abi_profile, abi_ledger = P0._suite_abi(suite)
    vm = TIMING.TimingVM(
        heap=heap.clone(), directory=directory,
        macro_symbols=P0._macro_symbol_objs(
            heap, entry_flags, resident_flags),
        max_steps=1_000_000, max_call_args=suite.get("max_call_args"),
        key_events=events, private_key_event_modes=True,
        abi_profile=abi_profile, abi_ledger=abi_ledger, batch_cap=8,
        delivered_callprims=delivered)
    try:
        vm.run(directory[heap.intern(entries[0])], [])
    except B.VMError as error:
        # Forty 'a' characters are intentionally not a bound top-level form;
        # the measurement ends after the input boundary, before this miss.
        require(not vm.key_events, f"full route stopped before input drain: {error}")
    points = [step for kind, step in vm.boundaries if kind == "private-2"]
    require(len(points) == 6, f"full-route batch boundary drift: {len(points)}")
    return {"characters": 40, "first_boundary_step": points[0],
            "last_boundary_step": points[-1],
            "stationary_steps": points[-1] - points[0],
            "stationary_vm_steps_per_character":
                (points[-1] - points[0]) / 40,
            "stationary_screen_cells": sum(
                points[0] <= step < points[-1] for step in vm.screen_steps),
            "screen_put_char_calls_total": vm.io_counters["screen_put_char"]}


def variant_a(truth: ElfTruth, rows: dict[str, str]) -> dict[str, Any]:
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    headroom = facade.address - (text.address + text.bytes)
    require(headroom >= 0, "sealed ordinary text already overlaps facade")
    baseline = int(rows["baseline_text_bytes"], 0)
    enabled = int(rows["variant_a_text_bytes"], 0)
    delta = enabled - baseline
    require(delta == 903, f"Variant A paired text delta drift: {delta}")
    require(int(rows["baseline_bss_bytes"]) == int(rows["variant_a_bss_bytes"])
            and int(rows["baseline_rodata_bytes"])
            == int(rows["variant_a_rodata_bytes"])
            and int(rows["baseline_far_service_bytes"])
            == int(rows["variant_a_far_service_bytes"])
            and int(rows["baseline_facade_bytes"])
            == int(rows["variant_a_facade_bytes"]),
            "Variant A changed a non-text resident arena")
    overrun = delta - headroom
    require(overrun == 630 and overrun > 0,
            f"Variant A facade overrun drift: {overrun}")
    require("#ifdef LISP65_SCREEN_WRITE_STRING" in VM.read_text()
            and "LISP65_SCREEN_WRITE_STRING" in EVAL.read_text(),
            "Variant A source feature seam drift")
    return {
        "change": "enable LISP65_SCREEN_WRITE_STRING in the product profile",
        "paired_final_lto": {"baseline_text_bytes": baseline,
                             "enabled_text_bytes": enabled,
                             "ordinary_text_delta_bytes": delta},
        "sealed_candidate": {"text_address": f"0x{text.address:04x}",
                             "text_bytes": text.bytes,
                             "facade_address": f"0x{facade.address:04x}",
                             "ordinary_text_headroom_bytes": headroom,
                             "projected_facade_overrun_bytes": overrun},
        "other_resident_deltas": {"bss_bytes": 0, "rodata_bytes": 0,
                                  "far_service_bytes": 0, "facade_bytes": 0},
        "automatic_stack_wbuf_bytes":
            int(rows["variant_a_automatic_wbuf_bytes"]),
        "symbol_slots_delta": 0, "namepool_bytes_delta": 0,
        "direct_fit": False,
        "required_followup": ("owner-priced relocation of at least 630 "
                              "ordinary-text bytes or an architectural split"),
    }


def variant_b(source: str, candidate: str, truth: ElfTruth,
              profile: dict[str, Any]) -> dict[str, Any]:
    baseline_sizes = compile_sizes(source)
    candidate_sizes = compile_sizes(candidate)
    require(baseline_sizes == {"%repl-read": 234, "%repl-step": 255,
                               "repl": 250},
            f"baseline Comfort object sizes drift: {baseline_sizes}")
    require(candidate_sizes == {"%repl-read": 234, "%repl-prompt": 80,
                                "%repl-step": 251, "repl": 250},
            f"fallback Comfort object sizes drift: {candidate_sizes}")
    byte_delta = sum(candidate_sizes.values()) - sum(baseline_sizes.values())
    require(byte_delta == 76, f"fallback library price drift: {byte_delta}")

    capacity = json.loads(CAPACITY.read_text(encoding="utf-8"))["capacity"]
    before = capacity["bias_adjusted_free"]
    name_cost = len("%repl-prompt") + 1
    after = {"symbol_slots": before["symbol_slots"] - 1,
             "namepool_bytes": before["namepool_bytes"] - name_cost}
    minimum = capacity["release_minimum"]
    require(after == {"symbol_slots": 32, "namepool_bytes": 581}
            and after["symbol_slots"] >= minimum["symbol_slots"]
            and after["namepool_bytes"] >= minimum["namepool_bytes"],
            f"fallback capacity floor drift: {after}")

    bulk = full_route("phase1b-bulk-reference", source, None)
    fallback = full_route(
        "phase1b-product-fallback-route", candidate, profile["delivered_ids"])
    require(bulk["stationary_steps"] == fallback["stationary_steps"] == 8945
            and bulk["stationary_screen_cells"]
            == fallback["stationary_screen_cells"] == 45,
            "fallback changed the stationary character service path")
    first_delta = (fallback["first_boundary_step"]
                   - bulk["first_boundary_step"])
    require(first_delta == 32, f"fallback prompt step price drift: {first_delta}")

    response = FINAL.derive(ELF)["responsiveness"]
    contract = json.loads(HYBRID_CONTRACT.read_text())["responsiveness"]
    stationary = (
        fallback["stationary_vm_steps_per_character"]
        * contract["calibration_cycles_per_vm_step"]
        / contract["cycles_per_frame"]
        + fallback["stationary_screen_cells"] / 40
        * contract["screen_cell_cycles"] / contract["cycles_per_frame"]
        + response["heap_cells_per_character"] * contract["collection_frames"]
        / contract["nursery_cells"]
        + response["linked_native_cycles_per_character"]
        / contract["cycles_per_frame"])
    stationary_rate = 1.0 / stationary
    stationary_margin = (stationary_rate - 1.0) * 100.0
    amortized = (stationary
                 + first_delta * contract["calibration_cycles_per_vm_step"]
                 / contract["cycles_per_frame"] / 40)
    rate = 1.0 / amortized
    margin = (rate - 1.0) * 100.0
    require(stationary <= contract["maximum_frames_per_character"]
            and stationary_rate >= contract["minimum_service_events_per_frame"]
            and stationary_margin >= contract["minimum_margin_percent"]
            and amortized <= contract["maximum_frames_per_character"]
            and rate >= contract["minimum_service_events_per_frame"]
            and margin >= contract["minimum_margin_percent"],
            "fallback responsiveness wall red")
    profile_gate = product_profile_gate(source, candidate, profile)
    return {
        "change": ("library-only capability helper: screen-bulk-p selects "
                   "screen-write-string or five screen-put-char fallback writes"),
        "product_bytes_delta": 0,
        "library": {"object_bytes_before": baseline_sizes,
                    "object_bytes_after": candidate_sizes,
                    "bank2_library_delta_bytes": byte_delta,
                    "new_private_names": ["%repl-prompt"],
                    "symbol_slots_delta": 1,
                    "namepool_bytes_delta": name_cost},
        "capacity": {"bias_adjusted_before": before,
                     "bias_adjusted_after": after,
                     "release_minimum": minimum,
                     "slot_margin": after["symbol_slots"]
                                    - minimum["symbol_slots"],
                     "namepool_margin_bytes": after["namepool_bytes"]
                                              - minimum["namepool_bytes"]},
        "responsiveness": {
            "bulk_reference": bulk, "product_fallback": fallback,
            "one_time_prompt_delta_vm_steps": first_delta,
            "stationary_frames_per_character": stationary,
            "stationary_service_events_per_frame": stationary_rate,
            "stationary_margin_percent": stationary_margin,
            "prior_final_world_reference_frames_per_character":
                response["frames_per_character"],
            "forty_character_prompt_amortized_frames_per_character": amortized,
            "forty_character_prompt_amortized_service_events_per_frame": rate,
            "forty_character_prompt_amortized_margin_percent": margin,
            "wall": contract,
        },
        "product_profile_qualification": profile_gate,
        "direct_fit": True,
        "watch": "exactly the 32-slot floor; no measured slot margin",
    }


def mutation_selftest(a: dict[str, Any], b: dict[str, Any]) -> dict[str, str]:
    rejected: dict[str, str] = {}
    mutations = {
        "pretend-a-fits": lambda: require(
            a["sealed_candidate"]["projected_facade_overrun_bytes"] <= 0,
            "A cannot fit the current ordinary-text arena"),
        "pin-bulk-host": lambda: require(
            b["product_profile_qualification"]["tombstone_rejection"] == "",
            "host qualification cannot ignore the product tombstone"),
        "hide-fallback-name": lambda: require(
            b["library"]["symbol_slots_delta"] == 0,
            "fallback private helper consumes one symbol slot"),
        "claim-stationary-drift": lambda: require(
            b["responsiveness"]["bulk_reference"]["stationary_steps"]
            != b["responsiveness"]["product_fallback"]["stationary_steps"],
            "prompt fallback is outside the stationary character path"),
        "erase-slot-floor": lambda: require(
            b["capacity"]["slot_margin"] > 0,
            "fallback has zero measured slot margin"),
    }
    for name, mutation in mutations.items():
        try:
            mutation()
        except PricingError as error:
            rejected[name] = str(error)
        else:
            raise PricingError(f"Phase 1b pricing mutation survived: {name}")
    return rejected


def derive() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    rows = parse_observation()
    source = COMFORT.read_text(encoding="utf-8")
    candidate = fallback_source(source)
    profile = DELIVERY.derive_profile(ELF)
    require(profile["tombstoned_ids"] == [1, 2, 12, 26, 27, 40],
            f"sealed product tombstone population drift: "
            f"{profile['tombstoned_ids']}")
    a = variant_a(truth, rows)
    b = variant_b(source, candidate, truth, profile)
    mutations = mutation_selftest(a, b)
    return {
        "format": FORMAT, "recorded_on": "2026-08-25",
        "status": "PASS: TWO PRICES BOUND; OWNER VARIANT CHOICE REQUIRED",
        "authority": {"commission": bind(PLAN),
                      "sealed_candidate_ELF": bind(ELF),
                      "paired_link_observation": bind(OBSERVATION),
                      "display_capacity_world": bind(CAPACITY)},
        "inputs": {"comfort": bind(COMFORT), "editor": bind(EDITOR),
                   "target_VM": bind(VM), "treewalk_eval": bind(EVAL),
                   "surface_delivery_profile": bind(PROFILE),
                   "hybrid_contract": bind(HYBRID_CONTRACT),
                   "pricing_driver": bind(Path(__file__).resolve()),
                   "product_callprim_delivery_gate": bind(
                       ROOT / "tools/host-lisp/"
                       "c2_product_callprim_delivery_gate.py"),
                   "host_VM": bind(ROOT / "tools/host-lisp/bytecode_p0.py"),
                   "host_suite_driver": bind(
                       ROOT / "tools/host-lisp/bytecode_p0_stdlib.py")},
        "product_callprim_profile": profile,
        "variants": {"A_deliver_primitive": a,
                     "B_shipped_fallback": b},
        "comparison": {
            "A": (
                "does not fit: "
                f"{a['sealed_candidate']['projected_facade_overrun_bytes']} "
                "ordinary-text bytes beyond the facade"
            ),
            "B": (
                "fits without product change; "
                f"{b['responsiveness']['stationary_margin_percent']:.2f}% "
                "stationary margin; zero slot margin"
            ),
            "price_winner": "B_shipped_fallback",
            "selection_authority": "owner Phase 1b touchpoint",
        },
        "permanent_rule": ("Host qualification of product-destined bytecode "
                           "consumes the final product primitive table, "
                           "including tombstones."),
        "verification": {"mutations_rejected": len(mutations),
                         "mutation_results": mutations,
                         "price_WPLTO_attempts":
                             int(rows["price_wplto_attempts"]),
                         "successful_price_links":
                             int(rows["successful_price_links"]),
                         "capacity_rejected_price_links":
                             int(rows["capacity_rejected_price_links"]),
                         "product_cards": 0, "product_sources_changed": 0,
                         "media_builds": 0, "device_contacts": 0},
        "claim_limit": ("Host/ELF price and product-profile qualification. "
                        "No variant is selected or implemented here."),
    }


def check_implemented_successor() -> None:
    require(OUT.is_file(), "Phase 1b pricing receipt absent")
    receipt = json.loads(OUT.read_text(encoding="utf-8"))
    require(isinstance(receipt, dict)
            and receipt.get("status")
                == "PASS: TWO PRICES BOUND; OWNER VARIANT CHOICE REQUIRED"
            and receipt.get("comparison", {}).get("price_winner")
                == "B_shipped_fallback",
            "Phase 1b pricing receipt identity drift")

    old_raw = era_blob(PRICING_COMMIT, COMFORT)
    old_source = old_raw.decode("utf-8")
    old_editor = era_blob(PRICING_COMMIT, EDITOR).decode("utf-8")
    current = COMFORT.read_text(encoding="utf-8")
    require(current == fallback_source(old_source),
            "implemented Variant B differs from the priced source transform")
    require(receipt["inputs"]["comfort"] == bind_raw(COMFORT, old_raw),
            "sealed pricing receipt lost its pricing-era Comfort input")

    profile = DELIVERY.derive_profile(ELF)
    qualification = product_profile_gate(old_source, current, profile, old_editor)
    variant = receipt["variants"]["B_shipped_fallback"]
    priced_qualification = variant["product_profile_qualification"]
    require(product_profile_claim(qualification)
            == product_profile_claim(priced_qualification),
            "implemented Variant-B product-profile semantic claim drift")
    require(isinstance(priced_qualification.get("fallback_steps"), int)
            and priced_qualification["fallback_steps"] > 0
            and isinstance(qualification.get("fallback_steps"), int)
            and qualification["fallback_steps"] > 0,
            "Variant-B sealed/current scheduling witnesses absent")
    require(compile_sizes(current) == variant["library"]["object_bytes_after"],
            "implemented Variant-B code-object price drift")

    implementation = json.loads(IMPLEMENTATION.read_text(encoding="utf-8"))
    require(implementation["authorization_commit"] == "65c3b76d"
            and implementation["pricing_commit"] == PRICING_COMMIT
            and implementation["selection_commit"] == "e890b5e8"
            and implementation["symbol_budget"]["bias_adjusted_free"]
                == {"symbol_slots": 32, "namepool_bytes": 581},
            "Variant-B implementation authority/capacity drift")


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--check":
        check_implemented_successor()
        print("v1.7 Comfort Phase 1b pricing: CHECK PASS")
        return 0
    value = derive()
    raw = canonical(value)
    require(len(sys.argv) == 1,
            "usage: c2_v17_comfort_phase1b_pricing.py [--check]")
    OUT.write_bytes(raw)
    print(value["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
