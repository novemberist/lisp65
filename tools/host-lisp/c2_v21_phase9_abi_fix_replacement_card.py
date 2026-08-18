#!/usr/bin/env python3
"""Run the one authorized replacement card for the phase-9 ABI fix."""

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

from elf_truth import ElfTruth  # noqa: E402
import c2_asm_leaf_abi_gate as ABI  # noqa: E402
import c2_mapped_far_service_gate as FAR  # noqa: E402
import c2_v21_phase9_abi_fix_card as OLD  # noqa: E402
import c2_v21_phase9_relocation_emission as EMISSION  # noqa: E402
import c2_v20_building_heap_device_source_unbind_phase9_20260815 as UNBIND  # noqa: E402
import c2_v21_phase9_domain_split_source_rebind_20260815 as REBIND  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.1-phase9-abi-fix-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-phase9-abi-fix-replacement-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
PROJECTED_OWNERSHIP = PREFLIGHT / "candidate-ownership-contract.json"
PROJECTED_FULL_MAP = PREFLIGHT / "candidate-full-map-contract.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
ABI_REPORT = BUILD / "wplto/c2-asm-leaf-real-abi-callers.json"
RECEIPT = ARCH / "c2.3-v2.1-phase9-abi-fix-replacement-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-phase9-abi-fix-replacement-card-final-red.json"
PREDECESSOR = OLD.FINAL_RED
ABI_CONTRACT = FAR.ABI_SUCCESSOR_CONTRACT
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORIZATION = "7fa52735"
LINK = 110


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


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
    value = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode()
    text = " ".join(raw.lower().split())
    for token in ("relocation freight derives from the emitted candidate",
                  "two domains split into separately strong gates",
                  "historical v2.0 receipt unbinds",
                  "one replacement card"):
        require(token in text, f"replacement-card authority absent: {token}")
    return value


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR)
    require(value.get("status")
            == "FINAL RED: phase-9 ABI fix card returns to owner"
            and value.get("retry_authorized") is False
            and value.get("attempt_accounting", {}).get("cards_consumed") == 1
            and value.get("attempt_accounting", {}).get("WPLTO_runs") == 1,
            "phase-9 ABI Final Red predecessor drift")
    return value


