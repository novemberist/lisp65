#!/usr/bin/env python3
"""Run the setup-owned v1.6 input-fidelity replacement card."""

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

import c2_v160_input_fidelity_graph_rebind_replacement_card as PREV  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
BUILD = ROOT / "build/c2.3/v1.6-input-fidelity-setup-owner-card"
PREFLIGHT = ROOT / "build/c2.3/v1.6-input-fidelity-setup-owner-preflight"
RECEIPT = ARCH / "c2.3-v1.6-input-fidelity-setup-owner-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v1.6-input-fidelity-setup-owner-card-final-red.json"
PREDECESSOR_RED = ARCH / (
    "c2.3-v1.6-input-fidelity-graph-rebind-card-final-red.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "67b72bb0"
FORMAT = "lisp65-c2-v160-input-fidelity-setup-owner-card-v1"
STATUS = "PASS: INPUT-FIDELITY SETUP-OWNER REPLACEMENT ARMED 0/1"
FINAL_STATUS = "PASS: V1.6 INPUT-FIDELITY SETUP-OWNER REPLACEMENT GREEN"
LINK = 118


class SetupOwnerError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SetupOwnerError(message)


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
                  "setup() creates nothing under any producer-owned root",
                  "producer-owned root that exists before invocation",
                  "setup that writes outside its own scope", "exceptionless"):
        require(token in text, f"setup-owner authority token absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR_RED)
    require(value["status"] ==
                "FINAL RED: INPUT-FIDELITY GRAPH REBIND RETURNS TO OWNER"
            and value["retry_authorized"] is False
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["attempt_accounting"]["WPLTO_runs"] == 0
            and value["attempt_accounting"]["product_link_attempts"] == 0
            and value["attribution"]["classification"] ==
                "pre-producer-static-plane-materialization-precreated-exclusive-build-root"
            and value["attribution"]["product_freight_reached"] is False,
            "setup-owner predecessor drift")
    return value


def setup_scope(preflight: Path) -> Path:
    return preflight / "setup-owned"


def setup_owned(build: Path = BUILD, preflight: Path = PREFLIGHT
                ) -> tuple[Any, dict[str, Any]]:
    """Prepare candidate inputs without creating the producer-owned root."""
    core, activation = PREV.PREV.PREV.configure_stack(build, preflight)
    static = core.install_static(setup_scope(preflight))
    core.bind_paths_only(build, preflight)
    core.write_projections()
    require(static["consumer_observed_bytes"] == 46043,
            "candidate static-plane consumer drift")
    require(not build.exists(), "setup created the producer-owned build root")
    receipt = preflight / "setup-ownership-boundary.json"
    declared = [core.PROJECTED_OWNERSHIP, core.PROJECTED_FULL_MAP, receipt]
    validate_setup_writes(producer_root_exists=False,
                          setup_root=preflight, written_paths=declared)
    receipt.write_bytes(canonical({
        "status": "PASS: SETUP YIELDED EXCLUSIVE PRODUCT ROOT",
        "producer_root": build.relative_to(ROOT).as_posix(),
        "producer_root_absent_at_handoff": True,
        "setup_scope": preflight.relative_to(ROOT).as_posix(),
        "declared_writes": [path.relative_to(ROOT).as_posix()
                            for path in declared],
        "static_plane_binding": static,
    }))
    return core, activation


def configure_module() -> None:
    PREV.BUILD = BUILD; PREV.PREFLIGHT = PREFLIGHT
    PREV.RECEIPT = RECEIPT; PREV.FINAL_RED = FINAL_RED
    PREV.DRIVER = DRIVER; PREV.AUTHORIZATION = AUTHORIZATION
    PREV.FORMAT = FORMAT; PREV.STATUS = FINAL_STATUS
    PREV.configure_module()
    reopen = PREV.PREV.PREV
    reopen.setup = setup_owned
    reopen.PREFLIGHT_STATUS_VOCABULARY.add(STATUS)


def _relative(path: Path, root: Path) -> str | None:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def validate_setup_writes(*, producer_root_exists: bool,
                          setup_root: Path,
                          written_paths: list[Path]) -> None:
    require(not producer_root_exists,
            "pre-invocation producer root exists")
    outside = [str(path) for path in written_paths
               if _relative(path, setup_root) is None]
    require(not outside, f"setup writes outside its owned scope: {outside}")


def setup_ownership_gate() -> dict[str, Any]:
    producer = PREFLIGHT / "real-producer-dry-build"
    scope = PREFLIGHT / "real-producer-dry-preflight"
    handoff = load(scope / "setup-ownership-boundary.json")
    written = [ROOT / path for path in handoff["declared_writes"]]
    require(handoff["status"] == "PASS: SETUP YIELDED EXCLUSIVE PRODUCT ROOT"
            and handoff["producer_root"] == producer.relative_to(ROOT).as_posix()
            and handoff["producer_root_absent_at_handoff"] is True
            and handoff["setup_scope"] == scope.relative_to(ROOT).as_posix()
            and handoff["static_plane_binding"]["consumer_observed_bytes"] ==
                46043,
            "real setup ownership handoff drift")
    validate_setup_writes(producer_root_exists=False,
                          setup_root=scope, written_paths=written)
    rejected: list[str] = []
    try:
        validate_setup_writes(producer_root_exists=True,
                              setup_root=scope, written_paths=written)
    except SetupOwnerError:
        rejected.append("pre-invocation-producer-root")
    try:
        validate_setup_writes(producer_root_exists=False,
                              setup_root=scope,
                              written_paths=written + [PREFLIGHT / "foreign-write"])
    except SetupOwnerError:
        rejected.append("setup-write-outside-owned-scope")
    require(rejected == ["pre-invocation-producer-root",
                         "setup-write-outside-owned-scope"],
            "setup ownership mutation survived")
    return {"status": "PASS: SETUP OWNS ONLY PREFLIGHT SCOPE",
        "producer_root": producer.relative_to(ROOT).as_posix(),
        "producer_root_absent_at_handoff": True,
        "setup_scope": scope.relative_to(ROOT).as_posix(),
        "declared_write_count": len(written),
        "mutations_rejected": rejected}


def real_consumer_vocabulary_gate(value: dict[str, Any]) -> dict[str, Any]:
    PREV.PREV.PREV.validate_card_preflight(value)
    mutant = dict(value); mutant["status"] = "PASS: UNKNOWN SETUP OWNER 0/1"
    rejected = False
    try:
        PREV.PREV.PREV.validate_card_preflight(mutant)
    except Exception:
        rejected = True
    require(rejected, "unknown setup-owner status survived real consumer")
    return {"status": "PASS: REAL CARD CONSUMER ACCEPTS SETUP-OWNER STATUS",
        "emitted_status": value["status"],
        "unknown_status_mutation_rejected": True}


def preflight() -> None:
    predecessor(); authority = authorization()
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "setup-owner replacement is one-shot")
    configure_module()
    PREV.preflight()
    path = PREFLIGHT / "preflight.json"
    value = load(path)
    value["format"] = FORMAT + "-preflight"
    value["status"] = STATUS
    value["setup_owner_authority"] = authority
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["setup_ownership"] = setup_ownership_gate()
    value["real_consumer_vocabulary"] = real_consumer_vocabulary_gate(value)
    path.write_bytes(canonical(value))
    print("v1.6 input fidelity setup owner: PREFLIGHT PASS card=0/1 "
          "producer-root=absent mutations=2")


