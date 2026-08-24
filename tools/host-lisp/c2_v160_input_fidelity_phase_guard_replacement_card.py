#!/usr/bin/env python3
"""Run the phase-correct v1.6 input-fidelity replacement card."""

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

import c2_v160_input_fidelity_setup_owner_replacement_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-input-fidelity-phase-guard-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-input-fidelity-phase-guard-preflight"
RECEIPT = ARCH / "c2.3-v1.6-input-fidelity-phase-guard-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-input-fidelity-phase-guard-card-final-red.json"
PREDECESSOR_RED = ARCH / (
    "c2.3-v1.6-input-fidelity-setup-owner-card-final-red.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "26731694"
FORMAT = "lisp65-c2-v160-input-fidelity-phase-guard-card-v1"
STATUS = "PASS: INPUT-FIDELITY PHASE-GUARD REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 INPUT-FIDELITY PHASE-GUARD REPLACEMENT GREEN"
ACTIVE_PHASE = "preflight"


class PhaseGuardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PhaseGuardError(message)


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
    for token in ("one replacement card", "a guard belongs to the phase",
                  "runs exactly once", "exists and is sha-bound",
                  "scope phase missing the identity assertion", "exceptionless"):
        require(token in text, f"phase-guard authority token absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR_RED)
    require(value["status"] ==
                "FINAL RED: INPUT-FIDELITY SETUP OWNER RETURNS TO REVIEW"
            and value["retry_authorized"] is False
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["attempt_accounting"]["product_link_attempts"] == 1
            and value["attribution"]["classification"] ==
                "phase-insensitive-setup-handoff-guard-rejected-valid-post-producer-root",
            "phase-guard predecessor drift")
    return value


def validate_phase(phase: str, *, root_exists: bool,
                   identity_asserted: bool) -> None:
    require(phase in {"produce", "scope", "accept"},
            f"unknown setup phase: {phase}")
    if phase == "produce":
        require(not root_exists,
                "producer phase received a pre-created exclusive root")
        require(not identity_asserted,
                "producer phase consumed post-production identity")
    else:
        require(root_exists,
                "read-only phase fired the pre-production absence guard")
        require(identity_asserted,
                "read-only phase omitted production identity assertion")


def production_identity(build: Path) -> dict[str, Any]:
    result = load(build / "producer-result.json")
    expected = result.get("artifacts", {})
    actual = {
        "elf": bind(build / "wplto/lisp65-c2-substitution-linked.prg.elf"),
        "prg": bind(build / "wplto/lisp65-c2-substitution-linked.prg"),
    }
    require(result.get("status") == "PASS"
            and expected.get("elf") == actual["elf"]
            and expected.get("prg") == actual["prg"],
            "read-only phase product identity drift")
    return {"status": "PASS: READ-ONLY PHASE CONSUMES PRODUCER IDENTITY",
            "producer_receipt": bind(build / "producer-result.json"),
            "artifacts": actual}


def phase_setup(build: Path = BUILD, preflight: Path = PREFLIGHT
                ) -> tuple[Any, dict[str, Any]]:
    core, activation = PREV.PREV.PREV.PREV.configure_stack(build, preflight)
    static = core.install_static(PREV.setup_scope(preflight))
    core.bind_paths_only(build, preflight)
    core.write_projections()
    require(static["consumer_observed_bytes"] == 46043,
            "candidate static-plane consumer drift")
    if ACTIVE_PHASE == "produce":
        validate_phase("produce", root_exists=build.exists(),
                       identity_asserted=False)
        receipt = preflight / "setup-ownership-boundary.json"
        declared = [core.PROJECTED_OWNERSHIP, core.PROJECTED_FULL_MAP, receipt]
        PREV.validate_setup_writes(producer_root_exists=False,
                                   setup_root=preflight,
                                   written_paths=declared)
        receipt.write_bytes(canonical({
            "status": "PASS: SETUP YIELDED EXCLUSIVE PRODUCT ROOT",
            "producer_root": build.relative_to(ROOT).as_posix(),
            "producer_root_absent_at_handoff": True,
            "setup_scope": preflight.relative_to(ROOT).as_posix(),
            "declared_writes": [path.relative_to(ROOT).as_posix()
                                for path in declared],
            "static_plane_binding": static,
            "phase": "produce",
        }))
    else:
        identity = production_identity(build)
        validate_phase(ACTIVE_PHASE, root_exists=build.exists(),
                       identity_asserted=True)
        witness = preflight / f"{ACTIVE_PHASE}-production-identity.json"
        witness.write_bytes(canonical(identity | {"phase": ACTIVE_PHASE}))
    return core, activation


def configure_module() -> None:
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT
    PREV.RECEIPT = RECEIPT; PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER; PREV.AUTHORIZATION = AUTHORIZATION
    PREV.FORMAT = FORMAT; PREV.STATUS = FINAL_STATUS
    PREV.configure_module()
    reopen = PREV.PREV.PREV.PREV
    reopen.setup = phase_setup
    reopen.PREFLIGHT_STATUS_VOCABULARY.add(STATUS)


def phase_gate() -> dict[str, Any]:
    rejected: list[str] = []
    try:
        validate_phase("scope", root_exists=False, identity_asserted=True)
    except PhaseGuardError:
        rejected.append("pre-production-guard-in-read-only-phase")
    try:
        validate_phase("scope", root_exists=True, identity_asserted=False)
    except PhaseGuardError:
        rejected.append("scope-without-production-identity")
    require(rejected == ["pre-production-guard-in-read-only-phase",
                         "scope-without-production-identity"],
            "phase guard mutation survived")
    return {"status": "PASS: GUARDS ARE PHASE-OWNED",
        "produce_invariant": "root-absent-before-exclusive-producer",
        "read_only_invariant": "root-present-and-SHA-bound-to-producer-receipt",
        "mutations_rejected": rejected}


def real_consumer_vocabulary_gate(value: dict[str, Any]) -> dict[str, Any]:
    PREV.PREV.PREV.PREV.validate_card_preflight(value)
    mutant = dict(value); mutant["status"] = "PASS: UNKNOWN PHASE GUARD 0/1"
    rejected = False
    try:
        PREV.PREV.PREV.PREV.validate_card_preflight(mutant)
    except Exception:
        rejected = True
    require(rejected, "unknown phase-guard status survived real consumer")
    return {"status": "PASS: REAL CONSUMER ACCEPTS PHASE-GUARD STATUS",
        "emitted_status": value["status"],
        "unknown_status_mutation_rejected": True}


def preflight() -> None:
    predecessor(); authority = authorization()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "phase-guard replacement is one-shot")
    configure_module()
    PREV.preflight()
    path = PREFLIGHT / "preflight.json"
    value = load(path)
    value["format"] = FORMAT + "-preflight"
    value["status"] = STATUS
    value["phase_guard_authority"] = authority
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["phase_owned_guards"] = phase_gate()
    value["real_consumer_vocabulary"] = real_consumer_vocabulary_gate(value)
    path.write_bytes(canonical(value))
    print("v1.6 input fidelity phase guard: PREFLIGHT PASS card=0/1 "
          "mutations=2")


def card() -> None:
    predecessor(); authority = authorization(); configure_module()
    value = load(PREFLIGHT / "preflight.json")
    require(value["status"] == STATUS
            and value["phase_owned_guards"] == phase_gate()
            and value["real_consumer_vocabulary"] ==
                real_consumer_vocabulary_gate(value),
            "persisted phase-guard preflight drift")
    PREV.PREV.PREV.PREV.card()
    receipt = load(RECEIPT)
    receipt["format"] = FORMAT; receipt["status"] = FINAL_STATUS
    receipt["phase_guard_authority"] = authority
    receipt["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    receipt["phase_owned_guards"] = value["phase_owned_guards"]
    receipt["setup_ownership"] = value["setup_ownership"]
    receipt["transitive_output_owner_rebind"] = value[
        "transitive_output_owner_rebind"]
    receipt["card_owned_inventory_registration"] = value[
        "card_owned_inventory_registration"]
    receipt["next"] = "owner device acceptance of v1.6 items 1 and 2"
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 input fidelity phase guard: CARD PASS card=1/1 "
          "device-path=OPEN")


def child(action: str) -> None:
    global ACTIVE_PHASE
    ACTIVE_PHASE = {"_dry": "produce", "_produce": "produce",
                    "_scope": "scope", "_accept": "accept"}.get(
                        action, ACTIVE_PHASE)
    configure_module()
    PREV.child(action)


def record_red(error: Exception) -> None:
    configure_module(); PREV.record_red(error)
    if not FINAL_RED.exists():
        return
    value = load(FINAL_RED)
    value["format"] = FORMAT + "-final-red"
    value["status"] = "FINAL RED: INPUT-FIDELITY PHASE GUARD RETURNS TO REVIEW"
    value["phase_guard_authority"] = authorization()
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["retry_authorized"] = False
    value["review_disposition_required"] = True
    FINAL_RED.write_bytes(canonical(value))


def check() -> None:
    if RECEIPT.exists(): print("v1.6 input fidelity phase guard: CHECK PASS")
    elif FINAL_RED.exists(): print("v1.6 input fidelity phase guard: CHECK FINAL RED")
    elif (PREFLIGHT / "preflight.json").exists():
        print("v1.6 input fidelity phase guard: CHECK ARMED")
    else: print("v1.6 input fidelity phase guard: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
        "_dry", "_produce", "_scope", "_accept", "_r1_arm", "_owner_graph"))
    action = parser.parse_args().action
    if action == "preflight": preflight()
    elif action == "card": card()
    elif action == "check": check()
    elif action == "_owner_graph":
        configure_module(); print(json.dumps(PREV.PREV.graph_gate(), sort_keys=True))
    else: child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try: record_red(error)
            except Exception as receipt_error:
                print(f"phase-guard Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 input fidelity phase guard: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
