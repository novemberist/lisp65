#!/usr/bin/env python3
"""Bind the physical-keyboard First Red for the Link-85 Ship sample."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/c2-ship-builder-v1-link85-interactive-human-test.json"
REVIEW = ROOT / "docs/planning/1.3-link84-closing-first-red-review.md"
HOST_READING = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link85-interactive-method-host-reading-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link85-interactive-human-device-first-red-receipt.json"
)
RUN = ROOT / "build/ship-builder/v13/link85-interactive-human-test/run"
SESSION = ROOT / "scripts/c2-v13-link85-interactive-human-test-hw.sh"
DRIVER = Path(__file__).resolve()


class CloseError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CloseError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path, address: str | None = None) -> dict[str, object]:
    require(path.is_file(), f"evidence absent: {path}")
    result: dict[str, object] = {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
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
        sys.argv[1:] == ["silent-after-Ada-RETURN"],
        "usage: c2_v13_link85_interactive_human_close.py "
        "silent-after-Ada-RETURN",
    )
    config = load(CONFIG)
    host = load(HOST_READING)
    review = REVIEW.read_text(encoding="utf-8")
    session = SESSION.read_text(encoding="utf-8")
    require(
        config["status"] == "owner-authorized-physical-keyboard-discriminator"
        and config["physical_input"] == "Ada followed by RETURN"
        and config["virtual_input"] == "forbidden",
        "physical-keyboard commission drift",
    )
    require(
        host["status"]
        == "host-reading-complete-physical-keyboard-discriminator-required",
        "host-reading authority drift",
    )
    require(
        "Physical-keyboard discriminator — Product First Red" in review,
        "operator observation absent from owner review",
    )
    require("run_m65 -t" not in session and "mega65_ftp" in session,
            "human-test runner contains virtual-key injection")

    image = ROOT / str(config["image"])
    readback = RUN / "package-readback.d81"
    require(image.read_bytes() == readback.read_bytes(),
            "mounted interactive D81 readback drift")
    before = (RUN / "state-before-human.bin").read_bytes()
    result = (RUN / "result.bin").read_bytes()
    require(before == b"\x02", f"pre-human state drift: {before.hex()}")
    require(result == b"\x02\x00\x00\x00",
            f"post-human state/result drift: {result.hex()}")
    screen = (RUN / "complete.txt").read_text(
        encoding="utf-8", errors="replace")
    lines = screen.splitlines()
    require(len(lines) == 27, f"captured screen height drift: {len(lines)}")
    require(all(not line.strip() for line in lines),
            "post-human screen is no longer wholly blank")
    require(str(config["expected_screen_text"]) not in screen,
            "expected greeting unexpectedly present")

    value = {
        "format": "lisp65-c2.3-v1.3-link85-interactive-human-device-first-red-v1",
        "recorded_on": date.today().isoformat(),
        "status": "PRODUCT-FIRST-RED-physical-keyboard-input-not-observed",
        "candidate_link": 85,
        "release_ready": False,
        "product_bytes_changed": 0,
        "product_links_created": 0,
        "preconditions": {
            "cold_reset": "passed",
            "fresh_BASIC": "passed",
            "exact_D81_readback": "passed",
            "runtime_state_before_input": 2,
            "virtual_keys_sent": 0,
        },
        "operator_observation": {
            "physical_input": "Ada followed by RETURN",
            "screen_before_input": "completely blue, no prompt",
            "screen_after_input": "no visible effect",
            "classification": "human-attested",
        },
        "post_input_readback": {
            "runtime_state": 2,
            "runtime_result": "0x0000",
            "raw": bind(RUN / "result.bin", str(config["runtime_state"])),
            "captured_lines": len(lines),
            "nonblank_lines": 0,
            "expected_greeting": str(config["expected_screen_text"]),
            "greeting_present": False,
            "screen": bind(RUN / "complete.png"),
            "screen_text": bind(RUN / "complete.txt"),
        },
        "decision": {
            "pre_registered_outcome": "silence=product-read-line-red",
            "result": "product-interactive-input-end-to-end-red",
            "virtual_transport_only_explanation": "refuted-by-physical-keyboard",
            "next": "owner-review-before-attribution-or-product-change",
        },
        "preserved_green": {
            "Link85_full_reset_D3": True,
            "Link85_D4_require_q_time": True,
            "standalone_noninteractive_samples": 3,
        },
        "bindings": {
            "config": bind(CONFIG),
            "owner_review": bind(REVIEW),
            "host_reading": bind(HOST_READING),
            "session": bind(SESSION),
            "driver": bind(DRIVER),
            "image": bind(image),
            "package_readback": bind(readback),
            "state_before_human": bind(
                RUN / "state-before-human.bin", str(config["runtime_state"])),
            "waiting_screen": bind(RUN / "waiting-for-human.png"),
            "upload_log": bind(RUN / "upload.log"),
        },
        "claim_limit": (
            "The physical keyboard did not advance the exact Link-85 "
            "interactive sample beyond state 2 or produce any echo/greeting. "
            "This convicts the shipped interactive input composition "
            "end-to-end; it does not yet attribute the fault within KERNAL "
            "keyboard scanning, GETIN, key-event or Bank-2 read-line."
        ),
    }
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    print(
        "c2-v13-link85-interactive-human-close: PRODUCT FIRST RED "
        "state=2 result=0 screen=blank virtual-keys=0"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CloseError, OSError, ValueError, KeyError, TypeError,
            json.JSONDecodeError) as error:
        print(f"c2-v13-link85-interactive-human-close: FIRST RED: {error}")
        raise SystemExit(2)
