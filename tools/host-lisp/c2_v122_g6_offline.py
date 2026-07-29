#!/usr/bin/env python3
"""Verify the v1.2.2 C2-lite R6/G6 closure live or from its seal."""

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
    "359809d4a6b3bde95b9624f375ae38c32446ea54024a58691e07eb4673bcf7de"
)
VERIFY.PACKAGE_SET = (
    "129cbf443beb4433bcf87388c2131a8f084df3b2e812b21fb5893f008932d651"
)
VERIFY.R6_SHIP_REL = Path("build/c2.2/v1.2.2-acceptance/r6/ship")
VERIFY.R6_RECEIPT_REL = Path(
    "build/c2.2/v1.2.2-acceptance/r6/r6-packaging-receipt.json"
)
VERIFY.G6_SESSION_REL = Path(
    "build/c2.2/v1.2.2-acceptance/g6/session-01"
)
VERIFY.TOP_RELEASE_CLAIM = "not-promoted-until-remote-head-seal"
VERIFY.SEAL_RELEASE_CLAIM = "acceptance-sealed-v1.2.2-not-promoted"
VERIFY.RELEASE_LABEL = "v1.2.2-acceptance"


if __name__ == "__main__":
    raise SystemExit(VERIFY.main())
