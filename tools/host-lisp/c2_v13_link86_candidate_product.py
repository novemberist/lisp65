#!/usr/bin/env python3
"""Build/check the v1.3.0 Ship boot-timebase successor as Link 86."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_v13_candidate_product as PREV  # noqa: E402


LINK = 86
BUILD = ROOT / "build/c2.3/v1.3.0-candidate-product-link86-r1"
MANIFEST = BUILD / "canonical-product-manifest.json"
DRIVER = Path(__file__).resolve()
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CARD = EVIDENCE / "c2.3-v1.3-link86-boot-timebase-wplto-receipt.json"
BOOT = EVIDENCE / "c2.3-v1.3-ship-boot-inheritance-gate-receipt.json"


def configure_successor() -> None:
    PREV.LINK = LINK
    PREV.BUILD = BUILD
    PREV.MANIFEST = MANIFEST
    PREV.DRIVER = DRIVER
    PREV.CARD = CARD
    PREV.PRODUCT.LINK = LINK
    PREV.PRODUCT.BUILD = BUILD
    PREV.PRODUCT.MANIFEST = MANIFEST
    PREV.PRODUCT.DRIVER = DRIVER


def freight_gates() -> dict[str, Any]:
    summaries = {
        "banner": PREV.run(
            [sys.executable, "tools/host-lisp/c2_repl_banner_version_gate.py",
             "--selftest"], "v1.3 banner gate"),
        "input_wait": PREV.run(
            [sys.executable, "tools/host-lisp/c2_ship_input_wait_gate.py"],
            "v1.3 input/wait gate"),
        "boot_inheritance": PREV.run(
            [sys.executable, "tools/host-lisp/c2_ship_boot_inheritance_gate.py"],
            "v1.3 Ship boot-inheritance gate"),
        "q": PREV.run(
            [sys.executable, "tools/host-lisp/c2_q_gate.py"], "v1.3 q gate"),
        "editor": PREV.run(
            [sys.executable, "tools/host-lisp/c2_v126_editor_allocation_gate.py",
             "check"], "v1.3 editor allocation gate"),
        "surface": PREV.run(
            [sys.executable, "tools/host-lisp/v11_surface_delivery_parity.py"],
            "v1.3 surface-delivery parity"),
    }
    card = PREV.load(CARD)
    boot = PREV.load(BOOT)
    rebind = PREV.load(PREV.BANNER_REBIND)
    input_receipt = PREV.load(PREV.INPUT_RECEIPT)
    q_receipt = PREV.load(PREV.Q_RECEIPT)
    editor = PREV.load(PREV.EDITOR_RECEIPT)
    profile = PREV.load(PREV.PROFILE)
    PREV.require(
        card["status"]
            == "passed-Link86-boot-timebase-one-product-shaped-WPLTO"
        and card["wplto_probes_consumed"] == 1
        and card["workbench_owner"] == {
            "byteidentical_to_link85": True,
            "c2_kernal_take_ownership_bytes": 126,
            "noinit_address": "0xc34d",
            "noinit_bytes": 6,
            "overlay_floor": "0xc354",
        }
        and card["ship_runtime_price"]["runtime_delta_bytes"] == 116
        and boot["status"]
            == "passed-ship-boot-arms-and-verifies-inherited-io"
        and boot["host_execution"]["executions"] == 1
        and boot["mutation_count"] == 10
        and rebind["status"]
            == "passed-linker-free-regular-v1.3-banner-identity-rebind"
        and input_receipt["status"]
            == "passed-bank2-lisp-source-artifact-allocation-and-execution"
        and q_receipt["status"].startswith("passed-")
        and editor["status"] == "passed"
        and profile["product_build_id"] == PREV.EXPECTED_PRODUCT_ID
        and profile["bank2_static_code"]["sha256"] == PREV.EXPECTED_BANK2_SHA,
        "Link-86 freight authority drift",
    )
    return {
        "mode": "v1.3-Ship-boot-timebase-successor",
        "summaries": summaries,
        "input_wait": PREV.bind(PREV.INPUT_RECEIPT),
        "q": PREV.bind(PREV.Q_RECEIPT),
        "editor": PREV.bind(PREV.EDITOR_RECEIPT),
        "accepted_native_geometry": PREV.bind(CARD),
        "regular_banner_identity": PREV.bind(PREV.BANNER_REBIND),
        "boot_inheritance": PREV.bind(BOOT),
    }


def main() -> int:
    configure_successor()
    PREV.freight_gates = freight_gates
    return PREV.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        PREV.CandidateError, RuntimeError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            f"c2-v1.3.0-link86-candidate-product: FIRST RED: {error}",
            file=sys.stderr,
        )
        raise SystemExit(2)
