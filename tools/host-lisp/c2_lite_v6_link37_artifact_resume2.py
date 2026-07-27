#!/usr/bin/env python3
"""Class-A successor replay for Link-37 artifact completion."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link37_artifact_resume as RESUME  # noqa: E402


FIRST_RED = RESUME.RECEIPT
OUT = ROOT / (
    "build/c2.2/substitution/product-link-37-c2-lite-v6-artifact-resume2")
RECEIPT = RESUME.LINK.EVIDENCE / (
    "c2.2-product-link37-c2-lite-v6-artifact-resume2-structural-receipt.json")
DIAGNOSIS = RESUME.LINK.EVIDENCE / (
    "c2.2-product-link37-c2-lite-v6-family-contract-gate-diagnosis.json")


def disposition() -> dict[str, Any]:
    RESUME.require(FIRST_RED.is_file() and not DIAGNOSIS.exists(),
                   "family-contract First Red disposition is not one-shot")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    RESUME.require(first.get("status")
                   == "FIRST RED: Link-37 artifact continuation stopped"
                   and first["diagnostic"]["message"]
                       == "boot: runtime-family record field drift"
                   and first["execution_accounting"] == {
                       "artifact_resume_compiler_runs": 0,
                       "artifact_resume_linker_runs": 0,
                       "hardware_runs": 0,
                       "source_product_closure_links": 1},
                   "family-contract First Red history drift")
    value = {
        "format": "lisp65-c2-lite-v6-family-contract-gate-disposition-v1",
        "recorded_on": "2026-07-21",
        "status": "passed-class-a-pack-contract-correction",
        "class": "A",
        "first_red": RESUME.bind(FIRST_RED),
        "diagnosis": {
            "cause": (
                "The replay repacked final families against the generated C "
                "header while the SHA-bound unbound reference used the "
                "resolved-profile contract. This changed build-id and record "
                "CRC fields and therefore correctly failed identity."),
            "product_finding": "none",
            "correction": (
                "Repack both final families against the exact same SHA-bound "
                "resolved-profile.txt contract as the unbound references."),
        },
        "scope": {"product_bytes_changed": 0, "capacity_effect_bytes": 0,
                  "compiler_runs": 0, "linker_runs": 0,
                  "product_links": 0, "hardware_runs": 0},
    }
    RESUME.write_json(DIAGNOSIS, value)
    os.chmod(DIAGNOSIS, 0o444)
    return value


def main() -> int:
    disposition()
    RESUME.OUT = OUT
    RESUME.RECEIPT = RECEIPT
    RESUME.EXTRA_AUTHORITY = {
        "class_a_family_contract_disposition": RESUME.bind(DIAGNOSIS),
        "successor_replay_driver": RESUME.bind(Path(__file__)),
    }
    value = RESUME.build()
    print("c2-lite-v6-link37-artifact-resume2: " + value["status"])
    return 2 if value["status"].startswith("FIRST RED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
