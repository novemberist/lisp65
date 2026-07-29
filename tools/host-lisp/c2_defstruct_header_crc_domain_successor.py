#!/usr/bin/env python3
"""Qualify and link the Link-70 canonical L65I header-CRC successor."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_header_crc_successor as BASE  # noqa: E402


BASE.LINK = 71
BASE.ROOT_BUILD = (
    ROOT / "build/post-promotion/link71-defstruct-header-crc-domain")
BASE.PROBE_BUILD = BASE.ROOT_BUILD / "product-shaped-probe"
BASE.LINK_BUILD = BASE.ROOT_BUILD
BASE.WPLTO_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link71-defstruct-header-crc-domain-wplto-receipt.json")
BASE.LINK_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link71-defstruct-header-crc-domain-structural-receipt.json")
BASE.FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link70-require-header-crc-domain-hardware-first-red.json")
BASE.LINK69 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link70-defstruct-header-crc-structural-receipt.json")
BASE.EVIDENCE = BASE.WPLTO_RECEIPT.parent
BASE.DRIVER = Path(__file__).resolve()


if __name__ == "__main__":
    try:
        raise SystemExit(BASE.main())
    except (
        BASE.SuccessorError,
        BASE.PROBE.ProbeError,
        BASE.CAN.CanonicalError,
        BASE.SERVICE.GateError,
        BASE.SERVICE.ElfTruthError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as error:
        print(
            "c2-defstruct-header-crc-domain: FIRST RED: " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
