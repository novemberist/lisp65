#!/usr/bin/env python3
"""Bind the current direct-entry ABI as C2-lite pre-projection authority."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_hot_refill_direct_entry_contract as HOT  # noqa: E402


RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-direct-entry-contract-receipt.json")


def value() -> dict:
    result = HOT.build()
    parity = result["cross_parity"]
    if not (parity["direct_entry_references"] == 637
            and parity["fixnum_decodable_published_values"] == 0
            and parity["target_phase12_negative_classes"] == 4):
        raise RuntimeError("C2-lite direct-entry semantic closure is red")
    result.update({
        "format": "lisp65-c2-lite-v6-direct-entry-contract-v1",
        "status": "passed-current-source-preprojection-direct-entry-contract",
        "role": (
            "Pre-projection ABI authority. The product gate reruns the same "
            "637-reference check against the generated C2-lite phase-8/12 "
            "translation units after the sole product link."),
        "next_gate": "Exactly one authorized first C2-lite product link.",
    })
    return result


def data() -> bytes:
    return (json.dumps(value(), indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    expected = data()
    if args.action == "write":
        if RECEIPT.exists():
            os.chmod(RECEIPT, 0o644)
        RECEIPT.write_bytes(expected)
        os.chmod(RECEIPT, 0o444)
        verb = "WROTE"
    elif args.action == "check":
        if not RECEIPT.is_file() or RECEIPT.read_bytes() != expected:
            raise RuntimeError("C2-lite direct-entry receipt drift")
        verb = "PASS"
    else:
        verb = "SELFTEST PASS"
    print("c2-lite-v6-direct-entry-contract: " + verb
          + " refs=637 fixnums=0 target-negatives=4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
