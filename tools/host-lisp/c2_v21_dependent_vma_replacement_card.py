#!/usr/bin/env python3
"""Run the one owner-unlocked card behind the dependent-VMA Golden.

The previous Link-107 replacement produced and linked the intended product,
then correctly stopped when the v3 Golden froze two dependent-free gap VMAs.
This card changes no producer or qualification rule.  It gives those rules a
fresh one-shot domain and replaces only the fixed-address comparison operator
with the once-reviewed v4 dependent-address authority.
"""

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

import c2_v20_map_tuple_fix_card as ACCEPTANCE_OWNER  # noqa: E402
import c2_v21_dependency_invariant_golden as GOLD  # noqa: E402
import c2_v21_dependency_invariant_successor_check as GOLD_CHECK  # noqa: E402
import c2_v21_postlink_schema_replacement_card as BASE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.1-dependent-vma-replacement-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-dependent-vma-replacement-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
ABI_REPORT = BUILD / "wplto/c2-asm-leaf-real-abi-callers.json"
RECEIPT = ARCH / "c2.3-v2.1-dependent-vma-replacement-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-dependent-vma-replacement-card-final-red.json"
PREDECESSOR = BASE.FINAL_RED
REVIEW = GOLD.RECEIPT
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "62c3aef6"
RECORDED_ON = "2026-08-15"
LINK = 107


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
    authority = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{authority['commit']}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in (
            "one-time golden review", "accepted",
            "101 fixed vmas", "gap0`/`gap1",
            "both the v2.0 and v2.1 worlds pass",
            "exactly one card is authorized", "unchanged authorities",
            "wrapper/schema preflight"):
        require(token in text, f"dependent-VMA card authority absent: {token}")
    return authority


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR)
    require(
        value.get("status") ==
            "FINAL RED: post-link schema replacement returns to owner"
        and value.get("retry_authorized") is False
        and value.get("owner_disposition_required") is True
        and value.get("attempt_accounting", {}).get("WPLTO_runs") == 1
        and value.get("attempt_accounting", {}).get("product_link_attempts") == 1
        and "candidate invariant geometry differs from reviewed VMA golden"
            in value.get("error", {}).get("message", ""),
        "dependent-VMA predecessor Final Red drift")
    return value


def review_authority() -> dict[str, Any]:
    value = load(REVIEW)
    require(value == GOLD_CHECK.build_receipt(),
            "dependent-VMA review package is not reproducible")
    require(
        value.get("status") ==
            "PASS: awaiting one-time dependent-VMA Golden review"
        and value.get("card_lock") == {
            "review_accepted": False,
            "card_authorized_by_this_receipt": False,
            "wplto_allowed": False}
        and value["dependent_vma_golden"]["sha256"] ==
            "28190ae2e5c3f02b229a3cea257ef3ca5b98f76ac19b35ef77f1f48dc318f1f3"
        and value["dependent_vma_golden"]["dependent_fixed_vmas"] == 101
        and value["dependent_vma_golden"]["dependent_free_derived_vmas"] == 2
        and value["world_probe"]["shared_fixed_projection"] is True
        and value["world_probe"]["different_valid_derived_projection"] is True
        and value["execution_witness"]["golden_mutations"] == 10
        and value["execution_witness"]["candidate_mutations"] == 7,
        "dependent-VMA review authority drift")
    return {"receipt": bind(REVIEW), "golden": bind(GOLD.GOLDEN),
            "fixed_vmas": 101, "derived_vmas": 2,
            "golden_mutations": 10, "candidate_mutations": 7,
            "later_acceptance": authorization()}


def fresh_gate(name: str, script: str, action: str, token: str) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(HOST / script), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0 and token in result.stdout,
            f"fresh {name} preflight red:\n{result.stdout}")
    return {"status": "PASS", "command": f"{script} {action}",
            "witness": " ".join(result.stdout.split())}


