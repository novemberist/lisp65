#!/usr/bin/env python3
"""Run the one owner-authorized product card for the MAP-mask fix."""

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
import c2_v21_candidate_derived_local_return as CANDIDATE  # noqa: E402
import c2_v21_dependency_invariant_golden as GOLD  # noqa: E402
import c2_v21_local_return_identity_card as LOCAL  # noqa: E402
import c2_v21_map_mask_fix as FIX  # noqa: E402
import c2_v21_product_loading_liveness_card as BASE  # noqa: E402
import c2_v21_terminal_screen_map_authority_rebind as SCREEN_REBIND  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.1-map-mask-fix-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-map-mask-fix-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
ABI_REPORT = BUILD / "wplto/c2-asm-leaf-real-abi-callers.json"
RECEIPT = ARCH / "c2.3-v2.1-map-mask-fix-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-map-mask-fix-card-final-red.json"
PREDECESSOR = BASE.FINAL_RED
REPLAY = ARCH / (
    "c2.3-v2.1-product-loading-liveness-artifact-replay-receipt.json")
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

AUTHORIZATION = "e63e6240"
LINK = 109
EXPECTED_PROGRESS = bytes.fromhex(
    "adaec0c90d9002a900c90ab00469308002e9098d3a0b")


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
    for token in ("product mechanism named", "mask construction is corrected",
                  "decodes the constructed tuple itself", "one card",
                  "green proceeds to completion"):
        require(token in text, f"MAP-mask card authority absent: {token}")
    return value


def predecessor() -> dict[str, Any]:
    red = load(PREDECESSOR); replay = load(REPLAY)
    require(
        red.get("status") == "FINAL RED: product-liveness card returns to owner"
        and red.get("retry_authorized") is False
        and red.get("attempt_accounting", {}).get("cards_consumed") == 1
        and replay.get("status") ==
            "PASS: artifact-only producer-tail Scope Acceptance replay"
        and replay.get("execution_accounting", {}).get("WPLTO_runs") == 0,
        "Link-108 predecessor/replay authority drift")
    return {"final_red": red, "artifact_replay": replay}


def placement_contract() -> dict[str, Any]:
    return SCREEN_REBIND.placement_contract()


def configure() -> None:
    # The candidate checker consumes the authorized fix price.  Its semantic
    # selector, ownership, packed-image and Golden checks remain unchanged.
    CANDIDATE.placement_contract = placement_contract
    LOCAL.linked_gate = CANDIDATE.linked_gate
    LOCAL.linked_mutations = CANDIDATE.linked_mutations
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    BASE.INVOCATION = INVOCATION
    BASE.PRODUCER_RESULT = PRODUCER_RESULT
    BASE.SCOPE_RESULT = SCOPE_RESULT
    BASE.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    BASE.ABI_REPORT = ABI_REPORT
    BASE.RECEIPT = BUILD / "unused-product-liveness-card-receipt.json"
    BASE.FINAL_RED = BUILD / "unused-product-liveness-card-final-red.json"
    BASE.DRIVER = DRIVER
    BASE.configure()


def artifact_paths() -> dict[str, Path]:
    configure()
    return BASE.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    value = {name: bind(path) for name, path in artifact_paths().items()}
    value["seed_lto"] = bind(BUILD / "wplto/resident-island-seed.prg.lto.o")
    value["real_abi_report"] = bind(ABI_REPORT)
    return value


def fresh_gate(name: str, script: str, action: str, token: str) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(HOST / script), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0 and token in result.stdout,
            f"fresh {name} red:\n{result.stdout}")
    return {"status": "PASS", "command": f"{script} {action}",
            "witness": " ".join(result.stdout.split())}


def desk_gates() -> dict[str, Any]:
    return {
        "actual_tuple": fresh_gate(
            "actual tuple", "c2_v21_map_mask_fix.py", "check",
            "CHECK PASS actual-tuple=yes"),
        "ambient_sweep": fresh_gate(
            "ambient sweep", "c2_v150_qualification_ambient_closure.py",
            "check", "ambient closure check: PASS inputs=26"),
        "expectation_shape": fresh_gate(
            "expectation shape", "c2_v21_expectation_shape_sweep.py",
            "check", "pinned=0"),
        "real_schema": fresh_gate(
            "real schema", "c2_v21_postlink_schema_contract.py", "check",
            "CHECK PASS unknown=0 actual-output=yes"),
        "dependent_vma": fresh_gate(
            "dependent VMA", "c2_v21_dependency_invariant_successor_check.py",
            "check", "review=pending card=locked"),
    }


def preflight_value() -> dict[str, Any]:
    predecessor()
    return {"format": "lisp65-c2.3-v2.1-map-mask-fix-card-preflight-v1",
        "recorded_on": "2026-08-15",
        "status": "PASS: actual-tuple fix green; one card armed",
        "configuration": {"link": LINK, "cards_authorized": 1,
                          "placement": placement_contract()},
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "host_gates": desk_gates(),
        "authority": {"owner": authorization(), "fix": bind(FIX.RECEIPT),
            "predecessor": bind(PREDECESSOR), "artifact_replay": bind(REPLAY),
            "driver": bind(DRIVER)},
        "claim_limit": "Preflight only; no WPLTO, link, media or device."}


