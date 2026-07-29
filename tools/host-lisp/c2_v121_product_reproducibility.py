#!/usr/bin/env python3
"""Prove the v1.2.1 candidate media set in two varied fresh checkouts."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_product_reproducibility as BASE  # noqa: E402


BASE.GENERATOR = Path(__file__).resolve()
BASE.DEFAULT_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.1-media-fresh-clone-reproducibility-receipt.json")
BASE.FORMAT = "lisp65-c2-lite-v1.2.1-media-product-reproducibility-v1"
BASE.BUILD_COMMANDS = (
    (
        "python3",
        "tools/host-lisp/c2_v121_candidate_product.py",
        "build",
    ),
    (
        "python3",
        "tools/host-lisp/c2_v121_candidate_media.py",
        "build",
    ),
)
BASE.MEDIA_MANIFEST_RELATIVE = Path(
    "build/c2.2/v1.2.1-candidate-media/candidate-manifest.json")


if __name__ == "__main__":
    raise SystemExit(BASE.main())
