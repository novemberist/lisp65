#!/usr/bin/env python3
"""Bind the Link-71 pre-rollback hold to canonical-identity defstruct media."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link71_pre_rollback_hold_v2 as V2  # noqa: E402


OUT = ROOT / (
    "build/post-promotion/link71-defstruct-product-identity-"
    "pre-rollback-hold-NONPROMOTABLE")
RECEIPT = ROOT / (
    "tests/fixtures/c2-migration-evidence/"
    "c2.2-link71-product-identity-pre-rollback-hold-"
    "nonpromotable-receipt.json")
MEDIA = ROOT / (
    "build/post-promotion/link71-defstruct-product-identity-media-rebind/"
    "require-defstruct-product-bound.d81")
REBIND = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link71-defstruct-product-identity-media-rebind-receipt.json")
FIRST_RED = ROOT / (
    "build/post-promotion/link71-defstruct-product-identity-hardware-replay-v2/"
    "first-red-product-identity-passed")
REMOTE_MEDIA = "L71IDF2.D81"
MEDIA_SHA256 = "0e14ac686d661e4df35c4514bf6d43b201575940ac20bd17d597d4ff12ff2b32"


class ProductIdentityHoldError(RuntimeError):
    pass


def configure() -> None:
    V2.OUT = OUT
    V2.RECEIPT = RECEIPT
    V2.MEDIA = MEDIA
    V2.MEDIA_SHA256 = MEDIA_SHA256
    V2.REMOTE_MEDIA = REMOTE_MEDIA


def prepare() -> dict[str, object]:
    configure()
    value = V2.prepare()
    receipt = V2.load(RECEIPT)
    receipt.update({
        "format":
            "lisp65-c2.2-Link71-product-identity-pre-rollback-hold-v1",
        "status":
            "ready-canonical-media-nonpromotable-primary-failure-capture",
        "authority": {
            **receipt["authority"],
            "product_identity_rebind": V2.bind(REBIND),
            "post_rollback_First_Red": {
                "phase_scratch": V2.bind(FIRST_RED / "phase-scratch.bin"),
                "C2J": V2.bind(FIRST_RED / "c2j.bin"),
                "C2D": V2.bind(FIRST_RED / "c2d.bin"),
                "screen": V2.bind(FIRST_RED / "screen.png"),
            },
            "driver_product_identity": V2.bind(Path(__file__).resolve()),
        },
        "supersedes_harness_runs": {
            "v1": "discarded-unbound-mounted-medium",
            "v2": "discarded-second-reset-restored-prior-mount",
            "v3": (
                "authoritative old-media capture proved envelope build-ID "
                "mismatch at slot 23"
            ),
            "current_question": (
                "which primary phase fails after the canonical build-ID "
                "correction passes slot 23"
            ),
        },
        "media_binding": {
            **receipt["media_binding"],
            "remote_name": REMOTE_MEDIA,
            "operation":
                "reuse already uploaded/read-back/mounted canonical media "
                "from the stopped First-Red session",
        },
    })
    V2.write(RECEIPT, receipt)
    deployment = V2.load(V2.BASE.DEPLOYMENT)
    deployment.update({
        "format":
            "lisp65-c2.2-Link71-product-identity-pre-rollback-deployment-v1",
        "remote_media": REMOTE_MEDIA,
        "test": {"form": "(%disk-load-lib 39 1)"},
    })
    deployment["authority"]["receipt"] = V2.bind(RECEIPT)
    deployment["authority"]["product_identity_rebind"] = V2.bind(REBIND)
    deployment["authority"]["driver_product_identity"] = V2.bind(
        Path(__file__).resolve())
    V2.write(V2.BASE.DEPLOYMENT, deployment)
    return {
        **value,
        "status": "ready-canonical-media-current-session",
        "remote_media": REMOTE_MEDIA,
    }


def verify() -> dict[str, object]:
    configure()
    value = V2.verify()
    receipt = V2.load(RECEIPT)
    deployment = V2.load(V2.BASE.DEPLOYMENT)
    if (
        receipt["authority"]["product_identity_rebind"] != V2.bind(REBIND)
        or deployment["media"] != V2.bind(MEDIA)
        or deployment["test"]["form"] != "(%disk-load-lib 39 1)"
    ):
        raise ProductIdentityHoldError(
            "canonical-media hold deployment drift")
    return {**value, "remote_media": REMOTE_MEDIA}


def capture() -> dict[str, object]:
    configure()
    verify()
    return V2.capture()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "verify", "capture"))
    action = parser.parse_args().action
    value = (
        prepare() if action == "prepare"
        else verify() if action == "verify"
        else capture())
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ProductIdentityHoldError, V2.V2Error, V2.BASE.HoldError, OSError,
        ValueError, KeyError, json.JSONDecodeError,
    ) as error:
        print(
            "c2-defstruct-Link71-product-identity-pre-rollback: FIRST RED: "
            + str(error))
        raise SystemExit(2)
