#!/usr/bin/env python3
"""Run the owner-authorized R1 scope-projection replacement card."""

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

import c2_v160_r1_graph_collective_adapter_replacement as PREV  # noqa: E402
import c2_v160_r1_scope_projection_repair as REPAIR  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-r1-scope-projection-replacement"
PREFLIGHT = ROOT / "build/c2.3/v1.6-r1-scope-projection-replacement-preflight"
RECEIPT = ARCH / "c2.3-v1.6-r1-scope-projection-replacement-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-r1-scope-projection-replacement-final-red.json"
PREDECESSOR_RED = ARCH / (
    "c2.3-v1.6-r1-graph-collective-adapter-replacement-final-red.json")
ATTRIBUTION = ARCH / "c2.3-v1.6-r1-scope-identity-attribution-receipt.json"
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "d55b5d2a"
STATUS = "PASS: V1.6 R1 SCOPE PROJECTION REPLACEMENT GREEN — R1 CLOSED"
FORMAT = "lisp65-c2-v160-r1-scope-projection-replacement-v1"
ORIGINAL_CONFIGURE = PREV.configure_module


class ProjectionReplacementError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ProjectionReplacementError(message)


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
    for token in ("projection is derived only after complete configuration",
                  "early-capture mutation", "all six conversions",
                  "one wplto", "one product link", "scope and acceptance",
                  "green closes r1"):
        require(token in text, f"projection replacement authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    red = load(PREDECESSOR_RED)
    attribution = load(ATTRIBUTION)
    require(red["status"] ==
                "FINAL RED: R1 ADAPTER REPLACEMENT RETURNS TO OWNER"
            and red["retry_authorized"] is False
            and red["owner_disposition_required"] is True
            and red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["cards_consumed"] == 1
            and "scope identity differs from candidate projection"
                in red["error"]["message"]
            and attribution["decision"]["classification"] ==
                "incomplete-candidate-projection-at-scope-boundary"
            and attribution["disposition"]["successor_cards_authorized"] == 0,
            "scope projection predecessor/attribution drift")
    return red


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


def configured_collective_arm() -> dict[str, Any]:
    """Run the inherited arm after the real configuration chain."""
    PREV.configure_module = configure_module
    configure_module()
    core = PREV.PREV.PREV.PREV.CORE
    core.install()
    core.PRODUCT.BASE.configure()
    return PREV.arm()


def run_configured_collective_arm() -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(DRIVER), "_configured_arm"], cwd=ROOT,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0,
            f"configured six-conversion arm red: {result.stderr}")
    value = json.loads(result.stdout)
    require(isinstance(value, dict), "configured collective arm absent")
    return value


def arm() -> dict[str, Any]:
    repair = REPAIR.preflight()
    unchanged = run_configured_collective_arm()
    real = unchanged["unchanged_six_class_arm"]["conversions"][
        "real_consumer_preflight"]
    rechecked = real["six_conversion_projection_recheck"]
    checklist = unchanged["unchanged_six_class_arm"]["conversions"][
        "inventory_ids"]
    scope = real["corrected_projection"]["scope"]
    require(repair["mutations_rejected"] == [
                "capture-before-configuration", "omit-live-scope-projection"]
            and set(rechecked) == set(checklist) and len(rechecked) == 6
            and len({row["projection_sha256"]
                     for row in rechecked.values()}) == 1
            and all(row["complete_abort_component"] is True
                    for row in rechecked.values())
            and "LISP65_C2_ABORT_DRIVER_FAR" in scope["defines"],
            "projection repair or six-conversion recheck incomplete")
    return {"status": "PASS: R1 SCOPE PROJECTION REPLACEMENT ARMED 0/1",
        "authority": authorization(), "predecessor": bind(PREDECESSOR_RED),
        "attribution": bind(ATTRIBUTION), "projection_order_gate": repair,
        "corrected_projection": real["corrected_projection"],
        "six_conversion_projection_recheck": rechecked,
        "unchanged_collective_arm": unchanged}


def append_chain(path: Path, *, green: bool) -> None:
    value = load(path)
    value["recorded_on"] = "2026-08-19"
    value["scope_projection_replacement_authority"] = authorization()
    value["adapter_replacement_Final_Red"] = bind(PREDECESSOR_RED)
    value["scope_identity_attribution"] = bind(ATTRIBUTION)
    value["scope_projection_replacement"] = arm()
    value["next"] = ("R1 closed; reopen input fidelity on 82-byte reserve"
                     if green else
                     "owner disposition required; no retry or downstream work")
    path.write_bytes(canonical(value))


def preflight() -> None:
    predecessor()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "scope projection replacement is one-shot")
    armed = arm()
    PREV.configure_module = configure_module
    configure_module()
    core = PREV.PREV.PREV.PREV.CORE
    core.install()
    core.PRODUCT.BASE.configure()
    PREV.preflight()
    path = PREFLIGHT / "preflight.json"
    value = load(path)
    value["scope_projection_replacement"] = armed
    value["scope_projection_replacement_authority"] = authorization()
    path.write_bytes(canonical(value))
    print("v1.6 R1 scope projection: PREFLIGHT PASS card=0/1 classes=6")


def card() -> None:
    predecessor()
    PREV.configure_module = configure_module
    configure_module()
    core = PREV.PREV.PREV.PREV.CORE
    core.install()
    core.PRODUCT.BASE.configure()
    PREV.card()
    value = load(RECEIPT)
    value["status"] = STATUS
    value["format"] = FORMAT
    RECEIPT.write_bytes(canonical(value))
    append_chain(RECEIPT, green=True)
    print("v1.6 R1 scope projection: CARD PASS card=1/1 R1=CLOSED")


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
        value["status"] = "FINAL RED: R1 SCOPE PROJECTION REPLACEMENT RETURNS TO OWNER"
        value["format"] = FORMAT + "-final-red"
        value["owner_disposition_required"] = True
        value["retry_authorized"] = False
        FINAL_RED.write_bytes(canonical(value))
        append_chain(FINAL_RED, green=False)


def check() -> None:
    if RECEIPT.exists():
        print("v1.6 R1 scope projection: CHECK PASS R1=CLOSED")
    elif FINAL_RED.exists():
        print("v1.6 R1 scope projection: CHECK FINAL RED")
    elif (PREFLIGHT / "preflight.json").exists():
        print("v1.6 R1 scope projection: CHECK ARMED")
    else:
        print("v1.6 R1 scope projection: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
        "_dry", "_produce", "_scope", "_accept", "_graph",
        "_configured_arm"))
    parser.add_argument("mode", nargs="?", default="normal")
    args = parser.parse_args()
    if args.action == "preflight": preflight()
    elif args.action == "card": card()
    elif args.action == "check": check()
    elif args.action == "_graph":
        print(json.dumps(PREV.PREV.graph_probe(args.mode), sort_keys=True))
    elif args.action == "_configured_arm":
        print(json.dumps(configured_collective_arm(), sort_keys=True))
    else: child(args.action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"scope projection receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 R1 scope projection: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
