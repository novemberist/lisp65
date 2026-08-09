#!/usr/bin/env python3
"""Bind the transport-proof RAM-entry D2 choreography before hardware."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import c2_v16_d2_ram_entry_witness as ENTRY  # noqa: E402
import c2_v16_d2_launch_screen as SCREEN  # noqa: E402


PLAN = ROOT / "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
TRANSPORT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-D2-transport-desk-attribution-receipt.json")
PHASE_C = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-phase-c-diagnostic-preparation-receipt.json")
DEPLOY = ROOT / "build/c2.3/v1.6-defstruct-phase-c/deployment.json"
RUNNER = ROOT / "scripts/c2-v16-defstruct-closing-d2-hw.sh"
WITNESS = ROOT / "tools/host-lisp/c2_v16_d2_ram_entry_witness.py"
SCREEN_CLASSIFIER = ROOT / "tools/host-lisp/c2_v16_d2_launch_screen.py"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-closing-d2-RAM-entry-device-first-red-receipt.json")
HALF_MAPPED_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-closing-d2-half-mapped-entry-device-first-red-receipt.json")
SIXTH_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-closing-d2-complete-pair-entry-device-first-red-receipt.json")
PHYSICAL_FALLBACK = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-physical-fallback-preparation-receipt.json")
PHYSICAL_LAUNCH_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-physical-launch-no-repl-device-first-red-receipt.json")
PHYSICAL_RUNNER = ROOT / "scripts/c2-v16-defstruct-closing-d2-physical.sh"
PRIOR_LAUNCH_SCREENS = (
    ROOT / "build/c2.3/v1.6-defstruct-closing-session/d2/launch-before-return.txt",
    ROOT / ("build/c2.3/v1.6-defstruct-closing-session/"
            "d2-arm-order-correction/launch-before-return.txt"),
)
DRIVER = Path(__file__).resolve()
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.6-defstruct-d2-choreography-closure-receipt.json")
FORMAT = "lisp65-c2.3-v1.6-D2-choreography-closure-v2"


class ClosureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ClosureError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    return {"path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha256(path)}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def runner_audit() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    require("c2_v16_d2_entry_witness.py" not in source,
            "obsolete monitor-breakpoint entry helper survived")
    require("c2_v16_d2_ram_entry_witness.py" in source,
            "RAM entry helper absent")
    require("c2_v16_d2_launch_screen.py" in source,
            "case-normalized launch-screen classifier absent")
    launch = source.index("screen launch-before-return")
    prompt = source.index('python3 "$LAUNCH_SCREEN" classify', launch)
    submit = source.index('python3 "$ENTRY" submit', prompt)
    after = source.index("screen boot-after-entry", submit)
    workbench = source.index("grep -q 'lisp65>'", after)
    readback = source.index('readback "$entry_stamp" 1', workbench)
    decode = source.index('python3 "$ENTRY" decode', readback)
    context = source.index("# Immediate context asserts", decode)
    require(launch < prompt < submit < after < workbench < readback < decode < context,
            "RETURN/RAM-entry/context ordering drift")
    require("! grep -q 'lisp65>'" not in source[prompt:submit],
            "obsolete split Workbench rejection unexpectedly survived")
    require('python3 "$ENTRY" device' not in source[launch:context]
            and "b2023" not in source[launch:context].lower(),
            "launch still invokes the obsolete monitor-breakpoint witness")
    require("contact.consumed" in source and "FTP_STALL_LIMIT" in source,
            "one-contact/progress guard absent")
    require("d2-ram-entry-witness-complete-map" in source,
            "corrected contact does not have a fresh accounting directory")
    require_start = source.index('quiet_input require "$require_form"')
    reset = source.index('run_m65 -H -@ "$reset@$record_hex"', require_start)
    arm = source.index('run_m65 -H -@ "$arm@$record_hex"', reset)
    defstruct = source.index('quiet_input defstruct "$defstruct_form"', arm)
    require(require_start < reset < arm < defstruct,
            "full record reset/arm is not between require and defstruct")
    for marker in ("sleep 120", "sleep 180", "record-1.bin",
                   "record-2.bin", "record-3.bin"):
        require(marker in source, f"quiet/stable-read policy absent: {marker}")


def witness_source_audit() -> None:
    source = WITNESS.read_text(encoding="utf-8")
    submit = source.index("def submit_return")
    classify = source.index("def classify")
    require('MONITOR.monitor_command(fd, b"t0"' in source[submit:]
            and 'MONITOR.virtual_matrix_press(fd, "~M")' in source[submit:],
            "Stage-1-proved virtual RETURN transport absent")
    submit_body = source[submit:].split("def main", 1)[0]
    require('SERIAL.slow_write(fd, f"b' not in submit_body
            and 'MONITOR.monitor_command(fd, b"t1"' not in submit_body,
            "RETURN submit path arms or consumes a monitor breakpoint")
    require('method == "RAM-store-at-_start"' in source[classify:]
            and "live monitor breakpoint across launch" in source[classify:],
            "RAM witness method/breakpoint rejection absent")
    require("RAM_mapping_active_before_entry_call" in source
            and 'bytes.fromhex(witness["RAM_mapping_activation_bytes"])' in source,
            "entry witness does not prove RAM mapping before the far routine")


def facts() -> dict[str, Any]:
    transport = load(TRANSPORT)
    phase_c = load(PHASE_C)
    deployment = load(DEPLOY)
    require(transport["status"] == "attributed-breakpoint-loss-not-RETURN-loss"
            and transport["facts"]["transport_decision"]["decision"] ==
            "breakpoint-loss-not-RETURN-loss"
            and transport["facts"]["transport_decision"]["virtual_RETURN_arrival"] ==
            "proved-by-execution-beyond-_start",
            "Stage-1 transport authority drift")
    require(phase_c["status"] ==
            "PREPARED-NON-PROMOTABLE-LINK82-DIAGNOSTIC",
            "Phase-C authority status drift")
    entry_selftest = ENTRY.selftest(DEPLOY)
    screen_selftest = SCREEN.selftest()
    first_red = load(FIRST_RED)
    screen_row = first_red["setup_first_red"]["launch_screen_text"]
    observed_path = ROOT / screen_row["path"]
    require(bind(observed_path) == screen_row,
            "bound RUN:+BREAK screen evidence drift")
    observed_text = observed_path.read_text(encoding="utf-8", errors="replace")
    observed_view = SCREEN.inspect(observed_text)
    require(observed_view["run_seen_casefolded"]
            and observed_view["terminal_markers"] == [
                "BREAK", "MONITOR-COMMANDS", "MONITOR-REGISTER-HEADER"],
            "bound RUN:+BREAK screen no longer matches the classifier fixture")
    try:
        SCREEN.classify(observed_text)
    except SCREEN.LaunchScreenError as error:
        observed_rejection = str(error)
    else:
        raise ClosureError("bound RUN:+BREAK screen was classified healthy")
    half_mapped_red = load(HALF_MAPPED_RED)
    half_screen_row = half_mapped_red["setup_first_red"]["launch_screen_text"]
    half_screen_path = ROOT / half_screen_row["path"]
    require(bind(half_screen_path) == half_screen_row,
            "bound half-mapped RUN:+BREAK screen evidence drift")
    half_screen_text = half_screen_path.read_text(
        encoding="utf-8", errors="replace")
    half_screen_view = SCREEN.inspect(half_screen_text)
    require(half_screen_view["run_seen_casefolded"]
            and half_screen_view["terminal_markers"] == [
                "BREAK", "MONITOR-COMMANDS", "MONITOR-REGISTER-HEADER"],
            "half-mapped RUN:+BREAK screen classification drift")
    try:
        SCREEN.classify(half_screen_text)
    except SCREEN.LaunchScreenError as error:
        half_screen_rejection = str(error)
    else:
        raise ClosureError("half-mapped RUN:+BREAK screen was classified healthy")
    sixth_red = load(SIXTH_RED)
    physical_fallback = load(PHYSICAL_FALLBACK)
    physical_launch_red = load(PHYSICAL_LAUNCH_RED)
    require(sixth_red["status"] ==
            "FIRST RED: virtual runner launch strand exhausted; physical-owner fallback active"
            and physical_fallback["status"] ==
            "prepared-hook-free-physical-owner-fallback"
            and physical_fallback["facts"]["virtual_launch_contacts_remaining"] == 0
            and not physical_fallback["facts"]["entry_hook_present"]
            and physical_launch_red["status"] ==
            "FIRST RED: corrected physical RUN did not reach REPL; contact ended before D2"
            and physical_launch_red["contact"]["measured_forms_run"] == 0,
            "sixth-red/physical-fallback authority drift")
    prior_screens = []
    for path in PRIOR_LAUNCH_SCREENS:
        row = bind(path)
        view = SCREEN.inspect(path.read_text(encoding="utf-8", errors="replace"))
        require(view["run_seen_casefolded"] and not view["terminal_markers"],
                f"prior hook-free launch screen is not clean: {path}")
        prior_screens.append(row)
    witness = deployment["entry_witness"]
    hooks = phase_c["facts"]["instrument"]["hooks"]
    require(any(row["name"] == "entry-RAM-witness-hook" for row in hooks),
            "RAM entry hook is not enumerated in Phase-C identity")
    runner_audit()
    witness_source_audit()
    return {
        "identity": {
            "product_bytes_changed": 0,
            "diagnostic_identity_reprepared_and_enumerated": True,
            "diagnostic_promotable": False,
            "product_links": 0,
            "WPLTO_runs": 0,
            "hardware_contacts_claimed_by_host_closure": 0,
        },
        "launch_boundary": {
            "attributed": "monitor-breakpoint loss; virtual RETURN arrived",
            "virtual_RETURN_submitted": True,
            "virtual_RETURN_arrival_authority": "execution beyond _start at $754a",
            "entry_proof_method": witness["method"],
            "entry_hook": f"0x{witness['hook']:04x}",
            "entry_routine": f"0x{witness['routine']:04x}",
            "entry_stamp_address": f"0x{witness['stamp_address']:04x}",
            "entry_stamp_value": f"0x{witness['stamp_value']:02x}",
            "RAM_mapping_activation_address":
            f"0x{witness['RAM_mapping_activation_address']:04x}",
            "RAM_mapping_active_before_entry_call":
            witness["RAM_mapping_active_before_entry_call"],
            "entry_before_measured_forms": True,
            "live_monitor_breakpoint_across_launch": False,
            "screen_inference_is_entry_proof": False,
            "full_65_byte_record_reset_before_defstruct": True,
            "bootstrap_through_protected_refill": False,
        },
        "dry_run": {
            "submitted_RETURN_witness": True,
            "fired_entry_stamp": entry_selftest["synthetic_fired_stamp"],
            "entry_mutations_rejected": len(
                entry_selftest["mutations_rejected"]),
            "launch_screen_mutations_rejected": len(
                screen_selftest["mutations_rejected"]),
        },
        "launch_screen": {
            "platform_case_is_load_bearing": False,
            "healthy_case_forms_executed": screen_selftest["healthy_case_forms"],
            "old_case_sensitive_observed_acceptance":
            screen_selftest["old_case_sensitive_observed_acceptance"],
            "bound_observed_RUN_seen_casefolded":
            observed_view["run_seen_casefolded"],
            "bound_observed_terminal_markers": observed_view["terminal_markers"],
            "bound_observed_is_healthy": False,
            "bound_observed_rejection": observed_rejection,
            "half_mapped_observed_is_healthy": False,
            "half_mapped_observed_rejection": half_screen_rejection,
        },
        "BREAK_attribution": {
            "classification": "diagnostic-bootstrap-mapping-order-defect",
            "old_hook": "JSR $C03F at $2024",
            "old_displaced_mapping_activation": "LDX #$2F; STX $00",
            "mechanism": (
                "both failed hooks fetched $C03F before the complete $00/$01 "
                "RAM-mapping pair: first before both stores, then after only $00"
            ),
            "previous_hook_free_launch_captures_checked": len(prior_screens),
            "previous_hook_free_launch_captures_with_BREAK": 0,
            "product_claim": False,
            "half_mapped_hook": "JSR $C03F at $2028",
            "half_mapped_prefix": "only LDX #$2F; STX $00 completed",
            "half_mapped_stopped_X": "0x2f",
            "corrected_hook": "JSR $C03F at $202C",
            "corrected_mapping_activation":
            "complete $00/$01 pair intact at $2024 before the call",
            "unexplained_BREAK_allowed": False,
        },
        "appointment": {
            "preauthorized": False,
            "authorized_contacts_remaining": 0,
            "virtual_runner_closed": True,
            "physical_owner_fallback_active": False,
            "physical_contact_budget_remaining": 0,
            "physical_setup_contacts_recorded": 1,
            "next_step": "owner method review after physical no-REPL First Red",
            "setup_first_red_fallback": "consumed without reaching D2",
            "rider_order": ["corrected-D2-defstruct-R/A/I/G",
                            "standing-trailing-peeks"],
            "device_requires_owner_keyboard": False,
        },
    }


def audit(value: dict[str, Any]) -> None:
    require(value["identity"] == {
        "product_bytes_changed": 0,
        "diagnostic_identity_reprepared_and_enumerated": True,
        "diagnostic_promotable": False,
        "product_links": 0,
        "WPLTO_runs": 0,
        "hardware_contacts_claimed_by_host_closure": 0,
    }, "Class-A identity/run boundary drift")
    launch = value["launch_boundary"]
    require(launch["virtual_RETURN_submitted"]
            and launch["virtual_RETURN_arrival_authority"] ==
            "execution beyond _start at $754a"
            and launch["entry_proof_method"] == "RAM-store-at-_start"
            and launch["entry_hook"] == "0x202c"
            and launch["entry_routine"] == "0xc03f"
            and launch["entry_stamp_address"] == "0xc07a"
            and launch["entry_stamp_value"] == "0x44"
            and launch["RAM_mapping_activation_address"] == "0x2024"
            and launch["RAM_mapping_active_before_entry_call"]
            and launch["entry_before_measured_forms"]
            and not launch["live_monitor_breakpoint_across_launch"]
            and not launch["screen_inference_is_entry_proof"]
            and launch["full_65_byte_record_reset_before_defstruct"]
            and not launch["bootstrap_through_protected_refill"],
            "RAM-entry choreography closure drift")
    dry = value["dry_run"]
    require(dry["submitted_RETURN_witness"]
            and dry["fired_entry_stamp"]["entry_stamp_fired"]
            and dry["fired_entry_stamp"]["method"] == "RAM-store-at-_start"
            and not dry["fired_entry_stamp"]["live_monitor_breakpoint_required"]
            and dry["entry_mutations_rejected"] == 8
            and dry["launch_screen_mutations_rejected"] == 3,
            "dry-run RETURN/RAM-entry witnesses drift")
    screen = value["launch_screen"]
    require(not screen["platform_case_is_load_bearing"]
            and screen["healthy_case_forms_executed"] == 2
            and not screen["old_case_sensitive_observed_acceptance"]
            and screen["bound_observed_RUN_seen_casefolded"]
            and screen["bound_observed_terminal_markers"] == [
                "BREAK", "MONITOR-COMMANDS", "MONITOR-REGISTER-HEADER"]
            and not screen["bound_observed_is_healthy"]
            and "unhealthy BREAK/monitor state" in
            screen["bound_observed_rejection"]
            and not screen["half_mapped_observed_is_healthy"]
            and "unhealthy BREAK/monitor state" in
            screen["half_mapped_observed_rejection"],
            "case-normalized fail-closed launch-screen classification drift")
    attribution = value["BREAK_attribution"]
    require(attribution["classification"] ==
            "diagnostic-bootstrap-mapping-order-defect"
            and attribution["old_hook"] == "JSR $C03F at $2024"
            and attribution["old_displaced_mapping_activation"] ==
            "LDX #$2F; STX $00"
            and attribution["previous_hook_free_launch_captures_checked"] == 2
            and attribution["previous_hook_free_launch_captures_with_BREAK"] == 0
            and not attribution["product_claim"]
            and attribution["half_mapped_hook"] == "JSR $C03F at $2028"
            and attribution["half_mapped_prefix"] ==
            "only LDX #$2F; STX $00 completed"
            and attribution["half_mapped_stopped_X"] == "0x2f"
            and attribution["corrected_hook"] == "JSR $C03F at $202C"
            and attribution["corrected_mapping_activation"] ==
            "complete $00/$01 pair intact at $2024 before the call"
            and not attribution["unexplained_BREAK_allowed"],
            "BREAK desk attribution/corrected bootstrap drift")
    require(not value["appointment"]["preauthorized"]
            and value["appointment"]["authorized_contacts_remaining"] == 0
            and value["appointment"]["virtual_runner_closed"]
            and not value["appointment"]["physical_owner_fallback_active"]
            and value["appointment"]["physical_contact_budget_remaining"] == 0
            and value["appointment"]["physical_setup_contacts_recorded"] == 1
            and value["appointment"]["next_step"] ==
            "owner method review after physical no-REPL First Red"
            and value["appointment"]["setup_first_red_fallback"] ==
            "consumed without reaching D2"
            and value["appointment"]["rider_order"] == [
        "corrected-D2-defstruct-R/A/I/G", "standing-trailing-peeks"]
            and not value["appointment"]["device_requires_owner_keyboard"],
        "appointment dependency order drift")


def mutations(base: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[list[str], Any]] = {
        "drop-return": (["launch_boundary", "virtual_RETURN_submitted"], False),
        "drop-entry-stamp": (["dry_run", "fired_entry_stamp",
                              "entry_stamp_fired"], False),
        "live-monitor-breakpoint-entry-proof": (
            ["launch_boundary", "entry_proof_method"],
            "live-monitor-breakpoint-across-launch"),
        "claim-live-breakpoint": (
            ["launch_boundary", "live_monitor_breakpoint_across_launch"], True),
        "screen-inference": (
            ["launch_boundary", "screen_inference_is_entry_proof"], True),
        "partial-record-reset": (
            ["launch_boundary", "full_65_byte_record_reset_before_defstruct"],
            False),
        "bootstrap-through-refill": (
            ["launch_boundary", "bootstrap_through_protected_refill"], True),
        "product-delta": (["identity", "product_bytes_changed"], 1),
        "make-promotable": (["identity", "diagnostic_promotable"], True),
        "claim-device": (["identity", "hardware_contacts_claimed_by_host_closure"], 1),
        "reorder-riders": (["appointment", "rider_order"],
                            ["standing-trailing-peeks",
                             "corrected-D2-defstruct-R/A/I/G"]),
        "case-sensitive-launch": (
            ["launch_screen", "platform_case_is_load_bearing"], True),
        "accept-observed-BREAK": (
            ["launch_screen", "bound_observed_is_healthy"], True),
        "erase-BREAK-attribution": (
            ["BREAK_attribution", "classification"], "unexplained"),
        "entry-before-RAM-mapping": (
            ["launch_boundary", "RAM_mapping_active_before_entry_call"], False),
        "reopen-virtual-contact": (
            ["appointment", "authorized_contacts_remaining"], 1),
        "claim-virtual-preauthorization": (
            ["appointment", "preauthorized"], True),
        "reopen-physical-contact": (
            ["appointment", "physical_contact_budget_remaining"], 1),
    }
    rejected: dict[str, str] = {}
    for name, (path, replacement) in cases.items():
        trial = deepcopy(base)
        target: Any = trial
        for component in path[:-1]:
            target = target[component]
        target[path[-1]] = replacement
        try:
            audit(trial)
        except ClosureError as error:
            rejected[name] = str(error)
        else:
            raise ClosureError(f"choreography mutation survived: {name}")
    return rejected


def expected_receipt() -> dict[str, Any]:
    value = facts()
    audit(value)
    rejected = mutations(value)
    return {
        "format": FORMAT,
        "recorded_on": date.today().isoformat(),
        "status": "all-launch-contact-budgets-consumed-D2-not-entered",
        "authorities": {
            "plan": bind(PLAN),
            "transport_attribution": bind(TRANSPORT),
            "phase_C": bind(PHASE_C),
            "deployment": bind(DEPLOY),
            "runner": bind(RUNNER),
            "RAM_entry_witness": bind(WITNESS),
            "launch_screen_classifier": bind(SCREEN_CLASSIFIER),
            "launch_first_red": bind(FIRST_RED),
            "half_mapped_launch_first_red": bind(HALF_MAPPED_RED),
            "sixth_launch_first_red": bind(SIXTH_RED),
            "physical_fallback": bind(PHYSICAL_FALLBACK),
            "physical_launch_first_red": bind(PHYSICAL_LAUNCH_RED),
            "physical_runner": bind(PHYSICAL_RUNNER),
            "prior_hook_free_launch_screens": [bind(path) for path in
                                                PRIOR_LAUNCH_SCREENS],
            "driver": bind(DRIVER),
        },
        "facts": value,
        "mutations_rejected": rejected,
        "execution_witnesses": 2 + len(rejected),
        "claim_limit": (
            "Historical virtual closure and the consumed hook-free physical "
            "fallback only; no product byte, submitted Lisp form, defstruct "
            "R/A/I/G row, fix or Link is claimed."
        ),
    }


def synthetic_value() -> dict[str, Any]:
    return {
        "identity": {
            "product_bytes_changed": 0,
            "diagnostic_identity_reprepared_and_enumerated": True,
            "diagnostic_promotable": False,
            "product_links": 0,
            "WPLTO_runs": 0,
            "hardware_contacts_claimed_by_host_closure": 0,
        },
        "launch_boundary": {
            "attributed": "monitor-breakpoint loss; virtual RETURN arrived",
            "virtual_RETURN_submitted": True,
            "virtual_RETURN_arrival_authority": "execution beyond _start at $754a",
            "entry_proof_method": "RAM-store-at-_start",
            "entry_hook": "0x202c",
            "entry_routine": "0xc03f",
            "entry_stamp_address": "0xc07a",
            "entry_stamp_value": "0x44",
            "RAM_mapping_activation_address": "0x2024",
            "RAM_mapping_active_before_entry_call": True,
            "entry_before_measured_forms": True,
            "live_monitor_breakpoint_across_launch": False,
            "screen_inference_is_entry_proof": False,
            "full_65_byte_record_reset_before_defstruct": True,
            "bootstrap_through_protected_refill": False,
        },
        "dry_run": {
            "submitted_RETURN_witness": True,
            "fired_entry_stamp": {
                "entry_stamp_fired": True,
                "method": "RAM-store-at-_start",
                "live_monitor_breakpoint_required": False,
            },
            "entry_mutations_rejected": 8,
            "launch_screen_mutations_rejected": 3,
        },
        "launch_screen": {
            "platform_case_is_load_bearing": False,
            "healthy_case_forms_executed": 2,
            "old_case_sensitive_observed_acceptance": False,
            "bound_observed_RUN_seen_casefolded": True,
            "bound_observed_terminal_markers": [
                "BREAK", "MONITOR-COMMANDS", "MONITOR-REGISTER-HEADER"],
            "bound_observed_is_healthy": False,
            "bound_observed_rejection":
            "unhealthy BREAK/monitor state at BASIC launch: BREAK,MONITOR-COMMANDS,MONITOR-REGISTER-HEADER",
            "half_mapped_observed_is_healthy": False,
            "half_mapped_observed_rejection":
            "unhealthy BREAK/monitor state at BASIC launch: BREAK,MONITOR-COMMANDS,MONITOR-REGISTER-HEADER",
        },
        "BREAK_attribution": {
            "classification": "diagnostic-bootstrap-mapping-order-defect",
            "old_hook": "JSR $C03F at $2024",
            "old_displaced_mapping_activation": "LDX #$2F; STX $00",
            "mechanism": (
                "both failed hooks fetched $C03F before the complete $00/$01 "
                "RAM-mapping pair: first before both stores, then after only $00"
            ),
            "previous_hook_free_launch_captures_with_BREAK": 0,
            "previous_hook_free_launch_captures_checked": 2,
            "product_claim": False,
            "half_mapped_hook": "JSR $C03F at $2028",
            "half_mapped_prefix": "only LDX #$2F; STX $00 completed",
            "half_mapped_stopped_X": "0x2f",
            "corrected_hook": "JSR $C03F at $202C",
            "corrected_mapping_activation":
            "complete $00/$01 pair intact at $2024 before the call",
            "unexplained_BREAK_allowed": False,
        },
        "appointment": {
            "preauthorized": False,
            "authorized_contacts_remaining": 0,
            "virtual_runner_closed": True,
            "physical_owner_fallback_active": False,
            "physical_contact_budget_remaining": 0,
            "physical_setup_contacts_recorded": 1,
            "next_step": "owner method review after physical no-REPL First Red",
            "setup_first_red_fallback": "consumed without reaching D2",
            "rider_order": ["corrected-D2-defstruct-R/A/I/G",
                            "standing-trailing-peeks"],
            "device_requires_owner_keyboard": False,
        },
    }


def selftest() -> int:
    value = synthetic_value()
    audit(value)
    rejected = mutations(value)
    require(len(rejected) == 18, "closure mutation count drift")
    print("D2 CHOREOGRAPHY SELFTEST PASS mutations=18 witnesses=20 "
          "virtual=closed physical=consumed D2=not-entered")
    return 0


def main() -> int:
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    if action == "selftest":
        return selftest()
    if action == "write":
        write_json(RECEIPT, expected_receipt())
        print("D2 CHOREOGRAPHY PASS virtual=closed physical=consumed "
              "mutations=18 D2-contacts=0")
        return 0
    if action == "check":
        expected = expected_receipt()
        require(load(RECEIPT) == expected, "D2 choreography receipt drift")
        print("D2 CHOREOGRAPHY PASS virtual=closed physical=consumed "
              "mutations=18 D2-contacts=0")
        return 0
    print(f"usage: {Path(sys.argv[0]).name} <selftest|write|check>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ClosureError, ENTRY.RAMEntryWitnessError,
            SCREEN.LaunchScreenError) as error:
        print(f"D2 CHOREOGRAPHY FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
