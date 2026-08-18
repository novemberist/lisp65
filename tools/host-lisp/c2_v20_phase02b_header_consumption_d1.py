#!/usr/bin/env python3
"""Prepare, verify and record the fresh Link-106 D1 boot."""

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

import c2_v20_source_oracle_d1 as BASE  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


CONFIG = ROOT / (
    "config/c2-v150-v20-phase02b-header-consumption-far-device-session.json")
RUNNER = ROOT / "scripts/c2-v20-phase02b-header-consumption-d1-hw.sh"
MEDIA = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-phase02b-header-consumption-media-receipt.json")
SUMMARY = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-phase02b-header-consumption-completion-media-receipt.json")
PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-phase02b-header-consumption-d1-preparation-receipt.json")
RESULT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-phase02b-header-consumption-d1-receipt.json")
OUT = ROOT / "build/c2.3/v2.0-phase02b-header-consumption-d1"
SIGNS = ["LISP65: STAGING MEDIA", "LISP65: BUILDING HEAP",
         "LISP65: LOADING LIBRARIES"]


D1Error = BASE.D1Error


def require(value: bool, message: str) -> None:
    if not value:
        raise D1Error(message)


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


def configure_base() -> None:
    BASE.CONFIG = CONFIG
    BASE.RUNNER = RUNNER
    BASE.MEDIA = MEDIA
    BASE.PREP = PREP
    BASE.RESULT = RESULT
    BASE.OUT = OUT
    BASE.SIGNS = SIGNS
    BASE.contract = contract


def contract(value: dict[str, Any] | None = None) -> dict[str, Any]:
    value = value or load(CONFIG)
    media = load(MEDIA)
    summary = load(SUMMARY)
    packed = media.get("packed_artifact_gate_registry", {})
    require(
        value.get("format") == "lisp65-c2-v150-v20-far-payload-device-session-v1"
        and value.get("status") == "prepared-D1-repeat-authorized"
        and value.get("boot_access_free_seconds") == 45
        and value.get("recontact_authorized") is True
        and value.get("D2_D5_open") is False
        and value.get("identity", {}).get("product_medium")
            == media["shared_system"]["product_D81"]["path"]
        and value.get("identity", {}).get("library_medium")
            == media["library"]["D81"]["path"]
        and media.get("status")
            == "V20-MAPPED-FAR-PAYLOAD-DELIVERED; D1-REPEAT-AUTHORIZED"
        and media["materialization"]["delivered_bytes"] == 48156
        and media["materialization"]["source_bytes_preserved"] == 46043
        and media["materialization"]["payload_bytes"] == 874
        and media["materialization"]["gate"]["identity_mismatches"] == 0
        and media["pair_identity"]["result"] == "same-world-pair"
        and packed.get("complete") is True
        and packed.get("registered") == packed.get("executed")
        and packed["results"]["autoboot.c65.elf"]["result"]
            == "passed-actual-linked-stager-prefix"
        and media["hardware_handoff"]["D1_repeat_authorized"] is True
        and media["hardware_handoff"]["D2_D5_open"] is False
        and summary.get("status")
            == "PASS: Link 106 completed and media closed; D1 ready"
        and summary["hardware_handoff"]["D1_ready"] is True
        and summary["hardware_handoff"]["D2_D5_open"] is False,
        "Link 106 D1 contract/media authority drift")
    return value


def runner_gate(source_override: str | None = None) -> dict[str, Any]:
    configure_base()
    return BASE.runner_gate(source_override)


def mutations(config: dict[str, Any], source: str) -> list[str]:
    configure_base()
    return BASE.mutations(config, source)


