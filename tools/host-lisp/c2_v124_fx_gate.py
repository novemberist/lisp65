#!/usr/bin/env python3
"""Permanent host-first gate for the v1.2.4 Q8.7 base composition."""

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
CONTRACT = ROOT / "config/c2-fx-contract.json"
SOURCE = ROOT / "lib/stdlib-fx.lisp"
SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-fx-base.json"
BASE_SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-random-base.json"
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
BUILD = ROOT / "build/post-promotion/v124/fx/host-first"
BASE_PREFIX = BUILD / "base/stdlib-p0"
CANDIDATE_PREFIX = BUILD / "candidate/stdlib-p0"
GENERATED_SUITE = BUILD / "equivalence-cases.json"
OBSERVATIONS = BUILD / "candidate/observations.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.4-fx-host-first-receipt.json"
)
POST_TIME_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.4-fx-post-time-revalidation-receipt.json"
)
FINAL_COMPOSITION_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.4-fx-final-composition-revalidation-receipt.json"
)
PUBLIC_BUILD_RECEIPT = BUILD / "public-build-current-source-receipt.json"
FX_NAMES = [
    "%fx-error",
    "%fx-add2",
    "int->fx",
    "fx",
    "fx->int",
    "fx+",
    "fx-",
    "%fx-negative-product-p",
    "%fx-mag-low",
    "%fx-mag-high",
    "%fx-write-inputs",
    "%fx-wait-multiply",
    "%fx-wait-divide",
    "%fx-finish-magnitude",
    "%fx-round-magnitude",
    "%fx-product-result",
    "%fx-read-product",
    "fx*",
    "%fx-scaled-low",
    "%fx-scaled-mid",
    "%fx-scaled-high",
    "%fx-division-result",
    "%fx-read-division",
    "fx/",
    "%fx-fraction-string",
    "fx->string",
]


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


def _defun_block(source: str, name: str) -> str:
    anchor = f"(defun {name} "
    start = source.find(anchor)
    require(start >= 0, f"fx defun absent: {name}")
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise GateError(f"unterminated fx defun: {name}")


def validate(
    contract: dict[str, Any], source: str, suite: dict[str, Any]
) -> dict[str, Any]:
    representation = contract["representation"]
    arithmetic = contract["arithmetic"]
    unit = contract["math_unit"]
    placement = contract["placement"]
    require(
        contract["format"] == "lisp65-c2-fx-base-composition-v1"
        and representation["scale"] == 128
        and representation["format_name"] == "signed Q8.7"
        and representation["raw_domain"] == [-16384, 16383]
        and arithmetic["rounding"] == "nearest, ties away from zero"
        and arithmetic["integer_conversion"] == "fx->int truncates toward zero",
        "fx semantic contract drift",
    )
    require(
        unit["inputs"] == {
            "left_u32_le": "$D770-$D773",
            "right_u32_le": "$D774-$D777",
        }
        and unit["multiply"]["product_u64_le"] == "$D778-$D77F"
        and unit["divide"]["quotient_u32_le"] == "$D76C-$D76F"
        and unit["divide"]["fraction_u32_le"] == "$D768-$D76B"
        and unit["divide"]["rounding_probe"] == "$D76B bit 7",
        "fx math-register contract drift",
    )
    require(
        placement == {
            "code": "Bank-2 base composition after random",
            "resident_code_bytes": 0,
            "resident_state_bytes": 0,
            "new_resident_gc_roots": 0,
            "static_plane_root_records": 0,
            "runtime_overlay_records": 0,
            "require_dependency": False,
            "legacy_stdlib_fixed": "superseded; it is neither extended nor included",
        },
        "fx placement contract drift",
    )
    require(
        suite["extends"] == "p0-stdlib-random-base.json"
        and suite["sources"] == ["lib/stdlib-fx.lisp"]
        and suite["functions"] == FX_NAMES
        and suite["tailcall_self"]
            == ["%fx-wait-multiply", "%fx-wait-divide"],
        "fx base-composition suite drift",
    )
    case_by_name = {row["name"]: row for row in suite["cases"]}
    for name in ("fx-multiply-main", "fx-divide-main"):
        require(
            case_by_name[name].get("expect_io_min") == {
                "math_input_write": 24,
                "math_refresh": 24,
            },
            f"fx execution witness absent: {name}",
        )

    write_inputs = _defun_block(source, "%fx-write-inputs")
    require(
        write_inputs.count("(poke 215 ") == 8
        and all(f"(poke 215 {address} " in write_inputs
                for address in range(112, 120)),
        "fx input-register writer drift",
    )
    product_read = _defun_block(source, "%fx-read-product")
    divide_read = _defun_block(source, "%fx-read-division")
    require(
        all(f"(peek 215 {address})" in product_read
            for address in range(120, 128))
        and all(f"(peek 215 {address})" in divide_read
                for address in (108, 109, 110, 111, 107))
        and "(peek 215 106)" not in divide_read,
        "fx result-register read drift",
    )
    multiply = _defun_block(source, "fx*")
    divide = _defun_block(source, "fx/")
    require(
        multiply.count("%fx-write-inputs") == 1
        and multiply.find("(%fx-write-inputs")
            < multiply.find("(%fx-wait-multiply)")
            < multiply.find("(%fx-read-product negative)")
        and divide.count("%fx-write-inputs") == 1
        and divide.find("(%fx-write-inputs")
            < divide.find("(%fx-wait-divide)")
            < divide.find("(%fx-read-division negative)"),
        "fx transaction sequence drift",
    )
    for block, wait_name, read_name in (
        (multiply, "%fx-wait-multiply", "%fx-read-product"),
        (divide, "%fx-wait-divide", "%fx-read-division"),
    ):
        transaction = block[block.find("(%fx-write-inputs"):]
        read_end = transaction.find(f"({read_name} negative)")
        require(read_end >= 0, "fx transaction result edge absent")
        protected = transaction[:read_end]
        require(
            not any(token in protected for token in ("(* ", "(/ ", "(mod ", "(remainder "))
            and f"({wait_name})" in protected,
            "arithmetic entered the shared math-unit transaction",
        )
    require(
        "stdlib-fixed" not in source
        and "(require " not in source
        and "integer->fx" not in source
        and "fx->integer" not in source,
        "fx revived its legacy implementation or require dependency",
    )
    return {
        "status": "passed-Q8.7-source-and-transaction-contract",
        "public_functions": list(contract["public_surface"]),
        "private_functions": len(FX_NAMES) - len(contract["public_surface"]),
        "transaction_input_writes": 8,
        "resident_delta_bytes": 0,
        "runtime_overlay_records": 0,
        "require_dependency": False,
    }


