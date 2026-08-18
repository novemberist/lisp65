#!/usr/bin/env python3
"""Bind the canonical Link-116 D1-D5 owner-observed hardware result."""

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

import c2_v150_name_freight_d2_d5 as SESSION  # noqa: E402
import c2_v150_name_freight_pricing as PRICING  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
MEDIA = ARCH / "c2.3-v2.1-link116-name-freight-media-receipt.json"
ELF = ROOT / (
    "build/c2.3/v2.1-wysiwyg-text-recovery-replacement-card/final/"
    "lisp65-c2-substitution-linked.prg.elf")
PRODUCT = ROOT / (
    "build/c2.3/v2.1-wysiwyg-text-recovery-media/shared-system/"
    "lisp65-product.d81")
LIBRARY = ROOT / (
    "build/c2.3/v2.1-link116-name-freight-media/library/"
    "lisp65-library.d81")
OUT = ROOT / "build/c2.3/v2.1-link116-name-freight-hardware-contact"
PRODUCT_READBACK = OUT / "product-readback.d81"
LIBRARY_READBACK = OUT / "library-readback.d81"
GUARD = OUT / "final-terminal-return-guard.bin"
BANK0 = OUT / "final-physical-bank0.bin"
RECEIPT = ARCH / "c2.3-v2.1-link116-name-freight-device-receipt.json"
FORMAT = "lisp65-c2.3-v2.1-link116-name-freight-device-v1"
STATUS = "PASS: LINK-116 CANONICAL D1-D5 HARDWARE GREEN; HALT-1-PENDING"


