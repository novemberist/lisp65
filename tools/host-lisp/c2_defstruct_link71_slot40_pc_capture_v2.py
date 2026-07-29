#!/usr/bin/env python3
"""Capture the identity-preserving Slot-40 v2 error-edge hold PC."""

from __future__ import annotations

import json

import c2_defstruct_link71_slot40_failure_hold_v2 as HOLD
import c2_defstruct_link71_slot40_pc_capture as CAPTURE


CAPTURE.HOLD = HOLD
CAPTURE.OUT = HOLD.OUT
CAPTURE.PC_CAPTURE = HOLD.OUT / "pc-captures.json"
CAPTURE.SITE_BY_PC = {
    vma: name for name, vma in HOLD.V1.SITES
}


if __name__ == "__main__":
    try:
        raise SystemExit(CAPTURE.main())
    except (HOLD.HoldError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-defstruct-Link71-Slot40-PC-v2: FIRST RED: " + str(error))
        raise SystemExit(2)
