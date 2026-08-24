#!/usr/bin/env python3
"""Run the call-time path-derived v1.6 input-fidelity replacement card."""

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

import c2_v160_input_fidelity_phase_callback_replacement_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-input-fidelity-live-path-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-input-fidelity-live-path-preflight"
RECEIPT = ARCH / "c2.3-v1.6-input-fidelity-live-path-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-input-fidelity-live-path-card-final-red.json"
PREDECESSOR_RED = ARCH / (
    "c2.3-v1.6-input-fidelity-phase-callback-card-final-red.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "8a5fc5a9"
FORMAT = "lisp65-c2-v160-input-fidelity-live-path-card-v1"
STATUS = "PASS: INPUT-FIDELITY LIVE-PATH REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 INPUT-FIDELITY LIVE-PATH REPLACEMENT GREEN"


class LivePathError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise LivePathError(message)


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
    for token in ("no path authority resides in function defaults",
                  "exactly one replacement card",
                  "callback resolves build and preflight at call time",
                  "actual callback without path arguments",
                  "restoring either predecessor default", "exceptionless"):
        require(token in text, f"live-path authority token absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR_RED)
    require(value["status"] ==
                "FINAL RED: INPUT-FIDELITY PHASE CALLBACK RETURNS TO REVIEW"
            and value["retry_authorized"] is False
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["attempt_accounting"]["product_link_attempts"] == 1
            and value["attribution"]["classification"] ==
                "stored-default-argument-routed-no-arg-producer-to-predecessor-root",
            "live-path predecessor drift")
    return value


def live_phase_setup(build: Path | None = None,
                     preflight: Path | None = None) -> tuple[Any, dict[str, Any]]:
    """Resolve candidate roots at call time; defaults carry no authority."""
    return PREV.PREV.phase_setup(BUILD if build is None else build,
                                 PREFLIGHT if preflight is None else preflight)


def configure_module() -> None:
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT
    PREV.RECEIPT = RECEIPT; PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER; PREV.AUTHORIZATION = AUTHORIZATION
    PREV.FORMAT = FORMAT; PREV.FINAL_STATUS = FINAL_STATUS
    PREV.configure_module()
    setup_adapter = PREV.PREV.PREV
    setup_adapter.setup_owned = live_phase_setup
    reopen = PREV.PREV.PREV.PREV.PREV.PREV
    reopen.setup = live_phase_setup
    reopen.PREFLIGHT_STATUS_VOCABULARY.add(STATUS)


def run_default_probe() -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER), "_default_probe"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0,
            f"no-argument real callback probe red: {result.stderr}")
    value = json.loads(result.stdout)
    require(isinstance(value, dict), "no-argument callback returned no object")
    return value


def default_probe_child() -> None:
    PREV.PREV.ACTIVE_PHASE = "produce"
    configure_module()
    live_phase_setup()
    handoff = load(PREFLIGHT / "setup-ownership-boundary.json")
    print(json.dumps(handoff, sort_keys=True))


def no_argument_consumer_gate(value: dict[str, Any]) -> dict[str, Any]:
    handoff = run_default_probe()
    expected_build = BUILD.relative_to(ROOT).as_posix()
    expected_preflight = PREFLIGHT.relative_to(ROOT).as_posix()

    def validate(candidate: dict[str, Any]) -> None:
        require(candidate.get("producer_root") == expected_build
                and candidate.get("setup_scope") == expected_preflight
                and candidate.get("phase") == "produce",
                "no-argument callback consumed predecessor path authority")

    validate(handoff)
    rejected: list[str] = []
    for key, old in (("producer_root",
                      "build/c2.3/v1.6-input-fidelity-phase-guard-card"),
                     ("setup_scope",
                      "build/c2.3/v1.6-input-fidelity-phase-guard-preflight")):
        mutant = dict(handoff); mutant[key] = old
        try:
            validate(mutant)
        except LivePathError:
            rejected.append(key)
    require(rejected == ["producer_root", "setup_scope"],
            "stored callback path mutation survived")
    return {"status": "PASS: NO-ARGUMENT CALLBACK CONSUMES LIVE PATHS",
        "consumer": "real parameterless producer callback",
        "producer_root": expected_build, "setup_scope": expected_preflight,
        "mutations_rejected": rejected,
        "outer_preflight_status": value["status"]}


