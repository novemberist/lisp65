#!/usr/bin/env python3
"""Fresh-process artifact-only replay of the corrected MAP-tuple card."""

from __future__ import annotations

import argparse
import ast
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

import c2_v20_map_tuple_fix_card as CARD  # noqa: E402
import c2_v20_map_tuple_fix_replacement_card as REPLACEMENT  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.0-ownership-recharter-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.0-map-tuple-artifact-replay"
SCOPE_RESULT = BUILD / "fresh-owner-scope.json"
ACCEPTANCE_RESULT = BUILD / "fresh-artifact-acceptance.json"
RECEIPT = EVIDENCE / "c2.3-v2.0-map-tuple-artifact-replay-receipt.json"
FINAL_RED = REPLACEMENT.FINAL_RED
CARD_BUILD = REPLACEMENT.BUILD
AUTHORIZATION_COMMIT = "a6b1214a"
RECORDED_ON = "2026-08-13"
DRIVER = Path(__file__).resolve()


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


def git_bind(commit: str, path: Path) -> dict[str, Any]:
    name = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    full = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"], cwd=ROOT, check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    text = " ".join(raw.decode().split()).lower()
    require(
        "fresh-process replay authorized" in text
        and "artifact-only replay" in text
        and "no wplto, no relink" in text
        and "selftest joins the fresh-process isolation rule" in text,
        "artifact-only replay authorization text drift")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authorization() -> dict[str, Any]:
    return git_bind(AUTHORIZATION_COMMIT, PLAN)


def artifact_paths() -> dict[str, Path]:
    base = CARD_BUILD / "wplto"
    return {
        "elf": base / "lisp65-c2-substitution-linked.prg.elf",
        "prg": base / "lisp65-c2-substitution-linked.prg",
        "map": base / "lisp65-c2-substitution-linked.prg.map",
        "lto": base / "lisp65-c2-substitution-linked.prg.lto.o",
        "linker": base / "c2-substitution.ld",
        "resolved_profile": base / "resolved-profile.txt",
        "publish_last": base / "kernal-window-publish-last.json",
        "kernal_window": base / "c2-product-kernal-window.bin",
    }


def frozen_artifacts() -> dict[str, dict[str, Any]]:
    values = {name: bind(path) for name, path in artifact_paths().items()}
    red = load(FINAL_RED)
    require(
        red.get("status") == "FINAL RED: replacement card returns to owner"
        and red.get("retry_authorized") is False
        and all(red["artifacts"][name] == values[name]
                for name in ("elf", "prg", "map")),
        "replacement Final Red or frozen artifact identity drift")
    return values


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8") if source_override is None else source_override
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
    replay = functions.get("replay_action")
    scope = functions.get("scope_child")
    accept = functions.get("acceptance_child")
    require(replay is not None and scope is not None and accept is not None,
            "artifact replay lifecycle entrypoint absent")
    replay_calls = [ast.unparse(node.func) for node in ast.walk(replay)
                    if isinstance(node, ast.Call)]
    scope_calls = [ast.unparse(node.func) for node in ast.walk(scope)
                   if isinstance(node, ast.Call)]
    accept_calls = [ast.unparse(node.func) for node in ast.walk(accept)
                    if isinstance(node, ast.Call)]
    forbidden = {"REPLACEMENT.card", "CARD.card", "CARD.produce_candidate",
                 "REPLACEMENT.produce_candidate", "subprocess.check_call"}
    require(
        replay_calls.count("run_child") == 2
        and "REPLACEMENT.single_implementation_gate" not in replay_calls
        and scope_calls.count("REPLACEMENT.single_implementation_gate") == 1
        and not (set(replay_calls + scope_calls + accept_calls) & forbidden),
        "replay can run owner-scope in-process or re-enter a producer/card")
    return {"status": "PASS: owner-scope selftest is fresh-process isolated",
            "child_processes": 2, "direct_parent_scope_calls": 0,
            "forbidden_calls_absent": sorted(forbidden)}


