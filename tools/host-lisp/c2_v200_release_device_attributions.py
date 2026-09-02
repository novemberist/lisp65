#!/usr/bin/env python3
"""Close the v2.0 device D5/event deltas and bind cold-boot choreography."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
PLAN_HEADER = "## Independent review and pre-Ship attribution closure — 2026-09-02"
DEVICE = ARCH / "c2.3-v2.0-release-strip-device-result-receipt.json"
CURRENT_SESSION = ROOT / "config/c2-v200-release-strip-device-session.json"
V19_R7 = ARCH / "c2.3-v1.9-blocks-ab-display-r7-device-result-receipt.json"
V19_R7_SESSION = ROOT / "config/c2-v190-blocks-ab-display-r7-acceptance-session.json"
V19_R8 = ARCH / "c2.3-v1.9-r8-release-terminal-d5-receipt.json"
V19_R8_SESSION = ROOT / "config/c2-v190-block-a-delivered-consumer-r8-session.json"
BASELINE = ARCH / "c2.3-v2.0-symbol22-build-id-device-result-receipt.json"
PRODUCT = ARCH / "c2.3-v2.0-release-strip-product-card-r1-receipt.json"
CHOREOGRAPHY = ROOT / "config/release-device-cold-boot-choreography.json"
RECEIPT = ARCH / "c2.3-v2.0-release-device-attributions-receipt.json"
REPORT = ROOT / "docs/planning/v2.0.0-release-device-attributions.md"
STATUS = "PASS: V2.0 DEVICE DELTAS ATTRIBUTED AND COLD-BOOT RULE ARMED"


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def plan_section() -> dict[str, Any]:
    text = PLAN.read_text(encoding="utf-8")
    require(text.count(PLAN_HEADER) == 1, "attribution plan section drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").replace("*", "").split())
    for token in ("+2 symbols / +19 bytes", "physical ingress",
                  "freshly restores the bound d81", "workbench 2.0.0"):
        require(token in folded, f"attribution authority token absent: {token}")
    raw = section.encode()
    return {"path": PLAN.relative_to(ROOT).as_posix(), "section": PLAN_HEADER,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def d5_row(device: dict[str, Any]) -> dict[str, Any]:
    return next(row["D5"] for row in device["rows"]
                if row["id"] == "S20-4-release-terminal-D5-and-performance")


def input_row(device: dict[str, Any]) -> dict[str, Any]:
    return next(row for row in device["rows"]
                if row["id"] == "S20-2-v1.9-input-and-forced-collection")


def validate_choreography(value: dict[str, Any]) -> None:
    cold = value["qualifying_cold_boot"]
    policy = value["failure_policy"]
    require(cold["restore_bound_medium_before_each_boot"] is True
            and cold["read_back_entire_medium_before_each_boot"] is True
            and cold["required_readback_identity"].startswith("SHA-256")
            and cold["reuse_previously_staged_remote_copy"] is False
            and cold["stopped_state_read_invalidates_staging_for_next_boot"] is True
            and policy["readback_mismatch"] == "stop before boot"
            and policy["preserve_incident_as_evidence"] is True,
            "cold-boot choreography weakened")


def choreography_mutations(value: dict[str, Any]) -> list[str]:
    cases = {
        "allow-stale-staged-copy": lambda x: x["qualifying_cold_boot"].update(
            reuse_previously_staged_remote_copy=True),
        "omit-full-medium-readback": lambda x: x["qualifying_cold_boot"].update(
            read_back_entire_medium_before_each_boot=False),
        "accept-readback-SHA-mismatch": lambda x: x["failure_policy"].update(
            readback_mismatch="continue"),
        "reuse-after-stopped-state-read": lambda x: x[
            "qualifying_cold_boot"].update(
                stopped_state_read_invalidates_staging_for_next_boot=False),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = copy.deepcopy(value)
        mutate(trial)
        try:
            validate_choreography(trial)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "cold-boot choreography mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    device, r7, r8, baseline, product = map(load,
        (DEVICE, V19_R7, V19_R8, BASELINE, PRODUCT))
    session, r7_session, r8_session = map(load,
        (CURRENT_SESSION, V19_R7_SESSION, V19_R8_SESSION))
    choreography = load(CHOREOGRAPHY)
    validate_choreography(choreography)

    current_d5 = d5_row(device)
    r7_d5 = r7["D5"]
    r8_d5 = r8["D5"]
    baseline_used = {"nsym": int.from_bytes(bytes.fromhex(
        baseline["raw_first"]["nsym"]["hex"]), "little"),
        "npool": int.from_bytes(bytes.fromhex(
            baseline["raw_first"]["npool"]["hex"]), "little")}
    require(current_d5["observed"] == r7_d5["observed"] == {
                "nsym": 645, "npool": 8741}
            and current_d5["free"] == r7_d5["free"] == {
                "symbol_slots": 107, "namepool_bytes": 1467}
            and current_d5["projection"] == r8_d5["free"] == {
                "symbol_slots": 109, "namepool_bytes": 1486}
            and baseline_used == {"nsym": 642, "npool": 8720},
            "D5 comparison worlds drift")
    require("v20-perf-probe" in json.dumps(session)
            and "v19-perf-probe" in json.dumps(r7_session)
            and r8_session["controller"]["form"].startswith(
                "(progn (setq s (read-line))"),
            "D5 session-shape authority drift")
    require(product["final_product"]["D5_projection"]["projected_free"] ==
                r8_d5["free"],
            "stripped product D5 projection authority drift")

    current_growth = {"symbols": current_d5["observed"]["nsym"]
                      - baseline_used["nsym"],
                      "name_bytes": current_d5["observed"]["npool"]
                      - baseline_used["npool"]}
    r8_growth = {"symbols": r8_d5["observed"]["nsym"]
                 - baseline_used["nsym"],
                 "name_bytes": r8_d5["observed"]["npool"]
                 - baseline_used["npool"]}
    residual = {"symbols": current_growth["symbols"] - r8_growth["symbols"],
                "name_bytes": current_growth["name_bytes"]
                - r8_growth["name_bytes"]}
    require(current_growth == {"symbols": 3, "name_bytes": 21}
            and r8_growth == {"symbols": 1, "name_bytes": 2}
            and residual == {"symbols": 2, "name_bytes": 19},
            "D5 session-population attribution arithmetic drift")

    row = input_row(device)
    counters = row["captures"]["counter_values"]
    projected = row["fixture_projection"]["expected"]
    observed = row["fixture_projection"]["observed"]
    downstream = {name: value - counters["raw"]
                  for name, value in counters.items() if name != "raw"}
    require(projected == 136 and observed == 138
            and counters == {"raw": 138, "seen": 138,
                              "stored": 138, "taken": 138}
            and downstream == {"seen": 0, "stored": 0, "taken": 0},
            "event stimulus attribution drift")

    return {"format": "lisp65-c2-v200-release-device-attributions-v1",
        "recorded_on": "2026-09-02", "status": STATUS,
        "authority": {"reviewed_device_result": bind(DEVICE),
            "current_session": bind(CURRENT_SESSION),
            "v1_9_r7_performance_result": bind(V19_R7),
            "v1_9_r7_performance_session": bind(V19_R7_SESSION),
            "v1_9_r8_collection_D5": bind(V19_R8),
            "v1_9_r8_collection_session": bind(V19_R8_SESSION),
            "common_pre_session_baseline": bind(BASELINE),
            "stripped_product": bind(PRODUCT), "plan": plan_section()},
        "D5_delta": {
            "status": "ATTRIBUTED: SESSION NAME POPULATION; ZERO PRODUCT RESIDUAL",
            "projection_session": {"shape": "forced collection; session name s",
                "observed": r8_d5["observed"], "free": r8_d5["free"],
                "growth_from_common_baseline": r8_growth},
            "device_session": {"shape": "performance probe and final smokes",
                "observed": current_d5["observed"], "free": current_d5["free"],
                "growth_from_common_baseline": current_growth,
                "byteidentical_precedent": r7_d5["observed"]},
            "observed_minus_projection_used": residual,
            "observed_minus_projection_free": {
                "symbol_slots": -residual["symbols"],
                "namepool_bytes": -residual["name_bytes"]},
            "unexplained_product_symbols": 0,
            "unexplained_product_name_bytes": 0,
            "claim": "107 free slots / 1467 free name bytes is release-terminal"},
        "event_delta": {
            "status": "ATTRIBUTED: HAND-DRIVEN STIMULUS CARDINALITY",
            "fixture_projection": projected, "physical_raw_ingress": observed,
            "delta": observed - projected, "downstream_deltas_from_raw": downstream,
            "classification": ("two additional physical ingress events outside "
                "the modeled fixture count; every delivered stage conserves them"),
            "losslessness_predicate": "raw=seen=stored=taken and nonzero",
            "exact_136_claim": False, "unexplained_capture_events": 0},
        "cold_boot_choreography": {"contract": bind(CHOREOGRAPHY),
            "mutations_rejected": choreography_mutations(choreography),
            "incident_count": len(device["nonqualifying_staging_incidents"][
                "observations"]), "status": "PERMANENT GATE ARMED"},
        "decision": {"hardware_acceptance": "INDEPENDENT-REVIEW-GREEN",
            "release_card": "AUTHORIZED", "Ship": "CLOSED-PENDING-RELEASE-CARD",
            "Publish": "CLOSED"},
        "claim_limit": {"accepts": ["D5 floor 107/1467",
                "losslessness at 138/138/138/138", "both deltas attributed",
                "cold-boot choreography permanent"],
            "excludes": ["identity of the two unmodeled physical key events",
                "Ship", "Publish"]}}


def validate(value: dict[str, Any]) -> None:
    require(value == derive()
            and value["D5_delta"]["observed_minus_projection_used"] == {
                "symbols": 2, "name_bytes": 19}
            and value["D5_delta"]["unexplained_product_symbols"] == 0
            and value["event_delta"]["delta"] == 2
            and value["event_delta"]["downstream_deltas_from_raw"] == {
                "seen": 0, "stored": 0, "taken": 0}
            and value["decision"]["release_card"] == "AUTHORIZED"
            and value["decision"]["Ship"].startswith("CLOSED"),
            "device attribution closure drift")


def write_report(value: dict[str, Any]) -> None:
    REPORT.write_text(f"""# v2.0 device delta attribution and cold-boot rule

