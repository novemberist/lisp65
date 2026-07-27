#!/usr/bin/env python3
"""Rebind the direct-entry contract freshly for the hot-refill successor."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_direct_entry_contract as D  # noqa: E402


HISTORICAL = D.RECEIPT
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-hot-refill-direct-entry-contract-receipt.json")


class RebindError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RebindError(message)


def bind(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def build() -> dict[str, Any]:
    require(HISTORICAL.is_file(), "historical Link-29 direct-entry receipt absent")
    historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    fresh = D.collect()
    differences = {
        key: {"historical": historical["bindings"].get(key),
              "hot_refill": fresh["bindings"].get(key)}
        for key in sorted(set(historical["bindings"]) | set(fresh["bindings"]))
        if historical["bindings"].get(key) != fresh["bindings"].get(key)
    }
    require(set(differences) == {"target_decoder"},
            f"unexpected direct-entry rebind surface: {sorted(differences)}")
    require(fresh["cross_parity"]["direct_entry_references"] == 637
            and fresh["cross_parity"]["fixnum_decodable_published_values"] == 0
            and fresh["cross_parity"]["target_phase12_negative_classes"] == 4,
            "fresh direct-entry semantic closure is not exact")
    return {
        **fresh,
        "format": "lisp65-c2-hot-refill-direct-entry-contract-receipt-v1",
        "status": "passed-fresh-hot-refill-contract-and-cross-parity-probe-only",
        "historical_link29_receipt": bind(HISTORICAL),
        "rebind_attribution": {
            "changed_bindings": differences,
            "changed_binding_count": 1,
            "reason": (
                "The shared decoder translation unit now contains the separately "
                "authorized phase-13 hot-refill call. Phase 8 still calls the one "
                "MK_BCODE constructor and all 637 emitted direct references are "
                "recomputed and checked freshly; no historical green is inherited."),
        },
        "claim_limit": (
            "Fresh host execution of the current target phase-8/phase-12 code and "
            "exact 637-reference ABI cross-check for the hot-refill successor. This "
            "is not a product link, capacity, hardware, latency or promotion claim."),
        "next_gate": (
            "The owner-authorized hot-refill successor product link may start only "
            "while this receipt remains byte-identical."),
    }


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    try:
        data = canonical(build())
        if args.action == "write":
            if RECEIPT.exists(): os.chmod(RECEIPT, 0o644)
            RECEIPT.write_bytes(data); os.chmod(RECEIPT, 0o444); verb = "WROTE"
        elif args.action == "check":
            require(RECEIPT.is_file() and RECEIPT.read_bytes() == data,
                    "hot-refill direct-entry receipt drift")
            verb = "PASS"
        else:
            verb = "SELFTEST PASS"
        print("c2-hot-refill-direct-entry-contract: " + verb
              + " refs=637 fixnums=0 target-negatives=4 changed-bindings=1")
        return 0
    except (OSError, ValueError, KeyError, RuntimeError,
            D.DirectEntryError, RebindError) as error:
        print(f"c2-hot-refill-direct-entry-contract: FAIL: {error}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
