#!/usr/bin/env python3
"""One CRC-sealed verifier-frame WPLTO successor probe; no product Link 33."""

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


OUT = ROOT / "build/c2.2/substitution/link33-l65r-v2-frame-seal-probe"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v2-verifier-frame-seal-capacity-probe-receipt.json")
CONTRACT = ROOT / "config/c2-l65r-v2-verifier-frame-seal-contract.json"
PREDECESSOR = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v2-verifier-frame-handoff-capacity-probe-receipt.json")
PREDECESSOR_SHA = (
    "d778247b6728ae9d00d9793c75e117e799a5217ba0730b531724d2f5fc02a11f")
DIAGNOSIS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v2-verifier-frame-handoff-capacity-first-red-diagnosis.json")
DIAGNOSIS_SHA = (
    "f11bb4933a9cebf978b34f9d842119565409c7c2d53f6905c941e523035d7e16")
PREDECESSOR_MAP = ROOT / (
    "build/c2.2/substitution/link33-l65r-v2-frame-handoff-probe/"
    "l65r-v2-boot-family-seed.prg.map")
PREDECESSOR_MAP_SHA = (
    "d1c474ae3ce0d00cd879ed21e1738242e7f44babb14c020b79fe39ae0768d1ab")


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


PRODUCER = (
    "verify.seal = rtov_crc_mem(\n"
    "        (const uint8_t *)&verify, offsetof(rtov_verify_context, seal));")
CONSUMER = (
    "rtov_crc_mem((const uint8_t *)frame,\n"
    "                         offsetof(rtov_verify_context, seal)) != frame->seal")


def _seal_errors(source: str) -> list[str]:
    errors: list[str] = []
    field = source.find("uint16_t seal;", source.find("typedef struct {"))
    structure_end = source.find("} rtov_verify_context;", field)
    if field < 0 or structure_end < field:
        errors.append("seal-is-not-final-frame-field")
    producer = source.find(PRODUCER)
    marker = source.find("RTOV_INSTALL_FRAME_AUTHENTICATED")
    call = source.find("*entry_result = RTOV_CALL(", marker)
    if min(producer, marker, call) < 0 or not producer < marker < call:
        errors.append("seal-producer-cutpoint-order-invalid")
    span = source[marker:call] if marker >= 0 and call >= 0 else ""
    if re.search(r"verify\s*\.[A-Za-z_][A-Za-z0-9_]*\s*=", span):
        errors.append("frame-written-after-seal")
    if CONSUMER not in source:
        errors.append("slot8-seal-check-absent")
    if "? (void *)&verify : context" not in source[call:call + 220]:
        errors.append("slot8-does-not-consume-sealed-frame")
    if re.search(r"rtov_island_u16\(record \+ (?:4|6|10|12|20)\) != frame->",
                 source):
        errors.append("field-by-field-rebinding-survives")
    if re.search(r"install->(?:read|payload_off|image_limit|count|scratch)",
                 source):
        errors.append("second-install-representation-survives")
    return errors


def frame_seal_gate() -> dict[str, Any]:
    path = ROOT / "src/vm_runtime_overlay.c"
    source = path.read_text(encoding="utf-8")
    require(not _seal_errors(source),
            "frame-seal source contract is red: " + str(_seal_errors(source)))
    marker = source.find("RTOV_INSTALL_FRAME_AUTHENTICATED")
    call = source.find("*entry_result = RTOV_CALL(", marker)
    post_write = source[:call] + "verify.file_len = 0;\n    " + source[call:]
    mutations = {
        "producer-removed": source.replace(PRODUCER, "verify.seal = 0;", 1),
        "consumer-removed": source.replace(CONSUMER, "0", 1),
        "post-seal-write": post_write,
        "sealed-domain-shortened": source.replace(
            "(const uint8_t *)&verify, offsetof(rtov_verify_context, seal)",
            "verify.buffer, sizeof verify.buffer", 1),
        "caller-context-forwarded": source.replace(
            "? (void *)&verify : context", "? context : context", 1),
    }
    rejected: dict[str, str] = {}
    for name, mutant in mutations.items():
        require(_seal_errors(mutant), f"frame-seal mutation accepted: {name}")
        rejected[name] = "rejected"
    return {
        "status": "passed-crc-sealed-direct-frame-single-truth",
        "source": bind(path),
        "sealed_domain": "offsetof(rtov_verify_context, seal)",
        "writes_after_seal_before_slot8": 0,
        "field_rebinding_count": 0,
        "second_install_representations": 0,
        "negative_mutations": rejected,
    }