def mutations(
    contract: dict[str, Any], source: str, suite: dict[str, Any]
) -> dict[str, str]:
    candidates: list[tuple[str, dict[str, Any], str, dict[str, Any]]] = []

    def source_mutation(label: str, old: str, new: str) -> None:
        require(old in source, f"mutation anchor absent: {label}")
        candidates.append((label, contract, source.replace(old, new, 1), suite))

    changed = copy.deepcopy(contract)
    changed["representation"]["scale"] = 256
    candidates.append(("scale-256", changed, source, suite))
    changed = copy.deepcopy(contract)
    changed["arithmetic"]["rounding"] = "truncate"
    candidates.append(("truncate-rounding", changed, source, suite))
    changed = copy.deepcopy(contract)
    changed["placement"]["resident_code_bytes"] = 1
    candidates.append(("resident-byte", changed, source, suite))
    changed = copy.deepcopy(contract)
    changed["math_unit"]["divide"]["rounding_probe"] = "$D76A bit 7"
    candidates.append(("wrong-fraction-contract-byte", changed, source, suite))
    source_mutation(
        "wrong-product-low-byte", "(p0 (peek 215 120))", "(p0 (peek 215 122))")
    source_mutation(
        "wrong-fraction-high-byte",
        "(fraction-high (peek 215 107))",
        "(fraction-high (peek 215 106))",
    )
    source_mutation(
        "math-inside-multiply-transaction",
        "(%fx-write-inputs a0 a1 0 0 b0 b1 0 0)\n"
        "      (%fx-wait-multiply)",
        "(%fx-write-inputs a0 a1 0 0 b0 b1 0 0)\n"
        "      (progn (* 1 1) (%fx-wait-multiply))",
    )
    source_mutation(
        "legacy-source-reintroduced",
        "; Q8.7 fixed-point values",
        "; stdlib-fixed Q8.7 fixed-point values",
    )
    source_mutation(
        "require-dependency",
        "(defun %fx-error ()",
        "(require 'fixed-support)\n\n(defun %fx-error ()",
    )
    changed_suite = copy.deepcopy(suite)
    changed_suite["extends"] = "p0-defstruct-v1-lib.json"
    candidates.append(("parked-defstruct-dependency", contract, source, changed_suite))
    changed_suite = copy.deepcopy(suite)
    for row in changed_suite["cases"]:
        if row["name"] == "fx-multiply-main":
            del row["expect_io_min"]
    candidates.append(("built-but-not-executed", contract, source, changed_suite))

    rejected: dict[str, str] = {}
    for label, candidate_contract, candidate_source, candidate_suite in candidates:
        try:
            validate(candidate_contract, candidate_source, candidate_suite)
        except GateError as error:
            rejected[label] = str(error)
        else:
            raise GateError(f"fx mutation survived: {label}")
    return rejected


