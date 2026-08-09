#!/usr/bin/env python3
"""Prepare and capture the no-prelaunch-monitor v1.6 discriminator."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v16_corrected_view_contact as BASE  # noqa: E402

OWNER_COMMIT = "aab22b3c"
PLAN = "docs/planning/1.6-defstruct-diagnosis-work-plan.md"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
HANDOVER = EVIDENCE / "c2.3-v1.6-defstruct-d2-physical-run-handover-desk-receipt.json"
QUIET_RESULT = EVIDENCE / "c2.3-v1.6-defstruct-d2-corrected-view-quiet-result-receipt.json"
QUIET_PREP = EVIDENCE / "c2.3-v1.6-defstruct-d2-corrected-view-quiet-preparation-receipt.json"
PRODUCT = ROOT / ("build/c2.3/v1.6-defstruct-closing-session/"
                  "d2-corrected-view-quiet-appointment/"
                  "diagnostic-link82-corrected-view-b5c3.prg")
OUT = ROOT / ("build/c2.3/v1.6-defstruct-closing-session/"
              "d2-control-shaped-discriminator")
SENTINEL = OUT / "durable-witness-reset.bin"
PREPARATION = EVIDENCE / "c2.3-v1.6-defstruct-d2-control-shaped-preparation-receipt.json"
DEVICE_RECEIPT = EVIDENCE / "c2.3-v1.6-defstruct-d2-control-shaped-device-receipt.json"
RUNNER = ROOT / "scripts/c2-v16-defstruct-control-shaped-hw.sh"
DRIVER = Path(__file__).resolve()

QUIET_SECONDS = 27.653
SPACING_SECONDS = 5.0
SAMPLES = 3


class DiscriminatorError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise DiscriminatorError(message)


def audit_runner(source: str) -> dict[str, Any]:
    require('screen launch-ready' in source and ': > "$OUT/stage.ready"' in source,
            "stage READY boundary absent")
    post_ready = source.split('screen launch-ready', 1)[1].split(
        ': > "$OUT/stage.ready"', 1)[0]
    forbidden = ("prelaunch", "monitor_sync", "command(fd", "t1", "t0")
    require(not any(token in post_ready for token in forbidden),
            "monitor crossing exists after READY gate and before owner RUN")
    require('exec python3 "$PY" capture' in source,
            "post-owner capture entrypoint absent")
    return {"post_READY_pre_owner_monitor_calls": 0,
            "owner_launch_is_next_device_action": True}


def capture_schedule(source: str) -> dict[str, Any]:
    boundary = "\ndef capture(device: str) -> dict[str, Any]:\n"
    require(boundary in source and "\ndef prepare()" in source,
            "capture schedule boundary absent")
    body = source.split(boundary, 1)[1].split("\ndef prepare()", 1)[0]
    markers = [
        "quiet_started = time.monotonic()",
        "time.sleep(QUIET_SECONDS)",
        "fd = os.open(device,",
        "BASE.SERIAL.monitor_sync(fd,",
        'BASE.command(fd, b"t1", 0.05)',
    ]
    require(all(body.count(marker) == 1 for marker in markers),
            "capture marker multiplicity drift")
    positions = [body.index(marker) for marker in markers]
    require(positions == sorted(positions), "monitor entered before quiet floor")
    require("PRELAUNCH" not in body and "prelaunch(" not in body,
            "capture depends on a prelaunch monitor crossing")
    return {"ordered_steps": ["owner-RUN", "quiet-start",
                               "27.653-second-sleep", "serial-open",
                               "monitor-sync", "t1"],
            "first_device_access_after_sleep": True}


def exact_facts() -> dict[str, Any]:
    owner_commit, plan = BASE.git_blob(OWNER_COMMIT, PLAN)
    text = plan.decode("utf-8")
    require("Discriminator contact authorized — 2026-08-05" in text
            and "no monitor access of any kind before the owner's RUN" in text
            and "No measured form in this contact" in text,
            "owner discriminator authority drift")
    handover, quiet_result, quiet_prep = (
        BASE.load(path) for path in (HANDOVER, QUIET_RESULT, QUIET_PREP))
    require(handover["status"] ==
            "BOUNDARY NAMED; PRELAUNCH MONITOR CROSSING LEADS"
            and not handover["facts"]["decision"]["causal_mechanism_proved"],
            "handover authority drift")
    require(quiet_result["status"] ==
            "PHYSICAL RUN ENTERED MONITOR; DIAGNOSTIC ENTRY NOT REACHED",
            "quiet result authority drift")
    require(quiet_prep["facts"]["identity"]["diagnostic_PRG"] ==
            BASE.bind(PRODUCT), "diagnostic identity drift")
    runner = audit_runner(RUNNER.read_text(encoding="utf-8"))
    schedule = capture_schedule(DRIVER.read_text(encoding="utf-8"))
    return {
        "owner_authority": BASE.bind_blob(f"git:{owner_commit}:{PLAN}", plan),
        "identity": {"diagnostic_PRG": BASE.bind(PRODUCT),
                     "promotable": False, "product_bytes_changed": 0,
                     "entry_witness": {"address": "0xb5c3", "reset": "0xd7",
                                       "entered": "0x44"}},
        "choreography": {
            "cold_reset": True, "physical_RUN": True,
            "control_shaped_before_owner_RUN": True,
            "prelaunch_monitor_crossing": False,
            "runner_source_proof": runner,
            "capture_schedule": schedule,
            "first_observation_quiet_seconds": QUIET_SECONDS,
            "sample_offsets_seconds": [27.653, 32.653, 37.653],
            "samples": SAMPLES, "authorized": True,
            "measured_forms": 0, "R_A_I_G_claimed": False,
            "leave_CPU_stopped": True,
        },
        "decision_table": {
            "owner_prompt_plus_witness_44":
                "PRELAUNCH-MONITOR-CROSSING-CAUSAL",
            "no_prompt_clean_witness_D7":
                "TARGET-SIDE-LAUNCH-DIFFERENCE-DESK-RETURN",
            "ambiguous_view_or_owner": "VIEW-OR-OWNER-FIRST-RED",
        },
    }


def audit(facts: dict[str, Any]) -> None:
    identity, choreography = facts["identity"], facts["choreography"]
    table = facts["decision_table"]
    require(not identity["promotable"] and identity["product_bytes_changed"] == 0
            and identity["entry_witness"] ==
            {"address": "0xb5c3", "reset": "0xd7", "entered": "0x44"},
            "diagnostic identity boundary drift")
    require(choreography["cold_reset"] and choreography["physical_RUN"]
            and choreography["control_shaped_before_owner_RUN"]
            and not choreography["prelaunch_monitor_crossing"]
            and choreography["runner_source_proof"] ==
            {"post_READY_pre_owner_monitor_calls": 0,
             "owner_launch_is_next_device_action": True}
            and choreography["capture_schedule"]["first_device_access_after_sleep"]
            and choreography["first_observation_quiet_seconds"] == 27.653
            and choreography["sample_offsets_seconds"] ==
                [27.653, 32.653, 37.653]
            and choreography["samples"] == 3 and choreography["authorized"]
            and choreography["measured_forms"] == 0
            and not choreography["R_A_I_G_claimed"]
            and choreography["leave_CPU_stopped"],
            "control-shaped choreography drift")
    require(len(table) == 3 and table["ambiguous_view_or_owner"] ==
            "VIEW-OR-OWNER-FIRST-RED", "decision table drift")


def selftest() -> dict[str, Any]:
    facts = exact_facts()
    audit(facts)
    cases: dict[str, tuple[list[str], Any]] = {
        "promotable": (["identity", "promotable"], True),
        "product-byte": (["identity", "product_bytes_changed"], 1),
        "virtual-RUN": (["choreography", "physical_RUN"], False),
        "erase-control-shape":
            (["choreography", "control_shaped_before_owner_RUN"], False),
        "prelaunch-monitor":
            (["choreography", "prelaunch_monitor_crossing"], True),
        "short-quiet":
            (["choreography", "first_observation_quiet_seconds"], 0.0),
        "drop-sample": (["choreography", "samples"], 2),
        "revoke": (["choreography", "authorized"], False),
        "measured-form": (["choreography", "measured_forms"], 1),
        "claim-R-A-I-G": (["choreography", "R_A_I_G_claimed"], True),
        "resume-final": (["choreography", "leave_CPU_stopped"], False),
        "drop-table-row":
            (["decision_table", "ambiguous_view_or_owner"], "continue"),
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
        except DiscriminatorError as error:
            rejected[name] = str(error)
        else:
            raise DiscriminatorError(f"verification mutation survived: {name}")
    runner = RUNNER.read_text(encoding="utf-8")
    injected = runner.replace('screen launch-ready\n',
                              'screen launch-ready\npython3 "$PY" prelaunch\n', 1)
    try:
        audit_runner(injected)
    except DiscriminatorError as error:
        rejected["inject-prelaunch-after-READY"] = str(error)
    else:
        raise DiscriminatorError("prelaunch source mutation survived")
    source = DRIVER.read_text(encoding="utf-8")
    early = source.replace("    time.sleep(QUIET_SECONDS)\n", "", 1).replace(
        '            BASE.command(fd, b"t1", 0.05)\n',
        '            BASE.command(fd, b"t1", 0.05)\n'
        "    time.sleep(QUIET_SECONDS)\n", 1)
    try:
        capture_schedule(early)
    except DiscriminatorError as error:
        rejected["early-t1-source-order"] = str(error)
    else:
        raise DiscriminatorError("early-t1 source mutation survived")
    return {"status": "SELFTEST PASS", "mutations": len(rejected),
            "rejected": rejected}


def expected_preparation() -> dict[str, Any]:
    facts = exact_facts()
    audit(facts)
    return {
        "format": "lisp65-c2.3-v1.6-D2-control-shaped-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "HOST-GREEN; ONE CONTROL-SHAPED CONTACT AUTHORIZED",
        "authorities": {
            "owner": facts.pop("owner_authority"), "handover": BASE.bind(HANDOVER),
            "quiet_result": BASE.bind(QUIET_RESULT),
            "quiet_preparation": BASE.bind(QUIET_PREP),
            "runner": BASE.bind(RUNNER), "driver": BASE.bind(DRIVER),
        },
        "facts": facts, "mutations_rejected": selftest()["rejected"],
        "claim_limit": (
            "One owner-authorized control-shaped diagnostic launch with no "
            "prelaunch monitor crossing, a 27.653-second quiet floor and three "
            "CPU-view samples. No measured form, R/A/I/G row, product fix, "
            "Link or release is authorized."),
    }


def product_owned(row: dict[str, Any]) -> bool:
    return row["code_owner"]["selected_owner"] in {
        "diagnostic-PRG", "diagnostic-E000-window"}


def classify(samples: list[dict[str, Any]]) -> str:
    if not BASE.owners_proved(samples):
        return "VIEW-OR-OWNER-FIRST-RED"
    stamps = [int(row["durable_witness"], 16) for row in samples]
    if stamps == [BASE.STAMP] * SAMPLES and all(product_owned(row) for row in samples):
        return "PRODUCT-ENTRY-WITNESS-SET"
    if stamps == [BASE.RESET] * SAMPLES and all(not product_owned(row) for row in samples):
        return "DIAGNOSTIC-ENTRY-NOT-REACHED"
    return "ENTRY-OR-OWNER-FIRST-RED"


def capture(device: str) -> dict[str, Any]:
    expected = expected_preparation()
    require(PREPARATION.is_file() and BASE.load(PREPARATION) == expected,
            "control-shaped preparation drift")
    require((OUT / "stage.ready").is_file(), "control-shaped stage absent")
    require(not DEVICE_RECEIPT.exists(), "control-shaped contact is one-shot")
    quiet_started = time.monotonic()
    time.sleep(QUIET_SECONDS)
    elapsed = time.monotonic() - quiet_started
    require(elapsed >= QUIET_SECONDS, "monitor entered before quiet floor")
    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    samples: list[dict[str, Any]] = []
    try:
        BASE.SERIAL.configure_serial(fd)
        for index in range(SAMPLES):
            BASE.SERIAL.monitor_sync(fd, f"#c2v16control{index}\r".encode())
            BASE.command(fd, b"t1", 0.05)
            samples.append(BASE.sample(fd, index + 1))
            if index + 1 < SAMPLES:
                BASE.command(fd, b"t0", 0.03)
                time.sleep(SPACING_SECONDS)
    finally:
        os.close(fd)
    status = classify(samples)
    value = {
        "format": "lisp65-c2.3-v1.6-D2-control-shaped-device-v1",
        "recorded_on": date.today().isoformat(), "status": status,
        "device": device,
        "authorities": {"preparation": BASE.bind(PREPARATION),
                        "driver": BASE.bind(DRIVER)},
        "samples": samples,
        "result": {"classification": status, "CPU_left_stopped": True,
                   "first_observation_quiet_seconds": elapsed,
                   "measured_forms_run": 0, "R_A_I_G_claimed": False,
                   "prelaunch_monitor_crossing": False,
                   "all_state_reads_CPU_view": True,
                   "code_owner_bound_before_interpretation": True},
        "claim_limit": expected["claim_limit"],
    }
    BASE.write_json(DEVICE_RECEIPT, value)
    return value


def prepare() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    SENTINEL.write_bytes(bytes([BASE.RESET]))
    value = expected_preparation()
    BASE.write_json(PREPARATION, value)
    return value


def check() -> dict[str, Any]:
    value = expected_preparation()
    require(PREPARATION.is_file() and BASE.load(PREPARATION) == value,
            "control-shaped preparation receipt drift")
    return {"status": "PASS", "mutations": 14, "authorized": True,
            "prelaunch_monitor_crossing": False,
            "device_result_present": DEVICE_RECEIPT.exists()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "check", "selftest", "capture"))
    parser.add_argument("--device", default=BASE.SERIAL.DEVICE)
    args = parser.parse_args()
    if args.action == "prepare":
        value = prepare()
    elif args.action == "check":
        value = check()
    elif args.action == "selftest":
        value = selftest()
    else:
        value = capture(args.device)
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DiscriminatorError, BASE.CorrectedViewError, OSError, ValueError,
            KeyError, json.JSONDecodeError) as error:
        print("c2-v1.6-control-shaped-discriminator: FIRST RED: " + str(error))
        raise SystemExit(2)
