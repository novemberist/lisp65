#!/usr/bin/env python3
"""Class-A replay after removing a duplicate profile application."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_real_abi_e000_eviction_wplto as PROBE  # noqa: E402


FIRST_RED = PROBE.RECEIPT
FIRST_RED_SHA = (
    "afb39f3fe346a27f603e1d69efd25150db7813ec7ddff9d4af361581be1a0631")
OUT = ROOT / (
    "build/c2-lite/v6-link39-real-abi-e000-evacuation-wplto-replay")
RECEIPT = PROBE.EVIDENCE / (
    "c2.2-c2-lite-v6-link39-real-abi-e000-evacuation-"
    "wplto-replay-receipt.json")
DIAGNOSIS = PROBE.EVIDENCE / (
    "c2.2-c2-lite-v6-link39-real-abi-e000-evacuation-"
    "profile-harness-diagnosis.json")


def main() -> int:
    PROBE.require(PROBE.sha(FIRST_RED) == FIRST_RED_SHA
                  and not OUT.exists() and not RECEIPT.exists()
                  and not DIAGNOSIS.exists(),
                  "evacuation Class-A replay state drift")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    PROBE.require(first["failure"] == {
                      "type": "ProfileError",
                      "message": "Link-33 configured append/runtime ABI drift"}
                  and not first["evidence"],
                  "unexpected evacuation harness First Red")
    diagnosis = {
        "format": "lisp65-c2-lite-v6-e000-evacuation-profile-harness-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-class-a-single-profile-application",
        "first_red": PROBE.bind(FIRST_RED),
        "cause": (
            "The probe applied the C2-lite/Bank-3 profile before calling the "
            "shared WPLTO driver, which applies that exact profile itself. "
            "The second application reached a historical Link-33 cardinality "
            "assertion. No compiler or linker had run."),
        "correction": (
            "Delegate the sole profile application to the shared WPLTO driver."),
        "scope": {"product_bytes_changed": 0, "capacity_effect_bytes": 0,
                  "compiler_runs": 0, "linker_runs": 0,
                  "product_links": 0, "hardware_runs": 0},
    }
    PROBE.write_json(DIAGNOSIS, diagnosis)
    os.chmod(DIAGNOSIS, 0o444)
    old_out, old_receipt = PROBE.OUT, PROBE.RECEIPT
    old_authority = PROBE.authority

    def authority():
        value = old_authority()
        value["class_a_profile_harness_disposition"] = PROBE.bind(DIAGNOSIS)
        value["replay_driver"] = PROBE.bind(Path(__file__))
        return value

    try:
        PROBE.OUT, PROBE.RECEIPT = OUT, RECEIPT
        PROBE.authority = authority
        value = PROBE.build()
    finally:
        PROBE.OUT, PROBE.RECEIPT = old_out, old_receipt
        PROBE.authority = old_authority
    print("c2-lite-v6-real-abi-e000-evacuation-wplto-replay: "
          + value["status"])
    return 2 if value["status"].startswith("FIRST RED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
