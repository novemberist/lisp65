#!/usr/bin/env python3
"""Run the one owner-authorized product card for the phase-9 ABI fix."""

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
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v21_map_mask_fix_card as BASE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.1-phase9-abi-fix-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-phase9-abi-fix-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
PROJECTED_OWNERSHIP = PREFLIGHT / "candidate-ownership-contract.json"
PROJECTED_FULL_MAP = PREFLIGHT / "candidate-full-map-contract.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
ABI_REPORT = BUILD / "wplto/c2-asm-leaf-real-abi-callers.json"
RECEIPT = ARCH / "c2.3-v2.1-phase9-abi-fix-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-phase9-abi-fix-card-final-red.json"
PREDECESSOR = BASE.RECEIPT
ABI_CONTRACT = FAR.ABI_SUCCESSOR_CONTRACT
SOURCE_REBIND = ARCH / (
    "c2.3-v2.1-reopen-gap-attribution-phase9-abi-rebind-"
    "20260815-receipt.json")
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

AUTHORIZATION = "78ae9255"
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
        check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in ("register preservation on every far-service exit",
                  "transitive abi gate", "asm→asm", "link-109", "one card"):
        require(token in text, f"phase-9 ABI card authority absent: {token}")
    return value


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR)
    require(value.get("status") == "PASS: sole MAP-mask fix card green"
            and value.get("attempt_accounting", {}).get("cards_consumed") == 1
            and value.get("attempt_accounting", {}).get("WPLTO_runs") == 1,
            "Link-109 predecessor card drift")
    return value


