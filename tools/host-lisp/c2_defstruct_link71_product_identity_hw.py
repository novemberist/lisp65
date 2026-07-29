#!/usr/bin/env python3
"""Bind the Link-71 hardware oracle to canonically identity-bound media."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link69_hw as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CONFIG = ROOT / "config/c2.2-defstruct-link71-product-identity-replay.json"
LINK = EVIDENCE / (
    "c2.2-product-link71-defstruct-header-crc-domain-structural-receipt.json")
QUALIFIED_WPLTO = EVIDENCE / (
    "c2.2-link71-defstruct-header-crc-domain-wplto-receipt.json")
REBIND = EVIDENCE / (
    "c2.2-link71-defstruct-product-identity-media-rebind-receipt.json")
MANIFEST = ROOT / (
    "build/post-promotion/link71-defstruct-header-crc-domain/"
    "canonical-product-manifest.json")
OUT = ROOT / os.environ.get(
    "C2_DEFSTRUCT_IDENTITY_OUT",
    "build/post-promotion/link71-defstruct-product-identity-hardware-replay")
RECEIPT = ROOT / os.environ.get(
    "C2_DEFSTRUCT_IDENTITY_RECEIPT",
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link71-defstruct-product-identity-hardware-receipt.json")
HARNESS_FIRST_RED = EVIDENCE / (
    "c2.2-link71-defstruct-product-identity-hardware-harness-first-red.json")
REMOTE_MEDIA = os.environ.get("C2_DEFSTRUCT_IDENTITY_REMOTE", "L71IDFIX.D81")


def configure() -> None:
    BASE.CONFIG = CONFIG
    BASE.LINK = LINK
    BASE.FOUNDATIONS = REBIND
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
        "format":
            "lisp65-c2.2-link71-defstruct-product-identity-deployment-v1",
        "remote_media": REMOTE_MEDIA,
        "media_transport":
            "upload/readback/mount before product load; later loads preserve "
            "the mounted canonical-identity medium",
    })
    deployment["authority"]["product_identity_rebind"] = BASE.bind(REBIND)
    deployment["authority"]["qualified_Link71_WPLTO"] = BASE.bind(
        QUALIFIED_WPLTO)
    deployment["authority"]["driver"] = BASE.bind(Path(__file__).resolve())
    BASE.write(BASE.DEPLOYMENT, deployment)
    observations = BASE.load(BASE.OBSERVATIONS)
    observations["format"] = (
        "lisp65-c2.2-link71-defstruct-product-identity-observations-v1")
    BASE.write(BASE.OBSERVATIONS, observations)


def finalize() -> None:
    BASE.finalize()
    receipt = BASE.load(RECEIPT)
    receipt.update({
        "format":
            "lisp65-c2.2-link71-defstruct-product-identity-hardware-v1",
        "status":
            "passed-Link71-canonical-product-identity-require-defstruct-"
            "on-hardware",
    })
    receipt["candidate"]["link"] = 71
    receipt["evidence"]["product_identity_rebind"] = BASE.bind(REBIND)
    receipt["evidence"]["qualified_Link71_WPLTO"] = BASE.bind(
        QUALIFIED_WPLTO)
    receipt["evidence"]["driver"] = BASE.bind(Path(__file__).resolve())
    receipt["claim_limit"] = (
        "Link 71 require/defstruct freight and canonical product-bound media "
        "qualification only; no promotion, release or unrelated library "
        "claim.")
    BASE.write(RECEIPT, receipt)


def main() -> int:
    configure()
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("prepare")
    record = sub.add_parser("record")
    record.add_argument("--id", required=True)
    record.add_argument("--screen", type=Path, required=True)
    sub.add_parser("finalize")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "record":
        BASE.record(args.id, args.screen)
    else:
        finalize()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BASE.HardwareError, KeyError, OSError) as error:
        print(
            "c2-defstruct-link71-product-identity-hw: FIRST RED: "
            + str(error))
        raise SystemExit(1)
