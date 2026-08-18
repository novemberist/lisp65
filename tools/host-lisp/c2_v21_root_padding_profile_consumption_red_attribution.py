#!/usr/bin/env python3
"""Attribute the consumed profile feature's missing derived binding."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v21_root_padding_profile_consumption_replacement as R  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RED = R.FINAL_RED
RECEIPT = ARCH / (
    "c2.3-v2.1-root-padding-profile-consumption-red-attribution.json")
FORMAT = "lisp65-c2.3-v2.1-profile-consumption-red-attribution-v1"
STATUS = "ATTRIBUTED FINAL RED: DERIVED FEATURE BINDING NOT PROJECTED"
FAILED_SOURCE = (
    "build/c2.3/v2.1-probe-oracle-root-padding-replacement-card/wplto/"
    "generated-product-sources/c2_product_runtime.c")
REQUIRED_BINDING = "LISP65_C2_BANK3_STAGE_SESSION_SLOT"


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


def parse_command(red: dict[str, Any]) -> list[str]:
    message = red["error"]["message"]
    prefix = "Command '"
    suffix = "' returned non-zero exit status 1."
    require(message.startswith(prefix) and message.endswith(suffix),
            "profile-consumption compiler command absent")
    value = ast.literal_eval(message[len(prefix):-len(suffix)])
    require(isinstance(value, list) and all(isinstance(item, str) for item in value),
            "profile-consumption command is not a string list")
    return value


def compile_control(command: list[str], *, add_slot: bool) -> dict[str, Any]:
    probe = list(command)
    output = probe.index("-o")
    probe[output + 1] = "/dev/null"
    if add_slot:
        probe[1:1] = [f"-D{REQUIRED_BINDING}=8"]
    before = object_bindings()
    completed = subprocess.run(
        probe, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        text=True, check=False)
    require(object_bindings() == before,
            "read-only semantic compile control changed partial objects")
    diagnostic = [line.strip() for line in completed.stderr.splitlines()
                  if "error:" in line]
    return {"slot_binding_added": add_slot, "exit_status": completed.returncode,
            "errors": diagnostic,
            "stderr_sha256": hashlib.sha256(
                completed.stderr.encode()).hexdigest(),
            "output": "/dev/null", "filesystem_writes": 0}


def object_bindings() -> list[dict[str, Any]]:
    if not R.OBJECT_ROOT.exists():
        return []
    return [bind(path) for path in sorted(R.OBJECT_ROOT.glob("*.o"))]


def final_paths() -> list[str]:
    return [path.relative_to(ROOT).as_posix()
            for path in R.BASE.family(R.FINAL) if path.exists()]


def validate(value: dict[str, Any]) -> None:
    mechanism = value["mechanism"]
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and mechanism["class"] ==
            "PROFILE-FEATURE-CONSUMED-DERIVED-BINDING-UNPROJECTED"
        and mechanism["profile_features_consumed"] == 24
        and mechanism["candidate_features_consumed"] == 6
        and mechanism["preprocessor_translation_units_green"] == 66
        and mechanism["semantic_compile_started"] is True
        and mechanism["failed_object_ordinal"] == 5
        and mechanism["completed_object_count"] == 5
        and mechanism["required_derived_binding"] == REQUIRED_BINDING
        and mechanism["required_derived_value"] == 8
        and mechanism["failed_command_has_feature"] is True
        and mechanism["failed_command_has_derived_binding"] is False
        and mechanism["negative_control"]["exit_status"] == 1
        and mechanism["positive_control"]["exit_status"] == 0
        and mechanism["final_link_started"] is False
        and mechanism["final_artifacts_present"] == []
        and value["classification"]["product_red"] is False
        and value["classification"]["seed_red"] is False
        and value["classification"]["producer_configuration_red"] is True
        and value["execution_accounting"]["replacement_runs"] == 1
        and value["execution_accounting"]["final_product_links"] == 0
        and value["disposition"]["retry_authorized"] is False
        and value["disposition"]["owner_required"] is True,
        "profile-derived binding attribution drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-binding-consumed": lambda x: x["mechanism"].update(
            failed_command_has_derived_binding=True),
        "hide-feature": lambda x: x["mechanism"].update(
            failed_command_has_feature=False),
        "claim-preprocessor-incomplete": lambda x: x["mechanism"].update(
            preprocessor_translation_units_green=65),
        "hide-semantic-red": lambda x: x["mechanism"][
            "negative_control"].update(exit_status=0),
        "break-positive-control": lambda x: x["mechanism"][
            "positive_control"].update(exit_status=1),
        "claim-final-link": lambda x: x["mechanism"].update(
            final_link_started=True),
        "blame-product": lambda x: x["classification"].update(product_red=True),
        "authorize-retry": lambda x: x["disposition"].update(
            retry_authorized=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate(trial)
        except AttributionError:
            rejected.append(name)
    require(rejected == list(cases), "derived-binding mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    red = load(RED)
    preflight = load(R.PREFLIGHT)
    command = parse_command(red)
    definitions = {item[2:].split("=", 1)[0]
                   for item in command if item.startswith("-D")}
    objects = object_bindings()
    source = (ROOT / FAILED_SOURCE).read_text(encoding="utf-8")
    producer = (ROOT / "tools/host-lisp/c2_product_substitution_link.py"
                ).read_text(encoding="utf-8")
    require(
        red.get("status") ==
            "FINAL RED: PROFILE-CONSUMPTION REPLACEMENT RETURNS TO OWNER"
        and red["retry_authorized"] is False
        and red["owner_disposition_required"] is True
        and preflight["real_preprocessor_smoke"]["translation_unit_count"] == 66
        and preflight["compiler_feature_gate"]["report"][
            "consumed_feature_count"] == 24
        and len(objects) == 5
        and final_paths() == []
        and "LISP65_C2_LITE_BANK3_STAGING" in definitions
        and REQUIRED_BINDING not in definitions
        and REQUIRED_BINDING in source
        and "if BANK3_STAGING_SLICES:" in producer
        and f'f"{REQUIRED_BINDING}={{BOOT_BANK3_STAGE_SLOT}}"' in producer,
        "profile-consumption Red signature drift")
    negative = compile_control(command, add_slot=False)
    positive = compile_control(command, add_slot=True)
    require(negative["exit_status"] == 1
            and any(REQUIRED_BINDING in row for row in negative["errors"])
            and positive["exit_status"] == 0,
            "derived-binding semantic controls drift")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-17", "status": STATUS,
        "authority": {"Final_Red": bind(RED), "preflight": bind(R.PREFLIGHT),
            "resolved_profile": bind(R.BASE.PROFILE),
            "driver": bind(Path(__file__))},
        "mechanism": {
            "class": "PROFILE-FEATURE-CONSUMED-DERIVED-BINDING-UNPROJECTED",
            "why": (
                "The real compiler consumes the Bank-3 staging feature name, "
                "but the continuation did not reconstruct the configurator state "
                "that emits its numeric session-slot companion. Preprocessing "
                "cannot diagnose an undeclared C identifier; semantic compilation "
                "does."),
            "profile_features_consumed": 24,
            "candidate_features_consumed": 6,
            "preprocessor_translation_units_green": 66,
            "semantic_compile_started": True,
            "failed_source": bind(ROOT / FAILED_SOURCE),
            "failed_object_ordinal": 5,
            "completed_objects": objects,
            "completed_object_count": len(objects),
            "trigger_feature": "LISP65_C2_LITE_BANK3_STAGING",
            "required_derived_binding": REQUIRED_BINDING,
            "required_derived_value": 8,
            "producer_condition": "BANK3_STAGING_SLICES",
            "failed_command_has_feature": True,
            "failed_command_has_derived_binding": False,
            "negative_control": negative,
            "positive_control": positive,
            "final_link_started": False,
            "final_artifacts_present": final_paths(),
            "historical_partial_objects_preserved": True,
            "immutable_source_evidence_unchanged": True,
        },
        "classification": {"product_red": False, "seed_red": False,
            "materializer_red": False, "producer_configuration_red": True},
        "execution_accounting": red["execution_accounting"],
        "disposition": {"retry_authorized": False, "owner_required": True,
            "narrow_repair_not_authorized": (
                "Project every profile feature through its real configurator, "
                "derive the Bank-3 slot binding from that configured candidate, "
                "and extend the preflight from -E reference consumption to an "
                "actual semantic compile of every translation unit into a "
                "separately owned disposable object domain."),
            "permanent_rule_candidate": (
                "Consuming a feature name is incomplete when that feature owns "
                "derived numeric or layout bindings; the real semantic compiler "
                "must consume the complete configured projection.")},
        "claim_limit": (
            "Read-only attribution only. The replacement run is consumed; no "
            "retry, final link, Completion, medium or device action is authorized.")}
    validate(value)
    value["mutations_rejected"] = mutations(value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check"))
    action = parser.parse_args().action
    value = derive()
    if action == "record":
        require(not RECEIPT.exists(), "profile-consumption attribution exists")
        RECEIPT.write_bytes(canonical(value))
    else:
        require(RECEIPT.read_bytes() == canonical(value),
                "profile-consumption attribution stale")
    print("profile-consumption Red attribution: PASS feature=24/24 "
          "objects=5 final-link=0 mutations=8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError, SyntaxError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"profile-consumption Red attribution: FAIL {error}",
              file=sys.stderr)
        raise SystemExit(2)
