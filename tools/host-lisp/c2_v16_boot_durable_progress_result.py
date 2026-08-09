#!/usr/bin/env python3
"""Classify the consumed v1.6 durable boot-progress contact."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-durable-progress-preparation-receipt.json")
DEVICE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-durable-progress-device-receipt.json")
DURABLE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-boot-order-durable-witness-receipt.json")
OUT = ROOT / (
    "build/c2.3/v1.6-defstruct-closing-session/"
    "d2-durable-progress-appointment")
PATCHED_PRG = OUT / "diagnostic-link82-durable-b5c3.prg"
PAYLOAD_READBACK = OUT / "diagnostic-prg-payload.bin"
WITNESS_BEFORE_RESUME = OUT / "witness-before-resume.bin"
WITNESS_BEFORE_RUN = OUT / "witness-before-run.bin"
RESULT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-durable-progress-first-red-receipt.json")
DRIVER = Path(__file__).resolve()


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
            "bytes": len(raw), "sha256": sha_bytes(raw)}


def in_root_scan(pc: int, prep: dict[str, Any]) -> bool:
    row = next(item for item in prep["facts"]["progress"]["intervals"]
               if item["name"] == "c2_product_gc_mark_roots")
    return int(row["start"], 16) <= pc < int(row["end_exclusive"], 16)


def exact_facts() -> dict[str, Any]:
    plan = PLAN.read_text(encoding="utf-8")
    require("Durable-progress contact result — 2026-08-05" in plan,
            "result disposition absent from plan")
    prep = load(PREP)
    device = load(DEVICE)
    durable = load(DURABLE)
    require(device["authorities"]["preparation"]["sha256"] ==
            sha_bytes(PREP.read_bytes()), "device/preparation binding drift")
    prep_identity = prep["facts"]["identity"]
    prep_witness = prep["facts"]["witness"]
    require(prep["status"] ==
            "HOST-GREEN; ONE DURABLE-WITNESS CONTACT AUTHORIZED"
            and prep_identity["changes"] == [
                {"address": "0xc045", "before": "0x7a", "after": "0xc3"},
                {"address": "0xc046", "before": "0xc0", "after": "0xb5"},
            ]
            and prep_identity["diagnostic_bytes_changed"] == 2
            and prep_identity["product_bytes_changed"] == 0
            and prep_identity["promotable"] is False
            and prep_witness["address"] == "0xb5c3"
            and prep_witness["prelaunch_reset"] == "0xd7"
            and prep_witness["entry_stamp"] == "0x44"
            and prep["facts"]["appointment"]["measured_forms"] == 0,
            "historical preparation boundary drift")
    require(device["status"] == "BOOT-ENTRY-IDENTITY-OR-VIEW-FIRST-RED"
            and device["result"] == {
                "CPU_left_stopped": True,
                "R_A_I_G_claimed": False,
                "classification": "BOOT-ENTRY-IDENTITY-OR-VIEW-FIRST-RED",
                "measured_forms_run": 0,
            }, "device result boundary drift")
    samples = device["samples"]
    require(len(samples) == 3, "sample count drift")
    pcs = [int(row["PC"], 16) for row in samples]
    stamps = [int(row["durable_witness"], 16) for row in samples]
    freelists = [int(row["freelist_head"], 16) for row in samples]
    runs = [row["gc_runs"] for row in samples]
    contexts = [row["GC_context"] for row in samples]
    x_values = [int(row["registers"]["X"], 16) for row in samples]
    require(all(in_root_scan(pc, prep) for pc in pcs),
            "a sample is outside the bound root-scan interval")
    require(stamps == [0xD7, 0xD7, 0xD7]
            and freelists == [0, 0, 0] and runs == [0, 0, 0]
            and len(set(contexts)) == 1,
            "stopped-state tuple drift")
    require(durable["facts"]["durable_witness"]["address"] == "0xb5c3"
            and durable["facts"]["durable_witness"]
            ["disjoint_from_all_post_ownership_owners"],
            "durable owner proof drift")
    patched = PATCHED_PRG.read_bytes()
    require(PAYLOAD_READBACK.read_bytes() == patched[2:],
            "staged diagnostic payload differs from the prepared identity")
    require(WITNESS_BEFORE_RESUME.read_bytes() == b"\xd7"
            and WITNESS_BEFORE_RUN.read_bytes() == b"\xd7",
            "prelaunch durable sentinel was not read back")

    return {
        "staging": {
            "diagnostic_payload_readback": bind(PAYLOAD_READBACK),
            "prepared_diagnostic": bind(PATCHED_PRG),
            "payload_byteidentical": True,
            "witness_before_resume": bind(WITNESS_BEFORE_RESUME),
            "witness_before_physical_RUN": bind(WITNESS_BEFORE_RUN),
            "prelaunch_values": ["0xd7", "0xd7"],
        },
        "samples": {
            "PCs": [f"0x{pc:04x}" for pc in pcs],
            "all_inside_c2_product_gc_mark_roots": True,
            "durable_witness": [f"0x{value:02x}" for value in stamps],
            "freelist_heads": [f"0x{value:04x}" for value in freelists],
            "gc_runs": runs,
            "GC_context": contexts,
            "X_values": [f"0x{value:02x}" for value in x_values],
            "CPU_left_stopped": True,
        },
        "contradiction": {
            "entry_path_reached_if_linked_identity_and_view_apply": True,
            "durable_stamp_observed": False,
            "gc_runs_increment_observed": False,
            "why_double": (
                "the sampled root-scan is post-entry and post-gc_collect increment, "
                "yet both independently bound RAM witnesses retain reset values"),
            "classification": "BOOT-ENTRY-IDENTITY-OR-VIEW-FIRST-RED",
        },
        "decision": {
            "contact_consumed": True,
            "new_contact_authorized": False,
            "product_hang_claim": False,
            "allocation_GC_loop_claim": False,
            "slow_progress_claim": False,
            "F018B_membership_claim": False,
            "R_A_I_G_claim": False,
            "X_regression": "observation only; not an atomic or monotonic oracle",
            "required_owner_review": (
                "choose a launch identity/view proof that makes the entry stamp "
                "and gc_runs observations cohere before any new device contact"),
        },
    }


def audit(facts: dict[str, Any]) -> None:
    staging = facts["staging"]
    samples = facts["samples"]
    contradiction = facts["contradiction"]
    decision = facts["decision"]
    require(staging["payload_byteidentical"]
            and staging["prelaunch_values"] == ["0xd7", "0xd7"],
            "staging proof drift")
    require(samples["all_inside_c2_product_gc_mark_roots"]
            and samples["durable_witness"] == ["0xd7"] * 3
            and samples["gc_runs"] == [0, 0, 0]
            and samples["CPU_left_stopped"],
            "stopped-state conclusion drift")
    require(contradiction == {
        "entry_path_reached_if_linked_identity_and_view_apply": True,
        "durable_stamp_observed": False,
        "gc_runs_increment_observed": False,
        "why_double": (
            "the sampled root-scan is post-entry and post-gc_collect increment, "
            "yet both independently bound RAM witnesses retain reset values"),
        "classification": "BOOT-ENTRY-IDENTITY-OR-VIEW-FIRST-RED",
    }, "identity/view classification drift")
    require(decision["contact_consumed"]
            and not decision["new_contact_authorized"]
            and not decision["product_hang_claim"]
            and not decision["allocation_GC_loop_claim"]
            and not decision["slow_progress_claim"]
            and not decision["F018B_membership_claim"]
            and not decision["R_A_I_G_claim"]
            and decision["X_regression"] ==
            "observation only; not an atomic or monotonic oracle",
            "claim/contact boundary drift")


def expected() -> dict[str, Any]:
    facts = exact_facts()
    audit(facts)
    return {
        "format": "lisp65-c2.3-v1.6-defstruct-D2-durable-progress-first-red-v1",
        "recorded_on": date.today().isoformat(),
        "status": "DESK-FIRST-RED-BOOT-ENTRY-IDENTITY-OR-VIEW",
        "authorities": {"plan": bind(PLAN), "preparation": bind(PREP),
                        "device": bind(DEVICE), "durable_witness": bind(DURABLE),
                        "driver": bind(DRIVER)},
        "facts": facts,
        "execution_witnesses": [
            "the staged payload is byteidentical to the prepared two-byte sibling",
            "$B5C3 read back as $D7 after all loads and before physical RUN",
            "all three PCs are inside the bound root-scan interval",
            "$B5C3 remains $D7 in all three stopped samples",
            "gc_runs remains zero although the linked scan follows its increment",
            "the final CPU state remains stopped and no measured form ran",
        ],
        "rejected_mutations": [
            "claim-entry-stamp", "claim-gc-runs-increment", "claim-product-hang",
            "claim-allocation-loop", "claim-slow-progress", "claim-F018B",
            "claim-R-A-I-G", "claim-new-contact", "claim-CPU-resumed",
            "promote-X-to-oracle", "drop-payload-readback",
        ],
        "claim_limit": (
            "Classification of the consumed durable-progress contact only. "
            "No product hang, allocation loop, slow progress, F018B membership, "
            "R/A/I/G result, reset, resume, measured form or new contact is claimed."),
    }


def selftest() -> dict[str, Any]:
    base = exact_facts()
    cases: dict[str, tuple[list[str], Any]] = {
        "claim-entry-stamp": (["contradiction", "durable_stamp_observed"], True),
        "claim-gc-runs-increment":
            (["contradiction", "gc_runs_increment_observed"], True),
        "claim-product-hang": (["decision", "product_hang_claim"], True),
        "claim-allocation-loop": (["decision", "allocation_GC_loop_claim"], True),
        "claim-slow-progress": (["decision", "slow_progress_claim"], True),
        "claim-F018B": (["decision", "F018B_membership_claim"], True),
        "claim-R-A-I-G": (["decision", "R_A_I_G_claim"], True),
        "claim-new-contact": (["decision", "new_contact_authorized"], True),
        "claim-CPU-resumed": (["samples", "CPU_left_stopped"], False),
        "promote-X-to-oracle": (["decision", "X_regression"], "monotonic oracle"),
        "drop-payload-readback": (["staging", "payload_byteidentical"], False),
    }
    rejected = []
    for name, (path, replacement) in cases.items():
        trial = deepcopy(base)
        cursor: Any = trial
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except ResultError:
            rejected.append(name)
        else:
            raise ResultError(f"mutation survived: {name}")
    require(len(rejected) == len(cases), "mutation count drift")
    return {"status": "SELFTEST PASS", "mutations": len(rejected)}


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        value = selftest()
    else:
        value = expected()
        if args.action == "write":
            RESULT.write_bytes(canonical(value))
        else:
            require(RESULT.is_file() and RESULT.read_bytes() == canonical(value),
                    "durable progress First-Red receipt drift")
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResultError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print("c2-v1.6-durable-progress-result: FIRST RED: " + str(error))
        raise SystemExit(2)
