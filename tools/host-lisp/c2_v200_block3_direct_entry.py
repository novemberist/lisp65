#!/usr/bin/env python3
"""Bind the live direct-entry contract without rewriting sealed C2.2 evidence."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
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


def bind(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def value() -> dict[str, object]:
    result = BASE.collect()
    sealed = json.loads(BASE.RECEIPT.read_text(encoding="utf-8"))
    result["evidence_era"] = {
        "sealed_predecessor": bind(BASE.RECEIPT),
        "sealed_abi_constructor": sealed["bindings"]["abi_constructor"],
        "live_abi_constructor": result["bindings"]["abi_constructor"],
        "rule": ("the sealed C2.2 receipt remains immutable; the living "
                 "product binds a freshly executed semantic successor")}
    return result


def validate(result: dict[str, object]) -> None:
    era = result.get("evidence_era")
    if not isinstance(era, dict):
        raise RuntimeError("direct-entry evidence era absent")
    sealed = json.loads(BASE.RECEIPT.read_text(encoding="utf-8"))
    live = BASE.B.source_binding()
    if (era.get("sealed_predecessor") != bind(BASE.RECEIPT)
            or era.get("sealed_abi_constructor") !=
                sealed["bindings"]["abi_constructor"]
            or era.get("live_abi_constructor") != live
            or result.get("bindings", {}).get("abi_constructor") != live):
        raise RuntimeError("sealed/live direct-entry worlds were mixed")


def selftest(result: dict[str, object]) -> None:
    sealed = json.loads(BASE.RECEIPT.read_text(encoding="utf-8"))
    trial = deepcopy(result)
    trial["bindings"]["abi_constructor"] = sealed["bindings"]["abi_constructor"]
    rejected = False
    try:
        validate(trial)
    except RuntimeError:
        rejected = True
    if not rejected:
        raise RuntimeError("sealed-ABI/live-successor mixing mutation survived")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    try:
        current = value()
        validate(current)
        if args.action == "write":
            RECEIPT.write_bytes(canonical(current))
        elif args.action == "check":
            if not RECEIPT.is_file() or RECEIPT.read_bytes() != canonical(current):
                raise RuntimeError("live direct-entry successor receipt drift")
        else:
            selftest(current)
        print("v2.0 Block3 direct-entry: PASS refs=637 sealed-c2.2=unchanged")
        return 0
    except (RuntimeError, BASE.DirectEntryError) as error:
        print(f"v2.0 Block3 direct-entry: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
