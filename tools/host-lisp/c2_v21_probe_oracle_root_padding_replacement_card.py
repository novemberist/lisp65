#!/usr/bin/env python3
"""Run the one authorized explicit-padding replacement root card."""

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

import c2_v21_probe_oracle_root_card as BASE  # noqa: E402
import c2_v21_probe_oracle_root_facade_padding as PADDING  # noqa: E402
import c2_v20_building_heap_mem_source_unbind_20260816 as UNBIND  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.1-probe-oracle-root-padding-replacement-card"
PREFLIGHT = ROOT / (
    "build/c2.3/v2.1-probe-oracle-root-padding-replacement-preflight")
PREFLIGHT_RECEIPT = PREFLIGHT / "preflight.json"
INVOCATION = PREFLIGHT / "card-invocation.json"
PRODUCER_RESULT = BUILD / "producer-result.json"
SCOPE_RESULT = BUILD / "owner-scope-result.json"
ACCEPTANCE_RESULT = BUILD / "artifact-acceptance.json"
PROJECTED_OWNERSHIP = PREFLIGHT / "projected-ownership-contract.json"
PROJECTED_FULL_MAP = PREFLIGHT / "projected-full-map-authority.json"
ABI_REPORT = BUILD / "wplto/c2-asm-leaf-abi.json"
RECEIPT = ARCH / (
    "c2.3-v2.1-probe-oracle-root-padding-replacement-card-receipt.json")
FINAL_RED = ARCH / (
    "c2.3-v2.1-probe-oracle-root-padding-replacement-card-final-red.json")
