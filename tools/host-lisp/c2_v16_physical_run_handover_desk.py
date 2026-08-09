#!/usr/bin/env python3
"""Narrow the v1.6 physical RUN handover without another contact."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
QUIET = EVIDENCE / "c2.3-v1.6-defstruct-d2-corrected-view-quiet-result-receipt.json"
CONTROL_DEVICE = EVIDENCE / "c2.3-v1.6-defstruct-d2-launch-boundary-control-device-receipt.json"
CONTROL_PRG = ROOT / "build/c2.3/v1.6-defstruct-phase-c/artifacts/control-link82.prg"
DIAGNOSTIC_PRG = ROOT / ("build/c2.3/v1.6-defstruct-closing-session/"
                         "d2-corrected-view-quiet-appointment/"
                         "diagnostic-link82-corrected-view-b5c3.prg")
CONTROL_RUNNER = ROOT / "scripts/c2-v16-defstruct-launch-boundary-control.sh"
DIAGNOSTIC_RUNNER = ROOT / "scripts/c2-v16-defstruct-corrected-view-hw.sh"
CONTACT_DRIVER = ROOT / "tools/host-lisp/c2_v16_corrected_view_contact.py"
RESULT = EVIDENCE / "c2.3-v1.6-defstruct-d2-physical-run-handover-desk-receipt.json"
DRIVER = Path(__file__).resolve()


class HandoverError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise HandoverError(message)


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


def prg(path: Path) -> tuple[int, bytes]:
    raw = path.read_bytes()
    require(len(raw) >= 2, f"truncated PRG: {path}")
    return int.from_bytes(raw[:2], "little"), raw[2:]


def at(path: Path, address: int, count: int) -> bytes:
    base, payload = prg(path)
    offset = address - base
    require(0 <= offset <= len(payload) - count,
            f"PRG address outside payload: 0x{address:04x}")
    return payload[offset:offset + count]


def first_difference(left: bytes, right: bytes, base: int) -> int:
    require(len(left) == len(right), "PRG length drift")
    for index, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return base + index
    raise HandoverError("identities unexpectedly byteidentical")


def write_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def exact_facts() -> tuple[dict[str, Any], dict[str, Any]]:
    quiet, control = load(QUIET), load(CONTROL_DEVICE)
    require(quiet["status"] ==
            "PHYSICAL RUN ENTERED MONITOR; DIAGNOSTIC ENTRY NOT REACHED"
            and quiet["facts"]["launch"]["durable_entry_witness"] == ["0xd7"] * 3,
            "quiet launch authority drift")
    require(control["status"] == "CONTROL-PHYSICAL-BOOT-PASS"
            and control["control_identity"]["physical_RUN"]
            and control["control_identity"]["screen_result"]["visible_REPL"]
            and not control["control_identity"]["screen_result"]["terminal_markers"],
            "control launch authority drift")

    control_base, control_payload = prg(CONTROL_PRG)
    diagnostic_base, diagnostic_payload = prg(DIAGNOSTIC_PRG)
    require(control_base == diagnostic_base == 0x2001, "PRG load address drift")
    require(first_difference(control_payload, diagnostic_payload, control_base)
            == 0x202C, "first executable delta drift")
    require(at(CONTROL_PRG, 0x2001, 0x22) ==
            at(DIAGNOSTIC_PRG, 0x2001, 0x22), "BASIC program identity drift")
    require(at(CONTROL_PRG, 0x2023, 9) == at(DIAGNOSTIC_PRG, 0x2023, 9)
            == bytes.fromhex("78a22f8600a23e8601"), "bootstrap prefix drift")
    require(at(CONTROL_PRG, 0x202C, 5) == bytes.fromhex("a2448e30d0")
            and at(DIAGNOSTIC_PRG, 0x202C, 5) == bytes.fromhex("203fc0eaea")
            and at(DIAGNOSTIC_PRG, 0xC03F, 9) ==
            bytes.fromhex("a2448e30d08ec3b560"), "entry witness delta drift")

    control_runner = CONTROL_RUNNER.read_text(encoding="utf-8")
    diagnostic_runner = DIAGNOSTIC_RUNNER.read_text(encoding="utf-8")
    contact_driver = CONTACT_DRIVER.read_text(encoding="utf-8")
    require('run_m65 -H "$product"' in control_runner
            and 'run_m65 -H "$PRODUCT"' in diagnostic_runner,
            "BASIC installation form drift")
    require("screen control-launch-ready" in control_runner
            and "prelaunch" not in control_runner, "control choreography drift")
    require("screen launch-ready" in diagnostic_runner
            and 'python3 "$PY" prelaunch' in diagnostic_runner,
            "diagnostic choreography drift")
    prelaunch = contact_driver.split("def prelaunch", 1)[1].split("def capture", 1)[0]
    require("SERIAL.monitor_sync" in prelaunch
            and 'command(fd, b"t1"' in prelaunch
            and 'command(fd, b"t0"' in prelaunch,
            "prelaunch monitor crossing drift")

    facts = {
        "identity": {
            "load_address": "0x2001",
            "BASIC_program_identical_through": "0x2022",
            "bootstrap_prefix_identical": "0x2023..0x202b",
            "first_executable_delta": "0x202c",
            "control_at_202c": "a2448e30d0",
            "diagnostic_at_202c": "203fc0eaea",
            "diagnostic_witness_routine_at_c03f": "a2448e30d08ec3b560",
            "witness_store": "STX $B5C3",
        },
        "reachability": {
            "entry_witness_after_quiet": ["0xd7"] * 3,
            "first_diagnostic_delta_completed": False,
            "later_diagnostic_delta_causal_claim": False,
        },
        "choreography_diff": {
            "both_install_PRG_with_m65_H": True,
            "control_post_READY_monitor_crossing": False,
            "diagnostic_post_READY_pre_owner_monitor_crossing": True,
            "diagnostic_crossing_sequence":
                ["monitor-sync", "t1", "CPU-view reads", "t0"],
            "only_unpaired_post_READY_pre_owner_action":
                "diagnostic prelaunch monitor crossing",
        },
        "decision": {
            "named_boundary": "post-READY pre-owner launch choreography before $202c",
            "leading_setup_hypothesis":
                "prelaunch monitor crossing changes or retains launch-visible state",
            "causal_mechanism_proved": False,
            "cheapest_discriminator":
                "control-shaped diagnostic launch with no prelaunch monitor crossing",
            "new_contact_authorized": False,
            "product_hang_claim": False, "F018B_membership_claim": False,
            "R_A_I_G_claim": False, "measured_forms_run": 0,
        },
    }
    return facts, {
        "quiet_result": bind(QUIET), "control_device": bind(CONTROL_DEVICE),
        "control_PRG": bind(CONTROL_PRG), "diagnostic_PRG": bind(DIAGNOSTIC_PRG),
        "control_runner": bind(CONTROL_RUNNER),
        "diagnostic_runner": bind(DIAGNOSTIC_RUNNER),
        "contact_driver": bind(CONTACT_DRIVER), "driver": bind(DRIVER),
    }


def audit(facts: dict[str, Any]) -> None:
    identity, reach = facts["identity"], facts["reachability"]
    choreography, decision = facts["choreography_diff"], facts["decision"]
    require(identity["BASIC_program_identical_through"] == "0x2022"
            and identity["bootstrap_prefix_identical"] == "0x2023..0x202b"
            and identity["first_executable_delta"] == "0x202c"
            and identity["witness_store"] == "STX $B5C3",
            "handover identity boundary drift")
    require(reach["entry_witness_after_quiet"] == ["0xd7"] * 3
            and not reach["first_diagnostic_delta_completed"]
            and not reach["later_diagnostic_delta_causal_claim"],
            "handover reachability boundary drift")
    require(choreography["both_install_PRG_with_m65_H"]
            and not choreography["control_post_READY_monitor_crossing"]
            and choreography["diagnostic_post_READY_pre_owner_monitor_crossing"]
            and choreography["diagnostic_crossing_sequence"] ==
                ["monitor-sync", "t1", "CPU-view reads", "t0"]
            and choreography["only_unpaired_post_READY_pre_owner_action"] ==
                "diagnostic prelaunch monitor crossing",
            "handover choreography comparison drift")
    require(decision["named_boundary"] ==
            "post-READY pre-owner launch choreography before $202c"
            and not decision["causal_mechanism_proved"]
            and not decision["new_contact_authorized"]
            and not decision["product_hang_claim"]
            and not decision["F018B_membership_claim"]
            and not decision["R_A_I_G_claim"]
            and decision["measured_forms_run"] == 0,
            "handover decision boundary drift")


def rejected_mutations(facts: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[list[str], Any]] = {
        "move-first-delta": (["identity", "first_executable_delta"], "0x2023"),
        "erase-BASIC-identity":
            (["identity", "BASIC_program_identical_through"], "unknown"),
        "erase-bootstrap-identity":
            (["identity", "bootstrap_prefix_identical"], "unknown"),
        "erase-witness-store": (["identity", "witness_store"], "unknown"),
        "claim-first-delta-completed":
            (["reachability", "first_diagnostic_delta_completed"], True),
        "claim-later-delta-cause":
            (["reachability", "later_diagnostic_delta_causal_claim"], True),
        "invent-entry-stamp":
            (["reachability", "entry_witness_after_quiet"], ["0x44"] * 3),
        "erase-shared-installer":
            (["choreography_diff", "both_install_PRG_with_m65_H"], False),
        "invent-control-crossing":
            (["choreography_diff", "control_post_READY_monitor_crossing"], True),
        "erase-diagnostic-crossing":
            (["choreography_diff", "diagnostic_post_READY_pre_owner_monitor_crossing"], False),
        "erase-crossing-sequence":
            (["choreography_diff", "diagnostic_crossing_sequence"], []),
        "claim-causal-mechanism":
            (["decision", "causal_mechanism_proved"], True),
        "authorize-contact": (["decision", "new_contact_authorized"], True),
        "claim-product-hang": (["decision", "product_hang_claim"], True),
        "claim-F018B": (["decision", "F018B_membership_claim"], True),
        "claim-R-A-I-G": (["decision", "R_A_I_G_claim"], True),
        "invent-form": (["decision", "measured_forms_run"], 1),
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
        except HandoverError as error:
            rejected[name] = str(error)
        else:
            raise HandoverError(f"verification mutation survived: {name}")
    return rejected


def expected() -> dict[str, Any]:
    facts, authorities = exact_facts()
    audit(facts)
    return {
        "format": "lisp65-c2.3-v1.6-D2-physical-RUN-handover-desk-v1",
        "recorded_on": date.today().isoformat(),
        "status": "BOUNDARY NAMED; PRELAUNCH MONITOR CROSSING LEADS",
        "authorities": authorities, "facts": facts,
        "mutations_rejected": rejected_mutations(facts),
        "claim_limit": (
            "Host/artifact-only narrowing. The first executable diagnostic "
            "delta is at $202C and remained uncompleted; the prelaunch monitor "
            "crossing is the only unpaired post-READY pre-owner runner action. "
            "It is not yet causal. No contact, form, product claim, F018B "
            "membership or R/A/I/G row is authorized."),
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
                "physical RUN handover desk receipt drift")
    else:
        value = {"status": "SELFTEST PASS",
                 "mutations": len(value["mutations_rejected"])}
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HandoverError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-v1.6-physical-run-handover-desk: FIRST RED: " + str(error))
        raise SystemExit(2)
