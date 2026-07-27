#!/usr/bin/env python3
"""Validate the one-time Workbench-to-C2 gate inheritance inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "config/c2-historical-gate-inheritance.json"
PRODUCT_DRIVER = ROOT / "tools/host-lisp/c2_product_substitution_link.py"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-historical-gate-inheritance-receipt.json")
EXPECTED = {
    "overlay-control-geometry-and-bootstrap",
    "overlay-control-resident-placement",
    "runtime-crc-codegen",
    "f011-mount-window",
    "boot-overlay-package",
    "runtime-overlay-package",
    "overlay-stage-layout-and-footprint",
    "overlay-build-reproducibility",
    "legacy-bootstrap-host-smoke",
    "legacy-hardware-stack-readback",
}
DISPOSITIONS = {
    "migrated", "superseded", "retired-with-reason",
    "retained-hardware-only",
}


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(value: dict[str, Any], driver_text: str) -> dict[str, Any]:
    require(value.get("format") == "lisp65-c2-historical-gate-inheritance-v1",
            "inventory format drift")
    entries = value.get("entries")
    require(isinstance(entries, list), "inventory entries must be a list")
    ids = [row.get("id") for row in entries]
    require(len(ids) == len(set(ids)), "duplicate inheritance inventory id")
    require(set(ids) == EXPECTED,
            f"inheritance inventory mismatch missing={sorted(EXPECTED-set(ids))} "
            f"extra={sorted(set(ids)-EXPECTED)}")
    counts = {name: 0 for name in sorted(DISPOSITIONS)}
    migrated: list[str] = []
    for row in entries:
        disposition = row.get("disposition")
        require(disposition in DISPOSITIONS,
                f"invalid disposition for {row.get('id')}: {disposition}")
        require(isinstance(row.get("reason"), str)
                and len(row["reason"].strip()) >= 32,
                f"missing reason for {row.get('id')}")
        truths = row.get("current_truth")
        require(isinstance(truths, list) and truths
                and all(isinstance(item, str) and item for item in truths),
                f"missing current truth for {row.get('id')}")
        counts[disposition] += 1
        if disposition == "migrated":
            token = row.get("product_link_token")
            require(isinstance(token, str) and token in driver_text,
                    f"migrated gate absent from central product driver: "
                    f"{row.get('id')}")
            migrated.append(str(row["id"]))
    return {
        "status": "passed-complete-historical-gate-disposition",
        "entry_count": len(entries),
        "disposition_counts": counts,
        "migrated_into_every_c2_product_link": sorted(migrated),
        "unresolved_entries": 0,
    }


def selftest() -> dict[str, str]:
    value = json.loads(INVENTORY.read_text(encoding="utf-8"))
    driver = PRODUCT_DRIVER.read_text(encoding="utf-8")
    validate(value, driver)
    mutations: dict[str, dict[str, Any] | tuple[dict[str, Any], str]] = {
        "missing-entry": {**value, "entries": value["entries"][:-1]},
        "bad-disposition": {**value, "entries": [
            {**value["entries"][0], "disposition": "hand-waved"},
            *value["entries"][1:]]},
        "missing-link-binding": (value, driver.replace(
            "CRC_CODEGEN.audit_elf", "CRC_CODEGEN.removed_binding")),
    }
    passed: dict[str, str] = {}
    for name, mutation in mutations.items():
        candidate, text = mutation if isinstance(mutation, tuple) \
            else (mutation, driver)
        try:
            validate(candidate, text)
        except GateError as error:
            passed[name] = str(error)
        else:
            raise GateError(f"inventory mutation was accepted: {name}")
    return passed


def check(*, write_receipt: bool) -> dict[str, Any]:
    value = json.loads(INVENTORY.read_text(encoding="utf-8"))
    result = validate(value, PRODUCT_DRIVER.read_text(encoding="utf-8"))
    result.update({
        "format": "lisp65-c2-historical-gate-inheritance-receipt-v1",
        "recorded_on": "2026-07-21",
        "inventory": {
            "path": INVENTORY.relative_to(ROOT).as_posix(),
            "sha256": sha(INVENTORY),
        },
        "product_driver": {
            "path": PRODUCT_DRIVER.relative_to(ROOT).as_posix(),
            "sha256": sha(PRODUCT_DRIVER),
        },
        "claim_limit": (
            "Paper and source-wiring inventory only; no product link, "
            "hardware execution, promotion or acceptance claim."),
    })
    if write_receipt:
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--write-receipt", action="store_true")
    args = parser.parse_args()
    try:
        if args.selftest:
            cases = selftest()
            print("c2-historical-gate-inheritance: SELFTEST PASS mutations="
                  + str(len(cases)))
        else:
            value = check(write_receipt=args.write_receipt)
            print("c2-historical-gate-inheritance: " + value["status"])
        return 0
    except (GateError, OSError, ValueError, json.JSONDecodeError) as error:
        print("c2-historical-gate-inheritance: FAIL: " + str(error),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
