#!/usr/bin/env python3
"""Capture the post-boot Slot-40 v5 discriminator PC."""

from __future__ import annotations

import json

import c2_defstruct_link71_slot40_failure_hold_v4 as HOLD
import c2_defstruct_link71_slot40_failure_hold_v5 as LATE
import c2_defstruct_link71_slot40_pc_capture as CAPTURE


CAPTURE.HOLD = HOLD
CAPTURE.OUT = LATE.OUT
CAPTURE.PC_CAPTURE = LATE.OUT / "pc-captures.json"
CAPTURE.SITE_BY_PC = {
    **{vma: name for name, vma in HOLD.V1.SITES},
    HOLD.COMMON_HOLD_VMA: "dispatcher-or-publish-entry-precondition",
}


if __name__ == "__main__":
    try:
        raise SystemExit(CAPTURE.main())
    except (HOLD.HoldError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-defstruct-Link71-Slot40-PC-v5: FIRST RED: " + str(error))
        raise SystemExit(2)
