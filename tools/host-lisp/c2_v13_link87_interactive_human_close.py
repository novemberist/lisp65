#!/usr/bin/env python3
"""Bind the final physical-keyboard acceptance for Link 87."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/c2-ship-builder-v1-link87-interactive-human-test.json"
REVIEW = ROOT / "docs/planning/1.3-link84-closing-first-red-review.md"
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BOOT_GATE = EVIDENCE / "c2.3-v1.3-ship-boot-inheritance-gate-receipt.json"
WPLTO = EVIDENCE / "c2.3-v1.3-link87-repeated-timebase-wplto-receipt.json"
RECEIPT = EVIDENCE / "c2.3-v1.3-link87-interactive-human-device-receipt.json"
RUN = ROOT / "build/ship-builder/v13/link87-interactive-human-test/run"
FLEET = ROOT / "build/ship-builder/v13/link87-final-3bcb488d/fleet-receipt.json"
REPRO = ROOT / (
    "build/ship-builder/v13/link87-interactive-repro-3bcb488d/"
    "reproducibility.json"
)
SESSION = ROOT / "scripts/c2-v13-link87-interactive-human-test-hw.sh"
DRIVER = Path(__file__).resolve()


class CloseError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CloseError(message)


def bind(path: Path, address: str | None = None) -> dict[str, object]:
    require(path.is_file(), f"evidence absent: {path}")
    data = path.read_bytes()
    result: dict[str, object] = {
        "path": str(path.relative_to(ROOT)),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    if address is not None:
        result["address"] = address
    return result


def load(path: Path) -> dict[str, object]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def main() -> int:
    require(sys.argv[1:] in (["Ada-RETURN-greeted"], ["silent"]),
            "usage: c2_v13_link87_interactive_human_close.py "
            "{Ada-RETURN-greeted|silent}")
    outcome = sys.argv[1]
    config = load(CONFIG)
    boot = load(BOOT_GATE)
    card = load(WPLTO)
    fleet = load(FLEET)
    repro = load(REPRO)
    session = SESSION.read_text(encoding="utf-8")
    require(
        config["status"]
            == "owner-commissioned-Link87-physical-keyboard-acceptance"
        and config["source_commit"]
            == "3bcb488d57194cea0ffa204a3b023c7e3ebd4a76"
        and config["virtual_input"] == "forbidden",
        "Link-87 physical-keyboard commission drift")
    require(
        boot["status"] == "passed-ship-owned-repeated-frame-clock"
        and boot["host_execution"]["executions"] == 3
        and boot["mutation_count"] == 19
        and boot["target_object_execution"]["bytes"] == 23
        and card["status"]
            == "passed-Link87-repeated-timebase-one-product-shaped-WPLTO"
        and card["ship_runtime_price"]["runtime_delta_bytes"] == 220
        and fleet["status"] == "passed"
        and fleet["host_executions"] == 4
        and fleet["media_members_verified"] == 36
        and repro["status"] == "passed-byte-identical"
        and repro["fresh_checkouts"] is True
        and repro["executions"] == 2
        and repro["comparison_sha256"] == config["image_sha256"],
        "Link-87 host/card authority drift")
    require("run_m65 -t" not in session and "mega65_ftp" in session,
            "human-test runner contains virtual-key injection")

    image = ROOT / str(config["image"])
    readback = RUN / "package-readback.d81"
    require(image.read_bytes() == readback.read_bytes(),
            "mounted Link-87 interactive D81 readback drift")
    require(bind(image)["sha256"] == config["image_sha256"],
            "Link-87 interactive image identity drift")
    before = (RUN / "state-before-human.bin").read_bytes()
    result = (RUN / "result.bin").read_bytes()
    require(before == b"\x02", f"pre-human state drift: {before.hex()}")
    screen = (RUN / "complete.txt").read_text(
        encoding="utf-8", errors="replace")
    expected = str(config["expected_screen_text"])
    greeted = result == b"\x03\x28\x00\x00" and expected in screen
    if outcome == "Ada-RETURN-greeted":
        require(greeted, "physical Ada+RETURN greeting absent")
    else:
        require(not greeted, "silent outcome contradicts captured greeting")

    passed = outcome == "Ada-RETURN-greeted"
    value = {
        "format": "lisp65-c2.3-v1.3-link87-interactive-human-device-v1",
        "recorded_on": date.today().isoformat(),
        "status": ("passed-Link87-physical-keyboard-end-to-end" if passed
                   else "PRODUCT-FIRST-RED-Link87-physical-row"),
        "candidate_link": 87,
        "release_ready": passed,
        "product_bytes_changed_after_link": 0,
        "product_links_created": 1,
        "preconditions": {
            "cold_reset": "passed",
            "fresh_BASIC": "passed",
            "exact_D81_readback": "passed",
            "runtime_state_before_input": 2,
            "timebase_proof": "one independent sync plus three unit deltas",
            "owned_raster_acknowledgement": "bound in 23-byte target wrapper",
            "virtual_keys_sent": 0,
        },
        "operator_observation": {
            "physical_input": "Ada followed by RETURN",
            "expected_greeting": expected,
            "greeting_present": greeted,
            "classification": "human-typed-plus-screen-and-state-readback",
        },
        "post_input_readback": {
            "raw": bind(RUN / "result.bin", str(config["runtime_state"])),
            "runtime_state": result[0],
            "runtime_result": f"0x{int.from_bytes(result[1:3], 'little'):04x}",
            "screen": bind(RUN / "complete.png"),
            "screen_text": bind(RUN / "complete.txt"),
        },
        "decision": {
            "v1.3_status": ("eligible-for-owner-Halt-2-review" if passed
                            else "closed-pending-owner-review"),
            "result": ("wait, physical GETIN, read-line and greeting green"
                       if passed else "physical closing row red"),
            "run_stop_91": "separately parked and not claimed",
        },
        "bindings": {
            "config": bind(CONFIG), "owner_review": bind(REVIEW),
            "boot_gate": bind(BOOT_GATE), "wplto": bind(WPLTO),
            "fleet": bind(FLEET), "fresh_repro": bind(REPRO),
            "session": bind(SESSION), "driver": bind(DRIVER),
            "image": bind(image), "package_readback": bind(readback),
            "state_before_human": bind(
                RUN / "state-before-human.bin", str(config["runtime_state"])),
            "fresh_BASIC_screen": bind(RUN / "fresh-basic.png"),
            "upload_log": bind(RUN / "upload.log"),
        },
        "claim_limit": (
            "The exact committed Link-87 interactive image proves the owned "
            "repeated clock and its physical Ada+RETURN path only; the parked "
            "$91 RUN/STOP seam remains outside this row."
        ),
    }
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    print("c2-v13-link87-interactive-human-close: "
          + ("PASS state=3 result=0x0028 greeting='Hello, Ada!'"
             if passed else "PRODUCT FIRST RED physical closing row"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CloseError, OSError, ValueError, KeyError, TypeError,
            json.JSONDecodeError) as error:
        print(f"c2-v13-link87-interactive-human-close: FIRST RED: {error}")
        raise SystemExit(2)
