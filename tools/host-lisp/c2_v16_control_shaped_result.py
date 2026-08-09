#!/usr/bin/env python3
"""Close the no-prelaunch-monitor v1.6 launch discriminator."""

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
CONTACT_COMMIT = "5d656d6a"
PLAN = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
DEVICE = EVIDENCE / "c2.3-v1.6-defstruct-d2-control-shaped-device-receipt.json"
PREPARATION = EVIDENCE / "c2.3-v1.6-defstruct-d2-control-shaped-preparation-receipt.json"
QUIET_RESULT = EVIDENCE / "c2.3-v1.6-defstruct-d2-corrected-view-quiet-result-receipt.json"
HANDOVER = EVIDENCE / "c2.3-v1.6-defstruct-d2-physical-run-handover-desk-receipt.json"
CONTROL = EVIDENCE / "c2.3-v1.6-defstruct-d2-launch-boundary-control-device-receipt.json"
RESULT = EVIDENCE / "c2.3-v1.6-defstruct-d2-control-shaped-result-receipt.json"
DRIVER = Path(__file__).resolve()


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


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
    require("Control-shaped discriminator raw result — 2026-08-05" in plan_text
            and "again saw the monitor instead of a prompt" in plan_text
            and "This time no prelaunch monitor" in plan_text
            and "crossing existed:" in plan_text,
            "owner observation authority drift")
    device, prep, prior, handover, control = (
        load(path) for path in
        (DEVICE, PREPARATION, QUIET_RESULT, HANDOVER, CONTROL))
    require(device["status"] == "VIEW-OR-OWNER-FIRST-RED"
            and device["result"]["CPU_left_stopped"]
            and device["result"]["first_observation_quiet_seconds"] >= 27.653
            and not device["result"]["prelaunch_monitor_crossing"]
            and device["result"]["measured_forms_run"] == 0
            and not device["result"]["R_A_I_G_claimed"],
            "device boundary drift")
    require(prep["status"] ==
            "HOST-GREEN; ONE CONTROL-SHAPED CONTACT AUTHORIZED"
            and not prep["facts"]["choreography"]["prelaunch_monitor_crossing"],
            "preparation authority drift")
    require(prior["status"] ==
            "PHYSICAL RUN ENTERED MONITOR; DIAGNOSTIC ENTRY NOT REACHED",
            "prior quiet result drift")
    require(handover["status"] ==
            "BOUNDARY NAMED; PRELAUNCH MONITOR CROSSING LEADS"
            and not handover["facts"]["decision"]["causal_mechanism_proved"],
            "handover hypothesis authority drift")
    require(control["status"] == "CONTROL-PHYSICAL-BOOT-PASS"
            and control["control_identity"]["screen_result"]["visible_REPL"],
            "physical control authority drift")

    samples = device["samples"]
    live = prior["facts"]["view_and_owner"]["observed_E000_bytes"]
    product = prior["facts"]["view_and_owner"]["product_E000_bytes"]
    require(len(samples) == 3 and live != product
            and all(row["E000_owner"]["observed"] == live
                    and row["mapping"]["MAPH"] == "0x8300"
                    and row["mapping"]["MAPL"] == "0x82a0"
                    and row["durable_witness"] == "0xd7"
                    and row["freelist_head"] == "0x0000"
                    and row["gc_runs"] == 0 for row in samples),
            "control-shaped stopped-state tuple drift")

    facts = {
        "experiment": {
            "treatment_removed": "prelaunch monitor-sync/t1/reads/t0",
            "prelaunch_monitor_crossing_present": False,
            "owner_observed_monitor_after_RETURN": True,
            "visible_lisp65_prompt": False,
            "outcome_matches_prior_failed_launch": True,
            "prelaunch_monitor_crossing_causal": False,
        },
        "view_and_owner": {
            "all_reads_CPU_view": True, "MAPH": "0x8300", "MAPL": "0x82a0",
            "observed_E000_bytes": live, "product_E000_bytes": product,
            "selected_owner_class":
                "historical-live-C65/BOOT-high-MAP-non-product",
            "exact_backing_image_named": False,
        },
        "launch": {
            "PCs": [row["PC"] for row in samples],
            "durable_entry_witness": [row["durable_witness"] for row in samples],
            "diagnostic_entry_observed": False,
            "first_executable_diagnostic_delta": "0x202c",
            "named_boundary": "target-side physical launch before $202c",
            "residual_target_side_launch_difference": True,
            "mechanism_attributed": False,
        },
        "decision": {
            "contact_consumed": True, "new_contact_authorized": False,
            "measured_forms_run": 0, "R_A_I_G_claim": False,
            "product_hang_claim": False, "F018B_membership_claim": False,
            "next_step":
                "desk attribution of the residual target-side launch difference",
        },
    }
    return facts, {
        "owner_observation": bind_blob(f"git:{contact_commit}:{PLAN}", plan),
        "device": bind(DEVICE), "preparation": bind(PREPARATION),
        "prior_quiet_result": bind(QUIET_RESULT), "handover": bind(HANDOVER),
        "physical_control": bind(CONTROL), "driver": bind(DRIVER),
    }


