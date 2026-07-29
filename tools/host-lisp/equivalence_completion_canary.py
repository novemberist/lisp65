#!/usr/bin/env python3
"""Prove that every equivalence lane executed its pinned positive case count."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parents[2]
FORMAT = "lisp65-equivalence-completion-v2"
EXPECTED = [
    ("control-sf-parity", 99),
    ("disk-macro-parity", 99),
    ("case-parity", 6),
    ("macro-only-semantics", 3),
    ("lcc-byte-oracle", 100),
    ("quote-emission-parity", 5),
    ("c2d-v6-session-execution", 2),
    ("lcc-execution-parity", 50),
    ("macro-lcc-parity", 25),
    ("lcc-fixed-point", 8),
    ("lcc-first-repl", 50),
]
AUTHORITIES = [
    ROOT / "scripts/equivalence-check.sh",
    ROOT / "scripts/equivalence-main.c",
    ROOT / "scripts/c2-equivalence-overlay-model.c",
    ROOT / "tools/host-lisp/equivalence_completion_canary.py",
    ROOT / "tools/host-lisp/c2_product_session_host.py",
    ROOT / "tests/equivalence/c2-product-session-cross-entry.json",
    ROOT / "tests/equivalence/c2-product-session-prim68-overlay.lisp",
    ROOT / "src/eval.c",
    ROOT / "src/vm.c",
    ROOT / "src/intern_service_overlay.c",
]


class CanaryError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CanaryError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def read_journal(path: Path) -> list[dict[str, int | str]]:
    require(path.is_file(), f"missing lane journal: {path}")
    lanes: list[dict[str, int | str]] = []
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        columns = raw.split("\t")
        require(
            len(columns) == 3 and all(columns),
            f"lane journal row {number} is not name/actual/expected TSV",
        )
        name, actual_raw, expected_raw = columns
        try:
            actual = int(actual_raw, 10)
            expected = int(expected_raw, 10)
        except ValueError as error:
            raise CanaryError(
                f"lane journal row {number} has a nonnumeric witness"
            ) from error
        lanes.append({
            "name": name,
            "executed_cases": actual,
            "expected_cases": expected,
        })
    return lanes


def validate_lanes(lanes: list[dict[str, int | str]]) -> None:
    expected_rows = [
        {
            "name": name,
            "executed_cases": count,
            "expected_cases": count,
        }
        for name, count in EXPECTED
    ]
    require(
        lanes == expected_rows,
        "equivalence lanes incomplete, unexecuted, miscounted or out of order: "
        f"expected={expected_rows!r} actual={lanes!r}",
    )
    require(
        all(int(row["executed_cases"]) > 0 for row in lanes),
        "a permanent equivalence lane has no positive execution witness",
    )


def finalize(journal: Path, receipt: Path, status: int) -> dict[str, object]:
    lanes = read_journal(journal)
    validate_lanes(lanes)
    require(status == 0, f"equivalence chain ended red: status={status}")
    value: dict[str, object] = {
        "format": FORMAT,
        "status": "passed-complete-chain",
        "lane_count": len(lanes),
        "executed_case_count": sum(
            int(row["executed_cases"]) for row in lanes),
        "lanes": lanes,
        "journal": binding(journal),
        "authority": {
            path.relative_to(ROOT).as_posix(): binding(path)
            for path in AUTHORITIES
        },
    }
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return value


def check(receipt: Path) -> dict[str, object]:
    require(receipt.is_file(), f"missing equivalence completion receipt: {receipt}")
    value = json.loads(receipt.read_text(encoding="utf-8"))
    require(
        value.get("format") == FORMAT
        and value.get("status") == "passed-complete-chain",
        "equivalence completion receipt format/status drift",
    )
    lanes = value.get("lanes")
    require(isinstance(lanes, list), "receipt lanes are not a list")
    validate_lanes(lanes)
    require(value.get("lane_count") == len(EXPECTED), "lane count drift")
    require(
        value.get("executed_case_count") == sum(count for _, count in EXPECTED),
        "total positive execution witness drift",
    )
    authority = value.get("authority")
    require(isinstance(authority, dict), "receipt authority is absent")
    for path in AUTHORITIES:
        name = path.relative_to(ROOT).as_posix()
        require(
            authority.get(name) == binding(path),
            f"stale equivalence completion authority: {name}",
        )
    return value


def selftest() -> None:
    rows = [
        {
            "name": name,
            "executed_cases": count,
            "expected_cases": count,
        }
        for name, count in EXPECTED
    ]
    validate_lanes(list(rows))
    mutations = {
        "missing-final-lane": rows[:-1],
        "missing-middle-lane": rows[:5] + rows[6:],
        "reordered-lanes": rows[:3] + [rows[4], rows[3]] + rows[5:],
        "extra-lane": rows + [{
            "name": "unregistered-lane",
            "executed_cases": 1,
            "expected_cases": 1,
        }],
        "zero-execution": [
            ({**row, "executed_cases": 0} if index == 5 else row)
            for index, row in enumerate(rows)
        ],
        "short-execution": [
            ({**row, "executed_cases": int(row["expected_cases"]) - 1}
             if index == 4 else row)
            for index, row in enumerate(rows)
        ],
        "self-reported-expectation": [
            ({**row, "executed_cases": 99, "expected_cases": 99}
             if index == 4 else row)
            for index, row in enumerate(rows)
        ],
    }
    for label, lanes in mutations.items():
        try:
            validate_lanes(lanes)
        except CanaryError:
            continue
        raise CanaryError(f"canary mutation survived: {label}")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        journal = root / "lanes"
        receipt = root / "receipt.json"
        journal.write_text(
            "".join(
                f"{name}\t{count}\t{count}\n"
                for name, count in EXPECTED
            ),
            encoding="utf-8",
        )
        try:
            finalize(journal, receipt, 1)
        except CanaryError:
            pass
        else:
            raise CanaryError("red-status mutation survived")
    print("equivalence-completion-canary: PASS mutations=8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    finish = sub.add_parser("finalize")
    finish.add_argument("--journal", type=Path, required=True)
    finish.add_argument("--receipt", type=Path, required=True)
    finish.add_argument("--status", type=int, required=True)
    verify = sub.add_parser("check")
    verify.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "selftest":
            selftest()
        elif args.command == "finalize":
            value = finalize(args.journal.resolve(), args.receipt.resolve(), args.status)
            print(
                "equivalence-completion-canary: COMPLETE "
                f"lanes={value['lane_count']} "
                f"executed={value['executed_case_count']} "
                f"receipt={args.receipt}"
            )
        else:
            value = check(args.receipt.resolve())
            print(
                "equivalence-completion-canary: PASS "
                f"lanes={value['lane_count']} "
                f"executed={value['executed_case_count']}"
            )
    except (CanaryError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"equivalence-completion-canary: FIRST RED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
