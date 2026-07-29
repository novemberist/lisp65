#!/usr/bin/env python3
"""Capture the complete Slot-40 v4 discriminator hold PC and state."""

from __future__ import annotations

import json

import c2_defstruct_link71_slot40_failure_hold_v4 as HOLD
import c2_defstruct_link71_slot40_pc_capture as CAPTURE


CAPTURE.HOLD = HOLD
CAPTURE.OUT = HOLD.OUT
CAPTURE.PC_CAPTURE = HOLD.OUT / "pc-captures.json"
CAPTURE.SITE_BY_PC = {
    **{vma: name for name, vma in HOLD.V1.SITES},
    HOLD.COMMON_HOLD_VMA: "dispatcher-or-publish-entry-precondition",
}


if __name__ == "__main__":
    try:
        raise SystemExit(CAPTURE.main())
    except (HOLD.HoldError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-defstruct-Link71-Slot40-PC-v4: FIRST RED: " + str(error))
        raise SystemExit(2)
