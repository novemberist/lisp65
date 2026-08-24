#!/usr/bin/env python3
"""Attribute the message-less product-profile parity selftest assertion."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as LINK  # noqa: E402

PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
OUT = ROOT / ("tests/bytecode/dialect-v2/evidence/architecture-blocks/"
              "c2.3-v1.6-product-profile-parity-assertion-attribution.json")
RED_COMMIT = "f893531f"
SUCCESSOR_COMMIT = "596e170f"
SOURCE = "tools/host-lisp/c2_product_substitution_link.py"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True,
                          stdout=subprocess.PIPE).stdout


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def derive() -> dict[str, Any]:
    red_commit = git("rev-parse", f"{RED_COMMIT}^{{commit}}").decode().strip()
    successor_commit = git(
        "rev-parse", f"{SUCCESSOR_COMMIT}^{{commit}}").decode().strip()
    red_source = git("show", f"{red_commit}:{SOURCE}")
    require(b"assert len(control_matrix) == 6" in red_source,
            "attributed one-sided count assertion absent from frozen Red")
    observed = LINK._owned_control_flow_model_selftest()
    expected_predecessor_names = sorted(
        name for name in observed if name != "owned-tail-continuation")
    observed_names = sorted(observed)
    difference = sorted(set(observed_names) - set(expected_predecessor_names))
    require(len(expected_predecessor_names) == 6
            and len(observed_names) == 7
            and difference == ["owned-tail-continuation"]
            and observed["owned-tail-continuation"] == "passed",
            "product-profile parity Red no longer matches attributed matrix")
    successor_diff = git("show", "--format=", successor_commit, "--", SOURCE)
    require(b'"owned-tail-continuation"' in successor_diff,
            "authorized successor case absent from introducing commit")
    return {
        "format": "lisp65-c2.3-v1.6-product-profile-parity-assertion-attribution-v1",
        "recorded_on": "2026-08-24",
        "status": "ATTRIBUTED: OWNED-CONTROL-FLOW MATRIX COUNT PIN",
        "authority": {
            "red_commit": red_commit,
            "authorized_successor_commit": successor_commit,
            "review_plan": bind(PLAN),
        },
        "inputs": {
            "frozen_red_source": {
                "path": SOURCE,
                "bytes": len(red_source),
                "sha256": hashlib.sha256(red_source).hexdigest(),
            },
            "live_source": bind(ROOT / SOURCE),
        },
        "drift": {
            "expected_by_frozen_assertion": {
                "count": 6,
                "names_reconstructed_from_predecessor_matrix":
                    expected_predecessor_names,
            },
            "observed_named_matrix": observed,
            "difference": {
                "added": difference,
                "removed": [],
                "outcome_changes": {},
            },
        },
        "decision": {
            "class": "counted expectation over an authorized named successor",
            "known_family": True,
            "product_profile_defect": False,
            "reason": ("commit 596e170f added the owned retired-window IRQ "
                       "tail continuation and its passing model case; the old "
                       "message-less six-case assertion alone drifted"),
            "conversion": ("validate the complete named case/outcome mapping "
                           "and report expected, observed, missing, unexpected "
                           "and mismatched members"),
        },
        "attempt_accounting": {
            "cards_consumed": 0,
            "WPLTO_runs": 0,
            "product_links": 0,
            "media_builds": 0,
            "device_contacts": 0,
        },
        "claim_limit": ("Host-only attribution of the product-link selftest "
                        "failure. It does not qualify a product or medium."),
    }


def main() -> int:
    value = derive()
    OUT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    print(f"product-profile parity assertion: {value['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
