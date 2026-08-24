#!/usr/bin/env python3
"""Run the owner-authorized R1 graph-card adapter replacement."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_r1_graph_collective_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-r1-graph-collective-adapter-replacement"
PREFLIGHT = ROOT / (
    "build/c2.3/v1.6-r1-graph-collective-adapter-replacement-preflight")
RECEIPT = ARCH / (
    "c2.3-v1.6-r1-graph-collective-adapter-replacement-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v1.6-r1-graph-collective-adapter-replacement-final-red.json")
PREDECESSOR_RED = ARCH / (
    "c2.3-v1.6-r1-graph-collective-card-final-red.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "642b902b"
STATUS = "PASS: V1.6 R1 GRAPH COLLECTIVE ADAPTER REPLACEMENT GREEN"
FORMAT = "lisp65-c2-v160-r1-graph-collective-adapter-replacement-v1"
ORIGINAL_CONFIGURE = PREV.configure_module


class AdapterReplacementError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AdapterReplacementError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    full = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").split())
    for token in ("exactly one replacement card",
                  "real qualification consumer's adapter",
                  "executed by its real caller", "one wplto",
                  "one product link", "exceptionless"):
        require(token in text, f"adapter replacement authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR_RED)
    require(value["status"] == "FINAL RED: R1 GRAPH COLLECTIVE RETURNS TO OWNER"
            and value["retry_authorized"] is False
            and value["owner_disposition_required"] is True
            and value["attempt_accounting"] == {
                "WPLTO_runs": 1, "cards_authorized": 1,
                "cards_consumed": 1, "device_contacts": 0,
                "media_builds": 0, "product_link_attempts": 1}
            and set(value["artifacts"]) == {"ELF", "PRG"}
            and "linked_mutations() missing 2 required positional arguments"
                in value["error"]["message"],
            "adapter replacement predecessor drift")
    return value


def configure_module() -> None:
    PREV.BUILD = BUILD
    PREV.PREFLIGHT = PREFLIGHT
    PREV.RECEIPT = RECEIPT
    PREV.FINAL_RED = FINAL_RED
    PREV.PREDECESSOR_RED = PREDECESSOR_RED
    PREV.DRIVER = DRIVER
    PREV.AUTHORIZATION = AUTHORIZATION
    PREV.STATUS = STATUS
    PREV.FORMAT = FORMAT
    PREV.predecessor = predecessor
    ORIGINAL_CONFIGURE()


def arm() -> dict[str, Any]:
    value = PREV.arm()
    real = value["conversions"]["real_consumer_preflight"]
    require(real["status"] ==
                "PASS: converted consumers executed by real callers"
            and real["signature_mismatch_mutation_rejected"] is True
            and len(real["local_return_callers"]) == 4,
            "adapter replacement real-consumer rung is incomplete")
    return {"status": "PASS: R1 ADAPTER REPLACEMENT ARMED 0/1",
        "authority": authorization(), "predecessor": bind(PREDECESSOR_RED),
        "unchanged_six_class_arm": value,
        "real_consumer_signature_rung": real}


def append_chain(path: Path, *, green: bool) -> None:
    value = load(path)
    value["recorded_on"] = "2026-08-19"
    value["adapter_replacement_authority"] = authorization()
    value["graph_collective_Final_Red"] = bind(PREDECESSOR_RED)
    value["adapter_replacement"] = arm()
    value["next"] = ("R1 closed; reopen input fidelity on 82-byte reserve"
                     if green else
                     "owner disposition required; no retry or downstream work")
    path.write_bytes(canonical(value))


def preflight() -> None:
    predecessor()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "adapter replacement is one-shot")
    armed = arm()
    PREV.configure_module = configure_module
    configure_module()
    PREV.preflight()
    path = PREFLIGHT / "preflight.json"
    value = load(path)
    value["adapter_replacement"] = armed
    value["adapter_replacement_authority"] = authorization()
    path.write_bytes(canonical(value))
    print("v1.6 R1 adapter replacement: PREFLIGHT PASS card=0/1 callers=real")


def card() -> None:
    predecessor()
    PREV.configure_module = configure_module
    configure_module()
    PREV.card()
    value = load(RECEIPT)
    value["status"] = STATUS
    value["format"] = FORMAT
    RECEIPT.write_bytes(canonical(value))
    append_chain(RECEIPT, green=True)
    print("v1.6 R1 adapter replacement: CARD PASS card=1/1 R1=closed")


def child(action: str) -> None:
    PREV.configure_module = configure_module
    configure_module()
    PREV.child(action)


def record_red(error: Exception) -> None:
    PREV.configure_module = configure_module
    configure_module()
    PREV.record_red(error)
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        value["status"] = "FINAL RED: R1 ADAPTER REPLACEMENT RETURNS TO OWNER"
        value["format"] = FORMAT + "-final-red"
        value["owner_disposition_required"] = True
        value["retry_authorized"] = False
        FINAL_RED.write_bytes(canonical(value))
        append_chain(FINAL_RED, green=False)


def check() -> None:
    if RECEIPT.exists():
        print("v1.6 R1 adapter replacement: CHECK PASS R1=closed")
    elif FINAL_RED.exists():
        print("v1.6 R1 adapter replacement: CHECK FINAL RED")
    elif (PREFLIGHT / "preflight.json").exists():
        print("v1.6 R1 adapter replacement: CHECK ARMED")
    else:
        print("v1.6 R1 adapter replacement: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
        "_dry", "_produce", "_scope", "_accept", "_graph"))
    parser.add_argument("mode", nargs="?", default="normal")
    args = parser.parse_args()
    if args.action == "preflight": preflight()
    elif args.action == "card": card()
    elif args.action == "check": check()
    elif args.action == "_graph":
        print(json.dumps(PREV.graph_probe(args.mode), sort_keys=True))
    else: child(args.action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"adapter replacement receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 R1 adapter replacement: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
