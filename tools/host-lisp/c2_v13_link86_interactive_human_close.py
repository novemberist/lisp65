#!/usr/bin/env python3
"""Bind the final physical-keyboard acceptance for Link 86."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/c2-ship-builder-v1-link86-interactive-human-test.json"
REVIEW = ROOT / "docs/planning/1.3-link84-closing-first-red-review.md"
BOOT_GATE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-ship-boot-inheritance-gate-receipt.json"
)
WPLTO = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link86-boot-timebase-wplto-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link86-interactive-human-device-acceptance-receipt.json"
)
FIRST_RED_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link86-interactive-human-device-first-red-receipt.json"
)
RUN = ROOT / "build/ship-builder/v13/link86-interactive-human-test/run"
FLEET = ROOT / "build/ship-builder/v13/link86-final-5a7c0d18/fleet-receipt.json"
REPRO = ROOT / (
    "build/ship-builder/v13/link86-final-repro2-5a7c0d18/"
    "reproducibility.json"
)
SESSION = ROOT / "scripts/c2-v13-link86-interactive-human-test-hw.sh"
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
    require(
        sys.argv[1:] in (["Ada-RETURN-greeted"],
                         ["silent-after-Ada-RETURN"]),
        "usage: c2_v13_link86_interactive_human_close.py "
        "{Ada-RETURN-greeted|silent-after-Ada-RETURN}",
    )
    outcome = sys.argv[1]
    config = load(CONFIG)
    boot = load(BOOT_GATE)
    card = load(WPLTO)
    fleet = load(FLEET)
    repro = load(REPRO)
    session = SESSION.read_text(encoding="utf-8")
    require(
        config["status"]
            == "owner-commissioned-Link86-physical-keyboard-acceptance"
        and config["physical_input"] == "Ada followed by RETURN"
        and config["virtual_input"] == "forbidden"
        and config["source_commit"]
            == "5a7c0d18531a351aa262e73230c40c0105652f78",
        "Link-86 physical-keyboard commission drift",
    )
    require(
        boot["status"] == "passed-ship-boot-arms-and-verifies-inherited-io"
        and card["status"]
            == "passed-Link86-boot-timebase-one-product-shaped-WPLTO"
        and fleet["status"] == "passed"
        and fleet["host_executions"] == 4
        and fleet["media_members_verified"] == 36
        and repro["status"] == "passed-byte-identical"
        and repro["fresh_checkouts"] is True
        and repro["executions"] == 2
        and repro["comparison_sha256"] == config["image_sha256"],
        "Link-86 host/card authority drift",
    )
    require("run_m65 -t" not in session and "mega65_ftp" in session,
            "human-test runner contains virtual-key injection")

    image = ROOT / str(config["image"])
    readback = RUN / "package-readback.d81"
    require(image.read_bytes() == readback.read_bytes(),
            "mounted Link-86 interactive D81 readback drift")
    require(bind(image)["sha256"] == config["image_sha256"],
            "Link-86 interactive image identity drift")
    before = (RUN / "state-before-human.bin").read_bytes()
    result = (RUN / "result.bin").read_bytes()
    require(before == b"\x02", f"pre-human state drift: {before.hex()}")
    screen = (RUN / "complete.txt").read_text(
        encoding="utf-8", errors="replace")
    expected = str(config["expected_screen_text"])
    if outcome == "silent-after-Ada-RETURN":
        require(result == b"\x02\x00\x00\x00",
                f"silent post-human state/result drift: {result.hex()}")
        require(expected not in screen, "expected greeting unexpectedly present")
        lines = screen.splitlines()
        require(len(lines) == 27 and all(not line.strip() for line in lines),
                "silent screen is no longer wholly blank")
        value = {
            "format": "lisp65-c2.3-v1.3-link86-interactive-human-device-first-red-v1",
            "recorded_on": date.today().isoformat(),
            "status": "PRODUCT-FIRST-RED-physical-input-still-unobserved-after-timebase-fix",
            "candidate_link": 86,
            "release_ready": False,
            "product_bytes_changed_after_link": 0,
            "product_links_created": 1,
            "preconditions": {
                "cold_reset": "passed",
                "fresh_BASIC": "passed",
                "exact_D81_readback": "passed",
                "runtime_state_before_input": 2,
                "timebase_arm_and_tick_before_state_2": "product-enforced",
                "virtual_keys_sent": 0,
            },
            "operator_observation": {
                "physical_input": "Ada followed by RETURN",
                "screen_before_input": "completely blue, no prompt",
                "screen_after_input": "no visible effect",
                "classification": "human-attested-plus-state-and-screen-readback",
            },
            "post_input_readback": {
                "runtime_state": 2,
                "runtime_result": "0x0000",
                "raw": bind(RUN / "result.bin", str(config["runtime_state"])),
                "captured_lines": len(lines),
                "nonblank_lines": 0,
                "expected_greeting": expected,
                "greeting_present": False,
                "screen": bind(RUN / "complete.png"),
                "screen_text": bind(RUN / "complete.txt"),
            },
            "decision": {
                "timebase_fix": "reached state 2 after target-enforced arm/readback/tick proof",
                "physical_input_end_to_end": "red; program remained waiting",
                "v1.3_status": "closed-pending-owner-review",
                "next": "no retry, hardware contact or product fix authorized",
                "run_stop_91": "separately parked and not claimed",
            },
            "bindings": {
                "config": bind(CONFIG),
                "owner_review": bind(REVIEW),
                "boot_gate": bind(BOOT_GATE),
                "wplto": bind(WPLTO),
                "fleet": bind(FLEET),
                "fresh_repro": bind(REPRO),
                "session": bind(SESSION),
                "driver": bind(DRIVER),
                "image": bind(image),
                "package_readback": bind(readback),
                "state_before_human": bind(
                    RUN / "state-before-human.bin", str(config["runtime_state"])),
                "fresh_BASIC_screen": bind(RUN / "fresh-basic.png"),
                "upload_log": bind(RUN / "upload.log"),
            },
            "claim_limit": (
                "The exact committed Link-86 image proved a live raster jiffy "
                "before state 2, but physical Ada+RETURN produced no echo, "
                "greeting, result or state transition. This is an end-to-end "
                "Ship input First Red; it does not yet attribute the remaining "
                "fault within KERNAL keyboard scan, GETIN, key-event or read-line."
            ),
        }
        FIRST_RED_RECEIPT.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            "c2-v13-link86-interactive-human-close: PRODUCT FIRST RED "
            "state=2 result=0 screen=blank live-jiffy-proved virtual-keys=0"
        )
        return 0

    require(result == b"\x03\x28\x00\x00",
            f"post-human state/result drift: {result.hex()}")
    require(expected in screen, f"physical greeting absent: {expected}")

    value = {
        "format": "lisp65-c2.3-v1.3-link86-interactive-human-device-acceptance-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-Link86-physical-keyboard-end-to-end",
        "candidate_link": 86,
        "release_ready": True,
        "product_bytes_changed_after_link": 0,
        "product_links_created": 1,
        "preconditions": {
            "cold_reset": "passed",
            "fresh_BASIC": "passed",
            "exact_D81_readback": "passed",
            "runtime_state_before_input": 2,
            "timebase_arm_and_tick_before_state_2": "product-enforced",
            "virtual_keys_sent": 0,
        },
        "operator_observation": {
            "physical_input": "Ada followed by RETURN",
            "expected_greeting": expected,
            "greeting_present": True,
            "classification": "human-typed-plus-screen-and-state-readback",
        },
        "post_input_readback": {
            "runtime_state": 3,
            "runtime_result": "0x0028",
            "raw": bind(RUN / "result.bin", str(config["runtime_state"])),
            "screen": bind(RUN / "complete.png"),
            "screen_text": bind(RUN / "complete.txt"),
        },
        "decision": {
            "result": "Ship clock, wait, physical GETIN, read-line and greeting are end-to-end green",
            "v1.3_status": "eligible-for-owner-Halt-2-review",
            "run_stop_91": "separately parked and not claimed",
        },
        "bindings": {
            "config": bind(CONFIG),
            "owner_review": bind(REVIEW),
            "boot_gate": bind(BOOT_GATE),
            "wplto": bind(WPLTO),
            "fleet": bind(FLEET),
            "fresh_repro": bind(REPRO),
            "session": bind(SESSION),
            "driver": bind(DRIVER),
            "image": bind(image),
            "package_readback": bind(readback),
            "state_before_human": bind(
                RUN / "state-before-human.bin", str(config["runtime_state"])),
            "fresh_BASIC_screen": bind(RUN / "fresh-basic.png"),
            "upload_log": bind(RUN / "upload.log"),
        },
        "claim_limit": (
            "The exact committed Link-86 interactive Ship image armed and proved "
            "its timebase, then accepted Ada+RETURN from the physical keyboard "
            "and rendered the expected greeting. This does not close the separately "
            "parked $91 RUN/STOP seam."
        ),
    }
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    print(
        "c2-v13-link86-interactive-human-close: PASS "
        "state=3 result=0x0028 greeting='Hello, Ada!' virtual-keys=0"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CloseError, OSError, ValueError, KeyError, TypeError,
            json.JSONDecodeError) as error:
        print(f"c2-v13-link86-interactive-human-close: FIRST RED: {error}")
        raise SystemExit(2)
