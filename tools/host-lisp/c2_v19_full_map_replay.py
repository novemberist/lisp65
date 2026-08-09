#!/usr/bin/env python3
"""SHA-bound, zero-WPLTO rehearsal for the sole v1.9 ownership card."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))

import c2_asm_leaf_abi_gate as ABI  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
VOCABULARY = EVIDENCE / "c2.3-v1.9-acceptance-vocabulary-receipt.json"
PHASE_C = EVIDENCE / "c2.3-v1.8-full-map-phase-c-gate-receipt.json"
RECEIPT = EVIDENCE / "c2.3-v1.9-full-map-replay-closure-receipt.json"
PLAN = ROOT / "docs/planning/1.9-full-map-recharter-work-plan.md"
DRIVER = ROOT / "tools/host-lisp/c2_v19_full_map_recharter_wplto.py"
TERMINAL = ROOT / "build/post-promotion/v18/full-map-ownership-repair-wplto/wplto"
SEED_ELF = TERMINAL / "resident-island-seed.prg.elf"
FINAL_ELF = TERMINAL / "lisp65-c2-substitution-linked.prg.elf"
SEED_INVENTORY = TERMINAL / "final-section-inventory-resident-island-seed.prg.json"
FINAL_INVENTORY = TERMINAL / (
    "final-section-inventory-lisp65-c2-substitution-linked.prg.json")
RECORDED_ON = "2026-08-06"
HISTORICAL_GATE_COMMIT = "361c95df369f332224a5d8ac71a6b6de5465370a"


class ReplayError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplayError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular replay authority absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            f"regular JSON replay authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def immutable_binding(commit: str, binding: dict[str, Any]) -> None:
    raw = subprocess.run(
        ["git", "show", f"{commit}:{binding['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    require(len(raw) == binding["bytes"] and
            hashlib.sha256(raw).hexdigest() == binding["sha256"],
            "historical v1.9 replay-gate binding drift")


def append_only_plan(binding: dict[str, Any]) -> None:
    raw = PLAN.read_bytes()
    prefix = raw[:binding["bytes"]]
    require(len(prefix) == binding["bytes"] and
            hashlib.sha256(prefix).hexdigest() == binding["sha256"],
            "v1.9 plan is not an exact append-only dated rebind")


def historical_rebind(
    historical: dict[str, Any], current: dict[str, Any],
) -> dict[str, Any]:
    require(historical.get("recorded_on") == RECORDED_ON,
            "v1.9 historical calendar tag drift")
    immutable_binding(HISTORICAL_GATE_COMMIT,
                      historical["authorities"]["gate"])
    append_only_plan(historical["authorities"]["plan"])
    current["authorities"]["plan"] = historical["authorities"]["plan"]
    current["authorities"]["gate"] = historical["authorities"]["gate"]
    require(canonical(current) == canonical(historical),
            "v1.9 replay-closure receipt drift")
    return historical


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout.strip()


def reject(label: str, action: Callable[[], None],
           mutations: dict[str, str]) -> None:
    try:
        action()
    except ReplayError as error:
        mutations[label] = str(error)
    else:
        raise ReplayError(f"v1.9 replay mutation survived: {label}")


def audit_inventory(value: dict[str, Any], expected_elf: Path) -> None:
    require(value["status"] == "passed", "historical inventory is red")
    require(value["final_elf_sha256"] == sha(expected_elf),
            "historical inventory is bound to another ELF")
    require(value["pin"]["expected_sections"] == 190
            and len(value["actual_sections"]) == 190,
            "historical inventory does not close all 190 sections")
    require(value["missing_sections"] == []
            and value["unknown_sections"] == [],
            "historical inventory contains a vocabulary hole")
    require(set(value["negative_matrix"]) == {
        "additional-section", "allocated-sympart", "exact-pinned-inventory",
        "full-map-deleted-sections", "full-map-moved-sections",
        "full-map-unowned-stray", "loaded-address-sympart",
        "missing-section", "reordered-sections", "resized-sympart",
    }, "historical inventory negative-matrix drift")


def audit_facts(facts: dict[str, Any]) -> None:
    require(facts["vocabulary_status"] == "PASS",
            "acceptance vocabulary is red")
    require(facts["vocabulary_mutations"] >= 340,
            "acceptance vocabulary mutation closure is incomplete")
    require(facts["phase_c_status"] == "PASS",
            "SHA-bound v1.8 replay gate is red")
    require(facts["product_replay_links"] == 2
            and facts["micro_links"] == 2,
            "replay link execution witness drift")
    require(facts["phase_c_mutations"] == 29,
            "replay mutation execution witness drift")
    require(facts["product_compiles"] == 0
            and facts["fresh_wplto"] == 0
            and facts["device_contacts"] == 0,
            "replay crossed its host-only/no-WPLTO boundary")
    require(facts["five_byte_margin"] == 5,
            "ordinary-chain non-freight margin drift")
    require(facts["seed_inventory_sections"] == 190
            and facts["final_inventory_sections"] == 190,
            "190/190 final-inventory replay drift")
    require(facts["seed_abi_status"] ==
            facts["final_abi_status"] ==
            "passed-all-assembler-leaf-abi-contracts",
            "exact terminal artifact ABI closure is red")
    require(facts["seed_c_called_assembler_members"] ==
            facts["final_c_called_assembler_members"] == 13,
            "ELF-derived assembler caller universe drift")
    require(facts["unclassified_assembler_members"] == 0,
            "ELF-derived assembler member lacks ABI policy")
    require(facts["terminal_result_union"] ==
            "typed-failure-no-success-consumption",
            "terminal failure/success receipt union regressed")
    require(facts["sole_card_driver_present"],
            "sole v1.9 card driver absent")


def mutation_selftest(facts: dict[str, Any]) -> dict[str, str]:
    cases: dict[str, tuple[str, Any]] = {
        "vocabulary-red": ("vocabulary_status", "FAIL"),
        "vocabulary-member-missing": ("vocabulary_mutations", 339),
        "phase-c-red": ("phase_c_status", "FAIL"),
        "one-product-replay": ("product_replay_links", 1),
        "one-micro-link": ("micro_links", 1),
        "phase-c-mutation-missing": ("phase_c_mutations", 28),
        "product-compile": ("product_compiles", 1),
        "fresh-wplto": ("fresh_wplto", 1),
        "device-contact": ("device_contacts", 1),
        "margin-consumed": ("five_byte_margin", 4),
        "seed-section-missing": ("seed_inventory_sections", 189),
        "final-section-missing": ("final_inventory_sections", 189),
        "seed-abi-red": ("seed_abi_status", "FAIL"),
        "final-abi-red": ("final_abi_status", "FAIL"),
        "derived-caller-missing": ("final_c_called_assembler_members", 12),
        "unclassified-assembler-leaf": ("unclassified_assembler_members", 1),
        "failure-consumed-as-success": ("terminal_result_union", "ambiguous"),
        "card-driver-absent": ("sole_card_driver_present", False),
    }
    rejected: dict[str, str] = {}
    for name, (key, bad) in cases.items():
        mutant = deepcopy(facts)
        mutant[key] = bad
        reject(name, lambda mutant=mutant: audit_facts(mutant), rejected)
    return rejected


def build_receipt() -> dict[str, Any]:
    vocabulary = load(VOCABULARY)
    phase_c = load(PHASE_C)
    seed_inventory = load(SEED_INVENTORY)
    final_inventory = load(FINAL_INVENTORY)
    run([sys.executable,
         "tools/host-lisp/c2_v19_acceptance_vocabulary.py", "check"],
        "v1.9 vocabulary reconstruction")
    phase_c_output = run(
        [sys.executable, "tools/host-lisp/c2_v18_full_map_phase_c.py", "check"],
        "SHA-bound v1.8 Phase-C replay")
    audit_inventory(seed_inventory, SEED_ELF)
    audit_inventory(final_inventory, FINAL_ELF)
    seed_abi = ABI.audit_elf(SEED_ELF)
    final_abi = ABI.audit_elf(FINAL_ELF)
    seed_derived = seed_abi["ELF_derived_C_called_inventory"]
    final_derived = final_abi["ELF_derived_C_called_inventory"]
    facts = {
        "vocabulary_status": vocabulary["status"],
        "vocabulary_mutations": vocabulary["execution_witness"]["mutations"],
        "phase_c_status": phase_c["status"],
        "product_replay_links": phase_c["execution_witness"][
            "bound_product_object_relinks"],
        "micro_links": phase_c["execution_witness"]["clean_micro_links"],
        "phase_c_mutations": phase_c["execution_witness"]["mutations"],
        "product_compiles": phase_c["execution_witness"]["product_compiles"],
        "fresh_wplto": phase_c["execution_witness"]["fresh_wplto"],
        "device_contacts": phase_c["execution_witness"]["hardware_runs"],
        "five_byte_margin": phase_c["bound_product_object_replay"][
            "five_byte_margin"],
        "seed_inventory_sections": len(seed_inventory["actual_sections"]),
        "final_inventory_sections": len(final_inventory["actual_sections"]),
        "seed_abi_status": seed_abi["status"],
        "final_abi_status": final_abi["status"],
        "seed_c_called_assembler_members": len(
            seed_derived["C_called_functions"]),
        "final_c_called_assembler_members": len(
            final_derived["C_called_functions"]),
        "unclassified_assembler_members": len(set(
            seed_derived["unclassified_C_called_functions"])
            | set(final_derived["unclassified_C_called_functions"])),
        "terminal_result_union": vocabulary["classes"][
            "driver_receipt_tokens"]["historical_failure_class"],
        "sole_card_driver_present": DRIVER.is_file(),
    }
    audit_facts(facts)
    mutations = mutation_selftest(facts)
    return {
        "format": "lisp65-c2.3-v1.9-full-map-replay-closure-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS",
        "claim": (
            "SHA-bound no-WPLTO rehearsal of the full-map acceptance path "
            "against the real v1.7 failure object and both exact terminal "
            "v1.8 artifacts; no fresh product compile, WPLTO, device, Link "
            "91, parity-surface or release claim."),
        "facts": facts,
        "phase_c_reconstruction": {
            "status": "PASS",
            "stdout": phase_c_output.splitlines()[-1],
            "product_replay_links": facts["product_replay_links"],
            "micro_links": facts["micro_links"],
            "fresh_wplto": 0,
        },
        "exact_terminal_artifacts": {
            "seed_elf": bind(SEED_ELF),
            "final_elf": bind(FINAL_ELF),
            "seed_inventory": bind(SEED_INVENTORY),
            "final_inventory": bind(FINAL_INVENTORY),
            "seed_abi": facts["seed_abi_status"],
            "final_abi": facts["final_abi_status"],
        },
        "mutations_rejected": mutations,
        "execution_witness": {
            "product_replay_links": facts["product_replay_links"],
            "micro_links": facts["micro_links"],
            "phase_c_mutations": facts["phase_c_mutations"],
            "recharter_mutations": len(mutations),
            "vocabulary_mutations": facts["vocabulary_mutations"],
            "product_compiles": 0,
            "fresh_wplto": 0,
            "device_contacts": 0,
        },
        "authorities": {
            "vocabulary": bind(VOCABULARY),
            "phase_c": bind(PHASE_C),
            "plan": bind(PLAN),
            "sole_card_driver": bind(DRIVER),
            "gate": bind(Path(__file__).resolve()),
        },
        "card_gate": {
            "authorized": True,
            "cards_remaining": 1,
            "retry_authorized": False,
            "condition": (
                "This receipt authorizes exactly one fresh host-only v1.9 "
                "product-shaped WPLTO card. Every red is terminal."),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("selftest", "write", "check"))
    args = parser.parse_args()
    value = build_receipt()
    if args.mode == "write":
        RECEIPT.write_bytes(canonical(value))
    elif args.mode == "check":
        require(RECEIPT.is_file(), "v1.9 replay-closure receipt absent")
        # The finally parked receipt remains immutable. Reconstruct today's
        # facts, then bind the historical plan/gate authorities that existed
        # when the receipt was recorded. The append-only and git checks above
        # make this a loud dated rebind rather than a silent receipt rewrite.
        value = historical_rebind(load(RECEIPT), value)
    witness = value["execution_witness"]
    print("c2-v19-full-map-replay: PASS "
          f"micro={witness['micro_links']} "
          f"replays={witness['product_replay_links']} "
          f"sections=190/190 abi=13/17 "
          f"mutations={witness['recharter_mutations']} "
          "compiles=0 wplto=0 device=0 card=one")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReplayError, OSError, ValueError, KeyError) as error:
        print(f"c2-v19-full-map-replay: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
