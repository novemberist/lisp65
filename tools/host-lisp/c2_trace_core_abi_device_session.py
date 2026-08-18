#!/usr/bin/env python3
"""Bind the physical, quiet Link-93 trace/restoration acceptance row."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/c2-trace-core-abi-device-session.json"
LINK_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-trace-core-abi-link93-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-trace-core-abi-link93-device-preparation-receipt.json"
)
GATES = ROOT / "mk/gates.mk"
FORMAT = "lisp65-c2.3-trace-core-abi-link93-device-preparation-v1"
PRODUCT_D81_SHA = "57afdf35587106ad4b813da2cfecf5220276863a939591c0667750e4e712b315"
LIBRARY_D81_SHA = "5e282937436e6d2656590490734d800fcd9fecb4b3a740a3ec39009cdeb5a1bd"
INDEX_SHA = "c5df5fa3ff650ccab7f84483f7d03e3e9b93f9090f64051e75054d9db707fdbe"
SOURCE_SHA = "c89c230fa647f8f90cf9c18845f7fe15d6eee9f9699227025f829c5c87416746"
CONTRACT_SHA = "33d1dbb062763a3f35d1960064219ef2588217a882bd7e7895961fb42a910f91"
LINK_RECEIPT_SHA = "9b60005d3bec53bb2891ca1ce85c278a41a69ba7b733976fd2db4f38aec5a05b"


class SessionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SessionError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def validate_contract(value: dict[str, Any]) -> None:
    require(value.get("format")
            == "lisp65-c2.3-trace-core-abi-link93-device-session-v1",
            "trace device contract format drift")
    require(value.get("status") == "prepared-not-run",
            "trace device row status broadened")
    require(value.get("link_authority") == {
        "path": LINK_RECEIPT.relative_to(ROOT).as_posix(),
        "status": "LINK93-HOST-AND-MEDIA-GREEN; HARDWARE-PENDING",
    }, "trace device Link-93 authority drift")
    identity = value["identity"]
    require(identity.get("cold_reset") is True
            and identity.get("boot_quiet_seconds") == 45
            and identity.get("banner") == "WORKBENCH 1.4.0"
            and identity.get("prompt") == "lisp65>",
            "trace device boot contract drift")
    require(value.get("input") == {
        "owner_physical_keyboard": True,
        "virtual_transport_forbidden": True,
        "one_form_per_submission": True,
    }, "trace device physical-input contract drift")
    require(value.get("observation_policy") == {
        "classification": "persistent-by-default",
        "monitor_during_active_form": False,
        "screen_polling_during_active_form": False,
        "first_observation": "single-postcondition-after-quiet-floor",
        "failure": "stop-row-without-device-improvisation",
    }, "trace device quiet-observation policy drift")
    rows = value.get("rows", [])
    require([row.get("id") for row in rows] == [
        "require-inspect", "define-probe", "install-trace",
        "traced-call", "remove-trace", "restored-call",
    ], "trace device row order drift")
    require([row.get("form") for row in rows] == [
        "(require (quote inspect))",
        "(defun trace-probe (x) (+ x 1))",
        "(trace trace-probe)",
        "(trace-probe 4)",
        "(untrace trace-probe)",
        "(trace-probe 4)",
    ], "trace device forms drift")
    require([row.get("quiet_floor_seconds") for row in rows]
            == [180, 180, 180, 30, 120, 30],
            "trace device quiet floors drift")
    require(rows[3].get("expect_ordered") == [
        "(trace-enter trace-probe 4)",
        "(trace-exit trace-probe 5)", "5", "lisp65>",
    ], "traced-call ordered oracle drift")
    require(rows[5].get("expect") == ["5", "lisp65>"]
            and rows[5].get("forbid") == ["trace-enter", "trace-exit"],
            "exact restoration oracle drift")
    claim = value.get("claim_limit", "")
    require("eligible for a later release scope" in claim
            and "no publication" in claim
            and "Link-91 claim" in claim,
            "trace device claim limit broadened")


def derive() -> dict[str, Any]:
    contract = load(CONFIG)
    validate_contract(contract)
    link = load(LINK_RECEIPT)
    require(link.get("status")
            == contract["link_authority"]["status"],
            "trace device row lacks a green Link-93 authority")
    require(link.get("hardware_handoff", {}).get("status")
            == "prepared-not-run"
            and link.get("attempt_accounting", {}).get("hardware_runs") == 0,
            "trace device row inherited a hardware claim")
    identity = contract["identity"]
    artifacts = {
        key: bind(ROOT / identity[key])
        for key in ("product_medium", "library_medium", "library_index",
                    "library_source")
    }
    link_media = link["media"]
    require(artifacts["product_medium"] == link_media["product_D81"]
            and artifacts["library_medium"] == link["library"]["medium"]["D81"]
            and artifacts["library_index"] == link["library"]["medium"]["index"]
            and artifacts["library_source"] == link["library"]["medium"]["inspect"],
            "trace device artifacts diverge from Link-93 closure")
    require(artifacts["product_medium"]["bytes"] == 819200
            and artifacts["library_medium"]["bytes"] == 819200
            and artifacts["library_index"]["bytes"] == 80,
            "trace device medium geometry drift")
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-09",
        "status": "TRACE-ROW-PREPARED; OWNER-SESSION-NOT-RUN",
        "bindings": {
            "contract": bind(CONFIG),
            "link_receipt": bind(LINK_RECEIPT),
            **artifacts,
        },
        "execution": {
            "hardware_runs": 0,
            "monitor_accesses_during_active_forms": 0,
            "screen_polls_during_active_forms": 0,
            "input": "physical-owner-keyboard-only",
            "forms": [row["form"] for row in contract["rows"]],
            "quiet_floors_seconds": [
                row["quiet_floor_seconds"] for row in contract["rows"]
            ],
        },
        "oracles": {
            "traced_call": contract["rows"][3]["expect_ordered"],
            "restored_call": contract["rows"][5]["expect"],
            "restored_call_forbids": contract["rows"][5]["forbid"],
        },
        "scope": {
            "product_link": 93,
            "release_claim": False,
            "public_surface_changed": False,
            "defstruct_claim": False,
            "parity_claim": False,
            "result_receipt_exists": False,
        },
    }


def validate(value: dict[str, Any], *, verify_sources: bool) -> None:
    require(value.get("format") == FORMAT,
            "trace device preparation format drift")
    require(value.get("status")
            == "TRACE-ROW-PREPARED; OWNER-SESSION-NOT-RUN",
            "trace device preparation status broadened")
    require(value.get("execution") == {
        "hardware_runs": 0,
        "monitor_accesses_during_active_forms": 0,
        "screen_polls_during_active_forms": 0,
        "input": "physical-owner-keyboard-only",
        "forms": [
            "(require (quote inspect))",
            "(defun trace-probe (x) (+ x 1))",
            "(trace trace-probe)", "(trace-probe 4)",
            "(untrace trace-probe)", "(trace-probe 4)",
        ],
        "quiet_floors_seconds": [180, 180, 180, 30, 120, 30],
    }, "trace device execution contract drift")
    require(value.get("oracles") == {
        "traced_call": [
            "(trace-enter trace-probe 4)",
            "(trace-exit trace-probe 5)", "5", "lisp65>",
        ],
        "restored_call": ["5", "lisp65>"],
        "restored_call_forbids": ["trace-enter", "trace-exit"],
    }, "trace device result oracle drift")
    bindings = value.get("bindings", {})
    require(bindings.get("contract") == {
        "path": "config/c2-trace-core-abi-device-session.json",
        "bytes": 2599,
        "sha256": CONTRACT_SHA,
    } and bindings.get("link_receipt") == {
        "path": "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.3-trace-core-abi-link93-receipt.json",
        "bytes": 7288,
        "sha256": LINK_RECEIPT_SHA,
    } and bindings.get("product_medium") == {
        "path": "build/c2.3/trace-core-abi-link93-r6/"
                "trace-acceptance-media/shared-system/lisp65-product.d81",
        "bytes": 819200,
        "sha256": PRODUCT_D81_SHA,
    } and bindings.get("library_medium") == {
        "path": "build/c2.3/trace-core-abi-link93-r6/"
                "trace-acceptance-media/trace-library/lisp65-library.d81",
        "bytes": 819200,
        "sha256": LIBRARY_D81_SHA,
    } and bindings.get("library_index") == {
        "path": "build/c2.3/trace-core-abi-link93-r6/"
                "trace-acceptance-media/trace-library/l65index",
        "bytes": 80,
        "sha256": INDEX_SHA,
    } and bindings.get("library_source") == {
        "path": "build/c2.3/trace-core-abi-link93-r6/"
                "trace-acceptance-media/trace-library/inspect.l65s",
        "bytes": 5668,
        "sha256": SOURCE_SHA,
    }, "trace device staged identity drift")
    require(value.get("scope") == {
        "product_link": 93,
        "release_claim": False,
        "public_surface_changed": False,
        "defstruct_claim": False,
        "parity_claim": False,
        "result_receipt_exists": False,
    }, "trace device preparation claim broadened")
    if verify_sources:
        require(value == derive(), "trace device preparation receipt is stale")


def rejected_mutations(base: dict[str, Any]) -> list[str]:
    mutations: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-run": lambda x: x["execution"].update(hardware_runs=1),
        "allow-monitor": lambda x: x["execution"].update(
            monitor_accesses_during_active_forms=1),
        "allow-polling": lambda x: x["execution"].update(
            screen_polls_during_active_forms=1),
        "virtual-input": lambda x: x["execution"].update(input="virtual"),
        "drop-require": lambda x: x["execution"]["forms"].pop(0),
        "swap-trace-untrace": lambda x: x["execution"]["forms"].reverse(),
        "short-persistent-floor": lambda x: x["execution"][
            "quiet_floors_seconds"].__setitem__(2, 1),
        "drop-enter": lambda x: x["oracles"]["traced_call"].pop(0),
        "drop-exit": lambda x: x["oracles"]["traced_call"].pop(1),
        "wrong-result": lambda x: x["oracles"].update(restored_call=["4", "lisp65>"]),
        "allow-post-untrace-enter": lambda x: x["oracles"][
            "restored_call_forbids"].remove("trace-enter"),
        "replace-product-medium": lambda x: x["bindings"][
            "product_medium"].update(sha256="00" * 32),
        "replace-library-medium": lambda x: x["bindings"][
            "library_medium"].update(sha256="00" * 32),
        "replace-link-authority": lambda x: x["bindings"][
            "link_receipt"].update(sha256="00" * 32),
        "claim-release": lambda x: x["scope"].update(release_claim=True),
        "claim-public": lambda x: x["scope"].update(public_surface_changed=True),
        "claim-defstruct": lambda x: x["scope"].update(defstruct_claim=True),
        "claim-parity": lambda x: x["scope"].update(parity_claim=True),
        "forge-result": lambda x: x["scope"].update(result_receipt_exists=True),
    }
    rejected: list[str] = []
    for name, mutate in mutations.items():
        candidate = deepcopy(base)
        mutate(candidate)
        try:
            validate(candidate, verify_sources=False)
        except SessionError:
            rejected.append(name)
    require(len(rejected) == len(mutations),
            "trace device mutation survived: "
            + ", ".join(sorted(set(mutations) - set(rejected))))
    return rejected


def gate_wiring() -> None:
    text = GATES.read_text(encoding="utf-8")
    require(all(token in text for token in (
        "c2-trace-core-abi-device-selftest:",
        "python3 tools/host-lisp/c2_trace_core_abi_device_session.py selftest",
        "c2-trace-core-abi-device-check:",
        "python3 tools/host-lisp/c2_trace_core_abi_device_session.py check",
        "check-source: c2-trace-core-abi-device-selftest",
    )), "trace device preparation gate wiring absent")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    if action == "record":
        value = derive()
        validate(value, verify_sources=False)
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_bytes(canonical(value))
        print(f"trace core-ABI device row: WROTE {RECEIPT.relative_to(ROOT)}")
        return 0
    value = load(RECEIPT)
    gate_wiring()
    validate(value, verify_sources=(action == "check"))
    mutations = rejected_mutations(value)
    if action == "check":
        print("trace core-ABI device row: PASS prepared-not-run")
    else:
        print(f"trace core-ABI device row selftest: PASS mutations={len(mutations)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SessionError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as error:
        print(f"trace core-ABI device row: FAIL: {error}", file=sys.stderr)
        raise SystemExit(2)