def desk_guard_park() -> dict[str, Any]:
    # Each gate runs in a fresh process.  Importing the historical wrapper
    # chain into one process would recreate the one-shot configuration leak
    # that the process-isolation rule was written to prohibit.
    return {
        "ambient_sweep": fresh_gate(
            "ambient sweep", "c2_v150_qualification_ambient_closure.py",
            "check", "ambient closure check: PASS inputs=26"),
        "pinned_expectation_shape_sweep": fresh_gate(
            "expectation-shape sweep", "c2_v21_expectation_shape_sweep.py",
            "check", "pinned=0"),
        "guard_invariant": fresh_gate(
            "guard invariant", "c2_v21_guard_invariant.py", "check",
            "CHECK PASS positive=2277 negative=5000"),
        "wrapper_and_real_schema": fresh_gate(
            "post-link schema contract", "c2_v21_postlink_schema_contract.py",
            "check", "CHECK PASS unknown=0 actual-output=yes"),
        "dependent_vma_selftest": fresh_gate(
            "dependent-VMA selftest",
            "c2_v21_dependency_invariant_successor_check.py",
            "selftest", "mutations=10+7 card=locked"),
        "dependent_vma_check": fresh_gate(
            "dependent-VMA check",
            "c2_v21_dependency_invariant_successor_check.py",
            "check", "review=pending card=locked"),
    }


def configure() -> None:
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    BASE.INVOCATION = INVOCATION
    BASE.PRODUCER_RESULT = PRODUCER_RESULT
    BASE.SCOPE_RESULT = SCOPE_RESULT
    BASE.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    BASE.ABI_REPORT = ABI_REPORT
    BASE.RECEIPT = BUILD / "unused-postlink-schema-receipt.json"
    BASE.FINAL_RED = BUILD / "unused-postlink-schema-final-red.json"
    BASE.DRIVER = DRIVER
    BASE.configure()
    # This is the sole authority change: every surrounding acceptance gate is
    # inherited verbatim, while the comparison owner consumes reviewed v4.
    ACCEPTANCE_OWNER.INV = GOLD


def artifact_paths() -> dict[str, Path]:
    configure()
    return BASE.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    result = {name: bind(path) for name, path in artifact_paths().items()}
    result["seed_lto"] = bind(BUILD / "wplto/resident-island-seed.prg.lto.o")
    result["real_abi_report"] = bind(ABI_REPORT)
    return result


