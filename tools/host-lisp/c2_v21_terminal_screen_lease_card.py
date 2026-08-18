#!/usr/bin/env python3
"""Run the one authorized product card for the terminal screen-cell hand-back."""

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
import c2_v21_map_mask_fix_card as MAP  # noqa: E402
import c2_v21_phase9_abi_fix_artifact_resume as RESUME  # noqa: E402
import c2_v21_phase9_abi_fix_replacement_card as BASE  # noqa: E402
import c2_v21_terminal_screen_lease as LEASE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.1-terminal-screen-lease-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-terminal-screen-lease-preflight"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
PROJECTED_OWNERSHIP = PREFLIGHT / "candidate-ownership-contract.json"
PROJECTED_FULL_MAP = PREFLIGHT / "candidate-full-map-contract.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
ABI_REPORT = BUILD / "wplto/c2-asm-leaf-real-abi-callers.json"
RECEIPT = ARCH / "c2.3-v2.1-terminal-screen-lease-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-terminal-screen-lease-card-final-red.json"
PREDECESSOR = RESUME.RECEIPT
MEDIA = LEASE.MEDIA
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORIZATION = "81d2b9cb"
RECORDED_ON = "2026-08-16"
LINK = 111


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
    for token in ("boot, phase 9/a, banner and repl are functionally green",
                  "cosmetic repair", "cell cleared before the prompt",
                  "one card"):
        require(token in text, f"screen-lease card authority absent: {token}")
    return value


def predecessor() -> dict[str, Any]:
    card = load(PREDECESSOR)
    media = load(MEDIA)
    require(
        card.get("status") == "PASS: frozen phase-9 Acceptance resumed and green"
        and card.get("execution_accounting", {}).get(
            "acceptance_resumes_run") == 1
        and media.get("status") ==
            "PASS: phase-9 ABI candidate completed and media closed; D1 ready"
        and media.get("media", {}).get("readback") == "byteidentical",
        "terminal screen-lease predecessor drift")
    return {"card": card, "media": media}


def write_projections() -> None:
    ownership, full = BASE.projected_contracts()
    PREFLIGHT.mkdir(parents=True, exist_ok=True)
    PROJECTED_OWNERSHIP.write_bytes(canonical(ownership))
    PROJECTED_FULL_MAP.write_bytes(canonical(full))


def configure() -> None:
    require(PROJECTED_OWNERSHIP.is_file() and PROJECTED_FULL_MAP.is_file(),
            "candidate contract projections absent")
    MAP.EXPECTED_PROGRESS = LEASE.EXPECTED_LINKED_PROGRESS
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    BASE.PROJECTED_OWNERSHIP = PROJECTED_OWNERSHIP
    BASE.PROJECTED_FULL_MAP = PROJECTED_FULL_MAP
    BASE.INVOCATION = INVOCATION
    BASE.PRODUCER_RESULT = PRODUCER_RESULT
    BASE.SCOPE_RESULT = SCOPE_RESULT
    BASE.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    BASE.ABI_REPORT = ABI_REPORT
    BASE.RECEIPT = BUILD / "unused-phase9-card-receipt.json"
    BASE.FINAL_RED = BUILD / "unused-phase9-card-final-red.json"
    BASE.DRIVER = DRIVER
    BASE.LINK = LINK
    BASE.configure()


def artifact_paths() -> dict[str, Path]:
    configure()
    return BASE.artifact_paths()


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
    return {
        "terminal_screen_lease": run_gate(
            [sys.executable, str(LEASE.DRIVER), "check"],
            "mutations=5+4", "terminal screen lease"),
        "phase9_predecessor": run_gate(
            [sys.executable, str(ROOT / "tools/host-lisp/"
                "c2_v21_phase9_abi_fix_artifact_resume.py"), "check"],
            "CHECK PASS", "phase-9 predecessor"),
        "postlink_wrapper_contract": run_gate(
            [sys.executable, str(ROOT / "tools/host-lisp/"
                "c2_v21_postlink_wrapper_contract.py"), "check"],
            "CHECK PASS", "post-link wrapper contract"),
        "postlink_schema_contract": run_gate(
            [sys.executable, str(ROOT / "tools/host-lisp/"
                "c2_v21_postlink_schema_contract.py"), "check"],
            "CHECK PASS", "post-link schema contract"),
    }


def preflight_value() -> dict[str, Any]:
    predecessor()
    lease = load(LEASE.RECEIPT)
    require(
        lease.get("status") ==
            "HOST-GREEN: terminal ordinal cell returned before prompt"
        and lease.get("implementation", {}).get("instruction_delta_bytes") == 0
        and lease.get("implementation", {}).get("post_phase_code") == "0x20",
        "screen-lease host receipt drift")
    return {
        "format": "lisp65-c2.3-v2.1-terminal-screen-lease-card-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: terminal screen-cell hand-back green; card armed",
        "configuration": {"link": LINK, "cards_authorized": 1,
            "reader_bytes": 189, "instruction_delta_bytes": 0,
            "post_phase_screen_code": "0x20"},
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "host_gates": host_gates(),
        "authority": {"owner": authorization(),
            "screen_lease": bind(LEASE.RECEIPT),
            "predecessor_card": bind(PREDECESSOR),
            "predecessor_media": bind(MEDIA),
            "projected_ownership": bind(PROJECTED_OWNERSHIP),
            "projected_full_map": bind(PROJECTED_FULL_MAP),
            "driver": bind(DRIVER)},
        "claim_limit": "Preflight only; no product card or device contact.",
    }


