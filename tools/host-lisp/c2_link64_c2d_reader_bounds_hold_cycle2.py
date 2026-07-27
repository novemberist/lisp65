#!/usr/bin/env python3
"""Bind cycle 2 of the nonpromotable Link-64 reader-bounds hold."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_link64_c2d_reader_bounds_hold as D  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
NOHIT = EVIDENCE / (
    "c2.2-link64-c2d-reader-bounds-nohit-hardware-receipt.json")
OUT = ROOT / (
    "build/c2.2/hardware-link64-c2d-reader-bounds-hold-cycle2-"
    "NONPROMOTABLE")
DEPLOYMENT = OUT / "deployment.json"


class CycleError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CycleError(message)


def data(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink(),
            f"authority absent or not regular: {path}")
    return path.read_bytes()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    value = data(path)
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(value),
        "sha256": sha_bytes(value),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(data(path))
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def main() -> int:
    D.verify()
    prior = load(NOHIT)
    base = load(D.DEPLOYMENT)
    require(
        prior["status"]
            == "NO HIT: no C2D-reader bounds rejection in this episode"
        and prior["answer"]["runtime_bounds_rejection_observed"] is False
        and base["status"] == "ready-authorized-nonpromotable-hardware",
        "cycle-2 authority drift")
    value = {
        **base,
        "format":
            "lisp65-c2.2-Link64-c2d-reader-bounds-hold-hardware-v2",
        "status": "ready-authorized-nonpromotable-hardware-cycle-2",
        "diagnostic_cycle": 2,
        "authority": {
            **base["authority"],
            "cycle_1_nohit_receipt": bind(NOHIT),
            "cycle_2_driver": bind(Path(__file__)),
        },
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs_before_this_cycle": 1,
            "latency_attempts_consumed": 0,
        },
        "claim_limit": (
            "Second episode of the same nonpromotable reader-bounds "
            "question. C1 remains OPEN."),
    }
    encoded = (
        json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    OUT.mkdir(parents=True, exist_ok=True)
    if DEPLOYMENT.exists():
        require(data(DEPLOYMENT) == encoded, "cycle-2 deployment drift")
    else:
        DEPLOYMENT.write_bytes(encoded)
        DEPLOYMENT.chmod(0o444)
    print(json.dumps({
        "status": "ready",
        "diagnostic_cycle": 2,
        "product_delta": 0,
        "capacity_delta": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CycleError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-link64-reader-bounds-cycle2: FIRST RED: " + str(error))
        raise SystemExit(2)
