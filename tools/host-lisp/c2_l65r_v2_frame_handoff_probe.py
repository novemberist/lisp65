#!/usr/bin/env python3
"""One verifier-frame-handoff WPLTO successor probe; no product Link 33."""

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


OUT = ROOT / "build/c2.2/substitution/link33-l65r-v2-frame-handoff-probe"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v2-verifier-frame-handoff-capacity-probe-receipt.json")
CONTRACT = ROOT / "config/c2-l65r-v2-verifier-frame-handoff-contract.json"
PREDECESSOR = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v2-boot-family-capacity-probe-receipt.json")
PREDECESSOR_SHA = (
    "892163b704fc78aa0f7573130cf7d9e9955e3d85991e26610ec0c6b84a2819cc")
PREDECESSOR_MAP = ROOT / (
    "build/c2.2/substitution/link33-l65r-v2-boot-family-probe/"
    "l65r-v2-boot-family-seed.prg.map")
PREDECESSOR_MAP_SHA = (
    "ac2dcff8b9a165aa543474133f14a89b984d3d3a1bdd904fb610cc0e50a72f79")


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def _frame_errors(source: str) -> list[str]:
    errors: list[str] = []
    marker = "RTOV_INSTALL_FRAME_AUTHENTICATED"
    start = source.find(marker)
    call = source.find("*entry_result = RTOV_CALL(", start)
    end = source.find("#else", call)
    span = source[start:end] if start >= 0 and call >= 0 and end >= 0 else ""
    if not span:
        errors.append("authenticated-cutpoint-or-slot8-call-absent")
    if re.search(r"verify\s*\.[A-Za-z_][A-Za-z0-9_]*\s*=", span):
        errors.append("verifier-frame-written-after-authentication")
    if "? (void *)&verify : context" not in span:
        errors.append("slot8-does-not-consume-verifier-frame-directly")
    if re.search(r"install->(?:read|payload_off|image_limit|count|scratch)", source):
        errors.append("second-install-representation-survives")
    rebound = (
        "rtov_island_u16(record + 4) != frame->file_off",
        "rtov_island_u16(record + 6) != frame->file_len",
        "rtov_island_u16(record + 12) != frame->entry_off",
        "rtov_island_u16(record + 20) != frame->payload_crc",
    )
    if any(item not in source for item in rebound):
        errors.append("consumer-record-rebinding-incomplete")
    return errors


def frame_handoff_gate() -> dict[str, Any]:
    path = ROOT / "src/vm_runtime_overlay.c"
    source = path.read_text(encoding="utf-8")
    require(not _frame_errors(source),
            "verifier-frame handoff source contract is red: "
            + str(_frame_errors(source)))
    call_at = source.find("*entry_result = RTOV_CALL(", source.find(
        "RTOV_INSTALL_FRAME_AUTHENTICATED"))
    require(call_at >= 0, "Slot-8 handoff call absent")
    post_auth_write = (source[:call_at] + "verify.file_len = 0;\n    "
                       + source[call_at:])
    mutations = {
        "cutpoint-removed": source.replace(
            "RTOV_INSTALL_FRAME_AUTHENTICATED", "CUTPOINT_REMOVED", 1),
        "post-auth-write": post_auth_write,
        "caller-context-forwarded": source.replace(
            "? (void *)&verify : context", "? context : context", 1),
        "record-rebind-removed": source.replace(
            "rtov_island_u16(record + 20) != frame->payload_crc",
            "0", 1),
    }
    rejected: dict[str, str] = {}
    for name, mutant in mutations.items():
        require(_frame_errors(mutant),
                f"verifier-frame handoff mutation accepted: {name}")
        rejected[name] = "rejected"
    return {
        "status": "passed-direct-authenticated-frame-single-truth",
        "source": bind(path),
        "writes_between_authentication_and_slot8": 0,
        "second_install_representations": 0,
        "consumer_record_fields_rebound": 4,
        "negative_mutations": rejected,
    }


