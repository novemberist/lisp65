#!/usr/bin/env python3
"""Bind Link 75's canonical retry to the complete Bank-5 reset domain."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "build/post-promotion/link75-bound-compiler-carrier"
FINAL = BASE / "final"
BUNDLED = BASE / "bundled-completion-session"
SOURCE_DEPLOYMENT = BUNDLED / "product-phase-deployment.json"
OUT = BUNDLED / "reset-domain-successor"
RESET_DOMAIN = BUNDLED / "c2d-v6-reset-domain.bin"
DEPLOYMENT = OUT / "product-phase-deployment.json"
PREFIX = FINAL / (
    "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
C4_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link57-destructive-restage-contract-probe-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link75-bundled-reset-domain-successor-receipt.json")

C2D_ADDRESS = 0x00050000
PREFIX_BYTES = 33840
REGION_BYTES = 50816
C2J = (50752, 50816)


class SuccessorError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SuccessorError(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if address is not None:
        value["address"] = f"0x{address:08x}"
    return value


def replace_json(path: Path, value: dict[str, Any]) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode(
        "ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    temporary.replace(path)


def expected_reset_domain() -> bytes:
    prefix = PREFIX.read_bytes()
    require(len(prefix) == PREFIX_BYTES, "canonical prefix size drift")
    return prefix + bytes(REGION_BYTES - PREFIX_BYTES)


def mutation_results(reset: bytes) -> dict[str, str]:
    prefix = PREFIX.read_bytes()

    def valid(candidate: bytes) -> bool:
        return (
            len(candidate) == REGION_BYTES
            and candidate[:PREFIX_BYTES] == prefix
            and not any(candidate[PREFIX_BYTES:])
        )

    candidates = {
        "prefix-only": reset[:PREFIX_BYTES],
        "short-reset-domain": reset[:-1],
        "wrong-prefix": bytes([reset[0] ^ 1]) + reset[1:],
        "nonzero-inactive-suffix":
            reset[:PREFIX_BYTES] + b"\x01" + reset[PREFIX_BYTES + 1:],
        "nonzero-C2J":
            reset[:C2J[0]] + b"\x10" + reset[C2J[0] + 1:],
    }
    require(valid(reset), "canonical complete reset domain rejected")
    require(
        all(not valid(candidate) for candidate in candidates.values()),
        "reset-domain mutation escaped",
    )
    return {name: "rejected" for name in candidates}


def prepare() -> dict[str, Any]:
    source = load(SOURCE_DEPLOYMENT)
    c4 = load(C4_RECEIPT)
    require(
        source["status"] == "ready-product-phase-hardware-not-run"
        and c4["ordinary_presmoke_gap"]["required_cold_reset_domain_bytes"]
            == REGION_BYTES
        and c4["source_truth"]["c2j"]
            == "[50752,50816)-zero-before-ready-and-first-append",
        "successor authority drift",
    )
    reset = expected_reset_domain()
    RESET_DOMAIN.parent.mkdir(parents=True, exist_ok=True)
    if RESET_DOMAIN.exists():
        require(RESET_DOMAIN.read_bytes() == reset,
                "reset-domain artifact drift")
    else:
        RESET_DOMAIN.write_bytes(reset)

    deployment = json.loads(json.dumps(source))
    replacements = 0
    preloads = []
    for row in deployment["preloads"]:
        copy = dict(row)
        if copy["role"] == "c2d-v6-code-plane":
            require(
                copy["address"] == f"0x{C2D_ADDRESS:08x}"
                and copy["bytes"] == PREFIX_BYTES
                and copy["sha256"] == sha(PREFIX),
                "source prefix preload drift",
            )
            copy = {
                **bind(RESET_DOMAIN, C2D_ADDRESS),
                "role": "c2d-v6-complete-reset-domain",
            }
            replacements += 1
        preloads.append(copy)
    require(replacements == 1, "reset-domain replacement not unique")
    deployment["preloads"] = preloads
    deployment["format"] = (
        "lisp65-c2.2-link75-bundled-product-reset-successor-v1")
    deployment["status"] = (
        "ready-product-phase-after-reset-domain-harness-correction")
    deployment["cold_reset_contract"] = {
        "reset_domain": [0, REGION_BYTES],
        "canonical_prefix": [0, PREFIX_BYTES],
        "zero_suffix": [PREFIX_BYTES, REGION_BYTES],
        "c2j": list(C2J),
        "pre_run_readback_required": True,
    }
    deployment["authority"]["C4_complete_reset_contract"] = bind(C4_RECEIPT)
    deployment["authority"]["superseded_prefix_only_deployment"] = bind(
        SOURCE_DEPLOYMENT)
    replace_json(DEPLOYMENT, deployment)

    mutations = mutation_results(reset)
    receipt = {
        "format": "lisp65-c2.2-link75-reset-domain-successor-receipt-v1",
        "recorded_on": "2026-07-28",
        "status": "passed-harness-reset-domain-correction-no-product-delta",
        "classification": "hardware-harness-First-Red",
        "finding": (
            "The canonical retry rebound only the 33840-byte C2D prefix. "
            "Its post-failure [33840,50816) suffix is byte-identical to the "
            "pre-clear diagnostic snapshot, so the run violated C4 before "
            "the first append."
        ),
        "correction": (
            "Bind and readback-verify the complete 50816-byte reset domain; "
            "require C2J zero before the product is released."
        ),
        "product_delta": 0,
        "new_product_link": False,
        "reset_domain": bind(RESET_DOMAIN, C2D_ADDRESS),
        "successor_deployment": bind(DEPLOYMENT),
        "authority": {
            "C4": bind(C4_RECEIPT),
            "superseded_deployment": bind(SOURCE_DEPLOYMENT),
        },
        "mutations": mutations,
        "next": (
            "Deploy this successor, prove C2J zero before start, mount the "
            "same D81, then rerun require-first."
        ),
    }
    replace_json(RECEIPT, receipt)
    return receipt


def verify() -> dict[str, Any]:
    reset = RESET_DOMAIN.read_bytes()
    deployment = load(DEPLOYMENT)
    receipt = load(RECEIPT)
    rows = [
        row for row in deployment["preloads"]
        if row["role"] == "c2d-v6-complete-reset-domain"
    ]
    require(
        reset == expected_reset_domain()
        and len(rows) == 1
        and rows[0]["bytes"] == REGION_BYTES
        and rows[0]["sha256"] == sha(RESET_DOMAIN)
        and deployment["cold_reset_contract"]["c2j"] == list(C2J)
        and receipt["status"]
            == "passed-harness-reset-domain-correction-no-product-delta"
        and receipt["product_delta"] == 0,
        "reset-domain successor verification failed",
    )
    mutations = mutation_results(reset)
    return {
        "status": "verified",
        "reset_domain_bytes": len(reset),
        "mutations": len(mutations),
        "product_delta": 0,
    }


def main() -> int:
    action = sys.argv[1:] or ["prepare"]
    require(action in (["prepare"], ["verify"]),
            "usage: c2_link75_reset_domain_successor.py [prepare|verify]")
    value = prepare() if action == ["prepare"] else verify()
    print("c2-link75-reset-domain-successor: "
          + json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SuccessorError as exc:
        print(f"c2-link75-reset-domain-successor: ERROR: {exc}",
              file=sys.stderr)
        raise SystemExit(2)
