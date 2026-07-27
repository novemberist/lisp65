#!/usr/bin/env python3
"""Run Link-60 C1 cutpoints 3/4 with accepted cutpoints 1/2."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_c1_freezer_carrier_link60 as CARRIER_BUILD  # noqa: E402
import c2_c1_freezer_hw_fixture as M  # noqa: E402
import runtime_overlay_bank as R  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK = CARRIER_BUILD.LINK
LINK_RECEIPT = CARRIER_BUILD.LINK_RECEIPT
CARRIER = CARRIER_BUILD.OUT
CARRIER_BASENAME = (
    "runtime-overlays-session-c1-freezer-link60-stage-bound.bin")
CARRIER_REGION1_BASENAME = (
    "runtime-overlays-session-c1-freezer-link60-region1.bin")
CARRIER_RECEIPT = CARRIER_BUILD.RECEIPT
CARRIER_STATUS = (
    "passed-capacity-and-gates-awaiting-separate-hardware-run")
OUT = ROOT / (
    "build/c2.2/"
    "c1-freezer-hardware-link60-cutpoints3-4-NONPROMOTABLE")
PRIOR_STATE = ROOT / (
    "build/c2.2/"
    "c1-freezer-memory-hold-hardware-link58-attempt5-NONPROMOTABLE/"
    "hardware-state.json")
PRIOR_FIRST_RED = EVIDENCE / (
    "c2.2-link58-C1-Freezer-memory-hold-cutpoint3-"
    "continuation-hardware-first-red.json")
PRODUCT_SHA = CARRIER_BUILD.PRODUCT_SHA
LINK58_SHA = (
    "4bab8371aa54060bef4ab9493e12dd6afd230baeb83a11f07daccdaa05000e6f")
HARDWARE_RECEIPT = EVIDENCE / (
    "c2.2-link60-C1-Freezer-four-cutpoint-hardware-receipt.json")
DEPLOYMENT_STATUS = (
    "ready-nonpromotable-Link60-cutpoints-3-and-4")
ACTIVE_LINK_LABEL = "Link60"
ARTIFACTS = M.ARTIFACTS


def current_paths() -> dict[str, Path]:
    artifacts = M.read_json(ARTIFACTS)
    shelf = ROOT / artifacts["artifacts"]["shelf"]["path"]
    return {
        "product": LINK / "lisp65-c2-substitution-linked.prg",
        "elf": LINK / "lisp65-c2-substitution-linked.prg.elf",
        "window": LINK / "c2-product-kernal-window.bin",
        "boot_family": LINK / "runtime-overlays-boot-final.bin",
        "session_family": CARRIER / CARRIER_BASENAME,
        "session_region1": CARRIER / CARRIER_REGION1_BASENAME,
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
        M.require(path.is_file(), f"missing Link-60 {name}: {path}")
    link = M.read_json(LINK_RECEIPT)
    carrier = M.read_json(CARRIER_RECEIPT)
    contract = M.read_json(M.CONTRACT)
    artifacts = M.read_json(ARTIFACTS)
    M.require(
        M.sha(paths["product"]) == PRODUCT_SHA
        and link["status"]
        == "passed-link60-two-region-E000-S1-product-identity-hardware-not-run"
        and link["product_identity"]["product"]["sha256"] == PRODUCT_SHA
        and carrier["status"] == CARRIER_STATUS
        and carrier["construction"]["product_bytes_changed"] == 0
        and carrier["construction"]["resident_bytes_changed"] == 0
        and carrier["construction"]["main_region_size_delta"] == 0
        and carrier["construction"]["region1_size_delta"] == 0
        and carrier["construction"]["main_family_crc16"] == "0x7753"
        and carrier["construction"]["region1_byteidentical_Link60"]
        and contract["status"] == "owner-reviewed-fixture-contract"
        and contract["link60_successor_authority"]["sha256"] == PRODUCT_SHA
        and contract["hardware_protocol"]["freezer_roundtrips"] == 4
        and M.FIRST_RED_RECEIPT.is_file()
        and M.ZERO_JOURNAL_FIRST_RED_RECEIPT.is_file()
        and M.CROSS_IDENTITY_FIRST_RED_RECEIPT.is_file()
        and artifacts["artifacts"]["shelf"]["sha256"]
            == M.sha(paths["shelf"])
        and M.sha(paths["session_region1"]) == CARRIER_BUILD.OVERFLOW_SHA,
        "Link-60 C1 fixture authority is incomplete")
    M.HW.verify_c2d_product_identity(paths, ARTIFACTS)
    return paths


def configure() -> None:
    M.LINK = LINK
    M.LINK_RECEIPT = LINK_RECEIPT
    M.PRODUCT_SHA = PRODUCT_SHA
    M.CARRIER = CARRIER
    M.CARRIER_BASENAME = CARRIER_BASENAME
    M.CARRIER_RECEIPT = CARRIER_RECEIPT
    M.CARRIER_RECEIPT_STATUS = CARRIER_STATUS
    M.DEPLOYMENT_STATUS = DEPLOYMENT_STATUS
    M.OUT = OUT
    M.HARDWARE_RECEIPT = HARDWARE_RECEIPT
    M.paths = current_paths
    M.validate_authority = current_authority


def accepted_prior() -> list[dict[str, Any]]:
    M.require(
        PRIOR_STATE.is_file() and PRIOR_FIRST_RED.is_file(),
        "accepted predecessor cutpoint-1/2 authority is absent")
    state = M.read_json(PRIOR_STATE)
    rows = deepcopy(state["cutpoints"][:2])
    M.require(
        state["product_sha256"] == LINK58_SHA
        and [row["id"] for row in rows] == [1, 2]
        and all(row["status"] == "passed" for row in rows)
        and all(row["operator_call_output"] == "t" for row in rows),
        "accepted predecessor cutpoint-1/2 authority drift")
    for row in rows:
        row["accepted_predecessor_identity"] = LINK58_SHA
        row["evidence_origin"] = M.bind(PRIOR_FIRST_RED)
    return rows


def prepare(out: Path) -> None:
    accepted_prior()
    M.prepare(out)
    deployment_path = out / "deployment.json"
    os.chmod(deployment_path, 0o644)
    deployment = M.read_json(deployment_path)
    deployment["format"] = (
        f"lisp65-c2.2-C1-Freezer-{ACTIVE_LINK_LABEL}-v4-"
        "hardware-fixture-v1")
    deployment["status"] = DEPLOYMENT_STATUS
    deployment["authority"][f"{ACTIVE_LINK_LABEL.lower()}_receipt"] = deployment[
        "authority"].pop("link58_receipt")
    deployment["authority"]["accepted_predecessor_cutpoints_1_2"] = M.bind(
        PRIOR_FIRST_RED)
    deployment["protocol"] = {
        "accepted_predecessor_cutpoints": [1, 2],
        f"current_{ACTIVE_LINK_LABEL}_appointment_cutpoints": [3, 4],
        "return_from_Freezer_key": "F3",
        "cutpoint_3_requirement":
            "episode latch accepts one source-less return IRQ after each "
            "real raster IRQ and still rejects two consecutive source-less IRQs",
        "cutpoint_4_requirement":
            "all CPU-to-Chip writes converge before rollback wipe/bookkeeping; "
            "Bank2, Bank3 and Bank5 return byte-identically to baseline",
        "hold_carrier":
            "fresh load of 0x17e0 on every loop iteration; no register-resume "
            "assumption",
        "virtual_keyboard_form":
            "quoted t is transported as (quote t); the m65 apostrophe path "
            "is not an input authority",
        "autorun_submission":
            "if and only if a pre-boot screen shows standalone BASIC run: "
            "without lisp65>, inject one explicit RETURN",
        "v4_regions": {
            "main_source": "0x08000000",
            "overflow_source":
                f"0x{R.REGION1_SOURCE_BASE:08x}",
            "overflow_target":
                f"0x{R.REGION1_RUNTIME_SOURCE_BASE:08x}",
            "overflow_byteidentical_product": True,
        },
    }
    deployment["execution_accounting"][
        "accepted_predecessor_device_runs"] = 1
    deployment["execution_accounting"][
        "current_device_appointment_runs"] = 0
    deployment_path.write_text(
        json.dumps(deployment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(deployment_path, 0o444)
    print(
        f"c2-c1-freezer-hw-fixture-{ACTIVE_LINK_LABEL.lower()}: PREPARE PASS "
        "accepted=1,2 pending=3,4 regions=2 hardware=not-run")


def verify(out: Path) -> None:
    accepted_prior()
    M.verify(out)
    deployment = M.read_json(out / "deployment.json")
    overflow = [
        row for row in deployment["preloads"]
        if row.get("address")
        == f"0x{R.REGION1_SOURCE_BASE:08x}"
    ]
    M.require(
        deployment["status"] == DEPLOYMENT_STATUS
        and deployment["protocol"]["accepted_predecessor_cutpoints"] == [1, 2]
        and deployment["protocol"][
            f"current_{ACTIVE_LINK_LABEL}_appointment_cutpoints"]
            == [3, 4]
        and deployment["protocol"]["return_from_Freezer_key"] == "F3"
        and deployment["protocol"]["virtual_keyboard_form"]
            == "quoted t is transported as (quote t); the m65 apostrophe "
               "path is not an input authority"
        and deployment["protocol"]["autorun_submission"]
            == "if and only if a pre-boot screen shows standalone BASIC run: "
               "without lisp65>, inject one explicit RETURN"
        and len(overflow) == 1
        and overflow[0]["sha256"] == CARRIER_BUILD.OVERFLOW_SHA
        and deployment["span_checks"][
            "region1_durable_source_disjoint_from_shelf_and_boot"],
        "Link-60 C1 two-region hardware protocol drift")
    print(
        f"c2-c1-freezer-hw-fixture-{ACTIVE_LINK_LABEL.lower()}: VERIFY PASS "
        "hardware=not-run next=device-start")


def observe_boot(out: Path) -> None:
    prior = accepted_prior()
    M.observe_boot(out)
    state = M.load_state(out)
    state["format"] = (
        f"lisp65-c2.2-C1-Freezer-{ACTIVE_LINK_LABEL}-v4-"
        "hardware-state-v1")
    state["status"] = "passed-cutpoint-2-ready-for-cutpoint-3"
    state["device_runs"] = 1
    state["current_device_appointment_runs"] = 1
    state["next_cutpoint"] = 3
    state["cutpoints"] = prior
    M.save_state(out, state)
    print(
        f"c2-c1-freezer-hw-fixture-{ACTIVE_LINK_LABEL.lower()}: BOOT PASS "
        "accepted=1,2 next=cutpoint-3")


def confirm_output(out: Path, cutpoint: int, output: str) -> None:
    M.confirm_output(out, cutpoint, output)
    if cutpoint != 4:
        return
    os.chmod(HARDWARE_RECEIPT, 0o644)
    receipt = M.read_json(HARDWARE_RECEIPT)
    receipt["format"] = (
        f"lisp65-c2.2-{ACTIVE_LINK_LABEL.lower()}-C1-Freezer-"
        "four-cutpoint-hardware-receipt-v1")
    receipt["status"] = (
        "passed-C1-open-transaction-Freezer-four-cutpoint-"
        "successor-fixture")
    receipt["authority"][ACTIVE_LINK_LABEL.lower()] = receipt[
        "authority"].pop("link58")
    receipt["authority"]["accepted_predecessor_cutpoints_1_2"] = M.bind(
        PRIOR_FIRST_RED)
    receipt["hardware"]["accepted_predecessor_cutpoints"] = [1, 2]
    receipt["hardware"][f"current_{ACTIVE_LINK_LABEL}_cutpoints"] = [3, 4]
    receipt["hardware"][f"current_{ACTIVE_LINK_LABEL}_device_runs"] = 1
    receipt["hardware"]["Freezer_return_key"] = "F3"
    receipt["hardware"]["L65R_regions"] = 2
    receipt["verdict"]["C1_matrix_status"] = "PROVEN"
    receipt["verdict"]["cutpoint_3_episode_latch"] = "passed"
    receipt["verdict"]["cutpoint_4_write_completion_barriers"] = "passed"
    receipt["execution_accounting"]["hardware_runs"] = 1
    receipt["execution_accounting"]["accepted_predecessor_device_runs"] = 1
    receipt["claim_limit"] = (
        "Closes matrix row C1 under accepted predecessor cutpoints 1/2 and "
        f"the exact {ACTIVE_LINK_LABEL} cutpoint-3/4 successor run. "
        "It is not promotion, "
        "an acceptance-chain result or a release claim.")
    HARDWARE_RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    os.chmod(HARDWARE_RECEIPT, 0o444)
    print(
        f"c2-c1-freezer-hw-fixture-{ACTIVE_LINK_LABEL.lower()}: COMPLETE "
        "accepted=1,2 measured=3,4 matrix=C1-PROVEN")


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
            observe_boot(out)
        elif args.mode == "observe-hold":
            M.require(args.cutpoint is not None, "--cutpoint is required")
            M.observe_hold(out, args.cutpoint)
        elif args.mode == "observe-thaw":
            M.require(args.cutpoint is not None, "--cutpoint is required")
            M.require(
                args.freezer_output is not None,
                "--freezer-output is required")
            M.observe_thaw(
                out, args.cutpoint, args.freezer_output)
        else:
            M.require(args.cutpoint is not None, "--cutpoint is required")
            M.require(args.output is not None, "--output is required")
            confirm_output(out, args.cutpoint, args.output)
    except (
        M.FixtureError, M.HW.PreSmokeError, OSError, ValueError, KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-c1-freezer-hw-fixture-link60: FIRST RED: " + str(error))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
