#!/usr/bin/env python3
"""Prepare, verify and record the fresh Link 105 D1 boot."""

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
import repl_screen_check as SCREEN  # noqa: E402


CONFIG = ROOT / "config/c2-v150-v20-source-oracle-far-device-session.json"
RUNNER = ROOT / "scripts/c2-v20-source-oracle-d1-hw.sh"
MEDIA = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-source-oracle-media-closure-receipt.json")
PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-source-oracle-d1-preparation-receipt.json")
RESULT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.0-source-oracle-d1-receipt.json")
OUT = ROOT / "build/c2.3/v2.0-source-oracle-d1"
SIGNS = ["LISP65: STAGING MEDIA", "LISP65: BUILDING HEAP",
         "LISP65: LOADING LIBRARIES"]


class D1Error(RuntimeError):
    pass


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


def contract(value: dict[str, Any] | None = None) -> dict[str, Any]:
    value = value or load(CONFIG)
    media = load(MEDIA)
    packed = media.get("packed_artifact_gate_registry", {})
    require(
        value.get("format")
            == "lisp65-c2-v150-v20-far-payload-device-session-v1"
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
        and media["materialization"]["payload_bytes"] == 874
        and media["materialization"]["gate"]["identity_mismatches"] == 0
        and media["pair_identity"]["result"] == "same-world-pair"
        and packed.get("complete") is True
        and packed.get("registered") == packed.get("executed")
        and packed["results"]["autoboot.c65.elf"]["result"]
            == "passed-actual-linked-stager-prefix"
        and media["hardware_handoff"]["D1_repeat_authorized"] is True
        and media["hardware_handoff"]["D2_D5_open"] is False,
        "Link 105 D1 contract/media authority drift")
    return value


def runner_gate(source_override: str | None = None) -> dict[str, Any]:
    source = source_override or RUNNER.read_text(encoding="utf-8")
    require(
        "dry-run|stage|confirm-liveness" in source
        and source.count("ftp_bundle_under_basic") == 2
        and 'cmp "$product" "$OUT/product-readback.d81"' in source
        and 'cmp "$library" "$OUT/library-readback.d81"' in source
        and "# PRODUCT-LIVE-BEGIN" in source
        and "# PRODUCT-LIVE-END" in source
        and 'python3 "$PY" record' in source,
        "Link 105 D1 runner lifecycle token absent")
    live = source.split("# PRODUCT-LIVE-BEGIN", 1)[1].split(
        "# PRODUCT-LIVE-END", 1)[0]
    require(
        "mega65_ftp" not in live and "$FTP" not in live
        and "run_m65" not in live and "capture_screen" not in live
        and live.count("sleep") == 1,
        "Link 105 D1 liveness window admits device access")
    require(all(f"grep -Fqx '{sign}'" in source for sign in SIGNS),
            "Link 105 D1 can omit owner liveness confirmation")
    return {"result": "passed", "access_free_seconds": 45,
            "pre_terminal_device_accesses": 0, "post_boot_FTP": 0,
            "D2_D5_actions": 0, "owner_visible_signs": 3}


def mutations(config: dict[str, Any], source: str) -> list[str]:
    cases: dict[str, Callable[[], None]] = {}
    for name, key, value in (
        ("short-window", "boot_access_free_seconds", 20),
        ("authorize-D2-D5", "D2_D5_open", True),
        ("disable-recontact", "recontact_authorized", False),
    ):
        def run(key=key, value=value) -> None:
            trial = deepcopy(config); trial[key] = value; contract(trial)
        cases[name] = run
    source_cases = {
        "observe-window": source.replace(
            "# PRODUCT-LIVE-BEGIN: no device access during the boot window.\n"
            "  sleep",
            "# PRODUCT-LIVE-BEGIN: no device access during the boot window.\n"
            "  capture_screen forbidden\n  sleep", 1),
        "skip-product-readback": source.replace(
            '  cmp "$product" "$OUT/product-readback.d81"\n', "", 1),
        "skip-library-readback": source.replace(
            '  cmp "$library" "$OUT/library-readback.d81"\n', "", 1),
        "drop-owner-sign": source.replace(
            "grep -Fqx 'LISP65: STAGING MEDIA' \"$OUT/owner-visible-signs.txt\"\n",
            "", 1),
    }
    for name, candidate in source_cases.items():
        cases[name] = lambda candidate=candidate: runner_gate(candidate)
    rejected: list[str] = []
    for name, run in cases.items():
        try:
            run()
        except D1Error:
            rejected.append(name)
    require(rejected == list(cases), "Link 105 D1 mutation survived")
    return rejected


