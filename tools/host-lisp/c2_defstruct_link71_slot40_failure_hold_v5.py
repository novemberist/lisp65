#!/usr/bin/env python3
"""Bind late activation of the complete Slot-40 v4 discriminator.

Slot 40 is deliberately called once with a null context during startup.  A
global entry-precondition hold therefore stops that expected boot probe.
This deployment boots pristine Link 71 first, then replaces only the Attic
Session-family source with the already identity-preserving v4 carrier.  The
next explicit ``%disk-load-lib`` call is consequently the first execution of
the instrumented Slot 40.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_link71_slot40_failure_hold as V1  # noqa: E402
import c2_defstruct_link71_slot40_failure_hold_v2 as V2  # noqa: E402
import c2_defstruct_link71_slot40_failure_hold_v4 as V4  # noqa: E402


HoldError = V1.HoldError
require = V1.require
write_json = V1.write_json

OUT = V1.BASE / "slot40-failure-hold-v5-late-NONPROMOTABLE"
DEPLOYMENT = OUT / "deployment.json"
RECEIPT = V1.EVIDENCE / (
    "c2.2-link71-slot40-failure-hold-v5-late-nonpromotable-receipt.json")


def prepare() -> dict[str, Any]:
    V4.verify()
    base = V1.load(V1.BASE_DEPLOYMENT)
    source = V1.data(V1.SOURCE)
    candidate = V1.data(V4.CARRIER)
    require(len(source) == len(candidate), "late carrier size drift")
    require(V1.data(V2.ZERO_C2J) == bytes(64),
            "canonical zero-C2J preload drift")
    boot_preloads = [dict(row) for row in base["preloads"]]
    boot_preloads.append({
        **V1.bind(V2.ZERO_C2J, 0x0005C640),
        "role": "known-zero-C2J-diagnostic-baseline",
    })
    V1.write_json(RECEIPT, {
        "format": "lisp65-c2.2-Link71-slot40-failure-hold-late-v1",
        "recorded_on": "2026-07-27",
        "status": "ready-nonpromotable-post-boot-Slot40-discriminator",
        "promotable": False,
        "authority": {
            "source_deployment": V1.bind(V1.BASE_DEPLOYMENT),
            "carrier_v4_receipt": V1.bind(V4.RECEIPT),
            "carrier_v4": V1.bind(V4.CARRIER, 0x08000000),
            "driver": V1.bind(Path(__file__).resolve()),
        },
        "boot_probe_finding": {
            "stable_PC": "0xc3f7",
            "context_pointer": "0x0000",
            "C2J": "all zero",
            "meaning": (
                "startup intentionally reaches Slot 40 with null context; "
                "the broad v4 entry-precondition hold must therefore be "
                "activated only after the pristine boot reaches its REPL"),
        },
        "activation": {
            "order": [
                "boot pristine Link 71 with pristine Session family",
                "prove clean REPL",
                "replace only Attic Session-family source at 0x08000000 "
                "with the v4 carrier and read it back byte-identically",
                "invoke (%disk-load-lib 39 1) exactly once",
            ],
            "product_bytes_delta": 0,
            "carrier_bytes_delta": 0,
            "new_product_links": 0,
        },
        "claim_limit": (
            "Nonpromotable Link-71 Slot-40 attribution only; require and "
            "defstruct remain unqualified."),
    })
    V1.write_json(DEPLOYMENT, {
        "format": "lisp65-c2.2-Link71-slot40-failure-hold-late-deployment-v1",
        "recorded_on": "2026-07-27",
        "status": "ready-authorized-nonpromotable-hardware",
        "promotable": False,
        "authority": {
            "receipt": V1.bind(RECEIPT),
            "source_deployment": V1.bind(V1.BASE_DEPLOYMENT),
        },
        "product": base["product"],
        "media": base["media"],
        "remote_media": base["remote_media"],
        "boot_preloads": boot_preloads,
        "late_preload": {
            **V1.bind(V4.CARRIER, 0x08000000),
            "role": "post-boot-identity-preserving-Slot40-discriminator",
        },
        "test": {"form": "(%disk-load-lib 39 1)"},
        "execution_accounting": {
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs": 0,
        },
    })
    return {
        "status": "ready",
        "carrier_sha256": hashlib.sha256(candidate).hexdigest(),
        "boot_carrier_sha256": hashlib.sha256(source).hexdigest(),
    }


def verify() -> dict[str, Any]:
    V4.verify()
    receipt = V1.load(RECEIPT)
    deployment = V1.load(DEPLOYMENT)
    require(
        deployment["authority"]["receipt"]["sha256"]
        == hashlib.sha256(V1.data(RECEIPT)).hexdigest()
        and deployment["late_preload"]["sha256"]
        == hashlib.sha256(V1.data(V4.CARRIER)).hexdigest(),
        "late deployment binding drift")
    for row in deployment["boot_preloads"] + [deployment["late_preload"]]:
        path = ROOT / row["path"]
        require(
            len(V1.data(path)) == row["bytes"]
            and hashlib.sha256(V1.data(path)).hexdigest() == row["sha256"],
            f"late deployment artifact drift: {path}")
    return {
        "status": "verified",
        "late_carrier_sha256": deployment["late_preload"]["sha256"],
    }


def main() -> int:
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    require(action in ("prepare", "verify"), "usage: prepare|verify")
    value = prepare() if action == "prepare" else verify()
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            HoldError) as error:
        print(f"c2-defstruct-Link71-Slot40-hold-v5: FIRST RED: {error}")
        raise SystemExit(2)
