#!/usr/bin/env python3
"""Run the one owner-authorized product-liveness card."""

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
import c2_v21_dependent_vma_replacement_card as BASE  # noqa: E402
import c2_v21_product_loading_liveness as LIVE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.1-product-loading-liveness-card"
PREFLIGHT = ROOT / "build/c2.3/v2.1-product-loading-liveness-preflight-card"
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
ABI_REPORT = BUILD / "wplto/c2-asm-leaf-real-abi-callers.json"
RECEIPT = ARCH / "c2.3-v2.1-product-loading-liveness-card-receipt.json"
FINAL_RED = ARCH / "c2.3-v2.1-product-loading-liveness-card-final-red.json"
PREDECESSOR = BASE.RECEIPT
LIVENESS = LIVE.RECEIPT
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

AUTHORIZATION = "395a91aa"
RECORDED_ON = "2026-08-15"
LINK = 108
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
    authority = git_binding(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{authority['commit']}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in ("product card authorized", "one product card",
                  "cpu transport", "liveness ordinal", "2 bytes reserve",
                  "wrapper/schema preflight", "green proceeds to"):
        require(token in text, f"product-liveness card authority absent: {token}")
    return authority


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR)
    require(
        value.get("status") == "PASS: sole dependent-VMA replacement card green"
        and value.get("attempt_accounting", {}).get("cards_consumed") == 1
        and value.get("attempt_accounting", {}).get("WPLTO_runs") == 1
        and value.get("transport", {}).get("reader", {}).get("bytes") == 166
        and value.get("local_return", {}).get("ordinary", {}).get(
            "reserve_bytes") == 24
        and value.get("local_return", {}).get("ownership", {}).get(
            "violations") == [],
        "product-liveness predecessor card drift")
    return value


def liveness_authority() -> dict[str, Any]:
    persisted = load(LIVENESS)
    current = LIVE.derive()
    current["source_mutations"] = LIVE.source_mutations()
    require(persisted == current
            and persisted.get("status") ==
                "HOST-GREEN-PRODUCT-LIVENESS; PRODUCT-CARD-LOCKED"
            and persisted.get("implementation", {}).get("delta_bytes") == 22
            and persisted.get("capacity", {}).get("projected_free_bytes") == 2,
            "product-liveness preflight authority drift")
    return {"receipt": bind(LIVENESS), "delta_bytes": 22,
            "state_bytes": 0, "IRQ_hooks": 0,
            "diagnostic_identity": False, "projected_free_bytes": 2,
            "mutations_rejected": 10}


def configure() -> None:
    BASE.BUILD = BUILD
    BASE.PREFLIGHT = PREFLIGHT
    BASE.PREFLIGHT_RECEIPT = PREFLIGHT_RECEIPT
    BASE.INVOCATION = INVOCATION
    BASE.PRODUCER_RESULT = PRODUCER_RESULT
    BASE.SCOPE_RESULT = SCOPE_RESULT
    BASE.ACCEPTANCE_RESULT = ACCEPTANCE_RESULT
    BASE.ABI_REPORT = ABI_REPORT
    BASE.RECEIPT = BUILD / "unused-dependent-vma-card-receipt.json"
    BASE.FINAL_RED = BUILD / "unused-dependent-vma-card-final-red.json"
    BASE.DRIVER = DRIVER
    BASE.configure()


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
        "format": "lisp65-c2.3-v21-product-loading-liveness-card-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: product-liveness card armed after real preflight",
        "configuration": {"link": LINK, "cards_authorized": 1,
                          "candidate_delta_bytes": 22},
        "attempt_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "host_gates": {**BASE.desk_guard_park(),
                       "product_liveness": liveness_authority()},
        "authority": {"owner": authorization(), "predecessor": bind(PREDECESSOR),
                      "liveness": bind(LIVENESS), "driver": bind(DRIVER)},
        "claim_limit": "Preflight only; no WPLTO, link, Completion, media or device.",
    }


def validate_preflight(
        value: dict[str, Any], expected: dict[str, Any] | None = None) -> None:
    require(value == (preflight_value() if expected is None else expected),
            "product-liveness card preflight drift")


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "authorize-two-cards": lambda x: x["configuration"].update(
            cards_authorized=2),
        "drop-real-schema": lambda x: x["host_gates"].pop(
            "wrapper_and_real_schema"),
        "drop-golden-check": lambda x: x["host_gates"].pop(
            "dependent_vma_check"),
        "invent-state": lambda x: x["host_gates"]["product_liveness"].update(
            state_bytes=1),
        "spend-margin": lambda x: x["host_gates"]["product_liveness"].update(
            projected_free_bytes=24),
        "spend-card": lambda x: x["attempt_accounting"].update(cards_consumed=1),
        "authorize-device": lambda x: x["attempt_accounting"].update(
            device_contacts=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate_preflight(candidate, value)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "product-liveness preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "product-liveness preflight/card is one-shot")
    value = preflight_value()
    validate_preflight(value, value)
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT.mkdir(parents=True)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("2.1 product liveness: PREFLIGHT PASS delta=22 card=0/1")


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
            f"fresh product-liveness child {action} red:\n{result.stdout}")


