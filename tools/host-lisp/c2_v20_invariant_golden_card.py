#!/usr/bin/env python3
"""Run the sole reviewer-unlocked 2.0 invariant-golden product card.

The producer is the already exercised 2.0 producer, configured only onto a
fresh output root.  This successor owns no product or qualification logic.
Its sole acceptance operation is the reviewed invariant-golden comparison,
which exact-compares freight-independent geometry and derives/validates sizes,
LMAs and overlay_end from the candidate that was just linked.
"""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v20_invariant_golden as INV  # noqa: E402
import c2_v20_ownership_recharter as PRODUCER  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
CHARTER = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
REVIEW_COMMIT = "bf195e3202c904810d6986df20bd8df762747fab"
REVIEW_PARENT = "87f4254e4d1ff883911c1a1b9cd5cdb0903c80e0"
BUILD = ROOT / "build/c2.3/v2.0-invariant-golden-card"
PREFLIGHT = ROOT / "build/c2.3/v2.0-invariant-golden-card-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
RECEIPT = EVIDENCE / "c2.3-v2.0-invariant-golden-card-receipt.json"
FINAL_RED = EVIDENCE / "c2.3-v2.0-invariant-golden-card-final-red.json"
DRIVER = Path(__file__).resolve()
RECORDED_ON = "2026-08-12"
FORMAT = "lisp65-c2.3-v20-invariant-golden-card-v1"


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular authority absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def git_binding(commit: str, path: Path) -> dict[str, Any]:
    relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{relative}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    return {
        "git_commit": commit, "path": relative, "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def reviewer_acceptance() -> dict[str, Any]:
    parent = subprocess.run(
        ["git", "rev-parse", f"{REVIEW_COMMIT}^"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    require(parent == REVIEW_PARENT,
            "invariant-golden review does not descend from review package")
    authority = git_binding(REVIEW_COMMIT, CHARTER)
    raw = subprocess.run(
        ["git", "show", f"{REVIEW_COMMIT}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode("utf-8").split())
    require(
        "One-time invariant-golden review" in text
        and "ACCEPTED" in text
        and "two-worlds test" in text
        and "The card unlocks: exactly one" in text
        and "candidate-derived contract validation and nothing else" in text,
        "one-time invariant-golden acceptance is not bound")
    return authority


def review_package() -> dict[str, Any]:
    expected = INV.build_receipt()
    require(INV.canonical(load(INV.RECEIPT)) == INV.canonical(expected),
            "invariant-golden review package drift")
    require(expected["card_lock"] == {
        "review_accepted": False,
        "card_authorized_by_this_receipt": False,
        "wplto_allowed": False,
    }, "pre-review package improperly authorized its own card")
    return expected


PRODUCER_INPUTS = {
    "candidate_profile": PRODUCER.CANDIDATE_PROFILE,
    "candidate_contract": PRODUCER.CANDIDATE_CONTRACT,
    "candidate_header": PRODUCER.CANDIDATE_HEADER,
    "full_map_contract": PRODUCER.PRODUCT.FULL_MAP_OWNERSHIP_CONTRACT,
    "f018b_contract": PRODUCER.SAFE.CONTRACT,
    "f018b_pricing": PRODUCER.SAFE.RECEIPT,
    "v1.5_preflight": PRODUCER.BASE.PRE.RECEIPT,
    "v1.5_freight_closure": PRODUCER.BASE.CLOSURE.RECEIPT,
}


def producer_input_closure(
    *, sealed: bool = False,
) -> dict[str, dict[str, Any]]:
    historical = load(PRODUCER.PREFLIGHT_RECEIPT)["authorities"]
    if sealed:
        frozen = load(PREFLIGHT_RECEIPT).get("producer_inputs")
        require(isinstance(frozen, dict),
                "sealed card producer input closure absent")
        expected: dict[str, dict[str, Any]] = {}
        for name, path in PRODUCER_INPUTS.items():
            row = historical.get(name)
            require(isinstance(row, dict)
                    and row.get("path")
                        == path.resolve().relative_to(ROOT.resolve()).as_posix()
                    and isinstance(row.get("bytes"), int)
                    and row["bytes"] >= 0
                    and isinstance(row.get("sha256"), str)
                    and len(row["sha256"]) == 64,
                    f"sealed producer input binding invalid: {name}")
            expected[name] = row
        require(frozen == expected,
                "sealed card producer input closure drift")
        return expected
    current = {name: bind(path) for name, path in PRODUCER_INPUTS.items()}
    require(all(historical.get(name) == value for name, value in current.items()),
            "reviewed producer input closure changed after the first card")
    return current


def validate_preflight(value: dict[str, Any]) -> None:
    require(
        value.get("format")
            == "lisp65-c2.3-v20-invariant-golden-card-preflight-v1"
        and value.get("status")
            == "PASS: one reviewed invariant-golden card armed"
        and value.get("execution_accounting") == {
            "cards_consumed": 0, "product_compiles": 0,
            "wplto_runs": 0, "device_contacts": 0}
        and value.get("acceptance") == {
            "operation": "INV.compare_elf(candidate_elf)",
            "fixed_authority": bind(INV.GOLDEN),
            "candidate_derived_validation": [
                "section sizes against fixed capacity arenas",
                "numeric LMAs against fixed load order and non-overlap",
                "overlay_end against candidate section VMA plus size",
            ],
            "other_acceptance_operations": 0,
        }
        and value.get("authority", {}).get("reviewer_acceptance")
            == reviewer_acceptance()
        and value["authority"].get("review_package") == bind(INV.RECEIPT)
        and value["authority"].get("producer") == bind(PRODUCER.DRIVER)
        and value["authority"].get("driver") == bind(DRIVER)
        and value.get("producer_inputs") == producer_input_closure()
        and value.get("card_path_gate") == audit_card_path(),
        "invariant-golden card preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "detach-review": lambda x: x["authority"]["reviewer_acceptance"].update(
            sha256="0" * 64),
        "restore-snapshot-golden": lambda x: x["acceptance"].update(
            fixed_authority=bind(PRODUCER.GOLD.GOLDEN)),
        "drop-derived-validation": lambda x: x["acceptance"][
            "candidate_derived_validation"].pop(),
        "add-acceptor": lambda x: x["acceptance"].update(
            other_acceptance_operations=1),
        "change-producer-input": lambda x: x["producer_inputs"][
            "candidate_profile"].update(sha256="0" * 64),
        "claim-card": lambda x: x["execution_accounting"].update(
            cards_consumed=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_preflight(candidate)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases),
            "invariant-golden preflight mutation survived")
    return rejected


FORBIDDEN_ACCEPTORS = {
    "postlink", "guard_result", "check", "linked_gates",
    "replacement_gates", "fresh_current_product_postlink_gate",
    "full_map_layout", "complete_in_fresh_process",
}


def call_name(node: ast.Call) -> str:
    try:
        return ast.unparse(node.func)
    except Exception:
        return ""


def audit_card_path(source: str | None = None) -> dict[str, Any]:
    text = DRIVER.read_text(encoding="utf-8") if source is None else source
    tree = ast.parse(text)
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    require("card" in functions, "invariant-golden card function absent")
    calls = [node for node in ast.walk(functions["card"])
             if isinstance(node, ast.Call)]
    comparison = sum(call_name(node) == "INV.compare_elf" for node in calls)
    production = sum(call_name(node) == "produce_candidate" for node in calls)
    forbidden = [call_name(node) for node in calls
                 if call_name(node).split(".")[-1] in FORBIDDEN_ACCEPTORS]
    require(comparison == 1,
            "card must contain exactly one invariant-golden comparison")
    require(production == 1, "card must invoke the reviewed producer once")
    require(not forbidden,
            f"non-golden acceptance call present in card: {forbidden}")
    return {
        "invariant_golden_comparisons": comparison,
        "producer_invocations": production,
        "other_acceptance_operations": 0,
    }


def card_path_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    anchor = "comparison = INV.compare_elf(artifacts[\"elf\"])"
    require(source.count(anchor) == 1,
            "invariant-golden card comparison anchor drift")
    cases = {
        "remove-invariant-comparison": source.replace(
            anchor, "comparison = {}", 1),
        "double-invariant-comparison": source.replace(
            anchor, anchor + "\n    " + anchor, 1),
        "restore-snapshot-comparison": source.replace(
            anchor,
            "comparison = PRODUCER.GOLD.compare_elf(artifacts[\"elf\"])", 1),
        "add-postlink-acceptor": source.replace(
            anchor, "PRODUCER.SAFE.postlink(artifacts[\"elf\"])\n    " + anchor,
            1),
        "remove-producer": source.replace(
            "\n    artifacts = produce_candidate()\n    comparison =",
            "\n    artifacts = {}\n    comparison =", 1),
    }
    rejected: list[str] = []
    for name, mutant in cases.items():
        try:
            audit_card_path(mutant)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases),
            "invariant-golden card-path mutation survived")
    return rejected


def build_preflight() -> dict[str, Any]:
    review = review_package()
    require(review["two_natures"]["source_world"][
                "invariant_projection_sha256"]
            == review["two_natures"]["v1.5_plus_convergence_world"][
                "invariant_projection_sha256"],
            "reviewed two-worlds invariant projection drift")
    return {
        "format": "lisp65-c2.3-v20-invariant-golden-card-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: one reviewed invariant-golden card armed",
        "execution_accounting": {
            "cards_consumed": 0, "product_compiles": 0,
            "wplto_runs": 0, "device_contacts": 0},
        "acceptance": {
            "operation": "INV.compare_elf(candidate_elf)",
            "fixed_authority": bind(INV.GOLDEN),
            "candidate_derived_validation": [
                "section sizes against fixed capacity arenas",
                "numeric LMAs against fixed load order and non-overlap",
                "overlay_end against candidate section VMA plus size",
            ],
            "other_acceptance_operations": 0,
        },
        "producer_inputs": producer_input_closure(),
        "card_path_gate": audit_card_path(),
        "authority": {
            "reviewer_acceptance": reviewer_acceptance(),
            "review_package": bind(INV.RECEIPT),
            "producer": bind(PRODUCER.DRIVER),
            "driver": bind(DRIVER),
        },
        "terminal_clause": (
            "Exactly one card. Any red returns as final owner disposition; "
            "no retry is implied."),
    }


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "invariant-golden card preflight is one-shot")
    require(card_path_mutations() == [
        "remove-invariant-comparison", "double-invariant-comparison",
        "restore-snapshot-comparison", "add-postlink-acceptor",
        "remove-producer"], "card-path mutation closure drift")
    value = build_preflight()
    validate_preflight(value)
    value["mutations_rejected"] = preflight_mutations(value)
    value["card_path_mutations_rejected"] = card_path_mutations()
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.0 invariant-golden card: PREFLIGHT PASS "
          "review=accepted mutations=11 cards=0 wplto=0 device=0")


