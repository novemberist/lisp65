#!/usr/bin/env python3
"""Permanent host gate for the 1.10 persistent-path performance freight.

The historical Link-82 resolver, compiler carrier, append model and window
state machine remain the ruler.  Only the post-require defstruct library is
overlaid with the current candidate artifact.  This is deliberately not a
delivery, device, release, or completion-time claim.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from decimal import Decimal, getcontext
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0_stdlib as STD  # noqa: E402
import c2_v16_defstruct_phase_a as PHASE_A  # noqa: E402


CONTRACT = ROOT / "config/c2-v110-persistent-performance.json"
PLAN = ROOT / "docs/planning/1.10-persistent-path-performance-work-plan.md"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.10-persistent-performance-receipt.json"
)
DRIVER = Path(__file__).resolve()
GATES = ROOT / "mk/gates.mk"
OWNER_COMMIT = "be23689f"
FORMAT = "lisp65-c2.3-v1.10-persistent-performance-v1"
RECORDED_ON = "2026-08-07"
getcontext().prec = 40


class PerformanceError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PerformanceError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def git_bind(commit: str, path: str) -> dict[str, Any]:
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout.decode().strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{path}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    return {"commit": full, "path": path, "bytes": len(raw), "sha256": sha(raw)}


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def json_pointer(value: Any, pointer: str) -> Any:
    require(pointer.startswith("/"), "budget JSON pointer must be absolute")
    current = value
    for raw in pointer[1:].split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        require(isinstance(current, dict) and key in current,
                f"budget JSON pointer absent: {pointer}")
        current = current[key]
    return current


def audit_contract(contract: dict[str, Any]) -> None:
    require(contract.get("format") ==
            "lisp65-c2-v110-persistent-performance-contract-v1",
            "1.10 contract format drift")
    require(contract.get("scope") == {
        "execution": "host-only",
        "placement": "Bank 2 library freight",
        "resident_delta_bytes": 0,
        "device_contacts": 0,
        "product_links": 0,
        "release_claim": False,
        "public_surface_claim": False,
        "packaging_deferred_to_release_block": True,
    }, "1.10 scope broadened")
    sacred = contract.get("sacred_contracts", {})
    require(sacred.get("persistent_appends") == 9
            and sacred.get("publish_last") is True
            and sacred.get("rollback_correct") is True
            and sacred.get("final_journal") == "CLEAR"
            and len(sacred.get("generated_entries", [])) == 9,
            "persistent correctness contract drift")
    price = contract.get("price", {})
    require(price.get("window_event_ceiling_frames") == 1
            and price.get("append_cycle_ceiling_frames") == 98
            and price.get("historical_cycles_per_vm_instruction") == 1100
            and price.get("target_cpu_hz") == 40000000
            and price.get("headline_seconds") == 180,
            "pricing constants drift")


def build_candidate(contract: dict[str, Any]) -> dict[str, Any]:
    candidate = contract["candidate"]
    suite_path = ROOT / candidate["suite"]
    integration_path = ROOT / candidate["integration_suite"]
    suite = STD._read_suite(str(suite_path))
    integration = STD._read_suite(str(integration_path))
    standalone = STD.check_suite(str(suite_path), suite)
    integrated = STD.check_suite(str(integration_path), integration)
    prefix = ROOT / candidate["artifact_prefix"]
    info = STD.emit_artifacts(
        str(suite_path), suite, str(prefix),
        base_addr=0, artifact_role="disk-lib",
    )
    manifest_path = prefix.with_suffix(".manifest.json")
    manifest = load(manifest_path)
    manifest_suite = Path(manifest["suite"])
    if not manifest_suite.is_absolute():
        manifest_suite = ROOT / manifest_suite
    require(manifest["artifact_role"] == "disk-lib"
            and manifest_suite.resolve() == suite_path.resolve(),
            "candidate artifact identity drift")
    return {
        "manifest_path": manifest_path,
        "manifest": manifest,
        "standalone": standalone,
        "integration": integrated,
        "emit": info,
    }


def candidate_sequence(manifest_path: Path, lane: str) -> dict[str, Any]:
    original = PHASE_A.install_published_libraries

    def install_candidate(
        carrier: Any, plane: Any, identities: dict[str, dict[str, Any]],
    ) -> tuple[dict[int, Any], set[int], dict[int, str], list[dict[str, Any]]]:
        runtime, macros, names, installed = original(carrier, plane, identities)
        overlay, overlay_macros, overlay_names = PHASE_A.manifest_directory(
            carrier.heap, manifest_path, identities,
            role="v1.10-current-defstruct-host-overlay",
        )
        runtime.update(overlay)
        macros.update(overlay_macros)
        names.update(overlay_names)
        return runtime, macros, names, installed

    PHASE_A.install_published_libraries = install_candidate
    try:
        return PHASE_A.sequence(lane)
    finally:
        PHASE_A.install_published_libraries = original


def count_sequence(value: dict[str, Any]) -> dict[str, int]:
    instructions = int(value["require"]["steps"])
    instructions += int(value["expansion"]["steps"])
    instructions += int(value["constructor"]["steps"])
    for row in value["forms"]:
        instructions += int(row["compiler_steps"])
        instructions += int(row.get("evaluation_steps", 0))
    return {
        "initial_windows": int(value["initial_window_schedule"]["event_count"]),
        "refills": int(value["refill_schedule"]["event_count"]),
        "window_events": (
            int(value["initial_window_schedule"]["event_count"])
            + int(value["refill_schedule"]["event_count"])
        ),
        "vm_instructions": instructions,
        "persistent_appends": sum(
            row.get("kind") == "persistent-definition" for row in value["forms"]
        ),
    }


def decimal_text(value: Decimal, places: int = 9) -> str:
    return format(value.quantize(Decimal(1).scaleb(-places)), "f")


def price_lane(
    counts: dict[str, int], constants: dict[str, Any], *,
    persistent_appends: int | None = None, charge_vm: bool = True,
) -> dict[str, Any]:
    hz = Decimal(str(constants["frame_hz"]))
    windows = int(counts["window_events"])
    appends = (int(counts["persistent_appends"])
               if persistent_appends is None else persistent_appends)
    vm_exact = Decimal(0)
    if charge_vm:
        vm_exact = (
            Decimal(int(counts["vm_instructions"]))
            * Decimal(int(constants["historical_cycles_per_vm_instruction"]))
            / Decimal(int(constants["target_cpu_hz"])) * hz
        )
    vm_frames = math.ceil(vm_exact)
    window_frames = windows * int(constants["window_event_ceiling_frames"])
    append_frames = appends * int(constants["append_cycle_ceiling_frames"])
    base = window_frames + append_frames + vm_frames
    margin = math.ceil(
        base * int(constants["safety_margin_numerator"])
        / int(constants["safety_margin_denominator"])
    )
    total = base + margin
    seconds = Decimal(total) / hz
    return {
        "window_frames": window_frames,
        "append_frames": append_frames,
        "ordinary_VM_frames": vm_frames,
        "base_frames": base,
        "margin_frames": margin,
        "total_frames": total,
        "exact_seconds": decimal_text(seconds),
        "operational_floor_seconds": math.ceil(seconds),
    }


def delta(before: int, after: int) -> dict[str, Any]:
    require(before > 0 and after >= 0, "invalid delta inputs")
    change = after - before
    return {
        "before": before,
        "after": after,
        "delta": change,
        "reduction_percent": decimal_text(
            Decimal(-change) * Decimal(100) / Decimal(before), 6
        ),
    }


def segments(value: dict[str, Any]) -> list[dict[str, Any]]:
    refills = {
        row["name"]: int(row["event_count"])
        for row in value["refill_schedule"]["segments"]
    }
    return [
        {
            "name": row["name"],
            "initial_windows": int(row["event_count"]),
            "refills": refills[row["name"]],
            "window_events": int(row["event_count"]) + refills[row["name"]],
        }
        for row in value["initial_window_schedule"]["segments"]
    ]


def behavioral_projection(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "require": value["require"]["result"],
        "form_kinds": [row["kind"] for row in value["forms"]],
        "generated_entries": [
            row["entry"] for row in value["forms"] if row.get("entry")
        ],
        "evaluated_results": [
            row["result"] for row in value["forms"] if "result" in row
        ],
        "last_successful_definition": value["last_successful_definition"],
        "constructor": value["constructor"]["result"],
        "final_images": value["final_counts"]["images"],
        "final_entries": value["final_counts"]["entries"],
        "final_roots": value["final_counts"]["roots"],
        "C2J": value["final_counts"]["C2J"],
    }


def core_receipt() -> dict[str, Any]:
    contract = load(CONTRACT)
    audit_contract(contract)
    phase = load(ROOT / contract["baseline"]["phase_a_receipt"])
    vm_cost = load(ROOT / contract["baseline"]["vm_cost_receipt"])
    baseline_manifest_path = ROOT / contract["baseline"]["defstruct_manifest"]
    baseline_manifest = load(baseline_manifest_path)
    built = build_candidate(contract)
    candidate_manifest = built["manifest"]
    windowed = candidate_sequence(built["manifest_path"], "windowed")
    direct = candidate_sequence(built["manifest_path"], "direct")
    require(
        behavioral_projection(windowed) == behavioral_projection(direct),
        "candidate windowed/direct semantics differ",
    )

    sacred = contract["sacred_contracts"]
    behavior = behavioral_projection(windowed)
    require(behavior == {
        "require": "t",
        "form_kinds": [
            "evaluated-expression",
            *(["persistent-definition"] * 9),
            "evaluated-expression",
        ],
        "generated_entries": sacred["generated_entries"],
        "evaluated_results": ["t", "t"],
        "last_successful_definition": "point-with-y",
        "constructor": "(point 3 4)",
        "final_images": 17,
        "final_entries": 766,
        "final_roots": 358,
        "C2J": "CLEAR",
    }, "candidate persistent semantics drift")

    baseline_counts = dict(vm_cost["exact_workload"])
    baseline_counts["window_events"] = (
        int(baseline_counts["initial_windows"])
        + int(baseline_counts["refills"])
    )
    require(baseline_counts == {
        "vm_instructions": 199573,
        "initial_windows": 12310,
        "refills": 13803,
        "persistent_appends": 9,
        "window_events": 26113,
    }, "bound 1.6 workload drift")
    candidate_counts = count_sequence(windowed)
    require_counts = {
        "initial_windows": int(
            phase["require_only_control"]["require"]["window_trace"]
            ["initial_window_count"]
        ),
        "refills": int(
            phase["require_only_control"]["require"]["window_trace"]
            ["refill_count"]
        ),
        "vm_instructions": int(
            phase["require_only_control"]["require"]["steps"]
        ),
        "persistent_appends": 0,
    }
    require_counts["window_events"] = (
        require_counts["initial_windows"] + require_counts["refills"]
    )
    require(
        candidate_counts["window_events"] > require_counts["window_events"]
        and candidate_counts["vm_instructions"] > require_counts["vm_instructions"]
        and windowed["require"]["window_trace"]
        == phase["windowed_sequence"]["require"]["window_trace"],
        "candidate changed the bound one-time require lane",
    )
    baseline_post = {
        name: int(baseline_counts[name]) - int(require_counts[name])
        for name in ("initial_windows", "refills", "window_events", "vm_instructions")
    }
    candidate_post = {
        name: int(candidate_counts[name]) - int(require_counts[name])
        for name in ("initial_windows", "refills", "window_events", "vm_instructions")
    }
    baseline_post["persistent_appends"] = 9
    candidate_post["persistent_appends"] = 9

    constants = contract["price"]
    prices = {
        "full_sequence": {
            "baseline": price_lane(baseline_counts, constants),
            "candidate": price_lane(candidate_counts, constants),
        },
        "post_require_definition": {
            "baseline": price_lane(baseline_post, constants),
            "candidate": price_lane(candidate_post, constants),
        },
    }
    require(
        prices["full_sequence"]["baseline"]["operational_floor_seconds"] == 788,
        "1.6 completed price was not reproduced",
    )

    base_external = int(baseline_manifest["external_image"]["bytes"])
    candidate_external = int(candidate_manifest["external_image"]["bytes"])
    budget = contract["budget"]
    headroom_authority = load(ROOT / budget["bank2_headroom_authority"])
    headroom = int(json_pointer(
        headroom_authority, budget["bank2_headroom_json_pointer"]
    ))
    external_delta = candidate_external - base_external
    remaining = headroom - external_delta
    require(external_delta > 0
            and remaining >= int(budget["minimum_preserved_headroom_bytes"]),
            "candidate Bank-2 freight exceeds budget")

    baseline_generated_bytes = sum(
        int(row["code"]["encoded_bytes"])
        for row in phase["windowed_sequence"]["forms"]
    )
    candidate_generated_bytes = sum(
        int(row["code"]["encoded_bytes"]) for row in windowed["forms"]
    )
    headline = int(constants["headline_seconds"])
    append_batch_post = price_lane(
        candidate_post, constants, persistent_appends=1
    )
    zero_dispatch_post = price_lane(candidate_post, constants, charge_vm=False)

    value = {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "HOST-CLOSED-MATERIAL-REDUCTION; HEADLINE-NOT-REACHED",
        "scope": deepcopy(contract["scope"]),
        "authorities": {
            "owner_commission": git_bind(
                OWNER_COMMIT,
                "docs/planning/1.10-persistent-path-performance-work-plan.md",
            ),
            "contract": bind(CONTRACT),
            "closing_plan": bind(PLAN),
            "phase_A_baseline": bind(
                ROOT / contract["baseline"]["phase_a_receipt"]
            ),
            "VM_cost_baseline": bind(
                ROOT / contract["baseline"]["vm_cost_receipt"]
            ),
            "baseline_defstruct_manifest": bind(baseline_manifest_path),
            "candidate_source": bind(ROOT / contract["candidate"]["source"]),
            "candidate_suite": bind(ROOT / contract["candidate"]["suite"]),
            "integration_suite": bind(
                ROOT / contract["candidate"]["integration_suite"]
            ),
            "candidate_manifest": bind(built["manifest_path"]),
            "bank2_headroom": bind(ROOT / budget["bank2_headroom_authority"]),
            "phase_A_driver": bind(ROOT / "tools/host-lisp/c2_v16_defstruct_phase_a.py"),
            "driver": bind(DRIVER),
            "gate_wiring": bind(GATES),
        },
        "host_execution": {
            "standalone_cases": int(built["standalone"]["cases"]),
            "standalone_steps": int(built["standalone"]["steps"]),
            "integration_cases": int(built["integration"]["cases"]),
            "integration_steps": int(built["integration"]["steps"]),
            "windowed_direct_behavior_byteidentical": True,
            "behavior_projection": behavior,
            "window_schedule_sha256": sha(canonical({
                "initial": windowed["initial_window_schedule"]["sha256"],
                "refill": windowed["refill_schedule"]["sha256"],
            })),
            "segments": segments(windowed),
        },
        "freight": {
            "resident_delta_bytes": 0,
            "baseline": {
                "objects": len(baseline_manifest["entries"]),
                "code_bytes": int(baseline_manifest["code_bytes"]),
                "directory_bytes": int(baseline_manifest["directory_bytes"]),
                "external_image_bytes": base_external,
            },
            "candidate": {
                "objects": len(candidate_manifest["entries"]),
                "code_bytes": int(candidate_manifest["code_bytes"]),
                "directory_bytes": int(candidate_manifest["directory_bytes"]),
                "external_image_bytes": candidate_external,
            },
            "delta": {
                "objects": len(candidate_manifest["entries"])
                - len(baseline_manifest["entries"]),
                "code_bytes": int(candidate_manifest["code_bytes"])
                - int(baseline_manifest["code_bytes"]),
                "directory_bytes": int(candidate_manifest["directory_bytes"])
                - int(baseline_manifest["directory_bytes"]),
                "external_image_bytes": external_delta,
            },
            "bank2_headroom_before_bytes": headroom,
            "bank2_headroom_after_delta_bytes": remaining,
            "minimum_preserved_headroom_bytes": int(
                budget["minimum_preserved_headroom_bytes"]
            ),
        },
        "workload": {
            "one_time_require": require_counts,
            "full_sequence": {
                "baseline": baseline_counts,
                "candidate": candidate_counts,
                "window_event_delta": delta(
                    baseline_counts["window_events"],
                    candidate_counts["window_events"],
                ),
                "VM_instruction_delta": delta(
                    baseline_counts["vm_instructions"],
                    candidate_counts["vm_instructions"],
                ),
            },
            "post_require_definition": {
                "baseline": baseline_post,
                "candidate": candidate_post,
                "window_event_delta": delta(
                    baseline_post["window_events"],
                    candidate_post["window_events"],
                ),
                "VM_instruction_delta": delta(
                    baseline_post["vm_instructions"],
                    candidate_post["vm_instructions"],
                ),
            },
            "generated_definition_bytes": delta(
                baseline_generated_bytes, candidate_generated_bytes
            ),
        },
        "pricing": {
            **prices,
            "full_sequence_floor_delta_seconds": (
                prices["full_sequence"]["candidate"]
                ["operational_floor_seconds"]
                - prices["full_sequence"]["baseline"]
                ["operational_floor_seconds"]
            ),
            "post_require_floor_delta_seconds": (
                prices["post_require_definition"]["candidate"]
                ["operational_floor_seconds"]
                - prices["post_require_definition"]["baseline"]
                ["operational_floor_seconds"]
            ),
            "historical_observation_alignment": {
                "seconds": headline,
                "starts_after_defstruct_submission": True,
                "aligned_lane": "post_require_definition",
                "full_788_second_lane_contains_pre-submission_require": True,
                "candidate_below_observation_window": (
                    prices["post_require_definition"]["candidate"]
                    ["operational_floor_seconds"] < headline
                ),
            },
            "claim": (
                "Conservative structural price, not target wall time and not a "
                "completion upper bound. The post-require split aligns the price "
                "with the historical observation clock; it does not rewrite the "
                "bound 788-second full-sequence baseline."
            ),
        },
        "lever_disposition": {
            "generated_body_factoring": {
                "status": "implemented",
                "mechanism": (
                    "predicate, copy, reader, setter and functional-update "
                    "semantics live once in the Bank-2 library; each generated "
                    "persistent function is a small call wrapper"
                ),
                "publish_last_preserved": True,
                "rollback_correctness_preserved": True,
            },
            "append_batching": {
                "status": "rejected",
                "maximum_shared_cycles_removed": 8,
                "maximum_base_frames_removed": 8 * int(
                    constants["append_cycle_ceiling_frames"]
                ),
                "post_require_floor_if_one_append_cycle_seconds": (
                    append_batch_post["operational_floor_seconds"]
                ),
                "reaches_headline": (
                    append_batch_post["operational_floor_seconds"] < headline
                ),
                "reason": (
                    "even the impossible best case remains above 180 seconds; "
                    "changing nine independently publish-last definitions into "
                    "one transaction would renegotiate rollback/visibility"
                ),
            },
            "VM_dispatch": {
                "status": "not-pursued-nondominant",
                "post_require_floor_with_zero_dispatch_charge_seconds": (
                    zero_dispatch_post["operational_floor_seconds"]
                ),
                "reaches_headline": (
                    zero_dispatch_post["operational_floor_seconds"] < headline
                ),
                "reason": "removing the entire priced VM term cannot reach 180 seconds",
            },
            "window_geometry": {
                "status": "rejected",
                "reason": (
                    "a larger VM_CODEBUF consumes resident state; the block's "
                    "zero-resident wall forbids it"
                ),
            },
            "compiler_carrier_wide_rewrite": {
                "status": "deferred-separate-scope",
                "reason": (
                    "remaining events are dominated by shared compiler/prelude "
                    "helpers; changing them is cross-surface compiler freight, not "
                    "a defstruct-local lever, and needs its own carrier-equivalence "
                    "and release-cycle authority"
                ),
            },
        },
        "decision": {
            "material_reduction_achieved": True,
            "headline_under_180_seconds_achieved": False,
            "candidate_retained_for_next_release_block": True,
            "release_recommendation": (
                "carry the Bank-2 defstruct factoring into the next ordinary "
                "release block beside comfort freight and the editor known-issue "
                "correction; obtain normal product/link/device acceptance there"
            ),
            "further_performance_recommendation": (
                "if sub-180 remains a priority, commission a compiler-carrier "
                "locality block; append batching and VM-dispatch pricing cannot "
                "close the remaining gap"
            ),
        },
        "accounting": {
            "product_bytes_changed": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "device_contacts": 0,
        },
        "claim_limit": (
            "This proves a host-executed semantic-preserving candidate and prices "
            "its structural deltas against the bound Link-82 reconstruction. It "
            "does not claim target duration, completion, delivery, packaging, a "
            "release, public surface, product bytes, a link, or hardware acceptance."
        ),
    }
    return value


def recompute_price_from_receipt(
    value: dict[str, Any], lane: str, side: str,
) -> dict[str, Any]:
    contract = load(CONTRACT)
    counts = value["workload"][lane][side]
    return price_lane(counts, contract["price"])


def audit_result(value: dict[str, Any]) -> None:
    contract = load(CONTRACT)
    audit_contract(contract)
    require(value.get("format") == FORMAT
            and value.get("status") ==
            "HOST-CLOSED-MATERIAL-REDUCTION; HEADLINE-NOT-REACHED",
            "performance result identity drift")
    require(value.get("scope") == contract["scope"], "result scope drift")
    require(value.get("accounting") == {
        "product_bytes_changed": 0,
        "product_links": 0,
        "hardware_runs": 0,
        "device_contacts": 0,
    }, "host-only accounting drift")
    behavior = value["host_execution"]["behavior_projection"]
    require(behavior["generated_entries"] ==
            contract["sacred_contracts"]["generated_entries"]
            and behavior["constructor"] == "(point 3 4)"
            and behavior["evaluated_results"] == ["t", "t"]
            and behavior["C2J"] == "CLEAR"
            and value["host_execution"]["windowed_direct_behavior_byteidentical"]
            and value["host_execution"]["integration_cases"] >= 14,
            "candidate semantic closure drift")
    for lane in ("full_sequence", "post_require_definition"):
        row = value["workload"][lane]
        for side in ("baseline", "candidate"):
            require(row[side]["window_events"] ==
                    row[side]["initial_windows"] + row[side]["refills"],
                    f"{lane} count closure drift")
            require(value["pricing"][lane][side] ==
                    recompute_price_from_receipt(value, lane, side),
                    f"{lane} price closure drift")
        require(row["window_event_delta"] == delta(
            row["baseline"]["window_events"], row["candidate"]["window_events"]
        ), f"{lane} window delta drift")
        require(row["VM_instruction_delta"] == delta(
            row["baseline"]["vm_instructions"],
            row["candidate"]["vm_instructions"],
        ), f"{lane} VM delta drift")
    require(value["workload"]["full_sequence"]["candidate"]
            ["persistent_appends"] == 9
            and value["workload"]["post_require_definition"]["candidate"]
            ["persistent_appends"] == 9,
            "append-count contract drift")
    freight = value["freight"]
    require(freight["resident_delta_bytes"] == 0
            and freight["delta"]["code_bytes"] ==
            freight["candidate"]["code_bytes"] - freight["baseline"]["code_bytes"]
            and freight["delta"]["directory_bytes"] ==
            freight["candidate"]["directory_bytes"]
            - freight["baseline"]["directory_bytes"]
            and freight["delta"]["external_image_bytes"] ==
            freight["candidate"]["external_image_bytes"]
            - freight["baseline"]["external_image_bytes"]
            and freight["bank2_headroom_after_delta_bytes"] ==
            freight["bank2_headroom_before_bytes"]
            - freight["delta"]["external_image_bytes"]
            and freight["bank2_headroom_after_delta_bytes"] >=
            freight["minimum_preserved_headroom_bytes"],
            "Bank-2 freight closure drift")
    aligned = value["pricing"]["historical_observation_alignment"]
    candidate_floor = value["pricing"]["post_require_definition"]
    candidate_floor = candidate_floor["candidate"]["operational_floor_seconds"]
    require(aligned["aligned_lane"] == "post_require_definition"
            and aligned["starts_after_defstruct_submission"] is True
            and aligned["candidate_below_observation_window"]
            == (candidate_floor < int(contract["price"]["headline_seconds"])),
            "180-second comparison drift")
    require(value["decision"] == {
        "material_reduction_achieved": True,
        "headline_under_180_seconds_achieved": False,
        "candidate_retained_for_next_release_block": True,
        "release_recommendation": (
            "carry the Bank-2 defstruct factoring into the next ordinary "
            "release block beside comfort freight and the editor known-issue "
            "correction; obtain normal product/link/device acceptance there"
        ),
        "further_performance_recommendation": (
            "if sub-180 remains a priority, commission a compiler-carrier "
            "locality block; append batching and VM-dispatch pricing cannot "
            "close the remaining gap"
        ),
    }, "closing decision drift")
    levers = value["lever_disposition"]
    require(levers["generated_body_factoring"]["status"] == "implemented"
            and levers["generated_body_factoring"]["publish_last_preserved"]
            and levers["generated_body_factoring"]["rollback_correctness_preserved"]
            and levers["append_batching"]["status"] == "rejected"
            and levers["append_batching"]["reaches_headline"] is False
            and levers["VM_dispatch"]["status"] == "not-pursued-nondominant"
            and levers["VM_dispatch"]["reaches_headline"] is False
            and levers["window_geometry"]["status"] == "rejected"
            and levers["compiler_carrier_wide_rewrite"]["status"]
            == "deferred-separate-scope",
            "lever disposition drift")


def rejected(
    label: str, value: dict[str, Any], mutate: Callable[[dict[str, Any]], None],
    result: dict[str, str],
) -> None:
    candidate = deepcopy(value)
    mutate(candidate)
    try:
        audit_result(candidate)
    except PerformanceError as error:
        result[label] = str(error)
    else:
        raise PerformanceError(f"performance mutation survived: {label}")


def mutation_proof(value: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    tests: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("format", lambda x: x.__setitem__("format", "wrong")),
        ("resident-byte", lambda x: x["freight"].__setitem__(
            "resident_delta_bytes", 1)),
        ("device-contact", lambda x: x["accounting"].__setitem__(
            "device_contacts", 1)),
        ("product-link", lambda x: x["accounting"].__setitem__(
            "product_links", 1)),
        ("release-claim", lambda x: x["scope"].__setitem__(
            "release_claim", True)),
        ("public-surface-claim", lambda x: x["scope"].__setitem__(
            "public_surface_claim", True)),
        ("journal-not-clear", lambda x: x["host_execution"]
         ["behavior_projection"].__setitem__("C2J", "ACTIVE")),
        ("constructor-semantics", lambda x: x["host_execution"]
         ["behavior_projection"].__setitem__("constructor", "nil")),
        ("generated-entry", lambda x: x["host_execution"]
         ["behavior_projection"]["generated_entries"].pop()),
        ("integration-case", lambda x: x["host_execution"].__setitem__(
            "integration_cases", 13)),
        ("append-count", lambda x: x["workload"]["full_sequence"]
         ["candidate"].__setitem__("persistent_appends", 8)),
        ("window-count", lambda x: x["workload"]["full_sequence"]
         ["candidate"].__setitem__("window_events", 1)),
        ("price", lambda x: x["pricing"]["full_sequence"]["candidate"]
         .__setitem__("operational_floor_seconds", 1)),
        ("code-freight", lambda x: x["freight"]["delta"].__setitem__(
            "code_bytes", 0)),
        ("external-freight", lambda x: x["freight"]["delta"].__setitem__(
            "external_image_bytes", 0)),
        ("bank2-headroom", lambda x: x["freight"].__setitem__(
            "bank2_headroom_after_delta_bytes", 1)),
        ("headline-overclaim", lambda x: x["decision"].__setitem__(
            "headline_under_180_seconds_achieved", True)),
        ("publish-last", lambda x: x["lever_disposition"]
         ["generated_body_factoring"].__setitem__("publish_last_preserved", False)),
        ("rollback", lambda x: x["lever_disposition"]
         ["generated_body_factoring"].__setitem__(
             "rollback_correctness_preserved", False)),
        ("append-batching", lambda x: x["lever_disposition"]
         ["append_batching"].__setitem__("status", "implemented")),
        ("VM-dominance", lambda x: x["lever_disposition"]
         ["VM_dispatch"].__setitem__("status", "implemented")),
        ("resident-window-growth", lambda x: x["lever_disposition"]
         ["window_geometry"].__setitem__("status", "implemented")),
    ]
    for label, mutate in tests:
        rejected(label, value, mutate, result)
    require(len(result) == len(tests), "mutation execution count drift")
    return result


def derive() -> dict[str, Any]:
    value = core_receipt()
    audit_result(value)
    value["mutations_rejected"] = mutation_proof(value)
    return value


def audit(value: dict[str, Any]) -> None:
    audit_result(value)
    require(len(value.get("mutations_rejected", {})) == 22,
            "mutation closure drift")
    current = derive()
    require(value == current,
            "1.10 performance receipt differs from current host execution")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "check", "selftest"))
    args = parser.parse_args()
    try:
        if args.action == "selftest":
            audit_contract(load(CONTRACT))
            value = load(RECEIPT)
            audit_result(value)
            mutations = mutation_proof(value)
            require(len(mutations) == 22, "selftest mutation count drift")
            print("c2-v110-persistent-performance: SELFTEST PASS mutations=22")
            return 0
        if args.action == "run":
            value = derive()
            write_json(RECEIPT, value)
        else:
            value = load(RECEIPT)
            audit(value)
        full = value["pricing"]["full_sequence"]
        post = value["pricing"]["post_require_definition"]
        freight = value["freight"]["delta"]
        print(
            "c2-v110-persistent-performance: PASS "
            f"full={full['baseline']['operational_floor_seconds']}->"
            f"{full['candidate']['operational_floor_seconds']}s "
            f"post-require={post['baseline']['operational_floor_seconds']}->"
            f"{post['candidate']['operational_floor_seconds']}s "
            f"bank2-code={freight['code_bytes']:+d} "
            f"external={freight['external_image_bytes']:+d} resident=0"
        )
        return 0
    except (PerformanceError, KeyError, TypeError, ValueError) as error:
        print(f"c2-v110-persistent-performance: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