def round_half_away(numerator: int, denominator: int) -> int:
    magnitude = abs(numerator)
    quotient, remainder = divmod(magnitude, denominator)
    if remainder * 2 >= denominator:
        quotient += 1
    return -quotient if numerator < 0 else quotient


def fx_mul(left: int, right: int) -> int:
    value = round_half_away(left * right, 128)
    if value < -16384 or value > 16383:
        raise OverflowError
    return value


def fx_div(left: int, right: int) -> int:
    if right == 0:
        raise ZeroDivisionError
    value = round_half_away(left * 128, abs(right))
    if right < 0:
        value = -value
    if value < -16384 or value > 16383:
        raise OverflowError
    return value


def generated_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    multiply_pairs = [
        (-16384, 128), (-8192, 192), (-1024, -257), (-257, 255),
        (-129, 64), (-1, 64), (0, 16383), (1, 64), (3, 64),
        (64, 3), (127, 129), (128, 128), (192, 256), (255, 255),
        (1024, 1024), (8191, 129), (16383, 1), (16383, 129),
    ]
    divide_pairs = [
        (-16384, 128), (-8192, 192), (-1024, -257), (-257, 255),
        (-129, 64), (-1, 256), (0, 16383), (1, 256), (3, 256),
        (64, 3), (127, 129), (128, 384), (192, 256), (255, 255),
        (1024, 1024), (8191, 129), (16383, 128), (16383, 1),
    ]
    for index, (left, right) in enumerate(multiply_pairs):
        row = {
            "name": f"fx-oracle-mul-{index:02d}",
            "expr": f"(fx* {left} {right})",
            "expect_io_min": {"math_input_write": 8, "math_refresh": 8},
        }
        try:
            row["expect"] = str(fx_mul(left, right))
        except OverflowError:
            row["expect_vm_error"] = "TypeError"
        cases.append(row)
    for index, (left, right) in enumerate(divide_pairs):
        row = {
            "name": f"fx-oracle-div-{index:02d}",
            "expr": f"(fx/ {left} {right})",
            "expect_io_min": {"math_input_write": 8, "math_refresh": 8},
        }
        try:
            row["expect"] = str(fx_div(left, right))
        except OverflowError:
            row["expect_vm_error"] = "TypeError"
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
    require(result.returncode == 0, f"fx suite red:\n{result.stdout}")
    return {
        "manifest": load(prefix.with_suffix(".manifest.json")),
        "stdout": result.stdout.strip().splitlines(),
    }


