#!/usr/bin/env python3
"""Bind the current C2D-v6 direct-entry/root-surrogate source truth.

The historical C2-lite receipt predates the v6 root-surrogate harness branch.
This Class-A authority reruns the same target code with that branch enabled,
requires the configured direct-reference census and four negative classes, and attributes
the sole source rebind to the contract harness.  It creates no product bytes.
"""

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
import c2_direct_entry_contract as DIRECT  # noqa: E402


HISTORICAL = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-direct-entry-contract-receipt.json")
HISTORICAL_SHA = (
    "2777b476653d668cce6df6cf03a6722e84968a255995299db52133d2159cfdf2")
BUILD = ROOT / "build/c2.2/direct-entry-contract-v6-real-abi-canonical"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-c2-lite-v6-phase-self-stamp-direct-entry-contract-receipt.json")
EXPECTED_DIRECT_REFS = 637
EXPECTED_CHANGED_BINDINGS = {
    "normalized_plane", "target_contract_harness",
    "target_decoder", "target_resolved_plane",
}
PUBLIC_CLEAN_BUILD = False


def configure_from_environment() -> None:
    """Carry canonical artifact authority into CLI selftest subprocesses."""
    profile_path = os.environ.get("LISP65_DIRECT_ENTRY_PROFILE")
    if not profile_path:
        return
    profile = json.loads(Path(profile_path).read_text(encoding="utf-8"))
    DIRECT.SHELF = Path(os.environ["LISP65_DIRECT_ENTRY_SHELF"])
    DIRECT.C2D = Path(os.environ["LISP65_DIRECT_ENTRY_C2D"])
    DIRECT.ARTIFACTS = Path(os.environ["LISP65_DIRECT_ENTRY_ARTIFACTS"])
    DIRECT.EXPECTED_GEOMETRY = {
        "images": int(profile["images"]),
        "entries": int(profile["entries"]),
        "resolutions": int(profile["resolutions"]),
        "roots": int(profile["roots"]),
        "images_offset": 48,
    }
    global BUILD, RECEIPT, EXPECTED_DIRECT_REFS, EXPECTED_CHANGED_BINDINGS
    global PUBLIC_CLEAN_BUILD
    BUILD = Path(os.environ["LISP65_DIRECT_ENTRY_BUILD"])
    RECEIPT = Path(os.environ["LISP65_DIRECT_ENTRY_RECEIPT"])
    EXPECTED_DIRECT_REFS = int(
        os.environ["LISP65_DIRECT_ENTRY_EXPECTED_REFS"])
    DIRECT.EXPECTED_DIRECT_REFS = EXPECTED_DIRECT_REFS
    EXPECTED_CHANGED_BINDINGS = set(filter(
        None,
        os.environ[
            "LISP65_DIRECT_ENTRY_EXPECTED_CHANGED_BINDINGS"].split(",")))
    PUBLIC_CLEAN_BUILD = (
        os.environ.get("LISP65_DIRECT_ENTRY_PUBLIC_CLEAN_BUILD") == "1")


configure_from_environment()


class ContractError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ContractError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def value() -> dict[str, Any]:
    old_build = DIRECT.BUILD
    try:
        DIRECT.BUILD = BUILD
        fresh = DIRECT.collect()
    finally:
        DIRECT.BUILD = old_build
    historical: dict[str, Any] | None = None
    differences: dict[str, Any] = {}
    if not PUBLIC_CLEAN_BUILD:
        require(HISTORICAL.is_file() and sha(HISTORICAL) == HISTORICAL_SHA,
                "historical C2-lite direct-entry authority drift")
        historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))
        differences = {
            key: {"historical": historical["bindings"].get(key),
                  "current_v6": fresh["bindings"].get(key)}
            for key in sorted(
                set(historical["bindings"]) | set(fresh["bindings"]))
            if historical["bindings"].get(key) != fresh["bindings"].get(key)
        }
        require(set(differences) == EXPECTED_CHANGED_BINDINGS,
                f"unexpected current-v6 direct-entry rebind surface: "
                f"{sorted(differences)}")
    parity = fresh["cross_parity"]
    require(parity["direct_entry_references"] == EXPECTED_DIRECT_REFS
            and parity["fixnum_decodable_published_values"] == 0
            and parity["target_phase12_negative_classes"] == 4,
            "current-v6 direct-entry semantic closure red")
    result = {
        **fresh,
        "format": "lisp65-c2-lite-v6-real-abi-direct-entry-contract-v1",
        "recorded_on": "2026-07-22",
        "status": "passed-current-v6-root-surrogate-direct-entry-contract",
        "driver": bind(Path(__file__)),
        "rebind_attribution": {
            "changed_bindings": differences,
            "changed_binding_count": len(differences),
            "product_source_changes": 0 if PUBLIC_CLEAN_BUILD else 1,
            "reason": (
                "Fresh public builds validate the current generated plane "
                "directly; private historical rebind receipts are acceptance "
                "evidence, not build inputs."
                if PUBLIC_CLEAN_BUILD else
                "The target harness now contains the already-authorized "
                "C2D-v6 root-surrogate fixture branch while this preprojection "
                "run deliberately exercises its unchanged v5/default branch. "
                "The target decoder additionally carries the approved "
                f"provenance-only cold phase self-stamps; the {EXPECTED_DIRECT_REFS} resolved "
                "values and all four negative classes remain identical. "
                "The normalized and resolved planes live in a new evidence "
                "directory; the changed binding set is explicitly pinned "
                "for the active product plane. The generated "
                "product gate separately exercises the v6 branch after link."),
        },
        "role": (
            "Current pre-projection v6 direct-entry authority for Link 39. "
            f"The final product gate reruns all {EXPECTED_DIRECT_REFS} references after linking."),
        "claim_limit": (
            "Host-only direct-entry/root-surrogate contract replay. No product "
            "bytes, capacity, product link, hardware, latency or promotion."),
        "next_gate": "The unconsumed owner-authorized Link-39 replay may run.",
    }
    result["historical_c2_lite_receipt"] = (
        "acceptance-evidence-not-a-public-build-input"
        if PUBLIC_CLEAN_BUILD else bind(HISTORICAL))
    return result


def canonical(value_: dict[str, Any]) -> bytes:
    return (json.dumps(value_, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    data = canonical(value())
    if args.action == "write":
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        if RECEIPT.exists():
            os.chmod(RECEIPT, 0o644)
        RECEIPT.write_bytes(data)
        os.chmod(RECEIPT, 0o444)
        verb = "WROTE"
    elif args.action == "check":
        require(RECEIPT.is_file() and RECEIPT.read_bytes() == data,
                "current-v6 direct-entry receipt drift")
        verb = "PASS"
    else:
        verb = "SELFTEST PASS"
    print("c2-lite-v6-real-abi-direct-entry-contract: " + verb
          + f" refs={EXPECTED_DIRECT_REFS} fixnums=0 target-negatives=4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
