#!/usr/bin/env python3
"""Run the one authorized v1.6 primary VM_TYPE empty-phase fix card."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_hybrid_live_stack_card as BASE  # noqa: E402
import c2_v160_primary_vm_type_fix as FIX  # noqa: E402
import evidence_era as ERA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v1.6-primary-vm-type-fix-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-primary-vm-type-fix-preflight"
PROCESS = ROOT / "build/c2.3/v1.6-primary-vm-type-fix-process"
NORMAL_BUILD = PROCESS / "normal-build"
NORMAL_PREFLIGHT = PROCESS / "normal-preflight"
MUTANT_BUILD = PROCESS / "mutant-build"
MUTANT_PREFLIGHT = PROCESS / "mutant-preflight"
RECEIPT = ARCH / "c2.3-v1.6-primary-vm-type-fix-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-primary-vm-type-fix-card-final-red.json"
PREDECESSOR = ARCH / "c2.3-v1.6-hybrid-live-stack-replacement-card-receipt.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "43951e04"
FORMAT = "lisp65-c2-v160-primary-vm-type-fix-card-v1"
PREFLIGHT_STATUS = "PASS: V1.6 PRIMARY VM TYPE FIX ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 PRIMARY VM TYPE FIX FINAL WORLD GREEN"


def require(value: bool, message: str) -> None:
    if not value:
        raise BASE.CardError(message)


def authority() -> dict[str, Any]:
    value = ERA.era_bind(AUTHORIZATION, FIX.PLAN.relative_to(ROOT).as_posix())
    raw = ERA.era_blob(AUTHORIZATION, value["path"])
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("exactly one fix card", "empty phase explicitly",
                  "4,196-step reproduction", "preloaded input",
                  "all claims on the final world", "holder gate stands unchanged"):
        require(token in text, f"primary-fix authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, **value}


def predecessor() -> dict[str, Any]:
    value = BASE.load(PREDECESSOR)
    require(
        value["status"] ==
            "PASS: V1.6 HYBRID LIVE STACK REPLACEMENT FINAL WORLD GREEN"
        and value["attempt_accounting"]["WPLTO_runs"] == 1
        and value["attempt_accounting"]["product_links"] == 1
        and value["final_world_claims"]["status"] ==
            "PASS: HYBRID CLAIMS PROVED ON FINAL ELF"
        and value["final_world_claims"]["membership"]["section_bytes"] == 67,
        "primary-fix predecessor final world drift",
    )
    fix = FIX.derive()
    require(fix["status"] == "PASS: PRIMARY VM_TYPE EMPTY-PHASE FIX"
            and fix["regression"]["unfixed_mutation"]["steps"] == 4196
            and fix["regression"]["fixed_boundary"]["steps"] == 5156,
            "primary-fix host regression drift")
    return {"Final_World": value, "primary_fix": fix}


def configure_module() -> None:
    BASE.set_paths(BUILD, PREFLIGHT, tag="primary-vm-type-fix")
    BASE.PREV.configure_module()


def install() -> None:
    BASE.BUILD = BUILD
    BASE.PRODUCT_ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    BASE.PREFLIGHT = PREFLIGHT
    BASE.NORMAL_BUILD = NORMAL_BUILD
    BASE.NORMAL_PREFLIGHT = NORMAL_PREFLIGHT
    BASE.MUTANT_BUILD = MUTANT_BUILD
    BASE.MUTANT_PREFLIGHT = MUTANT_PREFLIGHT
    BASE.RECEIPT = RECEIPT
    BASE.FINAL_RED = FINAL_RED
    BASE.PREDECESSOR_RED = PREDECESSOR
    BASE.DRIVER = DRIVER
    BASE.AUTHORIZATION = AUTHORIZATION
    BASE.FORMAT = FORMAT
    BASE.PREFLIGHT_STATUS = PREFLIGHT_STATUS
    BASE.FINAL_STATUS = FINAL_STATUS
    BASE.authority = authority
    BASE.predecessor = predecessor
    BASE.configure_module = configure_module


def final_static_plane() -> dict[str, Any]:
    root = BUILD / "static-plane/narrow-static"
    manifest_path = root / "stdlib-p0.manifest.json"
    manifest = BASE.load(manifest_path)
    rows = [row for row in manifest["entries"] if row["name"] == "%read-line-loop"]
    require(len(rows) == 1 and int(rows[0]["length"]) == 248,
            "final product static plane lacks fixed read-line loop")
    blob = root / "stdlib-p0.blob.bin"
    require(manifest["blob_sha256"] == hashlib.sha256(blob.read_bytes()).hexdigest(),
            "final static-plane blob/manifest identity drift")
    return {"manifest": BASE.bind(manifest_path), "blob": BASE.bind(blob),
            "function": "%read-line-loop", "encoded_bytes": 248,
            "source_fix": BASE.bind(FIX.SOURCE),
            "consumer": "product static-plane producer consumed by final link"}


def check_receipt() -> dict[str, Any]:
    value = BASE.load(RECEIPT)
    require(value["status"] == FINAL_STATUS
            and value["attempt_accounting"] == {"cards_consumed": 1,
                "WPLTO_runs": 1, "product_links": 1,
                "media_builds": 0, "device_contacts": 0},
            "primary-fix card receipt drift")
    BASE.PREV.PREV.PREV.validate_final_claims(value)
    require(value["primary_vm_type_fix"]["regression"]["unfixed_mutation"]
                ["steps"] == 4196
            and value["primary_vm_type_fix"]["regression"]["fixed_boundary"]
                ["steps"] == 5156
            and value["final_static_plane"]["encoded_bytes"] == 248,
            "primary-fix final receipt claims drift")
    return value


def main() -> int:
    install()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "check":
        check_receipt()
        print("v1.6 primary VM_TYPE fix card: CHECK PASS final-world=green")
        return 0
    result = BASE.main()
    if action == "card" and RECEIPT.is_file():
        value = BASE.load(RECEIPT)
        value.update({"format": FORMAT, "status": FINAL_STATUS,
            "primary_fix_authority": authority(),
            "primary_fix_predecessor": BASE.bind(PREDECESSOR),
            "primary_vm_type_fix": FIX.derive(),
            "final_static_plane": final_static_plane(),
            "attempt_accounting": {"cards_consumed": 1, "WPLTO_runs": 1,
                "product_links": 1, "media_builds": 0, "device_contacts": 0},
            "media_authorized": False, "device_contacts": 0,
            "holder_liveness_gate": "OPEN; Track-2 read not executed",
            "next": "Track-2 holder/liveness contract; no device acceptance"})
        RECEIPT.write_bytes(BASE.canonical(value))
        check_receipt()
    return result


if __name__ == "__main__":
    install()
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                BASE.record_red(error)
            except Exception as receipt_error:
                print(f"primary VM_TYPE Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 primary VM_TYPE fix card: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
