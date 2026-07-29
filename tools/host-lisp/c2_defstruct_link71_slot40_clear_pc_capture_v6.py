#!/usr/bin/env python3
"""Capture the late-activated Slot-40 journal-clear discriminator PC."""

from __future__ import annotations

import json

import c2_defstruct_link71_slot40_clear_hold_v6 as HOLD
import c2_defstruct_link71_slot40_pc_capture as CAPTURE


CAPTURE.HOLD = HOLD
CAPTURE.OUT = HOLD.OUT
CAPTURE.PC_CAPTURE = HOLD.OUT / "pc-captures.json"
CAPTURE.SITE_BY_PC = {
    **{vma: name for name, vma in HOLD.V1.SITES},
    **{vma: name for name, vma, _before, _after in HOLD.CLEAR_SITES},
}


if __name__ == "__main__":
    try:
        raise SystemExit(CAPTURE.main())
    except (HOLD.HoldError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print("c2-defstruct-Link71-Slot40-clear-PC-v6: FIRST RED: "
              + str(error))
        raise SystemExit(2)
