#!/usr/bin/env python3
"""Bind the owner-authorized Wave-3 L-lite repin without hardware claims."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import block_capacity_delta_policy as CAPACITY
import v11_l_lite_probe as PROBE


ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-wave3-l-lite-repin-receipt.json"
)
PROBE_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-l-lite-probe-receipt.json"
)
AUTHORIZATION = ROOT / "config/v11-wave3-r3-aggregate-capacity-authorization.json"
BASELINE_PRODUCT_SET = "5c7c17f8b441f8acd4f5d57ac9dd17db852f1884f7450611985e13489cc0ffb6"

PRODUCT_SOURCES = tuple(ROOT / path for path in (
    "config/v11-l-lite-keymap.json",
    "config/ide-capacity-contract.json",
    "lib/ide-keymap-generated.lisp",
    "lib/ide-disk.lisp",
    "lib/ide-ui.lisp",
    "src/repl.c",
    "src/screen.c",
    "src/screen.h",
))

EVIDENCE_INPUTS = tuple(ROOT / path for path in (
    "config/v11-wave3-r3-aggregate-capacity-authorization.json",
    "config/v11-wave3-fail-fast.json",
    "docs/generated/ide-keymap.md",
    "docs/releases/1.1-wave-3-candidate.md",
    "scripts/hw-v11-wave3-presmoke.sh",
    "scripts/lisp65-screen-scroll-rider-gate.ld",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/v11-l-lite-probe-receipt.json",
    "tests/bytecode/dialect-v2/ide/l-lite-hardware-cases.generated.json",
    "tools/host-lisp/v11_color_scroll_binding.py",
    "tools/host-lisp/v11_l_lite_keymap.py",
    "tools/host-lisp/v11_l_lite_probe.py",
    "tools/host-lisp/v11_wave3_fail_fast.py",
    "tools/host-lisp/v11_wave3_l_lite_repin.py",
))

ARTIFACTS = tuple(ROOT / path for path in (
    "build/products/workbench/overlay-stack-guard/lisp65-workbench-overlay-linked.prg",
    "build/products/workbench/overlay-stack-guard/lisp65-workbench-resident.prg",
    "build/products/workbench/overlay-stack-guard/lisp65-workbench-overlay.bin",
    "build/products/workbench/overlay-stack-guard/lisp65-mvp-workbench.overlays.bin",
    "build/products/workbench/overlay-stack-guard/layout.json",
    "build/products/workbench/overlay-stack-guard/stage-manifest.json",
    "build/products/workbench/overlay-stack-guard/runtime-overlays-manifest.json",
    "build/products/workbench/overlay-stack-guard/footprint-audit.json",
    "build/bytecode/dialect-v2/workbench-library-composition-budget.json",
    "build/bytecode/dialect-v2/shelf/library-shelf.bin",
))


class RepinError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RepinError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path.relative_to(ROOT)}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing bound file: {path.relative_to(ROOT)}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    require(result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def artifact_set(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def policy_delta(candidate_identity: str, probe: dict[str, Any]) -> dict[str, Any]:
    baseline = probe["capacity"]["baseline_wave2"]
    candidate = probe["capacity"]["candidate_without_color_scroll"]
    selected = {
        "bank": (baseline["bank_post_boot_reserve_bytes"],
                 candidate["bank_post_boot_reserve_bytes"]),
        "ext": (baseline["ext_code_peak_headroom"],
                candidate["ext_code_peak_headroom"]),
        "symbols": (baseline["symbol_headroom"], candidate["symbol_headroom"]),
        "namepool": (baseline["namepool_headroom_bytes"],
                     candidate["namepool_headroom_bytes"]),
        "directory": (baseline["directory_post_align_headroom"],
                      candidate["directory_post_align_headroom"]),
    }
    auth_row = binding(AUTHORIZATION)
    auth = {"path": auth_row["path"], "sha256": auth_row["sha256"]}
    dimensions = {}
    for name, (before, after) in selected.items():
        delta = int(after) - int(before)
        dimensions[name] = {
            "baseline": int(before), "candidate": int(after), "delta": delta,
            "authorization": auth if delta < 0 else None,
        }
    value = {
        "baseline_identity_sha256": BASELINE_PRODUCT_SET,
        "candidate_identity_sha256": candidate_identity,
        "dimensions": dimensions,
    }
    CAPACITY.validate_policy()
    CAPACITY.validate_capacity_delta(value)
    return value


def validate_historical_probe(probe: dict[str, Any]) -> None:
    """Validate the probe record, then compare its metrics with the live repin.

    The probe binds the pre-commit candidate artifacts.  Rebuilding the committed
    candidate changes the product Build-ID, so checking those historical artifact
    paths against the live build would incorrectly turn a valid probe into mutable
    evidence.  Capacity values, unlike artifact identity, must remain equal.
    """
    PROBE.validate(probe, verify_files=False)
    measured = PROBE.current_metrics(
        load(PROBE.COMPOSITION), load(PROBE.FOOTPRINT), load(PROBE.RUNTIME)
    )
    require(measured == probe["capacity"]["candidate_without_color_scroll"],
            "live repin capacity differs from the owner-authorized probe")


def collect() -> dict[str, Any]:
    require(not git("status", "--porcelain"),
            "collect requires a clean committed L-lite source state")
    probe = load(PROBE_RECEIPT)
    validate_historical_probe(probe)
    auth = load(AUTHORIZATION)
    require(auth.get("status") == "authorized"
            and auth.get("authorized_debits") == {"ext": 236, "directory": 8},
            "owner capacity authorization drift")
    artifacts = [binding(path) for path in ARTIFACTS]
    candidate_identity = artifact_set(artifacts)
    return {
        "format": "lisp65-v11-wave3-l-lite-repin-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-19",
        "status": "passed-owner-authorized-ready-for-wave3-promotion",
        "claim_limit": (
            "This receipt binds the owner-authorized L-lite source/product link, "
            "all pinned capacity dimensions, the final C2 color-scroll fallback and "
            "the release Known Issue. Hardware, G5, G6, seal and release remain not-run."
        ),
        "baseline": {
            "wave": 2,
            "product_artifact_set_sha256": BASELINE_PRODUCT_SET,
            "source_commit": "4694dc24936f899eb333686c59b8a179e8dd0a71",
        },
        "candidate": {
            "source_commit": git("rev-parse", "HEAD"),
            "core_artifact_set_sha256": candidate_identity,
            "artifacts": artifacts,
            "product_sources": [binding(path) for path in PRODUCT_SOURCES],
            "evidence_inputs": [binding(path) for path in EVIDENCE_INPUTS],
        },
        "capacity": probe["capacity"],
        "capacity_delta": policy_delta(candidate_identity, probe),
        "color_scroll": {
            "product": "deferred-to-C2-after-final-authorized-attempt",
            "diagnostic_quantum": "unbooked",
            "third_attempt": "forbidden",
            "known_issue": probe["release_known_issue"],
        },
        "gates": {
            "generated_keymap": "41 bindings / 5 M-x / 6 outputs",
            "fail_fast": "six-new-first / three-dry-classes / receipt-less-presmoke",
            "screen_clear_color_semantics": "host-proven-color-unchanged",
            "frozen_capacity_dimensions": "all reported",
            "hardware": "not-run",
        },
    }


def write() -> dict[str, Any]:
    value = collect()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    return value


def check() -> dict[str, Any]:
    actual = load(RECEIPT)
    require(actual.get("format") == "lisp65-v11-wave3-l-lite-repin-receipt-v1"
            and actual.get("status") ==
                "passed-owner-authorized-ready-for-wave3-promotion",
            "repin receipt identity drift")
    git("merge-base", "--is-ancestor", actual["candidate"]["source_commit"], "HEAD")
    probe = load(PROBE_RECEIPT)
    validate_historical_probe(probe)
    artifacts = [binding(path) for path in ARTIFACTS]
    identity = artifact_set(artifacts)
    require(artifacts == actual["candidate"]["artifacts"], "artifact binding drift")
    require(identity == actual["candidate"]["core_artifact_set_sha256"],
            "core artifact-set drift")
    require([binding(path) for path in PRODUCT_SOURCES] ==
            actual["candidate"]["product_sources"], "product-source binding drift")
    require([binding(path) for path in EVIDENCE_INPUTS] ==
            actual["candidate"]["evidence_inputs"], "evidence-input binding drift")
    require(actual["capacity"] == probe["capacity"], "capacity receipt drift")
    require(actual["capacity_delta"] == policy_delta(identity, probe),
            "capacity policy delta drift")
    require(actual["gates"]["hardware"] == "not-run",
            "repin receipt overclaims hardware")
    return actual


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("collect", "check"))
    args = parser.parse_args(argv)
    try:
        value = write() if args.command == "collect" else check()
    except (OSError, ValueError, KeyError, CAPACITY.CapacityDeltaError,
            PROBE.ProbeError, RepinError) as exc:
        print(f"v11-wave3-l-lite-repin: FAIL: {exc}", file=sys.stderr)
        return 1
    dimensions = value["capacity_delta"]["dimensions"]
    print("v11-wave3-l-lite-repin: PASS "
          f"bank={dimensions['bank']['candidate']} "
          f"ext-peak={dimensions['ext']['candidate']} "
          f"symbols={dimensions['symbols']['candidate']} "
          f"namepool={dimensions['namepool']['candidate']} "
          f"directory={dimensions['directory']['candidate']} hardware=not-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
