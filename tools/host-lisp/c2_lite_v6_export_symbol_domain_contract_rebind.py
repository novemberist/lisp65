#!/usr/bin/env python3
"""Bind the post-replay SYMI wording correction without rerunning gates."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
WPLTO = EVIDENCE / (
    "c2.2-c2-lite-v6-export-symbol-domain-wplto-"
    "artifact-replay-receipt.json")
WPLTO_SHA = "7ab92ed79b9005d40a260a2eafad1aa7eef85fb7200b7458eb3cf4351580d3b4"
CONTRACT = ROOT / "config/c2-lite-execution-contract.json"
ADDENDUM = ROOT / "docs/planning/c2-lite-execution-contract-addendum.md"
RUNTIME = ROOT / "src/c2_product_runtime.c"
RECEIPT = EVIDENCE / (
    "c2.2-c2-lite-v6-export-symbol-domain-contract-rebind-receipt.json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise SystemExit(f"missing authority: {path}")
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    if RECEIPT.exists() or sha(WPLTO) != WPLTO_SHA:
        raise SystemExit("contract rebind authority drift or receipt exists")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    addendum = ADDENDUM.read_text(encoding="utf-8")
    if (contract["cold_export_plan"]["symbol_predicate"] != "IS_SYMI"
            or "canonical\ninterned SYMI objects" not in addendum
            or "heap symbol objects" in addendum):
        raise SystemExit("SYMI contract wording remains inconsistent")
    value = {
        "format": "lisp65-c2-lite-v6-export-symbol-domain-contract-rebind-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-document-wording-rebind-no-product-delta",
        "authority": {"green_wplto_replay": bind(WPLTO)},
        "correction": {
            "class": "Class A prose-domain consistency only",
            "old_phrase": "heap symbol objects",
            "new_phrase": "canonical interned SYMI objects",
            "product_bytes_changed": 0,
            "compiler_runs": 0,
            "linker_runs": 0,
            "gate_replays": 0,
            "hardware_runs": 0,
        },
        "current_authority": {
            "machine_contract": bind(CONTRACT),
            "prose_addendum": bind(ADDENDUM),
            "product_source": bind(RUNTIME),
        },
        "line1_first_red_budget": "1/3 consumed; 2 remain",
        "latency_measurement_attempts": "0/2 consumed",
        "next_gate": "Separate Class-C authorization for the successor product link",
    }
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    print("c2-lite-v6-export-symbol-domain-contract-rebind: PASS "
          "product-delta=0 compiler=0 linker=0 hardware=0")
    print(f"receipt={RECEIPT.relative_to(ROOT)} sha256={sha(RECEIPT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
