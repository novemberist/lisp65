#!/usr/bin/env python3
"""Run the bundled Link-66 C1 appointment with a passive Slot-39 witness."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_c1_bundled_session_carrier_link66 as CARRIER  # noqa: E402
import c2_c1_freezer_hw_fixture_link60 as BASE  # noqa: E402


M = BASE.M
LINK = CARRIER.LINK
LINK_RECEIPT = CARRIER.LINK_RECEIPT
CARRIER_DIR = CARRIER.OUT
CARRIER_RECEIPT = CARRIER.RECEIPT
PRODUCT_SHA = CARRIER.PRODUCT_SHA
OUT = ROOT / (
    "build/c2.2/"
    "c1-bundled-session-hardware-link66-NONPROMOTABLE")
HARDWARE_RECEIPT = CARRIER.EVIDENCE / (
    "c2.2-link66-C1-bundled-session-hardware-receipt.json")
DEPLOYMENT_STATUS = "ready-nonpromotable-Link66-bundled-session"
CARRIER_STATUS = (
    "passed-Link66-bundled-session-capacity-and-gates-awaiting-hardware")
CARRIER_BASENAME = (
    "runtime-overlays-session-c1-bundled-link66-stage-bound.bin")
CARRIER_REGION1_BASENAME = (
    "runtime-overlays-session-c1-bundled-link66-region1.bin")
WITNESS = {
    "stage": "0x17e2",
    "mode": "0x17e3",
    "reader": "0x17e4",
    "attempts": "0x17e5",
    "observed_crc": "0x17e6",
    "expected_crc": "0x17e8",
    "frame_start": "0x17ea",
    "frame_end": "0x17ec",
}


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
        M.require(path.is_file(), f"missing bundled Link-66 {name}: {path}")
    replay = M.read_json(LINK_RECEIPT)
    carrier = M.read_json(CARRIER_RECEIPT)
    contract = M.read_json(M.CONTRACT)
    artifacts = M.read_json(M.ARTIFACTS)
    boot_manifest = M.read_json(LINK / "runtime-overlays-boot-final.json")
    witness = carrier["proof"]["completion_observation"]["passive_witness"]
    M.require(
        M.sha(paths["product"]) == PRODUCT_SHA
        and replay["status"]
        == "passed-link66-single-submit-completion-product-identity-"
           "hardware-not-run"
        and replay["authority"]["product"]["sha256"] == PRODUCT_SHA
        and replay["gates"]["single_submit_completion_ELF"]
        == "passed-linked-stateless-mode-derived-completion-length"
        and replay["gates"]["complete_assembler_leaf_ABI"]
        == "passed-all-assembler-leaf-abi-contracts"
        and carrier["status"] == CARRIER_STATUS
        and carrier["construction"]["product_bytes_changed"] == 0
        and carrier["construction"]["resident_bytes_changed"] == 0
        and carrier["construction"]["main_region_size_delta"] == 0
        and carrier["construction"]["region1_size_delta"] == 0
        and carrier["construction"]["main_family_crc16"] == "0x206a"
        and carrier["construction"]["region1_byteidentical_Link66"]
        and carrier["proof"]["post_RTS_tail"]["bytes"] >= 2
        and witness == {
            name: address + "u" for name, address in WITNESS.items()
        }
        and carrier["proof"]["post_shelf_region1"][
            "durable_source"] == "0x08300000"
        and carrier["proof"]["completion_observation"][
            "reader_submit_count"] == 1
        and contract["status"] == "owner-reviewed-fixture-contract"
        and contract["hardware_protocol"]["freezer_roundtrips"] == 4
        and boot_manifest["storage"]["size"] == 19269
        and boot_manifest["storage"]["crc16"] == 0x4761
        and artifacts["artifacts"]["shelf"]["sha256"]
            == M.sha(paths["shelf"])
        and M.sha(paths["session_region1"])
            == BASE.CARRIER_BUILD.OVERFLOW_SHA,
        "bundled Link-66 C1 fixture authority is incomplete")
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
    BASE.ACTIVE_LINK_LABEL = "Link66"
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


def prepare(out: Path) -> None:
    BASE.prepare(out)
    path = out / "deployment.json"
    os.chmod(path, 0o644)
    deployment = M.read_json(path)
    deployment["format"] = (
        "lisp65-c2.2-C1-Freezer-Link66-bundled-hardware-fixture-v1")
    deployment["status"] = DEPLOYMENT_STATUS
    deployment["bundled_session"] = {
        "order": [
            "defun-smoke",
            "cutpoint-3-F3-return",
            "cutpoint-4-F3-return",
            "acceptance-measurement-lines-while-green",
        ],
        "passive_slot39_witness": WITNESS,
        "witness_policy": (
            "If defun fails before Cutpoint 3, read the witness in this same "
            "appointment; do not schedule a separate diagnostic deployment."),
        "C1_endpoint": (
            "A new error class ends pursuit: retain Cutpoints 1/2 and idle "
            "Freezer as proven, document Freezer-during-definition as a C2.3 "
            "restriction, then start the acceptance chain."),
        "physical_Freezer_return_key": "F3",
    }
    path.write_text(
        json.dumps(deployment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(path, 0o444)
    print(
        "c2-c1-bundled-session-hw-fixture-link66: PREPARE PASS "
        "order=defun,cp3,cp4,acceptance hardware=not-run")


def verify(out: Path) -> None:
    BASE.verify(out)
    deployment = M.read_json(out / "deployment.json")
    M.require(
        deployment["status"] == DEPLOYMENT_STATUS
        and deployment["bundled_session"]["order"] == [
            "defun-smoke",
            "cutpoint-3-F3-return",
            "cutpoint-4-F3-return",
            "acceptance-measurement-lines-while-green",
        ]
        and deployment["bundled_session"]["passive_slot39_witness"] == WITNESS
        and deployment["bundled_session"][
            "physical_Freezer_return_key"] == "F3",
        "bundled hardware appointment protocol drift")
    print(
        "c2-c1-bundled-session-hw-fixture-link66: VERIFY PASS "
        "hardware=not-run next=single-device-appointment")


def main() -> int:
    configure()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=(
            "prepare", "verify", "observe-boot", "observe-hold",
            "observe-thaw", "confirm-output"))
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--cutpoint", type=int, choices=(3, 4))
    parser.add_argument("--freezer-output")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        out = args.out.resolve()
        if args.mode == "prepare":
            prepare(out)
        elif args.mode == "verify":
            verify(out)
        elif args.mode == "observe-boot":
            BASE.observe_boot(out)
        elif args.mode == "observe-hold":
            M.require(args.cutpoint is not None, "--cutpoint is required")
            M.observe_hold(out, args.cutpoint)
        elif args.mode == "observe-thaw":
            M.require(args.cutpoint is not None, "--cutpoint is required")
            M.require(
                args.freezer_output is not None,
                "--freezer-output is required")
            M.observe_thaw(out, args.cutpoint, args.freezer_output)
        else:
            M.require(args.cutpoint is not None, "--cutpoint is required")
            M.require(args.output is not None, "--output is required")
            BASE.confirm_output(out, args.cutpoint, args.output)
    except (
        M.FixtureError, M.HW.PreSmokeError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-c1-bundled-session-hw-fixture-link66: FIRST RED: "
            + str(error))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
