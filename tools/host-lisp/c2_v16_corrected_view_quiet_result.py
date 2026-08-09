#!/usr/bin/env python3
"""Close the owner-authorized quiet corrected-view recontact."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTACT_COMMIT = "63b3d495"
PLAN = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
DEVICE = EVIDENCE / (
    "c2.3-v1.6-defstruct-d2-corrected-view-quiet-device-receipt.json")
PREPARATION = EVIDENCE / (
    "c2.3-v1.6-defstruct-d2-corrected-view-quiet-preparation-receipt.json")
HISTORICAL = EVIDENCE / (
    "c2.3-v1.6-defstruct-d2-corrected-view-result-receipt.json")
PRIOR = EVIDENCE / (
    "c2.3-v1.6-defstruct-d2-identity-view-desk-attribution-receipt.json")
RESULT = EVIDENCE / (
    "c2.3-v1.6-defstruct-d2-corrected-view-quiet-result-receipt.json")
DRIVER = Path(__file__).resolve()


class QuietResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise QuietResultError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {"path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
            "bytes": len(raw), "sha256": digest(raw)}


def run(args: list[str]) -> bytes:
    process = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    require(process.returncode == 0,
            f"command failed ({' '.join(args)}): "
            f"{process.stderr.decode(errors='replace')}")
    return process.stdout


def git_blob(commit: str, path: str) -> tuple[str, bytes]:
    full = run(["git", "rev-parse", f"{commit}^{{commit}}"] ).decode().strip()
    return full, run(["git", "show", f"{full}:{path}"])


def bind_blob(label: str, raw: bytes) -> dict[str, Any]:
    return {"path": label, "bytes": len(raw), "sha256": digest(raw)}


def write_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def exact_facts() -> tuple[dict[str, Any], dict[str, Any]]:
    contact_commit, plan = git_blob(CONTACT_COMMIT, PLAN)
    plan_text = plan.decode("utf-8")
    require("Corrected-view quiet recontact raw result — 2026-08-05"
            in plan_text
            and "the owner saw BASIC `READY.`; the monitor appeared"
            in plan_text
            and "only after RETURN" in plan_text,
            "owner physical observation authority drift")

    device, preparation, historical, prior = (
        load(path) for path in (DEVICE, PREPARATION, HISTORICAL, PRIOR))
    require(device["status"] == "VIEW-OR-OWNER-FIRST-RED"
            and device["result"]["CPU_left_stopped"]
            and device["result"]["all_state_reads_CPU_view"]
            and device["result"]["MAPH_MAPL_bound_per_sample"]
            and device["result"]["first_observation_quiet_seconds"] >= 27.653
            and device["result"]["measured_forms_run"] == 0
            and not device["result"]["R_A_I_G_claimed"],
            "quiet device boundary drift")
    require(preparation["status"] ==
            "HOST-GREEN; ONE QUIET RECONTACT AUTHORIZED"
            and preparation["facts"]["appointment"]["recontact_authorized"],
            "quiet preparation authority drift")
    require(historical["status"] ==
            "CORRECTED: NON-PRODUCT SAMPLES; LAUNCH OUTCOME UNDECIDABLE"
            and historical["facts"]["code_owner"]["selected_owner"] ==
            "C65/BOOT high-MAP KERNAL/BASIC image; non-product",
            "historical live-owner authority drift")
    require(prior["status"] ==
            "ATTRIBUTED WRONG E000 OWNER PLUS PHYSICAL-RAM VIEW",
            "view-attribution authority drift")

    samples = device["samples"]
    require(len(samples) == 3, "quiet sample count drift")
    live = historical["facts"]["code_owner"]["live_E000_bytes"]
    product = historical["facts"]["code_owner"]["product_E000_bytes"]
    require(live != product
            and all(row["E000_owner"]["observed"] == live
                    for row in samples),
            "historical live-E000 continuity drift")
    require(all(row["mapping"]["MAPH"] == "0x8300"
                and row["mapping"]["MAPL"] == "0x82a0"
                and row["durable_witness"] == "0xd7"
                and row["freelist_head"] == "0x0000"
                and row["gc_runs"] == 0 for row in samples),
            "quiet stopped-state tuple drift")
    require(historical["facts"]["code_owner"]["product_required_MAPHI"] ==
            "0x8f00", "product MAP authority drift")

    facts = {
        "choreography": {
            "physical_READY_before_RUN": True,
            "monitor_appeared_only_after_RETURN": True,
            "first_observation_quiet_seconds":
                device["result"]["first_observation_quiet_seconds"],
            "quiet_floor_seconds": 27.653,
            "samples": 3, "CPU_left_stopped": True,
        },
        "view_and_owner": {
            "all_reads_CPU_view": True,
            "MAPH": "0x8300", "MAPL": "0x82a0",
            "product_required_MAPHI": "0x8f00",
            "observed_E000_bytes": live,
            "product_E000_bytes": product,
            "selected_owner_class":
                "historical-live-C65/BOOT-high-MAP-non-product",
            "configured_ROM_exact_match": False,
            "exact_backing_image_named": False,
            "symbol_interpretation": "none; ownership precedes symbols",
        },
        "launch": {
            "PCs": [row["PC"] for row in samples],
            "durable_entry_witness": [row["durable_witness"]
                                      for row in samples],
            "diagnostic_entry_observed": False,
            "classification":
                "PHYSICAL-RUN-ENTERED-MONITOR-WITHOUT-DIAGNOSTIC-ENTRY",
            "control_launch_divergence_explained": False,
        },
        "decision": {
            "contact_consumed": True, "new_contact_authorized": False,
            "measured_forms_run": 0, "R_A_I_G_claim": False,
            "product_hang_claim": False, "F018B_membership_claim": False,
            "next_step": ("desk attribution of the physical BASIC RUN "
                          "handover before any further contact question"),
        },
    }
    authorities = {
        "owner_observation_and_raw_disposition": bind_blob(
            f"git:{contact_commit}:{PLAN}", plan),
        "device": bind(DEVICE), "preparation": bind(PREPARATION),
        "historical_live_owner": bind(HISTORICAL),
        "identity_view_attribution": bind(PRIOR), "driver": bind(DRIVER),
    }
    return facts, authorities


def audit(facts: dict[str, Any]) -> None:
    choreography = facts["choreography"]
    owner = facts["view_and_owner"]
    launch = facts["launch"]
    decision = facts["decision"]
    require(choreography["physical_READY_before_RUN"]
            and choreography["monitor_appeared_only_after_RETURN"]
            and choreography["first_observation_quiet_seconds"] >=
                choreography["quiet_floor_seconds"] == 27.653
            and choreography["samples"] == 3
            and choreography["CPU_left_stopped"],
            "quiet choreography result drift")
    require(owner["all_reads_CPU_view"] and owner["MAPH"] == "0x8300"
            and owner["MAPL"] == "0x82a0"
            and owner["product_required_MAPHI"] == "0x8f00"
            and owner["observed_E000_bytes"] != owner["product_E000_bytes"]
            and owner["selected_owner_class"] ==
                "historical-live-C65/BOOT-high-MAP-non-product"
            and not owner["configured_ROM_exact_match"]
            and not owner["exact_backing_image_named"]
            and owner["symbol_interpretation"] ==
                "none; ownership precedes symbols",
            "quiet code-owner closure drift")
    require(launch["durable_entry_witness"] == ["0xd7"] * 3
            and not launch["diagnostic_entry_observed"]
            and launch["classification"] ==
                "PHYSICAL-RUN-ENTERED-MONITOR-WITHOUT-DIAGNOSTIC-ENTRY"
            and not launch["control_launch_divergence_explained"],
            "quiet launch conclusion drift")
    require(decision["contact_consumed"]
            and not decision["new_contact_authorized"]
            and decision["measured_forms_run"] == 0
            and not decision["R_A_I_G_claim"]
            and not decision["product_hang_claim"]
            and not decision["F018B_membership_claim"],
            "quiet claim boundary drift")


def rejected_mutations(facts: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[list[Any], Any]] = {
        "erase-READY": (["choreography", "physical_READY_before_RUN"], False),
        "monitor-before-RETURN":
            (["choreography", "monitor_appeared_only_after_RETURN"], False),
        "shorten-quiet-floor":
            (["choreography", "first_observation_quiet_seconds"], 0.0),
        "resume-CPU": (["choreography", "CPU_left_stopped"], False),
        "physical-view": (["view_and_owner", "all_reads_CPU_view"], False),
        "discard-MAPH": (["view_and_owner", "MAPH"], "unknown"),
        "select-product-map": (["view_and_owner", "MAPH"], "0x8f00"),
        "same-product-bytes":
            (["view_and_owner", "product_E000_bytes"],
             facts["view_and_owner"]["observed_E000_bytes"]),
        "invent-exact-ROM":
            (["view_and_owner", "configured_ROM_exact_match"], True),
        "name-unknown-backing":
            (["view_and_owner", "exact_backing_image_named"], True),
        "symbolize-before-owner":
            (["view_and_owner", "symbol_interpretation"], "product ELF"),
        "claim-entry": (["launch", "diagnostic_entry_observed"], True),
        "claim-control-explained":
            (["launch", "control_launch_divergence_explained"], True),
        "authorize-contact": (["decision", "new_contact_authorized"], True),
        "invent-form": (["decision", "measured_forms_run"], 1),
        "claim-R-A-I-G": (["decision", "R_A_I_G_claim"], True),
        "claim-product-hang": (["decision", "product_hang_claim"], True),
        "claim-F018B": (["decision", "F018B_membership_claim"], True),
    }
    rejected: dict[str, str] = {}
    for label, (path, replacement) in cases.items():
        trial = deepcopy(facts)
        cursor: Any = trial
        for component in path[:-1]:
            cursor = cursor[component]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except QuietResultError as error:
            rejected[label] = str(error)
        else:
            raise QuietResultError(f"verification mutation survived: {label}")
    return rejected


def expected() -> dict[str, Any]:
    facts, authorities = exact_facts()
    audit(facts)
    return {
        "format": "lisp65-c2.3-v1.6-D2-corrected-view-quiet-result-v1",
        "recorded_on": date.today().isoformat(),
        "status": "PHYSICAL RUN ENTERED MONITOR; DIAGNOSTIC ENTRY NOT REACHED",
        "authorities": authorities, "facts": facts,
        "execution_witnesses": [
            "owner saw BASIC READY immediately before physical RUN",
            "monitor appeared only after physical RETURN",
            "first runner monitor access followed 27.653065 seconds of silence",
            "all three stopped-state reads use the CPU-resolved view",
            "all samples bind MAPH=0x8300 and MAPL=0x82a0",
            "current E000 bytes equal the bound historical live high-MAP stream",
            "current E000 bytes differ from the diagnostic product window",
            "the durable diagnostic-entry witness remains reset three times",
            "the exact backing image remains deliberately unnamed",
            "the CPU remains stopped and the one-shot contact is consumed",
        ],
        "mutations_rejected": rejected_mutations(facts),
        "claim_limit": (
            "Closes the owner-authorized quiet launch contact: the physical "
            "RUN entered a visible monitor state without reaching the durable "
            "diagnostic entry hook. It names only the historical non-product "
            "high-MAP owner class, not an exact ROM image. It claims no product "
            "hang, F018B membership, R/A/I/G row, form, fix or further contact."),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    value = expected()
    if args.action == "write":
        write_json(RESULT, value)
    elif args.action == "check":
        require(RESULT.is_file() and RESULT.read_bytes() == canonical(value),
                "corrected-view quiet result receipt drift")
    else:
        value = {"status": "SELFTEST PASS",
                 "mutations": len(value["mutations_rejected"])}
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (QuietResultError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-v1.6-corrected-view-quiet-result: FIRST RED: " + str(error))
        raise SystemExit(2)
