#!/usr/bin/env python3
"""Prepare/check D2-D5 plus the release-terminal user-headroom readback."""

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
import c2_v150_device_session as BASE  # noqa: E402
import c2_v150_name_freight_pricing as HEADROOM  # noqa: E402
import repl_screen_check as SCREEN  # noqa: E402


CONFIG = ROOT / "config/c2-v150-name-freight-d2-d5.json"
RUNNER = ROOT / "scripts/c2-v150-name-freight-d2-d5-hw.sh"
D1 = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-name-freight-d1-receipt.json")
MEDIA = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-name-freight-media-receipt.json")
PREP = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-name-freight-d2-d5-preparation-receipt.json")
RESULT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-name-freight-d2-d5-receipt.json")
OUT = ROOT / "build/c2.3/v1.5.0-name-freight-d2-d5"
FORMAT = "lisp65-c2.3-v1.5.0-name-freight-d2-d5-preparation-v1"
STATUS = "V150-NAME-FREIGHT-D2-D5-PREPARED-NOT-RUN"


class ContinuationError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ContinuationError(message)


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


def rows() -> list[dict[str, Any]]:
    return BASE.rows_contract()


def contract(value: dict[str, Any] | None = None,
             *, require_D1: bool) -> dict[str, Any]:
    value = value or load(CONFIG)
    media = load(MEDIA)
    require(value.get("format") == "lisp65-c2-v150-name-freight-d2-d5-v1"
            and value.get("status") == "prepared-not-run"
            and value.get("order") == ["D2", "D3", "D4", "D5"]
            and value.get("rows_authority") == BASE.ROWS.relative_to(ROOT).as_posix()
            and value.get("headroom_contract")
                == HEADROOM.CONTRACT.relative_to(ROOT).as_posix()
            and value.get("identity", {}).get("product_medium")
                == media["shared_system"]["product_D81"]["path"]
            and value.get("identity", {}).get("library_medium")
                == media["library"]["D81"]["path"]
            and len(rows()) == 19,
            "name-freight D2-D5 contract/media drift")
    if require_D1:
        d1 = load(D1)
        require(d1.get("status") == "V150-NAME-FREIGHT-D1-GREEN"
                and d1.get("unlock", {}).get("D2_D5") is True,
                "green name-freight D1 authority absent")
    return value


def runner_gate(source_override: str | None = None) -> dict[str, Any]:
    source = source_override or RUNNER.read_text(encoding="utf-8")
    require("dry-run|confirm-library|wait-row|capture-final" in source
            and "mega65_ftp" not in source and "ftp_bundle" not in source
            and "# ACTIVE-FORM-BEGIN" in source
            and "# ACTIVE-FORM-END" in source
            and source.count('python3 "$PY" verify-guard') == 2
            and source.count('python3 "$PY" verify-headroom') == 1
            and "0x00000000:0x0000c000" in source
            and "D1_GREEN" in source,
            "name-freight D2-D5 runner lifecycle token drift")
    active = source.split("# ACTIVE-FORM-BEGIN", 1)[1].split(
        "# ACTIVE-FORM-END", 1)[0]
    require("$M65" not in active and "capture_screen" not in active
            and "sleep" in active,
            "name-freight active form window admits an observer")
    final = source.split('[ -e "$OUT/rows-complete" ]', 1)[1]
    require(final.index("final-physical-bank0.bin")
            < final.index("verify-headroom")
            < final.rindex("final-capture-complete"),
            "headroom readback is not release-terminal before completion")
    return {"result": "passed", "physical_rows": 19,
            "post_boot_FTP": 0, "product_reboots": 0,
            "active_form_observations": 0, "guard_readbacks": 2,
            "final_stops": 1, "headroom_readbacks": 1,
            "headroom_addresses": "candidate ELF derived"}


def mutations(config: dict[str, Any], source: str) -> list[str]:
    cases: dict[str, Callable[[], None]] = {}
    changed = deepcopy(config); changed["headroom_contract"] = "missing"
    cases["drop-headroom-contract"] = lambda: contract(changed, require_D1=False)
    changed2 = deepcopy(config); changed2["identity"]["library_medium"] = "old"
    cases["reuse-old-library"] = lambda: contract(changed2, require_D1=False)
    source_cases = {
        "observe-active-form": source.replace(
            '  sleep "$quiet"\n  # ACTIVE-FORM-END',
            '  capture_screen forbidden\n  sleep "$quiet"\n'
            '  # ACTIVE-FORM-END', 1),
        "add-FTP": source.replace("# NO-POST-BOOT-FTP", "mega65_ftp forbidden", 1),
        "drop-headroom-readback": source.replace(
            'python3 "$PY" verify-headroom --path '
            '"$OUT/final-physical-bank0.bin"\n', "", 1),
        "hardcode-counter-address": source.replace(
            '"0x00000000:0x0000c000=$OUT/final-physical-bank0.bin"',
            '"0x0000005f:0x00000061=$OUT/final-physical-bank0.bin"', 1),
    }
    for name, candidate in source_cases.items():
        cases[name] = lambda candidate=candidate: runner_gate(candidate)
    rejected: list[str] = []
    for name, run in cases.items():
        try:
            run()
        except (ContinuationError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "name-freight D2-D5 mutation survived")
    return rejected


