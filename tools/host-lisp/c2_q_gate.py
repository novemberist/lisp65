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
CONTRACT = ROOT / "config/c2-q-contract.json"
SOURCE = ROOT / "lib/stdlib-q.lisp"
SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-q-base.json"
BASE_SUITE = ROOT / "tests/bytecode/libs/p0-stdlib-random-base.json"
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
BUILD = ROOT / "build/post-promotion/v124/q/host-first"
BASE_PREFIX = BUILD / "base/stdlib-p0"
CANDIDATE_PREFIX = BUILD / "candidate/stdlib-p0"
GENERATED_SUITE = BUILD / "equivalence-cases.json"
OBSERVATIONS = BUILD / "candidate/observations.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.3-q-host-first-receipt.json"
)
PUBLIC_BUILD_RECEIPT = BUILD / "public-build-current-source-receipt.json"
Q_NAMES = [
    "%q-error",
    "%q-add2",
    "int->q",
    "q",
    "q->int",
    "q+",
    "q-",
    "%q-negative-product-p",
    "%q-mag-low",
    "%q-mag-high",
    "%q-write-inputs",
    "%q-wait-multiply",
    "%q-wait-divide",
    "%q-finish-magnitude",
    "%q-round-magnitude",
    "%q-product-result",
    "%q-read-product",
    "q*",
    "%q-scaled-low",
    "%q-scaled-mid",
    "%q-scaled-high",
    "%q-division-result",
    "%q-read-division",
    "q/",
    "%q-fraction-string",
    "q->string",
]
LEGACY_PUBLIC_NAMES = [
    "fx", "int->fx", "fx->int", "fx+", "fx-", "fx*", "fx/", "fx->string",
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


def preserve_sealed_receipt(path: Path, value: dict[str, Any]) -> None:
    """Keep the sealed Q receipt when only manifest provenance has advanced."""
    if not path.is_file():
        atomic_json(path, value)
        return
    sealed = load(path)
    normalized = copy.deepcopy(value)
    for world in ("baseline", "candidate"):
        current = value["artifacts"][world]["manifest"]
        historical = sealed["artifacts"][world]["manifest"]
        require(
            {key: current.get(key) for key in ("path", "bytes")}
            == {key: historical.get(key) for key in ("path", "bytes")},
            f"sealed Q {world} manifest path/size drift",
        )
        normalized["artifacts"][world]["manifest"] = historical
    require(normalized["authority"]["gate"]["path"]
            == sealed["authority"]["gate"]["path"],
            "historical Q gate identity drift")
    normalized["authority"]["gate"] = sealed["authority"]["gate"]
    require(normalized == sealed, "historical Q receipt semantic drift")


def _defun_block(source: str, name: str) -> str:
    anchor = f"(defun {name} "
    start = source.find(anchor)
    require(start >= 0, f"q defun absent: {name}")
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
    raise GateError(f"unterminated q defun: {name}")


def validate(
    contract: dict[str, Any], source: str, suite: dict[str, Any]
) -> dict[str, Any]:
    representation = contract["representation"]
    arithmetic = contract["arithmetic"]
    unit = contract["math_unit"]
    placement = contract["placement"]
    require(
        contract["format"] == "lisp65-c2-q-base-composition-v1"
        and representation["scale"] == 128
        and representation["format_name"] == "signed Q8.7"
        and representation["raw_domain"] == [-16384, 16383]
        and arithmetic["rounding"] == "nearest, ties away from zero"
        and arithmetic["integer_conversion"] == "q->int truncates toward zero",
        "q semantic contract drift",
    )
    require(
        contract["public_surface_policy"]["first_advertised_release"] == "v1.3.0"
        and contract["public_surface_policy"]["legacy_fx_aliases"] == "forbidden"
        and all(f"(defun {name} " not in source for name in LEGACY_PUBLIC_NAMES),
        "q public surface revived a legacy fx alias",
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
        "q math-register contract drift",
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
        "q placement contract drift",
    )
    require(
        suite["extends"] == "p0-stdlib-random-base.json"
        and suite["sources"] == ["lib/stdlib-q.lisp"]
        and suite["functions"] == Q_NAMES
        and suite["tailcall_self"]
            == ["%q-wait-multiply", "%q-wait-divide"],
        "q base-composition suite drift",
    )
    case_by_name = {row["name"]: row for row in suite["cases"]}
    for name in ("q-multiply-main", "q-divide-main"):
        require(
            case_by_name[name].get("expect_io_min") == {
                "math_input_write": 24,
                "math_refresh": 24,
            },
            f"q execution witness absent: {name}",
        )

    write_inputs = _defun_block(source, "%q-write-inputs")
    require(
        write_inputs.count("(poke 215 ") == 8
        and all(f"(poke 215 {address} " in write_inputs
                for address in range(112, 120)),
        "q input-register writer drift",
    )
    product_read = _defun_block(source, "%q-read-product")
    divide_read = _defun_block(source, "%q-read-division")
    require(
        all(f"(peek 215 {address})" in product_read
            for address in range(120, 128))
        and all(f"(peek 215 {address})" in divide_read
                for address in (108, 109, 110, 111, 107))
        and "(peek 215 106)" not in divide_read,
        "q result-register read drift",
    )
    multiply = _defun_block(source, "q*")
    divide = _defun_block(source, "q/")
    require(
        multiply.count("%q-write-inputs") == 1
        and multiply.find("(%q-write-inputs")
            < multiply.find("(%q-wait-multiply)")
            < multiply.find("(%q-read-product negative)")
        and divide.count("%q-write-inputs") == 1
        and divide.find("(%q-write-inputs")
            < divide.find("(%q-wait-divide)")
            < divide.find("(%q-read-division negative)"),
        "q transaction sequence drift",
    )
    for block, wait_name, read_name in (
        (multiply, "%q-wait-multiply", "%q-read-product"),
        (divide, "%q-wait-divide", "%q-read-division"),
    ):
        transaction = block[block.find("(%q-write-inputs"):]
        read_end = transaction.find(f"({read_name} negative)")
        require(read_end >= 0, "q transaction result edge absent")
        protected = transaction[:read_end]
        require(
            not any(token in protected for token in ("(* ", "(/ ", "(mod ", "(remainder "))
            and f"({wait_name})" in protected,
            "arithmetic entered the shared math-unit transaction",
        )
    require(
        "stdlib-fixed" not in source
        and "(require " not in source
        and "integer->q" not in source
        and "q->integer" not in source,
        "q revived its legacy implementation or require dependency",
    )
    return {
        "status": "passed-Q8.7-source-and-transaction-contract",
        "public_functions": list(contract["public_surface"]),
        "private_functions": len(Q_NAMES) - len(contract["public_surface"]),
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
        "(%q-write-inputs a0 a1 0 0 b0 b1 0 0)\n"
        "      (%q-wait-multiply)",
        "(%q-write-inputs a0 a1 0 0 b0 b1 0 0)\n"
        "      (progn (* 1 1) (%q-wait-multiply))",
    )
    source_mutation(
        "legacy-source-reintroduced",
        "; Q8.7 fixed-point values",
        "; stdlib-fixed Q8.7 fixed-point values",
    )
    source_mutation(
        "require-dependency",
        "(defun %q-error ()",
        "(require 'fixed-support)\n\n(defun %q-error ()",
    )
    candidates.append((
        "legacy-public-alias",
        contract,
        source + "\n(defun fx (whole &optional fraction) (q whole fraction))\n",
        suite,
    ))
    changed_suite = copy.deepcopy(suite)
    changed_suite["extends"] = "p0-defstruct-v1-lib.json"
    candidates.append(("parked-defstruct-dependency", contract, source, changed_suite))
    changed_suite = copy.deepcopy(suite)
    for row in changed_suite["cases"]:
        if row["name"] == "q-multiply-main":
            del row["expect_io_min"]
    candidates.append(("built-but-not-executed", contract, source, changed_suite))

    rejected: dict[str, str] = {}
    for label, candidate_contract, candidate_source, candidate_suite in candidates:
        try:
            validate(candidate_contract, candidate_source, candidate_suite)
        except GateError as error:
            rejected[label] = str(error)
        else:
            raise GateError(f"q mutation survived: {label}")
    return rejected


def round_half_away(numerator: int, denominator: int) -> int:
    magnitude = abs(numerator)
    quotient, remainder = divmod(magnitude, denominator)
    if remainder * 2 >= denominator:
        quotient += 1
    return -quotient if numerator < 0 else quotient


def q_mul(left: int, right: int) -> int:
    value = round_half_away(left * right, 128)
    if value < -16384 or value > 16383:
        raise OverflowError
    return value


def q_div(left: int, right: int) -> int:
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
            "name": f"q-oracle-mul-{index:02d}",
            "expr": f"(q* {left} {right})",
            "expect_io_min": {"math_input_write": 8, "math_refresh": 8},
        }
        try:
            row["expect"] = str(q_mul(left, right))
        except OverflowError:
            row["expect_vm_error"] = "TypeError"
        cases.append(row)
    for index, (left, right) in enumerate(divide_pairs):
        row = {
            "name": f"q-oracle-div-{index:02d}",
            "expr": f"(q/ {left} {right})",
            "expect_io_min": {"math_input_write": 8, "math_refresh": 8},
        }
        try:
            row["expect"] = str(q_div(left, right))
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
    require(result.returncode == 0, f"q suite red:\n{result.stdout}")
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
            == (1451, 182, len(Q_NAMES), 71)
        and [row["name"] for row in new["entries"][-len(Q_NAMES):]]
            == Q_NAMES,
        "q emitted artifact delta drift",
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
        "q source execution witness drift",
    )
    profile = load(PROFILE)
    profile_code = int(profile["bank2_static_code"]["bytes"])
    profile_entries = int(profile["entries"])
    profile_resolutions = int(profile["resolutions"])
    profile_direct_refs = int(profile["direct_entry_refs"])
    option_a = profile.get("require_prior_append_option_A_delta")
    if option_a is not None:
        require(
            option_a["contract"] == "config/c2-require-resolver-contract.json",
            "bound require-option-A profile delta drift",
        )
    bound_time = profile.get("time_base_delta")
    if bound_time is not None:
        require(
            bound_time == {
                "baseline": "v1.3 q candidate",
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
    bound_q = profile.get("q_base_delta")
    if bound_q is None:
        baseline_code = 41485
        baseline_entries = 696
        baseline_resolutions = 2760
        baseline_direct_refs = 656
    else:
        require(
            bound_q == {
                "baseline": "Link 80",
                "stdlib_code_bytes": 1451,
                "new_entries": 26,
                "new_resolutions": 71,
                "new_roots": 0,
                "new_direct_entry_refs": 0,
                "resident_bytes": 0,
                "contract": "config/c2-q-contract.json",
            },
            "bound q profile delta drift",
        )
        # The accepted Link-80 predecessor is an explicit historical
        # authority; it is not today's total with every successor guessed
        # and subtracted.
        baseline_code = 41485
        baseline_entries = 696
        baseline_resolutions = 2760
        baseline_direct_refs = 656
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
        "q projected Bank-2 capacity red",
    )
    current = {
        "bank2_static_code_bytes": profile_code,
        "bank2_headroom_bytes": 65536 - profile_code,
        "entries": profile_entries,
        "entry_headroom": 2048 - profile_entries,
        "resolutions": profile_resolutions,
        "resolution_headroom": 4096 - profile_resolutions,
        "roots": int(profile["roots"]),
        "root_headroom": 1536 - int(profile["roots"]),
        "direct_entry_refs": profile_direct_refs,
    }
    require(
        int(profile["bank2_static_code"]["headroom_bytes"])
            == current["bank2_headroom_bytes"]
        and all(value >= 0 for key, value in current.items()
                if "headroom" in key),
        "q current-composition capacity red",
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
        "current_composition": current,
        "execution": {
            "tracked_q_cases_per_lane": 12,
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
                ROOT / "docs/planning/1.3-ship-builder-work-plan.md"
            )
        value = {
            "format": "lisp65-c2.2-v1.3-q-host-first-receipt-v1",
            "recorded_on": "2026-08-01",
            "status": "passed-q-host-reference-modeled-register-and-capacity",
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
                "only; no target register or on-metal q claim."
            ),
        }
        receipt = PUBLIC_BUILD_RECEIPT if public_build else RECEIPT
        if public_build:
            value["status"] = (
                "passed-q-current-source-artifact-public-build"
            )
            value["composition"] = {
                "successor": "v1.3-candidate",
                "private_evidence_inputs": 0,
            }
            value["claim_limit"] = (
                "Current public source/artifact semantics and capacity only; "
                "historical proof receipts and hardware claims are not inputs."
            )
        else:
            value["composition"] = {
                "successors": ["time", "require-option-A", "ship-v1.3"],
                "product_build_id": load(PROFILE)["product_build_id"],
            }
        if public_build:
            atomic_json(receipt, value)
        else:
            preserve_sealed_receipt(receipt, value)
        delta = artifacts["delta"]
        projected = artifacts["projected_post_Link80"]
        print(
            "c2-q-gate: PASS "
            f"oracle={artifacts['execution']['independent_oracle_cases_per_lane']}x2 "
            f"io={artifacts['execution']['math_io_witness_rows']} "
            f"mutations={len(rejected)} "
            f"bank2=+{delta['bank2_code_bytes']} "
            f"headroom={projected['bank2_headroom_bytes']} resident=+0"
        )
        return 0
    except (GateError, KeyError, OSError, ValueError) as error:
        print(f"c2-q-gate: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