def audit(facts: dict[str, Any]) -> None:
    experiment = facts["experiment"]
    owner = facts["view_and_owner"]
    launch = facts["launch"]
    decision = facts["decision"]
    require(experiment["treatment_removed"] ==
            "prelaunch monitor-sync/t1/reads/t0"
            and not experiment["prelaunch_monitor_crossing_present"]
            and experiment["owner_observed_monitor_after_RETURN"]
            and not experiment["visible_lisp65_prompt"]
            and experiment["outcome_matches_prior_failed_launch"]
            and not experiment["prelaunch_monitor_crossing_causal"],
            "discriminator conclusion drift")
    require(owner["all_reads_CPU_view"] and owner["MAPH"] == "0x8300"
            and owner["MAPL"] == "0x82a0"
            and owner["observed_E000_bytes"] != owner["product_E000_bytes"]
            and owner["selected_owner_class"] ==
                "historical-live-C65/BOOT-high-MAP-non-product"
            and not owner["exact_backing_image_named"],
            "owner closure drift")
    require(launch["durable_entry_witness"] == ["0xd7"] * 3
            and not launch["diagnostic_entry_observed"]
            and launch["first_executable_diagnostic_delta"] == "0x202c"
            and launch["named_boundary"] ==
                "target-side physical launch before $202c"
            and launch["residual_target_side_launch_difference"]
            and not launch["mechanism_attributed"],
            "residual launch boundary drift")
    require(decision["contact_consumed"]
            and not decision["new_contact_authorized"]
            and decision["measured_forms_run"] == 0
            and not decision["R_A_I_G_claim"]
            and not decision["product_hang_claim"]
            and not decision["F018B_membership_claim"],
            "claim boundary drift")


def rejected_mutations(facts: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[list[str], Any]] = {
        "restore-prelaunch":
            (["experiment", "prelaunch_monitor_crossing_present"], True),
        "invent-prompt": (["experiment", "visible_lisp65_prompt"], True),
        "erase-monitor":
            (["experiment", "owner_observed_monitor_after_RETURN"], False),
        "claim-prelaunch-causal":
            (["experiment", "prelaunch_monitor_crossing_causal"], True),
        "different-outcome":
            (["experiment", "outcome_matches_prior_failed_launch"], False),
        "physical-view": (["view_and_owner", "all_reads_CPU_view"], False),
        "select-product-map": (["view_and_owner", "MAPH"], "0x8f00"),
        "same-product-bytes":
            (["view_and_owner", "product_E000_bytes"],
             facts["view_and_owner"]["observed_E000_bytes"]),
        "name-unknown-backing":
            (["view_and_owner", "exact_backing_image_named"], True),
        "invent-entry": (["launch", "diagnostic_entry_observed"], True),
        "move-delta": (["launch", "first_executable_diagnostic_delta"], "0x2023"),
        "erase-target-difference":
            (["launch", "residual_target_side_launch_difference"], False),
        "claim-mechanism": (["launch", "mechanism_attributed"], True),
        "authorize-contact": (["decision", "new_contact_authorized"], True),
        "invent-form": (["decision", "measured_forms_run"], 1),
        "claim-R-A-I-G": (["decision", "R_A_I_G_claim"], True),
        "claim-product-hang": (["decision", "product_hang_claim"], True),
        "claim-F018B": (["decision", "F018B_membership_claim"], True),
    }
    rejected: dict[str, str] = {}
    for name, (path, replacement) in cases.items():
        trial = deepcopy(facts)
        cursor: Any = trial
        for component in path[:-1]:
            cursor = cursor[component]
        cursor[path[-1]] = replacement
        try:
            audit(trial)
        except ResultError as error:
            rejected[name] = str(error)
        else:
            raise ResultError(f"verification mutation survived: {name}")
    return rejected


def expected() -> dict[str, Any]:
    facts, authorities = exact_facts()
    audit(facts)
    return {
        "format": "lisp65-c2.3-v1.6-D2-control-shaped-result-v1",
        "recorded_on": date.today().isoformat(),
        "status":
            "PRELAUNCH MONITOR HYPOTHESIS FALSIFIED; TARGET-SIDE BOUNDARY REMAINS",
        "authorities": authorities, "facts": facts,
        "mutations_rejected": rejected_mutations(facts),
        "claim_limit": (
            "Closes the control-shaped discriminator. Removing the prelaunch "
            "monitor crossing did not change the physical monitor/no-entry "
            "outcome, so that hypothesis is falsified. The remaining boundary "
            "is target-side and before $202C, but its mechanism is not yet "
            "attributed. No product hang, F018B, R/A/I/G, form, fix or contact "
            "is claimed."),
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
                "control-shaped result receipt drift")
    else:
        value = {"status": "SELFTEST PASS",
                 "mutations": len(value["mutations_rejected"])}
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResultError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-v1.6-control-shaped-result: FIRST RED: " + str(error))
        raise SystemExit(2)
