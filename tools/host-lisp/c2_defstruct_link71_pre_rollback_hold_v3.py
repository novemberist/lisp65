#!/usr/bin/env python3
"""Bind the Link-71 hold to mount-reset-before-load ordering."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link71_pre_rollback_hold_v2 as V2  # noqa: E402


OUT = V2.BASE.BASE / "pre-rollback-hold-v3-mount-preserved-NONPROMOTABLE"
RECEIPT = (
    ROOT / "tests/fixtures/c2-migration-evidence"
    / "c2.2-link71-pre-rollback-hold-v3-mount-preserved-nonpromotable-receipt.json"
)
REMOTE_MEDIA = "L71PRBH3.D81"


class V3Error(RuntimeError):
    pass


def configure() -> None:
    V2.OUT = OUT
    V2.RECEIPT = RECEIPT
    V2.REMOTE_MEDIA = REMOTE_MEDIA


def prepare() -> dict[str, object]:
    configure()
    value = V2.prepare()
    receipt = V2.load(RECEIPT)
    receipt.update({
        "format": "lisp65-c2.2-Link71-pre-rollback-hold-v3",
        "status": "ready-mount-reset-before-product-load-nonpromotable",
        "authority": {
            **receipt["authority"],
            "driver_v3": V2.bind(Path(__file__).resolve()),
        },
        "supersedes_harness_runs": {
            "v1": "discarded-unbound-mounted-medium",
            "v2": (
                "discarded-media-upload-was-followed-by-a-second-reset-that-"
                "restored-the-prior-mount"
            ),
            "observed_stage_bytes_both_runs": 2374,
            "required_track_39_sector_1_bytes": 1925,
            "rule": "no product inference from v1 or v2",
        },
        "media_binding": {
            **receipt["media_binding"],
            "remote_name": REMOTE_MEDIA,
            "operation": (
                "FTP upload-readback-mount performs its reset first; product "
                "and preloads are then installed without a second -F reset"
            ),
        },
    })
    V2.write(RECEIPT, receipt)
    deployment = V2.load(V2.BASE.DEPLOYMENT)
    deployment.update({
        "format": "lisp65-c2.2-Link71-pre-rollback-mount-preserved-deployment-v3",
        "remote_media": REMOTE_MEDIA,
    })
    deployment["authority"]["receipt"] = V2.bind(RECEIPT)
    deployment["authority"]["driver_v3"] = V2.bind(Path(__file__).resolve())
    V2.write(V2.BASE.DEPLOYMENT, deployment)
    return {**value, "status": "ready-mount-preserved", "remote_media": REMOTE_MEDIA}


def verify() -> dict[str, object]:
    configure()
    value = V2.verify()
    receipt = V2.load(RECEIPT)
    deployment = V2.load(V2.BASE.DEPLOYMENT)
    if (
        receipt["format"] != "lisp65-c2.2-Link71-pre-rollback-hold-v3"
        or deployment["remote_media"] != REMOTE_MEDIA
        or deployment["authority"]["receipt"] != V2.bind(RECEIPT)
    ):
        raise V3Error("mount-preserved deployment drift")
    return {**value, "remote_media": REMOTE_MEDIA}


def capture() -> dict[str, object]:
    configure()
    verify()
    return V2.capture()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "verify", "capture"))
    action = parser.parse_args().action
    value = prepare() if action == "prepare" else verify() if action == "verify" else capture()
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (V3Error, V2.V2Error, V2.BASE.HoldError, OSError, ValueError,
            KeyError, json.JSONDecodeError) as error:
        print("c2-defstruct-Link71-pre-rollback-hold-v3: FIRST RED: " + str(error))
        raise SystemExit(2)