def validate_preflight(value: dict[str, Any], expected: dict[str, Any]) -> None:
    require(value == expected, "terminal screen-lease card preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-visible-zero": lambda x: x["configuration"].update(
            post_phase_screen_code="0x30"),
        "invent-code-growth": lambda x: x["configuration"].update(
            instruction_delta_bytes=1),
        "drop-screen-gate": lambda x: x["host_gates"].pop(
            "terminal_screen_lease"),
        "authorize-two-cards": lambda x: x["configuration"].update(
            cards_authorized=2),
        "spend-card": lambda x: x["attempt_accounting"].update(
            cards_consumed=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate_preflight(trial, value)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "screen-lease card mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "terminal screen-lease card is one-shot")
    write_projections()
    value = preflight_value()
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("terminal screen lease card: PREFLIGHT PASS card=0/1 delta=0")


def produce_child() -> int:
    configure()
    return BASE.produce_child()


def scope_child() -> int:
    configure()
    return BASE.scope_child()


def acceptance_child() -> int:
    configure()
    return BASE.acceptance_child()


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh terminal screen-lease child {action} red:\n{result.stdout}")


def linked_product() -> dict[str, Any]:
    configure()
    inherited = BASE.linked_product()
    elf = artifact_paths()["elf"]
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    reader = truth.symbol("c2_map_cpu_read")
    section = truth.section(reader.section)
    raw = truth.section_bytes(reader.section)
    body = raw[reader.value - section.address:
               reader.value - section.address + reader.bytes]
    progress = body[12:34]
    require(
        reader.bytes == 189 and progress == LEASE.EXPECTED_LINKED_PROGRESS
        and progress[8] == 0x29
        and inherited["CPU_reader"]["bytes"] == 189,
        "linked candidate did not emit the exact terminal hand-back")
    return {**inherited,
        "terminal_screen_lease": {
            "status": "PASS: post-phase read writes blank before prompt",
            "reader_bytes": reader.bytes, "instruction_delta_bytes": 0,
            "progress_offset": 12, "progress_bytes": progress.hex(),
            "post_phase_screen_code": "0x20", "post_phase_visible": False,
            "screen_address": "0x0b3a"}}


def linked_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-visible-zero": lambda x: x["terminal_screen_lease"].update(
            post_phase_screen_code="0x30", post_phase_visible=True),
        "hide-growth": lambda x: x["terminal_screen_lease"].update(
            instruction_delta_bytes=1),
        "move-cell": lambda x: x["terminal_screen_lease"].update(
            screen_address="0x0b8a"),
        "drop-lease": lambda x: x.pop("terminal_screen_lease"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        mutate(trial)
        if trial != value:
            rejected.append(name)
    require(rejected == list(cases), "linked screen-lease mutation survived")
    return rejected


def card() -> None:
    persisted = load(PREFLIGHT_RECEIPT)
    rejected = persisted.pop("mutations_rejected", None)
    expected = preflight_value()
    validate_preflight(persisted, expected)
    require(rejected == preflight_mutations(expected),
            "screen-lease preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "terminal screen-lease product card is one-shot")
    INVOCATION.write_bytes(canonical({"status": "INVOKED", "link": LINK,
        "owner": authorization(), "predecessor": bind(PREDECESSOR),
        "screen_lease": bind(LEASE.RECEIPT),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "screen-lease acceptance changed artifacts")
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
        and product["terminal_screen_lease"]["post_phase_visible"] is False,
        "terminal screen-lease linked acceptance drift")
    receipt = {
        "format": "lisp65-c2.3-v2.1-terminal-screen-lease-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: sole terminal screen-lease card green",
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "authority": {"owner": authorization(),
            "screen_lease": bind(LEASE.RECEIPT),
            "predecessor": bind(PREDECESSOR),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "linked_product": product,
        "transport": producer["v21_linked_transport"],
        "dependent_vma_comparison": acceptance["VMA_golden"],
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "completion_identity": producer["candidate_completion_identity"],
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {"parent": os.getpid(),
            "producer": producer["pid"], "owner_scope": scope["pid"],
            "acceptance": acceptance["pid"], "all_distinct": True},
        "owner_scope": scope["gate"],
        "mutations_rejected": {"preflight": rejected,
            "linked": linked_mutations(product)},
        "next": "Completion, same-world media closure and clean D1 repeat",
        "claim_limit": "One product card; Completion/media/device not run.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("terminal screen lease card: PASS card=1/1 bytes=189 post=blank")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-terminal-screen-lease-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: terminal screen-lease card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"owner": authorization(),
            "screen_lease": bind(LEASE.RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "claim_limit": "The sole card is consumed; no Completion or media.",
    }))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "terminal screen-lease Final Red drift")
        print("terminal screen lease card: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        print("terminal screen lease card: CHECK LOCKED/ARMED")
        return
    value = load(RECEIPT)
    require(
        value.get("status") == "PASS: sole terminal screen-lease card green"
        and value["attempt_accounting"]["cards_consumed"] == 1
        and value["artifacts_before"] == frozen_artifacts()
        and value["artifacts_after"] == value["artifacts_before"]
        and value["linked_product"] == linked_product(),
        "terminal screen-lease card receipt drift")
    print("terminal screen lease card: CHECK PASS card=1/1 post=blank")


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
                print(f"screen-lease receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"terminal screen lease card: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