def source_mutations() -> list[str]:
    source = DRIVER.read_text(encoding="utf-8")
    cases = {
        "scope-in-parent": source.replace(
            '    run_child("_scope")\n',
            "    REPLACEMENT.single_implementation_gate()\n", 1),
        "drop-scope-child": source.replace('    run_child("_scope")\n', "", 1),
        "reenter-card": source.replace(
            "    before = frozen_artifacts()\n",
            "    REPLACEMENT.card()\n    before = frozen_artifacts()\n", 1),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            source_gate(candidate)
        except (ReplayError, SyntaxError):
            rejected.append(name)
    require(rejected == list(cases), "fresh-process replay mutation survived")
    return rejected


def scope_child() -> int:
    require(not SCOPE_RESULT.exists(), "owner-scope child result already exists")
    gate = REPLACEMENT.single_implementation_gate()
    SCOPE_RESULT.write_bytes(canonical({
        "status": "PASS: owner-scope gate green in fresh process",
        "pid": os.getpid(), "gate": gate}))
    return 0


def acceptance_child() -> int:
    require(not ACCEPTANCE_RESULT.exists(), "acceptance child result already exists")
    paths = artifact_paths()
    CARD.PRODUCT.configure_e000_reopening()
    CARD.PRODUCT.configure_full_map_ownership()
    CARD.PRODUCT.configure_low_resident_lma_reset()
    CARD.CRC.BUILD = CARD_BUILD
    comparison = CARD.INV.compare_elf(paths["elf"])
    linker = CARD.PRODUCT.low_resident_lma_reset_gate(
        paths["linker"].read_text(encoding="utf-8"))
    delivery = CARD.CRC.delivered_bytes_gate(paths["elf"], paths["prg"])
    CARD.CRC.validate_delivery(delivery, paths["elf"], paths["prg"])
    delivery_mutations = CARD.CRC.delivery_mutations(
        delivery, paths["elf"], paths["prg"])
    tuple_gate = CARD.linked_tuple_gate(paths["elf"])
    tuple_mutations = CARD.linked_mutations(tuple_gate, paths["elf"])
    ACCEPTANCE_RESULT.write_bytes(canonical({
        "status": "PASS: frozen corrected-tuple artifacts accepted read-only",
        "pid": os.getpid(), "VMA_golden": comparison,
        "low_resident_linker_reset": linker, "delivered_bytes": delivery,
        "delivery_mutations_rejected": delivery_mutations,
        "linked_MAP_tuple": tuple_gate,
        "linked_MAP_mutations_rejected": tuple_mutations,
    }))
    return 0


def run_child(action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(DRIVER), action], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0,
            f"fresh replay child {action} red:\n{result.stdout}")