ROWS = [
    ("d2-require-inspect", "(require (quote inspect))", "t"),
    ("d2-require-string-extra", "(require (quote string-extra))", "t"),
    ("d2-define-probe", "(defun trace-probe (x) (+ x 1))", "trace-probe"),
    ("d2-trace", "(trace trace-probe)", "trace-probe"),
    ("d2-traced-call", "(trace-probe 4)", "trace-enter/exit; 5"),
    ("d2-untrace", "(untrace trace-probe)", "trace-probe"),
    ("d2-restored-call", "(trace-probe 4)", "5; no trace output"),
    ("d3-require-defstruct", "(require (quote defstruct))", "t"),
    ("d3-define-point", "(defstruct point x y)", "t"),
    ("d3-make-point", "(make-point 3 4)", "(point 3 4)"),
    ("d4-nested-arithmetic", "(+ 1 (* 2 3))", "7"),
    ("d4-accessor", "(point-y (make-point 3 4))", "4"),
    ("d4-list-read", "(car (cdr (list 1 2)))", "2"),
    ("d4-durable-ceremony", "(setq v15-ceremony-probe 1)", "1"),
    ("d5-setup-published-call", "(defun v15-perf-probe (x) (+ x 1))",
     "v15-perf-probe"),
    ("d5-list-read", "(time (car (cdr (list 1 2))))", "0 2"),
    ("d5-list-write",
     "(time ((lambda (x) (progn (rplaca x 9) x)) (list 1 2)))",
     "0 (9 2)"),
    ("d5-string-op", "(time (string-ref \"abc\" 1))", "0 98"),
    ("d5-published-call", "(time (v15-perf-probe 41))", "0 42"),
]


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
    require(path.is_file() and not path.is_symlink(), f"evidence absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def media_readback() -> dict[str, Any]:
    require(PRODUCT.read_bytes() == PRODUCT_READBACK.read_bytes(),
            "product D81 readback mismatch")
    require(LIBRARY.read_bytes() == LIBRARY_READBACK.read_bytes(),
            "name-freight library D81 readback mismatch")
    return {"status": "byteidentical", "product_source": bind(PRODUCT),
            "product_readback": bind(PRODUCT_READBACK),
            "library_source": bind(LIBRARY),
            "library_readback": bind(LIBRARY_READBACK)}


def live_postconditions() -> tuple[dict[str, Any], dict[str, Any]]:
    guard = SESSION.verify_guard(GUARD)
    headroom = PRICING.verify_device(ELF.resolve(), BANK0.resolve())
    require(
        guard.get("result") == "clean"
        and guard.get("raw_hex") == "00c92d02000000000000000000000000"
        and headroom["observed"] == {"nsym": 718, "npool": 9663}
        and headroom["free"] == {"symbol_slots": 34, "namepool_bytes": 545}
        and headroom["minimum_free"] == {
            "symbol_slots": 32, "namepool_bytes": 384},
        "canonical D5 stopped-state postcondition drift")
    return guard, headroom


def derive() -> dict[str, Any]:
    media = load(MEDIA)
    require(media.get("status") ==
            "PASS: LINK-116 SAME-WORLD NAME-FREIGHT LIBRARY MEDIA",
            "green Link-116 name-freight media authority absent")
    guard, headroom = live_postconditions()
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-17",
        "status": STATUS,
        "authority": {"media": bind(MEDIA), "ELF": bind(ELF),
                      "recorder": bind(Path(__file__).resolve())},
        "contact_lineage": {
            "predecessor_setup_reds": 1,
            "predecessor_freight_first_reds": 1,
            "successful_corrected_media_contacts": 1,
            "first_red_cause": "pre-freight library variants in Link-116 medium",
        },
        "media_readback": media_readback(),
        "D1": {
            "owner_observed": True,
            "visible_liveness": ["LISP65: STAGING MEDIA",
                                 "LISP65: BUILDING HEAP",
                                 "LISP65: LOADING LIBRARIES"],
            "terminal": ["WORKBENCH 1.5.0", "lisp65>"],
            "clean_screen": True,
            "post_mount_automated_accesses": 0,
            "exact_boot_duration_seconds": None,
        },
        "freezer_library_mount": {
            "owner_physical": True, "returned_to_REPL": True,
            "medium": "L116NF.D81", "post_boot_FTP": 0},
        "rows": [{"id": row_id, "form": form, "owner_observed": result,
                  "status": "passed"} for row_id, form, result in ROWS],
        "D3_terminal_return_guard": {**guard, "capture": bind(GUARD),
            "classification": "clean", "restoration_count": 0},
        "D5_user_headroom": headroom,
        "pricing_projection_delta": {
            "projected_free": {"symbol_slots": 35, "namepool_bytes": 549},
            "observed_free": headroom["free"],
            "delta": {"symbol_slots": -1, "namepool_bytes": -4},
            "contract_still_passes": True,
            "hardware_observation_is_authoritative": True,
        },
        "execution_accounting": {
            "successful_hardware_contacts": 1, "physical_forms": 19,
            "virtual_forms": 0, "post_boot_FTP": 0,
            "observations_during_active_persistent_forms": 0,
            "final_stops": 1, "final_read_only_ranges": 2,
            "resumes_after_final_stop": 0, "product_links": 0,
            "WPLTO_runs": 0,
        },
        "next": "owner-halt-1-after-boot-duration-disposition",
        "claim_limit": (
            "Canonical D1-D5 functional, performance, guard and user-headroom "
            "hardware acceptance. Exact cold-boot duration was not timed; "
            "release publication remains closed."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and len(value.get("rows", [])) == 19
        and all(row.get("status") == "passed" for row in value["rows"])
        and value.get("D1", {}).get("exact_boot_duration_seconds") is None
        and value.get("D3_terminal_return_guard", {}).get("classification") == "clean"
        and value.get("D5_user_headroom", {}).get("status") ==
            "D5 USER HEADROOM PASS"
        and value.get("pricing_projection_delta", {}).get(
            "hardware_observation_is_authoritative") is True
        and value.get("execution_accounting") == {
            "successful_hardware_contacts": 1, "physical_forms": 19,
            "virtual_forms": 0, "post_boot_FTP": 0,
            "observations_during_active_persistent_forms": 0,
            "final_stops": 1, "final_read_only_ranges": 2,
            "resumes_after_final_stop": 0, "product_links": 0,
            "WPLTO_runs": 0}
        and value.get("next") == "owner-halt-1-after-boot-duration-disposition",
        "Link-116 canonical device-result claim drift")
    if verify:
        require(value == derive(), "Link-116 canonical device receipt stale")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "drop-row": lambda x: x["rows"].pop(),
        "claim-boot-time": lambda x: x["D1"].update(exact_boot_duration_seconds=1),
        "claim-guard-restore": lambda x: x["D3_terminal_return_guard"].update(
            classification="restored"),
        "drop-headroom": lambda x: x["D5_user_headroom"].update(status="red"),
        "hide-projection-delta": lambda x: x["pricing_projection_delta"].update(
            hardware_observation_is_authoritative=False),
        "claim-resume": lambda x: x["execution_accounting"].update(
            resumes_after_final_stop=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate(trial, verify=False)
        except ResultError:
            rejected.append(name)
    require(rejected == list(cases), "device-result mutation survived")
    return rejected


def write() -> int:
    require(not RECEIPT.exists(), "Link-116 canonical device receipt exists")
    value = derive()
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("Link-116 canonical D1-D5 device result: PASS rows=19 free=34/545")
    return 0


def check() -> int:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value), "device-result mutation set drift")
    print("Link-116 canonical D1-D5 device check: PASS rows=19 free=34/545")
    return 0


def selftest() -> int:
    value = derive(); validate(value, verify=False); mutations(value)
    print("Link-116 canonical D1-D5 device selftest: PASS mutations=6")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "check", "selftest"))
    return {"write": write, "check": check, "selftest": selftest}[
        parser.parse_args().action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResultError, SESSION.ContinuationError, PRICING.PricingError,
            OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"LINK-116 CANONICAL DEVICE RESULT: {error}", file=sys.stderr)
        raise SystemExit(1)
