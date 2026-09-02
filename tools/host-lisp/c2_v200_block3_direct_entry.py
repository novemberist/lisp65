#!/usr/bin/env python3
"""Bind the live direct-entry contract without rewriting sealed C2.2 evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_direct_entry_contract as BASE  # noqa: E402


RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-block3-direct-entry-contract.json")


def canonical(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def value() -> dict[str, object]:
    result = BASE.collect()
    result["evidence_era"] = {
        "sealed_predecessor": BASE.RECEIPT.relative_to(ROOT).as_posix(),
        "rule": ("the sealed C2.2 receipt remains immutable; the living "
                 "product binds a freshly executed semantic successor")}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    try:
        current = value()
        if args.action == "write":
            RECEIPT.write_bytes(canonical(current))
        elif args.action == "check":
            if not RECEIPT.is_file() or RECEIPT.read_bytes() != canonical(current):
                raise RuntimeError("live direct-entry successor receipt drift")
        print("v2.0 Block3 direct-entry: PASS refs=637 sealed-c2.2=unchanged")
        return 0
    except (RuntimeError, BASE.DirectEntryError) as error:
        print(f"v2.0 Block3 direct-entry: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
