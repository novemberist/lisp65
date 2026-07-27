#!/usr/bin/env python3
"""Run Link-59 C1 cutpoints 3/4 with accepted Link-58 cutpoints 1/2."""

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
import c2_c1_freezer_hw_fixture as M  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
LINK = ROOT / (
    "build/c2.2/substitution/product-link-59-c1-freezer-irq-episode")
LINK_RECEIPT = EVIDENCE / (
    "c2.2-product-link59-c1-freezer-irq-episode-structural-receipt.json")
CARRIER = ROOT / (
    "build/c2.2/substitution/"
    "link59-c1-freezer-memory-holds-link59-rebound-"
    "stage-bound-NONPROMOTABLE")
CARRIER_BASENAME = (
    "runtime-overlays-session-c1-freezer-memory-holds-"
    "link59-rebound-stage-bound.bin")
CARRIER_RECEIPT = EVIDENCE / (
    "c2.2-link59-c1-freezer-memory-hold-carrier-"
    "nonpromotable-receipt.json")
CARRIER_STATUS = (
    "passed-capacity-and-gates-awaiting-separate-hardware-authorization")
OUT = ROOT / (
    "build/c2.2/"
    "c1-freezer-memory-hold-hardware-link59-attempt6-NONPROMOTABLE")
PRIOR_STATE = ROOT / (
    "build/c2.2/"
    "c1-freezer-memory-hold-hardware-link58-attempt5-NONPROMOTABLE/"
    "hardware-state.json")
PRIOR_FIRST_RED = EVIDENCE / (
    "c2.2-link58-C1-Freezer-memory-hold-cutpoint3-"
    "continuation-hardware-first-red.json")
PRODUCT_SHA = (
    "b46ab695a803f993e206f48f87e6ce310de1e6e56ca897bf07900502697000e6")
LINK58_SHA = (
    "4bab8371aa54060bef4ab9493e12dd6afd230baeb83a11f07daccdaa05000e6f")
HARDWARE_RECEIPT = EVIDENCE / (
    "c2.2-link59-C1-Freezer-four-cutpoint-hardware-receipt.json")
DEPLOYMENT_STATUS = (
    "ready-nonpromotable-Link59-memory-hold-cutpoints-3-and-4")


def current_authority() -> dict[str, Path]:
    paths = M.paths()
    for name, path in paths.items():
        M.require(path.is_file(), f"missing Link-59 {name}: {path}")
    link = M.read_json(LINK_RECEIPT)
    carrier = M.read_json(CARRIER_RECEIPT)
    contract = M.read_json(M.CONTRACT)
    artifacts = M.read_json(M.ARTIFACTS)
    M.require(
        M.sha(paths["product"]) == PRODUCT_SHA
        and link["status"]
        == "passed-link59-C1-IRQ-episode-product-identity-hardware-not-run"
        and link["product_identity"]["product"]["sha256"] == PRODUCT_SHA
        and carrier["status"] == CARRIER_STATUS
        and carrier["construction"]["product_bytes_changed"] == 0
        and carrier["construction"]["session_family_size_delta"] == 0
        and carrier["construction"]["external_relocation_sites_rebound"] == 23
        and carrier["construction"]["whole_family_crc16"] == "0x8bc9"
        and contract["status"] == "owner-reviewed-fixture-contract"
        and contract["hardware_protocol"]["freezer_roundtrips"] == 4
        and M.FIRST_RED_RECEIPT.is_file()
        and M.ZERO_JOURNAL_FIRST_RED_RECEIPT.is_file()
        and M.CROSS_IDENTITY_FIRST_RED_RECEIPT.is_file()
        and artifacts["artifacts"]["shelf"]["sha256"]
        == M.sha(paths["shelf"]),
        "Link-59 C1 fixture authority is incomplete",
    )
    host = link["fresh_prelink_gates"]["c2d_v6_host_semantics"]["artifacts"]
    M.require(
        host["c2d"]["sha256"] == M.sha(paths["c2d"])
        and host["code"]["sha256"] == M.sha(paths["bank2_static"]),
        "Link-59 C2D/Bank-2 plane binding drift",
    )
    M.HW.verify_c2d_product_identity(paths, M.ARTIFACTS)
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
    M.validate_authority = current_authority


