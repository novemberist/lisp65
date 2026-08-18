#!/usr/bin/env python3
"""Prepare and record the crossing-free Link-108 D1 successor."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/c2-v150-v21-product-liveness-far-device-session.json"
RUNNER = ROOT / "scripts/c2-v21-product-liveness-phase1-successor-hw.sh"
MEDIA = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.1-product-liveness-media-receipt.json")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.1-product-liveness-d1-first-red-receipt.json")
PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.1-product-liveness-phase1-successor-preparation-receipt.json")
RESULT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v2.1-product-liveness-phase1-successor-device-receipt.json")
OUT = ROOT / "build/c2.3/v2.1-product-liveness-phase1-successor"
VISIBLE = ["LISP65: STAGING MEDIA", "LISP65: BUILDING HEAP",
           "LISP65: LOADING LIBRARIES", "WORKBENCH 1.5.0", "lisp65>"]


class SuccessorError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SuccessorError(message)


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


def contract(config_override: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config_override or load(CONFIG)
    media = load(MEDIA); first_red = load(FIRST_RED)
    require(config.get("status") == "prepared-D1-repeat-authorized"
            and config.get("boot_access_free_seconds") == 45
            and config.get("recontact_authorized") is True
            and config.get("D2_D5_open") is False
            and config["identity"]["product_medium"] ==
                media["shared_system"]["product_D81"]["path"]
            and config["identity"]["library_medium"] ==
                media["library"]["D81"]["path"]
            and media["pair_identity"]["result"] == "same-world-pair"
            and media["hardware_handoff"]["D1_repeat_authorized"] is True
            and media["hardware_handoff"]["D2_D5_open"] is False
            and first_red.get("status") ==
                "D1-HARNESS-FIRST-RED-PHASE-1-CROSSED; NO-PRODUCT-LOOP-CLAIM"
            and first_red["unlock"] == {"D1": False, "D2_D5": False},
            "crossing-free D1 successor authority drift")
    return config


def runner_gate(source_override: str | None = None) -> dict[str, Any]:
    source = RUNNER.read_text(encoding="utf-8") if source_override is None else source_override
    require("dry-run|stage|confirm-terminal" in source
            and source.count("ftp_bundle_under_basic") == 2
            and 'cmp "$product" "$OUT/product-readback.d81"' in source
            and 'cmp "$library" "$OUT/library-readback.d81"' in source
            and "# PRODUCT-LIVE-BEGIN" in source
            and 'python3 "$PY" record' in source,
            "crossing-free D1 lifecycle token absent")
    live = source.split("# PRODUCT-LIVE-BEGIN", 1)[1]
    require("capture_screen" not in live and "run_m65" not in live
            and "mega65_ftp" not in live and "$FTP" not in live
            and live.count("sleep") == 1,
            "crossing-free D1 admits automated post-boot access")
    require(all(f"'{line}'" in live for line in VISIBLE),
            "crossing-free D1 owner postcondition incomplete")
    return {"result": "passed", "fresh_BASIC_capture_before_boot": 1,
            "media_readbacks_before_boot": 2,
            "automated_post_boot_observations": 0,
            "post_boot_FTP": 0, "owner_visible_postcondition": True,
            "minimum_hands_off_seconds": 45, "D2_D5_actions": 0}


def derive_preparation() -> dict[str, Any]:
    config = contract(); source = RUNNER.read_text(encoding="utf-8")
    cases: dict[str, Callable[[], None]] = {}
    for name, key, value in (("short-window", "boot_access_free_seconds", 20),
                             ("open-D2", "D2_D5_open", True)):
        def check(key=key, value=value) -> None:
            trial = deepcopy(config); trial[key] = value; contract(trial)
        cases[name] = check
    source_cases = {
        "postboot-screenshot": source.replace(
            "# PRODUCT-LIVE-BEGIN", "# PRODUCT-LIVE-BEGIN\n  capture_screen forbidden", 1),
        "postboot-monitor": source.replace(
            "# PRODUCT-LIVE-BEGIN", "# PRODUCT-LIVE-BEGIN\n  run_m65 -r", 1),
        "skip-product-readback": source.replace(
            '  cmp "$product" "$OUT/product-readback.d81"\n', "", 1),
        "skip-library-readback": source.replace(
            '  cmp "$library" "$OUT/library-readback.d81"\n', "", 1),
        "drop-terminal-owner-line": source.replace(
            "  'lisp65>' > \"$OUT/owner-visible-postcondition.txt\"\n", "", 1),
    }
    for name, candidate in source_cases.items():
        cases[name] = lambda candidate=candidate: runner_gate(candidate)
    rejected = []
    for name, action in cases.items():
        try:
            action()
        except SuccessorError:
            rejected.append(name)
    require(rejected == list(cases), "crossing-free D1 mutation survived")
    return {"format": "lisp65-c2.3-v2.1-product-liveness-phase1-successor-preparation-v1",
        "recorded_on": "2026-08-15",
        "status": "HOST-GREEN; CROSSING-FREE-D1-SUCCESSOR-AWAITS-AUTHORIZATION",
        "authority": {"first_red": bind(FIRST_RED), "media": bind(MEDIA),
            "config": bind(CONFIG), "runner": bind(RUNNER),
            "checker": bind(Path(__file__))},
        "runner_gate": runner_gate(source), "owner_visible_postcondition": VISIBLE,
        "phase_1_desk_bound": {"maximum_catalog_bytes": 2048,
            "multi_minute_normal_price_excluded": True},
        "mutations_rejected": rejected,
        "execution_accounting": {"hardware_contacts": 0, "stops": 0,
            "resumes": 0, "forms": 0, "product_links": 0, "WPLTO_runs": 0},
        "unlock": {"D1_successor": False, "D2_D5": False},
        "claim_limit": "Host preparation only; a new device contact needs authorization."}


def validate_preparation(value: dict[str, Any], *, replay: bool) -> None:
    require(value.get("status") ==
            "HOST-GREEN; CROSSING-FREE-D1-SUCCESSOR-AWAITS-AUTHORIZATION"
            and value.get("runner_gate", {}).get(
                "automated_post_boot_observations") == 0
            and len(value.get("mutations_rejected", [])) == 7
            and value.get("unlock") ==
                {"D1_successor": False, "D2_D5": False},
            "crossing-free D1 preparation claim drift")
    if replay:
        require(value == derive_preparation(), "crossing-free D1 preparation stale")


def derive_result() -> dict[str, Any]:
    prep = load(PREP); validate_preparation(prep, replay=True)
    lines = (OUT / "owner-visible-postcondition.txt").read_text(
        encoding="utf-8").splitlines()
    require(lines == VISIBLE and (OUT / "owner-terminal-confirmed").is_file(),
            "owner terminal confirmation absent")
    config = load(CONFIG)
    product = ROOT / config["identity"]["product_medium"]
    library = ROOT / config["identity"]["library_medium"]
    require((OUT / "product-readback.d81").read_bytes() == product.read_bytes()
            and (OUT / "library-readback.d81").read_bytes() == library.read_bytes(),
            "crossing-free D1 media readback drift")
    return {"format": "lisp65-c2.3-v2.1-product-liveness-phase1-successor-device-v1",
        "recorded_on": "2026-08-15", "status": "V21-LINK108-D1-GREEN",
        "authority": {"preparation": bind(PREP), "media": bind(MEDIA)},
        "physical_owner_observation": lines,
        "discipline": {"automated_post_boot_observations": 0,
            "stops": 0, "resumes": 0, "forms": 0},
        "unlock": {"D2_D5": True},
        "claim_limit": "D1 only; D2-D5 have not run."}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "prepare", "check", "record"))
    args = parser.parse_args()
    if args.action == "selftest":
        validate_preparation(derive_preparation(), replay=False)
        print("crossing-free D1 successor: SELFTEST PASS mutations=7")
    elif args.action == "prepare":
        require(not PREP.exists(), "crossing-free D1 preparation exists")
        PREP.write_bytes(canonical(derive_preparation()))
        print("crossing-free D1 successor: HOST GREEN authorization required")
    elif args.action == "check":
        validate_preparation(load(PREP), replay=True)
        print("crossing-free D1 successor: CHECK PASS D2-D5=CLOSED")
    else:
        require(not RESULT.exists(), "crossing-free D1 result exists")
        value = derive_result(); RESULT.write_bytes(canonical(value))
        print("crossing-free D1 successor: PASS D2-D5 now permitted")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SuccessorError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"CROSSING-FREE D1 SUCCESSOR: {error}", file=sys.stderr)
        raise SystemExit(1)