def card() -> None:
    predecessor(); authority = authorization(); configure_module()
    path = PREFLIGHT / "preflight.json"
    value = load(path)
    require(value["status"] == STATUS
            and value["setup_ownership"] == setup_ownership_gate()
            and value["real_consumer_vocabulary"] ==
                real_consumer_vocabulary_gate(value),
            "persisted setup-owner preflight drift")
    PREV.PREV.PREV.card()
    receipt = load(RECEIPT)
    receipt["format"] = FORMAT
    receipt["status"] = FINAL_STATUS
    receipt["setup_owner_authority"] = authority
    receipt["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    receipt["setup_ownership"] = value["setup_ownership"]
    receipt["transitive_output_owner_rebind"] = value[
        "transitive_output_owner_rebind"]
    receipt["card_owned_inventory_registration"] = value[
        "card_owned_inventory_registration"]
    receipt["next"] = "owner device acceptance of v1.6 items 1 and 2"
    RECEIPT.write_bytes(canonical(receipt))
    print("v1.6 input fidelity setup owner: CARD PASS card=1/1 "
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
    value["status"] = "FINAL RED: INPUT-FIDELITY SETUP OWNER RETURNS TO REVIEW"
    value["setup_owner_authority"] = authorization()
    value["predecessor_Final_Red"] = bind(PREDECESSOR_RED)
    value["retry_authorized"] = False
    value["review_disposition_required"] = True
    FINAL_RED.write_bytes(canonical(value))


def check() -> None:
    if RECEIPT.exists():
        print("v1.6 input fidelity setup owner: CHECK PASS")
    elif FINAL_RED.exists():
        print("v1.6 input fidelity setup owner: CHECK FINAL RED")
    elif (PREFLIGHT / "preflight.json").exists():
        print("v1.6 input fidelity setup owner: CHECK ARMED")
    else:
        print("v1.6 input fidelity setup owner: CHECK LOCKED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "card", "check",
        "_dry", "_produce", "_scope", "_accept", "_r1_arm", "_owner_graph"))
    action = parser.parse_args().action
    if action == "preflight":
        preflight()
    elif action == "card":
        card()
    elif action == "check":
        check()
    elif action == "_owner_graph":
        configure_module(); print(json.dumps(PREV.graph_gate(), sort_keys=True))
    else:
        child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_red(error)
            except Exception as receipt_error:
                print(f"setup-owner Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"v1.6 input fidelity setup owner: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
