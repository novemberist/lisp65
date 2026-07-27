#!/usr/bin/env python3
"""Run C1 Cutpoints 3/4 on the post-shelf Link-62 product identity."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_c1_freezer_carrier_link62 as CARRIER  # noqa: E402
import c2_c1_freezer_hw_fixture_link60 as BASE  # noqa: E402


M = BASE.M
LINK = CARRIER.LINK
LINK_RECEIPT = CARRIER.LINK_RECEIPT
CARRIER_DIR = CARRIER.OUT
CARRIER_RECEIPT = CARRIER.RECEIPT
PRODUCT_SHA = (
    "85fc3cad0eded7fd6a9079194a25b59415d86f2eb99ccec7d684ac756a831b3f")
OUT = ROOT / (
    "build/c2.2/"
    "c1-freezer-hardware-link62-cutpoints3-4-NONPROMOTABLE")
HARDWARE_RECEIPT = CARRIER.EVIDENCE / (
    "c2.2-link62-C1-Freezer-four-cutpoint-hardware-receipt.json")
DEPLOYMENT_STATUS = "ready-nonpromotable-Link62-cutpoints-3-and-4"
CARRIER_STATUS = "passed-Link62-capacity-and-gates-awaiting-hardware"
CARRIER_BASENAME = (
    "runtime-overlays-session-c1-freezer-link62-stage-bound.bin")
CARRIER_REGION1_BASENAME = (
    "runtime-overlays-session-c1-freezer-link62-region1.bin")


def current_paths() -> dict[str, Path]:
    artifacts = M.read_json(M.ARTIFACTS)
    shelf = ROOT / artifacts["artifacts"]["shelf"]["path"]
    return {
        "product": LINK / "lisp65-c2-substitution-linked.prg",
        "elf": LINK / "lisp65-c2-substitution-linked.prg.elf",
        "window": LINK / "c2-product-kernal-window.bin",
        "boot_family": LINK / "runtime-overlays-boot-final.bin",
        "session_family": CARRIER_DIR / CARRIER_BASENAME,
        "session_region1": CARRIER_DIR / CARRIER_REGION1_BASENAME,
        "shelf": shelf,
        "c2d": (
            LINK / "fresh-c2-lite-prelink-gates/v6-semantics/"
            "initial.c2d-v6.bin"),
        "bank2_static": (
            LINK / "fresh-c2-lite-prelink-gates/v6-semantics/"
            "bank2-static-code.bin"),
        "contract": LINK / "resolved-profile.txt",
        "stage_header": LINK / "stage-config.h",
    }


def current_authority() -> dict[str, Path]:
    paths = current_paths()
    for name, path in paths.items():
        M.require(path.is_file(), f"missing Link-62 {name}: {path}")
    replay = M.read_json(LINK_RECEIPT)
    carrier = M.read_json(CARRIER_RECEIPT)
    contract = M.read_json(M.CONTRACT)
    artifacts = M.read_json(M.ARTIFACTS)
    boot_manifest = M.read_json(
        LINK / "runtime-overlays-boot-final.json")
    M.require(
        M.sha(paths["product"]) == PRODUCT_SHA
        and replay["status"] == "passed-link62-pure-full-replay-all-gates-green"
        and replay["authority"]["product"]["sha256"] == PRODUCT_SHA
        and carrier["status"] == CARRIER_STATUS
        and carrier["construction"]["product_bytes_changed"] == 0
        and carrier["construction"]["resident_bytes_changed"] == 0
        and carrier["construction"]["main_region_size_delta"] == 0
        and carrier["construction"]["region1_size_delta"] == 0
        and carrier["construction"]["main_family_crc16"] == "0x8d75"
        and carrier["construction"]["region1_byteidentical_Link62"]
        and carrier["proof"]["post_RTS_tail"]["bytes"] == 6
        and carrier["proof"]["post_shelf_region1"][
            "durable_source"] == "0x08300000"
        and contract["status"] == "owner-reviewed-fixture-contract"
        and contract["hardware_protocol"]["freezer_roundtrips"] == 4
        and boot_manifest["storage"]["size"] == 19269
        and boot_manifest["storage"]["crc16"] == 0x1D2D
        and [row["name"] for row in boot_manifest["slices"]][-4:] == [
            "c2-decode-03b", "bank3-stage-session",
            "resident-island-installer", "resident-island-image"]
        and artifacts["artifacts"]["shelf"]["sha256"]
            == M.sha(paths["shelf"])
        and M.sha(paths["session_region1"]) == BASE.CARRIER_BUILD.OVERFLOW_SHA,
        "Link-62 C1 fixture authority is incomplete")
    M.HW.verify_c2d_product_identity(paths, M.ARTIFACTS)
    return paths


def configure() -> None:
    BASE.LINK = LINK
    BASE.LINK_RECEIPT = LINK_RECEIPT
    BASE.CARRIER = CARRIER_DIR
    BASE.CARRIER_BASENAME = CARRIER_BASENAME
    BASE.CARRIER_REGION1_BASENAME = CARRIER_REGION1_BASENAME
    BASE.CARRIER_RECEIPT = CARRIER_RECEIPT
    BASE.CARRIER_STATUS = CARRIER_STATUS
    BASE.PRODUCT_SHA = PRODUCT_SHA
    BASE.OUT = OUT
    BASE.HARDWARE_RECEIPT = HARDWARE_RECEIPT
    BASE.DEPLOYMENT_STATUS = DEPLOYMENT_STATUS
    BASE.ACTIVE_LINK_LABEL = "Link62"
    BASE.current_paths = current_paths
    BASE.current_authority = current_authority

    M.LINK = LINK
    M.LINK_RECEIPT = LINK_RECEIPT
    M.PRODUCT_SHA = PRODUCT_SHA
    M.CARRIER = CARRIER_DIR
    M.CARRIER_BASENAME = CARRIER_BASENAME
    M.CARRIER_RECEIPT = CARRIER_RECEIPT
    M.CARRIER_RECEIPT_STATUS = CARRIER_STATUS
    M.DEPLOYMENT_STATUS = DEPLOYMENT_STATUS
    M.OUT = OUT
    M.HARDWARE_RECEIPT = HARDWARE_RECEIPT
    M.paths = current_paths
    M.validate_authority = current_authority


def main() -> int:
    configure()
    original = BASE.configure
    BASE.configure = configure
    try:
        return BASE.main()
    finally:
        BASE.configure = original


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(
            "c2-c1-freezer-hw-fixture-link62: FAIL " + str(error),
            file=sys.stderr)
        raise SystemExit(2)
