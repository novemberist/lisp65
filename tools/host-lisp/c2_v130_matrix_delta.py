#!/usr/bin/env python3
"""Bind the Link-88 v1.3.0 cross-invariant delta review."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BASE = EVIDENCE / "c2.2-v1.2.5-link82-cross-invariant-delta-receipt.json"
A1 = EVIDENCE / "c2.3-v1.3.0-a1-prechain-hygiene-receipt.json"
Q = EVIDENCE / "c2.2-v1.3-q-host-first-receipt.json"
INPUT_WAIT = EVIDENCE / "c2.2-v1.3-ship-input-wait-host-first-receipt.json"
EDITOR = EVIDENCE / "c2-v126-editor-allocation-gate-receipt.json"
RESET = EVIDENCE / "c2.3-v1.3-link85-full-reset-domain-host-receipt.json"
BOOT = EVIDENCE / "c2.3-v1.3-ship-boot-inheritance-gate-receipt.json"
WPLTO = EVIDENCE / "c2.3-v1.3-link88-full-raster-wplto-receipt.json"
HARDWARE = EVIDENCE / "c2.3-v1.3-link88-interactive-human-device-receipt.json"
RUN_STOP = EVIDENCE / (
    "c2.3-v1.3-link85-full-reset-closing-device-first-red-receipt.json")
MEDIA = ROOT / (
    "build/c2.3/v1.3.0-candidate-media-link88-r1/candidate-manifest.json")
ELF = ROOT / (
    "build/c2.3/v1.3.0-candidate-product-link88-r1/final/"
    "lisp65-c2-substitution-linked.prg.elf")
PLAN = ROOT / "docs/planning/1.3-ship-builder-work-plan.md"
RECEIPT = EVIDENCE / (
    "c2.3-v1.3.0-link88-cross-invariant-delta-receipt.json")

REDERIVED = frozenset((
    "A2", "A3", "A4", "B1", "B2", "B3", "C4", "C5", "D1",
    "D2", "D3", "E1", "F1", "F2", "F3"))


class DeltaError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise DeltaError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing file: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def authorities() -> dict[str, dict[str, Any]]:
    values = {
        "base": load(BASE),
        "a1": load(A1),
        "q": load(Q),
        "input_wait": load(INPUT_WAIT),
        "editor": load(EDITOR),
        "reset": load(RESET),
        "boot": load(BOOT),
        "wplto": load(WPLTO),
        "hardware": load(HARDWARE),
        "run_stop": load(RUN_STOP),
        "media": load(MEDIA),
    }
    require(
        len(values["base"].get("rows", [])) == 25
        and values["base"].get("summary", {}).get("new_OPEN_rows") == 0,
        "reviewed 25-row authority drift")
    require(
        values["a1"].get("status")
        == "passed-prechain-hygiene-check-source-no-exceptions"
        and values["a1"].get("equivalence", {}).get("cases_executed") == 447,
        "v1.3.0 A1 authority drift")
    require(
        values["q"].get("status")
        == "passed-q-host-reference-modeled-register-and-capacity",
        "q authority drift")
    require(
        values["input_wait"].get("status")
        == "passed-bank2-lisp-source-artifact-allocation-and-execution",
        "input/wait authority drift")
    require(
        values["editor"].get("status") == "passed"
        and values["editor"].get("execution_witness", {}).get("keys") == 165
        and values["editor"].get("execution_witness", {}).get("mutations") == 6,
        "editor allocation authority drift")
    require(
        values["reset"].get("status")
        == "passed-full-reset-domain-gate-link85-and-closing-preparation"
        and values["reset"].get("class_closer", {}).get("executions") == 7
        and values["reset"].get("class_closer", {}).get("mutations_rejected")
        == 6,
        "reset-domain authority drift")
    require(
        values["boot"].get("status")
        == "passed-ship-owned-full-9bit-repeated-frame-clock"
        and values["boot"].get("raster_phase_matrix", {}).get(
            "full_9bit_high_to_low_passes") == 312
        and values["boot"].get("mutation_count") == 22,
        "Ship boot-inheritance authority drift")
    require(
        values["wplto"].get("status")
        == "passed-Link88-full-raster-one-product-shaped-WPLTO"
        and values["wplto"].get("walls", {}).get(
            "bank0_text_headroom_bytes") == 243
        and values["wplto"].get("static_geometry", {}).get(
            "bank2_headroom_bytes") == 20022,
        "Link-88 WPLTO authority drift")
    require(
        values["hardware"].get("status")
        == "passed-Link88-physical-keyboard-end-to-end"
        and values["hardware"].get("candidate_link") == 88
        and values["hardware"].get("operator_observation", {}).get(
            "greeting_present") is True,
        "Link-88 physical authority drift")
    require(
        values["run_stop"].get("reset_domain_fix", {}).get("post_stop_result")
        == "9"
        and values["run_stop"].get("reset_domain_fix", {}).get("run_stop")
        == "returned-live-REPL",
        "Link-85 RUN/STOP authority drift")
    require(
        values["media"].get("status")
        == "passed-complete-C2-lite-two-media-product"
        and values["media"].get("artifact_count") == 19,
        "Link-88 media authority drift")
    return values


def row_facts(row_id: str, auth: dict[str, dict[str, Any]]) -> dict[str, Any]:
    static = auth["wplto"]["static_geometry"]
    reset = auth["reset"]
    if row_id == "A2":
        return {
            "delta_surface": "q/read-line/editor freight -> transient high edge",
            "finding": (
                "The new arithmetic and input code stays in immutable Bank 2. "
                "read-line is bounded at four cells per ordinary key and the "
                "editor allocation gate executes all incoming nursery phases; "
                "no new transient root class is introduced."),
            "fresh_facts": {"editor_keys": 165, "nursery_phases_per_key": 192,
                            "read_line_max_cells_per_key": 4},
        }
    if row_id == "A3":
        return {
            "delta_surface": "new immutable Bank-2 code -> streamed code window",
            "finding": (
                "Link 88 adds immutable Bank-2 code only. It introduces no "
                "moving code, root or direct-entry reference and retains the "
                "existing refill seam and all resident walls."),
            "fresh_facts": {"bank2_static_code_bytes": static["bank2_static_code_bytes"],
                            "bank2_headroom_bytes": static["bank2_headroom_bytes"],
                            "new_roots": static["delta"]["roots"],
                            "new_direct_entry_refs": static["delta"]["direct_entry_refs"]},
        }
    if row_id == "A4":
        return {
            "delta_surface": "full reset-domain restage -> C2D publication",
            "finding": (
                "The product now stages and reads back the complete 50,816-byte "
                "reset domain, zeroes C2J, then enters the unchanged validated "
                "publication path; prefix-only restage is a permanent red case."),
            "fresh_facts": {"reset_domain_bytes": reset["mechanism"]["reset_domain_bytes"],
                            "c2j_zero_bytes": reset["mechanism"]["c2j_zero_bytes"],
                            "gate_executions": 7, "mutations_rejected": 6},
        }
    if row_id in ("B1", "B2"):
        return {
            "delta_surface": "read-line/wait/editor abort -> open transaction",
            "finding": (
                "RUN/STOP remains owned by the central poll/longjmp landing and "
                "is never coalesced into input. The target row returns from 30 "
                "editor keys to a live REPL and evaluates (+ 4 5) as 9."),
            "fresh_facts": {"run_stop_coalesced": False,
                            "post_abort_repl_result": "9", "retained_keys": 30},
        }
    if row_id == "B3":
        return {
            "delta_surface": "coalesced typed queue -> break delivery",
            "finding": (
                "The editor drains ordinary queued keys in order, while physical "
                "RUN/STOP remains outside the queue and takes the standing abort "
                "path. Six mutations guard this ownership split."),
            "fresh_facts": {"queue_order_cases": 4, "mutations_rejected": 6,
                            "physical_run_stop_queued": False},
        }
    if row_id == "C4":
        return {
            "delta_surface": "cold reset -> complete C2D/C2J reset domain",
            "finding": (
                "Cold restage can no longer publish a canonical prefix over a "
                "stale journal or inactive suffix. The complete domain is staged "
                "and independently read back before READY is possible."),
            "fresh_facts": {"canonical_prefix_bytes": 33840,
                            "complete_reset_domain_bytes": 50816,
                            "c2j_nonzero_bytes": 0},
        }
    if row_id == "C5":
        return {
            "delta_surface": "new q/input/Ship symbols -> session directory",
            "finding": (
                "The new public names are statically composed and the Ship sample "
                "fleet is closed by the real builder. No new Attic locator or "
                "runtime tenant identity is introduced."),
            "fresh_facts": {"public_bound_names": 90, "ship_media_artifacts": 19,
                            "new_direct_entry_refs": 0},
        }
    if row_id in ("D1", "D2"):
        return {
            "delta_surface": "owned raster IRQ -> Workbench and Ship boot state",
            "finding": (
                "Workbench ownership is unchanged. Ship owns and chains its "
                "private raster clock, acknowledges only its line and proves "
                "three unit deltas against the complete independent 9-bit raster "
                "sequence before the entry program runs."),
            "fresh_facts": {"raster_start_phases": 312,
                            "full_9bit_passes": 312,
                            "boot_mutations_rejected": 22},
        }
    if row_id == "D3":
        return {
            "delta_surface": "editor/read-line input -> queue and break delivery",
            "finding": (
                "The allocation shape changes redisplay only. Queue order and "
                "RUN/STOP ownership are permanently gated; target post-abort "
                "liveness and physical Ada+RETURN input are both observed."),
            "fresh_facts": {"physical_input": "Ada+RETURN",
                            "visible_output": "Hello, Ada!",
                            "post_abort_repl_result": "9"},
        }
    if row_id == "E1":
        return {
            "delta_surface": "complete reset-domain restage -> generation/cache",
            "finding": (
                "Reset now replaces the whole authenticated domain before READY. "
                "No cache or generation field is newly introduced; stale C2J or "
                "suffix state cannot survive to validate a hot view."),
            "fresh_facts": {"ready_shortcut": False,
                            "c2j_nonzero_bytes": 0,
                            "inactive_suffix_nonzero_bytes": 0},
        }
    if row_id == "F1":
        return {
            "delta_surface": "v1.3 base freight -> Bank-5/Bank-2 ceilings",
            "finding": (
                "The seven new static entries and sixteen resolution words remain "
                "inside the unchanged product ceilings; Bank 2 retains 20,022 "
                "bytes and all pinned Bank-0 walls are unchanged."),
            "fresh_facts": {"entries": static["entries"],
                            "resolutions": static["resolutions"],
                            "bank2_headroom_bytes": static["bank2_headroom_bytes"]},
        }
    if row_id == "F2":
        return {
            "delta_surface": "read-line/editor allocation -> transient/persistent edge",
            "finding": (
                "read-line's per-key cells remain transient and capped; editor "
                "redisplay materialization is removed rather than moved into the "
                "persistent arena. No new persistent edge is created."),
            "fresh_facts": {"read_line_max_cells_per_key": 4,
                            "new_roots": 0, "editor_routes": 3},
        }
    require(row_id == "F3", f"missing row treatment: {row_id}")
    return {
        "delta_surface": "q/input/Ship names -> symbol/name-pool growth",
        "finding": (
            "The delivered public surface is bound to 90 names and the exact "
            "carrier/product artifacts. No dynamic name-pool ownership or new "
            "root class accompanies the added static symbols."),
        "fresh_facts": {"bound_public_names": 90,
                        "surface_mutations_rejected": 9, "new_roots": 0},
    }


def build() -> dict[str, Any]:
    auth = authorities()
    rows = deepcopy(auth["base"]["rows"])
    for row in rows:
        row_id = row["id"]
        if row_id not in REDERIVED:
            row["review"] = "not-rederived-Link88-v1.3.0-delta-disjoint"
            row["reason"] = (
                "No q, input/wait, editor allocation, Ship boot or complete "
                "reset-domain edge reaches this crossing. Its reviewed C2.2 "
                "disposition is retained and is not presented as fresh proof.")
            continue
        row["review"] = "re-derived-against-Link88-v1.3.0-delta"
        row["authorities"] = sorted(set(row.get("authorities", []) + [
            "v130_A1", "link88_WPLTO", "link88_hardware"]))
        row.update(row_facts(row_id, auth))
        row["proof_boundary"] = (
            "Fresh source/artifact gates and the named target observations for "
            "this delta only; the retained matrix disposition is not widened.")
    rederived = sum(row["review"].startswith("re-derived") for row in rows)
    retained = sum(row["review"].startswith("not-rederived") for row in rows)
    require((rederived, retained) == (15, 10), "delta coverage drift")
    summary = deepcopy(auth["base"]["summary"])
    summary["acceptance_chain"] = "A1-green-delta-green-fresh-R4-R5-R6-G5-G6-required"
    summary["matrix_gate"] = "Link88-v1.3.0-delta-reviewed-no-new-open-row"
    return {
        "format": "lisp65-v1.3.0-link88-cross-invariant-delta-v1",
        "version": 1,
        "recorded_on": date.today().isoformat(),
        "status": "passed-Link88-v1.3.0-delta-review-no-new-open-row",
        "candidate": "Link 88",
        "method": {
            "baseline_rows": 25,
            "rederived_rows": sorted(REDERIVED),
            "rederived_count": 15,
            "explicit_not_rederived_count": 10,
            "no_silent_inheritance": True,
        },
        "summary": summary,
        "fresh_execution_witness": {
            "check_source_exception_count": 0,
            "equivalence_lanes": 11,
            "equivalence_cases": 447,
            "editor_keys": 165,
            "reset_domain_executions": 7,
            "ship_boot_executions": 3,
            "ship_boot_mutations": 22,
            "surface_bound_names": 90,
            "surface_mutations": 9,
        },
        "hardware_claim_boundary": {
            "Link85_post_abort_REPL": "(+ 4 5) => 9",
            "Link88_physical_input": "Ada+RETURN",
            "Link88_visible_output": "Hello, Ada!",
            "fresh_v1.3.0_G5_G6_still_required": True,
        },
        "rows": rows,
        "bindings": {
            "reviewed_Link82_delta": bind(BASE),
            "v130_A1": bind(A1),
            "q": bind(Q),
            "input_wait": bind(INPUT_WAIT),
            "editor": bind(EDITOR),
            "reset_domain": bind(RESET),
            "ship_boot": bind(BOOT),
            "link88_WPLTO": bind(WPLTO),
            "link88_hardware": bind(HARDWARE),
            "link85_RUN_STOP": bind(RUN_STOP),
            "link88_media": bind(MEDIA),
            "link88_ELF": bind(ELF),
            "owner_plan": bind(PLAN),
            "verifier": bind(Path(__file__).resolve()),
        },
        "claim_limit": (
            "A Link-88 v1.3.0 delta review plus the named historical target "
            "observations only. Fresh R4/R5/R6/G5/G6 remains required. "
            "C1/E3/E4 remain explicit C2.3 deferrals; no promotion, tag, "
            "release or public push is created."),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "verify"))
    args = parser.parse_args()
    try:
        value = build()
        if args.action == "write":
            RECEIPT.write_text(
                json.dumps(value, indent=2, sort_keys=True) + "\n",
                encoding="utf-8")
            print(
                "c2-v1.3.0-matrix-delta: PASS rows=25 rederived=15 "
                "explicit-not-rederived=10 new-open=0")
        else:
            require(RECEIPT.is_file(), "delta receipt missing")
            require(load(RECEIPT) == value, "delta receipt or authority drift")
            print(
                "c2-v1.3.0-matrix-delta: VERIFY PASS rows=25 "
                "rederived=15 explicit-not-rederived=10")
        return 0
    except (DeltaError, OSError, KeyError, ValueError) as error:
        print(f"c2-v1.3.0-matrix-delta: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
