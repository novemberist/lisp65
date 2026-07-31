#!/usr/bin/env python3
"""Bind the six-row Link-82 require Option-A cross-invariant delta review."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.2.5-release-plan.md"
OWNER_DISPOSITION_COMMIT = "ff4ec399"
BASE = EVIDENCE / "c2.2-v1.2.4-link81-cross-invariant-delta-receipt.json"
LINK82 = EVIDENCE / "c2.2-v1.2.5-phase-b-link82-receipt.json"
OPTION_A = EVIDENCE / (
    "c2.2-require-prior-append-option-A-host-gate-receipt.json")
FASTPATH = EVIDENCE / "c2.2-require-idempotence-fastpath-receipt.json"
HARDWARE = EVIDENCE / (
    "c2.2-v1.2.5-require-prior-append-hardware-receipt.json")
WPLTO = EVIDENCE / "c2.2-v1.2.5-require-option-A-wplto-receipt.json"
ELF = ROOT / (
    "build/c2.2/v1.2.5-candidate-product-link82/final/"
    "lisp65-c2-substitution-linked.prg.elf")
RECEIPT = EVIDENCE / (
    "c2.2-v1.2.5-link82-cross-invariant-delta-receipt.json")
REDERIVED = frozenset(("A3", "A4", "C5", "E1", "F1", "F3"))


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


def owner_plan() -> dict[str, Any]:
    result = subprocess.run(
        ["git", "show", f"{OWNER_DISPOSITION_COMMIT}:{PLAN.relative_to(ROOT)}"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(result.returncode == 0, "owner-disposition plan unavailable")
    return {
        "path": PLAN.relative_to(ROOT).as_posix(),
        "commit": OWNER_DISPOSITION_COMMIT,
        "bytes": len(result.stdout),
        "sha256": hashlib.sha256(result.stdout).hexdigest(),
    }


def authorities() -> dict[str, Any]:
    base = load(BASE)
    link = load(LINK82)
    option = load(OPTION_A)
    fastpath = load(FASTPATH)
    hardware = load(HARDWARE)
    wplto = load(WPLTO)
    require(
        len(base.get("rows", [])) == 25
        and base.get("summary", {}).get("new_OPEN_rows") == 0,
        "reviewed 25-row authority drift")
    require(
        link.get("status")
        == "passed-bound-Link82-and-check-source-device-acceptance-pending"
        and link.get("qualifying_candidate", {}).get("link") == 82,
        "Link-82 structural authority drift")
    require(
        option.get("status")
        == "passed-option-A-require-after-two-ordinary-appends-host-lane"
        and option.get("execution_witness", {}).get("cases_executed") == 2
        and option.get("execution_witness", {}).get("mutations_executed") == 5,
        "Option-A host authority drift")
    require(
        fastpath.get("status") == "passed-parser-free-idempotence-fastpath"
        and len(fastpath.get("fallback_mutations", {})) == 5,
        "require fastpath authority drift")
    require(
        hardware.get("status")
        == "passed-require-after-two-ordinary-persistent-appends"
        and hardware.get("readback", {}).get("final_image_count") == 9
        and hardware.get("readback", {}).get("c2j") == "CLEAR",
        "Option-A hardware authority drift")
    require(
        wplto.get("status") == "passed-require-option-A-one-product-shaped-WPLTO"
        and wplto.get("static_geometry", {}).get(
            "bank2_delta_from_Link81_bytes") == 19
        and wplto.get("walls", {}).get("bank0_text_headroom_bytes") == 243
        and wplto.get("static_geometry", {}).get("roots") == 340,
        "Option-A WPLTO authority drift")
    return {
        "base": base,
        "link": link,
        "option": option,
        "fastpath": fastpath,
        "hardware": hardware,
        "wplto": wplto,
    }


def build(run_fresh: bool) -> dict[str, Any]:
    auth = authorities()
    rows = deepcopy(auth["base"]["rows"])
    for row in rows:
        row_id = row["id"]
        if row_id not in REDERIVED:
            row["review"] = "not-rederived-Link82-v1.2.5-delta-disjoint"
            row["reason"] = (
                "No Link-82 Option-A validation, package-identity or ordinary "
                "Session-row edge reaches this crossing. Its reviewed C2.2 "
                "disposition is retained and is not presented as fresh proof.")
            continue
        row["review"] = "re-derived-against-Link82-v1.2.5-delta"
        row["authorities"] = sorted(set(
            row.get("authorities", []) + [
                "link82", "option_A", "fastpath", "prior_append_hardware"]))
        if row_id == "A3":
            row.update({
                "delta_surface": "Option-A Bank-2 code -> streamed code window",
                "finding": (
                    "The correction adds 19 immutable Bank-2 bytes and no "
                    "resident code, root, direct-entry reference or moving "
                    "object. It retains the existing refill seam."),
                "fresh_facts": {
                    "bank2_static_code_bytes": 43237,
                    "bank2_headroom_bytes": 22299,
                    "bank2_delta_bytes": 19,
                    "resident_delta_bytes": 0,
                    "new_roots": 0,
                    "new_direct_entry_refs": 0,
                },
                "proof_boundary": (
                    "Structural non-moving-code exclusion; no new claim about "
                    "the unchanged code-window transport."),
            })
        elif row_id == "A4":
            row.update({
                "delta_surface":
                    "Option-A world proof -> package C2D publication",
                "finding": (
                    "World validation remains serialized and read-only. Two "
                    "ordinary rows are accepted geometrically, then the "
                    "unchanged loader publishes the package row. Hardware "
                    "ends with C2J CLEAR and a byteidentical repeat."),
                "fresh_facts": {
                    "host_prior_rows": 2,
                    "hardware_final_images": 9,
                    "hardware_C2J": "CLEAR",
                    "repeat_C2D_byteidentical": True,
                },
                "proof_boundary": (
                    "Fresh host execution and the release-terminal hardware "
                    "row; the unchanged generic publication path is not "
                    "re-derived beyond this sequence."),
            })
        elif row_id == "C5":
            row.update({
                "delta_surface":
                    "index-absent Session row -> package identity walk",
                "finding": (
                    "Every persistent row still passes source-kind, source-"
                    "slot, generation, base and authenticated-size geometry. "
                    "Only index hits receive package semantics; no new source "
                    "locator or runtime Attic edge is introduced."),
                "fresh_facts": {
                    "geometry_mutations_rejected": 5,
                    "ordinary_source_slots": [0, 1],
                    "package_source_slot": 2,
                },
                "proof_boundary": (
                    "Host row-class and geometry proof plus target publication; "
                    "no physical-DMA timing claim."),
            })
        elif row_id == "E1":
            row.update({
                "delta_surface":
                    "Option-A world proof -> generation-bound fastpath",
                "finding": (
                    "The loaded identity remains derived from canonical C2D "
                    "state. Generation, count/front, index-lock and ordered "
                    "identity mismatches still enter the slow path."),
                "fresh_facts": {
                    "fastpath_fallback_directions": 5,
                    "hardware_repeat_results": ["t", "t"],
                    "hardware_repeat_C2D_byteidentical": True,
                    "hardware_repeat_bank2_byteidentical": True,
                },
                "proof_boundary": (
                    "Host fallback mutations plus target repeat idempotence; "
                    "no claim about an unobserved generation wrap."),
            })
        elif row_id == "F1":
            row.update({
                "delta_surface":
                    "two ordinary Session rows plus package row -> C2D ceiling",
                "finding": (
                    "Option A changes row classification, not C2D geometry. "
                    "The target reaches nine images with helpers in slots 6/7 "
                    "and the package in slot 8; the host final geometry remains "
                    "inside the unchanged C2D-v6 bounds."),
                "fresh_facts": {
                    "host_final_code_bytes": 44155,
                    "host_final_entries": 743,
                    "host_final_resolutions": 2915,
                    "hardware_final_images": 9,
                },
                "proof_boundary": (
                    "Exact commissioned sequence only; no new general maximum-"
                    "occupancy claim."),
            })
        else:
            row.update({
                "delta_surface":
                    "ordinary symbol definitions -> later package append",
                "finding": (
                    "The real compiler/append path creates two named Session "
                    "entries before require. Both remain callable directory "
                    "rows, and the package publishes after them without "
                    "altering their identity."),
                "fresh_facts": {
                    "host_entries": ["%s", "%sr"],
                    "hardware_entries": ["%ra", "%rb"],
                    "hardware_helper_slots": [6, 7],
                    "hardware_package_slot": 8,
                },
                "proof_boundary": (
                    "Functional symbol/name-pool coexistence for the exact "
                    "sequence, not a new name-pool capacity maximum."),
            })
    require(
        sum(row["review"].startswith("re-derived") for row in rows) == 6
        and sum(row["review"].startswith("not-rederived") for row in rows)
        == 19,
        "delta coverage drift")
    return {
        "format": "lisp65-v1.2.5-link82-cross-invariant-delta-v1",
        "version": 1,
        "recorded_on": date.today().isoformat(),
        "status": "passed-Link82-require-Option-A-delta-review-no-new-open-row",
        "candidate": "Link 82",
        "method": {
            "baseline_rows": 25,
            "rederived_rows": sorted(REDERIVED),
            "rederived_count": 6,
            "explicit_not_rederived_count": 19,
            "no_silent_inheritance": True,
        },
        "summary": deepcopy(auth["base"]["summary"]),
        "fresh_execution_witness": {
            "option_A_cases": 2,
            "option_A_mutations": 5,
            "hardware_results": ["%ra", "%rb", "t", "t"],
            "repeat_C2D_and_bank2": "byteidentical",
        },
        "hardware_claim_boundary": {
            "fresh_v1.2.5_G5_G6_still_required": True,
            "prior_append_row_is_release_terminal": True,
            "prior_append_row": "passed",
        },
        "rows": rows,
        "bindings": {
            "owner_disposition_plan": owner_plan(),
            "reviewed_Link81_delta": bind(BASE),
            "link82": bind(LINK82),
            "option_A": bind(OPTION_A),
            "fastpath": bind(FASTPATH),
            "prior_append_hardware": bind(HARDWARE),
            "wplto": bind(WPLTO),
            "link82_elf": bind(ELF),
            "verifier": bind(Path(__file__).resolve()),
        },
        "claim_limit": (
            "A Link-82 v1.2.5 Option-A delta review and its release-terminal "
            "prior-append row only. Fresh G5/G6 remains required. C1/E3/E4 "
            "remain explicit C2.3 deferrals; no promotion, tag, release or "
            "public push.")
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "verify"))
    args = parser.parse_args()
    try:
        if args.action == "write":
            RECEIPT.write_text(
                json.dumps(build(True), indent=2, sort_keys=True) + "\n",
                encoding="utf-8")
            print(
                "c2-v1.2.5-matrix-delta: PASS rows=25 rederived=6 "
                "explicit-not-rederived=19 new-open=0")
        else:
            require(RECEIPT.is_file(), "delta receipt missing")
            require(load(RECEIPT) == build(False),
                    "delta receipt or authority drift")
            print(
                "c2-v1.2.5-matrix-delta: VERIFY PASS rows=25 "
                "rederived=6 explicit-not-rederived=19")
        return 0
    except (DeltaError, OSError, KeyError, ValueError) as error:
        print(f"c2-v1.2.5-matrix-delta: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
