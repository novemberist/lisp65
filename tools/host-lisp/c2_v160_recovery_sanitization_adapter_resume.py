#!/usr/bin/env python3
"""Close the recovery-sanitization adapter Reds over the frozen final pair."""

from __future__ import annotations

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

import c2_v160_active_frame_liveness as ACTIVE  # noqa: E402
import c2_v160_active_frame_liveness_card as ACTIVE_CARD  # noqa: E402
import c2_v160_execution_boundary_backstop as BOUNDARY  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.6.0-freight-work-plan.md"
PARTIAL = ARCH / (
    "c2.3-v1.6-recovery-sanitization-library-replacement-card-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v1.6-recovery-sanitization-library-replacement-card-final-red.json")
ATTRIBUTION = ARCH / (
    "c2.3-v1.6-recovery-sanitization-final-adapter-attribution.json")
ALIAS_ATTRIBUTION = ARCH / (
    "c2.3-v1.6-execution-boundary-alias-lto-attribution.json")
BUILD = ROOT / "build/c2.3/v1.6-recovery-sanitization-library-replacement-card"
SCOPE = BUILD / "owner-scope-result.json"
ACCEPTANCE = BUILD / "artifact-acceptance.json"
RECEIPT = ARCH / (
    "c2.3-v1.6-recovery-sanitization-adapter-qualification-resume.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "0a897e80"
STATUS = "PASS: V1.6 RECOVERY SANITIZATION CLOSED READ-ONLY"


class ResumeError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ResumeError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{name}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace("*", "").split())
    for token in ("receipt adapter converts from the pre-raw world pin",
                  "candidate derivation",
                  "alias checker learns the difference between symbol size and allocation",
                  "read-only qualification resume", "no wplto, no link, no card"):
        require(token in text, f"adapter-resume authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def frozen_pair(partial: dict[str, Any]) -> dict[str, dict[str, Any]]:
    expected = {name: partial["artifacts_after"][name]
                for name in ("ELF", "PRG")}
    observed = {name: bind(ROOT / row["path"])
                for name, row in expected.items()}
    require(observed == expected, "recovery-sanitization frozen pair drift")
    return observed


def validate_execution(value: dict[str, int]) -> None:
    require(value == {"qualification_resumes": 1, "WPLTO_runs": 0,
        "product_links": 0, "cards_consumed": 0, "media_builds": 0,
        "device_contacts": 0},
        "recovery-sanitization resume attempted product work")


def execution_mutations(value: dict[str, int]) -> list[str]:
    rejected: list[str] = []
    for name in ("WPLTO_runs", "product_links", "cards_consumed"):
        trial = dict(value); trial[name] = 1
        try:
            validate_execution(trial)
        except ResumeError:
            rejected.append(name)
    require(rejected == ["WPLTO_runs", "product_links", "cards_consumed"],
            "read-only resume rebuild mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    partial = load(PARTIAL); red = load(FINAL_RED); attribution = load(ATTRIBUTION)
    alias_attribution = load(ALIAS_ATTRIBUTION)
    require(partial["status"] ==
                "PASS: V1.6 RECOVERY SANITIZATION SEMANTIC FINAL WORLD GREEN"
            and red["error"] == {"message": "active-frame final receipt drift",
                                 "type": "CardError"}
            and attribution["status"] ==
                "ATTRIBUTED: TWO STORED-WORLD ADAPTERS AFTER SANITIZED LINK"
            and alias_attribution["alias_result"]["aliases_are_zero_byte"] is True,
            "recovery-sanitization adapter predecessor drift")
    before = frozen_pair(partial)
    elf = ROOT / before["ELF"]["path"]

    active_gate = ACTIVE.final_gate(elf)
    counter_adapter = ACTIVE_CARD.validate_counter_receipt_adapter(active_gate)
    counter_mutations = ACTIVE_CARD.counter_receipt_adapter_mutations(active_gate)
    components = active_gate["enforcement"]["component_membership"]
    ACTIVE.validate_component_membership(components, full_section=False)

    boundary_gate = BOUNDARY.final_gate(elf)
    boundary_mutations = BOUNDARY.final_mutations(boundary_gate)
    aliases = boundary_gate["zero_byte_aliases"]
    owner_addresses = {row["owner_address"] for row in aliases.values()}
    require(len(owner_addresses) == len(aliases)
            and all(row["same_address"] is True
                    and row["additional_allocated_bytes"] == 0
                    and row["additional_allocated_addresses"] == []
                    and row["alias_symbol_bytes"] == row["owner_symbol_bytes"]
                    for row in aliases.values())
            and "alias-allocated" in boundary_mutations,
            "candidate-derived alias allocation adapter drift")

    library = partial["candidate_v16core"]
    ACTIVE_CARD.validate_empty_phase_claim(library["empty_phase_semantic_claim"])
    require(library["encoded_bytes"] == 250
            and library["mutations_rejected"] == [
                "restore-stored-248-size-pin", "unfixed-form-accepted",
                "emitted-object-not-consumed"]
            and components["derived_component_bytes"] == 84
            and boundary_gate["ordinary_free_bytes"] == 18
            and boundary_gate["mapped_far_service"] == {
                "bytes": 1488, "capacity_bytes": 1499, "free_bytes": 11}
            and boundary_gate["protected_BSS"]["bytes"] == 1585
            and boundary_gate["protected_BSS"]["validation_margin_bytes"] == 5,
            "recovery-sanitization final substance drift")

    scope = load(SCOPE); acceptance = load(ACCEPTANCE)
    delivered = acceptance["delivered_bytes"]
    require(scope["status"] == "PASS" and acceptance["status"] == "PASS"
            and delivered["candidate_elf"] == before["ELF"]
            and delivered["completed_resident_prg"] == before["PRG"],
            "frozen Scope/Acceptance identity drift")

    execution = {"qualification_resumes": 1, "WPLTO_runs": 0,
        "product_links": 0, "cards_consumed": 0, "media_builds": 0,
        "device_contacts": 0}
    validate_execution(execution)
    after = frozen_pair(partial)
    require(before == after, "read-only qualification resume changed frozen pair")
    return {
        "format": "lisp65-c2-v160-recovery-sanitization-adapter-resume-v1",
        "recorded_on": "2026-08-24", "status": STATUS,
        "authority": authority(), "driver": bind(DRIVER),
        "predecessor_Final_Red": bind(FINAL_RED),
        "adapter_attribution": bind(ATTRIBUTION),
        "partial_product_receipt": bind(PARTIAL),
        "sealed_alias_allocation_proof": bind(ALIAS_ATTRIBUTION),
        "frozen_pair_before": before, "frozen_pair_after": after,
        "receipt_adapter": {**counter_adapter,
            "mutations_rejected": counter_mutations},
        "alias_allocation_adapter": {
            "source": "unique C-owner addresses in final ELF",
            "aliases": aliases,
            "owner_address_count": len(owner_addresses),
            "additional_allocated_bytes": 0,
            "distinct-address_mutation_rejected": True},
        "active_frame_final_gate": active_gate,
        "execution_boundary_final_gate": boundary_gate,
        "execution_boundary_mutations_rejected": boundary_mutations,
        "candidate_v16core": library,
        "scope": {"status": scope["status"], "receipt": bind(SCOPE)},
        "acceptance": {"status": acceptance["status"],
            "receipt": bind(ACCEPTANCE), "delivered_bytes": delivered},
        "execution_witness": execution,
        "rebuild_mutations_rejected": execution_mutations(execution),
        "recovery_sanitization_closed": True,
        "media_authorized": False, "device_contacts": 0,
        "next": "artifact-only media, seam confirmation, witness removal, acceptance"}


def validate(value: dict[str, Any]) -> None:
    require(value["status"] == STATUS
            and value["recovery_sanitization_closed"] is True
            and value["frozen_pair_before"] == value["frozen_pair_after"]
            and value["receipt_adapter"]["ring_usable_events"] == 107
            and value["receipt_adapter"]["reserve_events"] == 13
            and value["receipt_adapter"]["loss_wall_events"] == 94
            and value["alias_allocation_adapter"][
                "additional_allocated_bytes"] == 0
            and value["scope"]["status"] == "PASS"
            and value["acceptance"]["status"] == "PASS",
            "recovery-sanitization qualification resume receipt drift")
    validate_execution(value["execution_witness"])


def resume() -> None:
    require(not RECEIPT.exists(), "recovery-sanitization resume is one-shot")
    value = derive(); validate(value)
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 recovery sanitization: RESUME PASS ring=107 reserve=13 "
          "aliases=4 allocation=0 scope=PASS acceptance=PASS "
          "WPLTO=0 link=0 card=0")


def check() -> None:
    value = load(RECEIPT); validate(value)
    for row in value["frozen_pair_after"].values():
        require(bind(ROOT / row["path"]) == row,
                "recovery-sanitization final artifact drift")
    print("v1.6 recovery sanitization: CHECK PASS final-world=CLOSED")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    if action == "resume":
        resume()
    elif action == "check":
        check()
    else:
        raise SystemExit("usage: ... resume|check")
