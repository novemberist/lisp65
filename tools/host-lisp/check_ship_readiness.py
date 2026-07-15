#!/usr/bin/env python3
"""Gate the machine-readable lisp65 ship readiness report."""

from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_REPORT = Path("build") / "ship" / "ship-readiness.txt"
VALID_STATUS = {"full-ship-ready", "interim-ready-with-known-blockers"}


def report_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def require(errors: list[str], values: dict[str, str], key: str) -> str:
    value = values.get(key, "missing")
    if value == "missing":
        errors.append(f"{key}=missing")
    return value


def is_uint(value: str) -> bool:
    return value.isdigit()


def validate(values: dict[str, str]) -> list[str]:
    errors: list[str] = []
    status = require(errors, values, "status")
    blockers = require(errors, values, "blockers")
    conformance = require(errors, values, "objective_stdlib_conformance_status")
    full_embed = require(errors, values, "objective_full_embed_status")
    f011_offline = require(errors, values, "objective_f011_offline_status")
    runtime = require(errors, values, "objective_full_stdlib_runtime_status")
    one_command = require(errors, values, "objective_one_command_ship_status")

    if status not in VALID_STATUS:
        errors.append(f"status must be one of {','.join(sorted(VALID_STATUS))}: {status}")
    if status == "full-ship-ready" and blockers != "none":
        errors.append("full-ship-ready must have blockers=none")
    if status == "interim-ready-with-known-blockers" and blockers == "none":
        errors.append("interim-ready-with-known-blockers must name blockers")

    if one_command not in {"ok", "interim-with-known-blockers", "missing"}:
        errors.append(f"invalid objective_one_command_ship_status: {one_command}")
    if one_command == "ok" and status != "full-ship-ready":
        errors.append("objective_one_command_ship_status=ok requires full-ship-ready")
    if one_command == "interim-with-known-blockers" and status != "interim-ready-with-known-blockers":
        errors.append("interim objective status requires interim readiness")

    if conformance != "covered":
        errors.append(f"stdlib conformance objective must stay covered: {conformance}")
    if values.get("conformance_abi_gate") != "ready":
        errors.append("conformance_abi_gate must be ready")
    if values.get("conformance_missing_categories") != "none":
        errors.append("conformance_missing_categories must be none")
    if values.get("conformance_blocked_cases") != "0":
        errors.append("conformance_blocked_cases must be 0")
    active_cases = values.get("conformance_active_cases", "missing")
    if not is_uint(active_cases) or int(active_cases) <= 0:
        errors.append("conformance_active_cases must be a positive integer")

    if f011_offline not in {"ok", "blocked", "missing"}:
        errors.append(f"invalid objective_f011_offline_status: {f011_offline}")
    if f011_offline != "ok":
        errors.append(f"F011 offline objective must stay ok: {f011_offline}")
    if values.get("f011_transport_status") != "ok":
        errors.append("f011_transport_status must be ok")
    loaded = values.get("f011_loaded", "missing")
    chunks = values.get("f011_chunks", "missing")
    if not (is_uint(loaded) and is_uint(chunks) and loaded == chunks and int(chunks) > 0):
        errors.append(f"F011 loaded/chunks mismatch: loaded={loaded} chunks={chunks}")

    if full_embed not in {"ok", "blocked", "missing"}:
        errors.append(f"invalid objective_full_embed_status: {full_embed}")
    if full_embed == "ok" and values.get("full_embed_status") != "default-fits":
        errors.append("objective_full_embed_status=ok requires full_embed_status=default-fits")
    if full_embed == "blocked" and "full-embed-bank0-footprint" not in blockers.split(","):
        errors.append("blocked full embed objective must name full-embed-bank0-footprint")

    if runtime not in {"ok", "known-blocker", "missing"}:
        errors.append(f"invalid objective_full_stdlib_runtime_status: {runtime}")
    if runtime == "ok" and values.get("f011_binding_status") != "full-sentinel-bindings":
        errors.append("objective_full_stdlib_runtime_status=ok requires full-sentinel-bindings")
    if runtime == "known-blocker" and "f011-stdlib-binding-gap" not in blockers.split(","):
        errors.append("known runtime blocker must name f011-stdlib-binding-gap")
    if values.get("f011_gap_report_status") == "missing":
        errors.append("f011_gap_report_status must be present")
    return errors


def interim_report() -> dict[str, str]:
    return {
        "status": "interim-ready-with-known-blockers",
        "blockers": "full-embed-bank0-footprint,f011-stdlib-binding-gap",
        "objective_one_command_ship_status": "interim-with-known-blockers",
        "objective_stdlib_conformance_status": "covered",
        "objective_full_embed_status": "blocked",
        "objective_f011_offline_status": "ok",
        "objective_full_stdlib_runtime_status": "known-blocker",
        "conformance_abi_gate": "ready",
        "conformance_active_cases": "32",
        "conformance_blocked_cases": "0",
        "conformance_missing_categories": "none",
        "full_embed_status": "bank0-footprint-blocked",
        "f011_transport_status": "ok",
        "f011_loaded": "25",
        "f011_chunks": "25",
        "f011_binding_status": "gap-observed",
        "f011_gap_report_status": "no-layer-probe",
    }


def full_ready_report() -> dict[str, str]:
    values = interim_report()
    values.update({
        "status": "full-ship-ready",
        "blockers": "none",
        "objective_one_command_ship_status": "ok",
        "objective_full_embed_status": "ok",
        "objective_full_stdlib_runtime_status": "ok",
        "full_embed_status": "default-fits",
        "f011_binding_status": "full-sentinel-bindings",
    })
    return values


def selftest() -> int:
    cases: list[tuple[str, dict[str, str], bool]] = [
        ("valid-interim", interim_report(), True),
        ("valid-full-ready", full_ready_report(), True),
        ("missing-objective", {k: v for k, v in interim_report().items() if k != "objective_stdlib_conformance_status"}, False),
        ("blocked-conformance", {**interim_report(), "conformance_blocked_cases": "1"}, False),
        ("f011-count-mismatch", {**interim_report(), "f011_loaded": "24"}, False),
        ("full-ready-with-blocker", {**full_ready_report(), "blockers": "f011-stdlib-binding-gap"}, False),
    ]
    failures: list[str] = []
    for name, values, should_pass in cases:
        errors = validate(values)
        passed = not errors
        if passed != should_pass:
            failures.append(f"{name}: expected {should_pass}, got {passed}: {'; '.join(errors)}")
    if failures:
        for failure in failures:
            print(f"ship-readiness-check selftest FAIL: {failure}")
        return 1
    print(f"ship-readiness-check selftest OK: {len(cases)} cases")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("report", nargs="?", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    if not args.report.exists():
        print(f"ship-readiness-check FAIL: missing report {args.report}")
        return 1

    errors = validate(report_values(args.report))

    if errors:
        for error in errors:
            print(f"ship-readiness-check FAIL: {error}")
        return 1

    print(f"ship-readiness-check OK: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
