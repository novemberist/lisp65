#!/usr/bin/env python3
"""Close the post-v1.4 defstruct completion-edge desk question.

This gate replays the delivered 1.11 compiler carrier through the exact 1.6
reconstruction, prices each post-require prefix, and binds the terminal red
sink in the immutable Link-92-r5 product.  It deliberately stops before a
root-cause claim: the Phase-D receipt contains no stopped-state evidence.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth, ElfTruthError  # noqa: E402
import c2_v110_persistent_performance as V110  # noqa: E402
import c2_v111_compiler_locality as V111  # noqa: E402
import c2_v16_defstruct_phase_b as PHASE_B  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / "c2.3-post-v1.4-defstruct-completion-edge-receipt.json"
D2_RECEIPT = EVIDENCE / "c2.3-v1.12-link92-r5-phase-d-d2-device-receipt.json"
PHASE_B_RECEIPT = EVIDENCE / "c2.3-v1.6-defstruct-phase-b-guard-partition-receipt.json"
SHADOW_RECEIPT = EVIDENCE / "c2.3-v1.6-defstruct-pre-rollback-shadow-result-first-red-receipt.json"
RING_RECEIPT = EVIDENCE / "c2.3-v1.6-defstruct-vm-progress-noninterference-receipt.json"
MANIFEST = ROOT / "build/c2.3/v1.4.0-candidate-product-link92-r5/canonical-product-manifest.json"
ELF = ROOT / "build/c2.3/v1.4.0-candidate-product-link92-r5/final/lisp65-c2-substitution-linked.prg.elf"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
PLAN = ROOT / "docs/planning/post-v1.4.0-direction-plan.md"
REGISTER = ROOT / "docs/reference/parked-items-register.md"
GATES = ROOT / "mk/gates.mk"
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2.3-post-v1.4-defstruct-completion-edge-v1"
RECORDED_ON = "2026-08-09"


class CompletionEdgeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CompletionEdgeError(message)


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


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def symbol_bytes(truth: ElfTruth, name: str, *, unsized: int = 0) -> bytes:
    symbol = truth.symbol(name)
    size = symbol.bytes or unsized
    require(size > 0, f"sized symbol required: {name}")
    section = truth.section(symbol.section)
    data = truth.section_bytes(symbol.section)
    begin = symbol.value - section.address
    require(0 <= begin and begin + size <= len(data),
            f"symbol outside section: {name}")
    return data[begin:begin + size]


def gate_wiring_projection() -> dict[str, Any]:
    text = GATES.read_text(encoding="utf-8")
    rows = [
        "c2-defstruct-completion-edge-selftest:",
        "python3 tools/host-lisp/c2_defstruct_completion_edge.py selftest",
        "c2-defstruct-completion-edge-check: c2-defstruct-completion-edge-selftest c2-v111-compiler-locality-check",
        "python3 tools/host-lisp/c2_defstruct_completion_edge.py check",
        "check-source: c2-defstruct-completion-edge-check",
    ]
    require(all(row in text for row in rows),
            "completion-edge permanent gate wiring absent")
    return {"path": "mk/gates.mk", "semantic_projection": rows}


def documentation_projection() -> dict[str, Any]:
    plan = PLAN.read_text(encoding="utf-8")
    register = REGISTER.read_text(encoding="utf-8")
    plan_rows = [
        "Priority-2 desk result — completion edge closed",
        "persistent append is structurally complete at prefix floor 172 s",
        "second source-less IRQ episode",
        "target-owned self-sampling ring with the current-carrier R/A/I/G record",
    ]
    register_rows = [
        "P2 DESK CLOSED 2026-08-09",
        "completion-edge append hypothesis is desk-falsified",
        "current-carrier terminal-ingress ring",
    ]
    require(all(row in plan for row in plan_rows),
            "direction-plan completion-edge projection absent")
    require(all(row in register for row in register_rows),
            "parked-register completion-edge projection absent")
    return {"plan": plan_rows, "register": register_rows}


def append_plans(manifest: dict[str, Any]) -> dict[str, list[int]]:
    plans = manifest["WPLTO"]["historical_checker_boundary"] \
        ["current_replacement_gates"]["append_phase_plan"]["plan_data"]
    names = {
        "stage": "lisp65_c2_append_stage_plan",
        "persistent_publish": "lisp65_c2_append_persistent_publish_plan",
        "rollback": "lisp65_c2_append_rollback_plan",
    }
    return {short: [int(x) for x in plans[name]["bytes"]]
            for short, name in names.items()}


def price_prefix(counts: dict[str, int], constants: dict[str, Any]) -> dict[str, Any]:
    priced = V110.price_lane(counts, constants)
    return {
        "window_events": counts["window_events"],
        "vm_instructions": counts["vm_instructions"],
        "persistent_appends": counts["persistent_appends"],
        "exact_seconds": priced["exact_seconds"],
        "operational_floor_seconds": priced["operational_floor_seconds"],
    }


def completion_timeline(sequence: dict[str, Any], constants: dict[str, Any]) -> list[dict[str, Any]]:
    segments = {row["name"]: row for row in V110.segments(sequence)}
    counts = {
        "initial_windows": 0,
        "refills": 0,
        "window_events": 0,
        "vm_instructions": 0,
        "persistent_appends": 0,
    }
    result: list[dict[str, Any]] = []

    def add(name: str, steps: int, *, append: bool = False,
            semantic_edge: str | None = None) -> None:
        row = segments[name]
        counts["initial_windows"] += int(row["initial_windows"])
        counts["refills"] += int(row["refills"])
        counts["window_events"] += int(row["window_events"])
        counts["vm_instructions"] += int(steps)
        if append:
            counts["persistent_appends"] += 1
        item = {"segment": name, **price_prefix(counts, constants)}
        if semantic_edge is not None:
            item["semantic_edge"] = semantic_edge
        result.append(item)

    add("defstruct-macro-expansion", int(sequence["expansion"]["steps"]))
    for index, form in enumerate(sequence["forms"]):
        add(f"form-{index}-compile", int(form["compiler_steps"]),
            append=form["kind"] == "persistent-definition",
            semantic_edge=(
                f"persistent definition {form['entry']} published"
                if form["kind"] == "persistent-definition"
                else None
            ))
        if "evaluation_steps" in form:
            edge = None
            if index == 10:
                edge = "setf layout registry committed; defstruct form complete"
            add(f"form-{index}-evaluate", int(form["evaluation_steps"]),
                semantic_edge=edge)
    add("constructor-control", int(sequence["constructor"]["steps"]),
        semantic_edge="make-point control returns (point 3 4)")
    return result


def fail_closed_graph(truth: ElfTruth) -> dict[str, Any]:
    fail = truth.symbol("c2_kernal_fail_closed")
    body = symbol_bytes(truth, "c2_kernal_fail_closed", unsized=14)
    require(fail.value == 0xE08B
            and body == bytes.fromhex("78a9008d1ad0a9028d20d04c96e0"),
            "Link-92 fail-closed body drift")
    needle = bytes.fromhex("a9028d20d0")
    red_sites: list[dict[str, Any]] = []
    for section in truth.sections:
        if not section.bytes or "PROGBITS" not in section.section_type:
            continue
        data = truth.section_bytes(section.name)
        for offset in range(max(0, len(data) - len(needle) + 1)):
            if data[offset:offset + len(needle)] == needle:
                red_sites.append({
                    "section": section.name,
                    "address": f"0x{section.address + offset:04x}",
                })
    require(red_sites == [{
        "section": ".lisp65_c2_kernal_window.map_switch_and_guards",
        "address": "0xe091",
    }], f"unique red-frame body drift: {red_sites}")
    ingresses = [row for row in truth.relocations
                 if row.target == "c2_kernal_fail_closed"]
    rows = [(row.source_section, row.offset, row.relocation_type)
            for row in ingresses]
    require(rows == [
        (".lisp65_c2_kernal_window.irq_handler", 0xE07B, "R_MOS_ADDR16"),
        (".lisp65_c2_vectors", 0xFFFC, "R_MOS_ADDR16"),
    ], f"fail-closed ingress set drift: {rows}")
    return {
        "terminal_sink": {
            "symbol": fail.name,
            "address": "0xe08b",
            "unique_red_store": red_sites[0],
            "guard_is_not_blamed": True,
        },
        "direct_ingresses": [
            {
                "kind": "active-sequence-asynchronous",
                "section": rows[0][0],
                "relocation_address": "0xe07b",
                "meaning": "second source-less IRQ episode",
                "classification": "terminal ingress or co-witness; not root cause",
            },
            {
                "kind": "external-reset-vector",
                "section": rows[1][0],
                "relocation_address": "0xfffc",
                "excluded_for_D2_active_interval": True,
            },
        ],
    }


def core_receipt() -> dict[str, Any]:
    contract = V111.load(V111.CONTRACT)
    V111.audit_contract(contract)
    defstruct = V110.build_candidate(V110.load(V110.CONTRACT))
    carrier = V111.build_carrier(contract)
    windowed = V111.run_with_carrier(
        carrier["manifest_path"], defstruct["manifest_path"], "windowed")
    direct = V111.run_with_carrier(
        carrier["manifest_path"], defstruct["manifest_path"], "direct")
    require(V111.code_projection(windowed) == V111.code_projection(direct),
            "delivered-carrier windowed/direct replay differs")
    behavior = V110.behavioral_projection(windowed)
    require(behavior["require"] == "t"
            and behavior["last_successful_definition"] == "point-with-y"
            and behavior["constructor"] == "(point 3 4)"
            and behavior["C2J"] == "CLEAR",
            "delivered-carrier completion semantics drift")

    constants = V110.load(V110.CONTRACT)["price"]
    timeline = completion_timeline(windowed, constants)
    last_append = next(row for row in reversed(timeline)
                       if row.get("semantic_edge") ==
                       "persistent definition point-with-y published")
    definition_complete = next(row for row in timeline
                               if row.get("semantic_edge") ==
                               "setf layout registry committed; defstruct form complete")
    constructor = timeline[-1]
    require(last_append["operational_floor_seconds"] == 172
            and definition_complete["operational_floor_seconds"] == 179
            and constructor["operational_floor_seconds"] == 179,
            "completion-prefix pricing drift")
    require(definition_complete["persistent_appends"] == 9
            and last_append["persistent_appends"] == 9,
            "final append ordering drift")

    v111 = load(V111.RECEIPT)
    V111.audit_result(v111)
    require(V110.behavioral_projection(windowed)
            == v111["host_execution"]["behavior_projection"],
            "desk replay is not the delivered 1.11 carrier workload")
    require(v111["pricing"]["claim"].endswith(
        "not target wall time and not a completion upper bound."),
        "1.11 price claim was broadened")

    d2 = load(D2_RECEIPT)
    require(d2["forms"] == {
        "definition_form": "(defstruct point x y)",
        "make_expect": "(point 3 4)",
        "make_form": "(make-point 3 4)",
        "observations_during_quiet_window": 0,
        "owner_physical_input_only": True,
        "quiet_floor_seconds": 180,
        "require_expect": "t",
        "require_form": "(require 'defstruct)",
        "structural_price_is_completion_upper_bound": False,
        "structural_price_seconds": 179,
    } and d2["physical_owner_observation"]["visible_red_frame"] is True
      and d2["physical_owner_observation"]["visible_prompt"] is False,
            "Phase-D D2 datum drift")

    manifest = load(MANIFEST)
    current_plans = append_plans(manifest)
    old_phase_b = load(PHASE_B_RECEIPT)
    PHASE_B.audit(old_phase_b["facts"])
    old_plans = old_phase_b["facts"]["graph"]["append_plans"]
    normalized_old = dict(old_plans)
    require(current_plans == normalized_old == {
        "stage": [30, 39, 33, 34, 35, 36, 0],
        "persistent_publish": [37, 38, 39, 40, 0],
        "rollback": [39, 41, 42, 43, 44, 45, 40, 39, 0],
    }, "Link-92 append plan differs from the partitioned Link-82 plan")

    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    terminal = fail_closed_graph(truth)

    historical = load(SHADOW_RECEIPT)
    ring = load(RING_RECEIPT)
    require(historical.get("format") is not None and ring.get("format") is not None,
            "1.6 restart authorities absent")

    value = {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "P2-DESK-CLOSED; COMPLETION-EDGE-APPEND-HYPOTHESIS-FALSIFIED",
        "scope": {
            "execution": "host-only",
            "product_bytes_changed": 0,
            "product_links": 0,
            "device_contacts": 0,
            "release_claim": False,
        },
        "authorities": {
            "v1.11_receipt": bind(V111.RECEIPT),
            "phase_D_D2": bind(D2_RECEIPT),
            "link92_manifest": bind(MANIFEST),
            "link92_product_ELF": bind(ELF),
            "phase_B_partition": bind(PHASE_B_RECEIPT),
            "historical_shadow_result": bind(SHADOW_RECEIPT),
            "self_sampling_ring": bind(RING_RECEIPT),
            "driver": bind(DRIVER),
            "gate_wiring": gate_wiring_projection(),
            "documentation": documentation_projection(),
        },
        "delivered_carrier_replay": {
            "behavior": behavior,
            "normalized_projection_sha256": sha(canonical(
                V111.code_projection(windowed))),
            "forms": [{
                "index": index,
                "kind": row["kind"],
                "entry": row.get("entry"),
                "source": row["source"],
                "compiler_steps": int(row["compiler_steps"]),
                "evaluation_steps": int(row.get("evaluation_steps", 0)),
                "result": row.get("result"),
            } for index, row in enumerate(windowed["forms"])],
            "completion_timeline": timeline,
            "final_persistent_append": last_append,
            "definition_complete": definition_complete,
            "structural_price_semantics": {
                "aggregate_conservative_floor": True,
                "event_timestamp": False,
                "completion_upper_bound": False,
                "failure_localizer": False,
            },
        },
        "linked_product": {
            "append_plans": current_plans,
            "append_plans_byteidentical_to_phase_B_link82": True,
            "terminal_graph": terminal,
        },
        "banked_exoneration_reread": {
            "R_refill": {
                "historical_status": "two retained Link-82 views byte-exact",
                "current_carrier_status": "not transferred",
                "reason": "the 1.11 schedule is different and D2 captured no fill bytes",
            },
            "A_append": {
                "historical_status": "Link-82 shadow/cleanup evidence",
                "current_carrier_status": "host replay green; target not exonerated",
                "reason": "host success and unchanged plans do not prove target execution",
            },
            "I_interrupt": {
                "historical_status": "post-terminal D01A=0",
                "current_carrier_status": "not exonerated",
                "reason": "the fail-closed body itself clears D01A",
            },
            "G_VM_GC": {
                "historical_status": "Link-82 stopped-state fields clean",
                "current_carrier_status": "not transferred",
                "reason": "D2 has no current-carrier stopped-state capture",
            },
            "retained_background": [
                "require returned t on hardware",
                "host replay publishes all nine definitions and clears C2J",
                "historical mem_init health remains unrelated background evidence",
            ],
        },
        "decision": {
            "completion_edge_append_hypothesis": "desk-falsified",
            "reasons": [
                "the 179-second number is an aggregate structural floor, not an event timestamp or upper bound",
                "the final persistent append ends at prefix floor 172 seconds",
                "the 172-to-179-second priced tail is non-persistent layout-registry compilation/evaluation",
                "the red frame was first observed at 180 seconds; its occurrence time inside the quiet interval is unknown",
            ],
            "host_mechanism_found": False,
            "named_terminal_ingress_candidate": "second source-less IRQ episode",
            "terminal_ingress_is_root_cause": False,
            "root_cause_partition": ["R", "A", "I", "G"],
            "desk_boundary": (
                "The immutable D2 receipt identifies a red terminal sink but has no "
                "stopped-state evidence capable of selecting R/A/I/G."
            ),
        },
        "future_device_row": {
            "name": "current-carrier terminal-ingress ring",
            "status": "specified-not-authorized",
            "identity": "non-promotable diagnostic sister of the delivered carrier",
            "sampling": (
                "target-owned raster IRQ samples into owned RAM; zero monitor or "
                "external observation until one terminal stop"
            ),
            "must_preserve": [
                "monotonic VM-dispatch progress and current C2 form/ordinal",
                "append checkpoint, phase owner and C2J state",
                "last two completed refill views checked against source bytes",
                "tagged first and second source-less episode plus raw D019 witness",
                "first-error, VM status, mem_oom and GC state",
            ],
            "decision_table": {
                "R": "independent refill byte oracle fails before terminal ingress",
                "A": "append checkpoint/phase/C2J names the forward failure",
                "I": "fills and transaction/error planes clean; tagged second source-less episode is first failing plane",
                "G": "first-error/VM/GC plane names the failure before terminal ingress",
            },
            "claim_rule": (
                "The source-less episode is terminal ingress or co-witness unless "
                "R/A/G are independently clean in the same current-carrier record."
            ),
            "device_contacts_now": 0,
        },
        "accounting": {
            "product_bytes_changed": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "device_contacts": 0,
        },
        "claim_limit": (
            "Host replay falsifies completion-edge append timing as an attribution "
            "and binds the only active direct ingress to the visible red sink. It "
            "does not attribute the target root cause, transfer old exonerations to "
            "Link-92, authorize a device contact, or reopen the parked ownership path."
        ),
    }
    return value


def audit_result(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT
            and value.get("status") ==
            "P2-DESK-CLOSED; COMPLETION-EDGE-APPEND-HYPOTHESIS-FALSIFIED",
            "completion-edge result identity drift")
    require(value.get("scope") == {
        "execution": "host-only",
        "product_bytes_changed": 0,
        "product_links": 0,
        "device_contacts": 0,
        "release_claim": False,
    }, "completion-edge scope broadened")
    replay = value["delivered_carrier_replay"]
    require(replay["behavior"]["constructor"] == "(point 3 4)"
            and replay["behavior"]["C2J"] == "CLEAR",
            "host completion semantics dimmed")
    require(replay["final_persistent_append"]["operational_floor_seconds"] == 172
            and replay["definition_complete"]["operational_floor_seconds"] == 179,
            "completion timeline drift")
    require(replay["structural_price_semantics"] == {
        "aggregate_conservative_floor": True,
        "event_timestamp": False,
        "completion_upper_bound": False,
        "failure_localizer": False,
    }, "structural price was promoted to a target clock")
    require(value["linked_product"]["append_plans"] == {
        "stage": [30, 39, 33, 34, 35, 36, 0],
        "persistent_publish": [37, 38, 39, 40, 0],
        "rollback": [39, 41, 42, 43, 44, 45, 40, 39, 0],
    }, "append-plan identity drift")
    terminal = value["linked_product"]["terminal_graph"]
    require(terminal["terminal_sink"]["unique_red_store"]["address"] == "0xe091"
            and terminal["direct_ingresses"][0]["meaning"] ==
            "second source-less IRQ episode"
            and terminal["direct_ingresses"][1]
            ["excluded_for_D2_active_interval"] is True,
            "terminal ingress binding drift")
    decision = value["decision"]
    require(decision["completion_edge_append_hypothesis"] == "desk-falsified"
            and decision["host_mechanism_found"] is False
            and decision["terminal_ingress_is_root_cause"] is False
            and decision["root_cause_partition"] == ["R", "A", "I", "G"],
            "desk boundary overclaimed")
    require(all(row["current_carrier_status"] != "exonerated"
                for key, row in value["banked_exoneration_reread"].items()
                if key in ("R_refill", "A_append", "I_interrupt", "G_VM_GC")),
            "historical exoneration transferred to current carrier")
    future = value["future_device_row"]
    require(future["name"] == "current-carrier terminal-ingress ring"
            and future["status"] == "specified-not-authorized"
            and future["device_contacts_now"] == 0
            and "zero monitor" in future["sampling"]
            and len(future["must_preserve"]) == 5
            and set(future["decision_table"]) == {"R", "A", "I", "G"},
            "decisive future row drift")
    require(value["accounting"] == {
        "product_bytes_changed": 0,
        "product_links": 0,
        "hardware_runs": 0,
        "device_contacts": 0,
    }, "completion-edge accounting drift")


def mutation_proof(value: dict[str, Any]) -> dict[str, str]:
    mutations: dict[str, Callable[[dict[str, Any]], None]] = {
        "promote-price-to-event-timestamp": lambda x: x["delivered_carrier_replay"]
            ["structural_price_semantics"].__setitem__("event_timestamp", True),
        "promote-price-to-upper-bound": lambda x: x["delivered_carrier_replay"]
            ["structural_price_semantics"].__setitem__("completion_upper_bound", True),
        "move-final-append-to-179": lambda x: x["delivered_carrier_replay"]
            ["final_persistent_append"].__setitem__("operational_floor_seconds", 179),
        "drop-host-constructor": lambda x: x["delivered_carrier_replay"]
            ["behavior"].__setitem__("constructor", "NIL"),
        "dirty-host-journal": lambda x: x["delivered_carrier_replay"]
            ["behavior"].__setitem__("C2J", "DIRTY"),
        "change-publish-plan": lambda x: x["linked_product"]["append_plans"]
            ["persistent_publish"].__setitem__(0, 39),
        "lose-unique-red-store": lambda x: x["linked_product"]["terminal_graph"]
            ["terminal_sink"]["unique_red_store"].__setitem__("address", "0xe092"),
        "rename-active-ingress": lambda x: x["linked_product"]["terminal_graph"]
            ["direct_ingresses"][0].__setitem__("meaning", "append failure"),
        "allow-reset-during-D2": lambda x: x["linked_product"]["terminal_graph"]
            ["direct_ingresses"][1].__setitem__("excluded_for_D2_active_interval", False),
        "claim-root-cause": lambda x: x["decision"].__setitem__(
            "terminal_ingress_is_root_cause", True),
        "claim-host-mechanism": lambda x: x["decision"].__setitem__(
            "host_mechanism_found", True),
        "transfer-old-R-exoneration": lambda x: x["banked_exoneration_reread"]
            ["R_refill"].__setitem__("current_carrier_status", "exonerated"),
        "transfer-old-A-exoneration": lambda x: x["banked_exoneration_reread"]
            ["A_append"].__setitem__("current_carrier_status", "exonerated"),
        "transfer-old-I-exoneration": lambda x: x["banked_exoneration_reread"]
            ["I_interrupt"].__setitem__("current_carrier_status", "exonerated"),
        "transfer-old-G-exoneration": lambda x: x["banked_exoneration_reread"]
            ["G_VM_GC"].__setitem__("current_carrier_status", "exonerated"),
        "authorize-device-row": lambda x: x["future_device_row"].__setitem__(
            "status", "authorized"),
        "allow-monitor-sampling": lambda x: x["future_device_row"].__setitem__(
            "sampling", "monitor polls during operation"),
        "drop-ingress-witness": lambda x: x["future_device_row"]
            ["must_preserve"].pop(3),
        "add-device-contact": lambda x: x["accounting"].__setitem__(
            "device_contacts", 1),
    }
    rejected: dict[str, str] = {}
    for name, mutate in mutations.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            audit_result(candidate)
        except CompletionEdgeError as error:
            rejected[name] = str(error)
        else:
            raise CompletionEdgeError(f"mutation survived: {name}")
    require(len(rejected) == len(mutations), "mutation count drift")
    return rejected


def derive() -> dict[str, Any]:
    value = core_receipt()
    audit_result(value)
    value["mutation_proof"] = {
        "expected": 19,
        "rejected": mutation_proof(value),
    }
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run", "check", "selftest"))
    args = parser.parse_args()
    if args.command == "run":
        value = derive()
        write_json(RECEIPT, value)
        print(f"wrote {RECEIPT.relative_to(ROOT)}")
        return 0
    if args.command == "check":
        stored = load(RECEIPT)
        expected = derive()
        require(stored == expected, "completion-edge receipt is stale")
        print("defstruct completion-edge check: PASS")
        return 0
    stored = load(RECEIPT)
    audit_result(stored)
    require(len(mutation_proof(stored)) == 19,
            "completion-edge selftest mutation drift")
    print("defstruct completion-edge selftest: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CompletionEdgeError, V110.PerformanceError, V111.LocalityError,
            PHASE_B.PhaseBError, ElfTruthError, KeyError, IndexError,
            TypeError, ValueError) as error:
        print(f"defstruct completion-edge: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
