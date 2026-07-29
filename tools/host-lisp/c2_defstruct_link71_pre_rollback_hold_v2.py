#!/usr/bin/env python3
"""Bind the Link-71 pre-rollback hold to one explicitly mounted D81."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link71_pre_rollback_hold as BASE  # noqa: E402


OUT = BASE.BASE / "pre-rollback-hold-v2-media-bound-NONPROMOTABLE"
RECEIPT = (
    ROOT / "tests/fixtures/c2-migration-evidence"
    / "c2.2-link71-pre-rollback-hold-v2-media-bound-nonpromotable-receipt.json"
)
MEDIA = ROOT / "build/post-promotion/defstruct-v1/foundations/require-defstruct.d81"
MEDIA_SHA256 = "e8aaff363306477e5ccd2d6df2af1b81a982c643b08a0ad679f2db0304867f45"
REMOTE_MEDIA = "L71PRBH2.D81"


class V2Error(RuntimeError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise V2Error(f"object expected: {path}")
    return value


def write(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def configure() -> None:
    BASE.OUT = OUT
    BASE.PATCH = OUT / "pre-rollback-hold.bin"
    BASE.DEPLOYMENT = OUT / "deployment.json"
    BASE.RECEIPT = RECEIPT
    BASE.CAPTURE = OUT / "register-captures.json"


def prepare() -> dict[str, object]:
    configure()
    if sha(MEDIA) != MEDIA_SHA256:
        raise V2Error("require-defstruct D81 authority drift")
    BASE.prepare()
    receipt = load(RECEIPT)
    receipt.update({
        "format": "lisp65-c2.2-Link71-pre-rollback-hold-v2",
        "status": "ready-authorized-media-bound-nonpromotable-primary-failure-capture",
        "authority": {
            **receipt["authority"],
            "driver_v2": bind(Path(__file__).resolve()),
            "media": bind(MEDIA),
        },
        "supersedes_harness_run": {
            "v1_result": "discarded-wrong-mounted-medium",
            "observed_stage_bytes": 2374,
            "required_track_39_sector_1_bytes": 1925,
            "rule": "no product inference from the v1 capture",
        },
        "media_binding": {
            "remote_name": REMOTE_MEDIA,
            "operation": "upload-readback-mount-before-product-reset",
            "post_capture_witness": (
                "c2_append_state.length must equal the D81 PLACE chain length 1925"
            ),
        },
    })
    write(RECEIPT, receipt)
    deployment = load(BASE.DEPLOYMENT)
    deployment.update({
        "format": "lisp65-c2.2-Link71-pre-rollback-media-bound-deployment-v2",
        "remote_media": REMOTE_MEDIA,
        "media": bind(MEDIA),
    })
    deployment["authority"]["receipt"] = bind(RECEIPT)
    deployment["authority"]["driver_v2"] = bind(Path(__file__).resolve())
    write(BASE.DEPLOYMENT, deployment)
    return {
        "status": "ready",
        "media_sha256": sha(MEDIA),
        "remote_media": REMOTE_MEDIA,
        "patch_address": f"0x{BASE.PATCH_ADDRESS:04x}",
    }


def verify() -> dict[str, object]:
    configure()
    value = BASE.verify()
    receipt = load(RECEIPT)
    deployment = load(BASE.DEPLOYMENT)
    if (
        receipt["authority"]["media"] != bind(MEDIA)
        or deployment["media"] != bind(MEDIA)
        or deployment["remote_media"] != REMOTE_MEDIA
        or deployment["authority"]["receipt"] != bind(RECEIPT)
    ):
        raise V2Error("media-bound deployment drift")
    return {**value, "media_sha256": sha(MEDIA), "remote_media": REMOTE_MEDIA}


def capture() -> dict[str, object]:
    configure()
    verify()
    return BASE.capture()


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
    except (V2Error, BASE.HoldError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-defstruct-Link71-pre-rollback-hold-v2: FIRST RED: " + str(error))
        raise SystemExit(2)
