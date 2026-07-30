#!/usr/bin/env python3
"""Permanent host-first gate for the v1.2.4 ``(time form)`` macro."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-time-contract.json"
SOURCE = ROOT / "lib/stdlib-time.lisp"
SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-time-base.json"
BASE_SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-fx-base.json"
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
BUILD = ROOT / "build/post-promotion/v124/time/host-first"
BASE_PREFIX = BUILD / "base/stdlib-p0"
CANDIDATE_PREFIX = BUILD / "candidate/stdlib-p0"
GENERATED_SUITE = BUILD / "equivalence-cases.json"
OBSERVATIONS = BUILD / "candidate/observations.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.4-time-host-first-receipt.json"
)
FINAL_COMPOSITION_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.4-time-final-composition-revalidation-receipt.json"
)
PUBLIC_BUILD_RECEIPT = BUILD / "public-build-current-source-receipt.json"
TIME_NAMES = ["%time-read", "%time-delta", "time"]


class GateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"bound input absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    temporary.replace(path)


def validate(
    contract: dict[str, Any], source: str, suite: dict[str, Any]
) -> dict[str, Any]:
    clock = contract["clock"]
    duration = contract["duration"]
    placement = contract["placement"]
    surface = contract["public_surface"]
    require(
        contract["format"] == "lisp65-c2-time-base-composition-v1"
        and contract["status"] == "owner-commissioned-host-first"
        and surface["syntax"] == "(time form)"
        and surface["evaluation"] == "form is evaluated exactly once"
        and surface["result"] == "the value of form is returned unchanged",
        "time public contract drift",
    )
    require(
        clock["low_byte"] == "$FF83"
        and clock["high_byte"] == "$FF84"
        and clock["read_order"]
            == "high-low-high; retry until both high reads agree"
        and clock["admission_band_hz"] == [48, 52]
        and 48 <= float(clock["calibration_hz"]) <= 52,
        "time clock authority drift",
    )
    require(
        duration == {
            "maximum_reportable_frames": 16383,
            "overflow_from_frames": 16384,
            "overflow_edge": "%time-error-duration-overflow",
            "overflow_policy": "named fail-closed error; no silent wrap",
        },
        "time duration boundary drift",
    )
    require(
        placement == {
            "code": "Bank-2 base composition after fx",
            "admission_budget_bytes": 512,
            "resident_code_bytes": 0,
            "resident_state_bytes": 0,
            "new_resident_gc_roots": 0,
            "static_plane_root_records": 0,
            "runtime_overlay_records": 0,
            "native_primitives": 0,
            "require_dependency": False,
        },
        "time placement/admission drift",
    )
    required = (
        "(high-before (peek 255 132))",
        "(low (peek 255 131))",
        "(high-after (peek 255 132))",
        "(if (= high-before high-after)",
        "(%time-read))))",
        "(borrow (if (< finish-low start-low) 1 0))",
        "(if (= wrapped-high 0) 255 (- wrapped-high 1))",
        "(if (>= high 64)",
        "(%time-error-duration-overflow)",
        "(+ (* high 256) low)",
        "(defmacro time (form)",
        "(,value ,form)",
        "(print (%time-delta ,start ,finish))",
    )
    require(all(token in source for token in required),
            "time source seam drift")
    require(
        source.count(",form") == 1
        and source.count("(print (%time-delta") == 1
        and "(poke 255 131" not in source
        and "(poke 255 132" not in source
        and "(require " not in source,
        "time single-evaluation/read-only/output invariant drift",
    )
    require(
        suite["extends"] == "p0-stdlib-fx-base.json"
        and suite["sources"] == ["lib/stdlib-time.lisp"]
        and suite["functions"] == TIME_NAMES
        and suite["tailcall_self"] == ["%time-read"]
        and any(row["name"] == "time-kind"
                and row["expect"] == "macro" for row in suite["cases"])
        and any(row["name"] == "time-expander-head"
                and row["expect"] == "let*" for row in suite["cases"])
        and any(row["name"] == "time-delta-overflow"
                and row["expect_vm_error"] == "DirMiss"
                for row in suite["cases"]),
        "time suite/execution witness drift",
    )
    return {
        "status": "passed-time-source-contract",
        "public_macros": ["time"],
        "private_functions": 2,
        "counter": "$FF84/$FF83/$FF84",
        "maximum_reportable_frames": 16383,
        "resident_delta_bytes": 0,
        "native_primitives": 0,
    }


def mutations(
    contract: dict[str, Any], source: str, suite: dict[str, Any]
) -> dict[str, str]:
    candidates: list[tuple[str, dict[str, Any], str, dict[str, Any]]] = []

    def source_mutation(label: str, old: str, new: str) -> None:
        require(old in source, f"mutation anchor absent: {label}")
        candidates.append((label, contract, source.replace(old, new, 1), suite))

    changed = copy.deepcopy(contract)
    changed["clock"]["high_byte"] = "$FF85"
    candidates.append(("wrong-high-byte-contract", changed, source, suite))
    changed = copy.deepcopy(contract)
    changed["placement"]["admission_budget_bytes"] = 513
    candidates.append(("budget-relaxed", changed, source, suite))
    changed = copy.deepcopy(contract)
    changed["placement"]["resident_code_bytes"] = 1
    candidates.append(("resident-byte", changed, source, suite))
    source_mutation("wrong-high-read", "(peek 255 132)", "(peek 255 133)")
    source_mutation(
        "non-atomic-read", "(if (= high-before high-after)",
        "(if (= high-before high-before)")
    source_mutation(
        "missing-retry", "(%time-read))))", "(cons high-after low))))")
    source_mutation(
        "borrow-removed",
        "(borrow (if (< finish-low start-low) 1 0))",
        "(borrow 0)",
    )
    source_mutation(
        "overflow-admitted", "(if (>= high 64)", "(if (> high 64)")
    source_mutation(
        "form-evaluated-twice",
        "(,value ,form)",
        "(,value (progn ,form ,form))",
    )
    source_mutation(
        "output-removed",
        "(print (%time-delta ,start ,finish))",
        "(%time-delta ,start ,finish)",
    )
    changed_suite = copy.deepcopy(suite)
    changed_suite["cases"] = [
        row for row in changed_suite["cases"] if row["name"] != "time-kind"
    ]
    candidates.append(("macro-built-not-executed", contract, source, changed_suite))

    rejected: dict[str, str] = {}
    for label, candidate_contract, candidate_source, candidate_suite in candidates:
        try:
            validate(candidate_contract, candidate_source, candidate_suite)
        except GateError as error:
            rejected[label] = str(error)
        else:
            raise GateError(f"time mutation survived: {label}")
    return rejected


def delta(start: int, finish: int) -> int:
    frames = (finish - start) & 0xFFFF
    if frames >= 16384:
        raise OverflowError
    return frames


def generated_cases() -> list[dict[str, Any]]:
    pairs = [
        (0x0000, 0x0000), (0x0000, 0x0001), (0x0001, 0x00FF),
        (0x00FA, 0x0105), (0x0105, 0x00FA), (0x3FFE, 0x7FFD),
        (0x8000, 0xBFFF), (0xFFFA, 0x0005), (0xFFFF, 0x0000),
        (0xC123, 0x0122), (0x0000, 0x4000), (0x1234, 0x9234),
    ]
    cases: list[dict[str, Any]] = []
    for index, (start, finish) in enumerate(pairs):
        row: dict[str, Any] = {
            "name": f"time-oracle-{index:02d}",
            "expr": (
                f"(%time-delta (cons {start >> 8} {start & 255}) "
                f"(cons {finish >> 8} {finish & 255}))"
            ),
        }
        try:
            row["expect"] = str(delta(start, finish))
        except OverflowError:
            row["expect_vm_error"] = "DirMiss"
        cases.append(row)
    return cases


def run_suite(
    suite_path: Path, prefix: Path, observation: Path | None = None
) -> dict[str, Any]:
    prefix.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "tools/host-lisp/bytecode_p0_stdlib.py",
        "--check",
        "--emit-artifacts",
        str(prefix.relative_to(ROOT)),
    ]
    if observation is not None:
        command.extend([
            "--observation-report", str(observation.relative_to(ROOT)),
        ])
    command.append(str(suite_path.relative_to(ROOT)))
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    require(result.returncode == 0, f"time suite red:\n{result.stdout}")
    return {
        "manifest": load(prefix.with_suffix(".manifest.json")),
        "stdout": result.stdout.strip().splitlines(),
    }


def artifact_gate() -> dict[str, Any]:
    dynamic = {
        "extends": str(SUITE.relative_to(ROOT)),
        "cases": generated_cases(),
        "description": "Generated independent modulo-delta oracle vectors.",
    }
    atomic_json(GENERATED_SUITE, dynamic)
    baseline = run_suite(BASE_SUITE, BASE_PREFIX)
    candidate = run_suite(GENERATED_SUITE, CANDIDATE_PREFIX, OBSERVATIONS)
    old = baseline["manifest"]
    new = candidate["manifest"]
    code_delta = int(new["code_bytes"]) - int(old["code_bytes"])
    directory_delta = int(new["directory_bytes"]) - int(old["directory_bytes"])
    entry_delta = int(new["objects"]) - int(old["objects"])
    resolution_delta = (
        sum(int(row["lit_count"]) for row in new["entries"])
        - sum(int(row["lit_count"]) for row in old["entries"])
    )
    require(
        code_delta <= 512
        and code_delta == 282
        and (directory_delta, entry_delta, resolution_delta) == (21, 3, 12)
        and [row["name"] for row in new["entries"][-3:]] == TIME_NAMES
        and new["entries"][-1]["flags"] == 1,
        "time emitted artifact delta/admission drift",
    )
    observations = load(OBSERVATIONS)["suites"][0]["observations"]
    generated_names = {row["name"] for row in dynamic["cases"]}
    observed = [row for row in observations if row["name"] in generated_names]
    require(
        len(observed) == len(dynamic["cases"])
        and {row["name"] for row in observed} == generated_names,
        "time independent-oracle execution witness drift",
    )
    profile = load(PROFILE)
    bound_time = profile.get("time_base_delta")
    if bound_time is None:
        baseline_code = int(profile["bank2_static_code"]["bytes"])
    else:
        require(
            bound_time == {
                "baseline": "v1.2.4 fx candidate",
                "stdlib_code_bytes": 282,
                "new_entries": 3,
                "new_resolutions": 12,
                "new_roots": 0,
                "new_direct_entry_refs": 0,
                "resident_bytes": 0,
                "native_primitives": 0,
                "contract": "config/c2-time-contract.json",
            },
            "bound time profile delta drift",
        )
        baseline_code = (
            int(profile["bank2_static_code"]["bytes"])
            - int(bound_time["stdlib_code_bytes"])
        )
    require(
        profile.get("fx_base_delta") is not None and baseline_code == 42936,
        "time profile is not the accepted fx predecessor",
    )
    projected = baseline_code + code_delta
    require(
        projected == 43218 and 65536 - projected == 22318,
        "time projected Bank-2 capacity drift",
    )
    return {
        "baseline": {
            "manifest": bind(BASE_PREFIX.with_suffix(".manifest.json")),
            "code_bytes": int(old["code_bytes"]),
            "objects": int(old["objects"]),
        },
        "candidate": {
            "manifest": bind(CANDIDATE_PREFIX.with_suffix(".manifest.json")),
            "code_bytes": int(new["code_bytes"]),
            "objects": int(new["objects"]),
        },
        "delta": {
            "bank2_code_bytes": code_delta,
            "directory_bytes": directory_delta,
            "objects": entry_delta,
            "resolution_words": resolution_delta,
            "resident_bytes": 0,
            "native_primitives": 0,
        },
        "projected": {
            "bank2_static_code_bytes": projected,
            "bank2_headroom_bytes": 65536 - projected,
            "admission_budget_bytes": 512,
        },
        "execution": {
            "tracked_cases_per_lane": len(load(SUITE)["cases"]),
            "independent_oracle_cases_per_lane": len(dynamic["cases"]),
            "lanes": 2,
            "observations": bind(OBSERVATIONS),
            "stdout": candidate["stdout"],
        },
    }


def main(*, public_build: bool = False) -> int:
    try:
        contract = load(CONTRACT)
        source = SOURCE.read_text(encoding="utf-8")
        suite = load(SUITE)
        source_gate = validate(contract, source, suite)
        rejected = mutations(contract, source, suite)
        artifacts = artifact_gate()
        authority = {
            "contract": bind(CONTRACT),
            "source": bind(SOURCE),
            "suite": bind(SUITE),
            "host_vm": bind(ROOT / "tools/host-lisp/bytecode_p0.py"),
            "stdlib_runner":
                bind(ROOT / "tools/host-lisp/bytecode_p0_stdlib.py"),
            "profile": bind(PROFILE),
            "gate": bind(Path(__file__)),
        }
        if not public_build:
            authority.update({
                "fx_predecessor":
                    bind(ROOT / "tests/bytecode/dialect-v2/evidence/"
                         "architecture-blocks/"
                         "c2.2-v1.2.4-fx-host-first-receipt.json"),
                "phase_m":
                    bind(ROOT / "tests/bytecode/dialect-v2/evidence/"
                         "architecture-blocks/"
                         "c2.2-v1.2.4-phase-m-hardware-receipt.json"),
            })
        value = {
            "format": "lisp65-c2.2-v1.2.4-time-host-first-receipt-v1",
            "recorded_on": "2026-07-30",
            "status": "passed-time-host-reference-and-admission",
            "promotable": False,
            "product_links": 0,
            "hardware_runs": 0,
            "source_contract": source_gate,
            "mutations_rejected": rejected,
            "artifacts": artifacts,
            "authority": authority,
            "next_gate": "One non-promotable combined fx+time WPLTO card.",
            "claim_limit": (
                "Host source/artifact semantics and projected Bank-2 "
                "admission only; no successor product or release claim."
            ),
        }
        receipt = (
            PUBLIC_BUILD_RECEIPT
            if public_build
            else FINAL_COMPOSITION_RECEIPT
            if load(PROFILE).get("product_build_id") == "0x15da63c2"
            else RECEIPT
        )
        if public_build:
            value["status"] = (
                "passed-time-current-source-artifact-public-build"
            )
            value["composition"] = {
                "release_banner": "WORKBENCH 1.2.4",
                "product_build_id": "0x15da63c2",
                "private_evidence_inputs": 0,
            }
            value["claim_limit"] = (
                "Current public source/artifact semantics and capacity only; "
                "historical proof receipts and hardware claims are not inputs."
            )
        elif receipt == FINAL_COMPOSITION_RECEIPT:
            value["status"] = (
                "passed-time-host-reference-in-final-v1.2.4-composition"
            )
            value["composition"] = {
                "release_banner": "WORKBENCH 1.2.4",
                "product_build_id": "0x15da63c2",
                "original_receipt": bind(RECEIPT),
            }
        atomic_json(receipt, value)
        delta_row = artifacts["delta"]
        projected = artifacts["projected"]
        print(
            "c2-v124-time-gate: PASS "
            f"oracle={artifacts['execution']['independent_oracle_cases_per_lane']}x2 "
            f"mutations={len(rejected)} "
            f"bank2=+{delta_row['bank2_code_bytes']} "
            f"headroom={projected['bank2_headroom_bytes']} resident=+0 native=+0"
        )
        return 0
    except (GateError, KeyError, OSError, ValueError) as error:
        print(f"c2-v124-time-gate: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
