#!/usr/bin/env python3
"""Bind the generic defstruct hardware oracle to successor Link 70."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link69_hw as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CONFIG = ROOT / "config/c2.2-defstruct-link70-hardware-session.json"
LINK = EVIDENCE / (
    "c2.2-product-link70-defstruct-header-crc-structural-receipt.json")
QUALIFIED_WPLTO = EVIDENCE / (
    "c2.2-link70-defstruct-header-crc-wplto-receipt.json")
FIRST_RED = EVIDENCE / (
    "c2.2-link69-require-header-crc-hardware-first-red.json")
MANIFEST = ROOT / (
    "build/post-promotion/link70-defstruct-header-crc/"
    "canonical-product-manifest.json")
OUT = ROOT / (
    "build/post-promotion/link70-defstruct-header-crc/hardware-session")
RECEIPT = EVIDENCE / "c2.2-link70-require-defstruct-hardware-receipt.json"


def configure() -> None:
    BASE.CONFIG = CONFIG
    BASE.LINK = LINK
    BASE.MANIFEST = MANIFEST
    BASE.OUT = OUT
    BASE.DEPLOYMENT = OUT / "deployment.json"
    BASE.OBSERVATIONS = OUT / "observed-rows.json"
    BASE.RECEIPT = RECEIPT
    BASE.HARNESS_FIRST_RED = FIRST_RED
    BASE.HARNESS_OUTPUT_RED = FIRST_RED


def prepare() -> None:
    BASE.prepare()
    deployment = BASE.load(BASE.DEPLOYMENT)
    deployment.update({
        "format": "lisp65-c2.2-link70-defstruct-deployment-v1",
        "remote_media": "L70DEF.D81",
    })
    deployment["authority"]["qualified_header_CRC_WPLTO"] = BASE.bind(
        QUALIFIED_WPLTO)
    deployment["authority"]["header_CRC_hardware_First_Red"] = BASE.bind(
        FIRST_RED)
    deployment["authority"]["driver"] = BASE.bind(Path(__file__).resolve())
    BASE.write(BASE.DEPLOYMENT, deployment)
    observations = BASE.load(BASE.OBSERVATIONS)
    observations["format"] = "lisp65-c2.2-link70-defstruct-observations-v1"
    BASE.write(BASE.OBSERVATIONS, observations)


def finalize() -> None:
    BASE.finalize()
    receipt = BASE.load(RECEIPT)
    receipt.update({
        "format": "lisp65-c2.2-link70-require-defstruct-hardware-v1",
        "status": "passed-Link70-require-defstruct-on-hardware",
    })
    receipt["candidate"]["link"] = 70
    receipt["evidence"]["qualified_header_CRC_WPLTO"] = BASE.bind(
        QUALIFIED_WPLTO)
    receipt["evidence"]["header_CRC_hardware_First_Red"] = BASE.bind(
        FIRST_RED)
    receipt["evidence"]["driver"] = BASE.bind(Path(__file__).resolve())
    receipt["claim_limit"] = (
        "Link 70 require/defstruct freight qualification only; no "
        "promotion, release or unrelated library claim.")
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
    except (
        BASE.HardwareError, KeyError, OSError,
    ) as error:
        print(f"c2-defstruct-link70-hw: FIRST RED: {error}")
        raise SystemExit(1)
