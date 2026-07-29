#!/usr/bin/env python3
"""Capture the late-activated identity-preserving Slot-39 hold PC."""

from __future__ import annotations

import json

import c2_defstruct_link71_slot39_failure_hold as CAPTURE
import c2_defstruct_link71_slot39_failure_hold_v2 as HOLD


CAPTURE.OUT = HOLD.OUT
CAPTURE.CARRIER = HOLD.CARRIER
CAPTURE.PATCH_RECEIPT = HOLD.PATCH_RECEIPT
CAPTURE.DEPLOYMENT = HOLD.DEPLOYMENT
CAPTURE.PC_CAPTURE = HOLD.PC_CAPTURE
CAPTURE.verify = HOLD.verify


if __name__ == "__main__":
    try:
        value = CAPTURE.capture_pc()
        print(json.dumps(value, sort_keys=True))
    except (HOLD.HoldError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-defstruct-Link71-Slot39-PC-v2: FIRST RED: " + str(error))
        raise SystemExit(2)
