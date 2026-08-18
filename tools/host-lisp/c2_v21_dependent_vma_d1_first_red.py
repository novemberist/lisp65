#!/usr/bin/env python3
"""Bind the sole Link-107 D1 fixed-time postcondition First Red."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v21_dependent_vma_d1 as D1  # noqa: E402


RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.1-dependent-vma-d1-first-red-receipt.json")


class FirstRedError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FirstRedError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    path = path if path.is_absolute() else ROOT / path
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def derive() -> dict[str, Any]:
    prep = load(D1.PREP)
    D1.validate_preparation(prep, verify=True)
    text_path = D1.OUT / "product-boot.txt"
    image_path = D1.OUT / "product-boot.png"
    text = text_path.read_text(encoding="utf-8", errors="replace")
    require(all(sign in text for sign in D1.SIGNS),
            "Link 107 D1 capture omitted a liveness line")
    require("WORKBENCH 1.5.0" not in text and "lisp65>" not in text,
            "Link 107 D1 terminal postcondition unexpectedly present")
    product = Path(load(D1.CONFIG)["identity"]["product_medium"])
    library = Path(load(D1.CONFIG)["identity"]["library_medium"])
    require((D1.OUT / "product-readback.d81").read_bytes() ==
            (ROOT / product).read_bytes(), "Link 107 product readback drift")
    require((D1.OUT / "library-readback.d81").read_bytes() ==
            (ROOT / library).read_bytes(), "Link 107 library readback drift")
    return {
        "format": "lisp65-c2.3-v2.1-dependent-vma-d1-first-red-v1",
        "recorded_on": "2026-08-15",
        "status": (
            "D1-FIRST-RED-LOADING-LIBRARIES-AT-45S; "
            "NO-LIVE-OR-LOOP-CLAIM"),
        "authority": {"preparation": bind(D1.PREP), "media": bind(D1.MEDIA),
            "summary": bind(D1.SUMMARY), "runner": bind(D1.RUNNER)},
        "transport": {
            "product_source": bind(ROOT / product),
            "product_readback": bind(D1.OUT / "product-readback.d81"),
            "library_source": bind(ROOT / library),
            "library_readback": bind(D1.OUT / "library-readback.d81"),
            "result": "byteidentical-both-media"},
        "single_postcondition_capture": {
            "access_free_seconds": 45,
            "text": bind(text_path), "image": bind(image_path),
            "visible_liveness": D1.SIGNS,
            "terminal_banner": False, "terminal_prompt": False,
            "fail_closed_red_frame_in_capture": False,
            "last_visible_phase": "LISP65: LOADING LIBRARIES"},
        "execution_accounting": {"hardware_contacts": 1,
            "post_boot_captures": 1, "forms": 0, "stops": 0,
            "resumes": 0, "additional_device_accesses": 0,
            "product_links": 0, "WPLTO_runs": 0},
        "unlock": {"D1": False, "D2_D5": False},
        "claim_limit": (
            "The fixed 45-second D1 postcondition was absent while all three "
            "liveness lines remained visible. The capture may have crossed an "
            "active loading phase; it proves neither a hang nor a loop, and "
            "authorizes no additional device access."),
        "next": "owner disposition of the Link-107 D1 fixed-time First Red",
    }


def validate(value: dict[str, Any], *, replay: bool) -> None:
    require(
        value.get("status") == (
            "D1-FIRST-RED-LOADING-LIBRARIES-AT-45S; "
            "NO-LIVE-OR-LOOP-CLAIM")
        and value.get("transport", {}).get("result")
            == "byteidentical-both-media"
        and value.get("single_postcondition_capture", {}).get(
            "last_visible_phase") == "LISP65: LOADING LIBRARIES"
        and value.get("single_postcondition_capture", {}).get(
            "terminal_prompt") is False
        and value.get("unlock") == {"D1": False, "D2_D5": False}
        and value.get("execution_accounting", {}).get("stops") == 0,
        "Link 107 D1 First Red claim drift")
    if replay:
        require(value == derive(), "Link 107 D1 First Red replay drift")


def selftest() -> None:
    value = derive()
    validate(value, replay=False)
    cases = {
        "claim-terminal": ("single_postcondition_capture", "terminal_prompt", True),
        "claim-D2": ("unlock", "D2_D5", True),
        "claim-stop": ("execution_accounting", "stops", 1),
        "claim-loop": (None, "status", "D1-LOOP-PROVEN"),
    }
    rejected = 0
    for section, key, replacement in cases.values():
        trial = deepcopy(value)
        target = trial if section is None else trial[section]
        target[key] = replacement
        try:
            validate(trial, replay=False)
        except FirstRedError:
            rejected += 1
    require(rejected == len(cases), "Link 107 D1 First Red mutation survived")
    print(f"Link 107 D1 First Red: SELFTEST PASS mutations={rejected}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "record", "check"))
    args = parser.parse_args()
    if args.action == "selftest":
        selftest()
    elif args.action == "record":
        require(not RECEIPT.exists(), "Link 107 D1 First Red receipt exists")
        value = derive()
        validate(value, replay=False)
        RECEIPT.write_bytes(canonical(value))
        print("Link 107 D1: FIRST RED at LOADING LIBRARIES after 45s")
    else:
        validate(load(RECEIPT), replay=True)
        print("Link 107 D1 First Red: CHECK PASS D2-D5=CLOSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FirstRedError, D1.D1Error, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"LINK 107 D1 FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
