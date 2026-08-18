#!/usr/bin/env python3
"""Artifact-only Scope/Acceptance replay for the frozen phase-9 ABI link."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v21_dependent_vma_replacement_card as DEP  # noqa: E402
import c2_v21_phase9_abi_fix_replacement_card as CARD  # noqa: E402
import c2_v21_phase9_freight_boundary_golden as GOLD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
FINAL_RED = CARD.FINAL_RED
BUILD = CARD.BUILD
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
REPLAY = BUILD / "freight-boundary-artifact-replay"
PREFLIGHT = REPLAY / "preflight.json"
SCOPE_RESULT = REPLAY / "owner-scope-result.json"
ACCEPTANCE_RESULT = REPLAY / "artifact-acceptance.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-phase9-abi-fix-artifact-replay-receipt.json")
REPLAY_FINAL_RED = ARCH / (
    "c2.3-v2.1-phase9-abi-fix-artifact-replay-final-red.json")
DRIVER = Path(__file__).resolve()

AUTHORIZATION = "b1dd0379"
RECORDED_ON = "2026-08-16"
FORMAT = "lisp65-c2.3-v2.1-phase9-ABI-freight-boundary-artifact-replay-v1"


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


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


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    raw = subprocess.run(
        ["git", "show", f"{full}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    authority = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{authority['commit']}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode()
    text = " ".join(raw.lower().split())
    for token in ("one-time golden review",
                  "artifact-only replay of the frozen green artifacts",
                  "no new wplto", "green proceeds to completion"):
        require(token in text, f"artifact-replay authority absent: {token}")
    return authority


def final_red() -> dict[str, Any]:
    value = load(FINAL_RED)
    require(value.get("status") == "FINAL RED: phase-9 replacement returns to owner"
            and value.get("retry_authorized") is False
            and value.get("attempt_accounting", {}).get("WPLTO_runs") == 1
            and value.get("attempt_accounting", {}).get("product_link_attempts") == 1,
            "phase-9 Final Red authority drift")
    return value


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    expected = final_red()["artifacts"]
    current = {name: bind(ROOT / row["path"]) for name, row in expected.items()}
    require(current == expected, "frozen phase-9 artifact SHA drift")
    return current


def install_freight_acceptance() -> None:
    # The inherited v4 wrapper adds only cardinality assertions around the
    # actual map-tuple acceptance owner.  Replace that wrapper in this fresh
    # replay process while leaving the complete lower acceptance chain intact.
    DEP.GOLD = GOLD

    def freight_acceptance_child() -> int:
        # The outer candidate configure has already installed the projected
        # phase-9 contracts.  Re-running the inherited configure here would
        # substitute predecessor contracts over those candidate bindings.
        DEP.ACCEPTANCE_OWNER.INV = GOLD
        result = DEP.BASE.acceptance_child()
        value = load(DEP.ACCEPTANCE_RESULT)
        comparison = value.get("VMA_golden", {})
        require(
            comparison.get("comparison")
                == "dependent-address-plus-freight-boundaries-exact"
            and comparison.get("dependent_fixed_vmas") == 101
            and comparison.get("dependent_free_derived_vmas") == 2
            and comparison.get("fixed_boundary_symbols") == 25
            and comparison.get("freight_derived_boundary_symbols") == 3
            and comparison.get("mapped_far_service_capacity", {}).get(
                "candidate_headroom_bytes") == 413,
            "acceptance did not consume reviewed freight-boundary Golden")
        value["freight_boundary_authority"] = bind(GOLD.RECEIPT)
        DEP.ACCEPTANCE_RESULT.write_bytes(canonical(value))
        return result

    DEP.acceptance_child = freight_acceptance_child


def configure() -> None:
    install_freight_acceptance()
    CARD.SCOPE_RESULT = SCOPE_RESULT
    CARD.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    CARD.configure()
    DEP.GOLD = GOLD
    DEP.ACCEPTANCE_OWNER.INV = GOLD


def linked_product() -> dict[str, Any]:
    configure()
    value = CARD.linked_product()
    require(
        value["mapped_far_service"]["bytes"] == 1086
        and value["relocation_section"]["bytes"] == 3972
        and value["C_reachable_transitive_preservation"][
            "unpreserved_callee_saved_writers"] == []
        and value["contractual_service_exits"]["inner_exits"] == 8,
        "frozen phase-9 linked product drift")
    return value


def preflight_value() -> dict[str, Any]:
    before = frozen_artifacts()
    golden = GOLD.compare_elf(ELF)
    require(golden["fixed_boundary_symbols"] == 25
            and golden["freight_derived_boundary_symbols"] == 3
            and golden["mapped_far_service_capacity"][
                "candidate_headroom_bytes"] == 413,
            "artifact replay Golden preflight red")
    producer = load(CARD.PRODUCER_RESULT)
    require(producer.get("status") == "PASS"
            and producer["v21_linked_transport"]["reader"]["address"] == "0x2277"
            and producer["v21_text_recovery"]["ownership"]["violations"] == [],
            "frozen producer result is not green")
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "PASS: frozen phase-9 artifacts armed for acceptance replay",
        "authority": {"owner": authorization(), "Final_Red": bind(FINAL_RED),
            "dependency_attribution": bind(GOLD.ATTR.RECEIPT),
            "golden_review": bind(GOLD.RECEIPT), "driver": bind(DRIVER)},
        "frozen_artifacts": before,
        "golden": golden,
        "producer": bind(CARD.PRODUCER_RESULT),
        "execution_lock": {"artifact_replays_authorized": 1,
            "artifact_replays_run": 0, "WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Acceptance replay only; frozen product bytes are read-only.",
    }


def validate_preflight(value: dict[str, Any], expected: dict[str, Any]) -> None:
    require(value == expected, "phase-9 artifact replay preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-wplto": lambda x: x["execution_lock"].update(WPLTO_runs=1),
        "authorize-link": lambda x: x["execution_lock"].update(product_links=1),
        "consume-card": lambda x: x["execution_lock"].update(cards_consumed=1),
        "dim-frozen-set": lambda x: x["frozen_artifacts"].pop("map"),
        "restore-fixed-service-end": lambda x: x["golden"].update(
            fixed_boundary_symbols=27),
        "dim-capacity-headroom": lambda x: x["golden"][
            "mapped_far_service_capacity"].update(candidate_headroom_bytes=0),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_preflight(trial, value)
        except ReplayError:
            rejected.append(name)
    require(rejected == list(cases), "artifact replay preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not REPLAY.exists() and not RECEIPT.exists(),
            "phase-9 artifact replay is one-shot")
    value = preflight_value(); validate_preflight(value, value)
    value["mutations_rejected"] = preflight_mutations(value)
    REPLAY.mkdir(parents=True)
    PREFLIGHT.write_bytes(canonical(value))
    print("2.1 phase-9 artifact replay: PREFLIGHT PASS frozen=exact replay=0/1")


def rebind_preflight() -> None:
    """Loudly rebind only this driver's identity after the adapter repair."""
    persisted = load(PREFLIGHT)
    persisted_rejected = persisted.pop("mutations_rejected", None)
    expected = preflight_value()
    prior_driver = persisted["authority"]["driver"]
    comparison = deepcopy(expected)
    comparison["authority"]["driver"] = prior_driver
    require(persisted == comparison,
            "artifact replay preflight changed beyond the driver repair")
    require(persisted_rejected == preflight_mutations(comparison),
            "pre-rebind mutation receipt drift")
    expected["authority"]["driver_pre_rebind"] = prior_driver
    # The additive lineage field is itself part of the rebound authority.
    rebound = deepcopy(expected)
    rebound.pop("authority")
    current_without_authority = deepcopy(preflight_value())
    current_without_authority.pop("authority")
    require(rebound == current_without_authority,
            "artifact replay rebind changed non-authority content")
    expected["mutations_rejected"] = preflight_mutations(preflight_value())
    PREFLIGHT.write_bytes(canonical(expected))
    print("2.1 phase-9 artifact replay: PREFLIGHT REBIND PASS driver-only")