def derive_preparation(*, require_D1: bool) -> dict[str, Any]:
    config = contract(require_D1=require_D1)
    source = RUNNER.read_text(encoding="utf-8")
    authority = {"media": bind(MEDIA), "config": bind(CONFIG),
                 "rows": bind(BASE.ROWS), "headroom_contract": bind(HEADROOM.CONTRACT),
                 "runner": bind(RUNNER), "checker": bind(Path(__file__))}
    if require_D1:
        authority["D1"] = bind(D1)
    return {
        "format": FORMAT, "recorded_on": "2026-08-11", "status": STATUS,
        "authority": authority,
        "session": {"order": config["order"], **runner_gate(source)},
        "mutations_rejected": mutations(config, source),
        "execution_accounting": {"new_hardware_contacts": 0, "forms": 0,
                                 "product_links": 0, "WPLTO_runs": 0},
        "claim_limit": (
            "Fresh D2-D5 preparation after green D1. The terminal D5 stop must "
            "pass performance, guard and ELF-derived user-headroom oracles."),
    }


def validate_preparation(value: dict[str, Any], *, verify: bool) -> None:
    require(value.get("format") == FORMAT and value.get("status") == STATUS
            and value.get("session", {}).get("physical_rows") == 19
            and value.get("session", {}).get("headroom_readbacks") == 1
            and len(value.get("mutations_rejected", [])) == 6
            and value.get("execution_accounting") == {
                "new_hardware_contacts": 0, "forms": 0,
                "product_links": 0, "WPLTO_runs": 0},
            "name-freight D2-D5 preparation claim drift")
    if verify:
        require(value == derive_preparation(require_D1=True),
                "name-freight D2-D5 preparation stale")


def verify_row(row_id: str, text: Path, image: Path) -> dict[str, Any]:
    try:
        return BASE.verify_row(row_id, text, image)
    except BASE.SessionError as error:
        raise ContinuationError(str(error)) from error


def verify_guard(path: Path) -> dict[str, Any]:
    try:
        return BASE.verify_guard(path)
    except BASE.SessionError as error:
        raise ContinuationError(str(error)) from error


def verify_headroom(path: Path) -> dict[str, Any]:
    try:
        return HEADROOM.verify_device(HEADROOM.ELF, path)
    except HEADROOM.PricingError as error:
        raise ContinuationError(str(error)) from error


def derive_result() -> dict[str, Any]:
    prep = load(PREP); validate_preparation(prep, verify=True)
    require((OUT / "final-capture-complete").is_file(),
            "name-freight final stopped-state capture absent")
    results = [verify_row(row["id"], OUT / f"row-{row['id']}.txt",
                          OUT / f"row-{row['id']}.png") for row in rows()]
    guard = verify_guard(OUT / "final-terminal-return-guard.bin")
    headroom = verify_headroom(OUT / "final-physical-bank0.bin")
    return {
        "format": "lisp65-c2.3-v1.5.0-name-freight-d2-d5-v1",
        "recorded_on": "2026-08-11",
        "status": "V150-NAME-FREIGHT-D1-D5-HARDWARE-GREEN; OWNER-HALT-1-PENDING",
        "authority": {"preparation": bind(PREP), "D1": bind(D1),
                      "media": bind(MEDIA)},
        "rows": results, "D3_guard": guard, "D5_user_headroom": headroom,
        "execution_accounting": {"hardware_contacts_total": 1,
                                 "physical_forms": 19, "post_boot_FTP": 0,
                                 "product_reboots_after_D1": 0, "final_stops": 1},
        "next": "owner-halt-1",
        "claim_limit": "D1-D5 hardware acceptance only; publication remains closed.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "check", "selftest",
                                           "verify-row", "verify-guard",
                                           "verify-headroom", "record"))
    parser.add_argument("--row")
    parser.add_argument("--text", type=Path)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--path", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        require(not PREP.exists(), "name-freight D2-D5 preparation exists")
        value = derive_preparation(require_D1=True); PREP.write_bytes(canonical(value))
        print("v1.5 name-freight D2-D5 preparation: PASS mutations=6")
    elif args.action == "check":
        validate_preparation(load(PREP), verify=True)
        print("v1.5 name-freight D2-D5 check: PASS mutations=6")
    elif args.action == "selftest":
        value = derive_preparation(require_D1=False)
        require(len(value["mutations_rejected"]) == 6,
                "name-freight D2-D5 selftest mutation drift")
        print("v1.5 name-freight D2-D5 selftest: PASS mutations=6 D1=pending")
    elif args.action == "verify-row":
        require(args.row is not None and args.text is not None and args.image,
                "verify-row requires --row/--text/--image")
        result = verify_row(args.row, args.text, args.image)
        print(f"v1.5 row {args.row}: PASS {result['values']}")
    elif args.action == "verify-guard":
        require(args.path is not None, "verify-guard requires --path")
        result = verify_guard(args.path)
        print(f"v1.5 guard: PASS {result['raw_hex']}")
    elif args.action == "verify-headroom":
        require(args.path is not None, "verify-headroom requires --path")
        result = verify_headroom(args.path)
        print("v1.5 user headroom: PASS " + json.dumps(result["free"], sort_keys=True))
    else:
        require(not RESULT.exists(), "name-freight D2-D5 result exists")
        RESULT.write_bytes(canonical(derive_result()))
        print("v1.5 name-freight D1-D5: PASS owner-halt-1-pending")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContinuationError, BASE.SessionError, SCREEN.CheckError,
            HEADROOM.PricingError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        message = error.message if isinstance(error, SCREEN.CheckError) else str(error)
        print(f"V1.5 NAME FREIGHT D2-D5: {message}", file=sys.stderr)
        raise SystemExit(1)
