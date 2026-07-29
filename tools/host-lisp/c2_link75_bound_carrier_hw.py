#!/usr/bin/env python3
"""Bind the bundled carrier/require/defstruct hardware oracle to Link 75."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link69_hw as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CONFIG = ROOT / "config/c2.2-link75-bound-carrier-hardware-session.json"
LINK = EVIDENCE / (
    "c2.2-product-link75-bound-compiler-carrier-structural-receipt.json")
QUALIFIED_WPLTO = EVIDENCE / (
    "c2.2-link75-bound-compiler-carrier-wplto-receipt.json")
FOUNDATIONS = EVIDENCE / "c2.2-defstruct-foundations-gate-receipt.json"
MANIFEST = ROOT / (
    "build/post-promotion/link75-bound-compiler-carrier/"
    "canonical-product-manifest.json")
SOURCE_BOUND_PARITY = ROOT / (
    "build/post-promotion/link75-bound-compiler-carrier/receipts/"
    "bound-artifact-source-parity-final-post-check-source.json")
OUT = ROOT / os.environ.get(
    "C2_DEFSTRUCT_HW_OUT",
    "build/post-promotion/link75-bound-compiler-carrier/hardware-session")
RECEIPT = EVIDENCE / (
    "c2.2-link75-bound-carrier-require-defstruct-hardware-receipt.json")
HARNESS_FIRST_RED = EVIDENCE / (
    "c2.2-link75-bound-carrier-hardware-harness-first-red.json")
REMOTE_MEDIA = "L75CARR.D81"


def configure() -> None:
    BASE.CONFIG = CONFIG
    BASE.LINK = LINK
    BASE.FOUNDATIONS = FOUNDATIONS
    BASE.MANIFEST = MANIFEST
    BASE.OUT = OUT
    BASE.DEPLOYMENT = OUT / "deployment.json"
    BASE.OBSERVATIONS = OUT / "observed-rows.json"
    BASE.RECEIPT = RECEIPT
    BASE.HARNESS_FIRST_RED = HARNESS_FIRST_RED
    BASE.HARNESS_OUTPUT_RED = HARNESS_FIRST_RED


def prepare() -> None:
    BASE.prepare()
    deployment = BASE.load(BASE.DEPLOYMENT)
    deployment.update({
        "format": "lisp65-c2.2-link75-bound-carrier-deployment-v1",
        "remote_media": REMOTE_MEDIA,
        "media_transport":
            "upload/readback, run bound-carrier and DIRMISS rows, then "
            "manual Freezer mount and F3 return before require/defstruct",
    })
    deployment["authority"]["qualified_Link75_WPLTO"] = BASE.bind(
        QUALIFIED_WPLTO)
    deployment["authority"]["source_bound_artifact_parity"] = BASE.bind(
        SOURCE_BOUND_PARITY)
    deployment["authority"]["driver"] = BASE.bind(Path(__file__).resolve())
    BASE.write(BASE.DEPLOYMENT, deployment)
    observations = BASE.load(BASE.OBSERVATIONS)
    observations["format"] = (
        "lisp65-c2.2-link75-bound-carrier-observations-v1")
    BASE.write(BASE.OBSERVATIONS, observations)


def finalize() -> None:
    BASE.finalize()
    receipt = BASE.load(RECEIPT)
    receipt.update({
        "format":
            "lisp65-c2.2-link75-bound-carrier-require-defstruct-hardware-v1",
        "status":
            "passed-Link75-bound-carrier-require-defstruct-on-hardware",
    })
    receipt["candidate"]["link"] = 75
    receipt["evidence"]["qualified_Link75_WPLTO"] = BASE.bind(
        QUALIFIED_WPLTO)
    receipt["evidence"]["source_bound_artifact_parity"] = BASE.bind(
        SOURCE_BOUND_PARITY)
    receipt["evidence"]["driver"] = BASE.bind(Path(__file__).resolve())
    receipt["results"]["bound_carrier"] = {
        "recursive_prim68_reproducer": "t",
        "direct_intern": "abc",
    }
    receipt["results"]["dirmiss_full_name"] = {
        "symbol": "intern-renderer-missing",
        "observed": "*** undefined function: intern-renderer-missing",
        "seam": "VM-to-evaluator SYMI detail",
        "historical_exact_intern_recreated": False,
    }
    receipt["claim_limit"] = (
        "Link 75 bound compiler carrier and require/defstruct freight only. "
        "The full-name row proves the common SYMI renderer with a deliberate "
        "missing symbol; it does not claim an exact recreation of the now-"
        "unreachable stale-carrier call to intern. No promotion claim.")
    BASE.write(RECEIPT, receipt)


def main() -> int:
    configure()
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("prepare")
    record = sub.add_parser("record")
    record.add_argument("--id", required=True)
    record.add_argument("--screen", type=Path, required=True)
    compare = sub.add_parser("compare-repeat")
    compare.add_argument("--name", required=True)
    sub.add_parser("finalize")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "record":
        BASE.record(args.id, args.screen)
    elif args.action == "compare-repeat":
        BASE.compare_repeat(args.name)
    else:
        finalize()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BASE.HardwareError, KeyError, OSError) as error:
        print("c2-link75-bound-carrier-hw: FIRST RED: " + str(error))
        raise SystemExit(1)
