#!/usr/bin/env python3
"""Prepare and close the informational v1.2.2 G2 target timing rows."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2.2-v1.2.2-g2-symbol-value-cost-session.json"
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.2-g2-symbol-value-cost-preparation-receipt.json")
CANDIDATE = ROOT / (
    "build/c2.2/v1.2.2-candidate-product/"
    "canonical-product-manifest.json")
BASE = ROOT / "build/c2.2/v1.2.2-acceptance/r5"
PREFLIGHT = BASE / "r5-preflight-receipt.json"
SESSION = BASE / "hardware-session-01"
EVIDENCE = SESSION / "g2-symbol-value-cost"
PLAN = EVIDENCE / "measurement-plan.json"
G5 = SESSION / "g5-hardware-receipt.json"
RECEIPT = SESSION / "g2-symbol-value-cost-hardware-receipt.json"
FORMAT = "lisp65-c2-lite-v1.2.2-G2-symbol-value-cost-hardware-v1"
TUPLE_RE = re.compile(
    r"^\s*\((\d+)\s+(\d+)\s+(\d+)\s+"
    r"(\d+)\s+(\d+)\s+(\d+)\)\s*$",
    re.MULTILINE,
)
NESTED_TUPLE_RE = re.compile(
    r"^\s*\(\s*\((\d+)\s+(\d+)\s+(\d+)\)\s+"
    r"\((\d+)\s+(\d+)\s+(\d+)\)\s*\)\s*$",
    re.MULTILINE,
)


class G2HardwareError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise G2HardwareError(message)


def load(path: Path, label: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"{label} missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise G2HardwareError(f"cannot read {label}: {error}") from error
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"binding missing: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write_exact(path: Path, value: dict[str, Any]) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")
    if path.exists() or path.is_symlink():
        require(
            path.is_file() and not path.is_symlink()
            and path.read_bytes() == data,
            f"existing generated file differs: {path}",
        )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def prepare() -> dict[str, Any]:
    contract = load(CONTRACT, "G2 contract")
    prior = load(PREPARATION, "G2 host preparation")
    candidate = load(CANDIDATE, "v1.2.2 candidate manifest")
    preflight = load(PREFLIGHT, "R5 preflight")
    carrier = candidate.get("static_plane", {}).get("compiler_carrier", {})
    prior_carrier = prior.get("bound_carrier_execution", {}).get("carrier", {})
    require(
        contract.get("status")
        == "host-qualified-queued-for-next-bundled-hardware-session"
        and prior.get("status")
        == "passed-host-qualified-two-row-measurement-awaiting-bundled-session"
        and preflight.get("status") == "passed-ready-for-fresh-G5-hardware"
        and carrier.get("sha256") == prior_carrier.get("sha256")
        and carrier.get("bytes") == prior_carrier.get("bytes")
        and candidate.get("candidate", {}).get("release") == "v1.2.2",
        "G2 candidate/carrier/preflight binding drift",
    )
    value = {
        "format": FORMAT,
        "version": 1,
        "recorded_on": date.today().isoformat(),
        "status": "prepared-independent-informational-measurement",
        "authority": {
            "contract": bind(CONTRACT),
            "host_preparation": bind(PREPARATION),
            "candidate_manifest": bind(CANDIDATE),
            "R5_preflight": bind(PREFLIGHT),
        },
        "carrier_rebind": {
            "status": "byteidentical-to-host-qualified-bound-carrier",
            "bytes": carrier["bytes"],
            "sha256": carrier["sha256"],
        },
        "rows": [
            {
                "id": row["id"],
                "form": row["form"],
                "acceptance_criterion": False,
            }
            for row in contract["rows"]
        ],
        "setup_forms": contract["setup_forms"],
        "input_transport": contract["input_transport"],
        "policy": {
            "same_physical_session_as_G5": True,
            "can_make_acceptance_chain_red": False,
            "red_acceptance_row_does_not_invalidate_measurement": True,
            "measurement_failure": "invalid-no-inference",
        },
        "execution": {
            "hardware_started": False,
            "product_builds": 0,
            "product_links": 0,
            "product_byte_changes": 0,
        },
        "claim_limit": (
            "Preparation only. It creates no target timing value, G5 result, "
            "acceptance, GC optimization authorization, promotion or release."
        ),
    }
    write_exact(PLAN, value)
    return value


def last_tuple(path: Path) -> list[int] | None:
    if not path.is_file() or path.is_symlink():
        return None
    content = path.read_text(encoding="utf-8", errors="strict")
    matches = NESTED_TUPLE_RE.findall(content)
    if not matches:
        matches = TUPLE_RE.findall(content)
    if not matches:
        return None
    values = [int(value) for value in matches[-1]]
    if any(value < 0 or value > 255 for value in values):
        return None
    return values


def record_input_transport_first_red() -> dict[str, Any]:
    plan = load(PLAN, "G2 measurement plan")
    contract = load(CONTRACT, "G2 contract")
    attempts = sorted(EVIDENCE.glob(
        "g2-boundp-control-1000-input-attempt-*.txt"))
    require(
        attempts and not (EVIDENCE / "g2-boundp-control-1000.txt").exists(),
        "long-input First Red evidence is incomplete",
    )
    old_form = (
        "(let((a(peek 255 132)))(let((b(peek 255 131)))"
        "(let((c(peek 255 132)))(let((r(dotimes(i 1000)"
        "(boundp(quote t)))))(let((d(peek 255 132)))"
        "(let((e(peek 255 131)))(let((f(peek 255 132)))"
        "(list a b c d e f))))))))"
    )
    require(len(old_form) > contract["input_transport"][
        "maximum_form_characters"], "old form was not over the bound")
    value = {
        "format":
            "lisp65-c2-lite-v1.2.2-G2-input-transport-first-red-v1",
        "recorded_on": date.today().isoformat(),
        "classification": "measurement-harness-input-transport-only",
        "status": "excluded-no-measurement-form-executed",
        "authority": {
            "plan": bind(PLAN),
            "corrected_contract": bind(CONTRACT),
        },
        "observation": {
            "rejected_form_characters": len(old_form),
            "corrected_maximum_form_characters":
                contract["input_transport"]["maximum_form_characters"],
            "verified_echo_attempts": [bind(path) for path in attempts],
            "result_capture_present": False,
        },
        "execution_accounting": {
            "accepted_measurement_rows": 0,
            "product_builds": 0,
            "product_links": 0,
            "product_byte_changes": 0,
        },
        "claim_limit": (
            "The verified-input harness rejected or cleared the overlong "
            "control form before a result capture. This receipt carries no "
            "timing value, G5 result, acceptance failure or product claim."
        ),
    }
    write_exact(EVIDENCE / "input-transport-first-red.json", value)
    return value


def frames(values: list[int]) -> int | None:
    sh1, sl, sh2, eh1, el, eh2 = values
    if sh1 != sh2 or eh1 != eh2:
        return None
    return (((eh1 << 8) | el) - ((sh1 << 8) | sl)) & 0xFFFF


def close(control_exit: int, measured_exit: int) -> dict[str, Any]:
    plan = load(PLAN, "G2 measurement plan")
    contract = load(CONTRACT, "G2 contract")
    control_path = EVIDENCE / "g2-boundp-control-1000.txt"
    measured_path = EVIDENCE / "g2-symbol-value-1000.txt"
    control_tuple = last_tuple(control_path)
    measured_tuple = last_tuple(measured_path)
    control_frames = (
        None if control_tuple is None else frames(control_tuple))
    measured_frames = (
        None if measured_tuple is None else frames(measured_tuple))
    valid = (
        control_exit == 0 and measured_exit == 0
        and control_frames is not None and measured_frames is not None
    )
    observations: dict[str, Any] = {
        "control_exit": control_exit,
        "measured_exit": measured_exit,
        "control_tuple": control_tuple,
        "measured_tuple": measured_tuple,
        "control_frames": control_frames,
        "measured_frames": measured_frames,
    }
    if valid:
        delta = measured_frames - control_frames
        projected = delta * 480 / 1000
        dominant = projected >= 44.5
        observations.update({
            "delta_frames_per_1000": delta,
            "frames_per_read": delta / 1000,
            "microseconds_per_read": delta * 20,
            "projected_480_frames": projected,
            "whole_collection_frames": 89,
            "dominance_threshold_frames": 44.5,
            "dominant_GC_lever": dominant,
            "value_string": (
                f"symval-minus-boundp={delta}f/1000 = "
                f"{delta / 1000:.6f}f/read = {delta * 20}us/read; "
                f"projected-480={projected:.3f}f/89f"
            ),
        })
        status = "passed-informational-measurement"
        disposition = (
            "threshold-met-separate-owner-decision-required"
            if dominant else "threshold-not-met-no-GC-cut-authorized"
        )
    else:
        status = "invalid-measurement-no-inference"
        disposition = "no-GC-cut-authorized"

    value = {
        "format": FORMAT,
        "version": 1,
        "recorded_on": date.today().isoformat(),
        "status": status,
        "authority": {
            "plan": bind(PLAN),
            "contract": bind(CONTRACT),
            "host_preparation": bind(PREPARATION),
            "G5": bind(G5) if G5.is_file() else None,
        },
        "acceptance_independence": {
            "G5_present": G5.is_file(),
            "can_make_acceptance_chain_red": False,
            "measurement_validity_independent_of_acceptance_rows": True,
        },
        "observations": observations,
        "disposition": disposition,
        "applicability":
            contract["cost_constant_applicability"],
        "execution_accounting": {
            "physical_sessions_added": 0,
            "product_builds": 0,
            "product_links": 0,
            "product_byte_changes": 0,
        },
        "claim_limit": (
            "Matched CALLPRIM-19 minus CALLPRIM-57 target measurement. "
            "Directly applicable only to the named 2-byte vm_dma paths; "
            "symname and Prim-67 remain reference-only. This receipt is not "
            "an acceptance criterion or an optimization authorization."
        ),
    }
    write_exact(RECEIPT, value)
    return value


def verify() -> None:
    value = load(RECEIPT, "G2 hardware receipt")
    require(
        value.get("format") == FORMAT
        and value.get("status") in {
            "passed-informational-measurement",
            "invalid-measurement-no-inference",
        }
        and value.get("acceptance_independence", {}).get(
            "can_make_acceptance_chain_red") is False,
        "G2 hardware receipt drift",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("prepare")
    sub.add_parser("record-input-transport-first-red")
    close_parser = sub.add_parser("close")
    close_parser.add_argument("--control-exit", type=int, required=True)
    close_parser.add_argument("--measured-exit", type=int, required=True)
    sub.add_parser("verify")
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            value = prepare()
            print(
                "c2-v1.2.2-g2-hardware: PREPARED "
                f"carrier={value['carrier_rebind']['sha256']} "
                "acceptance-criterion=no")
        elif args.action == "record-input-transport-first-red":
            value = record_input_transport_first_red()
            print(
                "c2-v1.2.2-g2-hardware: INPUT FIRST RED BOUND "
                f"class={value['classification']} product-execution=no")
        elif args.action == "close":
            value = close(args.control_exit, args.measured_exit)
            print(
                "c2-v1.2.2-g2-hardware: "
                f"{value['status']} "
                f"{value['observations'].get('value_string', 'no-value')}")
        else:
            verify()
            print("c2-v1.2.2-g2-hardware: VERIFY PASS")
        return 0
    except (
        G2HardwareError, KeyError, OSError, TypeError, ValueError,
    ) as error:
        print(f"c2-v1.2.2-g2-hardware: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
