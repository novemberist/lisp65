#!/usr/bin/env python3
"""Bind the crossed Link-108 D1 phase-1 observation without a product claim."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v21_product_liveness_d1 as D1  # noqa: E402


RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.1-product-liveness-d1-first-red-receipt.json")
DECODER = ROOT / (
    "build/c2.3/v2.1-product-loading-liveness-card/wplto/"
    "generated-product-sources/c2-stream-decoder.c")
CPU_PREFLIGHT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.1-cpu-transport-preflight-receipt.json")
OLD_RING = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-loading-libraries-progress-map-device-receipt.json")


class FirstRedError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FirstRedError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def derive(owner_report: str) -> dict[str, Any]:
    prep = load(D1.PREP)
    D1.validate_preparation(prep, verify=True)
    text_path = D1.OUT / "product-boot.txt"
    image_path = D1.OUT / "product-boot.png"
    text = text_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"LISP65:\s*LOADING LIBRARIES\s*([0-9A-F])", text,
                      flags=re.IGNORECASE)
    require(match is not None and match.group(1).upper() == "1",
            "Link-108 crossed capture is not phase 1")
    require("WORKBENCH 1.5.0" not in text and "lisp65>" not in text,
            "Link-108 crossed capture unexpectedly terminal")
    config = load(D1.CONFIG)
    product = ROOT / config["identity"]["product_medium"]
    library = ROOT / config["identity"]["library_medium"]
    require((D1.OUT / "product-readback.d81").read_bytes() == product.read_bytes(),
            "Link-108 product readback drift")
    require((D1.OUT / "library-readback.d81").read_bytes() == library.read_bytes(),
            "Link-108 library readback drift")

    decoder = DECODER.read_text(encoding="utf-8")
    require("catalog != c->image_count * 32u" in decoder
            and "c->image_count > 64u" in decoder
            and "shelf_crc32(32u, catalog, &crc)" in decoder,
            "phase-1 catalog/CRC bound drift")
    preflight = load(CPU_PREFLIGHT)
    crc = preflight["crc"]
    require(crc["maximum_admitted_bytes"] == 64
            and crc["pessimistic_seconds_at_40MHz"] < 0.001,
            "CRC static ceiling drift")
    ring = load(OLD_RING)
    require(ring["stopped_code_identity"]["symbol"] == "crc32_update"
            and "not by itself a loop proof" in
                ring["stopped_code_identity"]["interpretation"],
            "historical CRC PC claim boundary drift")

    return {
        "format": "lisp65-c2.3-v2.1-product-liveness-d1-first-red-v1",
        "recorded_on": "2026-08-15",
        "status": "D1-HARNESS-FIRST-RED-PHASE-1-CROSSED; NO-PRODUCT-LOOP-CLAIM",
        "authority": {"preparation": bind(D1.PREP), "media": bind(D1.MEDIA),
            "decoder": bind(DECODER), "CPU_transport_preflight": bind(CPU_PREFLIGHT),
            "historical_progress_ring": bind(OLD_RING)},
        "transport": {"product_source": bind(product),
            "product_readback": bind(D1.OUT / "product-readback.d81"),
            "library_source": bind(library),
            "library_readback": bind(D1.OUT / "library-readback.d81"),
            "result": "byteidentical-both-media"},
        "crossed_observation": {"access_free_seconds_before_capture": 45,
            "automated_post_boot_captures": 1, "phase_ordinal": 1,
            "terminal_banner": False, "terminal_prompt": False,
            "text": bind(text_path), "image": bind(image_path),
            "owner_report_after_capture": owner_report,
            "owner_duration_bound": "several-minutes-unquantified"},
        "desk_bound": {"phase": "c2_stream_phase_01",
            "work": "shelf header plus complete catalog CRC",
            "maximum_catalog_bytes": 64 * 32,
            "transport_block_bytes": 32,
            "normal_multi-minute_price_excluded": True,
            "historical_PC_correlation": "crc32_update only; not a loop proof"},
        "execution_accounting": {"hardware_contacts": 1,
            "post_boot_automated_captures": 1, "stops": 0, "resumes": 0,
            "forms": 0, "product_links": 0, "WPLTO_runs": 0},
        "unlock": {"D1": False, "D2_D5": False},
        "claim_limit": (
            "Phase 1 remained physically visible for several minutes, but the "
            "45-second automated screenshot crossed the active persistent boot "
            "phase. This contact proves neither a product hang nor a loop. The "
            "next contact must perform zero automated post-boot observation."),
        "next": "crossing-free owner-visible D1 successor; no device access authorized",
    }


def validate(value: dict[str, Any]) -> None:
    require(value.get("status") ==
            "D1-HARNESS-FIRST-RED-PHASE-1-CROSSED; NO-PRODUCT-LOOP-CLAIM"
            and value.get("transport", {}).get("result") ==
                "byteidentical-both-media"
            and value.get("crossed_observation", {}).get("phase_ordinal") == 1
            and value.get("crossed_observation", {}).get(
                "automated_post_boot_captures") == 1
            and value.get("desk_bound", {}).get(
                "normal_multi-minute_price_excluded") is True
            and value.get("unlock") == {"D1": False, "D2_D5": False},
            "Link-108 D1 First Red claim drift")


def selftest() -> None:
    value = derive("continues at LIBRARIES 1 after several minutes")
    validate(value)
    mutations = {
        "claim-loop": ("status", "D1-PRODUCT-LOOP"),
        "erase-capture": ("crossed_observation.automated_post_boot_captures", 0),
        "open-D2": ("unlock.D2_D5", True),
        "invent-normal-price": ("desk_bound.normal_multi-minute_price_excluded", False),
    }
    rejected = []
    for name, (path, replacement) in mutations.items():
        trial = deepcopy(value); target: Any = trial
        parts = path.split(".")
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = replacement
        try:
            validate(trial)
        except FirstRedError:
            rejected.append(name)
    require(rejected == list(mutations), "Link-108 First Red mutation survived")
    print(f"Link 108 D1 First Red: SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "record", "check"))
    parser.add_argument("--owner-report", default="")
    args = parser.parse_args()
    if args.action == "selftest":
        selftest()
    elif args.action == "record":
        require(args.owner_report != "", "record requires --owner-report")
        require(not RECEIPT.exists(), "Link-108 First Red receipt exists")
        value = derive(args.owner_report); validate(value)
        RECEIPT.write_bytes(canonical(value))
        print("Link 108 D1: HARNESS FIRST RED phase=1 D2-D5=CLOSED")
    else:
        validate(load(RECEIPT))
        print("Link 108 D1 First Red: CHECK PASS D2-D5=CLOSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FirstRedError, D1.D1Error, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"LINK 108 D1 FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