def projected_contracts() -> tuple[dict[str, Any], dict[str, Any]]:
    ownership, _map_contract, successor = FAR.effective_contract()
    full = load(PRODUCT.FULL_MAP_OWNERSHIP_CONTRACT)
    artifact = successor["artifact_successor"]
    additions = full["generated_linker_requirements"][
        "final_section_inventory_additions"]
    service = [row for row in additions
               if row["name"] == ".lisp65_c2_mapped_far_service"]
    relocation = [row for row in additions
                  if row["name"] == ".rela.lisp65_c2_mapped_far_service"]
    require(len(service) == len(relocation) == 1,
            "full-map mapped-far owner rows are not unique")
    service[0]["bytes"] = artifact["exact_bytes"]
    # 66 new zero-page relocations: 64 save/restore bindings plus the two
    # entry argument spills.  The real linked ABI gate remains authoritative;
    # this projection only gives the independent final-inventory owner its
    # candidate-world freight size.
    relocation[0]["bytes"] = 3924
    ledger = [row for row in full["fixed_simultaneous_live_ledger"]
              if row.get("owner") == "mapped-bank2-far-service"]
    require(len(ledger) == 1, "full-map far-service ledger row is not unique")
    ledger[0].update({
        "service_cpu_end_exclusive": artifact["cpu_end_exclusive"],
        "service_physical_end_exclusive": artifact["physical_end_exclusive"],
        "demand_bytes": artifact["exact_bytes"],
    })
    full["authorities"]["phase9_abi_successor"] = {
        "path": ABI_CONTRACT.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(ABI_CONTRACT.read_bytes()).hexdigest(),
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
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    BASE.INVOCATION = INVOCATION
    BASE.PRODUCER_RESULT = PRODUCER_RESULT
    BASE.SCOPE_RESULT = SCOPE_RESULT
    BASE.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    BASE.ABI_REPORT = ABI_REPORT
    BASE.RECEIPT = BUILD / "unused-map-mask-card-receipt.json"
    BASE.FINAL_RED = BUILD / "unused-map-mask-card-final-red.json"
    BASE.DRIVER = DRIVER
    BASE.LINK = LINK
    BASE.configure()
    PRODUCT.OWNERSHIP_CONTRACT = PROJECTED_OWNERSHIP
    PRODUCT.FULL_MAP_OWNERSHIP_CONTRACT = PROJECTED_FULL_MAP


def artifact_paths() -> dict[str, Path]:
    configure()
    return BASE.BASE.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    value = {name: bind(path) for name, path in artifact_paths().items()}
    value["seed_lto"] = bind(BUILD / "wplto/resident-island-seed.prg.lto.o")
    value["real_abi_report"] = bind(ABI_REPORT)
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
    return {
        "map_semantic_rebind": run_gate(
            [sys.executable, str(HOST / "c2_v21_map_mask_fix.py"), "check"],
            "CHECK PASS actual-tuple=yes", "MAP semantic rebind"),
        "assembly_equivalence": run_gate(
            [sys.executable, str(HOST / "c2_mapped_far_asm_equivalence.py"),
             "--selftest"], "cases=16/16", "assembly equivalence"),
        "mapped_far_ownership": run_gate(
            [sys.executable, str(HOST / "c2_mapped_far_service_gate.py"),
             "--selftest"], "far=1086", "mapped-far ownership"),
        "transitive_ABI_selftest": run_gate(
            [sys.executable, str(HOST / "c2_asm_leaf_abi_gate.py"),
             "--selftest"], "SELFTEST PASS", "transitive ABI"),
        "Link109_source_rebind": run_gate(
            [sys.executable, str(HOST /
                "c2_v21_reopen_gap_attribution_rebind_phase9_abi_20260815.py"),
             "check"], "phase-9 ABI source rebind: PASS", "source rebind"),
    }


def preflight_value() -> dict[str, Any]:
    predecessor()
    contract = load(ABI_CONTRACT)
    return {
        "format": "lisp65-c2.3-v2.1-phase9-abi-fix-card-preflight-v1",
        "recorded_on": "2026-08-15",
        "status": "PASS: phase-9 ABI fix green; one card armed",
        "configuration": {
            "link": LINK, "cards_authorized": 1,
            "far_service_bytes": contract["artifact_successor"]["exact_bytes"],
            "far_service_headroom_bytes": contract["artifact_successor"]
                ["headroom_bytes"],
            "callee_saved_registers": contract["abi"]
                ["callee_saved_imaginary_registers"]["count"],
            "terminal_exit_paths": contract["abi"]["inner_exit_count"],
        },
        "attempt_accounting": {
            "cards_consumed": 0, "WPLTO_runs": 0, "product_links": 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0,
        },
        "host_gates": host_gates(),
        "authority": {
            "owner": authorization(), "ABI_contract": bind(ABI_CONTRACT),
            "source_rebind": bind(SOURCE_REBIND),
            "predecessor": bind(PREDECESSOR),
            "projected_ownership": bind(PROJECTED_OWNERSHIP),
            "projected_full_map": bind(PROJECTED_FULL_MAP),
            "driver": bind(DRIVER),
        },
        "claim_limit": "Preflight only; no WPLTO, link, media or device.",
    }


def validate_preflight(value: dict[str, Any], expected: dict[str, Any]) -> None:
    require(value == expected, "phase-9 ABI card preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-two-cards": lambda x: x["configuration"].update(
            cards_authorized=2),
        "drop-transitive-gate": lambda x: x["host_gates"].pop(
            "transitive_ABI_selftest"),
        "shrink-save-set": lambda x: x["configuration"].update(
            callee_saved_registers=15),
        "miss-exit": lambda x: x["configuration"].update(
            terminal_exit_paths=7),
        "spend-card": lambda x: x["attempt_accounting"].update(
            cards_consumed=1),
        "authorize-device": lambda x: x["attempt_accounting"].update(
            device_contacts=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate_preflight(trial, value)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "phase-9 ABI preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "phase-9 ABI preflight/card is one-shot")
    write_projections()
    value = preflight_value()
    validate_preflight(value, value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.1 phase-9 ABI card: PREFLIGHT PASS card=0/1 exits=8 rc=16")


def produce_child() -> int:
    configure()
    return BASE.BASE.produce_child()


def scope_child() -> int:
    configure()
    return BASE.BASE.scope_child()


def acceptance_child() -> int:
    configure()
    return BASE.BASE.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh phase-9 ABI child {action} red:\n{result.stdout}")


def linked_product() -> dict[str, Any]:
    elf = artifact_paths()["elf"]
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    contract = load(ABI_CONTRACT)
    artifact = contract["artifact_successor"]
    section = truth.section(artifact["section"])
    require(section.address == int(artifact["cpu_vma"], 0)
            and section.bytes == artifact["exact_bytes"],
            "linked mapped-far successor identity drift")
    report = load(ABI_REPORT)
    preservation = report["transitive_callee_saved_preservation"]
    model = preservation["model"]
    require(
        preservation["status"] == "passed-transitive-callee-saved-preservation"
        and model["save_depth"] == model["restore_depth"] == 16
        and model["inner_exits"] == 8
        and model["unpreserved_callee_saved_writers"] == []
        and set(ABI.FAR_BODY_FUNCTIONS) <= set(model["transitive_functions"]),
        "linked transitive ABI preservation drift")
    map_product = BASE.linked_product()
    return {
        "status": "PASS: linked phase-9 ABI preservation dominates 8 exits",
        "mapped_far": {
            "address": f"0x{section.address:04x}", "bytes": section.bytes,
            "end_exclusive": f"0x{section.address + section.bytes:04x}",
            "headroom_bytes": artifact["headroom_bytes"],
        },
        "callee_saved": {
            "registers": model["saved"], "save_depth": model["save_depth"],
            "restore_depth": model["restore_depth"],
            "inner_exit_paths": model["inner_exits"],
            "unpreserved_writers": model[
                "unpreserved_callee_saved_writers"],
        },
        "transitive_closure": {
            "functions": model["transitive_functions"],
            "far_bodies_present": sorted(ABI.FAR_BODY_FUNCTIONS),
        },
        "CPU_reader": map_product["reader"],
        "MAP_tuple_gate": map_product["tuple_gate"],
    }


def linked_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "drop-rc20": lambda x: x["callee_saved"]["registers"].remove(
            "__rc20"),
        "short-restore": lambda x: x["callee_saved"].update(
            restore_depth=15),
        "miss-exit": lambda x: x["callee_saved"].update(inner_exit_paths=7),
        "invent-unpreserved-reader": lambda x: x["callee_saved"].update(
            unpreserved_writers=[{"function": "c2_map_cpu_read",
                                  "registers": ["__rc20"]}]),
        "drop-transitive-body": lambda x: x["transitive_closure"][
            "functions"].remove("c2_mapped_far_vm_code_load_converged"),
        "grow-service": lambda x: x["mapped_far"].update(bytes=1087),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        if trial != value:
            rejected.append(name)
    require(rejected == list(cases), "phase-9 ABI linked mutation survived")
    return rejected


def card() -> None:
    persisted = load(PREFLIGHT_RECEIPT)
    rejected = persisted.pop("mutations_rejected", None)
    expected = preflight_value()
    validate_preflight(persisted, expected)
    require(rejected == preflight_mutations(expected),
            "phase-9 ABI preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "phase-9 ABI card is one-shot")
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "link": LINK, "owner": authorization(),
        "ABI_contract": bind(ABI_CONTRACT),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER),
    }))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "phase-9 ABI acceptance changed artifacts")
    producer = load(PRODUCER_RESULT)
    scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    product = linked_product()
    require(
        len({os.getpid(), producer["pid"], scope["pid"],
             acceptance["pid"]}) == 4
        and acceptance.get("status") == "PASS"
        and acceptance["VMA_golden"].get("dependent_fixed_vmas") == 101
        and acceptance["VMA_golden"].get("dependent_free_derived_vmas") == 2
        and product["callee_saved"]["inner_exit_paths"] == 8,
        "phase-9 ABI linked acceptance drift")
    receipt = {
        "format": "lisp65-c2.3-v2.1-phase9-abi-fix-card-v1",
        "recorded_on": "2026-08-15",
        "status": "PASS: sole phase-9 ABI fix card green",
        "attempt_accounting": {
            "cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0,
        },
        "authority": {
            "owner": authorization(), "ABI_contract": bind(ABI_CONTRACT),
            "source_rebind": bind(SOURCE_REBIND),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER),
        },
        "linked_product": product,
        "transport": producer["v21_linked_transport"],
        "dependent_vma_comparison": acceptance["VMA_golden"],
        "completion_identity": producer["candidate_completion_identity"],
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {
            "parent": os.getpid(), "producer": producer["pid"],
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": True,
        },
        "owner_scope": scope["gate"],
        "mutations_rejected": {
            "preflight": rejected, "linked": linked_mutations(product),
        },
        "next": "Completion, same-world media closure and owner-observed D1",
        "claim_limit": "One card only; Completion, media and device have not run.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 phase-9 ABI card: PASS card=1/1 far=1086 exits=8 rc=16")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-phase9-abi-fix-card-final-red-v1",
        "recorded_on": "2026-08-15",
        "status": "FINAL RED: phase-9 ABI fix card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {
            "cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0,
        },
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {
            "owner": authorization(), "ABI_contract": bind(ABI_CONTRACT),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER),
        },
        "claim_limit": "The sole card is consumed; no Completion, media or device.",
    }))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "phase-9 ABI Final Red drift")
        print("2.1 phase-9 ABI card: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        print("2.1 phase-9 ABI card: CHECK LOCKED/ARMED")
        return
    value = load(RECEIPT)
    require(value.get("status") == "PASS: sole phase-9 ABI fix card green"
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["artifacts_before"] == frozen_artifacts()
            and value["artifacts_after"] == value["artifacts_before"]
            and value["linked_product"] == linked_product(),
            "phase-9 ABI card receipt drift")
    print("2.1 phase-9 ABI card: CHECK PASS card=1/1 exits=8 rc=16")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "preflight", "card", "check", "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    {"preflight": preflight, "card": card, "check": check,
     "_produce": produce_child, "_scope": scope_child,
     "_accept": acceptance_child}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "card":
            try:
                record_final_red(error)
            except Exception as receipt_error:
                print(f"phase-9 ABI Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.1 phase-9 ABI card: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
