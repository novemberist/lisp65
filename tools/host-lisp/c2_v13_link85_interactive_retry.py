#!/usr/bin/env python3
"""Prepare and evaluate the one-row Link-85 interactive Ship retry."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
from elf_truth import ElfTruth  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


CONFIG = ROOT / "config/c2-ship-builder-v1-link85-interactive-retry.json"
REVIEW = ROOT / "docs/planning/1.3-link84-closing-first-red-review.md"
PRIOR = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link85-full-reset-closing-device-first-red-receipt.json"
)
PREPARATION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link85-interactive-retry-preparation-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-link85-full-reset-closing-device-receipt.json"
)
OUT = ROOT / "build/ship-builder/v13/link85-interactive-retry"
RUN = OUT / "run"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
DRIVER = Path(__file__).resolve()
SESSION = ROOT / "scripts/c2-v13-link85-interactive-retry-hw.sh"


class RetryError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RetryError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path, address: int | None = None) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    result: dict[str, Any] = {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }
    if address is not None:
        result["address"] = f"0x{address:08x}"
    return result


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def prepare() -> dict[str, Any]:
    config = load(CONFIG)
    prior = load(PRIOR)
    review = REVIEW.read_text(encoding="utf-8")
    require(
        config["status"] == "owner-authorized-one-corrected-contact"
        and config["candidate_link"] == 85
        and config["transport_policy"]
            == "one-character-per-invocation-with-acknowledgement-boundary"
        and [row["transport"] for row in config["sequence"]]
            == ["A", "d", "a", "~M"]
        and [row.get("screen_ack") for row in config["sequence"][:3]]
            == ["A", "Ad", "Ada"]
        and config["sequence"][3]["state_ack"] == 3
        and "Authorized: one corrected contact" in review,
        "owner commission or transport table drift",
    )
    require(
        prior["status"]
            == "FIRST-RED-Link85-interactive-Ship-input-harness-owner-review"
        and prior["tool_first_red"]["classification"]
            == "unacknowledged-multi-character-input-transport"
        and prior["reset_domain_fix"]["status"] == "passed-on-target"
        and prior["D4"]["status"] == "passed-require-q-time",
        "prior Link-85 device truth drift",
    )
    image = ROOT / config["image"]
    elf = ROOT / config["elf"]
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
    state = truth.symbol("lisp65_runtime_state")
    result = truth.symbol("lisp65_runtime_result")
    require(
        state.value == int(config["runtime_state"], 16)
        and state.bytes == 1
        and result.value == int(config["runtime_result"], 16)
        and result.bytes == 2
        and result.value == state.value + 1,
        "interactive runtime oracle drift",
    )
    value = {
        "format": "lisp65-c2.3-v1.3-link85-interactive-retry-preparation-v1",
        "recorded_on": date.today().isoformat(),
        "status": "prepared-one-character-per-invocation-Link85-interactive-only",
        "candidate_link": 85,
        "product_bytes_changed": 0,
        "product_links_created": 0,
        "contact_budget": 1,
        "transport": {
            "sequence": config["sequence"],
            "acknowledgement_boundaries": 4,
            "multi_character_invocations": 0,
        },
        "artifacts": {
            "image": bind(image),
            "elf": bind(elf),
            "config": bind(CONFIG),
            "prior_device_receipt": bind(PRIOR),
            "owner_review": bind(REVIEW),
            "driver": bind(DRIVER),
            "session": bind(SESSION),
        },
        "addresses": {
            "state": f"0x{state.value:08x}",
            "result": f"0x{result.value:08x}",
        },
        "expected": {
            "terminal_state": 3,
            "result": config["expected_result"],
            "screen": config["expected_screen_text"],
        },
    }
    write(PREPARATION, value)
    return value


def evaluate() -> dict[str, Any]:
    preparation = load(PREPARATION)
    config = load(CONFIG)
    prior = load(PRIOR)
    require(
        preparation["status"]
            == "prepared-one-character-per-invocation-Link85-interactive-only",
        "retry preparation drift",
    )
    for index, expected in enumerate(("A", "Ad", "Ada"), 1):
        text = (RUN / f"ack-{index}.txt").read_text(
            encoding="utf-8", errors="replace")
        require(expected in text, f"input acknowledgement {index} absent")
        SCREEN.check_fail_closed_frame(RUN / f"ack-{index}.png")
    state_address = int(config["runtime_state"], 16)
    raw = (RUN / "result.bin").read_bytes()
    expected = int(config["expected_result"], 16)
    require(
        raw == bytes((3, expected & 0xff, expected >> 8, 0)),
        f"interactive result drift: {raw.hex()}",
    )
    screen_text = (RUN / "complete.txt").read_text(
        encoding="utf-8", errors="replace")
    require(config["expected_screen_text"] in screen_text,
            "interactive response absent")
    SCREEN.check_fail_closed_frame(RUN / "complete.png")
    image = ROOT / config["image"]
    require(image.read_bytes() == (RUN / "package-readback.d81").read_bytes(),
            "interactive package readback drift")
    value = {
        "format": "lisp65-c2.3-v1.3-link85-full-reset-closing-device-v1",
        "recorded_on": date.today().isoformat(),
        "status": "passed-Link85-full-reset-closing-session",
        "candidate_link": 85,
        "release_ready_for_halt2": True,
        "product_links_created_after_Link85": 0,
        "product_bytes_changed_by_retry": 0,
        "D1": {
            "status": "passed-four-standalone-images",
            "interactive": {
                "state": 3,
                "result": config["expected_result"],
                "screen_text": config["expected_screen_text"],
                "input_invocations": 4,
                "acknowledgement_boundaries": 4,
                "raw": bind(RUN / "result.bin", state_address),
                "screen": bind(RUN / "complete.png"),
                "package_readback": bind(RUN / "package-readback.d81"),
            },
            "prior_three_samples": "passed-and-bound-before-Link85",
        },
        "D3": prior["reset_domain_fix"],
        "D4": prior["D4"],
        "tool_first_red_closed": {
            "old": "unacknowledged-multi-character-input-transport",
            "new": "one-character-per-invocation-with-acknowledgement-boundary",
            "product_change": False,
        },
        "bindings": {
            "preparation": bind(PREPARATION),
            "prior_device_receipt": bind(PRIOR),
            "config": bind(CONFIG),
        },
        "claim": (
            "Link 85 closes the full reset-domain, editor-abort recovery, "
            "interactive Ship input and standing require/q/time rows. The "
            "candidate may proceed to Halt #2; release is not yet claimed."
        ),
    }
    write(RECEIPT, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "dry-run", "evaluate"))
    args = parser.parse_args()
    try:
        value = prepare() if args.action in {"prepare", "dry-run"} else evaluate()
        if args.action == "dry-run":
            print("c2-v13-link85-interactive-retry: DRY-RUN PASS "
                  "invocations=4 acknowledgements=4 product-delta=0")
        else:
            print(f"c2-v13-link85-interactive-retry: PASS status={value['status']}")
        return 0
    except (RetryError, SCREEN.CheckError, OSError, ValueError, KeyError,
            TypeError, json.JSONDecodeError) as error:
        print(f"c2-v13-link85-interactive-retry: FIRST RED: {error}",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
