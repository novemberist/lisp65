#!/usr/bin/env python3
"""Bind the bundled require/defstruct hardware oracle to Link 73."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link69_hw as BASE  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CONFIG = ROOT / (
    "config/c2.2-defstruct-link73-vm-codebuf-owner-hardware-session.json")
LINK = EVIDENCE / (
    "c2.2-product-link73-vm-codebuf-owner-structural-receipt.json")
QUALIFIED_WPLTO = EVIDENCE / (
    "c2.2-link73-vm-codebuf-owner-wplto-receipt.json")
FOUNDATIONS = EVIDENCE / (
    "c2.2-link71-defstruct-session-record-identity-media-rebind-receipt.json")
MANIFEST = ROOT / (
    "build/post-promotion/link73-vm-codebuf-owner/"
    "canonical-product-manifest.json")
OUT = ROOT / os.environ.get(
    "C2_DEFSTRUCT_HW_OUT",
    "build/post-promotion/link73-vm-codebuf-owner/hardware-session")
RECEIPT = EVIDENCE / (
    "c2.2-link73-require-defstruct-vm-codebuf-owner-hardware-receipt.json")
HARNESS_FIRST_RED = EVIDENCE / (
    "c2.2-link73-require-defstruct-vm-codebuf-owner-harness-first-red.json")
REMOTE_MEDIA = "L73OWN.D81"


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
        "format": "lisp65-c2.2-link73-vm-codebuf-owner-deployment-v1",
        "remote_media": REMOTE_MEDIA,
        "media_transport":
            "upload/readback, focused intern preflight, then manual Freezer "
            "mount and F3 return before require/defstruct rows",
    })
    deployment["authority"]["qualified_Link73_WPLTO"] = BASE.bind(
        QUALIFIED_WPLTO)
    deployment["authority"]["driver"] = BASE.bind(Path(__file__).resolve())
    BASE.write(BASE.DEPLOYMENT, deployment)
    observations = BASE.load(BASE.OBSERVATIONS)
    observations["format"] = (
        "lisp65-c2.2-link73-vm-codebuf-owner-observations-v1")
    BASE.write(BASE.OBSERVATIONS, observations)


def finalize() -> None:
    BASE.finalize()
    receipt = BASE.load(RECEIPT)
    receipt.update({
        "format":
            "lisp65-c2.2-link73-require-defstruct-vm-codebuf-owner-"
            "hardware-v1",
        "status":
            "passed-Link73-require-defstruct-and-vm-codebuf-owner-on-hardware",
    })
    receipt["candidate"]["link"] = 73
    receipt["evidence"]["qualified_Link73_WPLTO"] = BASE.bind(
        QUALIFIED_WPLTO)
    receipt["evidence"]["driver"] = BASE.bind(Path(__file__).resolve())
    receipt["claim_limit"] = (
        "Link 73 vm_codebuf owner-lifetime correction and require/defstruct "
        "freight only; no promotion or unrelated library claim.")
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
        print("c2-defstruct-link73-owner-hw: FIRST RED: " + str(error))
        raise SystemExit(1)
