#!/usr/bin/env python3
"""Attribute the replacement continuation's compiler-consumption Red."""

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

import c2_v21_root_padding_separate_target_replacement as R  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RED = R.FINAL_RED
RECEIPT = ARCH / (
    "c2.3-v2.1-root-padding-separate-target-replacement-red-attribution.json")
FORMAT = "lisp65-c2.3-v2.1-separate-target-replacement-red-attribution-v1"
STATUS = "ATTRIBUTED FINAL RED: COMPILER INPUT REFERENCE NOT CONSUMED"
EXPECTED_OBJECTS = (
    "000-buffer_overlay.c.o",
    "001-c2_hot_literal.c.o",
)
CONSUMERS = (
    ("src/c2_kernal_runtime.c", "c2-kernal-window.generated.h"),
    ("src/error_overlay.c", "error-text-table.h"),
)


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


def parse_failed_command(red: dict[str, Any]) -> list[str]:
    message = red["error"]["message"]
    prefix = "Command '"
    suffix = "' returned non-zero exit status 1."
    require(message.startswith(prefix) and message.endswith(suffix),
            "replacement compiler failure command absent")
    value = ast.literal_eval(message[len(prefix):-len(suffix)])
    require(isinstance(value, list) and all(isinstance(item, str) for item in value),
            "replacement compiler command is not a string list")
    return value


def compiler_probe(command: list[str], source: str, header: str) -> dict[str, Any]:
    probe = list(command)
    compile_index = probe.index("-c")
    output_index = probe.index("-o")
    probe[compile_index] = "-E"
    probe[compile_index + 1] = source
    probe[output_index + 1] = "/dev/null"
    before = object_bindings()
    negative = subprocess.run(
        probe, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        text=True, check=False)
    source_include = f'#include "{header}"'
    require(negative.returncode == 1 and header in negative.stderr
            and "file not found" in negative.stderr
            and source_include in (ROOT / source).read_text(encoding="utf-8"),
            f"real compiler negative-control drift: {source}")

    positive_command = list(probe)
    positive_command[compile_index:compile_index] = [
        "-I", R.BASE.SOURCE_WPLTO.relative_to(ROOT).as_posix()]
    positive = subprocess.run(
        positive_command, cwd=ROOT, stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE, text=True, check=False)
    require(positive.returncode == 0,
            f"real compiler source-include positive control failed: {source}")
    require(object_bindings() == before,
            "read-only compiler-consumption probe changed partial objects")
    return {
        "source": source,
        "quoted_include": header,
        "header_in_immutable_source": bind(R.BASE.SOURCE_WPLTO / header),
        "header_in_owned_target": (R.WPLTO / header).exists(),
        "exact_target_search_negative_exit": negative.returncode,
        "negative_diagnostic": next(
            line.strip() for line in negative.stderr.splitlines()
            if "fatal error:" in line),
        "immutable_source_search_positive_exit": positive.returncode,
        "filesystem_writes": 0,
    }


def object_bindings() -> list[dict[str, Any]]:
    root = R.WPLTO / (".canonical-objects-" + R.FINAL.stem)
    if not root.exists():
        return []
    return [bind(path) for path in sorted(root.glob("*.o"))]


def final_paths() -> list[str]:
    return [path.relative_to(ROOT).as_posix()
            for path in R.BASE.family(R.FINAL) if path.exists()]