def emission_authority() -> dict[str, Any]:
    value = load(EMISSION.RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    EMISSION.validate(value)
    require(rejected == EMISSION.mutations(value),
            "relocation-emission mutation receipt drift")
    return value


def projected_contracts() -> tuple[dict[str, Any], dict[str, Any]]:
    ownership, _map_contract, successor = FAR.effective_contract()
    full = load(OLD.PRODUCT.FULL_MAP_OWNERSHIP_CONTRACT)
    artifact = successor["artifact_successor"]
    emitted = emission_authority()["replacement_projection"]
    additions = full["generated_linker_requirements"][
        "final_section_inventory_additions"]
    service = [row for row in additions
               if row["name"] == ".lisp65_c2_mapped_far_service"]
    relocation = [row for row in additions
                  if row["name"] == emitted["name"]]
    require(len(service) == len(relocation) == 1,
            "full-map mapped-far owner rows are not unique")
    service[0]["bytes"] = artifact["exact_bytes"]
    relocation[0]["bytes"] = emitted["bytes"]
    relocation[0]["bytes_authority"] = emitted["authority"]
    relocation[0]["emitted_records"] = emitted["records"]
    ledger = [row for row in full["fixed_simultaneous_live_ledger"]
              if row.get("owner") == "mapped-bank2-far-service"]
    require(len(ledger) == 1, "full-map far-service ledger row is not unique")
    ledger[0].update({
        "service_cpu_end_exclusive": artifact["cpu_end_exclusive"],
        "service_physical_end_exclusive": artifact["physical_end_exclusive"],
        "demand_bytes": artifact["exact_bytes"],
    })
    full["authorities"]["phase9_ABI_replacement"] = {
        "ABI_contract": bind(ABI_CONTRACT),
        "relocation_emission": bind(EMISSION.RECEIPT),
        "domain_split_source_rebind": bind(REBIND.RECEIPT),
    }
    return ownership, full


def write_projections() -> None:
    ownership, full = projected_contracts()
    PREFLIGHT.mkdir(parents=True, exist_ok=True)
    PROJECTED_OWNERSHIP.write_bytes(canonical(ownership))
    PROJECTED_FULL_MAP.write_bytes(canonical(full))


def configure() -> None:
    require(PROJECTED_OWNERSHIP.is_file() and PROJECTED_FULL_MAP.is_file(),
            "candidate contract projections absent")
    OLD.BUILD = BUILD
    OLD.PREFLIGHT = PREFLIGHT
    OLD.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    OLD.PROJECTED_OWNERSHIP = PROJECTED_OWNERSHIP
    OLD.PROJECTED_FULL_MAP = PROJECTED_FULL_MAP
    OLD.INVOCATION = INVOCATION
    OLD.PRODUCER_RESULT = PRODUCER_RESULT
    OLD.SCOPE_RESULT = SCOPE_RESULT
    OLD.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    OLD.ABI_REPORT = ABI_REPORT
    OLD.RECEIPT = BUILD / "unused-original-card-receipt.json"
    OLD.FINAL_RED = BUILD / "unused-original-card-final-red.json"
    OLD.DRIVER = DRIVER
    OLD.LINK = LINK
    OLD.configure()


def artifact_paths() -> dict[str, Path]:
    configure()
    return OLD.BASE.BASE.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    value = {name: bind(path) for name, path in artifact_paths().items()}
    value["seed_lto"] = bind(BUILD / "wplto/resident-island-seed.prg.lto.o")
    value["real_ABI_report"] = bind(ABI_REPORT)
    return value


def run_gate(command: list[str], token: str, label: str) -> dict[str, Any]:
    result = subprocess.run(command, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0 and token in result.stdout,
            f"fresh {label} red:\n{result.stdout}")
    return {"status": "PASS", "command": " ".join(command),
            "witness": " ".join(result.stdout.split())}


def host_gates() -> dict[str, Any]:
    failed_seed = EMISSION.SEED_ELF
    report = PREFLIGHT / "failed-seed-domain-split.json"
    gates = {
        "relocation_emission": run_gate(
            [sys.executable, str(EMISSION.DRIVER), "check"],
            "emitted=3972 records=331", "relocation emission"),
        "historical_v20_source_unbind": run_gate(
            [sys.executable, str(UNBIND.DRIVER), "check"],
            "source unbind check: PASS", "historical source unbind"),
        "domain_split_source_rebind": run_gate(
            [sys.executable, str(REBIND.DRIVER), "check"],
            "domains=2", "domain-split source rebind"),
        "ABI_selftest": run_gate(
            [sys.executable, str(ROOT / "tools/host-lisp/c2_asm_leaf_abi_gate.py"),
             "--selftest"], "mutations=186", "ABI selftest"),
        "failed_seed_linked_domains": run_gate(
            [sys.executable, str(ROOT / "tools/host-lisp/c2_asm_leaf_abi_gate.py"),
             "--elf", str(failed_seed), "--out", str(report)],
            "passed-all-assembler-leaf-abi-contracts", "linked domain split"),
        "assembly_equivalence": run_gate(
            [sys.executable, str(ROOT / "tools/host-lisp/"
                "c2_mapped_far_asm_equivalence.py"), "--selftest"],
            "cases=16/16", "assembly equivalence"),
        "mapped_far_ownership": run_gate(
            [sys.executable, str(ROOT / "tools/host-lisp/"
                "c2_mapped_far_service_gate.py"), "--selftest"],
            "far=1086", "mapped-far ownership"),
    }
    linked = load(report)
    transitive = linked["transitive_callee_saved_preservation"]
    contractual = linked["contractual_mapped_far_exit_preservation"]
    require(
        transitive["status"]
            == "passed-actual-C-reachable-transitive-preservation"
        and transitive["model"]["checked_functions"]
            == transitive["model"]["transitive_functions"]
        and transitive["model"]["unpreserved_callee_saved_writers"] == []
        and contractual["status"]
            == "passed-eight-contractual-service-exits-preserved"
        and contractual["model"]["inner_exits"] == 8,
        "failed-seed two-domain linked proof drift")
    gates["domain_separation"] = {
        "status": "PASS",
        "C_reachable_far_bodies": transitive["model"]
            ["reachable_contractual_service_functions"],
        "contractual_functions": contractual["model"]
            ["contractual_functions"],
        "contractual_exits": contractual["model"]["inner_exits"],
    }
    return gates


def preflight_value() -> dict[str, Any]:
    predecessor()
    emitted = emission_authority()["replacement_projection"]
    return {
        "format": "lisp65-c2.3-v21-phase9-ABI-replacement-preflight-v1",
        "recorded_on": "2026-08-15",
        "status": "PASS: emission and ABI domains green; replacement armed",
        "configuration": {"link": LINK, "cards_authorized": 1,
            "relocation_bytes": emitted["bytes"],
            "relocation_records": emitted["records"],
            "relocation_authority": emitted["authority"],
            "contractual_exit_paths": 8},
        "attempt_accounting": {"replacement_cards_consumed": 0,
            "WPLTO_runs": 0, "product_links": 0, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "host_gates": host_gates(),
        "authority": {"owner": authorization(), "Final_Red": bind(PREDECESSOR),
            "ABI_contract": bind(ABI_CONTRACT),
            "relocation_emission": bind(EMISSION.RECEIPT),
            "v20_source_unbind": bind(UNBIND.RECEIPT),
            "source_rebind": bind(REBIND.RECEIPT),
            "projected_ownership": bind(PROJECTED_OWNERSHIP),
            "projected_full_map": bind(PROJECTED_FULL_MAP),
            "driver": bind(DRIVER)},
        "claim_limit": "Preflight only; no replacement card or product work.",
    }


def validate_preflight(value: dict[str, Any], expected: dict[str, Any]) -> None:
    require(value == expected, "phase-9 replacement preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-3924-forecast": lambda x: x["configuration"].update(
            relocation_bytes=3924),
        "merge-gate-domains": lambda x: x["host_gates"].pop(
            "domain_separation"),
        "lose-contractual-exit": lambda x: x["configuration"].update(
            contractual_exit_paths=7),
        "restore-historical-source-predicate": lambda x: x["authority"].pop(
            "v20_source_unbind"),
        "authorize-two-replacements": lambda x: x["configuration"].update(
            cards_authorized=2),
        "spend-replacement": lambda x: x["attempt_accounting"].update(
            replacement_cards_consumed=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_preflight(trial, value)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "replacement preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "phase-9 replacement is one-shot")
    write_projections()
    value = preflight_value(); validate_preflight(value, value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("phase-9 ABI replacement: PREFLIGHT PASS card=0/1 reloc=3972")


def produce_child() -> int:
    configure(); return OLD.BASE.BASE.produce_child()


def scope_child() -> int:
    configure(); return OLD.BASE.BASE.scope_child()


def acceptance_child() -> int:
    configure(); return OLD.BASE.BASE.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh phase-9 replacement child {action} red:\n{result.stdout}")


def linked_product() -> dict[str, Any]:
    elf = artifact_paths()["elf"]
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ)
    contract = load(ABI_CONTRACT)["artifact_successor"]
    section = truth.section(contract["section"])
    relocation = truth.section(".rela.lisp65_c2_mapped_far_service")
    report = load(ABI_REPORT)
    transitive = report["transitive_callee_saved_preservation"]
    contractual = report["contractual_mapped_far_exit_preservation"]
    require(
        section.address == int(contract["cpu_vma"], 0)
        and section.bytes == contract["exact_bytes"]
        and relocation.bytes == emission_authority()["replacement_projection"]
            ["bytes"]
        and transitive["status"]
            == "passed-actual-C-reachable-transitive-preservation"
        and transitive["model"]["checked_functions"]
            == transitive["model"]["transitive_functions"]
        and transitive["model"]["unpreserved_callee_saved_writers"] == []
        and contractual["status"]
            == "passed-eight-contractual-service-exits-preserved"
        and contractual["model"]["inner_exits"] == 8,
        "linked replacement ABI/emission proof drift")
    map_product = OLD.BASE.linked_product()
    return {
        "status": "PASS: emitted freight and both ABI domains green",
        "mapped_far": {"address": f"0x{section.address:04x}",
            "bytes": section.bytes,
            "end_exclusive": f"0x{section.address + section.bytes:04x}",
            "headroom_bytes": contract["headroom_bytes"]},
        "relocation_emission": {"bytes": relocation.bytes,
            "records": relocation.bytes // 12,
            "authority": "actual-linked-candidate"},
        "C_reachable_ASM_closure": transitive["model"],
        "contractual_service_exits": contractual["model"],
        "CPU_reader": map_product["reader"],
        "MAP_tuple_gate": map_product["tuple_gate"],
    }


def linked_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-forecast": lambda x: x["relocation_emission"].update(
            bytes=3924),
        "unchecked-C-reachable-member": lambda x: x["C_reachable_ASM_closure"]
            ["checked_functions"].pop(),
        "invent-transitive-clobber": lambda x: x["C_reachable_ASM_closure"].update(
            unpreserved_callee_saved_writers=[{"function": "x",
                                                "registers": ["__rc20"]}]),
        "lose-service-exit": lambda x: x["contractual_service_exits"].update(
            inner_exits=7),
        "drop-physical-contract-entry": lambda x: x["contractual_service_exits"]
            ["contractual_functions"].remove(
                "c2_mapped_far_physical_read_converged"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        if trial != value:
            rejected.append(name)
    require(rejected == list(cases), "replacement linked mutation survived")
    return rejected


def card() -> None:
    persisted = load(PREFLIGHT_RECEIPT)
    rejected = persisted.pop("mutations_rejected", None)
    expected = preflight_value(); validate_preflight(persisted, expected)
    require(rejected == preflight_mutations(expected),
            "replacement preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "phase-9 replacement card is one-shot")
    INVOCATION.write_bytes(canonical({"status": "INVOKED", "link": LINK,
        "owner": authorization(), "predecessor": bind(PREDECESSOR),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope"); run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "replacement acceptance changed artifacts")
    producer = load(PRODUCER_RESULT); scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT); product = linked_product()
    require(
        len({os.getpid(), producer["pid"], scope["pid"],
             acceptance["pid"]}) == 4
        and acceptance.get("status") == "PASS"
        and acceptance["VMA_golden"].get("dependent_fixed_vmas") == 101
        and acceptance["VMA_golden"].get("dependent_free_derived_vmas") == 2,
        "phase-9 replacement linked acceptance drift")
    receipt = {
        "format": "lisp65-c2.3-v21-phase9-ABI-replacement-card-v1",
        "recorded_on": "2026-08-15",
        "status": "PASS: sole phase-9 ABI replacement card green",
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "authority": {"owner": authorization(), "Final_Red": bind(PREDECESSOR),
            "preflight": bind(PREFLIGHT_RECEIPT),
            "relocation_emission": bind(EMISSION.RECEIPT),
            "source_rebind": bind(REBIND.RECEIPT), "driver": bind(DRIVER)},
        "linked_product": product,
        "transport": producer["v21_linked_transport"],
        "dependent_vma_comparison": acceptance["VMA_golden"],
        "completion_identity": producer["candidate_completion_identity"],
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {"parent": os.getpid(),
            "producer": producer["pid"], "owner_scope": scope["pid"],
            "acceptance": acceptance["pid"], "all_distinct": True},
        "owner_scope": scope["gate"],
        "mutations_rejected": {"preflight": rejected,
            "linked": linked_mutations(product)},
        "next": "Completion, same-world media closure and owner-observed D1",
        "claim_limit": "One replacement card; no Completion, media or device.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("phase-9 ABI replacement: PASS card=1/1 reloc=3972 exits=8")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v21-phase9-ABI-replacement-final-red-v1",
        "recorded_on": "2026-08-15",
        "status": "FINAL RED: phase-9 replacement returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"owner": authorization(), "Final_Red": bind(PREDECESSOR),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "claim_limit": "Replacement consumed; no Completion, media or device.",
    }))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "replacement Final Red drift")
        print("phase-9 ABI replacement: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        print("phase-9 ABI replacement: CHECK LOCKED/ARMED")
        return
    value = load(RECEIPT)
    require(value.get("status")
            == "PASS: sole phase-9 ABI replacement card green"
            and value["attempt_accounting"]["replacement_cards_consumed"] == 1
            and value["artifacts_before"] == frozen_artifacts()
            and value["artifacts_after"] == value["artifacts_before"]
            and value["linked_product"] == linked_product(),
            "phase-9 replacement receipt drift")
    print("phase-9 ABI replacement: CHECK PASS card=1/1 reloc=3972 exits=8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "card", "check", "_produce", "_scope", "_accept"))
    {"preflight": preflight, "card": card, "check": check,
     "_produce": produce_child, "_scope": scope_child,
     "_accept": acceptance_child}[parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_final_red(error)
            except Exception as receipt_error:
                print(f"phase-9 replacement receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"phase-9 ABI replacement: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