def accepted_prior() -> list[dict[str, Any]]:
    M.require(
        PRIOR_STATE.is_file() and PRIOR_FIRST_RED.is_file(),
        "accepted Link-58 cutpoint 1/2 authority is absent",
    )
    state = M.read_json(PRIOR_STATE)
    rows = deepcopy(state["cutpoints"][:2])
    M.require(
        state["product_sha256"] == LINK58_SHA
        and [row["id"] for row in rows] == [1, 2]
        and all(row["status"] == "passed" for row in rows)
        and all(row["operator_call_output"] == "t" for row in rows),
        "accepted Link-58 cutpoint 1/2 authority drift",
    )
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
        "lisp65-c2.2-C1-Freezer-Link59-memory-hold-hardware-fixture-v1")
    deployment["status"] = DEPLOYMENT_STATUS
    deployment["authority"]["link59_receipt"] = deployment[
        "authority"
    ].pop("link58_receipt")
    deployment["authority"]["accepted_Link58_cutpoints_1_2"] = M.bind(
        PRIOR_FIRST_RED
    )
    deployment["protocol"] = {
        "accepted_predecessor_cutpoints": [1, 2],
        "current_Link59_appointment_cutpoints": [3, 4],
        "return_from_Freezer_key": "F3",
        "hold_carrier": (
            "fresh load of 0x17e0 on every loop iteration; "
            "no register-resume assumption"
        ),
        "first_source_less_IRQ_per_raster_episode": "accepted",
        "second_consecutive_source_less_IRQ": "fail-closed",
    }
    deployment["execution_accounting"]["accepted_predecessor_device_runs"] = 1
    deployment["execution_accounting"]["current_device_appointment_runs"] = 0
    deployment_path.write_text(
        json.dumps(deployment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(deployment_path, 0o444)
    print(
        "c2-c1-freezer-memory-hold-hw-fixture-link59: PREPARE PASS "
        "accepted=1,2 pending=3,4 hardware=not-run"
    )


def verify(out: Path) -> None:
    accepted_prior()
    M.verify(out)
    deployment = M.read_json(out / "deployment.json")
    M.require(
        deployment["status"] == DEPLOYMENT_STATUS
        and deployment["protocol"]["accepted_predecessor_cutpoints"] == [1, 2]
        and deployment["protocol"]["current_Link59_appointment_cutpoints"]
        == [3, 4]
        and deployment["protocol"]["return_from_Freezer_key"] == "F3",
        "Link-59 C1 hardware protocol drift",
    )
    print(
        "c2-c1-freezer-memory-hold-hw-fixture-link59: VERIFY PASS "
        "hardware=not-run next=device-start"
    )


def observe_boot(out: Path) -> None:
    prior = accepted_prior()
    M.observe_boot(out)
    state = M.load_state(out)
    state["format"] = (
        "lisp65-c2.2-C1-Freezer-Link59-memory-hold-hardware-state-v1")
    state["status"] = "passed-cutpoint-2-ready-for-cutpoint-3"
    state["device_runs"] = 1
    state["current_device_appointment_runs"] = 1
    state["next_cutpoint"] = 3
    state["cutpoints"] = prior
    M.save_state(out, state)
    print(
        "c2-c1-freezer-memory-hold-hw-fixture-link59: BOOT PASS "
        "accepted=1,2 next=cutpoint-3"
    )


def confirm_output(out: Path, cutpoint: int, output: str) -> None:
    M.confirm_output(out, cutpoint, output)
    if cutpoint != 4:
        return
    os.chmod(HARDWARE_RECEIPT, 0o644)
    receipt = M.read_json(HARDWARE_RECEIPT)
    receipt["format"] = (
        "lisp65-c2.2-link59-C1-Freezer-four-cutpoint-hardware-receipt-v1")
    receipt["status"] = (
        "passed-C1-open-transaction-Freezer-four-cutpoint-"
        "successor-fixture")
    receipt["authority"]["link59"] = receipt["authority"].pop("link58")
    receipt["authority"]["accepted_Link58_cutpoints_1_2"] = M.bind(
        PRIOR_FIRST_RED
    )
    receipt["hardware"]["accepted_predecessor_cutpoints"] = [1, 2]
    receipt["hardware"]["current_Link59_cutpoints"] = [3, 4]
    receipt["hardware"]["current_Link59_device_runs"] = 1
    receipt["hardware"]["Freezer_return_key"] = "F3"
    receipt["verdict"]["C1_matrix_status"] = "PROVEN"
    receipt["execution_accounting"]["hardware_runs"] = 1
    receipt["execution_accounting"]["accepted_predecessor_device_runs"] = 1
    receipt["claim_limit"] = (
        "Closes matrix row C1 under the approved Link-58 cutpoint-1/2 "
        "predecessor evidence plus Link-59 cutpoint-3/4 successor replay. "
        "It is not promotion, an acceptance-chain result, or a release claim."
    )
    HARDWARE_RECEIPT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(HARDWARE_RECEIPT, 0o444)
    print(
        "c2-c1-freezer-memory-hold-hw-fixture-link59: COMPLETE "
        "accepted=1,2 measured=3,4 matrix=C1-PROVEN"
    )


def main() -> int:
    configure()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=(
            "prepare",
            "verify",
            "observe-boot",
            "observe-hold",
            "observe-thaw",
            "confirm-output",
        ),
    )
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
                "--freezer-output is required",
            )
            M.observe_thaw(out, args.cutpoint, args.freezer_output)
        else:
            M.require(args.cutpoint is not None, "--cutpoint is required")
            M.require(args.output is not None, "--output is required")
            confirm_output(out, args.cutpoint, args.output)
    except (
        M.FixtureError,
        M.HW.PreSmokeError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(
            "c2-c1-freezer-memory-hold-hw-fixture-link59: FIRST RED: "
            + str(error)
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