def derive_preparation() -> dict[str, Any]:
    config = contract(); source = RUNNER.read_text(encoding="utf-8")
    return {
        "format": "lisp65-c2.3-v2.0-source-oracle-d1-preparation-v1",
        "recorded_on": "2026-08-13",
        "status": "V20-SOURCE-ORACLE-D1-PREPARED-NOT-RUN",
        "authority": {"media": bind(MEDIA), "config": bind(CONFIG),
                      "runner": bind(RUNNER), "checker": bind(Path(__file__))},
        "runner_gate": runner_gate(source),
        "required_visible_liveness": SIGNS,
        "required_terminal_state": ["WORKBENCH 1.5.0", "lisp65>"],
        "mutations_rejected": mutations(config, source),
        "execution_accounting": {"hardware_contacts": 0, "forms": 0,
                                 "product_links": 0, "WPLTO_runs": 0},
        "unlock": {"D1_repeat": True, "D2_D5": False},
        "claim_limit": (
            "Fresh Link 105 D1 only. D2-D5 remain closed until the owner "
            "confirms all three visible signs and terminal state."),
    }


def validate_preparation(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format")
            == "lisp65-c2.3-v2.0-source-oracle-d1-preparation-v1"
        and value.get("status") == "V20-SOURCE-ORACLE-D1-PREPARED-NOT-RUN"
        and value.get("runner_gate", {}).get("pre_terminal_device_accesses") == 0
        and len(value.get("mutations_rejected", [])) == 7
        and value.get("execution_accounting") == {
            "hardware_contacts": 0, "forms": 0,
            "product_links": 0, "WPLTO_runs": 0}
        and value.get("unlock") == {"D1_repeat": True, "D2_D5": False},
        "Link 105 D1 preparation claim drift")
    if verify:
        require(value == derive_preparation(), "Link 105 D1 preparation stale")


def verify_terminal(text: Path, image: Path) -> dict[str, Any]:
    SCREEN.check_fail_closed_frame(image)
    raw = text.read_text(encoding="utf-8", errors="replace")
    require("WORKBENCH 1.5.0" in raw and "lisp65>" in raw,
            "Link 105 D1 banner/prompt absent")
    return {"result": "passed", "text": bind(text), "image": bind(image)}


def derive_result() -> dict[str, Any]:
    prep = load(PREP); validate_preparation(prep, verify=True)
    signs = (OUT / "owner-visible-signs.txt").read_text(
        encoding="utf-8").splitlines()
    require(signs == SIGNS and (OUT / "owner-visible-signs-confirmed").is_file(),
            "Link 105 D1 owner liveness confirmation absent")
    return {
        "format": "lisp65-c2.3-v2.0-source-oracle-d1-v1",
        "recorded_on": "2026-08-13",
        "status": "V20-SOURCE-ORACLE-D1-GREEN",
        "authority": {"preparation": bind(PREP), "media": bind(MEDIA)},
        "physical_observation": {"visible_liveness": signs,
            "terminal": verify_terminal(OUT / "product-boot.txt",
                                        OUT / "product-boot.png")},
        "execution_accounting": {"hardware_contacts": 1, "forms": 0,
                                 "product_links": 0, "WPLTO_runs": 0},
        "unlock": {"D2_D5": True},
        "claim_limit": "Fresh Link 105 D1 only; D2-D5 have not run.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=(
        "prepare", "check", "selftest", "verify-terminal", "record"))
    parser.add_argument("--text", type=Path)
    parser.add_argument("--image", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        require(not PREP.exists(), "Link 105 D1 preparation exists")
        PREP.write_bytes(canonical(derive_preparation()))
        print("Link 105 D1 preparation: PASS mutations=7")
    elif args.action == "check":
        validate_preparation(load(PREP), verify=True)
        print("Link 105 D1 check: PASS mutations=7")
    elif args.action == "selftest":
        validate_preparation(derive_preparation(), verify=False)
        print("Link 105 D1 selftest: PASS mutations=7")
    elif args.action == "verify-terminal":
        require(args.text is not None and args.image is not None,
                "verify-terminal requires --text/--image")
        verify_terminal(args.text, args.image)
        print("Link 105 D1 terminal: PASS")
    else:
        require(not RESULT.exists(), "Link 105 D1 result exists")
        RESULT.write_bytes(canonical(derive_result()))
        print("Link 105 D1: PASS D2-D5 now permitted")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (D1Error, SCREEN.CheckError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        message = error.message if isinstance(error, SCREEN.CheckError) else str(error)
        print(f"LINK 105 D1: {message}", file=sys.stderr)
        raise SystemExit(1)
