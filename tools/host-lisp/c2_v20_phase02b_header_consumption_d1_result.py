#!/usr/bin/env python3
"""Bind the non-terminal result of the fresh Link-106 D1 contact."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v20_phase02b_header_consumption_d1 as D1  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


OUT = D1.OUT
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-phase02b-header-consumption-d1-first-red-receipt.json")


class ResultError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResultError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def derive() -> dict[str, Any]:
    D1.configure_base()
    preparation = load(D1.PREP)
    D1.validate_preparation(preparation, verify=True)
    media = load(D1.MEDIA)
    product = ROOT / media["shared_system"]["product_D81"]["path"]
    library = ROOT / media["library"]["D81"]["path"]
    product_readback = OUT / "product-readback.d81"
    library_readback = OUT / "library-readback.d81"
    screen_text = OUT / "product-boot.txt"
    screen_image = OUT / "product-boot.png"
    raw = screen_text.read_text(encoding="utf-8", errors="replace")
    require(all(sign in raw for sign in D1.SIGNS),
            "post-window capture lacks a required liveness line")
    require("WORKBENCH 1.5.0" not in raw and "lisp65>" not in raw,
            "terminal state was present in the non-terminal capture")
    require("E25" not in raw, "capture belongs to the earlier E25 outcome")
    SCREEN.check_fail_closed_frame(screen_image)
    require(product.read_bytes() == product_readback.read_bytes(),
            "product medium/readback mismatch")
    require(library.read_bytes() == library_readback.read_bytes(),
            "library medium/readback mismatch")
    require(not (OUT / "terminal-banner-and-prompt-proven").exists()
            and not (OUT / "owner-visible-signs-confirmed").exists(),
            "green D1 state leaked into non-terminal result")
    return {
        "format": (
            "lisp65-c2.3-v2.0-phase02b-header-consumption-d1-first-red-v1"),
        "recorded_on": "2026-08-13",
        "status": (
            "D1-NONTERMINAL-AFTER-45S; POST-LOADING-LIBRARIES-UNDECIDED"),
        "authority": {"preparation": bind(D1.PREP),
            "media": bind(D1.MEDIA), "runner": bind(D1.RUNNER),
            "result_checker": bind(Path(__file__))},
        "delivery": {"product_source": bind(product),
            "product_readback": bind(product_readback),
            "product_byteidentical": True,
            "library_source": bind(library),
            "library_readback": bind(library_readback),
            "library_byteidentical": True},
        "post_window_capture": {"access_free_seconds": 45,
            "text": bind(screen_text), "image": bind(screen_image),
            "visible_liveness": D1.SIGNS,
            "error_text_absent": True, "red_frame_absent": True,
            "required_terminal_absent": ["WORKBENCH 1.5.0", "lisp65>"]},
        "physical_owner_observation": {
            "same_contact": True,
            "report": (
                "After LISP65: LOADING LIBRARIES no further visible change "
                "or REPL appeared."),
            "precision": "no separately priced elapsed-time bound"},
        "classification": {
            "result": "D1 did not reach its terminal state",
            "transport_mount_and_readback": "EXONERATED",
            "phase02a": "PREVIOUSLY-EXONERATED-AND-NOT-REOPENED",
            "phase02b_header_contract": "LINKED-AT-46043",
            "post_loading_libraries_mechanism": "UNDECIDED",
            "observation_crossing": (
                "NOT-EXCLUDED: the first tool observation occurred while the "
                "persistent library-loading phase was still visibly active")},
        "execution_accounting": {"hardware_contacts": 1, "forms": 0,
            "product_links": 0, "WPLTO_runs": 0,
            "post_result_device_accesses": 0},
        "unlock": {"D1": False, "D2_D5": False},
        "claim_limit": (
            "This proves byteidentical delivery and a non-terminal first "
            "observation after the 45-second floor, followed by the owner's "
            "same-screen report. It does not prove an infinite product hang, "
            "identify a post-loading-libraries mechanism, authorize a stopped-"
            "state read, repeat D1, D2-D5, resume, fix or release."),
    }


def validate(value: dict[str, Any]) -> None:
    require(value == derive(), "Link 106 D1 non-terminal result drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-terminal": lambda x: x["unlock"].update(D1=True),
        "open-D2-D5": lambda x: x["unlock"].update(D2_D5=True),
        "claim-hang": lambda x: x["classification"].update(
            post_loading_libraries_mechanism="INFINITE-HANG"),
        "drop-crossing-ambiguity": lambda x: x["classification"].update(
            observation_crossing="EXONERATED"),
        "claim-error-text": lambda x: x["post_window_capture"].update(
            error_text_absent=False),
        "claim-post-result-read": lambda x: x["execution_accounting"].update(
            post_result_device_accesses=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate)
        except ResultError:
            rejected.append(name)
    require(rejected == list(cases), "D1 non-terminal mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "Link 106 D1 first-red receipt exists")
    value = derive(); validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("Link 106 D1: NON-TERMINAL; D2-D5 CLOSED")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value)
    require(rejected == mutations(value), "D1 non-terminal mutation drift")
    print("Link 106 D1: CHECK NON-TERMINAL D2-D5=CLOSED")


def selftest() -> None:
    value = derive(); validate(value)
    require(len(mutations(value)) == 6, "D1 result mutation count drift")
    print("Link 106 D1 result: SELFTEST PASS mutations=6")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "record", "check"))
    action = parser.parse_args().action
    {"selftest": selftest, "record": record, "check": check}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResultError, D1.D1Error, SCREEN.CheckError, OSError, ValueError,
            KeyError, json.JSONDecodeError) as error:
        message = error.message if isinstance(error, SCREEN.CheckError) else str(error)
        print(f"LINK 106 D1 RESULT: {message}", file=sys.stderr)
        raise SystemExit(1)