def validate(value: dict[str, Any]) -> None:
    mechanism = value["mechanism"]
    require(
        value.get("format") == FORMAT
        and value.get("status") == STATUS
        and mechanism["class"] == "REFERENCE-RESOLVED-BUT-NOT-CONSUMED"
        and mechanism["materialization_started"] is True
        and mechanism["materialization_completed"] is True
        and mechanism["compiler_started"] is True
        and mechanism["final_link_started"] is False
        and mechanism["partial_object_names"] == list(EXPECTED_OBJECTS)
        and mechanism["final_artifacts_present"] == []
        and mechanism["preflight_reference_smoke_passed"] is True
        and mechanism["real_compiler_include_smoke_was_absent"] is True
        and len(mechanism["real_compiler_probes"]) == 2
        and all(row["header_in_owned_target"] is False
                and row["exact_target_search_negative_exit"] == 1
                and row["immutable_source_search_positive_exit"] == 0
                and row["filesystem_writes"] == 0
                for row in mechanism["real_compiler_probes"])
        and value["classification"]["product_red"] is False
        and value["classification"]["seed_red"] is False
        and value["classification"]["materializer_red"] is False
        and value["classification"]["pre_link_harness_red"] is True
        and value["disposition"]["retry_authorized"] is False
        and value["disposition"]["owner_required"] is True,
        "replacement compiler-consumption attribution drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "erase-materialization": lambda x: x["mechanism"].update(
            materialization_completed=False),
        "claim-final-link": lambda x: x["mechanism"].update(
            final_link_started=True),
        "blame-product": lambda x: x["classification"].update(
            product_red=True),
        "blame-seed": lambda x: x["classification"].update(seed_red=True),
        "blame-materializer": lambda x: x["classification"].update(
            materializer_red=True),
        "claim-reference-smoke-complete": lambda x: x["mechanism"].update(
            real_compiler_include_smoke_was_absent=False),
        "hide-missing-target-header": lambda x: x["mechanism"][
            "real_compiler_probes"][0].update(header_in_owned_target=True),
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
    require(rejected == list(cases),
            "replacement compiler-consumption mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    red = load(RED)
    preflight = load(R.PREFLIGHT)
    command = parse_failed_command(red)
    require(
        red.get("status") ==
            "FINAL RED: SEPARATE-TARGET REPLACEMENT RETURNS TO OWNER"
        and red["retry_authorized"] is False
        and red["owner_disposition_required"] is True
        and red["error"]["type"] == "CalledProcessError"
        and preflight["reference_resolution_smoke"]["reference_count"] == 83
        and preflight["real_consumer_dry_run"]["compiler_inputs"] == 66
        and R.BASE.immutable_tree() == red["source_evidence"]
        and final_paths() == [],
        "replacement Red/preflight signature drift")
    objects = object_bindings()
    require([Path(row["path"]).name for row in objects] == list(EXPECTED_OBJECTS),
            "replacement partial compiler boundary drift")
    header = bind(R.WPLTO / "resident-island.h")
    witness = bind(R.BASE.PREVIOUS.STATE /
                   "materialization-probe/resident-island-a.h")
    require(header["sha256"] == witness["sha256"],
            "replacement materialization witness mismatch")
    probes = [compiler_probe(command, source, required)
              for source, required in CONSUMERS]
    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-17",
        "status": STATUS,
        "authority": {
            "Final_Red": bind(RED),
            "preflight": bind(R.PREFLIGHT),
            "driver": bind(Path(__file__)),
        },
        "mechanism": {
            "class": "REFERENCE-RESOLVED-BUT-NOT-CONSUMED",
            "failed_operation": "third-real-translation-unit-preprocess",
            "why": (
                "The dry-run proved that each immutable input path existed and "
                "resolved, but did not execute the compiler's quoted-include "
                "search against the owned target layout. The immutable generated "
                "headers were force-included by explicit path yet absent by "
                "basename from the target include directory used by source files."),
            "preflight_reference_smoke_passed": True,
            "real_source_owner_consumer_passed": True,
            "real_compiler_include_smoke_was_absent": True,
            "materialization_started": True,
            "materialization_completed": True,
            "materialized_header": header,
            "equals_prior_determinism_witness": True,
            "compiler_started": True,
            "partial_object_names": [Path(row["path"]).name for row in objects],
            "partial_objects": objects,
            "real_compiler_probes": probes,
            "final_link_started": False,
            "final_artifacts_present": final_paths(),
            "immutable_source_evidence_unchanged": True,
        },
        "classification": {
            "product_red": False,
            "seed_red": False,
            "materializer_red": False,
            "pre_link_harness_red": True,
        },
        "execution_accounting": red["execution_accounting"],
        "disposition": {
            "retry_authorized": False,
            "owner_required": True,
            "narrow_repair_not_authorized": (
                "Expose the immutable generated-header inputs by canonical "
                "basename in the owned target include layout (or explicitly add "
                "their immutable directory to the real compiler search path), "
                "then make the dry-run execute the real compiler/preprocessor "
                "consumer for every translation unit before any run is spent."),
            "permanent_rule_candidate": (
                "A resolved input reference is not a consumed compiler input. "
                "Reference dry-runs must exercise the real consumer and its exact "
                "search domain."),
        },
        "claim_limit": (
            "Read-only attribution only. The replacement run is consumed; no "
            "repair, materialization, final link, Completion, medium or device "
            "action is authorized."),
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
        require(not RECEIPT.exists(), "replacement attribution receipt exists")
        RECEIPT.write_bytes(canonical(value))
    else:
        require(RECEIPT.read_bytes() == canonical(value),
                "replacement attribution receipt stale")
    print("replacement Red attribution: PASS materialized=1 objects=2 "
          "final-link=0 compiler-probes=2 mutations=8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttributionError, OSError, ValueError, KeyError, SyntaxError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"replacement Red attribution: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