def replay_action() -> int:
    require(not BUILD.exists() and not RECEIPT.exists(),
            "artifact-only replay is one-shot")
    authorization(); source_gate(); source_mutations()
    before = frozen_artifacts()
    BUILD.mkdir(parents=True)
    run_child("_scope")
    run_child("_accept")
    after = frozen_artifacts()
    require(after == before, "artifact-only replay changed a frozen input")
    scope = load(SCOPE_RESULT); acceptance = load(ACCEPTANCE_RESULT)
    require(
        scope["pid"] != os.getpid() and acceptance["pid"] != os.getpid()
        and scope["pid"] != acceptance["pid"]
        and scope["gate"]["status"]
            == "PASS: one name, one owner, one body per inventory"
        and acceptance["VMA_golden"]["allocatable_sections"] == 103
        and acceptance["VMA_golden"]["fixed_boundary_symbols"] == 27
        and acceptance["delivered_bytes"]["identity_mismatches"] == 0
        and acceptance["delivered_bytes"]["publish_last"]["values_correct"] is True
        and acceptance["linked_MAP_tuple"]["tuple"]
            == {"A": "0x40", "X": "0x82", "Y": "0x00", "Z": "0x80"},
        "fresh-process artifact acceptance drift")
    value = {
        "format": "lisp65-c2.3-v20-map-tuple-artifact-replay-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: fresh-process artifact-only replay green",
        "authority": {"owner_authorization": authorization(),
            "replacement_final_red": bind(FINAL_RED), "driver": bind(DRIVER)},
        "immutable_before": before, "immutable_after": after,
        "process_isolation": {"parent_pid": os.getpid(),
            "owner_scope_child_pid": scope["pid"],
            "acceptance_child_pid": acceptance["pid"],
            "all_distinct": True, "owner_scope": scope["gate"]},
        "acceptance": {key: value for key, value in acceptance.items()
                       if key not in ("status", "pid")},
        "source_gate": source_gate(),
        "source_mutations_rejected": source_mutations(),
        "execution_accounting": {"artifact_replays_authorized": 1,
            "artifact_replays_consumed": 1, "WPLTO_runs": 0,
            "compiler_runs": 0, "linker_runs": 0,
            "artifact_completions": 0, "media_builds": 0,
            "device_contacts": 0},
        "next_gate": "artifact completion, current-world media, then fresh D1",
        "claim_limit": (
            "Fresh-process read-only acceptance of frozen artifacts only. "
            "Completion, media, device, D1 and D2-D5 have not run."),
    }
    RECEIPT.write_bytes(canonical(value))
    print("2.0 MAP-tuple artifact replay: PASS processes=2 "
          "sections=103 boundaries=27 WPLTO=0 linker=0")
    return 0


def validate(value: dict[str, Any]) -> None:
    require(
        value.get("status") == "PASS: fresh-process artifact-only replay green"
        and value.get("immutable_before") == frozen_artifacts()
        and value.get("immutable_after") == value["immutable_before"]
        and value.get("process_isolation", {}).get("all_distinct") is True
        and value.get("acceptance", {}).get("VMA_golden", {}).get(
            "allocatable_sections") == 103
        and value["acceptance"]["delivered_bytes"]["identity_mismatches"] == 0
        and value["execution_accounting"] == {
            "artifact_replays_authorized": 1, "artifact_replays_consumed": 1,
            "WPLTO_runs": 0, "compiler_runs": 0, "linker_runs": 0,
            "artifact_completions": 0, "media_builds": 0,
            "device_contacts": 0},
        "artifact-only replay receipt drift")


def receipt_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "claim-WPLTO": lambda x: x["execution_accounting"].update(WPLTO_runs=1),
        "claim-link": lambda x: x["execution_accounting"].update(linker_runs=1),
        "same-process": lambda x: x["process_isolation"].update(all_distinct=False),
        "change-frozen-SHA": lambda x: x["immutable_after"]["elf"].update(
            sha256="0" * 64),
        "hide-delivery-diff": lambda x: x["acceptance"]["delivered_bytes"].update(
            identity_mismatches=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate)
        except ReplayError:
            rejected.append(name)
    require(rejected == list(cases), "artifact replay receipt mutation survived")
    return rejected


def selftest() -> int:
    authorization(); frozen_artifacts(); source_gate()
    require(len(source_mutations()) == 3, "replay source mutation count drift")
    print("2.0 MAP-tuple artifact replay: SELFTEST PASS source=3 frozen=8")
    return 0


def check() -> int:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value)
    require(rejected == receipt_mutations(value),
            "artifact replay mutation receipt drift")
    print("2.0 MAP-tuple artifact replay: CHECK PASS processes=fresh bytes=frozen")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "replay", "check",
                                           "_scope", "_accept"))
    action = parser.parse_args().action
    if action == "replay":
        result = replay_action()
        value = load(RECEIPT); value["mutations_rejected"] = receipt_mutations(value)
        RECEIPT.write_bytes(canonical(value))
        return result
    return {"selftest": selftest, "check": check,
            "_scope": scope_child, "_accept": acceptance_child}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"2.0 MAP-tuple artifact replay: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
