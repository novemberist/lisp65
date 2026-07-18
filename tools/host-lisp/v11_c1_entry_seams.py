#!/usr/bin/env python3
"""Validate and materialize the owner-bound C1 hardware entry-seam cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/v11-c1-entry-seams.json"
DECISION = ROOT / "config/v11-c1-architecture-decision.json"
FORMAT = "lisp65-v11-c1-entry-seam-contract-v1"
SAFE_ID = re.compile(r"^[a-z][a-z0-9-]*$")


class SeamError(RuntimeError):
    pass


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SeamError(f"not an object: {path}")
    return value


def validate(contract: dict[str, Any], decision: dict[str, Any]) -> list[dict[str, Any]]:
    if (
        contract.get("format") != FORMAT
        or contract.get("version") != 1
        or contract.get("id") != "v11-c1-public-entry-seams"
        or contract.get("decision") != DECISION.relative_to(ROOT).as_posix()
    ):
        raise SeamError("C1 entry-seam contract identity drift")
    reopening = decision.get("reopening")
    if not isinstance(reopening, dict) or reopening.get("status") != "owner-approved":
        raise SeamError("C1 reopening is not owner-approved")
    if reopening.get("entry_seam_contract") != CONTRACT.relative_to(ROOT).as_posix():
        raise SeamError("C1 decision does not bind the entry-seam contract")
    required = reopening.get("hardware_entry_seams")
    cases = contract.get("cases")
    if not isinstance(required, list) or not isinstance(cases, list) or not cases:
        raise SeamError("C1 entry-seam lists are missing")
    ids: list[str] = []
    entries: list[str] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or set(case) != {"id", "entry", "expect", "forms"}:
            raise SeamError(f"case[{index}] shape drift")
        case_id = case["id"]
        entry = case["entry"]
        expect = case["expect"]
        forms = case["forms"]
        if (
            not isinstance(case_id, str) or not SAFE_ID.fullmatch(case_id)
            or not isinstance(entry, str) or not entry
            or not isinstance(expect, str) or not expect or "\t" in expect or "\n" in expect
            or not isinstance(forms, list) or len(forms) < 2
            or any(not isinstance(form, str) or not form or "\n" in form for form in forms)
        ):
            raise SeamError(f"case[{index}] value drift")
        if not any(f"({entry}" in form for form in forms):
            raise SeamError(f"case {case_id} never calls its named entry {entry}")
        if not any(expect.strip('"') in form for form in forms):
            raise SeamError(f"case {case_id} never emits its oracle")
        ids.append(case_id)
        entries.append(entry)
    if len(ids) != len(set(ids)) or len(entries) != len(set(entries)):
        raise SeamError("duplicate C1 entry-seam case")
    if entries != required:
        raise SeamError(f"case/decision seam parity drift: cases={entries} decision={required}")
    compile_case = next((case for case in cases if case["entry"] == "compile-string"), None)
    if compile_case is None:
        raise SeamError("compile-string entry-seam case is missing")
    compile_forms = compile_case["forms"]
    required_prefix = ['(load-lib "m65d")', "(m65d-remount)"]
    if compile_forms[:2] != required_prefix:
        raise SeamError(
            "compile-string entry seam must load M65D and establish its mount "
            "before invoking the transactional compiler path"
        )
    return cases


def emit(out_dir: Path) -> None:
    cases = validate(load(CONTRACT), load(DECISION))
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[str] = []
    for case in cases:
        forms = out_dir / f"{case['id']}.forms"
        forms.write_text("\n".join(case["forms"]) + "\n", encoding="utf-8")
        rows.append(f"{case['id']}\t{case['expect']}\t{forms}\n")
    (out_dir / "cases.tsv").write_text("".join(rows), encoding="utf-8")
    print(f"v11-c1-entry-seams: EMIT cases={len(cases)} out={out_dir}")


def selftest() -> None:
    contract = load(CONTRACT)
    decision = load(DECISION)
    validate(contract, decision)
    mutated = json.loads(json.dumps(contract))
    mutated["cases"].pop()
    try:
        validate(mutated, decision)
    except SeamError:
        pass
    else:
        raise SeamError("selftest accepted a missing public seam")
    mutated = json.loads(json.dumps(contract))
    mutated["cases"][0]["forms"] = ["(+ 1 2)", '"wrong"']
    try:
        validate(mutated, decision)
    except SeamError:
        pass
    else:
        raise SeamError("selftest accepted a case that never calls its seam")
    mutated = json.loads(json.dumps(contract))
    compile_case = next(case for case in mutated["cases"] if case["entry"] == "compile-string")
    compile_case["forms"].pop(1)
    try:
        validate(mutated, decision)
    except SeamError:
        pass
    else:
        raise SeamError("selftest accepted compile-string without the M65D mount precondition")
    with tempfile.TemporaryDirectory(prefix="lisp65-c1-seams-") as raw:
        emit(Path(raw))
    print("v11-c1-entry-seams: SELFTEST PASS mutations=3")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--emit", type=Path)
    args = parser.parse_args()
    try:
        if args.selftest:
            selftest()
        elif args.emit:
            emit(args.emit)
        else:
            cases = validate(load(CONTRACT), load(DECISION))
            print("v11-c1-entry-seams: PASS seams=" + ",".join(c["entry"] for c in cases))
    except (OSError, UnicodeError, json.JSONDecodeError, SeamError) as exc:
        print(f"v11-c1-entry-seams: FAIL {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
