#!/usr/bin/env python3
"""Close the queue-owner caller-identity Red over its frozen final pair."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path: sys.path.insert(0, str(HOST))

import c2_preinstall_island_guard as ISLAND  # noqa: E402
import c2_v160_queue_single_owner_card as OWNER  # noqa: E402
import c2_v160_queue_single_owner_gate as SOURCE_OWNER  # noqa: E402
import c2_v160_queue_owner_cold_relocation as RELOCATION  # noqa: E402

ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
RED = ARCH / "c2.3-v1.6-queue-owner-cold-relocation-card-final-red.json"
RECEIPT = ARCH / "c2.3-v1.6-queue-owner-cold-relocation-resume-receipt.json"
BUILD = ROOT / "build/c2.3/v1.6-queue-owner-cold-relocation-card"
SCOPE = BUILD / "owner-scope-result.json"
ACCEPTANCE = BUILD / "artifact-acceptance.json"
AUTHORIZATION = "851e33ca"
STATUS = "PASS: V1.6 QUEUE-OWNER COLD RELOCATION CLOSED READ-ONLY"


def require(value: bool, message: str) -> None:
    if not value: raise RuntimeError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    full = subprocess.run(["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("linked caller identity", "blanket requirement",
                  "unguarded lisp_poll edge", "read-only qualification resume",
                  "no wplto, no relink, no new card"):
        require(token in text, f"queue-owner resume authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def pair(red: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {name: red["artifacts"][name] for name in ("ELF", "PRG")}
    for row in rows.values():
        require(bind(ROOT / row["path"]) == row,
                f"frozen queue-owner artifact drift: {row['path']}")
    return rows


def derive(red: dict[str, Any]) -> dict[str, Any]:
    before = pair(red)
    elf = ROOT / before["ELF"]["path"]
    scope = load(SCOPE); acceptance = load(ACCEPTANCE)
    require(scope["status"] == "PASS" and acceptance["status"] == "PASS"
        and acceptance["delivered_bytes"]["candidate_elf"] == before["ELF"]
        and acceptance["delivered_bytes"]["completed_resident_prg"] == before["PRG"],
        "frozen queue-owner Scope/Acceptance pair drift")
    source = SOURCE_OWNER.derive(); SOURCE_OWNER.validate(source)
    linked = OWNER.linked_owner_gate(elf)
    relocation = RELOCATION.linked_gate(elf)
    island = ISLAND.static_elf_gate(elf)
    after = pair(red)
    require(before == after, "read-only queue-owner resume changed final pair")
    return {"format": "lisp65-c2-v160-queue-owner-cold-relocation-resume-v1",
        "recorded_on": "2026-08-21", "status": STATUS,
        "authority": authority(), "predecessor_Final_Red": bind(RED),
        "frozen_pair_before": before, "frozen_pair_after": after,
        "scope": {"status": scope["status"], "receipt": bind(SCOPE)},
        "acceptance": {"status": acceptance["status"],
                       "receipt": bind(ACCEPTANCE)},
        "source_single_owner": source,
        "linked_single_owner": linked,
        "cold_relocation": relocation,
        "preinstall_island": {
            "status": island["status"],
            "Island_control_edges": island["Island_control_edges"],
            "guard_machine_branch_count": island["guard_machine_branch_count"],
            "unguarded_or_consuming_data_references":
                island["unguarded_or_consuming_data_references"]},
        "claim_boundary": {
            "closed": "evaluator drain has sole-owner domination; public key-event remains a distinct legitimate consumer",
            "excluded": "user key-event calls while Comfort capture is armed; registered for v1.7",
            "WPLTO_runs": 0, "product_links": 0, "cards_consumed": 0,
            "media_builds": 0, "device_contacts": 0}}


def validate(value: dict[str, Any]) -> None:
    linked = value["linked_single_owner"]
    require(value["status"] == STATUS
        and value["frozen_pair_before"] == value["frozen_pair_after"]
        and linked["queue_poll_calls"] == 2
        and linked["dominated_calls"] == 1
        and [row["owner"] for row in linked["consumers"]] ==
            ["vm_run_inner", "lisp_input_event"]
        and linked["mutations"] == {"blanket_requirement": "rejected",
                                    "unguarded_evaluator_edge": "rejected"}
        and value["cold_relocation"]["ordinary"]["free_bytes"] == 6
        and value["cold_relocation"]["far"]["free_bytes"] == 15
        and value["claim_boundary"]["WPLTO_runs"] == 0
        and value["claim_boundary"]["product_links"] == 0
        and value["claim_boundary"]["cards_consumed"] == 0,
        "queue-owner read-only resume receipt drift")


def run() -> None:
    require(not RECEIPT.exists(), "queue-owner qualification resume is one-shot")
    red = load(RED)
    require(red["status"] == "FINAL RED: V1.6 QUEUE-OWNER LINKED GUARD STOPS"
        and red["error"]["message"] ==
            "final ELF queue call lacks armed-state/matrix domination"
        and red["attempt_accounting"]["cards_consumed"] == 1,
        "queue-owner resume predecessor Red drift")
    value = derive(red); validate(value)
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 queue-owner cold relocation: RESUME PASS "
          "callers=2 evaluator-guarded=1 public=1 WPLTO=0 link=0 card=0")


def check() -> None:
    value = load(RECEIPT); validate(value)
    for row in value["frozen_pair_after"].values():
        require(bind(ROOT / row["path"]) == row,
                "queue-owner resume final artifact drift")
    print("v1.6 queue-owner cold relocation: CHECK PASS final-world=CLOSED")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    if action == "resume": run()
    elif action == "check": check()
    else: raise SystemExit("usage: ... resume|check")