def prerequisites() -> dict[str, Any]:
    require(PREDECESSOR.is_file() and sha(PREDECESSOR) == PREDECESSOR_SHA,
            "frame-handoff first-red receipt drift")
    require(DIAGNOSIS.is_file() and sha(DIAGNOSIS) == DIAGNOSIS_SHA,
            "frame-handoff diagnosis drift")
    previous = json.loads(PREDECESSOR.read_text(encoding="utf-8"))
    require(str(previous.get("status", "")).startswith("FIRST RED")
            and previous["scope"]["link33_attempts"] == 0,
            "predecessor is not the authorized no-Link first red")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract.get("status") ==
            "owner-authorized-single-successor-wplto-probe"
            and contract["single_truth"]["field_by_field_rebinding"] ==
            "forbidden",
            "frame-seal authorization contract drift")
    return {
        **BOOT.BASE.prerequisites(),
        "frame_seal_contract": bind(CONTRACT),
        "predecessor_first_red": bind(PREDECESSOR),
        "predecessor_diagnosis": bind(DIAGNOSIS),
    }


def attribution(probe_map: Path) -> dict[str, Any]:
    require(sha(PREDECESSOR_MAP) == PREDECESSOR_MAP_SHA,
            "frame-handoff WPLTO map identity drift")
    before = BOOT._text_function_sizes(PREDECESSOR_MAP)
    after = BOOT._text_function_sizes(probe_map)
    names = ("vm_runtime_overlay_exec_family",
             "vm_runtime_overlay_install_island")
    return {
        "predecessor_map": bind(PREDECESSOR_MAP),
        "resident_functions": {
            name: {"frame_handoff_bytes": before.get(name, 0),
                   "frame_seal_bytes": after.get(name, 0),
                   "delta_bytes": after.get(name, 0) - before.get(name, 0)}
            for name in names
        },
    }


def run_once() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "frame-seal WPLTO probe is one-shot and already has output")
    gate = frame_seal_gate()
    original = {"OUT": BOOT.OUT, "RECEIPT": BOOT.RECEIPT,
                "prerequisites": BOOT.prerequisites,
                "attribution": BOOT.attribution,
                "protect": BOOT.BASE.protect}
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
        "lisp65-c2-l65r-v2-verifier-frame-seal-capacity-" +
        ("first-red-v1" if first_red else "probe-v1"))
    value["status"] = (
        "FIRST RED: verifier-frame-seal WPLTO probe stopped" if first_red
        else "passed-verifier-frame-seal-wplto-no-link33")
    value["verifier_frame_seal"] = gate
    value["scope"]["link33_attempts"] = 0
    value["scope"]["hardware_runs"] = 0
    value["claim_limit"] = (
        "CRC-sealed direct-frame semantics, WPLTO capacity, placement and "
        "fresh structural gates only; not Link 33, hardware, promotion or "
        "acceptance.")
    value["next_gate"] = (
        "review; no automatic Link 33" if first_red
        else "fresh Link 33 with no inherited green")
    report = OUT / ("verifier-frame-seal-" +
                    ("first-red" if first_red else "capacity-probe") + ".json")
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
    require(RECEIPT.is_file(), "frame-seal capacity receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") == "passed-verifier-frame-seal-wplto-no-link33",
            "frame-seal capacity receipt is not green")
    require(value["verifier_frame_seal"]["status"] ==
            "passed-crc-sealed-direct-frame-single-truth",
            "frame-seal source gate receipt drift")
    require(sha(BOOT.BASE.LINK32) == BOOT.BASE.LINK32_SHA,
            "Link-32 rollback drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        gate = frame_seal_gate()
        print("c2-l65r-v2-frame-seal: SELFTEST PASS mutations=" +
              str(len(gate["negative_mutations"])))
        return 0
    value = run_once() if args.action == "run" else check()
    print("c2-l65r-v2-frame-seal: " + value["status"])
    return 3 if str(value["status"]).startswith("FIRST RED") else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, BOOT.GateError, BOOT.BASE.ProbeError,
            RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"c2-l65r-v2-frame-seal: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
