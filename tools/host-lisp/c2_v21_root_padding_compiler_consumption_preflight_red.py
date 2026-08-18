#!/usr/bin/env python3
"""Bind the real-consumer dry-run's missing profile-feature configuration."""

from __future__ import annotations

import argparse
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

import c2_v21_root_padding_compiler_consumption_replacement as C  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = ARCH / (
    "c2.3-v2.1-root-padding-compiler-consumption-preflight-final-red.json")
FORMAT = "lisp65-c2.3-v2.1-compiler-consumption-preflight-red-v1"
STATUS = "PREFLIGHT RED: BOUND PROFILE FEATURES NOT CONSUMED"


class PreflightRedError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PreflightRedError(message)


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


def profile_features() -> list[str]:
    lines = [line.split("=", 1)[1].split(",")
             for line in C.BASE.PROFILE.read_text(encoding="utf-8").splitlines()
             if line.startswith("feature_defines=")]
    require(len(lines) == 1 and len(lines[0]) == 24
            and len(set(lines[0])) == 24,
            "bound resolved-profile feature set drift")
    return lines[0]


def command_definitions() -> set[str]:
    return {item[2:].split("=", 1)[0]
            for item in C.failed_compile_command() if item.startswith("-D")}


def run_preprocessors(extra_features: list[str], *, stop_first: bool) -> dict[str, Any]:
    inputs = C.BASE.reference_inputs()["compiler_inputs"]
    prefix = C.preprocessor_command_prefix()
    rows: list[dict[str, Any]] = []
    failure: dict[str, Any] | None = None
    before = C.partial_prefix()
    for index, item in enumerate(inputs):
        source = item["path"]
        command = [prefix[0], *(f"-D{name}" for name in extra_features),
                   *prefix[1:]]
        if Path(source).suffix == ".s":
            command.insert(1, "-Qunused-arguments")
        completed = subprocess.run(
            [*command, "-E", source, "-o", "/dev/null"], cwd=ROOT,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, check=False)
        row = {"ordinal": index, "source": source,
               "exit_status": completed.returncode}
        rows.append(row)
        if completed.returncode:
            failure = {**row,
                "diagnostic": next(
                    line.strip() for line in completed.stderr.splitlines()
                    if "error:" in line)}
            if stop_first:
                break
    require(C.partial_prefix() == before,
            "read-only preprocessor attribution changed partial objects")
    return {"attempted": len(rows),
            "passed": sum(row["exit_status"] == 0 for row in rows),
            "failure": failure, "filesystem_writes": 0}


