#!/usr/bin/env python3
"""Build/check the v1.3.0 full-reset-domain successor as Link 85."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_v13_candidate_product as PREV  # noqa: E402


LINK = 85
BUILD = ROOT / "build/c2.3/v1.3.0-candidate-product-link85-r1"
MANIFEST = BUILD / "canonical-product-manifest.json"
DRIVER = Path(__file__).resolve()


def configure_successor() -> None:
    PREV.LINK = LINK
    PREV.BUILD = BUILD
    PREV.MANIFEST = MANIFEST
    PREV.DRIVER = DRIVER
    PREV.PRODUCT.LINK = LINK
    PREV.PRODUCT.BUILD = BUILD
    PREV.PRODUCT.MANIFEST = MANIFEST
    PREV.PRODUCT.DRIVER = DRIVER


def main() -> int:
    configure_successor()
    return PREV.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        PREV.CandidateError,
        RuntimeError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            f"c2-v1.3.0-link85-candidate-product: FIRST RED: {error}",
            file=sys.stderr,
        )
        raise SystemExit(2)