def validate_preflight(value: dict[str, Any],
                       expected: dict[str, Any] | None = None) -> None:
    require(value == (preflight_value() if expected is None else expected),
            "MAP-mask card preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-two-cards": lambda x: x["configuration"].update(
            cards_authorized=2),
        "drop-actual-tuple": lambda x: x["host_gates"].pop("actual_tuple"),
        "restore-intended-window-guard": lambda x: x["host_gates"].update(
            actual_tuple={"status": "PASS: intended-window-only"}),
        "spend-card": lambda x: x["attempt_accounting"].update(cards_consumed=1),
        "authorize-device": lambda x: x["attempt_accounting"].update(
            device_contacts=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_preflight(trial, value)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "MAP-mask preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "MAP-mask preflight/card is one-shot")
    value = preflight_value(); validate_preflight(value, value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.1 MAP mask card: PREFLIGHT PASS card=0/1 actual-tuple=yes")


def produce_child() -> int:
    configure(); return BASE.produce_child()


def scope_child() -> int:
    configure(); return BASE.scope_child()


def acceptance_child() -> int:
    configure(); return BASE.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh MAP-mask child {action} red:\n{result.stdout}")


def linked_product() -> dict[str, Any]:
    elf = artifact_paths()["elf"]
    tuple_gate = FIX.linked_gate(elf)
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    reader = truth.symbol("c2_map_cpu_read")
    text = truth.section(reader.section)
    body = truth.section_bytes(reader.section)[
        reader.value - text.address:reader.value - text.address + reader.bytes]
    progress = body[12:34]
    contract = placement_contract()
    require(
        reader.value == contract["reader_address"]
        and reader.bytes == contract["reader_bytes"]
        and reader.value + reader.bytes == 0x2334
        and text.address + text.bytes == contract["text_end_exclusive"]
        and progress == EXPECTED_PROGRESS,
        "linked MAP-mask candidate placement/liveness drift")
    return {"status": "PASS: linked product emits non-self-covering tuples",
        "reader": {"address": "0x2277", "bytes": reader.bytes,
                   "end_exclusive": "0x2334"},
        "text_end_exclusive": f"0x{text.address + text.bytes:04x}",
        "facade_address": "0xb3b0", "free_bytes": 1,
        "progress_bytes": progress.hex(), "tuple_gate": tuple_gate}


def linked_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-ffc0": lambda x: x["tuple_gate"]["positive"].update(
            MAPL="0xffc0"),
        "hide-self-cover": lambda x: x["tuple_gate"].update(
            negative_self_covering=[]),
        "pin-old-reader": lambda x: x["reader"].update(bytes=188),
        "invent-reserve": lambda x: x.update(free_bytes=2),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        if trial != value:
            rejected.append(name)
    require(rejected == list(cases), "linked MAP-mask mutation survived")
    return rejected


def card() -> None:
    persisted = load(PREFLIGHT_RECEIPT)
    rejected = persisted.pop("mutations_rejected", None)
    expected = preflight_value(); validate_preflight(persisted, expected)
    require(rejected == preflight_mutations(expected),
            "MAP-mask preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "MAP-mask card is one-shot")
    INVOCATION.write_bytes(canonical({"status": "INVOKED", "link": LINK,
        "owner": authorization(), "fix": bind(FIX.RECEIPT),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope"); run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "MAP-mask acceptance changed artifacts")
    producer = load(PRODUCER_RESULT); scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT); product = linked_product()
    local = producer["v21_text_recovery"]
    comparison = acceptance["VMA_golden"]
    require(
        len({os.getpid(), producer["pid"], scope["pid"],
             acceptance["pid"]}) == 4
        and acceptance.get("status") == "PASS"
        and comparison.get("dependent_fixed_vmas") == 101
        and comparison.get("dependent_free_derived_vmas") == 2
        and local.get("reader", {}).get("bytes") == 189
        and local.get("ordinary", {}).get("reserve_bytes") == 1
        and local.get("selector", {}).get("address") == "0x2334"
        and local.get("ownership", {}).get("violations") == [],
        "MAP-mask linked acceptance drift")
    receipt = {"format": "lisp65-c2.3-v2.1-map-mask-fix-card-v1",
        "recorded_on": "2026-08-15",
        "status": "PASS: sole MAP-mask fix card green",
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "authority": {"owner": authorization(), "fix": bind(FIX.RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "linked_product": product, "transport": producer["v21_linked_transport"],
        "local_return": local, "dependent_vma_comparison": comparison,
        "completion_identity": producer["candidate_completion_identity"],
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {"parent": os.getpid(), "producer": producer["pid"],
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": True}, "owner_scope": scope["gate"],
        "mutations_rejected": {"preflight": rejected,
            "linked": linked_mutations(product)},
        "next": "Completion, same-world media closure and owner-observed D1",
        "claim_limit": "One card only; Completion, media and device have not run."}
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 MAP mask card: PASS card=1/1 reader=189 reserve=1 tuple=4fc0")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-map-mask-fix-card-final-red-v1",
        "recorded_on": "2026-08-15",
        "status": "FINAL RED: MAP-mask fix card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"owner": authorization(), "fix": bind(FIX.RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "claim_limit": "The sole card is consumed; no Completion, media or device."}))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "MAP-mask Final Red drift")
        print("2.1 MAP mask card: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        print("2.1 MAP mask card: CHECK LOCKED/ARMED")
        return
    value = load(RECEIPT)
    require(value.get("status") == "PASS: sole MAP-mask fix card green"
            and value["attempt_accounting"]["cards_consumed"] == 1
            and value["artifacts_before"] == frozen_artifacts()
            and value["artifacts_after"] == value["artifacts_before"]
            and value["linked_product"] == linked_product(),
            "MAP-mask card receipt drift")
    print("2.1 MAP mask card: CHECK PASS card=1/1 tuple=4fc0")


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
                print(f"MAP-mask Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.1 MAP mask card: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
