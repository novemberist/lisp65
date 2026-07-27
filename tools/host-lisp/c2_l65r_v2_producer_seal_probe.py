#!/usr/bin/env python3
"""One record-verifier-produced frame-seal WPLTO probe; no Link 33."""

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
import c2_l65r_v2_frame_seal_probe as SEAL  # noqa: E402


OUT = ROOT / "build/c2.2/substitution/link33-l65r-v2-producer-seal-probe"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v2-producer-frame-seal-capacity-probe-receipt.json")
CONTRACT = ROOT / "config/c2-l65r-v2-producer-frame-seal-contract.json"
PREDECESSOR = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v2-verifier-frame-seal-capacity-probe-receipt.json")
PREDECESSOR_SHA = (
    "badef4b0af31020286032f1475a21070ce219b546b355744fb8a6547480575d7")
DIAGNOSIS = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-l65r-v2-verifier-frame-seal-capacity-first-red-diagnosis.json")
DIAGNOSIS_SHA = (
    "10890dc5ef835b96d7a7542d3b6e1625ec30cbe8a76d6708ffe29b3c001f717f")
PREDECESSOR_MAP = ROOT / (
    "build/c2.2/substitution/link33-l65r-v2-frame-seal-probe/"
    "l65r-v2-boot-family-seed.prg.map")
PREDECESSOR_MAP_SHA = (
    "342eda9b97942f422d8ec3dc3acf75a98ae00185e7b625b8a65c015cddb492b6")


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
    "if (context->slot == LISP65_RUNTIME_ISLAND_INSTALL_SLOT)\n"
    "        context->seal = rtov_crc_mem(\n"
    "            (const uint8_t *)context, offsetof(rtov_verify_context, seal));")


def _producer_errors(source: str) -> list[str]:
    errors: list[str] = []
    record_start = source.find(
        "RTOV_RECORDFN uint8_t vm_runtime_overlay_record_verifier")
    record_end = source.find("/* Keep both generated verifier tuples", record_start)
    dispatcher_start = source.find(
        "vm_runtime_overlay_status vm_runtime_overlay_exec_family")
    dispatcher_end = source.find(
        "vm_runtime_overlay_status vm_runtime_overlay_exec(", dispatcher_start)
    record = source[record_start:record_end]
    dispatcher = source[dispatcher_start:dispatcher_end]
    if PRODUCER not in record:
        errors.append("slot8-seal-producer-not-in-record-verifier")
    if "seal = rtov_crc_mem" in dispatcher:
        errors.append("resident-dispatcher-still-produces-seal")
    if dispatcher.count("RTOV_INSTALL_FRAME_AUTHENTICATED") != 1 or \
            "? (void *)&verify : context" not in dispatcher:
        errors.append("resident-dispatcher-is-not-pure-frame-transport")
    if SEAL.CONSUMER not in source:
        errors.append("slot8-seal-consumer-absent")
    marker = dispatcher.find("RTOV_INSTALL_FRAME_AUTHENTICATED")
    call = dispatcher.find("*entry_result = RTOV_CALL(", marker)
    span = dispatcher[marker:call] if marker >= 0 and call >= 0 else ""
    if re.search(r"verify\s*\.[A-Za-z_][A-Za-z0-9_]*\s*=", span):
        errors.append("frame-written-during-resident-transport")
    if re.search(r"rtov_island_u16\(record \+ (?:4|6|10|12|20)\) != frame->",
                 source):
        errors.append("field-by-field-rebinding-survives")
    return errors


def producer_seal_gate() -> dict[str, Any]:
    path = ROOT / "src/vm_runtime_overlay.c"
    source = path.read_text(encoding="utf-8")
    require(not _producer_errors(source),
            "producer-seal source contract is red: " +
            str(_producer_errors(source)))
    dispatcher = source.find(
        "vm_runtime_overlay_status vm_runtime_overlay_exec_family")
    marker = source.find("RTOV_INSTALL_FRAME_AUTHENTICATED", dispatcher)
    call = source.find("*entry_result = RTOV_CALL(", marker)
    post_write = source[:call] + "verify.file_len = 0;\n    " + source[call:]
    moved = source.replace(PRODUCER, "", 1)
    moved = moved[:marker] + PRODUCER.replace("context", "verify") + "\n" + moved[marker:]
    mutations = {
        "producer-removed": source.replace(PRODUCER, "", 1),
        "producer-moved-to-resident-dispatcher": moved,
        "slot-discriminant-removed": source.replace(
            "if (context->slot == LISP65_RUNTIME_ISLAND_INSTALL_SLOT)\n"
            "        context->seal",
            "context->seal", 1),
        "post-seal-transport-write": post_write,
        "consumer-removed": source.replace(SEAL.CONSUMER, "0", 1),
    }
    rejected: dict[str, str] = {}
    for name, mutant in mutations.items():
        require(_producer_errors(mutant),
                f"producer-seal mutation accepted: {name}")
        rejected[name] = "rejected"
    return {
        "status": "passed-record-verifier-produced-frame-seal",
        "source": bind(path),
        "producer": "vm_runtime_overlay_record_verifier-slot-8",
        "resident_dispatcher_role": "transport-only",
        "consumer": "vm_resident_island_install-before-scratch-reuse",
        "negative_mutations": rejected,
    }