def scope_child() -> int:
    configure()
    return CARD.scope_child()


def acceptance_child() -> int:
    configure()
    return CARD.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh phase-9 artifact replay {action} red:\n{result.stdout}")


def replay() -> None:
    persisted = load(PREFLIGHT)
    rejected = persisted.pop("mutations_rejected", None)
    lineage = persisted["authority"].pop("driver_pre_rebind", None)
    expected = preflight_value(); validate_preflight(persisted, expected)
    require(isinstance(lineage, dict) and lineage.get("sha256"),
            "artifact replay driver-rebind lineage absent")
    require(rejected == preflight_mutations(expected),
            "artifact replay preflight mutation receipt drift")
    require(not ACCEPTANCE_RESULT.exists() and not RECEIPT.exists(),
            "artifact replay acceptance output already exists")
    before = frozen_artifacts()
    if not SCOPE_RESULT.exists():
        run_child("_scope")
    else:
        require(load(SCOPE_RESULT).get("status") == "PASS",
                "persisted artifact replay Scope is not green")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "artifact replay changed frozen product artifacts")
    scope = load(SCOPE_RESULT); acceptance = load(ACCEPTANCE_RESULT)
    comparison = acceptance.get("VMA_golden", {})
    require(
        len({os.getpid(), scope.get("pid"), acceptance.get("pid")}) == 3
        and scope.get("status") == "PASS"
        and acceptance.get("status") == "PASS"
        and comparison.get("fixed_boundary_symbols") == 25
        and comparison.get("freight_derived_boundary_symbols") == 3
        and comparison.get("mapped_far_service_capacity", {}).get(
            "candidate_headroom_bytes") == 413,
        "artifact-only Scope/Acceptance replay red")
    receipt = {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "PASS: frozen phase-9 Scope Acceptance artifact replay",
        "authority": {"owner": authorization(), "Final_Red": bind(FINAL_RED),
            "preflight": bind(PREFLIGHT), "golden": bind(GOLD.GOLDEN),
            "golden_review": bind(GOLD.RECEIPT), "driver": bind(DRIVER)},
        "execution_accounting": {"artifact_replays_authorized": 1,
            "artifact_replays_run": 1, "WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "frozen_artifacts_before": before, "frozen_artifacts_after": after,
        "linked_product": linked_product(),
        "scope": scope, "acceptance": acceptance,
        "process_isolation": {"parent": os.getpid(),
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": True},
        "mutations_rejected": rejected,
        "next": "Completion, same-world media closure, owner-observed D1",
        "claim_limit": "Frozen Link accepted; Completion/media/device have not run.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 phase-9 artifact replay: PASS WPLTO=0 link=0 capacity=1086/1499")


def record_final_red() -> None:
    require(not ACCEPTANCE_RESULT.exists() and not RECEIPT.exists()
            and not REPLAY_FINAL_RED.exists(),
            "artifact replay Final Red lifecycle drift")
    before = frozen_artifacts()
    comparison = GOLD.compare_elf(ELF)
    scope = load(SCOPE_RESULT)
    require(scope.get("status") == "PASS"
            and comparison["fixed_boundary_symbols"] == 25
            and comparison["freight_derived_boundary_symbols"] == 3,
            "artifact replay did not pass Scope and freight Golden")
    # Bind every conjunct of the inherited tuple gate.  The only false one is
    # its historical freight-size pin; tuple bytes and decoded MAP semantics
    # remain exact.
    from elf_truth import ElfTruth
    import c2_v20_map_tuple_fix as MAP
    truth = ElfTruth.read(ELF, llvm_readobj=CARD.READOBJ,
                          include_section_data=True)
    enter = truth.symbol("c2_mapped_far_enter")
    enter_section = truth.section(enter.section)
    raw = truth.section_bytes(enter.section)
    body = raw[enter.value - enter_section.address:
               enter.value - enter_section.address + enter.bytes]
    expected_body = bytes.fromhex(
        "48da5aa940a282a000a3805ceaa3007afa6860")
    service = truth.symbol("c2_mapped_far_vm_code_load_converged")
    far = truth.section(GOLD.SECTION)
    far_raw = truth.section_bytes(far.name)
    decoded = MAP.decode_low(0x40, 0x82)
    conjuncts = {
        "trampoline_body": body == expected_body,
        "trampoline_bytes_19": enter.bytes == 19,
        "service_entry_0x79dc": service.value == 0x79DC,
        "service_entry_maps_to_0x2b9dc":
            MAP.map_low(service.value, decoded) == 0x2B9DC,
        "ordinary_0x3185_unmapped": MAP.map_low(0x3185, decoded) == 0x3185,
        "far_start_0x78b2": far.address == 0x78B2,
        "far_historical_bytes_874": far.bytes == 874,
        "first_descriptor_store": far_raw[0x32:0x37]
            == bytes.fromhex("a9048d00c0"),
    }
    require([name for name, passed in conjuncts.items() if not passed]
            == ["far_historical_bytes_874"] and far.bytes == 1086,
            "artifact replay Final Red attribution is not single-pin exact")
    value = {
        "format": FORMAT + "-final-red",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: phase-9 artifact-only replay returns to owner",
        "error": {"type": "historical-freight-pin",
            "message": (
                "The inherited MAP-tuple gate requires far.bytes == 874; "
                "the authorized ABI-preserving candidate emits 1086 bytes.")},
        "attribution": {"gate": "linked corrected MAP tuple or entry model",
            "conjuncts": conjuncts, "passed_conjuncts": 7,
            "failed_conjuncts": 1, "candidate_far_bytes": 1086,
            "historical_pinned_bytes": 874,
            "independent_capacity_bytes": 1499,
            "candidate_headroom_bytes": 413,
            "classification": "verifier freight pin; no tuple-semantic drift"},
        "attempt_accounting": {"artifact_replays_authorized": 1,
            "artifact_replays_consumed": 1, "WPLTO_runs": 0,
            "product_links": 0, "cards_consumed": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "passed_before_stop": {"owner_scope": scope,
            "freight_boundary_golden": comparison},
        "frozen_artifacts_before": before, "frozen_artifacts_after": before,
        "authority": {"owner": authorization(), "card_Final_Red": bind(FINAL_RED),
            "dependency_attribution": bind(GOLD.ATTR.RECEIPT),
            "golden_review": bind(GOLD.RECEIPT),
            "artifact_replay_preflight": bind(PREFLIGHT), "driver": bind(DRIVER)},
        "recommended_disposition": (
            "Make the tuple gate derive the far-service size from the emitted "
            "candidate and validate it against the fixed 1499-byte arena; "
            "then resume Acceptance only against the same frozen SHAs."),
        "retry_authorized": False,
        "owner_disposition_required": True,
        "claim_limit": (
            "The new Golden and Scope passed. Acceptance stopped at one "
            "historical verifier pin; Completion, media and device did not run."),
    }
    REPLAY_FINAL_RED.write_bytes(canonical(value))
    print("2.1 phase-9 artifact replay: FINAL RED tuple=7/8 pin=874 candidate=1086")


def check() -> None:
    if REPLAY_FINAL_RED.exists():
        value = load(REPLAY_FINAL_RED)
        require(value.get("status")
                == "FINAL RED: phase-9 artifact-only replay returns to owner"
                and value.get("retry_authorized") is False
                and value["attribution"]["failed_conjuncts"] == 1
                and value["frozen_artifacts_after"] == frozen_artifacts(),
                "phase-9 artifact replay Final Red drift")
        print("2.1 phase-9 artifact replay: CHECK FINAL RED pin=874")
        return
    value = load(RECEIPT)
    require(value.get("status")
            == "PASS: frozen phase-9 Scope Acceptance artifact replay"
            and value["execution_accounting"]["WPLTO_runs"] == 0
            and value["frozen_artifacts_before"] == frozen_artifacts()
            and value["frozen_artifacts_after"] == value["frozen_artifacts_before"]
            and value["process_isolation"]["all_distinct"] is True,
            "phase-9 artifact replay receipt drift")
    print("2.1 phase-9 artifact replay: CHECK PASS WPLTO=0 link=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "rebind-preflight", "replay", "record-final-red",
        "check", "_scope", "_accept"))
    action = parser.parse_args().action
    {"preflight": preflight, "rebind-preflight": rebind_preflight,
     "replay": replay, "check": check,
     "record-final-red": record_final_red,
     "_scope": scope_child, "_accept": acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
