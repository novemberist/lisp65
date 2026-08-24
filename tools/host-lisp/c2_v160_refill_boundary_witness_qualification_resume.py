#!/usr/bin/env python3
"""Close the witness successor-gate Red over its frozen final pair."""

from __future__ import annotations

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

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v160_refill_boundary_witness as WITNESS  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
RED = ARCH / (
    "c2.3-v1.6-refill-boundary-witness-replacement-card-final-red.json")
ATTRIBUTION = ARCH / (
    "c2.3-v1.6-refill-boundary-witness-successor-gate-attribution.json")
PREFLIGHT = ROOT / (
    "build/c2.3/v1.6-refill-boundary-witness-replacement-preflight/preflight.json")
RECEIPT = ARCH / (
    "c2.3-v1.6-refill-boundary-witness-qualification-resume-receipt.json")
AUTHORIZATION = "dfd230c8"
STATUS = "PASS: V1.6 REFILL WITNESS FINAL WORLD CLOSED READ-ONLY"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path, *, mode: bool = False) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    value: dict[str, Any] = {
        "path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest()}
    if mode:
        value["mode"] = f"{os.stat(path).st_mode & 0o777:04o}"
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    commit = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("linked candidate", "derived caller set", "vm_run_inner",
                  "read-only scope/qualification resume",
                  "no wplto, no relink, no card"):
        require(token in text, f"witness resume authority absent: {token}")
    return {"authority": "git-blob", "commit": commit, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def frozen_pair(attribution: dict[str, Any]) -> dict[str, dict[str, Any]]:
    expected = attribution["frozen_final_pair"]
    rows = {name: bind(ROOT / expected[name]["path"], mode=True)
            for name in ("ELF", "PRG")}
    require(rows == {name: expected[name] for name in ("ELF", "PRG")},
            "frozen witness final pair identity/mode drift")
    return rows


def derive() -> dict[str, Any]:
    red = load(RED)
    attribution = load(ATTRIBUTION)
    require(red["status"] ==
                "FINAL RED: V1.6 REFILL WITNESS REPLACEMENT STOPS"
            and red["attempt_accounting"]["cards_consumed"] == 1
            and attribution["decision"]["replacement_card_consumed"] is True
            and attribution["decision"]["product_fault"] is False,
            "witness qualification predecessor Red drift")
    before = frozen_pair(attribution)
    elf = ROOT / before["ELF"]["path"]

    preflight = load(PREFLIGHT)
    materialized = preflight["feature_materialization"]
    require(materialized["normal"]["witness_profile_present"] is True
            and materialized["normal"]["witness_source_process_present"] is True
            and materialized["normal"]["witness_seed_object_present"] is True
            and materialized["feature_generic"] is True
            and len(materialized["normal"][
                "feature_generic_mutations_rejected"]) == 4,
            "persisted feature-generic materialization proof drift")

    boot = PRODUCT._linked_c2_lite_boot_slot_evidence(elf)
    witness = WITNESS.final_gate(elf)
    witness["mutations_rejected"] = WITNESS.final_mutations(witness)
    require(boot["slots"] == {"installer": 10, "carrier": 11}
            and boot["seam_owner"] ==
                "vm_runtime_overlay_install_island_far"
            and len(boot["seam_calls"]) == 1
            and len(boot["mutations_rejected"]) == 3
            and witness["edges"]["witness_owner_set"] == ["vm_run_inner"]
            and bool(witness["edges"]["witness_callers"])
            and "foreign-witness-caller" in witness["mutations_rejected"]
            and "single-witness-caller-pin" in witness["mutations_rejected"],
            "candidate-derived witness successor qualification red")

    after = frozen_pair(attribution)
    require(before == after, "read-only witness resume changed frozen pair")
    return {
        "format": "lisp65-c2-v160-refill-boundary-witness-resume-v1",
        "recorded_on": "2026-08-22", "status": STATUS,
        "authority": authority(), "predecessor_Final_Red": bind(RED),
        "attribution": bind(ATTRIBUTION),
        "feature_generic_materialization": {
            "status": materialized["status"],
            "compiler_processes": materialized["normal"][
                "compiler_process_count"],
            "active_feature_scopes": len(materialized["normal"][
                "feature_generic_mutations_rejected"]),
            "registry_only_mutation": materialized[
                "registry_only_mutation"]["registry_only_mutation"]},
        "frozen_pair_before": before, "frozen_pair_after": after,
        "boot_successor_identity": boot,
        "refill_boundary_witness": witness,
        "execution": {"scope_qualification_resumes": 1, "WPLTO_runs": 0,
            "product_links": 0, "cards_consumed": 0, "media_builds": 0,
            "device_contacts": 0},
        "claim_boundary": {
            "proven": "witness materialized and qualified in the frozen final ELF",
            "not_authorized": "media construction or device contact",
            "removal_default": True},
        "next": "independent review, then fresh same-world media and one trace-reading contact"}


def validate(value: dict[str, Any]) -> None:
    witness = value["refill_boundary_witness"]
    boot = value["boot_successor_identity"]
    require(value["status"] == STATUS
            and value["frozen_pair_before"] == value["frozen_pair_after"]
            and boot["seam_owner"] ==
                "vm_runtime_overlay_install_island_far"
            and len(boot["seam_calls"]) == 1
            and witness["edges"]["witness_owner_set"] == ["vm_run_inner"]
            and bool(witness["edges"]["witness_callers"])
            and value["execution"]["WPLTO_runs"] == 0
            and value["execution"]["product_links"] == 0
            and value["execution"]["cards_consumed"] == 0,
            "witness qualification resume receipt drift")


def resume() -> None:
    require(not RECEIPT.exists(), "witness qualification resume is one-shot")
    value = derive()
    validate(value)
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 refill witness: RESUME PASS seam-owner=far "
          "trace-callers=7 owner=vm_run_inner WPLTO=0 link=0 card=0")


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    for row in value["frozen_pair_after"].values():
        require(bind(ROOT / row["path"], mode=True) == row,
                "witness resume final artifact drift")
    print("v1.6 refill witness: CHECK PASS final-world=CLOSED")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    if action == "resume":
        resume()
    elif action == "check":
        check()
    else:
        raise SystemExit("usage: ... resume|check")