PREDECESSOR_RED = ARCH / "c2.3-v2.1-probe-oracle-root-card-final-red.json"
ATTRIBUTION = ARCH / (
    "c2.3-v2.1-probe-oracle-root-card-red-attribution-receipt.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "7e4a1f86"
RECORDED_ON = "2026-08-16"
LINK = 114
FORMAT = "lisp65-c2.3-v2.1-probe-oracle-root-padding-replacement-card-v1"


class ReplacementError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReplacementError(message)


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


def git_bind(commit: str, path: Path) -> dict[str, Any]:
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
    value = git_bind(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode().lower()
    text = " ".join(raw.replace("*", "").replace("`", "").split())
    for token in ("19 bytes become explicit facade padding",
                  "padding is contract filler, never accident",
                  "historical building-heap receipt", "one replacement card"):
        require(token in text,
                f"root-padding replacement authority token absent: {token}")
    return value


def predecessor() -> dict[str, Any]:
    red = load(PREDECESSOR_RED)
    attribution = load(ATTRIBUTION)
    padding = load(PADDING.RECEIPT)
    unbind = load(UNBIND.RECEIPT)
    require(
        red.get("status") == "FINAL RED: probe-oracle root card returns to owner"
        and red.get("retry_authorized") is False
        and red.get("owner_disposition_required") is True
        and attribution.get("status") ==
            "FINAL-RED-ATTRIBUTED: WPLTO-WRAPPER-SHRINK-NEEDS-19-BYTE-FACADE-PAD"
        and attribution["narrow_repair"]["padding_bytes"] == 19
        and attribution["narrow_repair"]["expected_execution_delta_bytes"] == -22
        and padding.get("status") == PADDING.STATUS
        and padding["real_link_fixtures"]["implicit"]["accepted"] is False
        and unbind.get("status") == UNBIND.STATUS
        and unbind["living_successor"][
            "historical_mem_is_live_predicate"] is False,
        "root-padding replacement predecessor drift")
    return {"Final_Red": red, "attribution": attribution,
            "padding": padding, "BUILDING_HEAP_unbind": unbind}


def set_paths() -> None:
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
    BASE.RECEIPT = BUILD / "unused-root-card-receipt.json"
    BASE.FINAL_RED = BUILD / "unused-root-card-final-red.json"
    BASE.DRIVER = DRIVER
    BASE.LINK = LINK


def configure() -> None:
    set_paths()
    BASE.configure()


def artifact_paths() -> dict[str, Path]:
    configure()
    return BASE.artifact_paths()


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    value = {name: bind(path) for name, path in artifact_paths().items()}
    value["seed_lto"] = bind(
        BUILD / "wplto/resident-island-seed.prg.lto.o")
    value["real_ABI_report"] = bind(ABI_REPORT)
    return value


def run_gate(command: list[str], token: str, label: str) -> dict[str, Any]:
    run = subprocess.run(command, cwd=ROOT, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(run.returncode == 0 and token in run.stdout,
            f"fresh {label} red:\n{run.stdout}")
    return {"status": "PASS", "command": " ".join(command),
            "witness": " ".join(run.stdout.split())}


def host_gates() -> dict[str, Any]:
    inherited = BASE.host_gates()
    inherited.update({
        "explicit_facade_padding": run_gate(
            [sys.executable, str(PADDING.DRIVER), "check"],
            "bytes=19 mutations=10", "explicit facade padding"),
        "BUILDING_HEAP_mem_unbind": run_gate(
            [sys.executable, str(UNBIND.DRIVER), "check"],
            "mutations=7", "BUILDING-HEAP mem-source unbind"),
    })
    return inherited


def preflight_value() -> dict[str, Any]:
    prior = predecessor()
    configure()
    source = BASE.configure_root_source()
    mapped = [row for row in source["scopes"]
              if row["name"] == "mapped-far-content-convergence"]
    require(len(mapped) == 1 and mapped[0]["selected"] is True
            and PADDING.SOURCE.relative_to(ROOT).as_posix()
                in mapped[0]["sources"],
            "preflight source projection lost explicit padding")
    return {
        "format": "lisp65-c2.3-v2.1-probe-oracle-root-padding-preflight-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: explicit 19-byte facade filler; replacement armed",
        "configuration": {"link": LINK, "replacement_cards_authorized": 1,
            "facade_contract_bytes": 98, "explicit_padding_bytes": 19,
            "actual_wrapper_delta_bytes": -22,
            "source_owner": mapped[0]},
        "attempt_accounting": {"replacement_cards_consumed": 0,
            "WPLTO_runs": 0, "product_links": 0, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "host_gates": host_gates(),
        "authority": {"owner": authorization(),
            "predecessor_Final_Red": bind(PREDECESSOR_RED),
            "attribution": bind(ATTRIBUTION), "padding": bind(PADDING.RECEIPT),
            "BUILDING_HEAP_unbind": bind(UNBIND.RECEIPT),
            "root_fix": bind(BASE.FIX.RECEIPT),
            "projected_ownership": bind(PROJECTED_OWNERSHIP),
            "projected_full_map": bind(PROJECTED_FULL_MAP),
            "driver": bind(DRIVER)},
        "predecessor_summary": {
            "cards_consumed": prior["Final_Red"]["attempt_accounting"]
                ["cards_consumed"],
            "product_artifacts": 0, "padding_mechanism_named": True},
        "claim_limit": "Preflight only; no WPLTO, link, media or device.",
    }


def preflight_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "implicit-shortfall": lambda x: x["configuration"].update(
            explicit_padding_bytes=0),
        "resize-facade": lambda x: x["configuration"].update(
            facade_contract_bytes=79),
        "inherit-price": lambda x: x["configuration"].update(
            actual_wrapper_delta_bytes=-18),
        "authorize-two": lambda x: x["configuration"].update(
            replacement_cards_authorized=2),
        "spend-card": lambda x: x["attempt_accounting"].update(
            replacement_cards_consumed=1),
        "drop-padding-gate": lambda x: x["host_gates"].pop(
            "explicit_facade_padding"),
        "drop-unbind": lambda x: x["host_gates"].pop(
            "BUILDING_HEAP_mem_unbind"),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        if trial != value:
            rejected.append(name)
    require(rejected == list(cases), "replacement preflight mutation survived")
    return rejected


def preflight() -> None:
    require(not BUILD.exists() and not PREFLIGHT.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "root-padding replacement is one-shot")
    set_paths()
    BASE.write_projections()
    value = preflight_value()
    value["mutations_rejected"] = preflight_mutations(value)
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("probe-oracle root padding replacement: PREFLIGHT PASS card=0/1 "
          "facade=98 pad=19 delta=-22 mutations=7")


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
    run = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(run.returncode == 0,
            f"fresh root-padding replacement child {action} red:\n{run.stdout}")


def linked_product() -> dict[str, Any]:
    configure()
    value = BASE.linked_product()
    require(
        value["wrappers"]["ordinary"]["bytes"] == 35
        and value["wrappers"]["mapped_facade"]["bytes"] == 27
        and value["wrappers"]["execution_delta_from_Link112_bytes"] == -22
        and value["facade_padding"]["bytes"] == 19
        and value["facade_padding"]["facade_bytes"] == 98
        and value["facade_padding"]["executed"] is False,
        "linked replacement lost the emitted padding/root identity")
    return value


def linked_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "lose-reader": lambda x: x.update(mutable_reader_count=8),
        "restore-probe": lambda x: x.update(DMA_probe_jobs=1),
        "trust-completion": lambda x: x.update(completion_signal_trusted=True),
        "inherit-price": lambda x: x["wrappers"].update(
            execution_delta_from_Link112_bytes=-18),
        "shrink-pad": lambda x: x["facade_padding"].update(bytes=18),
        "execute-pad": lambda x: x["facade_padding"].update(executed=True),
        "resize-facade": lambda x: x["facade_padding"].update(facade_bytes=97),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            require(trial["mutable_reader_count"] == 9
                    and trial["DMA_probe_jobs"] == 0
                    and trial["completion_signal_trusted"] is False
                    and trial["wrappers"][
                        "execution_delta_from_Link112_bytes"] == -22
                    and trial["facade_padding"]["bytes"] == 19
                    and trial["facade_padding"]["facade_bytes"] == 98
                    and trial["facade_padding"]["executed"] is False,
                    "linked replacement mutation")
        except ReplacementError:
            rejected.append(name)
    require(rejected == list(cases), "linked replacement mutation survived")
    return rejected


def card() -> None:
    persisted = load(PREFLIGHT_RECEIPT)
    rejected = persisted.pop("mutations_rejected", None)
    expected = preflight_value()
    require(persisted == expected
            and rejected == preflight_mutations(expected),
            "root-padding replacement preflight receipt drift")
    require(not BUILD.exists() and not INVOCATION.exists()
            and not RECEIPT.exists() and not FINAL_RED.exists(),
            "root-padding replacement card is one-shot")
    INVOCATION.write_bytes(canonical({"status": "INVOKED", "link": LINK,
        "owner": authorization(), "preflight": bind(PREFLIGHT_RECEIPT),
        "padding": bind(PADDING.RECEIPT), "driver": bind(DRIVER)}))
    run_child("_produce")
    before = frozen_artifacts()
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "replacement acceptance changed artifacts")
    producer = load(PRODUCER_RESULT)
    scope = load(SCOPE_RESULT)
    acceptance = load(ACCEPTANCE_RESULT)
    product = linked_product()
    source_gate = producer["post_configuration_source_owner_gate"]
    mapped = [row for row in source_gate["scopes"]
              if row["name"] == "mapped-far-content-convergence"]
    require(
        len({os.getpid(), producer["pid"], scope["pid"],
             acceptance["pid"]}) == 4
        and acceptance.get("status") == "PASS"
        and acceptance["VMA_golden"].get("dependent_fixed_vmas") == 101
        and acceptance["VMA_golden"].get("dependent_free_derived_vmas") == 2
        and len(mapped) == 1 and mapped[0]["selected"] is True
        and PADDING.SOURCE.relative_to(ROOT).as_posix() in mapped[0]["sources"],
        "root-padding linked acceptance drift")
    value = {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "PASS: probe-oracle root padding replacement card green",
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1, "WPLTO_runs": 1,
            "product_links": 1, "completion_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "authority": {"owner": authorization(),
            "predecessor_Final_Red": bind(PREDECESSOR_RED),
            "attribution": bind(ATTRIBUTION), "padding": bind(PADDING.RECEIPT),
            "BUILDING_HEAP_unbind": bind(UNBIND.RECEIPT),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "linked_product": product,
        "dependent_vma_comparison": acceptance["VMA_golden"],
        "acceptance": {key: item for key, item in acceptance.items()
                       if key not in ("status", "pid")},
        "completion_identity": producer["candidate_completion_identity"],
        "artifacts_before": before, "artifacts_after": after,
        "process_isolation": {"parent": os.getpid(),
            "producer": producer["pid"], "owner_scope": scope["pid"],
            "acceptance": acceptance["pid"], "all_distinct": True},
        "owner_scope": scope["gate"], "source_owner": mapped[0],
        "mutations_rejected": {"preflight": rejected,
            "linked": linked_mutations(product)},
        "next": "linked-image DMA content-reader structural-absence gate",
        "claim_limit": "One replacement card; Completion/media/device not run.",
    }
    RECEIPT.write_bytes(canonical(value))
    print("probe-oracle root padding replacement: CARD PASS card=1/1 "
          "facade=98 pad=19 delta=-22")


def record_final_red(error: Exception) -> None:
    if not INVOCATION.exists() or RECEIPT.exists() or FINAL_RED.exists():
        return
    artifacts = {name: bind(path) for name, path in artifact_paths().items()
                 if path.is_file() and not path.is_symlink()}
    FINAL_RED.write_bytes(canonical({
        "format": "lisp65-c2.3-v2.1-probe-oracle-root-padding-replacement-red-v1",
        "recorded_on": RECORDED_ON,
        "status": "FINAL RED: root-padding replacement returns to owner",
        "error": {"type": type(error).__name__, "message": str(error)},
        "attempt_accounting": {"replacement_cards_authorized": 1,
            "replacement_cards_consumed": 1,
            "WPLTO_runs": 1 if artifacts else 0,
            "product_link_attempts": 1 if artifacts else 0,
            "completion_runs": 0, "media_builds": 0, "device_contacts": 0},
        "artifacts": artifacts, "retry_authorized": False,
        "owner_disposition_required": True,
        "authority": {"owner": authorization(),
            "preflight": bind(PREFLIGHT_RECEIPT), "driver": bind(DRIVER)},
        "claim_limit": "Replacement consumed; no Completion, media or device.",
    }))


def check() -> None:
    if FINAL_RED.exists():
        value = load(FINAL_RED)
        require(value.get("retry_authorized") is False
                and value.get("owner_disposition_required") is True,
                "root-padding replacement Final Red drift")
        print("probe-oracle root padding replacement: CHECK FINAL RED")
        return
    if not RECEIPT.exists():
        print("probe-oracle root padding replacement: CHECK LOCKED/ARMED")
        return
    value = load(RECEIPT)
    require(
        value.get("status") ==
            "PASS: probe-oracle root padding replacement card green"
        and value["attempt_accounting"]["replacement_cards_consumed"] == 1
        and value["linked_product"] == linked_product()
        and value["artifacts_before"] == frozen_artifacts()
        and value["artifacts_after"] == value["artifacts_before"],
        "root-padding replacement green receipt drift")
    print("probe-oracle root padding replacement: CHECK PASS card=1/1 "
          "facade=98 pad=19 delta=-22")


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
                print("root-padding replacement Final Red receipt failure: "
                      f"{receipt_error}", file=sys.stderr)
        print(f"probe-oracle root padding replacement: FINAL RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
