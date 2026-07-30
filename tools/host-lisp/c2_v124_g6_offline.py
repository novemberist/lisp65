#!/usr/bin/env python3
"""Verify the v1.2.4 C2-lite R6/G6 closure live or from its seal."""

from __future__ import annotations

from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
if (HERE / "payload").is_dir():
    REPOSITORY_ROOT = HERE / "payload"
else:
    REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "tools/host-lisp"))

import c2_lite_g6_offline as VERIFY  # noqa: E402


VERIFY.SCRIPT_ROOT = HERE
VERIFY.REPOSITORY_ROOT = REPOSITORY_ROOT
VERIFY.PRODUCT_SET = (
    "f686c8a78d7e65927740049e0b33c51f879613f21593b46be8342840c18093f8"
)
VERIFY.PACKAGE_SET = (
    "1fa8ef2494eeeff40e4456f80e007aa46cb30f1e876856aaed9ea225469c8eb6"
)
VERIFY.R6_SHIP_REL = Path("build/c2.2/v1.2.4-acceptance/r6/ship")
VERIFY.R6_RECEIPT_REL = Path(
    "build/c2.2/v1.2.4-acceptance/r6/r6-packaging-receipt.json"
)
VERIFY.G6_SESSION_REL = Path(
    "build/c2.2/v1.2.4-acceptance/g6/session-01"
)
VERIFY.TOP_RELEASE_CLAIM = "not-promoted-until-remote-head-seal"
VERIFY.SEAL_RELEASE_CLAIM = "acceptance-sealed-v1.2.4-not-promoted"
VERIFY.RELEASE_LABEL = "v1.2.4-acceptance"


if __name__ == "__main__":
    raise SystemExit(VERIFY.main())