def artifact_gate() -> dict[str, Any]:
    dynamic = {
        "extends": str(SUITE.relative_to(ROOT)),
        "cases": generated_cases(),
        "description": "Generated independent-oracle equivalence vectors.",
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
        (code_delta, directory_delta, entry_delta, resolution_delta)
            == (1451, 182, len(FX_NAMES), 71)
        and [row["name"] for row in new["entries"][-len(FX_NAMES):]]
            == FX_NAMES,
        "fx emitted artifact delta drift",
    )
    observations = load(OBSERVATIONS)["suites"][0]["observations"]
    dynamic_names = {row["name"] for row in dynamic["cases"]}
    observed_dynamic = [
        row for row in observations if row["name"] in dynamic_names
    ]
    io_rows = [row for row in observations if "io_witness" in row]
    require(
        len(observed_dynamic) == len(dynamic["cases"])
        and len(io_rows) >= len(dynamic["cases"]) + 2
        and all(row["io_witness"]["math_input_write"] >= 8
                and row["io_witness"]["math_refresh"] >= 8
                for row in io_rows),
        "fx source execution witness drift",
    )
    profile = load(PROFILE)
    profile_code = int(profile["bank2_static_code"]["bytes"])
    profile_entries = int(profile["entries"])
    profile_resolutions = int(profile["resolutions"])
    profile_direct_refs = int(profile["direct_entry_refs"])
    bound_time = profile.get("time_base_delta")
    if bound_time is not None:
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
        profile_code -= int(bound_time["stdlib_code_bytes"])
        profile_entries -= int(bound_time["new_entries"])
        profile_resolutions -= int(bound_time["new_resolutions"])
        profile_direct_refs -= int(bound_time["new_direct_entry_refs"])
    bound_fx = profile.get("fx_base_delta")
    if bound_fx is None:
        baseline_code = profile_code
        baseline_entries = profile_entries
        baseline_resolutions = profile_resolutions
        baseline_direct_refs = profile_direct_refs
    else:
        require(
            bound_fx == {
                "baseline": "Link 80",
                "stdlib_code_bytes": 1451,
                "new_entries": 26,
                "new_resolutions": 71,
                "new_roots": 0,
                "new_direct_entry_refs": 0,
                "resident_bytes": 0,
                "contract": "config/c2-fx-contract.json",
            },
            "bound fx profile delta drift",
        )
        baseline_code = profile_code - int(bound_fx["stdlib_code_bytes"])
        baseline_entries = profile_entries - int(bound_fx["new_entries"])
        baseline_resolutions = (
            profile_resolutions - int(bound_fx["new_resolutions"])
        )
        baseline_direct_refs = (
            profile_direct_refs - int(bound_fx["new_direct_entry_refs"])
        )
    projected = {
        "bank2_static_code_bytes": baseline_code + code_delta,
        "bank2_headroom_bytes": 65536 - baseline_code - code_delta,
        "entries": baseline_entries + entry_delta,
        "entry_headroom": 2048 - baseline_entries - entry_delta,
        "resolutions": baseline_resolutions + resolution_delta,
        "resolution_headroom":
            4096 - baseline_resolutions - resolution_delta,
        "roots": int(profile["roots"]),
        "root_headroom": 1536 - int(profile["roots"]),
        "direct_entry_refs": baseline_direct_refs,
    }
    require(
        baseline_code == 41485
        and baseline_entries == 696
        and baseline_resolutions == 2760
        and baseline_direct_refs == 656
        and projected["bank2_static_code_bytes"] == 42936
        and all(value >= 0 for key, value in projected.items()
                if "headroom" in key),
        "fx projected Bank-2 capacity red",
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
        },
        "projected_post_Link80": projected,
        "execution": {
            "tracked_fx_cases_per_lane": 12,
            "independent_oracle_cases_per_lane": len(dynamic["cases"]),
            "source_cases_total": len(observations),
            "artifact_cases_total": len(observations),
            "math_io_witness_rows": len(io_rows),
            "source_stdout": candidate["stdout"],
            "observations": bind(OBSERVATIONS),
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
            "base_suite": bind(BASE_SUITE),
            "host_vm": bind(ROOT / "tools/host-lisp/bytecode_p0.py"),
            "stdlib_runner":
                bind(ROOT / "tools/host-lisp/bytecode_p0_stdlib.py"),
            "profile": bind(PROFILE),
            "gate": bind(Path(__file__)),
        }
        if not public_build:
            authority["design"] = bind(
                ROOT / "docs/planning/c2.2-v1.2.4-fx-host-first.md"
            )
        value = {
            "format": "lisp65-c2.2-v1.2.4-fx-host-first-receipt-v1",
            "recorded_on": "2026-07-30",
            "status": "passed-fx-host-reference-modeled-register-and-capacity",
            "promotable": False,
            "product_links": 0,
            "hardware_runs": 0,
            "source_contract": source_gate,
            "mutations_rejected": rejected,
            "artifacts": artifacts,
            "authority": authority,
            "next_gate": (
                "Exactly one non-promotable WPLTO capacity card, then Phase "
                "M confirms the target register layout before any product link."
            ),
            "claim_limit": (
                "Independent host arithmetic, source/artifact P0 execution "
                "over a modeled math register file and projected capacity "
                "only; no target register or on-metal fx claim."
            ),
        }
        profile = load(PROFILE)
        receipt = (
            PUBLIC_BUILD_RECEIPT
            if public_build
            else FINAL_COMPOSITION_RECEIPT
            if profile.get("product_build_id") == "0x15da63c2"
            else POST_TIME_RECEIPT
            if profile.get("time_base_delta") is not None
            else RECEIPT
        )
        if public_build:
            value["status"] = (
                "passed-fx-current-source-artifact-public-build"
            )
            value["composition"] = {
                "successor": "time",
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
                "passed-fx-host-reference-in-final-v1.2.4-composition"
            )
            value["composition"] = {
                "successor": "time",
                "release_banner": "WORKBENCH 1.2.4",
                "product_build_id": "0x15da63c2",
                "original_receipt": bind(RECEIPT),
                "post_time_receipt": bind(POST_TIME_RECEIPT),
            }
        if not public_build and receipt == POST_TIME_RECEIPT:
            value["status"] = (
                "passed-fx-host-reference-revalidated-in-time-composition"
            )
            value["composition"] = {
                "successor": "time",
                "successor_delta_bytes": 282,
                "original_receipt": bind(RECEIPT),
            }
        atomic_json(receipt, value)
        delta = artifacts["delta"]
        projected = artifacts["projected_post_Link80"]
        print(
            "c2-v124-fx-gate: PASS "
            f"oracle={artifacts['execution']['independent_oracle_cases_per_lane']}x2 "
            f"io={artifacts['execution']['math_io_witness_rows']} "
            f"mutations={len(rejected)} "
            f"bank2=+{delta['bank2_code_bytes']} "
            f"headroom={projected['bank2_headroom_bytes']} resident=+0"
        )
        return 0
    except (GateError, KeyError, OSError, ValueError) as error:
        print(f"c2-v124-fx-gate: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
