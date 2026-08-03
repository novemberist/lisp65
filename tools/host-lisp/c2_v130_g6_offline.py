#!/usr/bin/env python3
"""Verify the v1.3.0 C2-lite R6/G6 closure live or from its seal."""

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
    "072ca89affc35bdf0e20cab382e8bd4a9df64babf535e23f6b2e268962daed1f"
)
VERIFY.PACKAGE_SET = (
    "3e0db21adb825cfa44c60bd005f2644a3717f4fcc5b02ae87e1139d3188a3397"
)
VERIFY.R6_SHIP_REL = Path("build/c2.3/v1.3.0-acceptance/r6/ship")
VERIFY.R6_RECEIPT_REL = Path(
    "build/c2.3/v1.3.0-acceptance/r6/r6-packaging-receipt.json"
)
VERIFY.G6_SESSION_REL = Path(
    "build/c2.3/v1.3.0-acceptance/g6/session-01"
)
VERIFY.TOP_RELEASE_CLAIM = "not-promoted-until-remote-head-seal"
VERIFY.SEAL_RELEASE_CLAIM = "acceptance-sealed-v1.3.0-not-promoted"
VERIFY.RELEASE_LABEL = "v1.3.0-acceptance"


if __name__ == "__main__":
    raise SystemExit(VERIFY.main())