def prerequisites() -> dict[str, Any]:
    require(PREDECESSOR.is_file() and sha(PREDECESSOR) == PREDECESSOR_SHA,
            "resident-produced seal first-red receipt drift")
    require(DIAGNOSIS.is_file() and sha(DIAGNOSIS) == DIAGNOSIS_SHA,
            "resident-produced seal diagnosis drift")
    previous = json.loads(PREDECESSOR.read_text(encoding="utf-8"))
    require(str(previous.get("status", "")).startswith("FIRST RED")
            and previous["scope"]["link33_attempts"] == 0,
            "predecessor is not the authorized no-Link first red")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    require(contract.get("status") ==
            "owner-authorized-single-successor-wplto-probe"
            and contract["single_truth"]["resident_seal_production"] ==
            "forbidden",
            "producer-seal authorization contract drift")
    return {
        **BOOT.BASE.prerequisites(),
        "producer_seal_contract": bind(CONTRACT),
        "predecessor_first_red": bind(PREDECESSOR),
        "predecessor_diagnosis": bind(DIAGNOSIS),
    }


def _section_size(path: Path, section: str) -> int:
    pattern = re.compile(
        r"^\s*[0-9a-f]+\s+[0-9a-f]+\s+([0-9a-f]+)\s+1\s+" +
        re.escape(section) + r"$")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line)
        if match:
            return int(match.group(1), 16)
    raise GateError(f"section absent from map: {section}")


def attribution(probe_map: Path) -> dict[str, Any]:
    require(sha(PREDECESSOR_MAP) == PREDECESSOR_MAP_SHA,
            "resident-produced seal WPLTO map identity drift")
    before = BOOT._text_function_sizes(PREDECESSOR_MAP)
    after = BOOT._text_function_sizes(probe_map)
    return {
        "predecessor_map": bind(PREDECESSOR_MAP),
        "resident_text": {
            "resident_producer_bytes": _section_size(PREDECESSOR_MAP, ".text"),
            "record_verifier_producer_bytes": _section_size(probe_map, ".text"),
        },
        "record_verifier_slice": {
            "resident_producer_bytes": _section_size(
                PREDECESSOR_MAP, ".lisp65_rt_rtov_record"),
            "record_verifier_producer_bytes": _section_size(
                probe_map, ".lisp65_rt_rtov_record"),
            "cap_bytes": 1792,
        },
        "installer_slice": {
            "resident_producer_bytes": _section_size(
                PREDECESSOR_MAP, ".lisp65_rt_island_00"),
            "record_verifier_producer_bytes": _section_size(
                probe_map, ".lisp65_rt_island_00"),
            "cap_bytes": 1792,
        },
        "vm_runtime_overlay_exec_family": {
            "resident_producer_bytes": before.get(
                "vm_runtime_overlay_exec_family", 0),
            "record_verifier_producer_bytes": after.get(
                "vm_runtime_overlay_exec_family", 0),
        },
    }


def run_once() -> dict[str, Any]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "producer-seal WPLTO probe is one-shot and already has output")
    gate = producer_seal_gate()
    original = {
        "OUT": SEAL.OUT, "RECEIPT": SEAL.RECEIPT,
        "frame_seal_gate": SEAL.frame_seal_gate,
        "prerequisites": SEAL.prerequisites,
        "attribution": SEAL.attribution,
        "protect": BOOT.BASE.protect,
    }
    SEAL.OUT, SEAL.RECEIPT = OUT, RECEIPT
    SEAL.frame_seal_gate = producer_seal_gate
    SEAL.prerequisites, SEAL.attribution = prerequisites, attribution
    BOOT.BASE.protect = lambda _path: None
    try:
        value = SEAL.run_once()
    finally:
        SEAL.OUT, SEAL.RECEIPT = original["OUT"], original["RECEIPT"]
        SEAL.frame_seal_gate = original["frame_seal_gate"]
        SEAL.prerequisites, SEAL.attribution = (
            original["prerequisites"], original["attribution"])
        BOOT.BASE.protect = original["protect"]
    first_red = str(value.get("status", "")).startswith("FIRST RED")
    value["format"] = (
        "lisp65-c2-l65r-v2-producer-frame-seal-capacity-" +
        ("first-red-v1" if first_red else "probe-v1"))
    value["status"] = (
        "FIRST RED: producer-frame-seal WPLTO probe stopped" if first_red
        else "passed-producer-frame-seal-wplto-no-link33")
    value["producer_frame_seal"] = gate
    value.pop("verifier_frame_seal", None)
    value["scope"]["link33_attempts"] = 0
    value["scope"]["hardware_runs"] = 0
    value["claim_limit"] = (
        "Record-verifier-produced frame-seal semantics, WPLTO capacity, "
        "placement and fresh structural gates only; not Link 33, hardware, "
        "promotion or acceptance.")
    value["next_gate"] = (
        "review; no automatic Link 33" if first_red
        else "fresh Link 33 with no inherited green")
    report = OUT / ("producer-frame-seal-" +
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
    require(RECEIPT.is_file(), "producer-seal capacity receipt absent")
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("status") ==
            "passed-producer-frame-seal-wplto-no-link33",
            "producer-seal capacity receipt is not green")
    require(value["producer_frame_seal"]["status"] ==
            "passed-record-verifier-produced-frame-seal",
            "producer-seal source gate receipt drift")
    require(sha(BOOT.BASE.LINK32) == BOOT.BASE.LINK32_SHA,
            "Link-32 rollback drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        gate = producer_seal_gate()
        print("c2-l65r-v2-producer-seal: SELFTEST PASS mutations=" +
              str(len(gate["negative_mutations"])))
        return 0
    value = run_once() if args.action == "run" else check()
    print("c2-l65r-v2-producer-seal: " + value["status"])
    return 3 if str(value["status"]).startswith("FIRST RED") else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, SEAL.GateError, BOOT.GateError, BOOT.BASE.ProbeError,
            RuntimeError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"c2-l65r-v2-producer-seal: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
