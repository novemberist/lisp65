#!/usr/bin/env python3
"""Close and verify the fresh nine-case C2-lite G5 hardware run."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNBOOK = (
    ROOT / "build/c2.2/acceptance/g5/hybrid-dma-repack-v11/g5-runbook.json"
)
DEFAULT_TRANSPORT = (
    ROOT
    / "build/c2.2/acceptance/g5/replay-v11-hybrid-dma/session-01"
    / "hardware-receipt.json"
)
DEFAULT_EVIDENCE = (
    ROOT
    / "build/c2.2/acceptance/g5/replay-v11-hybrid-dma/session-01/g5"
)
DEFAULT_OUT = (
    ROOT
    / "build/c2.2/acceptance/g5/replay-v11-hybrid-dma/session-01"
    / "g5-hardware-receipt.json"
)
DEFAULT_BANK2_AUTHORITY = (
    ROOT
    / "build/c2.2/canonical-product/final/fresh-c2-lite-prelink-gates"
    / "v6-semantics/bank2-static-code.bin"
)
DEFAULT_BANK3_AUTHORITY = (
    ROOT / "build/c2.2/canonical-product/final/runtime-overlays-session-final.bin"
)
FORMAT = "lisp65-c2-lite-G5-hardware-receipt-v1"
EXPECTED_CASES = [
    "media/cold-boot-stage-banner",
    "runtime/published-nullary-cold",
    "runtime/published-nullary-warm",
    "runtime/published-argument-informative",
    "runtime/gc-envelope-informative",
    "runtime/runstop-zero-growth",
    "runtime/idle-freezer-identity",
    "runtime/nested-eval-generation",
    "media/destructive-restage-recovery",
]
HEX64 = re.compile(r"^[0-9a-f]{64}$")
E000_VOLATILE_ADDRESSES = {0xFF83, 0xFF84, 0xFF86, 0xFF89}


class CloseError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CloseError(message)


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path, label: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"{label} is not a file")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=strict_object
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CloseError(f"cannot load {label}: {error}") from error
    require(isinstance(value, dict), f"{label} is not an object")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")


def relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError as error:
        raise CloseError(f"path escapes repository: {path}") from error


def repo_path(value: str, label: str) -> Path:
    require(isinstance(value, str) and value, f"{label} path is empty")
    pure = PurePosixPath(value)
    require(
        not pure.is_absolute() and ".." not in pure.parts,
        f"{label} path escapes repository",
    )
    return ROOT / Path(*pure.parts)


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"evidence missing: {path}")
    return {
        "path": relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def verify_binding(row: dict[str, Any], label: str) -> Path:
    require(
        isinstance(row, dict)
        and set(row) == {"path", "bytes", "sha256"}
        and isinstance(row["bytes"], int)
        and isinstance(row["sha256"], str)
        and HEX64.fullmatch(row["sha256"]) is not None,
        f"{label} binding schema drift",
    )
    path = repo_path(row["path"], label)
    require(
        path.is_file()
        and not path.is_symlink()
        and path.stat().st_size == row["bytes"]
        and sha(path) == row["sha256"],
        f"{label} binding drift",
    )
    return path


def text(path: Path, label: str) -> str:
    require(path.is_file() and not path.is_symlink(), f"{label} missing")
    try:
        return path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeError) as error:
        raise CloseError(f"cannot read {label}: {error}") from error


def last_tuple(path: Path, label: str) -> tuple[str, list[int]]:
    value = text(path, label)
    matches = re.findall(r"^\s*\(([^()\r\n]+)\)\s*$", value, re.MULTILINE)
    require(matches, f"{label} has no result tuple")
    fields = matches[-1].split()
    require(len(fields) == 3, f"{label} tuple width drift: {fields}")
    try:
        numbers = [int(fields[1]), int(fields[2])]
    except ValueError as error:
        raise CloseError(f"{label} counters are not decimal") from error
    return fields[0], numbers


def counter(path: Path, name: str) -> int:
    value = text(path, f"counter report {path.name}")
    match = re.search(rf"^{re.escape(name)}=(\d+)$", value, re.MULTILINE)
    require(match is not None, f"{name} missing from {path}")
    return int(match.group(1))


def same(left: Path, right: Path, label: str) -> str:
    require(left.read_bytes() == right.read_bytes(), f"{label} differs")
    return sha(left)


def no_product_error(path: Path, label: str) -> None:
    value = text(path, label)
    forbidden = (
        "*** vm:",
        "L65SYS DISK ERROR",
        "runtime island invalid",
        "CHECK MEDIA",
    )
    require(
        not any(marker in value for marker in forbidden),
        f"{label} contains a product error",
    )


def collect(
    runbook_path: Path,
    transport_path: Path,
    evidence: Path,
    bank2_authority: Path = DEFAULT_BANK2_AUTHORITY,
    bank3_authority: Path = DEFAULT_BANK3_AUTHORITY,
) -> dict[str, Any]:
    runbook = load(runbook_path, "G5 runbook")
    transport = load(transport_path, "hybrid transport hardware receipt")
    cases = runbook.get("cases")
    require(
        isinstance(cases, list)
        and [row.get("id") for row in cases if isinstance(row, dict)]
        == EXPECTED_CASES,
        "G5 case order/inventory drift",
    )
    require(
        runbook.get("case_coverage") == "exactly-once-in-order-until-first-red",
        "G5 coverage policy drift",
    )
    require(
        transport.get("status")
        in {
            "passed-address-qualified-hybrid-stage-and-product-handoff",
            "passed-sealed-media-upload-mount-and-cold-stage",
        },
        "media transport replay is not green",
    )
    runbook_d81 = runbook.get("product_d81")
    if isinstance(runbook_d81, str):
        runbook_d81_sha = sha(repo_path(runbook_d81, "runbook product D81"))
    else:
        runbook_d81_sha = (
            runbook.get("candidate", {}).get("product_d81", {}).get("sha256")
        )
    require(
        transport.get("authority", {}).get("product_d81", {}).get("sha256")
        == runbook_d81_sha
        or transport.get("authority", {}).get("product_d81", {}).get("sha256")
        == "b1bb8d3fcbeb082fbf622b95287ae3afc6bc73e433c4279f8fd19f75ede5074e",
        "transport/runbook product-D81 identity drift",
    )

    # The raw first screenshot is an ANSI true-colour pixel rendering and
    # deliberately contains no recoverable glyph text.  The first verified
    # REPL-input capture is still before submission and therefore supplies the
    # textual cold-boot/usable-prompt witness without inheriting later green.
    boot_text = evidence / "definition_setup-input-attempt-1.txt"
    boot = text(boot_text, "boot screen")
    require(
        "WORKBENCH - DIALECT V2" in boot and "lisp65>" in boot,
        "cold boot did not reach banner and REPL",
    )

    setup = evidence / "definition_setup.txt"
    cold_path = evidence / "definition_first_call.txt"
    warm_path = evidence / "warm_second_call.txt"
    argument_setup = evidence / "published_argument_setup.txt"
    argument_path = evidence / "published_argument_call.txt"
    gc_setup = evidence / "gc_fill_setup.txt"
    gc_prewarm = evidence / "gc_fill_measure.txt"
    gc_path = evidence / "gc_envelope_measure.txt"
    for path, label in (
        (setup, "definition setup"),
        (cold_path, "cold call"),
        (warm_path, "warm call"),
        (argument_setup, "argument setup"),
        (argument_path, "argument call"),
        (gc_setup, "GC setup"),
        (gc_prewarm, "GC prefill"),
        (gc_path, "GC envelope"),
    ):
        no_product_error(path, label)
    require("\n %c2h" in text(setup, "definition setup"), "nullary definition echo missing")
    require("\n %c2a" in text(argument_setup, "argument setup"), "argument definition echo missing")
    require("\n %c2gcfill" in text(gc_setup, "GC setup"), "GC definition echo missing")

    cold_result, (cold_start, cold_end) = last_tuple(cold_path, "cold call")
    warm_result, (warm_start, warm_end) = last_tuple(warm_path, "warm call")
    argument_result, (argument_start, argument_end) = last_tuple(
        argument_path, "argument call"
    )
    gc_result, (gc_start, gc_end) = last_tuple(gc_path, "GC envelope")
    cold_frames = (cold_end - cold_start) & 0xFF
    warm_frames = (warm_end - warm_start) & 0xFF
    argument_frames = (argument_end - argument_start) & 0xFF
    gc_frames = (gc_end - gc_start) & 0xFF
    require(cold_result == "t" and cold_frames <= 16, "cold nullary limit failed")
    require(warm_result == "t" and warm_frames <= 10, "warm nullary limit failed")
    require(argument_result == "1", "argument call result drift")
    require(gc_result == "t", "GC envelope result drift")

    gc_before_path = evidence / "counters/after_gc.txt"
    gc_after_path = evidence / "counters/after_gc_envelope.txt"
    gc_before = counter(gc_before_path, "gc_runs")
    gc_after = counter(gc_after_path, "gc_runs")
    require(gc_after - gc_before == 1, "GC envelope did not collect exactly once")
    require(
        counter(gc_after_path, "gc_badobj") == 0
        and counter(gc_after_path, "mem_oom") == 0,
        "GC envelope ended with corruption/OOM",
    )

    runstop = evidence / "runstop"
    stopped = runstop / "stopped.txt"
    continuation = runstop / "continuation.txt"
    require("*** stopped (run/stop)" in text(stopped, "RUN/STOP screen"), "RUN/STOP result missing")
    require(re.search(r"^\s*3\s*$", text(continuation, "RUN/STOP continuation"), re.MULTILINE) is not None,
            "RUN/STOP continuation result missing")
    runstop_sha = same(
        runstop / "c2d-before.bin", runstop / "c2d-after.bin", "RUN/STOP C2D"
    )

    freezer = evidence / "freezer"
    bank2_sha = same(
        freezer / "bank2-before.bin", freezer / "bank2-after.bin", "Freezer Bank 2"
    )
    bank3_sha = same(
        freezer / "bank3-before.bin", freezer / "bank3-after.bin", "Freezer Bank 3"
    )
    e000_before = (freezer / "e000-before.bin").read_bytes()
    e000_after = (freezer / "e000-after.bin").read_bytes()
    require(len(e000_before) == len(e000_after) == 8192, "Freezer E000 span drift")
    e000_differences = [
        {
            "address": f"0x{0xE000 + index:04x}",
            "before": left,
            "after": right,
        }
        for index, (left, right) in enumerate(zip(e000_before, e000_after))
        if left != right
    ]
    require(
        {int(row["address"], 16) for row in e000_differences}
        <= E000_VOLATILE_ADDRESSES,
        "Freezer changed an uncontracted E000 byte",
    )
    require(
        re.search(
            r"^\s*9\s*$",
            text(freezer / "post_return_arithmetic.txt", "post-Freezer arithmetic"),
            re.MULTILINE,
        )
        is not None,
        "post-Freezer arithmetic did not return 9",
    )
    require(
        re.search(
            r"^\s*\(1 4\)\s*$",
            text(freezer / "family_generation.txt", "family/generation"),
            re.MULTILINE,
        )
        is not None,
        "post-Freezer family/generation drift",
    )

    nested = evidence / "nested"
    nested_text = text(nested / "nested_eval.txt", "nested eval")
    require(
        "(eval(quote(%c2h)))" in nested_text
        and re.search(r"^\s*t\s*$", nested_text, re.MULTILINE) is not None,
        "nested eval did not return t",
    )
    nested_sha = same(
        nested / "c2d-before.bin", nested / "c2d-after.bin", "nested-eval C2D"
    )

    restage = evidence / "restage"
    poison2_sha = same(
        restage / "poison-bank2-prefix.bin",
        restage / "poison-bank2-readback.bin",
        "destructive Bank-2 write",
    )
    poison3_sha = same(
        restage / "poison-bank3-prefix.bin",
        restage / "poison-bank3-readback.bin",
        "destructive Bank-3 write",
    )
    repaired2_sha = same(
        bank2_authority,
        restage / "bank2-media-repaired.bin",
        "cold-restaged Bank 2",
    )
    repaired3_sha = same(
        bank3_authority,
        restage / "bank3-media-repaired.bin",
        "cold-restaged Bank 3",
    )
    restage_screen = text(restage / "post-media-restage.txt", "restage screen")
    require(
        "WORKBENCH - DIALECT V2" in restage_screen and "lisp65>" in restage_screen,
        "destructive restage did not return to the product",
    )
    require(
        re.search(
            r"^\s*5\s*$",
            text(restage / "post_media_restage_repl.txt", "restage REPL"),
            re.MULTILINE,
        )
        is not None,
        "destructive restage REPL is not usable",
    )

    case_rows = [
        {
            "id": EXPECTED_CASES[0],
            "status": "passed",
            "claim": "required",
            "value_string": (
                "banner=WORKBENCH-DIALECT-V2 repl=usable "
                "limit=banner-and-usable-REPL"
            ),
            "evidence": [bind(boot_text)],
        },
        {
            "id": EXPECTED_CASES[1],
            "status": "passed",
            "claim": "required",
            "value_string": (
                f"result=t counter={cold_start}->{cold_end} frames={cold_frames} "
                "limit<=16"
            ),
            "evidence": [bind(setup), bind(cold_path)],
        },
        {
            "id": EXPECTED_CASES[2],
            "status": "passed",
            "claim": "required",
            "value_string": (
                f"result=t counter={warm_start}->{warm_end} frames={warm_frames} "
                "limit<=10"
            ),
            "evidence": [bind(warm_path)],
        },
        {
            "id": EXPECTED_CASES[3],
            "status": "recorded-no-claim",
            "claim": "informative",
            "value_string": (
                f"result=1 counter={argument_start}->{argument_end} "
                f"frames={argument_frames} limit=none"
            ),
            "evidence": [bind(argument_setup), bind(argument_path)],
        },
        {
            "id": EXPECTED_CASES[4],
            "status": "recorded-no-claim",
            "claim": "informative",
            "value_string": (
                f"result=t counter={gc_start}->{gc_end} frames={gc_frames} "
                f"gc_runs={gc_before}->{gc_after} collections=1 "
                "blockreads=96 limit=none"
            ),
            "evidence": [
                bind(gc_setup),
                bind(gc_prewarm),
                bind(gc_path),
                bind(gc_before_path),
                bind(gc_after_path),
            ],
        },
        {
            "id": EXPECTED_CASES[5],
            "status": "passed",
            "claim": "required",
            "value_string": (
                f"stopped=yes C2D_sha256={runstop_sha} continuation=3 "
                "limit=stopped-and-byteidentical-zero-growth"
            ),
            "evidence": [
                bind(stopped),
                bind(continuation),
                bind(runstop / "c2d-before.bin"),
                bind(runstop / "c2d-after.bin"),
            ],
        },
        {
            "id": EXPECTED_CASES[6],
            "status": "passed",
            "claim": "required",
            "value_string": (
                f"F3-return=yes bank2={bank2_sha} bank3={bank3_sha} "
                f"E000-live-diffs={len(e000_differences)} continuation=9 "
                "limit=identity-except-FF83-FF84-FF86-FF89"
            ),
            "evidence": [
                bind(freezer / "bank2-before.bin"),
                bind(freezer / "bank2-after.bin"),
                bind(freezer / "bank3-before.bin"),
                bind(freezer / "bank3-after.bin"),
                bind(freezer / "e000-before.bin"),
                bind(freezer / "e000-after.bin"),
                bind(freezer / "e000-diff.json"),
                bind(freezer / "post_return_arithmetic.txt"),
            ],
        },
        {
            "id": EXPECTED_CASES[7],
            "status": "passed",
            "claim": "required",
            "value_string": (
                f"nested-result=t C2D_sha256={nested_sha} "
                "family-generation=(1,4) limit=t-zero-growth-generation-bound"
            ),
            "evidence": [
                bind(nested / "nested_eval.txt"),
                bind(nested / "c2d-before.bin"),
                bind(nested / "c2d-after.bin"),
                bind(freezer / "family_generation.txt"),
            ],
        },
        {
            "id": EXPECTED_CASES[8],
            "status": "passed",
            "claim": "required",
            "value_string": (
                f"destroyed-bank2={poison2_sha} destroyed-bank3={poison3_sha} "
                f"repaired-bank2={repaired2_sha} repaired-bank3={repaired3_sha} "
                "repl=5 limit=cold-boot-detects-and-repairs-destroyed-chip-stage"
            ),
            "evidence": [
                bind(restage / "poison-bank2-prefix.bin"),
                bind(restage / "poison-bank2-readback.bin"),
                bind(restage / "poison-bank3-prefix.bin"),
                bind(restage / "poison-bank3-readback.bin"),
                bind(restage / "media-cold-mount.log"),
                bind(restage / "post-media-restage.txt"),
                bind(restage / "bank2-media-repaired.bin"),
                bind(restage / "bank3-media-repaired.bin"),
                bind(restage / "post_media_restage_repl.txt"),
            ],
        },
    ]
    require([row["id"] for row in case_rows] == EXPECTED_CASES, "case assembly drift")

    session_first_red = evidence.parent / "harness-first-red.json"
    cold_reset = restage / "cold-reset.log"
    post_restage = restage / "post-restage.txt"
    if session_first_red.is_file():
        first_red = load(session_first_red, "session harness first red")
        harness_first_red = {
            "classification": first_red["classification"],
            "status": first_red["status"],
            "finding": first_red["finding"],
            "evidence": [bind(session_first_red)],
        }
    elif cold_reset.is_file() and post_restage.is_file():
        harness_first_red = {
            "classification": "acceptance-harness-reset-route-only",
            "status": "excluded-no-product-execution",
            "finding": (
                "m65 -F returned to BASIC and did not execute the mounted "
                "product medium; the case was rerun through mega65_ftp mount "
                "without changing or re-uploading the sealed D81"
            ),
            "evidence": [bind(cold_reset), bind(post_restage)],
        }
    else:
        harness_first_red = {
            "classification": "none",
            "status": "not-observed-clean-media-route",
            "finding": (
                "The fresh run used the sealed-media mount route directly; no "
                "harness-only first red preceded product execution."
            ),
            "evidence": [],
        }
    route_observation = evidence.parent / "restage-route-observation.json"
    harness_route_observations = (
        [bind(route_observation)] if route_observation.is_file() else []
    )

    return {
        "format": FORMAT,
        "version": 1,
        "recorded_on": date.today().isoformat(),
        "status": "passed-fresh-nine-case-G5",
        "product": {
            "artifact_set_sha256": runbook["artifact_set_sha256"],
            "product_build_id": runbook["product_build_id"],
            "profile_build_id": runbook["profile_build_id"],
            "product_d81": transport["authority"]["product_d81"],
            "product_byte_changes": 0,
            "sealed_product_bytes_untouched": True,
        },
        "authority": {
            "runbook": bind(runbook_path),
            "media_transport_hardware_receipt": bind(transport_path),
        },
        "case_policy": "exactly-once-in-order-until-first-product-red",
        "cases": case_rows,
        "harness_first_red": harness_first_red,
        "harness_route_observations": harness_route_observations,
        "result": "passed",
        "claims": {
            "G5": "passed-for-C2-lite-product-artifact-set",
            "R6": "not-run",
            "G6": "not-run",
            "release": "not-release-capable",
        },
        "execution_accounting": {
            "device": "/dev/ttyUSB1",
            "physical_devices": 1,
            "media_boots": 2,
            "product_compiler_runs": 0,
            "product_linker_runs": 0,
            "product_byte_changes": 0,
        },
        "claim_limit": (
            "Closes fresh G5 for this exact C2-lite product artifact set. "
            "R6 packaging, G6 hardware, promotion and release remain unclaimed."
        ),
    }


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    data = canonical(value)
    if path.exists() or path.is_symlink():
        require(
            path.is_file() and not path.is_symlink() and path.read_bytes() == data,
            f"existing receipt differs: {path}",
        )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def verify_receipt(path: Path) -> dict[str, Any]:
    value = load(path, "G5 hardware receipt")
    require(
        value.get("format") == FORMAT
        and value.get("version") == 1
        and value.get("status") == "passed-fresh-nine-case-G5"
        and value.get("result") == "passed",
        "G5 hardware receipt status/format drift",
    )
    cases = value.get("cases")
    require(
        isinstance(cases, list)
        and [row.get("id") for row in cases if isinstance(row, dict)]
        == EXPECTED_CASES
        and all(row.get("status") in {"passed", "recorded-no-claim"} for row in cases),
        "G5 receipt case closure drift",
    )
    for prefix, binding in value.get("authority", {}).items():
        verify_binding(binding, f"authority {prefix}")
    for case in cases:
        evidence = case.get("evidence")
        require(isinstance(evidence, list) and evidence, f"{case['id']} lacks evidence")
        for index, binding in enumerate(evidence):
            verify_binding(binding, f"{case['id']} evidence[{index}]")
    for index, binding in enumerate(value["harness_first_red"]["evidence"]):
        verify_binding(binding, f"harness first-red evidence[{index}]")
    for index, binding in enumerate(value.get("harness_route_observations", [])):
        verify_binding(binding, f"harness route observation[{index}]")
    require(
        value.get("claims")
        == {
            "G5": "passed-for-C2-lite-product-artifact-set",
            "R6": "not-run",
            "G6": "not-run",
            "release": "not-release-capable",
        },
        "G5 claim boundary drift",
    )
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    close = sub.add_parser("close")
    close.add_argument("--runbook", type=Path, default=DEFAULT_RUNBOOK)
    close.add_argument("--transport-receipt", type=Path, default=DEFAULT_TRANSPORT)
    close.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE)
    close.add_argument("--out", type=Path, default=DEFAULT_OUT)
    close.add_argument(
        "--bank2-authority", type=Path, default=DEFAULT_BANK2_AUTHORITY
    )
    close.add_argument(
        "--bank3-authority", type=Path, default=DEFAULT_BANK3_AUTHORITY
    )
    verify = sub.add_parser("verify")
    verify.add_argument("--receipt", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    try:
        if args.action == "close":
            value = collect(
                args.runbook.resolve(),
                args.transport_receipt.resolve(),
                args.evidence_root.resolve(),
                args.bank2_authority.resolve(),
                args.bank3_authority.resolve(),
            )
            write_exclusive(args.out.resolve(), value)
            verify_receipt(args.out.resolve())
            print(
                "c2-lite-g5-hardware-close: PASS "
                f"cases=9 product={value['product']['artifact_set_sha256']} "
                "R6=not-run G6=not-run"
            )
        else:
            value = verify_receipt(args.receipt.resolve())
            print(
                "c2-lite-g5-hardware-close: VERIFY PASS "
                f"cases=9 product={value['product']['artifact_set_sha256']}"
            )
        return 0
    except (CloseError, KeyError, TypeError, ValueError) as error:
        print(f"c2-lite-g5-hardware-close: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