def validate(value: dict[str, Any]) -> None:
    mechanism = value["mechanism"]
    first = mechanism["first_real_consumer"]
    failure = first.get("failure")
    require(
        value.get("format") == FORMAT
        and value.get("status") == STATUS
        and mechanism["class"] == "BOUND-PROFILE-FEATURES-NOT-CONSUMED"
        and mechanism["bound_profile_feature_count"] == 24
        and mechanism["compiler_consumed_profile_feature_count"] == 0
        and len(mechanism["missing_profile_features"]) == 24
        and first["attempted"] == 25
        and first["passed"] == 24
        and isinstance(failure, dict)
        and failure["ordinal"] == 24
        and failure["source"].endswith(
            "/vm_runtime_overlay.c")
        and "require convergence or proved Chip-RAM" in
            failure["diagnostic"]
        and mechanism["profile-derived_positive_control"] == {
            "attempted": 66, "passed": 66, "failure": None,
            "filesystem_writes": 0}
        and len(mechanism["read_only_header_references"]) == 2
        and all(row["target_is_symlink"] is True
                and row["target_is_copy"] is False
                for row in mechanism["read_only_header_references"])
        and value["classification"]["product_red"] is False
        and value["classification"]["seed_red"] is False
        and value["classification"]["pre_run_producer_configuration_red"] is True
        and value["execution_accounting"]["replacement_runs"] == 0
        and value["execution_accounting"]["new_compiled_objects"] == 0
        and value["execution_accounting"]["final_product_links"] == 0
        and value["disposition"]["retry_authorized"] is False
        and value["disposition"]["owner_required"] is True,
        "compiler-consumption preflight Red drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-profile-consumed": lambda x: x["mechanism"].update(
            compiler_consumed_profile_feature_count=24),
        "drop-missing-feature": lambda x: x["mechanism"][
            "missing_profile_features"].pop(),
        "hide-first-red": lambda x: x["mechanism"][
            "first_real_consumer"].update(failure=None),
        "fail-positive-control": lambda x: x["mechanism"][
            "profile-derived_positive_control"].update(passed=65),
        "copy-header": lambda x: x["mechanism"][
            "read_only_header_references"][0].update(
                target_is_symlink=False, target_is_copy=True),
        "blame-product": lambda x: x["classification"].update(product_red=True),
        "invent-run": lambda x: x["execution_accounting"].update(
            replacement_runs=1),
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
        except PreflightRedError:
            rejected.append(name)
    require(rejected == list(cases), "preflight Red mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    features = profile_features()
    consumed = command_definitions()
    missing = [name for name in features if name not in consumed]
    require(len(missing) == 24, "profile/real-compiler mismatch changed")
    first = run_preprocessors([], stop_first=True)
    positive = run_preprocessors(features, stop_first=False)
    require(first["failure"] is not None and positive["failure"] is None,
            "preprocessor attribution controls drift")
    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-17",
        "status": STATUS,
        "authority": {
            "owner": C.authorization(),
            "bound_resolved_profile": bind(C.BASE.PROFILE),
            "prior_Final_Red": bind(C.PREVIOUS.FINAL_RED),
            "red_attribution": bind(C.ATTR.RECEIPT),
            "dry_run_driver": bind(C.ROOT /
                "tools/host-lisp/c2_v21_root_padding_compiler_consumption_replacement.py"),
            "driver": bind(Path(__file__)),
        },
        "mechanism": {
            "class": "BOUND-PROFILE-FEATURES-NOT-CONSUMED",
            "why": (
                "The frozen resolved profile binds 24 feature definitions, "
                "while the reconstructed real compiler command consumes none. "
                "The first source whose safety branch depends on that profile "
                "therefore rejects compilation before a replacement run."),
            "bound_profile_features": features,
            "bound_profile_feature_count": len(features),
            "compiler_consumed_profile_features": sorted(
                set(features).intersection(consumed)),
            "compiler_consumed_profile_feature_count": 0,
            "missing_profile_features": missing,
            "first_real_consumer": first,
            "profile-derived_positive_control": positive,
            "read_only_header_references": C.header_references(),
            "partial_object_prefix": C.partial_prefix(),
        },
        "classification": {"product_red": False, "seed_red": False,
            "materializer_red": False,
            "pre_run_producer_configuration_red": True},
        "execution_accounting": {"authorized_header_symlinks_created": 2,
            "replacement_runs": 0, "new_materializations": 0,
            "new_compiled_objects": 0, "final_product_links": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "disposition": {"retry_authorized": False, "owner_required": True,
            "authorized_replacement_run_consumed": False,
            "narrow_repair_not_authorized": (
                "Derive the real compiler feature definitions from the frozen "
                "resolved profile, add the candidate-owned scope definitions, "
                "gate exact consumption of every bound profile feature, and "
                "repeat the 66/66 real-preprocessor dry-run before spending the "
                "still-unused replacement run."),
            "permanent_rule_candidate": (
                "A feature profile is bound only when the real compiler command "
                "consumes its complete feature set; configuration receipts alone "
                "are not consumption evidence.")},
        "claim_limit": (
            "Preflight attribution only. The authorized replacement run remains "
            "unused; no new object, final link, Completion, medium or device "
            "action occurred."),
    }
    validate(value)
    value["mutations_rejected"] = mutations(value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check"))
    action = parser.parse_args().action
    value = derive()
    if action == "record":
        require(not RECEIPT.exists(), "preflight Red receipt exists")
        RECEIPT.write_bytes(canonical(value))
    else:
        require(RECEIPT.read_bytes() == canonical(value),
                "preflight Red receipt stale")
    print("compiler-consumption preflight Red: PASS profile=24 consumed=0 "
          "first-red=24 positive=66 run=0 mutations=8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PreflightRedError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"compiler-consumption preflight Red: FAIL {error}",
              file=sys.stderr)
        raise SystemExit(2)
