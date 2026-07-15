#!/usr/bin/env python3
"""Audit the exact private-inline eligibility of IDE/IDEX/M65D helpers."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

import bytecode_p0_stdlib as Stdlib


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/capability-carrier/"
    "workbench-private-inline-composition-probe.json"
)
SUITES = {
    "m65d": {
        "path": ROOT / "tests/bytecode/libs/p0-m65d-lib.json",
        "existing_private": 13,
        "candidates": [
            "%m65d-set", "%m65d-mask", "%m65d-bitmap-off",
            "%m65d-bit-free-p", "%m65d-bam-header-ok-p",
            "%m65d-entry-valid-p", "%m65d-dir-scan",
            "%m65d-check-old-half", "%m65d-clear", "%m65d-copy",
            "%m65d-claim-new",
            "%m65d-dir-target-ok-p", "%m65d-dir-fill",
            "%m65d-commit-dir", "%m65d-old-validated",
            "%m65d-write-plan", "%m65d-run-record",
        ],
        "expected": {
            "rel8": 14,
            "code-object": 1,
            "recursive": 1,
            "unexpected": 0,
            "passed": 1,
        },
        "eligible_but_not_applied": ["%m65d-dir-target-ok-p"],
    },
    "idex": {
        "path": ROOT / "tests/bytecode/libs/p0-ide-extra-lib.json",
        "existing_private": 8,
        "candidates": [
            "%ide-buffer-with-mark", "%ide-kill-region-lines",
            "%ide-apply-word-edit-command", "%ide-apply-region-command",
            "%ide-apply-page-command", "%ide-apply-rare-edit-command",
            "%ide-mini-search-submit", "%ide-execute-command-submit",
        ],
        "expected": {
            "rel8": 5,
            "code-object": 3,
            "recursive": 0,
            "unexpected": 0,
            "passed": 0,
        },
        "eligible_but_not_applied": [],
    },
}


class ProbeError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(message: str) -> str:
    if "branch offset out of rel8 range" in message:
        return "rel8"
    if "code object" in message and "exceeds max_code_object_bytes 255" in message:
        return "code-object"
    if "private inline recursion" in message:
        return "recursive"
    return "unexpected"


def render() -> dict[str, object]:
    suites: list[dict[str, object]] = []
    total = 0
    for suite_id, spec in SUITES.items():
        path = spec["path"]
        suite = Stdlib._read_suite(str(path))
        private = suite.get("private_inline_functions", [])
        if len(private) != spec["existing_private"]:
            raise ProbeError(f"{suite_id} existing private-inline count drift")
        results: list[dict[str, str]] = []
        counts = {
            "rel8": 0,
            "code-object": 0,
            "recursive": 0,
            "unexpected": 0,
            "passed": 0,
        }
        for candidate in spec["candidates"]:
            probe = copy.deepcopy(suite)
            probe["private_inline_functions"].append(candidate)
            probe["min_private_inline_functions"] += 1
            try:
                Stdlib.check_suite(str(path), probe)
            except Exception as exc:  # The exact compiler rejection is the evidence.
                message = str(exc)
                outcome = classify(message)
                counts[outcome] += 1
                results.append({
                    "candidate": candidate,
                    "outcome": outcome,
                    "diagnostic": message,
                })
            else:
                counts["passed"] += 1
                results.append({
                    "candidate": candidate,
                    "outcome": "passed",
                    "diagnostic": "candidate unexpectedly became private-inline eligible",
                })
        expected = spec["expected"]
        eligible = [
            item["candidate"] for item in results if item["outcome"] == "passed"
        ]
        if counts != expected or eligible != spec["eligible_but_not_applied"]:
            raise ProbeError(f"{suite_id} rejection distribution drift: {counts}")
        total += len(results)
        suites.append({
            "id": suite_id,
            "suite": path.relative_to(ROOT).as_posix(),
            "suite_sha256": sha256(path),
            "existing_private_inline_functions": len(private),
            "additional_candidates": len(results),
            "rejections": counts,
            "eligible_but_not_applied": eligible,
            "results": results,
        })
    return {
        "format": "lisp65-workbench-private-inline-composition-probe-v1",
        "status": "passed-pinned-private-inline-eligibility",
        "method": "each-candidate-added-individually-to-the-real-suite-and-fully-compiled",
        "candidate_count": total,
        "additional_private_symbols_reclaimed": 0,
        "eligible_but_not_applied": ["m65d:%m65d-dir-target-ok-p"],
        "suites": suites,
        "decision": "defer-incidental-single-symbol-reclaim-product-identity-stable",
    }


def write_receipt(path: Path) -> None:
    value = render()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    print(f"workbench-private-inline-probe: WROTE candidates={value['candidate_count']} path={path}")


def check_receipt(path: Path) -> None:
    try:
        actual = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProbeError(f"cannot read receipt: {exc}") from exc
    expected = render()
    if actual != expected:
        raise ProbeError("receipt drift")
    print(
        "workbench-private-inline-probe: PASS "
        f"candidates={expected['candidate_count']} reclaimed=0"
    )


def selftest() -> None:
    if set(SUITES) != {"m65d", "idex"}:
        raise ProbeError("suite inventory drift")
    candidates = [
        name for spec in SUITES.values() for name in spec["candidates"]
    ]
    if len(candidates) != 25 or len(set(candidates)) != 25:
        raise ProbeError("candidate inventory must contain 25 unique names")
    if SUITES["m65d"]["eligible_but_not_applied"] != ["%m65d-dir-target-ok-p"]:
        raise ProbeError("deferred eligible candidate drift")
    if SUITES["idex"]["eligible_but_not_applied"]:
        raise ProbeError("IDEX deferred eligible candidate drift")
    if classify("branch offset out of rel8 range in if: 129") != "rel8":
        raise ProbeError("rel8 classifier drift")
    if classify("x: code object 300 B exceeds max_code_object_bytes 255") != "code-object":
        raise ProbeError("code-object classifier drift")
    if classify("private inline recursion: x -> x") != "recursive":
        raise ProbeError("recursive classifier drift")
    if classify("other") != "unexpected":
        raise ProbeError("unexpected classifier drift")
    print("workbench-private-inline-probe: SELFTEST PASS cases=5 candidates=25")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate", "check", "selftest"))
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args(argv)
    receipt = args.receipt if args.receipt.is_absolute() else ROOT / args.receipt
    try:
        if args.command == "selftest":
            selftest()
        elif args.command == "generate":
            write_receipt(receipt)
        else:
            check_receipt(receipt)
    except (ProbeError, KeyError, TypeError, ValueError) as exc:
        print(f"workbench-private-inline-probe: FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
