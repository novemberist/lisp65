#!/usr/bin/env python3
"""Run the graph-rebound v1.6 input-fidelity replacement card."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_input_fidelity_output_owner_rebind as OWNER  # noqa: E402
import c2_v160_input_fidelity_reopen_replacement_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-input-fidelity-graph-rebind-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-input-fidelity-graph-rebind-preflight"
RECEIPT = ARCH / "c2.3-v1.6-input-fidelity-graph-rebind-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-input-fidelity-graph-rebind-card-final-red.json"
PREDECESSOR_RED = ARCH / (
    "c2.3-v1.6-input-fidelity-reopen-replacement-card-final-red.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "cf41465e"
PREFLIGHT_DISPOSITION = "1f2ab432"
FORMAT = "lisp65-c2-v160-input-fidelity-graph-rebind-card-v1"
STATUS = "PASS: V1.6 INPUT-FIDELITY GRAPH-REBIND REPLACEMENT GREEN"
LINK = 118
SNAPSHOT_STACK_MUTANT = False
SNAPSHOT_STACK_MUTANT_DELEGATE: Any | None = None


class GraphReplacementError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GraphReplacementError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
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
    for token in ("exactly one replacement reopen card",
                  "transitively from the ownership graph",
                  "transitive owner checking a stale path",
                  "before any wplto", "exceptionless"):
        require(token in text, f"graph-rebind authority token absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def preflight_disposition() -> dict[str, Any]:
    full = subprocess.run(
        ["git", "rev-parse", f"{PREFLIGHT_DISPOSITION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").split())
    for token in ("zero cards consumed", "status vocabulary",
                  "real-caller preflight rung", "extends to vocabulary",
                  "unknown status name", "stands unconsumed"):
        require(token in text, f"preflight disposition token absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR_RED)
    require(value["status"] ==
                "FINAL RED: INPUT-FIDELITY REOPEN REPLACEMENT RETURNS TO OWNER"
            and value["retry_authorized"] is False
            and value["attempt_accounting"]["WPLTO_runs"] == 0
            and value["attempt_accounting"]["product_link_attempts"] == 0
            and value["attribution"]["classification"] ==
                "output-path-rebind-did-not-reach-exclusive-owner"
            and value["attribution"]["product_freight_reached"] is False,
            "graph-rebind predecessor drift")
    return value


def owner_roots(core: Any) -> list[Any]:
    return [PREV.PREV.R1_TOP, core, core.PRODUCT]


def configure_module() -> None:
    # Consume the stack already configured by outer feature owners.  A
    # module-import snapshot predates those owners; reusing it here silently
    # erases every feature registered above this historical graph layer.
    live_stack = PREV.PREV.configure_stack
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT
    PREV.RECEIPT = RECEIPT; PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER; PREV.AUTHORIZATION = AUTHORIZATION
    PREV.FORMAT = FORMAT; PREV.STATUS = STATUS
    PREV.configure_module()
    lower_stack = PREV.PREV.configure_stack
    if SNAPSHOT_STACK_MUTANT:
        delegate = (SNAPSHOT_STACK_MUTANT_DELEGATE
                    if SNAPSHOT_STACK_MUTANT_DELEGATE is not None
                    else lower_stack)
    else:
        delegate = live_stack

    def graph_configure_stack(
            build: Path = BUILD, preflight: Path = PREFLIGHT, *,
            activate_capture: bool = True) -> tuple[Any, dict[str, Any]]:
        core, activation = delegate(
            build, preflight, activate_capture=activate_capture)
        OWNER.rebind(owner_roots(core), build, preflight, DRIVER, LINK)
        return core, activation

    graph_configure_stack._graph_live_stack = not SNAPSHOT_STACK_MUTANT  # type: ignore[attr-defined]
    graph_configure_stack._graph_snapshot_mutant = SNAPSHOT_STACK_MUTANT  # type: ignore[attr-defined]
    if getattr(live_stack, "_v160_input_hybrid", False):
        graph_configure_stack._v160_input_hybrid = True  # type: ignore[attr-defined]
    if getattr(live_stack, "_v160_hybrid_before_install", False):
        graph_configure_stack._v160_hybrid_before_install = True  # type: ignore[attr-defined]
    PREV.PREV.configure_stack = graph_configure_stack


def graph_gate() -> dict[str, Any]:
    PREV.configure_module()
    core = PREV.PREV.set_core_paths(BUILD, PREFLIGHT)
    value = OWNER.rebind(owner_roots(core), BUILD, PREFLIGHT, DRIVER, LINK)
    require(value["exclusive_owner_count"] == 3
            and value["stale_transitive_owner_mutation_rejected"] is True
            and all(path == BUILD.relative_to(ROOT).as_posix()
                    for path in value["paths_after"].values()),
            "graph-derived output owner gate drift")
    return value


def run_graph_gate() -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER), "_owner_graph"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0,
            f"graph-derived owner preflight red: {result.stderr}")
    value = json.loads(result.stdout)
    require(isinstance(value, dict), "owner graph returned no object")
    return value


def real_consumer_vocabulary_gate(value: dict[str, Any]) -> dict[str, Any]:
    """Execute the actual inherited card consumer on the emitted status."""
    PREV.PREV.validate_card_preflight(value)
    mutant = dict(value)
    mutant["status"] = "PASS: UNKNOWN INPUT-FIDELITY SUCCESSOR ARMED 0/1"
    rejected = False
    try:
        PREV.PREV.validate_card_preflight(mutant)
    except Exception:
        rejected = True
    require(rejected, "unknown preflight status vocabulary survived real consumer")
    return {"status": "PASS: REAL CARD CONSUMER ACCEPTS EMITTED VOCABULARY",
        "emitted_status": value["status"],
        "consumer": "c2_v160_input_fidelity_reopen_card.validate_card_preflight",
        "unknown_status_mutation_rejected": True}


def preflight_resume() -> None:
    predecessor(); authorization(); disposition = preflight_disposition()
    require((PREFLIGHT / "preflight.json").is_file()
            and not (PREFLIGHT / "card-invocation.json").exists()
            and not BUILD.exists() and not RECEIPT.exists() and not FINAL_RED.exists(),
            "preflight vocabulary resume crossed the card boundary")
    path = PREFLIGHT / "preflight.json"
    value = load(path)
    require(value["status"] ==
                "PASS: INPUT-FIDELITY GRAPH-REBIND REPLACEMENT ARMED 0/1"
            and value["transitive_output_owner_rebind"] == run_graph_gate(),
            "persisted graph-rebind preflight drift before vocabulary resume")
    value["real_consumer_vocabulary"] = real_consumer_vocabulary_gate(value)
    value["preflight_vocabulary_disposition"] = disposition
    value["attempt_accounting"] = {"cards_consumed": 0, "WPLTO_runs": 0,
        "product_links": 0, "media_builds": 0, "device_contacts": 0}
    path.write_bytes(canonical(value))
    print("v1.6 input fidelity graph rebind: PREFLIGHT RESUME PASS "
          "card=0/1 real-consumer-vocabulary=green mutation=red")


def preflight() -> None:
    predecessor(); authorization()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "graph-rebind replacement is one-shot")
    graph = run_graph_gate()
    configure_module()
    PREV.preflight()
    path = PREFLIGHT / "preflight.json"
    value = load(path)
    value["status"] = "PASS: INPUT-FIDELITY GRAPH-REBIND REPLACEMENT ARMED 0/1"
    value["format"] = FORMAT + "-preflight"
    value["graph_rebind_authority"] = authorization()
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["transitive_output_owner_rebind"] = graph
    value["real_consumer_vocabulary"] = real_consumer_vocabulary_gate(value)
    value["preflight_vocabulary_disposition"] = preflight_disposition()
    path.write_bytes(canonical(value))
    print("v1.6 input fidelity graph rebind: PREFLIGHT PASS "
          "card=0/1 owners=3 stale-mutation=red")


def card() -> None:
    predecessor(); authorization(); configure_module()
    value = load(PREFLIGHT / "preflight.json")
    require(value["status"] ==
                "PASS: INPUT-FIDELITY GRAPH-REBIND REPLACEMENT ARMED 0/1"
            and value["transitive_output_owner_rebind"] == run_graph_gate()
            and value["real_consumer_vocabulary"] ==
                real_consumer_vocabulary_gate(value),
            "persisted graph-rebind preflight drift")
    PREV.card()
    receipt = load(RECEIPT)
    receipt["format"] = FORMAT; receipt["status"] = STATUS
    receipt["graph_rebind_authority"] = authorization()
    receipt["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    receipt["transitive_output_owner_rebind"] = value[
        "transitive_output_owner_rebind"]
    receipt["next"] = "owner device acceptance of v1.6 items 1 and 2"
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 input fidelity graph rebind: CARD PASS card=1/1 "
          "device-path=OPEN")


def child(action: str) -> None:
    configure_module()
    PREV.child(action)


def record_red(error: Exception) -> None:
    configure_module()
    PREV.record_red(error)
    if not FINAL_RED.exists():
        return
    value = load(FINAL_RED)
    value["format"] = FORMAT + "-final-red"
    value["status"] = "FINAL RED: INPUT-FIDELITY GRAPH REBIND RETURNS TO OWNER"
    value["graph_rebind_authority"] = authorization()
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["retry_authorized"] = False
    value["owner_disposition_required"] = True
    if "exclusive producer build directory was pre-created" in str(error):
        value["attempt_accounting"]["WPLTO_runs"] = 0
        value["attempt_accounting"]["product_link_attempts"] = 0
    FINAL_RED.write_bytes(canonical(value))


def check() -> None:
    if RECEIPT.exists(): print("v1.6 input fidelity graph rebind: CHECK PASS")
    elif FINAL_RED.exists(): print("v1.6 input fidelity graph rebind: CHECK FINAL RED")
    elif (PREFLIGHT / "preflight.json").exists():
        print("v1.6 input fidelity graph rebind: CHECK ARMED")
    else: print("v1.6 input fidelity graph rebind: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
        "_dry", "_produce", "_scope", "_accept", "_r1_arm",
        "_owner_graph", "preflight-resume"))
    action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "preflight-resume": preflight_resume()
    elif action == "card": card()
    elif action == "check": check()
    elif action == "_owner_graph": print(json.dumps(graph_gate(), sort_keys=True))
    else: child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"graph-rebind Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 input fidelity graph rebind: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