def configure_producer() -> None:
    # Only the output and internal First-Red roots change.  The producer
    # module, candidate profile, contract, header and qualification machinery
    # remain the exact inputs bound by producer_input_closure().
    PRODUCER.BUILD = BUILD
    PRODUCER.FINAL_RED = BUILD / "producer-internal-first-red.json"


def produce_candidate() -> dict[str, Any]:
    configure_producer()
    return PRODUCER.produce_candidate()


def card() -> None:
    preflight_value = load(PREFLIGHT_RECEIPT)
    mutations = preflight_value.pop("mutations_rejected", None)
    path_mutations = preflight_value.pop("card_path_mutations_rejected", None)
    validate_preflight(preflight_value)
    require(mutations == preflight_mutations(preflight_value)
            and path_mutations == card_path_mutations(),
            "invariant-golden card preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "invariant-golden product card is one-shot")
    INVOCATION.write_bytes(canonical({
        "format": "lisp65-c2.3-v20-invariant-golden-card-invocation-v1",
        "recorded_on": RECORDED_ON,
        "status": "INVOKED: terminal outcome required",
        "reviewer_acceptance": reviewer_acceptance(),
        "preflight": bind(PREFLIGHT_RECEIPT),
        "driver": bind(DRIVER),
    }))
    artifacts = produce_candidate()
    comparison = INV.compare_elf(artifacts["elf"])
    value = {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "PASS: owned v1.5 plus F018B candidate satisfies invariant golden",
        "attempt_accounting": {
            "cards_authorized": 1, "cards_consumed": 1,
            "wplto_runs": 1, "product_link_attempts": 1,
            "device_contacts": 0,
        },
        "acceptance": {
            **comparison, "operations": 1,
            "other_acceptance_operations": 0,
        },
        "producer": {
            "source_unchanged": bind(PRODUCER.DRIVER),
            "mechanical_completion_only": True,
            "historical_return_nonauthoritative": artifacts["producer_return"],
            "log": bind(artifacts["producer_log"]),
            "resolved_profile": bind(artifacts["resolved_profile"]),
            "target_stdlib_header": artifacts["target_stdlib_header"],
        },
        "artifacts": {
            key: bind(artifacts[key])
            for key in ("elf", "prg", "map", "lto", "linker")},
        "authority": {
            "reviewer_acceptance": reviewer_acceptance(),
            "invariant_golden": bind(INV.GOLDEN),
            "review_package": bind(INV.RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "invocation": bind(INVOCATION),
            "driver": bind(DRIVER),
        },
        "next_gate": (
            "Fresh v1.5 D1-D5 device session, v1.5 release and separate "
            "parity-chain owner decision."),
        "claim_limit": (
            "One host-only product card accepted solely by invariant geometry "
            "plus candidate-derived freight validation; no media, device, "
            "release, publication or parity claim."),
    }
    RECEIPT.write_bytes(canonical(value))
    headroom = {
        row["id"]: row["candidate_headroom_bytes"]
        for row in comparison["capacity_measurements"]}
    print("2.0 invariant-golden card: PASS "
          f"sections={comparison['allocatable_sections']} "
          f"boundaries={comparison['fixed_boundary_symbols']}+1-derived "
          f"margins={headroom['low-resident-and-ordinary-chain']}/"
          f"{headroom['runtime-overlay-slices']}/"
          f"{headroom['owned-bank0-state']} wplto=1 device=0")


def record_final_red(error: BaseException) -> None:
    require(not RECEIPT.exists() and not FINAL_RED.exists(),
            "invariant-golden card terminal result is immutable")
    artifacts: dict[str, dict[str, Any]] = {}
    for name, relative in {
        "seed_lto": "wplto/resident-island-seed.prg.lto.o",
        "candidate_lto": "wplto/lisp65-c2-substitution-linked.prg.lto.o",
        "candidate_elf": "wplto/lisp65-c2-substitution-linked.prg.elf",
        "candidate_prg": "wplto/lisp65-c2-substitution-linked.prg",
        "candidate_map": "wplto/lisp65-c2-substitution-linked.prg.map",
        "linker": "wplto/c2-substitution.ld",
        "resolved_profile": "wplto/resolved-profile.txt",
        "producer_log": "receipts/v20-producer.log",
        "producer_first_red": "producer-internal-first-red.json",
    }.items():
        path = BUILD / relative
        if path.is_file():
            artifacts[name] = bind(path)
    elf = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
    comparison: dict[str, Any] | None = None
    if elf.is_file():
        try:
            comparison = INV.compare_elf(elf)
        except Exception as compare_error:
            comparison = {
                "status": "red", "type": type(compare_error).__name__,
                "message": str(compare_error)}
    value = {
        "format": "lisp65-c2.3-v20-invariant-golden-card-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: invariant-golden card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {
            "cards_authorized": 1, "cards_consumed": 1,
            "wplto_runs": int((BUILD / "wplto").exists()),
            "product_link_attempts": int((BUILD / "wplto").exists()),
            "linked_candidate_elf_emitted": elf.is_file(),
            "device_contacts": 0,
        },
        "retry_authorized": False,
        "final_owner_disposition_required": True,
        "acceptance_observation": comparison,
        "artifacts": artifacts,
        "authority": {
            "reviewer_acceptance": reviewer_acceptance(),
            "invariant_golden": bind(INV.GOLDEN),
            "review_package": bind(INV.RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "invocation": bind(INVOCATION),
            "driver": bind(DRIVER),
        },
        "claim_limit": (
            "The sole invariant-golden card is consumed. No retry, device "
            "session, release or parity claim."),
    }
    FINAL_RED.write_bytes(canonical(value))


def selftest() -> None:
    reviewer_acceptance()
    review_package()
    terminal = RECEIPT if RECEIPT.exists() else FINAL_RED
    if terminal.exists():
        value = load(terminal)
        require(value.get("authority", {}).get("preflight")
                    == bind(PREFLIGHT_RECEIPT),
                "sealed card preflight authority drift")
        producer_input_closure(sealed=True)
    else:
        producer_input_closure()
    gate = audit_card_path()
    mutations = card_path_mutations()
    require(gate == {
        "invariant_golden_comparisons": 1,
        "producer_invocations": 1,
        "other_acceptance_operations": 0,
    } and len(mutations) == 5,
        "invariant-golden card selftest drift")
    print("2.0 invariant-golden card: SELFTEST PASS "
          "review=accepted comparison=one mutations=5")


def check() -> None:
    selftest()
    require(not (RECEIPT.exists() and FINAL_RED.exists()),
            "invariant-golden card has two terminal outcomes")
    if not RECEIPT.exists() and not FINAL_RED.exists():
        print("2.0 invariant-golden card: CHECK ARMED card=unused")
        return
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("final_owner_disposition_required") is True,
                "invariant-golden final-red disposition drift")
        print("2.0 invariant-golden card: CHECK FINAL RED "
              "retry=none owner-disposition=required")
        return
    value = load(RECEIPT)
    require(
        value.get("status")
            == "PASS: owned v1.5 plus F018B candidate satisfies invariant golden"
        and value.get("attempt_accounting", {}).get("cards_consumed") == 1
        and value["acceptance"].get("comparison")
            == "invariants-exact-derived-freight-validated"
        and value["acceptance"].get("operations") == 1
        and value["acceptance"].get("other_acceptance_operations") == 0,
        "green invariant-golden card receipt drift")
    candidate = ROOT / value["artifacts"]["elf"]["path"]
    require(INV.compare_elf(candidate) == {
        key: item for key, item in value["acceptance"].items()
        if key not in {"operations", "other_acceptance_operations"}},
        "persisted invariant-golden candidate comparison drift")
    print("2.0 invariant-golden card: CHECK PASS "
          "comparison=invariants+derived card=consumed device=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "preflight", "card", "check"))
    action = parser.parse_args().action
    if action == "selftest":
        selftest()
    elif action == "preflight":
        preflight()
    elif action == "card":
        card()
    else:
        check()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_final_red(error)
            except Exception as receipt_error:  # never hide the terminal red
                print("2.0 invariant-golden card: receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"2.0 invariant-golden card: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
