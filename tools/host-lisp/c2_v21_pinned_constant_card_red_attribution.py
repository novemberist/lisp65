#!/usr/bin/env python3
"""Attribute the Final Red of the sole pinned-constant-sweep card."""

from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_f1_published_value_call_wplto as F1  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v2.1-pinned-constant-card/wplto"
ELF = BUILD / "lisp65-c2-substitution-linked.prg.elf"
SCRATCH = BUILD / (
    "fresh-c2-lite-prelink-gates/bank2-target-stage/"
    "current-workbench-overlay.bin")
FINAL_RED = ARCH / "c2.3-v2.1-pinned-constant-card-final-red.json"
SWEEP = ARCH / "c2.3-v2.1-pinned-constant-sweep-receipt.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-pinned-constant-card-red-attribution-receipt.json")
CARD_DRIVER = HOST / "c2_v21_pinned_constant_card.py"
SWEEP_DRIVER = HOST / "c2_v21_pinned_constant_sweep.py"
WRAPPER = HOST / "c2_lite_v6_bank2_target_stage_successor_link.py"
CANONICAL = HOST / "c2_lite_canonical_product.py"
F1_DRIVER = Path(F1.__file__).resolve()
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
RECORDED_ON = "2026-08-14"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def function(text: str, name: str) -> ast.FunctionDef:
    nodes = [node for node in ast.walk(ast.parse(text))
             if isinstance(node, ast.FunctionDef) and node.name == name]
    require(len(nodes) == 1, f"unique function absent: {name}")
    return nodes[0]


