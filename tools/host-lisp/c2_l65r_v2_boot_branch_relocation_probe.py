#!/usr/bin/env python3
"""One boot-branch relocation WPLTO probe; never creates product Link 33."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_l65r_v2_boot_family_probe as BOOT  # noqa: E402
import c2_l65r_v2_branch_temperature as TEMP  # noqa: E402


OUT = ROOT / "build/c2.2/substitution/link33-l65r-v2-boot-branch-probe"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v2-boot-branch-relocation-capacity-probe-receipt.json")
ATTRIBUTION = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v2-branch-temperature-attribution-receipt.json")
ATTRIBUTION_SHA = (
    "b2b74094ce5b148fc4e8c2020eb981603be73fbd94f66d544fa2cc4ed922e56b")
PREDECESSOR = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v2-producer-frame-seal-capacity-probe-receipt.json")
PREDECESSOR_SHA = (
    "874d6de3bdd507f07520e29914fff4631d6fed51b73688b3b29212f94eb5d91f")
PREDECESSOR_MAP = TEMP.CURRENT_MAP
PREDECESSOR_MAP_SHA = TEMP.CURRENT_MAP_SHA
SOURCE = ROOT / "src/vm_runtime_overlay.c"
MAIN = ROOT / "src/main.c"


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


BOOT_GUARD = (
    "if (rtov_family != LISP65_RUNTIME_OVERLAY_FAMILY_BOOT ||\n"
    "            rtov_island_state != RTOV_ISLAND_INSTALLING)\n"
    "            return VM_RUNTIME_OVERLAY_ERR_ENTRY;")
FRAME_PUBLICATION = "RTOV_INSTALL_CONTEXT = context;"
FRAME_CONSUMER = (
    "rtov_verify_context *frame =\n"
    "        (rtov_verify_context *)RTOV_INSTALL_CONTEXT;")
GENERIC_CALL = "*entry_result = RTOV_CALL(entry, context);"
SEAL_THEN_PUBLISH = (
    "context->seal = rtov_crc_mem(\n"
    "            (const uint8_t *)context, offsetof(rtov_verify_context, seal));\n"
    "        RTOV_INSTALL_CONTEXT = context;")
PUBLISH_THEN_SEAL = (
    "RTOV_INSTALL_CONTEXT = context;\n"
    "        context->seal = rtov_crc_mem(\n"
    "            (const uint8_t *)context, offsetof(rtov_verify_context, seal));")


def _errors(source: str, main: str) -> list[str]:
    errors: list[str] = []
    record = _function(
        source, "RTOV_RECORDFN uint8_t vm_runtime_overlay_record_verifier",
        "/* Keep both generated verifier tuples")
    execute = _function(
        source, "vm_runtime_overlay_status vm_runtime_overlay_exec_family(",
        "vm_runtime_overlay_status vm_runtime_overlay_exec(")
    installer = _function(
        source, "RTOV_ISLANDFN uint8_t vm_resident_island_install",
        "static void rtov_read(")
    if BOOT_GUARD not in record:
        errors.append("boot-state-guard-not-in-record-verifier")
    if FRAME_PUBLICATION not in record:
        errors.append("authenticated-frame-not-published-by-record-verifier")
    seal = record.find("context->seal = rtov_crc_mem(")
    publish = record.find(FRAME_PUBLICATION)
    if seal < 0 or publish < seal:
        errors.append("frame-published-before-seal")
    if "LISP65_RUNTIME_ISLAND_INSTALL_SLOT" in execute:
        errors.append("slot8-branch-remains-in-resident-dispatcher")
    if "LISP65_RUNTIME_OVERLAY_FORMAT_VERSION == 2u" in execute:
        errors.append("v2-branch-remains-in-resident-dispatcher")
    if execute.count(GENERIC_CALL) != 1:
        errors.append("resident-dispatcher-not-single-generic-call")
    if FRAME_CONSUMER not in installer:
        errors.append("slot8-does-not-consume-existing-install-seam")
    if "if (!frame) return VM_RUNTIME_ISLAND_ERR_CONTEXT;" not in installer:
        errors.append("published-frame-null-guard-absent")
    if "rtov_verify_context *frame = (rtov_verify_context *)opaque;" in installer:
        errors.append("caller-frame-transport-survives")
    install = main.find("vm_runtime_overlay_install_island()")
    session = main.find("c2_product_boot()")
    repl = main.find("repl()")
    if main.count("vm_runtime_overlay_install_island()") != 1 or not (
            0 <= install < session < repl):
        errors.append("installer-not-single-and-before-session-repl")
    return errors


def relocation_gate() -> dict[str, Any]:
    source = SOURCE.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    errors = _errors(source, main)
    require(not errors, "boot-branch relocation source red: " + str(errors))
    mutations = {
        "guard-moved-back-to-resident": source.replace(
            GENERIC_CALL,
            "if (slot == LISP65_RUNTIME_ISLAND_INSTALL_SLOT) {}\n    " +
            GENERIC_CALL, 1),
        "record-boot-guard-removed": source.replace(BOOT_GUARD, "", 1),
        "frame-publication-removed": source.replace(
            FRAME_PUBLICATION, "/* frame publication removed */", 1),
        "frame-published-before-seal": source.replace(
            SEAL_THEN_PUBLISH, PUBLISH_THEN_SEAL, 1),
        "caller-frame-restored": source.replace(
            FRAME_CONSUMER,
            "rtov_verify_context *frame = (rtov_verify_context *)opaque;", 1),
        "generic-call-specialized": source.replace(
            GENERIC_CALL,
            "*entry_result = RTOV_CALL(entry, slot ? context : 0);", 1),
    }
    rejected: dict[str, str] = {}
    for name, mutant in mutations.items():
        require(_errors(mutant, main),
                f"boot-branch relocation mutation accepted: {name}")
        rejected[name] = "rejected"
    return {
        "status": "passed-boot-exclusive-frame-branch-relocation",
        "source": bind(SOURCE),
        "boot_boundary": "record-verifier-slot8-after-record-authentication",
        "seam": "RTOV_INSTALL_CONTEXT-existing-lifetime-exclusive-slot",
        "resident_dispatcher": "format-neutral-single-call",
        "session_reachable_installation_branches": 0,
        "negative_mutations": rejected,
    }


def prerequisites() -> dict[str, Any]:
    require(sha(ATTRIBUTION) == ATTRIBUTION_SHA,
            "branch-temperature attribution drift")
    require(sha(PREDECESSOR) == PREDECESSOR_SHA,
            "producer-seal first-red receipt drift")
    require(sha(PREDECESSOR_MAP) == PREDECESSOR_MAP_SHA,
            "producer-seal first-red map drift")
    temperature = json.loads(ATTRIBUTION.read_text(encoding="utf-8"))
    require(temperature["decision"]["measured_boot_exclusive_bytes"] == 56
            and temperature["decision"]["minimum_required_bytes"] == 48,
            "branch-temperature decision is not applicable")
    return {
        **BOOT.BASE.prerequisites(),
        "branch_temperature_contract": bind(TEMP.CONTRACT),
        "branch_temperature_attribution": bind(ATTRIBUTION),
        "predecessor_first_red": bind(PREDECESSOR),
    }


def attribution(probe_map: Path) -> dict[str, Any]:
    before = BOOT._text_function_sizes(PREDECESSOR_MAP)
    after = BOOT._text_function_sizes(probe_map)
    names = ("vm_runtime_overlay_exec_family",
             "vm_runtime_overlay_install_island")
    functions = {
        name: {
            "before_bytes": before.get(name, 0),
            "after_bytes": after.get(name, 0),
            "delta_bytes": after.get(name, 0) - before.get(name, 0),
        } for name in names
    }
    reclaimed = (before["vm_runtime_overlay_exec_family"] -
                 after["vm_runtime_overlay_exec_family"])
    require(reclaimed >= 48,
            f"FIRST RED: branch relocation reclaimed only {reclaimed} bytes")
    return {
        "predecessor_map": bind(PREDECESSOR_MAP),
        "functions": functions,
        "resident_exec_family_reclaimed_bytes": reclaimed,
        "required_bytes": 48,
        "reclaim_headroom_bytes": reclaimed - 48,
        "classification": "boot-exclusive-branches-not-byte-shaving",
    }


def run_once() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "boot-branch WPLTO probe is one-shot and already has output")
    gate = relocation_gate()
    original = {
        "OUT": BOOT.OUT, "RECEIPT": BOOT.RECEIPT,
        "prerequisites": BOOT.prerequisites,
        "attribution": BOOT.attribution,
        "protect": BOOT.BASE.protect,
    }
    BOOT.OUT, BOOT.RECEIPT = OUT, RECEIPT
    BOOT.prerequisites, BOOT.attribution = prerequisites, attribution
    BOOT.BASE.protect = lambda _path: None
    try:
        value = BOOT.run_once()
    finally:
        BOOT.OUT, BOOT.RECEIPT = original["OUT"], original["RECEIPT"]
        BOOT.prerequisites = original["prerequisites"]
        BOOT.attribution = original["attribution"]
        BOOT.BASE.protect = original["protect"]
    first_red = str(value.get("status", "")).startswith("FIRST RED")
    value["format"] = (
        "lisp65-c2-l65r-v2-boot-branch-relocation-capacity-" +
        ("first-red-v1" if first_red else "probe-v1"))
    value["status"] = (
        "FIRST RED: boot-branch relocation WPLTO probe stopped" if first_red
        else "passed-boot-branch-relocation-wplto-no-link33")
    value["boot_branch_relocation"] = gate
    value["scope"]["link33_attempts"] = 0
    value["scope"]["hardware_runs"] = 0
    value["claim_limit"] = (
        "Boot-branch relocation semantics, product-shaped WPLTO capacity, "
        "placement and fresh structural gates only; not Link 33, hardware, "
        "promotion, or acceptance.")
    value["next_gate"] = (
        "review; automatic SOLL/KANN triage only" if first_red
        else "review before fresh Link 33")
    report = OUT / ("boot-branch-relocation-" +
                    ("first-red" if first_red else "capacity-probe") +
                    ".json")
    report.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    value["report"] = bind(report)
    os.chmod(RECEIPT, 0o644)
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    BOOT.BASE.protect(OUT)
    return value


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "boot-branch capacity receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") ==
            "passed-boot-branch-relocation-wplto-no-link33",
            "boot-branch capacity receipt is not green")
    require(value["boot_branch_relocation"]["status"] ==
            "passed-boot-exclusive-frame-branch-relocation",
            "boot-branch source gate receipt drift")
    require(sha(BOOT.BASE.LINK32) == BOOT.BASE.LINK32_SHA,
            "Link-32 rollback drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        gate = relocation_gate()
        print("c2-l65r-v2-boot-branch: SELFTEST PASS mutations=" +
              str(len(gate["negative_mutations"])))
        return 0
    value = run_once() if args.action == "run" else check()
    print("c2-l65r-v2-boot-branch: " + value["status"])
    return 3 if str(value["status"]).startswith("FIRST RED") else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, BOOT.GateError, BOOT.BASE.ProbeError,
            RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"c2-l65r-v2-boot-branch: FAIL {exc}", file=sys.stderr)
        raise SystemExit(2)
