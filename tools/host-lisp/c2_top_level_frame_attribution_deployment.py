#!/usr/bin/env python3
"""Bind the nonpromotable frame probe to the standard C2 hardware loader."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
INTERNAL = EVIDENCE / (
    "c2.2-link57-top-level-frame-attribution-wplto3-internal.json")
REPLAY = EVIDENCE / (
    "c2.2-link57-top-level-frame-attribution-artifact-replay-receipt.json")
C2_ARTIFACT_AUTHORITY = ROOT / (
    "build/c2.2/substitution/"
    "link57-l-full-keymap-bytecode-artifacts/product/"
    "substitution-artifacts.json")
OUT = EVIDENCE / (
    "c2.2-link57-top-level-frame-attribution-deployment-authority.json")


class DeploymentError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise DeploymentError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"deployment authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def main() -> int:
    require(not OUT.exists(), "frame-attribution deployment authority exists")
    internal = json.loads(INTERNAL.read_text(encoding="utf-8"))
    replay = json.loads(REPLAY.read_text(encoding="utf-8"))
    require(
        internal["status"] ==
            "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and replay["status"] ==
            "passed-nonpromotable-frame-attribution-WPLTO-all-walls-green"
        and replay["promotable"] is False
        and replay["execution_accounting"][
            "whole_program_lto_closure_links"] == 1
        and replay["execution_accounting"]["hardware_runs"] == 0,
        "frame-attribution deployment inputs are not green/nonpromotable",
    )
    linked = replay["linked_dataflow_gate"]
    source = replay["source_contract_gate"]
    value = {
        "format": "lisp65-c2-top-level-frame-attribution-deployment-v1",
        "recorded_on": "2026-07-23",
        "status":
            "passed-nonpromotable-frame-attribution-deployment-authority",
        "promotable": False,
        "authority": {
            "WPLTO_internal": bind(INTERNAL),
            "artifact_replay": bind(REPLAY),
            "deployment_adapter": bind(Path(__file__)),
        },
        "product_identity": internal["product_identity"],
        "fresh_generic_gates": internal["fresh_generic_gates"],
        "fresh_prelink_gates": internal["fresh_prelink_gates"],
        "fresh_real_abi_gate": internal["fresh_real_abi_gate"],
        "fresh_replacement_gates": internal["fresh_replacement_gates"],
        "frame_attribution": {
            "source_contract_gate": source,
            "linked_dataflow_gate": linked,
            "capture_address": "0x00c1e5",
            "capture_bytes": 15,
            "delta_formula": "(next-current)&0xff",
            "complete_interval_limit_frames": 256,
            "acceptance_claim": "none",
            "c2_artifact_authority": bind(C2_ARTIFACT_AUTHORITY),
        },
        "execution_accounting": {
            "resident_island_seed_links": 1,
            "product_closure_links": 1,
            "hardware_runs": 0,
            "latency_attempts_consumed_this_run": 0,
            "completed_latency_measurements": "1/2",
        },
        "claim_limit":
            "One nonpromotable hardware attribution run. It cannot be "
            "promoted and is not latency attempt 2.",
    }
    OUT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(OUT, 0o444)
    print(
        "c2-top-level-frame-attribution-deployment: PASS "
        f"product={value['product_identity']['product']['sha256']} "
        "capture=0x00c1e5+15")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DeploymentError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(
            "c2-top-level-frame-attribution-deployment: FIRST RED: "
            + str(error))
        raise SystemExit(2)
