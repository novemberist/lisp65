#!/usr/bin/env python3
"""Package/check the v1.3.0 Link-85 full-reset-domain media."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_lite_canonical_product as CAN  # noqa: E402
import c2_lite_media_product as MEDIA  # noqa: E402
import c2_v13_link85_candidate_product as PRODUCT  # noqa: E402


BUILD = ROOT / "build/c2.3/v1.3.0-candidate-media-link85-r1"
MANIFEST = BUILD / "candidate-manifest.json"


def configure() -> None:
    PRODUCT.configure_successor()
    PRODUCT.PREV.configure()
    CAN.MANIFEST = PRODUCT.MANIFEST
    MEDIA.CANONICAL = CAN
    MEDIA.BUILD = BUILD
    MEDIA.PRODUCT_MANIFEST = PRODUCT.MANIFEST
    MEDIA.MANIFEST = MANIFEST
    MEDIA.DESCRIPTOR = BUILD / "boot.id"
    MEDIA.STAGER = BUILD / "autoboot.c65"
    MEDIA.STAGER_MAP = BUILD / "autoboot.c65.map"
    MEDIA.PRODUCT_D81 = BUILD / "lisp65-product.d81"
    MEDIA.WORK_D81 = BUILD / "lisp65-work.d81"
    MEDIA.MOUNT = BUILD / "lisp65-product.mount.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check"))
    args = parser.parse_args()
    configure()
    value = MEDIA.build() if args.action == "build" else MEDIA.check()
    if args.action == "build":
        MEDIA.check()
    print(
        "c2-v1.3.0-link85-candidate-media: PASS "
        f"artifacts={value['artifact_count']} "
        f"set={value['artifact_set_sha256']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        MEDIA.MediaError,
        CAN.CanonicalError,
        RuntimeError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            f"c2-v1.3.0-link85-candidate-media: FIRST RED: {error}",
            file=sys.stderr,
        )
        raise SystemExit(2)
