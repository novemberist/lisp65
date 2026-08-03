#!/usr/bin/env python3
"""Bind the owner-authorized Link-85 interactive retry First Red."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import repl_screen_check as SCREEN  # noqa: E402


RUN = ROOT / "build/ship-builder/v13/link85-interactive-retry/run"
CONFIG = ROOT / "config/c2-ship-builder-v1-link85-interactive-retry.json"
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link85-interactive-retry-preparation-receipt.json"
)
PRIOR = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link85-full-reset-closing-device-first-red-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link85-interactive-retry-first-red-receipt.json"
)


class RecordError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RecordError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    require(path.is_file(), f"evidence absent: {path}")
    result: dict[str, Any] = {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    if address is not None:
        result["address"] = f"0x{address:08x}"
    return result


def main() -> int:
    config = load(CONFIG)
    preparation = load(PREPARATION)
    prior = load(PRIOR)
    require(
        preparation["status"]
            == "prepared-one-character-per-invocation-Link85-interactive-only"
        and config["sequence"][0] == {"transport": "A", "screen_ack": "A"}
        and prior["reset_domain_fix"]["status"] == "passed-on-target",
        "interactive retry authority drift",
    )
    image = ROOT / config["image"]
    readback = RUN / "package-readback.d81"
    require(image.read_bytes() == readback.read_bytes(),
            "interactive retry medium drift")
    require((RUN / "state.bin").read_bytes() == b"\x02",
            "pre-input runtime state drift")
    text = (RUN / "ack-1.txt").read_text(encoding="utf-8", errors="replace")
    require("A" not in text, "expected missing first acknowledgement")
    SCREEN.check_fail_closed_frame(RUN / "ack-1.png")
    require(
        not (RUN / "ack-2.png").exists()
        and not (RUN / "result.bin").exists()
        and not (RUN / "complete.png").exists(),
        "runner advanced after the terminal first acknowledgement failure",
    )
    value = {
        "format": "lisp65-c2.3-v1.3-link85-interactive-retry-first-red-v1",
        "recorded_on": date.today().isoformat(),
        "status": "FIRST-RED-Link85-single-character-ack-absent-owner-review",
        "candidate_link": 85,
        "contact_budget": {"authorized": 1, "consumed": 1},
        "product_links_created": 0,
        "product_bytes_changed": 0,
        "release_ready": False,
        "preconditions": {
            "cold_reset": "passed",
            "fresh_BASIC": "passed",
            "exact_D81_readback": "passed",
            "runtime_state_before_input": 2,
        },
        "first_input": {
            "transport": "A",
            "invocations": 1,
            "expected_screen_ack": "A",
            "observed_screen_ack": "absent",
            "fail_closed_frame": False,
            "screen": bind(RUN / "ack-1.png"),
            "screen_text": bind(RUN / "ack-1.txt"),
            "pre_input_state": bind(
                RUN / "state.bin", int(config["runtime_state"], 16)),
        },
        "stopped_before": ["second-character", "RETURN", "result-read"],
        "attribution_boundary": (
            "The earlier unacknowledged multi-character burst is no longer a "
            "sufficient explanation: one isolated A also produced no visible "
            "echo after runtime state 2. This contact cannot distinguish the "
            "m65 virtual-keyboard to KERNAL-GETIN transport from the target "
            "read-line consumer. It does not establish a product failure."
        ),
        "next_gate": (
            "Owner methods review. No further device input or retry is "
            "authorized by this receipt."
        ),
        "preserved_green_claims": {
            "reset_domain_D3": prior["reset_domain_fix"],
            "D4": prior["D4"],
            "field_exposure": "zero-v1.3-first-advertised-release-still-closed",
        },
        "bindings": {
            "config": bind(CONFIG),
            "preparation": bind(PREPARATION),
            "prior_device_receipt": bind(PRIOR),
            "session": bind(ROOT / "scripts/c2-v13-link85-interactive-retry-hw.sh"),
            "driver": bind(ROOT / "tools/host-lisp/c2_v13_link85_interactive_retry.py"),
            "medium_readback": bind(readback),
            "upload_log": bind(RUN / "upload.log"),
        },
        "claim_limit": (
            "This receipt binds a harness/product boundary First Red at the "
            "first isolated input. It preserves the already passed Link-85 "
            "D3/D4 claims and makes no interactive Ship, acceptance or release claim."
        ),
    }
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("c2-v13-link85-interactive-retry-first-red: RECORDED "
          "state2=yes first-A-ack=absent advanced=no")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RecordError, SCREEN.CheckError, OSError, ValueError, KeyError,
            TypeError, json.JSONDecodeError) as error:
        print(f"c2-v13-link85-interactive-retry-first-red: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