def derive() -> dict[str, Any]:
    red = load(FINAL_RED)
    sweep = load(SWEEP)
    require(
        red.get("status") ==
            "FINAL RED: sole pinned-constant card returns to owner"
        and red.get("retry_authorized") is False
        and red.get("owner_disposition_required") is True
        and red["attempt_accounting"] == {
            "replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_link_attempts": 1, "media_builds": 0,
            "device_contacts": 0}
        and sweep.get("status") ==
            "PASS: remaining qualification constants candidate-derived; pinned=0"
        and sweep["sweep"]["pinned_count"] == 0
        and sweep["sweep"]["expectation_count"] == 14,
        "pinned card/sweep disposition drift")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=True)
    binding = truth.section(".lisp65_runtime_overlay_verifier_bindings")
    publish = load(BUILD / "runtime-verifier-publish-last.json")
    kernal = load(BUILD / "kernal-freedom-link.json")
    flow = kernal["control_flow_ownership"]
    require(
        (binding.address, binding.bytes) == (0xB98C, 40)
        and publish["status"] == "passed"
        and publish["address"] == publish["expected_address"] == 0xB98C
        and flow["violations"] == []
        and flow["same_function_basic_block_jumps"] == 181,
        "candidate stage/ownership was not green before the Final Red")

    f1_source = F1_DRIVER.read_text(encoding="utf-8")
    wrapper_source = WRAPPER.read_text(encoding="utf-8")
    canonical_source = CANONICAL.read_text(encoding="utf-8")
    sweep_source = SWEEP_DRIVER.read_text(encoding="utf-8")
    target = function(f1_source, "bank2_target_fixture")
    target_text = ast.unparse(target)
    require(
        "len(scratch) <= min(1792, static_bytes)" in target_text
        and "B.target_fixture(REPLAY.fixture_product())" in wrapper_source
        and "BANK2_REPLAY.B.target_fixture = fresh_bank2_target_fixture"
            in canonical_source
        and "CAN.fresh_bank2_target_fixture = bank2_target_fixture"
            in f1_source,
        "transitive F1 helper/size ceiling source mechanism drift")

    fixture = F1.bank2_fixture_product()["host_c2d_v6"]["artifacts"]
    expected_path = ROOT / fixture["code"]["path"]
    actual_binding = F1.bind(expected_path)
    expected_bytes = expected_path.stat().st_size
    scratch_bytes = SCRATCH.stat().st_size
    predicates = {
        "fixture_artifact_binding_equal": actual_binding == fixture["code"],
        "fixture_plane_length_equal": expected_bytes == fixture["code"]["bytes"],
        "scratch_nonempty": scratch_bytes > 0,
        "scratch_within_historical_1792_ceiling":
            scratch_bytes <= min(1792, expected_bytes),
    }
    require(predicates == {
        "fixture_artifact_binding_equal": True,
        "fixture_plane_length_equal": True,
        "scratch_nonempty": True,
        "scratch_within_historical_1792_ceiling": False,
    } and expected_bytes == 34748 and scratch_bytes == 1851,
            "F1 fixture predicate attribution drift")

    swept_sources = set(sweep["authority"]["sources"])
    require("f1" not in swept_sources
            and F1_DRIVER.name not in sweep_source,
            "historical sweep unexpectedly covered the F1 helper")
    return {
        "format": "lisp65-c2.3-v2.1-pinned-card-red-attribution-v1",
        "recorded_on": RECORDED_ON,
        "status": (
            "ATTRIBUTED FINAL RED: transitive F1 helper pins overlay-size ceiling"),
        "authority": {"final_red": bind(FINAL_RED), "sweep": bind(SWEEP),
            "ELF": bind(ELF), "scratch": bind(SCRATCH),
            "card_driver": bind(CARD_DRIVER),
            "sweep_driver": bind(SWEEP_DRIVER), "wrapper": bind(WRAPPER),
            "canonical_configurator": bind(CANONICAL),
            "F1_consumer": bind(F1_DRIVER), "driver": bind(DRIVER)},
        "authorized_work_result": {
            "specific_candidate_stage_address": "0xb98c",
            "candidate_stage_address_green": True,
            "candidate_stage_bytes": binding.bytes,
            "publish_last_status": publish["status"],
            "ownership_violations": 0,
            "same_function_basic_block_jumps": 181,
            "resident_reserve_bytes": 24,
        },
        "new_final_red": {
            "class": "TRANSITIVE-HELPER-PINNED-SIZE-CEILING",
            "reached_consumer": (
                "c2_f1_published_value_call_wplto.bank2_target_fixture"),
            "call_chain": [
                "c2_lite_v6_bank2_target_stage_successor_link.replacement",
                "B.target_fixture(REPLAY.fixture_product())",
                "c2_f1_published_value_call_wplto.bank2_target_fixture"],
            "predicate": "0 < len(scratch) <= min(1792, static_bytes)",
            "fixture_plane_bytes": expected_bytes,
            "actual_workbench_overlay_bytes": scratch_bytes,
            "historical_ceiling_bytes": 1792,
            "over_ceiling_bytes": scratch_bytes - 1792,
            "predicate_results": predicates,
            "artifact_identity_implicated": False,
            "product_geometry_implicated": False,
            "product_link_completed": True,
            "mechanism": (
                "The linked candidate reached the F1 target-fixture helper "
                "through a monkey-patched transitive call.  Its artifact "
                "binding and plane length both match.  Only the inherited "
                "1,792-byte Workbench-overlay ceiling rejects the candidate's "
                "1,851-byte overlay."),
        },
        "sweep_correction": {
            "historical_receipt_rewritten": False,
            "retracted_claims": [
                "complete remaining qualification-path enumeration",
                "pinned_count=0 over the complete reachable path",
                "no later card can discover this class"],
            "surviving_claims": [
                "the fourteen enumerated direct expectations are candidate-derived",
                "seven directly enumerated historical pins were converted or retired",
                "the concrete B9CD-to-B98C stage repair is linked green"],
            "omission": (
                "The sweep enumerated selected function bodies in seven source "
                "modules but did not close the reachable call graph or execute "
                "the real qualification consumer before arming the card."),
            "required_class_answer": (
                "Any renewed sweep must enumerate expectations transitively "
                "through the actual configured call graph and run the real "
                "qualification consumer; function-local AST closure is not a "
                "complete path closure."),
        },
        "card_disposition": {"replacement_card_consumed": True,
            "retry_authorized": False, "owner_disposition_required": True,
            "completion_promotion_allowed": False, "media_allowed": False,
            "device_allowed": False},
        "attempt_accounting": red["attempt_accounting"],
        "claim_limit": (
            "Read-only attribution and loud correction of the overbroad sweep "
            "claim. No helper fix, retry, completion, media or device action is "
            "authorized."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value == derive(), "pinned-card Final Red attribution drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "blame-artifact-binding": lambda x: x["new_final_red"].update(
            artifact_identity_implicated=True),
        "hide-size-red": lambda x: x["new_final_red"]["predicate_results"].update(
            scratch_within_historical_1792_ceiling=True),
        "erase-overrun": lambda x: x["new_final_red"].update(
            over_ceiling_bytes=0),
        "preserve-complete-sweep-claim": lambda x: x["sweep_correction"].update(
            retracted_claims=[]),
        "rewrite-historical-receipt": lambda x: x["sweep_correction"].update(
            historical_receipt_rewritten=True),
        "blame-product-geometry": lambda x: x["new_final_red"].update(
            product_geometry_implicated=True),
        "authorize-retry": lambda x: x["card_disposition"].update(
            retry_authorized=True),
        "allow-media": lambda x: x["card_disposition"].update(
            media_allowed=True),
        "claim-device": lambda x: x["attempt_accounting"].update(
            device_contacts=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases),
            "pinned-card attribution mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "pinned-card attribution receipt exists")
    value = derive(); validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 pinned-card red attribution: PASS scratch=1851 ceiling=1792 "
          "sweep=corrected mutations=9 retry=none")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value)
    require(rejected == mutations(value),
            "pinned-card attribution mutation set drift")
    print("2.1 pinned-card red attribution: CHECK PASS scratch=1851 "
          "ceiling=1792 sweep=corrected retry=none")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check"),
            "usage: c2_v21_pinned_constant_card_red_attribution.py record|check")
    {"record": record, "check": check}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"2.1 pinned-card red attribution: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
