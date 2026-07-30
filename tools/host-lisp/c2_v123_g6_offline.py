#!/usr/bin/env python3
"""Verify the v1.2.3 C2-lite R6/G6 closure live or from its seal."""

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
    "e71cc4f46068a1c5ebebf050a76fb14717c03a27e954d0bbaacd95a70970e315"
)
VERIFY.PACKAGE_SET = (
    "5691dd8011042713b953d0d132f0b3d42b13b7e7e5550d8e200186c97574643e"
)
VERIFY.R6_SHIP_REL = Path("build/c2.2/v1.2.3-acceptance/r6/ship")
VERIFY.R6_RECEIPT_REL = Path(
    "build/c2.2/v1.2.3-acceptance/r6/r6-packaging-receipt.json"
)
VERIFY.G6_SESSION_REL = Path(
    "build/c2.2/v1.2.3-acceptance/g6/session-01"
)
VERIFY.TOP_RELEASE_CLAIM = "not-promoted-until-remote-head-seal"
VERIFY.SEAL_RELEASE_CLAIM = "acceptance-sealed-v1.2.3-not-promoted"
VERIFY.RELEASE_LABEL = "v1.2.3-acceptance"


if __name__ == "__main__":
    raise SystemExit(VERIFY.main())