def real_consumer_vocabulary_gate(value: dict[str, Any]) -> dict[str, Any]:
    PREV.PREV.PREV.PREV.PREV.PREV.validate_card_preflight(value)
    mutant = dict(value); mutant["status"] = "PASS: UNKNOWN LIVE PATH 0/1"
    rejected = False
    try:
        PREV.PREV.PREV.PREV.PREV.PREV.validate_card_preflight(mutant)
    except Exception:
        rejected = True
    require(rejected, "unknown live-path status survived real consumer")
    return {"status": "PASS: REAL CONSUMER ACCEPTS LIVE-PATH STATUS",
        "emitted_status": value["status"],
        "unknown_status_mutation_rejected": True}


def preflight() -> None:
    predecessor(); authority = authorization()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "live-path replacement is one-shot")
    configure_module(); PREV.preflight()
    path = PREFLIGHT / "preflight.json"; value = load(path)
    live = no_argument_consumer_gate(value)
    value["format"] = FORMAT + "-preflight"; value["status"] = STATUS
    value["live_path_authority"] = authority
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["no_argument_real_consumer"] = live
    value["real_consumer_vocabulary"] = real_consumer_vocabulary_gate(value)
    path.write_bytes(canonical(value))
    print("v1.6 input fidelity live path: PREFLIGHT PASS card=0/1 "
          "no-arg-paths=live mutations=2")


def card() -> None:
    predecessor(); authority = authorization(); configure_module()
    value = load(PREFLIGHT / "preflight.json")
    require(value["status"] == STATUS
            and value["no_argument_real_consumer"]["producer_root"] ==
                BUILD.relative_to(ROOT).as_posix()
            and value["real_consumer_vocabulary"] ==
                real_consumer_vocabulary_gate(value),
            "persisted live-path preflight drift")
    PREV.PREV.PREV.PREV.PREV.PREV.card()
    receipt = load(RECEIPT)
    receipt["format"] = FORMAT; receipt["status"] = FINAL_STATUS
    receipt["live_path_authority"] = authority
    receipt["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    receipt["no_argument_real_consumer"] = value["no_argument_real_consumer"]
    receipt["phase_owned_guards"] = value["phase_owned_guards"]
    receipt["setup_ownership"] = value["setup_ownership"]
    receipt["transitive_output_owner_rebind"] = value[
        "transitive_output_owner_rebind"]
    receipt["card_owned_inventory_registration"] = value[
        "card_owned_inventory_registration"]
    receipt["next"] = "owner device acceptance of v1.6 items 1 and 2"
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 input fidelity live path: CARD PASS card=1/1 device-path=OPEN")


def child(action: str) -> None:
    configure_module(); PREV.child(action)


def record_red(error: Exception) -> None:
    configure_module(); PREV.record_red(error)
    if not FINAL_RED.exists(): return
    value = load(FINAL_RED)
    value["format"] = FORMAT + "-final-red"
    value["status"] = "FINAL RED: INPUT-FIDELITY LIVE PATH RETURNS TO REVIEW"
    value["live_path_authority"] = authorization()
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["retry_authorized"] = False; value["review_disposition_required"] = True
    FINAL_RED.write_bytes(canonical(value))


def check() -> None:
    if RECEIPT.exists(): print("v1.6 input fidelity live path: CHECK PASS")
    elif FINAL_RED.exists(): print("v1.6 input fidelity live path: CHECK FINAL RED")
    elif (PREFLIGHT / "preflight.json").exists():
        print("v1.6 input fidelity live path: CHECK ARMED")
    else: print("v1.6 input fidelity live path: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
        "_dry", "_produce", "_scope", "_accept", "_r1_arm", "_owner_graph",
        "_default_probe"))
    action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check": check()
    elif action == "_default_probe": default_probe_child()
    elif action == "_owner_graph":
        configure_module(); print(json.dumps(PREV.PREV.PREV.PREV.graph_gate(),
                                             sort_keys=True))
    else: child(action)
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"live-path Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 input fidelity live path: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