def linked_liveness() -> dict[str, Any]:
    elf = artifact_paths()["elf"]
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    reader = truth.symbol("c2_map_cpu_read")
    runtime = truth.symbol("__lisp65_c2_fixed_bank0_runtime")
    text = truth.section(reader.section)
    raw = truth.section_bytes(reader.section)
    body = raw[reader.value - text.address:
               reader.value - text.address + reader.bytes]
    progress = body[12:34]
    require(
        reader.value == 0x2277 and reader.bytes == 188
        and reader.value + reader.bytes == 0x2333
        and runtime.value == 0xC084
        and progress == EXPECTED_PROGRESS
        and text.address + text.bytes == 0xB3AE,
        "actual linked ELF does not contain exact product-liveness delta")
    return {"status": "PASS: packed ELF carries ordinary-product phase ordinal",
            "reader": {"address": "0x2277", "bytes": 188,
                       "end_exclusive": "0x2333"},
            "runtime_base": "0xc084", "phase_address": "0xc0ae",
            "progress_bytes": progress.hex(), "progress_offset": 12,
            "screen_address": "0x0b3a", "text_end_exclusive": "0xb3ae",
            "mapped_far_facade": "0xb3b0", "free_bytes": 2}


def linked_mutations(value: dict[str, Any]) -> list[str]:
    def validate(candidate: dict[str, Any]) -> None:
        require(candidate == value, "linked product-liveness identity changed")
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "shrink-reader": lambda x: x["reader"].update(bytes=166),
        "pin-old-text-end": lambda x: x.update(text_end_exclusive="0xb398"),
        "move-screen": lambda x: x.update(screen_address="0x0b8a"),
        "invent-reserve": lambda x: x.update(free_bytes=24),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            validate(candidate)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "linked liveness mutation survived")
    return rejected


def card() -> None:
    persisted = load(PREFLIGHT_RECEIPT)
    rejected = persisted.pop("mutations_rejected", None)
    expected = preflight_value()
    validate_preflight(persisted, expected)
    require(rejected == preflight_mutations(expected),
            "product-liveness preflight mutation receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "product-liveness card is one-shot")
    INVOCATION.write_bytes(canonical({
        "status": "INVOKED", "link": LINK, "owner": authorization(),
        "predecessor": bind(PREDECESSOR), "liveness": bind(LIVENESS),
        "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "product-liveness acceptance changed artifacts")
    producer = load(PRODUCER_RESULT)
    scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    liveness = linked_liveness()
    local = producer["v21_text_recovery"]
    transport = producer["v21_linked_transport"]
    comparison = acceptance["VMA_golden"]
    require(
        len({os.getpid(), producer["pid"], scope["pid"], acceptance["pid"]}) == 4
        and acceptance.get("status") == "PASS"
        and comparison.get("dependent_fixed_vmas") == 101
        and comparison.get("dependent_free_derived_vmas") == 2
        and transport.get("reader", {}).get("bytes") == 188
        and transport.get("reader", {}).get("end_exclusive") == "0x2333"
        and local.get("ordinary", {}).get("reserve_bytes") == 2
        and local.get("selector", {}).get("address") == "0x2333"
        and local.get("ownership", {}).get("violations") == [],
        "product-liveness linked acceptance drift")
    receipt = {
        "format": "lisp65-c2.3-v21-product-loading-liveness-card-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: sole product-liveness card green",
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1, "product_links": 1, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "authority": {"owner": authorization(), "predecessor": bind(PREDECESSOR),
            "liveness": bind(LIVENESS), "preflight": bind(PREFLIGHT_RECEIPT),
            "driver": bind(DRIVER)},
        "linked_liveness": liveness, "transport": transport,
        "local_return": local, "dependent_vma_comparison": comparison,
        "completion_identity": producer["candidate_completion_identity"],
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {"parent": os.getpid(), "producer": producer["pid"],
            "owner_scope": scope["pid"], "acceptance": acceptance["pid"],
            "all_distinct": True},
        "owner_scope": scope["gate"],
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "mutations_rejected": {"preflight": rejected,
            "linked_liveness": linked_mutations(liveness)},
        "next": "Completion, same-world media closure and D1",
        "claim_limit": "One card only; Completion, media and device have not run.",
    }
    RECEIPT.write_bytes(canonical(receipt))
    print("2.1 product liveness: PASS card=1/1 reader=188 reserve=2 ownership=0")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v21-product-loading-liveness-final-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: product-liveness card returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"cards_authorized": 1, "cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"owner": authorization(), "predecessor": bind(PREDECESSOR),
            "liveness": bind(LIVENESS), "preflight": bind(PREFLIGHT_RECEIPT),
            "driver": bind(DRIVER)},
        "claim_limit": "The sole card is consumed; no Completion, media or device.",
    }))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "product-liveness Final Red drift")
        print("2.1 product liveness: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        print("2.1 product liveness: CHECK LOCKED/ARMED")
        return
    value = load(RECEIPT)
    require(
        value.get("status") == "PASS: sole product-liveness card green"
        and value.get("attempt_accounting", {}).get("cards_consumed") == 1
        and value.get("linked_liveness") == linked_liveness()
        and value.get("artifacts_before") == frozen_artifacts()
        and value.get("artifacts_after") == value.get("artifacts_before")
        and value.get("process_isolation", {}).get("all_distinct") is True,
        "product-liveness green receipt drift")
    print("2.1 product liveness: CHECK PASS card=1/1 reader=188 reserve=2")


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
                print(f"product-liveness Final Red receipt failure: {receipt_error}",
                      file=sys.stderr)
        print(f"2.1 product liveness: FINAL RED: {error}", file=sys.stderr)
        raise SystemExit(2)
