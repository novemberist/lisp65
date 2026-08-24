#!/usr/bin/env python3
"""Close the semantic placement-witness Red over its frozen final pair."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v160_active_frame_liveness as ACTIVE  # noqa: E402
import c2_v160_comfort_input_fidelity as FIDELITY  # noqa: E402
import c2_v160_input_drop_counters as COUNTERS  # noqa: E402
import c2_v160_input_service_hybrid as HYBRID  # noqa: E402
import c2_v160_input_service_hybrid_final_world as FINAL  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RED = ARCH / (
    "c2.3-v1.6-bound-origin-fragmentation-second-replacement-card-final-red.json")
RECEIPT = ARCH / (
    "c2.3-v1.6-bound-origin-fragmentation-acceptance-resume-receipt.json")
BUILD = ROOT / "build/c2.3/v1.6-bound-origin-fragmentation-second-replacement-card"
SCOPE = BUILD / "owner-scope-result.json"
ACCEPTANCE = BUILD / "artifact-acceptance.json"


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def pair(red: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {name: red["artifacts"][name] for name in ("ELF", "PRG")}
    for row in rows.values():
        require(bind(ROOT / row["path"]) == row,
                f"frozen fragmentation artifact drift: {row['path']}")
    return rows


def run() -> None:
    require(not RECEIPT.exists(), "fragmentation acceptance resume is one-shot")
    red = load(RED)
    require(red["status"] ==
            "FINAL RED: V1.6 BOUND-ORIGIN POST-LINK PLACEMENT WITNESS STOPS"
        and red["error"]["message"] == "born-derived hybrid placement gate absent"
        and red["classification"]["product_link_green"] is True,
        "fragmentation resume predecessor Red drift")
    before = pair(red)
    elf = ROOT / before["ELF"]["path"]

    scope = load(SCOPE); acceptance = load(ACCEPTANCE)
    require(scope["status"] == "PASS" and acceptance["status"] == "PASS"
        and acceptance["delivered_bytes"]["candidate_elf"] == before["ELF"]
        and acceptance["delivered_bytes"]["completed_resident_prg"] == before["PRG"],
        "frozen Scope/Acceptance pair drift")

    host = HYBRID.derive()
    claims = FINAL.derive(elf)
    placement = FIDELITY.placement_gate(elf)
    liveness = ACTIVE.final_gate(elf)
    counters = COUNTERS.derive(); COUNTERS.validate(counters)
    require(host["status"] == "PASS: ADAPTIVE INPUT HYBRID HOST GREEN"
        and claims["status"] == "PASS: HYBRID CLAIMS PROVED ON FINAL ELF"
        and claims["membership"]["ring_index_values"] == 108
        and claims["membership"]["counter_bytes"] == 4
        and claims["loss"]["linked_dropped"] == 0
        and claims["responsiveness"]["margin_percent"] >= 29.0
        and placement["final_reserve_bytes"] == 57
        and placement["largest_contiguous_hole_bytes"] == 49
        and placement["fragments"][
            ".lisp65_c2_kernal_window.input_capture_main"]["bytes"] == 28
        and placement["fragments"][
            ".lisp65_c2_kernal_window.input_capture_helper"]["bytes"] == 40
        and liveness["input_counters"]["ring_usable_events"] == 107
        and liveness["input_counters"]["reserve_events"] == 13,
        "read-only fragmentation final-world proof red")
    after = pair(red)
    require(before == after, "read-only fragmentation resume changed final pair")

    value = {"format": "lisp65-c2-v160-bound-origin-fragmentation-resume-v1",
        "recorded_on": "2026-08-21",
        "status": "PASS: V1.6 BOUND-ORIGIN FINAL WORLD CLOSED READ-ONLY",
        "predecessor_Final_Red": bind(RED),
        "frozen_pair_before": before, "frozen_pair_after": after,
        "scope": {"status": scope["status"], "receipt": bind(SCOPE)},
        "acceptance": {"status": acceptance["status"],
                       "receipt": bind(ACCEPTANCE)},
        "semantic_placement_witness": {
            "source": "generated linker contract, not diagnostic prose",
            "fixed_floor_bytes": 54, "required_free_bytes": 57,
            "message_literal_is_authority": False},
        "final_world_claims": claims, "placement": placement,
        "active_frame_liveness": liveness,
        "bound_origin_instrument": counters,
        "execution": {"scope_acceptance_resumes": 1, "WPLTO_runs": 0,
            "product_links": 0, "cards_consumed": 0, "media_builds": 0,
            "device_contacts": 0},
        "next": "fresh same-world Completion and media after full-tail green"}
    RECEIPT.write_bytes(canonical(value))
    print("v1.6 bound-origin fragmentation: RESUME PASS "
          "scope=PASS acceptance=PASS WPLTO=0 link=0 card=0")


def check() -> None:
    value = load(RECEIPT)
    require(value["status"] ==
            "PASS: V1.6 BOUND-ORIGIN FINAL WORLD CLOSED READ-ONLY"
        and value["frozen_pair_before"] == value["frozen_pair_after"]
        and value["execution"]["WPLTO_runs"] == 0
        and value["execution"]["product_links"] == 0,
        "fragmentation resume receipt drift")
    for row in value["frozen_pair_after"].values():
        require(bind(ROOT / row["path"]) == row,
                "fragmentation resume final artifact drift")
    print("v1.6 bound-origin fragmentation: CHECK PASS final-world=CLOSED")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    if action == "resume": run()
    elif action == "check": check()
    else: raise SystemExit("usage: ... resume|check")