def derive_preparation() -> dict[str, Any]:
    configure_base()
    config = contract(); source = RUNNER.read_text(encoding="utf-8")
    return {
        "format": "lisp65-c2.3-v2.0-phase02b-header-consumption-d1-preparation-v1",
        "recorded_on": "2026-08-13",
        "status": "V20-LINK106-D1-PREPARED-NOT-RUN",
        "authority": {"media": bind(MEDIA), "summary": bind(SUMMARY),
            "config": bind(CONFIG), "runner": bind(RUNNER),
            "checker": bind(Path(__file__))},
        "runner_gate": runner_gate(source),
        "required_visible_liveness": SIGNS,
        "required_terminal_state": ["WORKBENCH 1.5.0", "lisp65>"],
        "mutations_rejected": mutations(config, source),
        "execution_accounting": {"hardware_contacts": 0, "forms": 0,
            "product_links": 0, "WPLTO_runs": 0},
        "unlock": {"D1_repeat": True, "D2_D5": False},
        "claim_limit": (
            "Fresh Link 106 D1 only. D2-D5 remain closed until the owner "
            "confirms all three visible signs and terminal state."),
    }


def validate_preparation(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("status") == "V20-LINK106-D1-PREPARED-NOT-RUN"
        and value.get("runner_gate", {}).get("pre_terminal_device_accesses") == 0
        and len(value.get("mutations_rejected", [])) == 7
        and value.get("execution_accounting") == {
            "hardware_contacts": 0, "forms": 0,
            "product_links": 0, "WPLTO_runs": 0}
        and value.get("unlock") == {"D1_repeat": True, "D2_D5": False},
        "Link 106 D1 preparation claim drift")
    if verify:
        require(value == derive_preparation(), "Link 106 D1 preparation stale")


def verify_terminal(text: Path, image: Path) -> dict[str, Any]:
    SCREEN.check_fail_closed_frame(image)
    raw = text.read_text(encoding="utf-8", errors="replace")
    require("WORKBENCH 1.5.0" in raw and "lisp65>" in raw,
            "Link 106 D1 banner/prompt absent")
    return {"result": "passed", "text": bind(text), "image": bind(image)}


def derive_result() -> dict[str, Any]:
    prep = load(PREP); validate_preparation(prep, verify=True)
    signs = (OUT / "owner-visible-signs.txt").read_text(
        encoding="utf-8").splitlines()
    require(signs == SIGNS and (OUT / "owner-visible-signs-confirmed").is_file(),
            "Link 106 D1 owner liveness confirmation absent")
    return {
        "format": "lisp65-c2.3-v2.0-phase02b-header-consumption-d1-v1",
        "recorded_on": "2026-08-13",
        "status": "V20-LINK106-D1-GREEN",
        "authority": {"preparation": bind(PREP), "media": bind(MEDIA)},
        "physical_observation": {"visible_liveness": signs,
            "terminal": verify_terminal(OUT / "product-boot.txt",
                                        OUT / "product-boot.png")},
        "execution_accounting": {"hardware_contacts": 1, "forms": 0,
            "product_links": 0, "WPLTO_runs": 0},
        "unlock": {"D2_D5": True},
        "claim_limit": "Fresh Link 106 D1 only; D2-D5 have not run.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=(
        "prepare", "check", "selftest", "verify-terminal", "record"))
    parser.add_argument("--text", type=Path)
    parser.add_argument("--image", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        require(not PREP.exists(), "Link 106 D1 preparation exists")
        PREP.write_bytes(canonical(derive_preparation()))
        print("Link 106 D1 preparation: PASS mutations=7")
    elif args.action == "check":
        validate_preparation(load(PREP), verify=True)
        print("Link 106 D1 check: PASS mutations=7")
    elif args.action == "selftest":
        validate_preparation(derive_preparation(), verify=False)
        print("Link 106 D1 selftest: PASS mutations=7")
    elif args.action == "verify-terminal":
        require(args.text is not None and args.image is not None,
                "verify-terminal requires --text/--image")
        verify_terminal(args.text, args.image)
        print("Link 106 D1 terminal: PASS")
    else:
        require(not RESULT.exists(), "Link 106 D1 result exists")
        RESULT.write_bytes(canonical(derive_result()))
        print("Link 106 D1: PASS D2-D5 now permitted")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (D1Error, BASE.D1Error, SCREEN.CheckError, OSError, ValueError,
            KeyError, json.JSONDecodeError) as error:
        message = error.message if isinstance(error, SCREEN.CheckError) else str(error)
        print(f"LINK 106 D1: {message}", file=sys.stderr)
        raise SystemExit(1)
