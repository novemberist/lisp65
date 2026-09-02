#!/usr/bin/env python3
"""Measure and validate one complete ``make check-source`` execution."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
FORMAT = "lisp65-check-source-runtime-v1"
TIER_FORMAT = "lisp65-check-source-tiers-v1"
START_RE = re.compile(r"^\s*Must remake target '([^']+)'\.$")
PASS_RE = re.compile(r"^\s*Successfully remade target file '([^']+)'\.$")
FAIL_RE = re.compile(r"^\s*Failed to remake target file '([^']+)'\.$")


class MeasurementError(RuntimeError):
    """A measurement or receipt is structurally incomplete."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
    ).strip()


def direct_prerequisites() -> list[str]:
    result = subprocess.run(
        ["make", "-npRrq", ":"], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    for line in result.stdout.splitlines():
        if line.startswith("check-source:"):
            values = line.partition(":")[2].split()
            return list(dict.fromkeys(item for item in values if item != ".WAIT"))
    raise MeasurementError("make database has no check-source target")


def parse_event(
    line: str, elapsed_ns: int, active: dict[str, list[int]],
    rows: list[dict[str, object]],
) -> None:
    start = START_RE.match(line)
    if start:
        active.setdefault(start.group(1), []).append(elapsed_ns)
        return
    end = PASS_RE.match(line) or FAIL_RE.match(line)
    if not end:
        return
    target = end.group(1)
    starts = active.get(target)
    if not starts:
        raise MeasurementError(f"completion without start: {target}")
    started_ns = starts.pop()
    if not starts:
        active.pop(target)
    rows.append({
        "target": target,
        "elapsed_ms": round((elapsed_ns - started_ns) / 1_000_000, 3),
        "result": "passed" if PASS_RE.match(line) else "failed",
    })


def aggregate(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    values: dict[str, dict[str, object]] = {}
    for row in rows:
        target = str(row["target"])
        item = values.setdefault(target, {
            "target": target, "invocations": 0, "elapsed_ms": 0.0,
            "max_ms": 0.0, "results": [],
        })
        elapsed = float(row["elapsed_ms"])
        item["invocations"] = int(item["invocations"]) + 1
        item["elapsed_ms"] = round(float(item["elapsed_ms"]) + elapsed, 3)
        item["max_ms"] = max(float(item["max_ms"]), elapsed)
        cast_results = item["results"]
        assert isinstance(cast_results, list)
        cast_results.append(row["result"])
    return sorted(values.values(), key=lambda item: (-float(item["elapsed_ms"]), str(item["target"])))


def measure(output: Path, log: Path) -> int:
    prerequisites = direct_prerequisites()
    output = output.resolve()
    log = log.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    started_wall = time.time()
    started_ns = time.monotonic_ns()
    active: dict[str, list[int]] = {}
    rows: list[dict[str, object]] = []
    error: str | None = None
    command = ["make", "--no-print-directory", "--debug=v", "-k", "check-source"]
    with log.open("w", encoding="utf-8") as raw:
        process = subprocess.Popen(
            command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            elapsed_ns = time.monotonic_ns() - started_ns
            raw.write(f"{elapsed_ns}\t{line}")
            try:
                parse_event(line.rstrip("\n"), elapsed_ns, active, rows)
            except MeasurementError as exception:
                error = str(exception)
        returncode = process.wait()
    finished_ns = time.monotonic_ns()
    ranking = aggregate(rows)
    observed = {str(row["target"]) for row in rows}
    missing = sorted(set(prerequisites) - observed)
    incomplete = sorted(active)
    failed = sorted({str(row["target"]) for row in rows if row["result"] != "passed"})
    status = "passed" if not (returncode or error or missing or incomplete or failed) else "failed"
    receipt = {
        "format": FORMAT,
        "version": 1,
        "status": status,
        "source": {
            "head": git("rev-parse", "HEAD"),
            "tree": git("rev-parse", "HEAD^{tree}"),
            "tracked_tree_clean": not bool(git("status", "--short", "--untracked-files=no")),
        },
        "measurement": {
            "command": command,
            "started_unix": round(started_wall, 6),
            "wall_ms": round((finished_ns - started_ns) / 1_000_000, 3),
            "returncode": returncode,
            "raw_log_bytes": log.stat().st_size,
            "raw_log_sha256": sha256(log),
            "executed_target_instances": len(rows),
            "ranked_targets": len(ranking),
        },
        "coverage": {
            "direct_prerequisites": prerequisites,
            "direct_prerequisite_count": len(prerequisites),
            "missing_direct_prerequisites": missing,
            "incomplete_targets": incomplete,
            "failed_targets": failed,
            "parse_error": error,
        },
        "ranking": ranking,
        "claim_limit": "One host-only full check-source runtime measurement; no product bytes, link, media, device or acceptance claim.",
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"check-source runtime: {status.upper()} wall={receipt['measurement']['wall_ms']}ms "
        f"targets={len(ranking)} direct={len(prerequisites)} missing={len(missing)}"
    )
    return 0 if status == "passed" else 1


def validate(receipt: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if receipt.get("format") != FORMAT or receipt.get("version") != 1:
        errors.append("receipt identity mismatch")
    if receipt.get("status") != "passed":
        errors.append("measurement did not pass")
    measurement = receipt.get("measurement")
    source = receipt.get("source")
    coverage = receipt.get("coverage")
    ranking = receipt.get("ranking")
    if not isinstance(source, dict):
        errors.append("missing source identity")
    else:
        if source.get("tracked_tree_clean") is not True:
            errors.append("measurement source was not a clean tracked tree")
        for key in ("head", "tree"):
            value = source.get(key)
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
                errors.append(f"invalid source {key}")
    if not isinstance(measurement, dict) or float(measurement.get("wall_ms", 0)) <= 0:
        errors.append("missing positive wall time")
    else:
        if measurement.get("command") != [
            "make", "--no-print-directory", "--debug=v", "-k", "check-source"
        ]:
            errors.append("measurement command drift")
        if measurement.get("returncode") != 0:
            errors.append("measurement return code is not zero")
        if not isinstance(measurement.get("raw_log_bytes"), int) or measurement["raw_log_bytes"] <= 0:
            errors.append("missing raw-log byte count")
        digest = measurement.get("raw_log_sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            errors.append("invalid raw-log digest")
    if not isinstance(coverage, dict):
        errors.append("missing coverage")
    else:
        for key in ("missing_direct_prerequisites", "incomplete_targets", "failed_targets"):
            if coverage.get(key) != []:
                errors.append(f"coverage is not closed: {key}")
        direct = coverage.get("direct_prerequisites")
        if not isinstance(direct, list) or len(direct) != coverage.get("direct_prerequisite_count"):
            errors.append("direct-prerequisite inventory mismatch")
    if not isinstance(ranking, list) or not ranking:
        errors.append("empty ranking")
    elif ranking != sorted(ranking, key=lambda item: (-float(item["elapsed_ms"]), str(item["target"]))):
        errors.append("ranking order mismatch")
    elif isinstance(measurement, dict):
        if measurement.get("ranked_targets") != len(ranking):
            errors.append("ranked-target count mismatch")
        instances = sum(int(item.get("invocations", 0)) for item in ranking)
        if measurement.get("executed_target_instances") != instances:
            errors.append("executed-target count mismatch")
    return errors


def validate_tiers(receipt: dict[str, object], tiers: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if tiers.get("format") != TIER_FORMAT or tiers.get("version") != 1:
        errors.append("tier identity mismatch")
    policy = tiers.get("policy")
    if not isinstance(policy, dict):
        return errors + ["missing tier policy"]
    threshold = policy.get("complete_only_threshold_ms")
    selected = policy.get("complete_only_targets")
    if not isinstance(threshold, (int, float)) or threshold <= 0:
        errors.append("invalid complete-only threshold")
        return errors
    if not isinstance(selected, list) or not all(isinstance(item, str) for item in selected):
        errors.append("invalid complete-only target list")
        return errors
    coverage = receipt.get("coverage")
    ranking = receipt.get("ranking")
    if not isinstance(coverage, dict) or not isinstance(ranking, list):
        return errors + ["measurement cannot support tier policy"]
    direct = set(coverage.get("direct_prerequisites", []))
    expected = [
        str(item["target"]) for item in ranking
        if item.get("target") in direct and float(item.get("elapsed_ms", 0)) >= threshold
    ]
    if selected != expected:
        errors.append("complete-only targets are not the measured threshold set")
    if len(selected) != len(set(selected)):
        errors.append("duplicate complete-only target")
    if policy.get("closing_certification_target") != "check-source":
        errors.append("complete check-source is not the closing certification")
    if policy.get("inner_loop_is_certification") is not False:
        errors.append("inner loop must explicitly carry no certification claim")
    return errors


def run_inner(receipt_path: Path, tiers_path: Path) -> int:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    tiers = json.loads(tiers_path.read_text(encoding="utf-8"))
    errors = validate(receipt) + validate_tiers(receipt, tiers)
    if errors:
        raise MeasurementError("; ".join(errors))
    policy = tiers["policy"]
    assert isinstance(policy, dict)
    selected = policy["complete_only_targets"]
    assert isinstance(selected, list)
    live = direct_prerequisites()
    missing = sorted(set(selected) - set(live))
    if missing:
        raise MeasurementError("complete-only target left live check-source: " + ", ".join(missing))
    print(
        "check-source inner: NON-CERTIFYING complete-only="
        + ",".join(str(item) for item in selected)
    )
    command = ["make", "--no-print-directory", "-k"]
    for target in selected:
        command.extend(("-o", str(target)))
    command.append("check-source")
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def selftest() -> int:
    active: dict[str, list[int]] = {}
    rows: list[dict[str, object]] = []
    parse_event(" Must remake target 'slow-check'.", 10, active, rows)
    parse_event(" Successfully remade target file 'slow-check'.", 2_000_010, active, rows)
    if rows != [{"target": "slow-check", "elapsed_ms": 2.0, "result": "passed"}] or active:
        raise MeasurementError("valid debug pair was not measured")
    mutations = 0
    for lines in (
        [" Successfully remade target file 'orphan'."],
        [" Must remake target 'unfinished'."],
        [" Must remake target 'red'.", " Failed to remake target file 'red'."],
    ):
        local_active: dict[str, list[int]] = {}
        local_rows: list[dict[str, object]] = []
        rejected = False
        try:
            for index, line in enumerate(lines):
                parse_event(line, index + 1, local_active, local_rows)
            rejected = bool(local_active) or any(row["result"] != "passed" for row in local_rows)
        except MeasurementError:
            rejected = True
        if not rejected:
            raise MeasurementError("runtime mutation was not rejected")
        mutations += 1
    synthetic_receipt = {
        "format": FORMAT, "version": 1, "status": "passed",
        "source": {
            "head": "a" * 40, "tree": "b" * 40, "tracked_tree_clean": True,
        },
        "measurement": {
            "wall_ms": 20.0,
            "command": ["make", "--no-print-directory", "--debug=v", "-k", "check-source"],
            "returncode": 0, "raw_log_bytes": 10, "raw_log_sha256": "c" * 64,
            "ranked_targets": 2, "executed_target_instances": 2,
        },
        "coverage": {
            "direct_prerequisites": ["slow", "fast"],
            "direct_prerequisite_count": 2,
            "missing_direct_prerequisites": [], "incomplete_targets": [],
            "failed_targets": [],
        },
        "ranking": [
            {"target": "slow", "elapsed_ms": 15.0, "invocations": 1},
            {"target": "fast", "elapsed_ms": 5.0, "invocations": 1},
        ],
    }
    if validate(synthetic_receipt):
        raise MeasurementError("valid synthetic measurement was rejected")
    synthetic_tiers = {
        "format": TIER_FORMAT, "version": 1,
        "policy": {
            "complete_only_threshold_ms": 10.0,
            "complete_only_targets": ["slow"],
            "closing_certification_target": "check-source",
            "inner_loop_is_certification": False,
        },
    }
    if validate_tiers(synthetic_receipt, synthetic_tiers):
        raise MeasurementError("valid tier policy was rejected")
    for key, value in (
        ("complete_only_targets", []),
        ("complete_only_targets", ["slow", "unknown"]),
        ("inner_loop_is_certification", True),
    ):
        mutated = json.loads(json.dumps(synthetic_tiers))
        mutated["policy"][key] = value
        if not validate_tiers(synthetic_receipt, mutated):
            raise MeasurementError(f"tier mutation was not rejected: {key}")
        mutations += 1
    for scope, key, value in (
        ("source", "tracked_tree_clean", False),
        ("measurement", "returncode", 1),
        ("measurement", "ranked_targets", 1),
    ):
        mutated = json.loads(json.dumps(synthetic_receipt))
        mutated[scope][key] = value
        if not validate(mutated):
            raise MeasurementError(f"measurement mutation was not rejected: {key}")
        mutations += 1
    print(f"check-source runtime: SELFTEST PASS mutations={mutations}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    measurement = subparsers.add_parser("measure")
    measurement.add_argument("--output", required=True, type=Path)
    measurement.add_argument("--log", required=True, type=Path)
    check = subparsers.add_parser("check")
    check.add_argument("receipt", type=Path)
    check.add_argument("--tiers", type=Path)
    inner = subparsers.add_parser("inner")
    inner.add_argument("--receipt", required=True, type=Path)
    inner.add_argument("--tiers", required=True, type=Path)
    subparsers.add_parser("selftest")
    args = parser.parse_args()
    try:
        if args.command == "measure":
            return measure(args.output, args.log)
        if args.command == "selftest":
            return selftest()
        if args.command == "inner":
            return run_inner(args.receipt, args.tiers)
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        errors = validate(receipt)
        if args.tiers is not None:
            tiers = json.loads(args.tiers.read_text(encoding="utf-8"))
            errors.extend(validate_tiers(receipt, tiers))
        if errors:
            raise MeasurementError("; ".join(errors))
        print(
            f"check-source runtime: CHECK PASS wall={receipt['measurement']['wall_ms']}ms "
            f"targets={receipt['measurement']['ranked_targets']}"
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError, MeasurementError) as exception:
        print(f"check-source runtime: FAIL: {exception}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
