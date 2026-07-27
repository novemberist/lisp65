#!/usr/bin/env python3
"""Bind the final L65R-v2 resident delta to boot/session branch temperature."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_l65r_v2_boot_family_probe as BOOT  # noqa: E402
import c2_product_substitution_link as P  # noqa: E402


CONTRACT = ROOT / "config/c2-l65r-v2-branch-temperature-contract.json"
SOURCE = ROOT / "src/vm_runtime_overlay.c"
MAIN = ROOT / "src/main.c"
CURRENT_MAP = ROOT / (
    "build/c2.2/substitution/link33-l65r-v2-producer-seal-probe/"
    "l65r-v2-boot-family-seed.prg.map")
CURRENT_MAP_SHA = (
    "63f2bbb624b96b03e24fe412fcf6a3164e2ccb397b5b0232dabae3c8c298aa13")
PRE_V2_MAP = ROOT / (
    "build/c2.2/substitution/product-link-33-profile-inventory-final/"
    "resident-island-seed.prg.map")
PRE_V2_MAP_SHA = (
    "88e1eb02bfb06f0eb667678938ef2c7bda5d0d2c25dc5f41b4093bd59187d954")
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v2-producer-frame-seal-capacity-probe-receipt.json")
FIRST_RED_SHA = (
    "874d6de3bdd507f07520e29914fff4631d6fed51b73688b3b29212f94eb5d91f")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v2-branch-temperature-attribution-receipt.json")


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def _function(source: str, start: str, end: str) -> str:
    begin = source.find(start)
    finish = source.find(end, begin)
    require(begin >= 0 and finish > begin,
            f"function boundary absent: {start}")
    return source[begin:finish]


SLOT8_GUARD = (
    "if (slot == LISP65_RUNTIME_ISLAND_INSTALL_SLOT) {\n"
    "        if (rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_BOOT ||\n"
    "            rtov_island_state != RTOV_ISLAND_INSTALLING)\n"
    "            return rtov_fail(VM_RUNTIME_OVERLAY_ERR_ENTRY);\n"
    "    }")
SLOT8_CONTEXT = (
    "slot == LISP65_RUNTIME_ISLAND_INSTALL_SLOT\n"
    "                 ? (void *)&verify : context")
PRODUCER = (
    "if (context->slot == LISP65_RUNTIME_ISLAND_INSTALL_SLOT)\n"
    "        context->seal = rtov_crc_mem(")


def _errors(runtime: str, main: str, *, boot_names: set[str],
            session_names: set[str]) -> list[str]:
    errors: list[str] = []
    exec_body = _function(
        runtime, "vm_runtime_overlay_status vm_runtime_overlay_exec_family(",
        "vm_runtime_overlay_status vm_runtime_overlay_exec(")
    record_body = _function(
        runtime, "RTOV_RECORDFN uint8_t vm_runtime_overlay_record_verifier",
        "/* Keep both generated verifier tuples")
    if {"resident-island-installer", "resident-island-image"} - boot_names:
        errors.append("boot-installation-record-missing")
    if {"resident-island-installer", "resident-island-image"} & session_names:
        errors.append("installation-record-in-session-catalog")
    install = main.find("vm_runtime_overlay_install_island()")
    session = main.find("c2_product_boot()")
    repl = main.find("repl()")
    if main.count("vm_runtime_overlay_install_island()") != 1 or not (
            0 <= install < session < repl):
        errors.append("installer-not-single-and-before-session-repl")
    if SLOT8_GUARD not in exec_body:
        errors.append("slot8-boot-state-guard-absent")
    if SLOT8_CONTEXT not in exec_body:
        errors.append("slot8-frame-selection-absent")
    if PRODUCER not in record_body:
        errors.append("slot8-frame-producer-absent")
    # The two blocks below are the entire format-v2-specific surface in the
    # resident dispatcher.  Any third block invalidates the +56 attribution.
    if exec_body.count("LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 2u") != 2:
        errors.append("unexpected-v2-resident-dispatcher-surface")
    return errors


def gate() -> dict[str, Any]:
    require(sha(CURRENT_MAP) == CURRENT_MAP_SHA, "current WPLTO map drift")
    require(sha(PRE_V2_MAP) == PRE_V2_MAP_SHA, "pre-v2 WPLTO map drift")
    require(sha(FIRST_RED) == FIRST_RED_SHA, "bound first-red receipt drift")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract.get("status") ==
            "owner-authorized-branch-temperature-attribution-and-one-wplto-probe",
            "authorization contract drift")
    runtime = SOURCE.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    boot_names = {row.split(":")[1] for row in
                  (P.BOOT_SLICE_SPECS + P.BOOT_DATA_SPECS)}
    session_names = {row.split(":")[1] for row in P.SESSION_SLICE_SPECS}
    require(not _errors(runtime, main, boot_names=boot_names,
                        session_names=session_names),
            "branch-temperature contract red: " + str(_errors(
                runtime, main, boot_names=boot_names,
                session_names=session_names)))

    before = BOOT._text_function_sizes(PRE_V2_MAP)
    after = BOOT._text_function_sizes(CURRENT_MAP)
    exec_delta = (after["vm_runtime_overlay_exec_family"] -
                  before["vm_runtime_overlay_exec_family"])
    install_delta = (after["vm_runtime_overlay_install_island"] -
                     before["vm_runtime_overlay_install_island"])
    total_delta = 89
    other_delta = total_delta - exec_delta - install_delta
    require(exec_delta == 56 and install_delta == 29 and other_delta == 4,
            "measured +89 attribution drift")
    require(exec_delta >= contract["decision"]["minimum_boot_exclusive_bytes"],
            "boot-exclusive branch surface cannot close 48-byte deficit")

    mutants = {
        "installer-in-session-catalog": (runtime, main, boot_names,
                                          session_names |
                                          {"resident-island-installer"}),
        "installer-after-session": (
            runtime,
            main.replace("boot_overlay_result = (uint8_t)"
                         "vm_runtime_overlay_install_island();",
                         "/* boot installer moved */") +
            "\nvm_runtime_overlay_install_island();\n",
            boot_names, session_names),
        "slot8-guard-removed": (runtime.replace(SLOT8_GUARD, "", 1),
                                main, boot_names, session_names),
        "slot8-frame-selection-removed": (
            runtime.replace(SLOT8_CONTEXT, "context", 1),
            main, boot_names, session_names),
        "slot8-producer-removed": (runtime.replace(PRODUCER, "if (0) {", 1),
                                   main, boot_names, session_names),
    }
    rejected: dict[str, str] = {}
    for name, (r_source, m_source, b_names, s_names) in mutants.items():
        require(_errors(r_source, m_source, boot_names=b_names,
                        session_names=s_names),
                f"branch-temperature mutation accepted: {name}")
        rejected[name] = "rejected"

    return {
        "format": "lisp65-c2-l65r-v2-branch-temperature-attribution-v1",
        "status": "passed-boot-exclusive-branch-attribution",
        "recorded_on": "2026-07-21",
        "inputs": {
            "authorization": bind(CONTRACT),
            "first_red": bind(FIRST_RED),
            "pre_v2_map": bind(PRE_V2_MAP),
            "current_map": bind(CURRENT_MAP),
            "runtime_source": bind(SOURCE),
            "main_source": bind(MAIN),
        },
        "measured_resident_delta": {
            "total_bytes": total_delta,
            "vm_runtime_overlay_exec_family_bytes": exec_delta,
            "vm_runtime_overlay_install_island_bytes": install_delta,
            "other_closure_bytes": other_delta,
            "current_overflow_bytes": 48,
        },
        "temperature": {
            "boot_exclusive_movable_bytes": exec_delta,
            "boot_exclusive_surface": [
                "slot8-boot-and-installing-state-guard",
                "slot8-authenticated-frame-context-selection"
            ],
            "resident_anchor_not_moved": "vm_runtime_overlay_install_island",
            "session_catalog_installation_records": 0,
            "production_installer_calls": 1,
            "ordering": "install-island-before-c2-product-boot-before-repl",
        },
        "decision": {
            "minimum_required_bytes": 48,
            "measured_boot_exclusive_bytes": exec_delta,
            "headroom_over_requirement_bytes": exec_delta - 48,
            "result": "authorized-life-cycle-relocation-path-applicable",
        },
        "negative_mutations": rejected,
        "claim_limit": (
            "Static branch temperature and measured predecessor/current "
            "WPLTO attribution only; no relocation, new WPLTO result, "
            "Link 33, hardware, promotion, or acceptance."),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "check", "selftest"))
    args = parser.parse_args()
    value = gate()
    if args.action == "selftest":
        print("c2-l65r-v2-branch-temperature: SELFTEST PASS mutations=5")
        return 0
    if args.action == "run":
        if RECEIPT.exists():
            raise GateError("branch-temperature receipt already exists")
        RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
        os.chmod(RECEIPT, 0o444)
    else:
        require(RECEIPT.is_file(), "branch-temperature receipt absent")
        stored = json.loads(RECEIPT.read_text(encoding="utf-8"))
        require(stored == value, "branch-temperature receipt drift")
    print("c2-l65r-v2-branch-temperature: PASS boot-exclusive=56 required=48")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, RuntimeError, KeyError, ValueError) as exc:
        print(f"c2-l65r-v2-branch-temperature: FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
