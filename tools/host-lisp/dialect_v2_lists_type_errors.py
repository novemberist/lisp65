#!/usr/bin/env python3
"""Seal the G2 evidence for the v2 public list-error channel."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/bytecode/dialect-v2/lists/cases.json"
BUILD = ROOT / "build/bytecode/dialect-v2/lists"
OUTPUT = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/lists-malformed-type-errors-g2.json"
BLOCK_RECEIPT = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/lists-malformed-type-errors-receipt.json"
ENGINES = (
    "native-c-treewalk",
    "native-c-compiler-vm",
    "python-p0-compiler-vm",
    "lisp-lcc",
)
CASES = (
    "assoc-finite-dotted-tail",
    "assoc-finite-malformed-entry",
    "count-library-dotted-tail",
    "filter-finite-dotted-tail",
    "find-finite-dotted-tail",
    "member-finite-dotted-tail",
    "nth-negative-index",
    "nth-non-fixnum-index",
    "nthcdr-negative-index",
    "nthcdr-non-fixnum-index",
    "position-library-dotted-tail",
)
SOURCES = (
    "config/bytecode-abi-ledger.json",
    "config/error-code-contract.json",
    "config/error-texts.json",
    "lib/dialect-v2/lists-core.lisp",
    "lib/dialect-v2/lists-library.lisp",
    "lib/dialect-v2/lcc-profile.lisp",
    "scripts/equivalence-main.c",
    "src/compile.c",
    "src/error_codes.h",
    "src/eval.c",
    "src/vm.c",
    "tests/bytecode/dialect-v2/lists/cases.json",
    "tools/host-lisp/bytecode_p0.py",
    "tools/host-lisp/bytecode_p0_compiler.py",
    "tools/host-lisp/dialect_v2_lists_p0.py",
    "tools/host-lisp/dialect_v2_lists_type_errors.py",
)


class EvidenceError(RuntimeError):
    pass


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceError(f"{path}: root is not an object")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def binding(relative: str) -> dict[str, str]:
    path = ROOT / relative
    if path.is_symlink() or not path.is_file():
        raise EvidenceError(f"missing regular evidence input: {relative}")
    return {"path": relative, "sha256": sha(path)}


def build_report() -> dict[str, Any]:
    fixture = load(FIXTURE)
    if fixture.get("format") != "lisp65-dialect-v2-lists-cases-v1":
        raise EvidenceError("lists fixture identity drift")
    by_id = {case.get("id"): case for case in fixture.get("cases", [])}
    if tuple(sorted(case_id for case_id in CASES if case_id in by_id)) != tuple(sorted(CASES)):
        raise EvidenceError("malformed-case inventory is incomplete")
    for case_id in CASES:
        observed = by_id[case_id].get("observations", {}).get("dialect-v2", {})
        if observed != {engine: "!error:runtime" for engine in ENGINES}:
            raise EvidenceError(f"{case_id}: dialect-v2 type-error oracle drift")

    expected_result_sha = hashlib.sha256(b"!error:runtime").hexdigest()
    engine_results = []
    for engine in ENGINES:
        verdict_path = BUILD / f"dialect-v2-{engine}-verdict.json"
        verdict = load(verdict_path)
        if (
            verdict.get("format") != "lisp65-dialect-v2-family-verdict-v1"
            or verdict.get("family") != "lists"
            or verdict.get("profile") != "dialect-v2"
            or verdict.get("engine") != engine
            or verdict.get("fixture_sha256") != sha(FIXTURE)
        ):
            raise EvidenceError(f"{engine}: verdict identity drift")
        verdict_cases = {case.get("id"): case for case in verdict.get("cases", [])}
        if len(verdict_cases) != len(fixture["cases"]):
            raise EvidenceError(f"{engine}: verdict case coverage drift")
        for case in verdict_cases.values():
            if case.get("verdict") != "accept":
                raise EvidenceError(f"{engine}: rejected case {case.get('id')}")
        for case_id in CASES:
            if verdict_cases[case_id].get("result_sha256") != expected_result_sha:
                raise EvidenceError(f"{engine}/{case_id}: result binding drift")
        provenance = verdict.get("provenance", {})
        engine_results.append(
            {
                "engine": engine,
                "verdict_sha256": sha(verdict_path),
                "binary_sha256": provenance.get("binary_sha256"),
                "build_profile_sha256": provenance.get("build_profile_sha256"),
                "accepted_cases": len(verdict_cases),
                "malformed_cases": list(CASES),
                "result_sha256": expected_result_sha,
            }
        )

    return {
        "format": "lisp65-dialect-v2-lists-type-errors-g2-v1",
        "gate": "G2",
        "result": "passed",
        "public_error_channel": {
            "error_code": 38,
            "c_name": "LISP65_ERR_VM_TYPE",
            "text": "vm: type error",
            "internal_prim_id": 58,
            "internal_prim_name": "%list-malformed-error",
            "public_surface_added": False,
        },
        "fixture_sha256": sha(FIXTURE),
        "case_count": len(fixture["cases"]),
        "observation_count": len(fixture["cases"]) * 2 * len(ENGINES),
        "malformed_case_ids": list(CASES),
        "engine_results": engine_results,
        "source_bindings": [binding(relative) for relative in SOURCES],
    }


def canonical(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("emit", "check"))
    args = parser.parse_args()
    expected = canonical(build_report()) if args.command == "emit" else None
    if args.command == "emit":
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(expected, encoding="utf-8")
    else:
        report = load(OUTPUT)
        if report.get("format") != "lisp65-dialect-v2-lists-type-errors-g2-v1":
            raise EvidenceError("sealed report identity drift")
        for item in report.get("source_bindings", []):
            if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
                raise EvidenceError("sealed report source binding shape drift")
            if (
                not isinstance(item["path"], str)
                or not isinstance(item["sha256"], str)
                or len(item["sha256"]) != 64
            ):
                raise EvidenceError("sealed report source binding value drift")
        receipt = load(BLOCK_RECEIPT)
        evidence = receipt.get("evidence")
        expected_binding = {"path": relative(OUTPUT), "sha256": sha(OUTPUT)}
        if (
            receipt.get("format") != "lisp65-architecture-block-receipt-v1"
            or receipt.get("block_id") != "lists-malformed-type-errors"
            or receipt.get("result") != "passed"
            or not isinstance(evidence, list)
            or expected_binding not in evidence
        ):
            raise EvidenceError("sealed report block-receipt binding drift")
    print(
        "dialect-v2-lists-type-errors: PASS "
        f"mode={args.command} cases={len(CASES)} engines={len(ENGINES)}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as exc:
        print(f"dialect-v2-lists-type-errors: FAIL {exc}")
        raise SystemExit(1)
