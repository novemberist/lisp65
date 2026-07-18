#!/usr/bin/env python3
"""Prove case-observation equivalence for the four v2 Workbench artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST_TOOLS = ROOT / "tools" / "host-lisp"
if str(HOST_TOOLS) not in sys.path:
    sys.path.insert(0, str(HOST_TOOLS))

import bytecode_p0_stdlib as Stdlib  # noqa: E402


DEFAULT_CLOSURE = ROOT / "config" / "v2-workbench-artifact-closure.json"
DEFAULT_CODEMOD_RECEIPT = ROOT / "build" / "bytecode" / "dialect-v2" / "codemod-receipt.json"
DEFAULT_BASELINE = (
    ROOT / "config" / "v11-workbench-differential-baseline.json"
)
DEFAULT_OUTPUT = (
    ROOT / "tests" / "bytecode" / "dialect-v2" / "evidence"
    / "capability-carrier" / "workbench-artifact-differential-receipt.json"
)
FORMAT = "lisp65-v2-workbench-artifact-differential-v1"
ARTIFACT_IDS = ("resident", "ide", "idex", "m65d")


class DifferentialError(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _path(raw: str, label: str, *, require=True) -> Path:
    if not isinstance(raw, str) or not raw or Path(raw).is_absolute():
        raise DifferentialError(f"{label} must be a project-relative path")
    path = (ROOT / raw).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise DifferentialError(f"{label} escapes the project root") from exc
    if require and (path.is_symlink() or not path.is_file()):
        raise DifferentialError(f"{label} is not a regular file: {raw}")
    return path


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DifferentialError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise DifferentialError(f"{label} must be an object")
    return value


def _compare(
    artifact_id: str, baseline: list[dict[str, str]], candidate: list[dict[str, str]],
    allowed_additions: list[dict[str, str]], allowed_removals: list[dict[str, str]],
    allowed_changes: list[dict[str, str]],
) -> None:
    baseline_rows = [(row["name"], _observation_value(row)) for row in baseline]
    candidate_rows = [(row["name"], _observation_value(row)) for row in candidate]
    baseline_map = dict(baseline_rows)
    candidate_map = dict(candidate_rows)
    missing = sorted(set(baseline_map) - set(candidate_map))
    added = sorted(set(candidate_map) - set(baseline_map))
    changed = sorted(
        name for name in set(baseline_map) & set(candidate_map)
        if baseline_map[name] != candidate_map[name]
    )
    allowed = {row["name"]: row["result"] for row in allowed_additions}
    allowed_missing = {row["name"]: row["result"] for row in allowed_removals}
    allowed_changed = {
        row["name"]: (row["before"], row["after"]) for row in allowed_changes
    }
    observed_additions = {name: candidate_map[name] for name in added}
    observed_removals = {name: baseline_map[name] for name in missing}
    observed_changes = {
        name: (baseline_map[name], candidate_map[name]) for name in changed
    }
    if (
        observed_additions != allowed
        or observed_removals != allowed_missing
        or observed_changes != allowed_changed
    ):
        raise DifferentialError(
            f"{artifact_id} observation drift: missing={missing} added={added} "
            f"changed={changed} allowed_added={sorted(allowed)} "
            f"allowed_removed={sorted(allowed_missing)} "
            f"allowed_changed={sorted(allowed_changed)}"
        )


def _observation_value(row: dict[str, str]) -> str:
    if isinstance(row.get("result"), str):
        return row["result"]
    if isinstance(row.get("error"), str):
        return f"error:{row['error']}"
    raise DifferentialError(f"observation has neither result nor error: {row.get('name')}")


def _load_observation_baseline(
    contract_path: Path,
) -> tuple[
    dict[str, list[dict[str, str]]], dict[str, list[dict[str, str]]],
    dict[str, list[dict[str, str]]], dict[str, list[dict[str, str]]], Path,
]:
    contract = _json(contract_path, "differential observation baseline")
    additions = contract.get("intentional_additions")
    removals = contract.get("intentional_removals")
    changes = contract.get("intentional_changes")
    if (
        contract.get("format") != "lisp65-v11-workbench-differential-baseline-v1"
        or not isinstance(additions, dict)
        or not isinstance(removals, dict)
        or not isinstance(changes, dict)
        or tuple(additions) != ARTIFACT_IDS
        or tuple(removals) != ARTIFACT_IDS
        or tuple(changes) != ARTIFACT_IDS
    ):
        raise DifferentialError("observation-baseline contract identity drift")
    normalized_additions: dict[str, list[dict[str, str]]] = {}
    normalized_removals: dict[str, list[dict[str, str]]] = {}
    for label, groups, normalized in (
        ("additions", additions, normalized_additions),
        ("removals", removals, normalized_removals),
    ):
      for artifact_id, rows in groups.items():
        if (
            not isinstance(rows, list)
            or any(
                not isinstance(row, dict)
                or set(row) != {"name", "result", "reason"}
                or not all(
                    isinstance(row.get(key), str) and row.get(key)
                    for key in ("name", "result", "reason")
                )
                for row in rows
            )
            or len({row["name"] for row in rows}) != len(rows)
        ):
            raise DifferentialError(
                f"observation-baseline {label} for {artifact_id} are invalid"
            )
        normalized[artifact_id] = [
            {"name": row["name"], "result": row["result"]} for row in rows
        ]
    normalized_changes: dict[str, list[dict[str, str]]] = {}
    for artifact_id, rows in changes.items():
        if (
            not isinstance(rows, list)
            or any(
                not isinstance(row, dict)
                or set(row) != {"name", "before", "after", "reason"}
                or not all(
                    isinstance(row.get(key), str) and row.get(key)
                    for key in ("name", "before", "after", "reason")
                )
                for row in rows
            )
            or len({row["name"] for row in rows}) != len(rows)
        ):
            raise DifferentialError(
                f"observation-baseline changes for {artifact_id} are invalid"
            )
        normalized_changes[artifact_id] = [
            {"name": row["name"], "before": row["before"], "after": row["after"]}
            for row in rows
        ]

    receipt_path = _path(
        contract.get("observation_receipt"), "observation-baseline receipt"
    )
    if _sha(receipt_path.read_bytes()) != contract.get("observation_receipt_sha256"):
        raise DifferentialError("observation-baseline receipt SHA drift")
    receipt = _json(receipt_path, "observation-baseline receipt")
    artifacts = receipt.get("artifacts")
    if (
        receipt.get("format") != FORMAT
        or receipt.get("status") != "passed"
        or not isinstance(artifacts, list)
        or tuple(row.get("id") for row in artifacts) != ARTIFACT_IDS
        or receipt.get("summary", {}).get("artifacts")
        != contract.get("expected_artifacts")
        or receipt.get("summary", {}).get("cases") != contract.get("expected_cases")
        or receipt.get("summary", {}).get("observation_differences") != 0
    ):
        raise DifferentialError("observation-baseline receipt identity drift")
    baseline: dict[str, list[dict[str, str]]] = {}
    for row in artifacts:
        observations = row.get("observations")
        if (
            not isinstance(observations, list)
            or any(
                not isinstance(item, dict)
                or not isinstance(item.get("name"), str)
                or not isinstance(item.get("result"), str)
                for item in observations
            )
        ):
            raise DifferentialError(
                f"observation baseline for {row.get('id')} is invalid"
            )
        baseline[row["id"]] = [
            {"name": item["name"], "result": item["result"]}
            for item in observations
        ]
    return (
        baseline, normalized_additions, normalized_removals, normalized_changes,
        receipt_path,
    )


def build_receipt(
    closure_path: Path, codemod_path: Path, baseline_contract_path: Path,
) -> dict[str, Any]:
    closure = _json(closure_path, "artifact closure")
    if (
        closure.get("format") != "lisp65-v2-workbench-artifact-closure-v1"
        or closure.get("target_abi_profile") != "dialect-v2"
    ):
        raise DifferentialError("artifact closure identity drift")
    artifacts = closure.get("artifacts")
    if (
        not isinstance(artifacts, list)
        or tuple(item.get("id") for item in artifacts) != ARTIFACT_IDS
    ):
        raise DifferentialError("artifact closure is not the exact four-artifact set")

    codemod = _json(codemod_path, "codemod receipt")
    if (
        codemod.get("format") != "lisp65-v2-workbench-codemod-receipt-v1"
        or codemod.get("abi_profile") != "dialect-v2"
        or codemod.get("strict_arity") is not True
    ):
        raise DifferentialError("codemod receipt identity drift")
    codemod_outputs = {
        item.get("path"): item.get("sha256") for item in codemod.get("outputs", [])
        if isinstance(item, dict) and item.get("role") == "suite"
    }
    baseline, additions, removals, changes, baseline_receipt_path = (
        _load_observation_baseline(baseline_contract_path)
    )

    rows = []
    total_cases = 0
    for spec in artifacts:
        source_path = _path(spec.get("source_suite"), f"{spec['id']} source suite")
        candidate_path = _path(spec.get("suite"), f"{spec['id']} candidate suite")
        candidate_rel = _relative(candidate_path)
        if codemod_outputs.get(candidate_rel) != _sha(candidate_path.read_bytes()):
            raise DifferentialError(f"{spec['id']} suite is not bound by the codemod receipt")

        candidate_suite = Stdlib._read_suite(str(candidate_path))
        candidate = Stdlib.check_suite(str(candidate_path), candidate_suite)
        _compare(
            spec["id"], baseline[spec["id"]], candidate["observations"],
            additions.get(spec["id"], []), removals.get(spec["id"], []),
            changes.get(spec["id"], []),
        )

        manifest_path = _path(spec.get("manifest"), f"{spec['id']} manifest")
        manifest = _json(manifest_path, f"{spec['id']} manifest")
        if (
            manifest.get("suite") != candidate_rel
            or manifest.get("abi_profile") != "dialect-v2"
            or manifest.get("strict_arity") is not True
        ):
            raise DifferentialError(f"{spec['id']} manifest profile/suite drift")
        observations = [
            {"name": row["name"], "result": _observation_value(row)}
            for row in candidate["observations"]
        ]
        total_cases += len(observations)
        rows.append({
            "id": spec["id"],
            "source_suite": _relative(source_path),
            "source_suite_sha256": _sha(source_path.read_bytes()),
            "candidate_suite": candidate_rel,
            "candidate_suite_sha256": _sha(candidate_path.read_bytes()),
            "manifest": _relative(manifest_path),
            "manifest_sha256": _sha(manifest_path.read_bytes()),
            "blob_sha256": manifest.get("blob_sha256"),
            "cases": len(observations),
            "observations": observations,
        })

    abi_path = _path(closure.get("abi_ledger"), "ABI ledger")
    return {
        "format": FORMAT,
        "version": 1,
        "status": "passed",
        "profile": "v2-capability-candidate",
        "abi_profile": "dialect-v2",
        "closure": _relative(closure_path),
        "closure_sha256": _sha(closure_path.read_bytes()),
        "abi_ledger": _relative(abi_path),
        "abi_ledger_sha256": _sha(abi_path.read_bytes()),
        "codemod_receipt": _relative(codemod_path),
        "codemod_receipt_sha256": _sha(codemod_path.read_bytes()),
        "observation_baseline_contract": _relative(baseline_contract_path),
        "observation_baseline_contract_sha256": _sha(
            baseline_contract_path.read_bytes()
        ),
        "observation_baseline_receipt": _relative(baseline_receipt_path),
        "observation_baseline_receipt_sha256": _sha(
            baseline_receipt_path.read_bytes()
        ),
        "source_suites": "recorded-for-provenance-not-executed-as-a-live-baseline",
        "intentional_additions": additions,
        "intentional_removals": removals,
        "intentional_changes": changes,
        "artifacts": rows,
        "summary": {
            "artifacts": len(rows), "cases": total_cases,
            "observation_differences": 0,
        },
    }


def selftest() -> None:
    baseline = [{"name": "a", "result": "1"}, {"name": "b", "result": "nil"}]
    _compare("fixture", baseline, list(baseline), [], [], [])
    _compare(
        "fixture", baseline, baseline + [{"name": "c", "result": "2"}],
        [{"name": "c", "result": "2"}], [], [],
    )
    _compare(
        "fixture", baseline, baseline[:-1], [],
        [{"name": "b", "result": "nil"}], [],
    )
    _compare(
        "fixture", baseline, baseline + [{"name": "e", "error": "TypeError"}],
        [{"name": "e", "result": "error:TypeError"}], [], [],
    )
    _compare(
        "fixture", baseline, [{"name": "a", "result": "2"}, baseline[1]],
        [], [], [{"name": "a", "before": "1", "after": "2"}],
    )
    for label, candidate in (
        ("missing", baseline[:-1]),
        ("added", baseline + [{"name": "c", "result": "2"}]),
        ("changed", [{"name": "a", "result": "2"}, baseline[1]]),
    ):
        try:
            _compare("fixture", baseline, candidate, [], [], [])
        except DifferentialError as exc:
            if label not in str(exc):
                raise DifferentialError(f"unclear {label} diagnostic: {exc}") from exc
        else:
            raise DifferentialError(f"{label} observation mutation was accepted")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--closure", type=Path, default=DEFAULT_CLOSURE)
    parser.add_argument("--codemod-receipt", type=Path, default=DEFAULT_CODEMOD_RECEIPT)
    parser.add_argument(
        "--observation-baseline", type=Path, default=DEFAULT_BASELINE
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            selftest()
            print("v2-workbench-differential: SELFTEST PASS mutations=3 contracts=5")
            return 0
        receipt = build_receipt(
            args.closure.resolve(), args.codemod_receipt.resolve(),
            args.observation_baseline.resolve(),
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except (DifferentialError, Stdlib.StdlibCheckError, AssertionError, OSError) as exc:
        print(f"v2-workbench-differential: FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "v2-workbench-differential: PASS "
        f"artifacts={receipt['summary']['artifacts']} "
        f"cases={receipt['summary']['cases']} differences=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
