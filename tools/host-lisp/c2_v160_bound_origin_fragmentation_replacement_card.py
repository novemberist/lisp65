#!/usr/bin/env python3
"""Run the authorized fragmentation-safe bound-origin replacement card."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_bound_origin_final_card as BOUND  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-bound-origin-fragmentation-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-bound-origin-fragmentation-replacement-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-bound-origin-fragmentation-replacement-process"
RECEIPT = ARCH / (
    "c2.3-v1.6-bound-origin-fragmentation-replacement-card-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v1.6-bound-origin-fragmentation-replacement-card-final-red.json")
PREDECESSOR_RED = ARCH / "c2.3-v1.6-bound-origin-final-card-final-red.json"
AUTHORIZATION = "76ff3147"
DRIVER = Path(__file__).resolve()
FORMAT = "lisp65-c2-v160-bound-origin-fragmentation-replacement-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 BOUND-ORIGIN FRAGMENTATION REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 BOUND-ORIGIN FRAGMENTATION-SAFE FINAL WORLD GREEN"


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    commit = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("aggregate free space is not placement capacity",
                  "tenant needs a hole", "exactly one card",
                  "re-cut the placement explicitly", "four arcs",
                  "atomic origin", "raw-before-code-read", "floor is untouched"):
        BOUND.CARD.require(token in text,
            f"fragmentation replacement authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    red = BOUND.CARD.BASE.load(PREDECESSOR_RED)
    geometry = red["final_geometry_attribution"]
    BOUND.CARD.require(red["status"] ==
            "FINAL RED: V1.6 BOUND-ORIGIN FINAL LINK STOPS"
        and red["attempt_accounting"]["WPLTO_runs"] == 1
        and red["attempt_accounting"]["product_link_attempts"] == 1
        and red["attempt_accounting"]["media_builds"] == 0
        and geometry["capture_main"]["available_bytes"] == 36
        and geometry["capture_main"]["bytes"] == 37
        and geometry["capture_main"]["overflow_bytes"] == 1
        and geometry["aggregate"]["free_bytes_after_freight"] == 57,
        "fragmentation replacement predecessor Red drift")
    source = BOUND.CARD.FIDELITY.target_object_gate()
    BOUND.CARD.require(source["sizes"] == {
        "irq": 74, "main": 28, "helper": 40, "state": 16}
        and source["counter_order"][:4] == [
            "queue_present", "raw", "queue_read", "seen"],
        "fragmentation-safe source split drift")
    return {"Final_Red": red, "replacement_source": source,
            "price": {"main_before": 37, "main_after": 28,
                "helper_before": 31, "helper_after": 40,
                "combined_before": 68, "combined_after": 68,
                "new_E000_bytes": 0}}


def configure_module() -> None:
    BOUND.CARD.configure_for_paths(BUILD, PREFLIGHT,
        tag="bound-origin-fragmentation-replacement")


def install() -> None:
    BOUND.BUILD = BUILD
    BOUND.PREFLIGHT = PREFLIGHT
    BOUND.PROCESS = PROCESS
    BOUND.RECEIPT = RECEIPT
    BOUND.FINAL_RED = FINAL_RED
    BOUND.PREDECESSOR = PREDECESSOR_RED
    BOUND.DRIVER = DRIVER
    BOUND.AUTHORIZATION = AUTHORIZATION
    BOUND.FORMAT = FORMAT
    BOUND.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    BOUND.FINAL_STATUS = FINAL_STATUS
    BOUND.authority = authority
    BOUND.predecessor = predecessor
    BOUND.configure_module = configure_module
    BOUND.install()


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    result = BOUND.main()
    if action == "card" and RECEIPT.is_file():
        value = BOUND.CARD.BASE.load(RECEIPT)
        placement = value["final_world_claims"]["placement"]
        BOUND.CARD.require(placement["final_reserve_bytes"] == 57
            and placement["largest_contiguous_hole_bytes"] == 49
            and placement["fragments"][
                ".lisp65_c2_kernal_window.input_capture_main"]["bytes"] == 28
            and placement["fragments"][
                ".lisp65_c2_kernal_window.input_capture_helper"]["bytes"] == 40,
            "fragmentation-safe final placement proof drift")
        value["fragmentation_replacement_authority"] = authority()
        value["fragmentation_predecessor_Final_Red"] = (
            BOUND.CARD.BASE.bind(PREDECESSOR_RED))
        value["fragmentation_price"] = predecessor()["price"]
        RECEIPT.write_bytes(BOUND.CARD.canonical(value))
        BOUND.check_receipt()
    return result


if __name__ == "__main__":
    install()
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                BOUND.CARD.record_red(error)
            except Exception as receipt_error:
                print("fragmentation replacement Final Red receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"v1.6 fragmentation replacement: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