Status: **{value['status']}**

The D5 delta is a session-population delta.  The device's 645/8,741 counters
are byte-identical to the v1.9 r7 performance session.  The 109/1,486
projection came from the v1.9 r8 collection session with the single session
name `s`.  Relative to the common 642/8,720 pre-session baseline, the current
performance contact adds 3 symbols/21 bytes and the projection session adds
1/2.  The complete difference is therefore **+2 symbols/+19 used bytes**, or
**-2 free slots/-19 free bytes**, with zero product-population residual.  The
release-terminal observation is 107 free slots / 1,467 free name bytes.

The event delta is upstream of Capture: raw ingress is 138 rather than the
fixture projection 136, and seen/stored/taken are each exactly 138.  Two
hand-driven stimulus events were outside the arithmetic model; the ring
neither loses nor duplicates an event.  The accepted predicate remains
equality and nonzero, and no exact-136 claim is made.

The staging incidents permanently arm
`config/release-device-cold-boot-choreography.json`: every qualifying cold
boot freshly restores and rereads the complete bound D81, a SHA mismatch
stops before boot, and a previously staged copy is never reused.  Four sharp
mutations fall.  Both pre-Ship attributions are closed; the release card is
authorized, while Ship and Publish remain owner-gated.
""", encoding="utf-8")


def build() -> None:
    require(not RECEIPT.exists(), "device attributions are one-shot")
    value = derive()
    write_report(value)
    RECEIPT.write_bytes(canonical(value))
    validate(value)
    print("v2.0 device attributions: BUILD PASS D5=-2/-19 events=+2")


def check() -> None:
    validate(load(RECEIPT))
    require(REPORT.is_file(), "device attribution report absent")
    print("v2.0 device attributions: CHECK PASS residual=0")


def selftest() -> None:
    base = load(RECEIPT)
    cases = {
        "hide-product-residual": lambda x: x["D5_delta"].update(
            unexplained_product_symbols=1),
        "move-event-after-raw": lambda x: x["event_delta"][
            "downstream_deltas_from_raw"].update(taken=-2),
        "invent-exact-136": lambda x: x["event_delta"].update(exact_136_claim=True),
        "weaken-cold-boot-rule": lambda x: x["cold_boot_choreography"].update(
            mutations_rejected=[]),
        "infer-Ship": lambda x: x["decision"].update(Ship="YES"),
    }
    rejected = 0
    for name, mutate in cases.items():
        trial = copy.deepcopy(base)
        mutate(trial)
        try:
            validate(trial)
        except AttributionError:
            rejected += 1
        else:
            raise AttributionError(f"mutation survived: {name}")
    require(rejected == len(cases), "device attribution mutation count drift")
    print(f"v2.0 device attributions: SELFTEST PASS mutations={rejected}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check", "selftest"))
    action = parser.parse_args().action
    {"build": build, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v2.0 device attributions: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
