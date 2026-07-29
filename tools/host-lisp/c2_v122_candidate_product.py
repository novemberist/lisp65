#!/usr/bin/env python3
"""Build/check the isolated v1.2.2 candidate derived from Link 78."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v121_candidate_product as PRODUCT  # noqa: E402


PRODUCT.RELEASE = "v1.2.2"
PRODUCT.LINK = 78
PRODUCT.BUILD = ROOT / "build/c2.2/v1.2.2-candidate-product"
PRODUCT.MANIFEST = PRODUCT.BUILD / "canonical-product-manifest.json"
PRODUCT.DRIVER = Path(__file__).resolve()


if __name__ == "__main__":
    raise SystemExit(PRODUCT.main())