def prerequisites() -> dict[str, Any]:
    require(PREDECESSOR.is_file() and sha(PREDECESSOR) == PREDECESSOR_SHA,
            "boot-family first-red receipt drift")
    previous = json.loads(PREDECESSOR.read_text(encoding="utf-8"))
    require(str(previous.get("status", "")).startswith("FIRST RED")
            and previous["scope"]["link33_attempts"] == 0,
            "predecessor is not the authorized no-Link first red")
    require(CONTRACT.is_file(), "verifier-frame handoff contract absent")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract.get("status") ==
            "owner-authorized-single-successor-wplto-probe"
            and contract["single_truth"]["second_install_context"] ==
            "forbidden",
            "verifier-frame handoff authorization contract drift")
    return {
        **BOOT.BASE.prerequisites(),
        "frame_handoff_contract": bind(CONTRACT),
        "predecessor_first_red": bind(PREDECESSOR),
    }


def attribution(probe_map: Path) -> dict[str, Any]:
    require(sha(PREDECESSOR_MAP) == PREDECESSOR_MAP_SHA,
            "predecessor WPLTO map identity drift")
    before = BOOT._text_function_sizes(PREDECESSOR_MAP)
    after = BOOT._text_function_sizes(probe_map)
    names = ("vm_runtime_overlay_exec_family",
             "vm_runtime_overlay_install_island",
             "vm_resident_island_install")
    return {
        "predecessor_map": bind(PREDECESSOR_MAP),
        "functions": {
            name: {
                "predecessor_bytes": before.get(name, 0),
                "frame_handoff_bytes": after.get(name, 0),
                "delta_bytes": after.get(name, 0) - before.get(name, 0),
            } for name in names
        },
    }


def protect(path: Path) -> None:
    BOOT.BASE.protect(path)


def run_once() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "verifier-frame WPLTO probe is one-shot and already has output")
    gate = frame_handoff_gate()
    original = {
        "OUT": BOOT.OUT, "RECEIPT": BOOT.RECEIPT,
        "prerequisites": BOOT.prerequisites,
        "attribution": BOOT.attribution,
        "protect": BOOT.BASE.protect,
    }
    BOOT.OUT = OUT
    BOOT.RECEIPT = RECEIPT
    BOOT.prerequisites = prerequisites
    BOOT.attribution = attribution
    BOOT.BASE.protect = lambda _path: None
    try:
        value = BOOT.run_once()
    finally:
        BOOT.OUT = original["OUT"]
        BOOT.RECEIPT = original["RECEIPT"]
        BOOT.prerequisites = original["prerequisites"]
        BOOT.attribution = original["attribution"]
        BOOT.BASE.protect = original["protect"]

    first_red = str(value.get("status", "")).startswith("FIRST RED")
    value["format"] = (
        "lisp65-c2-l65r-v2-verifier-frame-handoff-capacity-"
        + ("first-red-v1" if first_red else "probe-v1"))
    value["status"] = (
        "FIRST RED: verifier-frame-handoff WPLTO probe stopped"
        if first_red else
        "passed-verifier-frame-handoff-wplto-no-link33")
    value["verifier_frame_handoff"] = gate
    value["scope"]["link33_attempts"] = 0
    value["scope"]["hardware_runs"] = 0
    value["claim_limit"] = (
        "Direct authenticated frame semantics, WPLTO capacity, placement and "
        "fresh structural gates only; not Link 33, hardware, promotion or "
        "acceptance.")
    value["next_gate"] = (
        "review; no automatic Link 33" if first_red
        else "fresh Link 33 with no inherited green")
    report = OUT / ("verifier-frame-handoff-" +
                    ("first-red" if first_red else "capacity-probe") + ".json")
    report.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    value["report"] = bind(report)
    os.chmod(RECEIPT, 0o644)
    RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    os.chmod(RECEIPT, 0o444)
    protect(OUT)
    return value


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "verifier-frame capacity receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") ==
            "passed-verifier-frame-handoff-wplto-no-link33",
            "verifier-frame capacity receipt is not green")
    require(value["verifier_frame_handoff"]["status"] ==
            "passed-direct-authenticated-frame-single-truth",
            "verifier-frame source gate receipt drift")
    require(sha(BOOT.BASE.LINK32) == BOOT.BASE.LINK32_SHA,
            "Link-32 rollback drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        gate = frame_handoff_gate()
        print("c2-l65r-v2-frame-handoff: SELFTEST PASS mutations=" +
              str(len(gate["negative_mutations"])))
        return 0
    value = run_once() if args.action == "run" else check()
    print("c2-l65r-v2-frame-handoff: " + value["status"])
    return 3 if str(value["status"]).startswith("FIRST RED") else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, BOOT.GateError, BOOT.BASE.ProbeError,
            RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"c2-l65r-v2-frame-handoff: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