def preflight_value() -> dict[str, Any]:
    predecessor()
    return {
        "format": "lisp65-c2.3-v21-dependent-vma-replacement-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: reviewed dependent-VMA Golden; one card armed",
        "configuration": {"link": LINK, "cards_authorized": 1,
                          "acceptance_operator": "GOLD.compare_elf(candidate)"},
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "host_gates": desk_guard_park(),
        "authority": {"owner_acceptance": authorization(),
            "review": review_authority(), "predecessor": bind(PREDECESSOR),
            "unchanged_postlink_schema": bind(
                ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.3-v2.1-postlink-schema-contract-receipt.json"),
            "driver": bind(DRIVER)},
        "claim_limit": "Preflight only; no WPLTO, link, Completion, media or device.",
    }


def validate_preflight(
        value: dict[str, Any], expected: dict[str, Any] | None = None) -> None:
    require(value == (preflight_value() if expected is None else expected),
            "dependent-VMA card preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-two-cards": lambda x: x["configuration"].update(
            cards_authorized=2),
        "restore-v3-operator": lambda x: x["configuration"].update(
            acceptance_operator="V3.compare_elf(candidate)"),
        "dim-review": lambda x: x["authority"]["review"].update(
            fixed_vmas=103),
        "skip-real-schema": lambda x: x["host_gates"].pop(
            "wrapper_and_real_schema"),
        "skip-ambient-sweep": lambda x: x["host_gates"].pop(
            "ambient_sweep"),
        "spend-card-in-preflight": lambda x: x["attempt_accounting"].update(
            cards_consumed=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate_preflight(candidate, value)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases),
            "dependent-VMA preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "dependent-VMA preflight/card is one-shot")
    value = preflight_value(); validate_preflight(value, value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.1 dependent-VMA replacement: PREFLIGHT PASS fixed=101 "
          "derived=2 card=0/1")


def produce_child() -> int:
    configure()
    return BASE.produce_child()


def scope_child() -> int:
    configure()
    return BASE.scope_child()


def acceptance_child() -> int:
    configure()
    result = BASE.acceptance_child()
    value = load(ACCEPTANCE_RESULT)
    comparison = value.get("VMA_golden", {})
    require(
        comparison.get("comparison") ==
            "dependent-address-invariants-plus-derived-vmas-exact"
        and comparison.get("allocatable_sections") == 103
        and comparison.get("dependent_fixed_vmas") == 101
        and comparison.get("dependent_free_derived_vmas") == 2
        and comparison.get("fixed_boundary_symbols") == 27,
        "acceptance did not consume dependent-VMA Golden v4")
    value["dependent_vma_authority"] = review_authority()
    ACCEPTANCE_RESULT.write_bytes(canonical(value))
    return result


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh dependent-VMA child {action} red:\n{result.stdout}")


def card() -> None:
    value = load(PREFLIGHT_RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate_preflight(value)
    require(rejected == preflight_mutations(value),
            "dependent-VMA preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "dependent-VMA replacement card is one-shot")
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "link": LINK,
        "owner_acceptance": authorization(), "review": bind(REVIEW),
        "predecessor": bind(PREDECESSOR),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "dependent-VMA acceptance changed artifacts")
    producer = load(PRODUCER_RESULT)
    scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    require(len({os.getpid(), producer["pid"], scope["pid"],
                 acceptance["pid"]}) == 4,
            "dependent-VMA card process isolation drift")
    comparison = acceptance["VMA_golden"]
    require(
        acceptance.get("status") == "PASS"
        and comparison["dependent_fixed_vmas"] == 101
        and comparison["dependent_free_derived_vmas"] == 2
        and producer["v21_linked_transport"]["reader"]["address"] == "0x2277"
        and producer["v21_text_recovery"]["ownership"]["violations"] == [],
        "dependent-VMA linked or acceptance result drift")
    receipt = {
        "format": "lisp65-c2.3-v21-dependent-vma-replacement-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: sole dependent-VMA replacement card green",
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "authority": {"owner_acceptance": authorization(),
            "review": bind(REVIEW), "golden": bind(GOLD.GOLDEN),
            "predecessor": bind(PREDECESSOR),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "dependent_vma_comparison": comparison,
        "transport": producer["v21_linked_transport"],
        "local_return": producer["v21_text_recovery"],
        "completion_identity": producer["candidate_completion_identity"],
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {"parent": os.getpid(),
            "producer": producer["pid"], "owner_scope": scope["pid"],
            "acceptance": acceptance["pid"], "all_distinct": True},
        "owner_scope": scope["gate"],
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "mutations_rejected": {"preflight": rejected,
            "golden": load(REVIEW)["mutations_rejected"]},
        "next": "Completion and same-world media closure, then D1 and D2-D5",
        "claim_limit": "One product card; Completion, media and device have not run.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 dependent-VMA replacement: PASS card=1/1 fixed=101 "
          "derived=2 ownership=0 reserve=24")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v21-dependent-vma-replacement-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: dependent-VMA replacement returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"owner_acceptance": authorization(),
            "review": bind(REVIEW), "golden": bind(GOLD.GOLDEN),
            "predecessor": bind(PREDECESSOR),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "claim_limit": "The sole card is consumed; no Completion, media or device.",
    }))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "dependent-VMA Final Red drift")
        print("2.1 dependent-VMA replacement: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        if PREFLIGHT_RECEIPT.exists():
            value = load(PREFLIGHT_RECEIPT)
            rejected = value.pop("mutations_rejected")
            validate_preflight(value)
            require(rejected == preflight_mutations(value),
                    "dependent-VMA armed preflight drift")
        print("2.1 dependent-VMA replacement: CHECK ARMED")
        return
    value = load(RECEIPT)
    require(
        value.get("status") ==
            "PASS: sole dependent-VMA replacement card green"
        and value["attempt_accounting"]["cards_consumed"] == 1
        and value["dependent_vma_comparison"] ==
            GOLD.compare_elf(artifact_paths()["elf"])
        and value["artifacts_before"] == frozen_artifacts()
        and value["artifacts_after"] == value["artifacts_before"]
        and value["process_isolation"]["all_distinct"] is True,
        "dependent-VMA green receipt drift")
    print("2.1 dependent-VMA replacement: CHECK PASS card=1/1 "
          "fixed=101 derived=2")


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
                print(f"dependent-VMA Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.1 dependent-VMA replacement: FINAL RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
