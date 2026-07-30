#!/usr/bin/env python3
"""Build/check the isolated v1.2.3 candidate from the current source tree."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v121_candidate_product as PRODUCT  # noqa: E402


PRODUCT.__doc__ = __doc__
PRODUCT.RELEASE = "v1.2.3"
PRODUCT.LINK = 80
PRODUCT.BUILD = ROOT / "build/c2.2/v1.2.3-candidate-product-link80"
PRODUCT.MANIFEST = PRODUCT.BUILD / "canonical-product-manifest.json"
PRODUCT.DRIVER = Path(__file__).resolve()
PRODUCT.V.EXPECTED_PRODUCT_ID = "0x7356f9e6"
PRODUCT.V.EXPECTED_BANK2_SHA = (
    "c193033d5f1e318b5c6b67e94b045e6848ebb57bef7e091abd3bf818dda3cf31"
)


if __name__ == "__main__":
    raise SystemExit(PRODUCT.main())
