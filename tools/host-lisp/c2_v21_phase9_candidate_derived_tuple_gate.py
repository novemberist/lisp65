#!/usr/bin/env python3
"""Candidate-derived MAP-tuple gate for the enlarged far service."""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_v20_map_tuple_fix as FIX  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
ELF = ROOT / (
    "build/c2.3/v2.1-phase9-abi-fix-replacement-card/wplto/"
    "lisp65-c2-substitution-linked.prg.elf")
PREDECESSOR = ARCH / (
    "c2.3-v2.1-phase9-abi-fix-artifact-replay-final-red.json")
RECEIPT = ARCH / (
    "c2.3-v2.1-phase9-candidate-derived-tuple-gate-receipt.json")
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
AUTHORIZATION = "ded37acd"
RECORDED_ON = "2026-08-16"
SECTION = ".lisp65_c2_mapped_far_service"
ARENA_START = 0x78B2
ARENA_END = 0x7E8D


class TupleGateError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise TupleGateError(message)


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
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode()
    text = " ".join(raw.lower().split())
    for token in ("size derivation approved", "emitted candidate",
                  "fixed arena capacity", "reintroduced size pin",
                  "no wplto, no relink, no card consumed"):
        require(token in text, f"candidate-derived tuple authority absent: {token}")
    return authority


def predecessor() -> dict[str, Any]:
    value = load(PREDECESSOR)
    require(value.get("status")
            == "FINAL RED: phase-9 artifact-only replay returns to owner"
            and value.get("retry_authorized") is False
            and value["attribution"]["passed_conjuncts"] == 7
            and value["attribution"]["failed_conjuncts"] == 1
            and value["attribution"]["historical_pinned_bytes"] == 874
            and value["attribution"]["candidate_far_bytes"] == 1086,
            "artifact replay Final Red predecessor drift")
    return value


def linked_tuple_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    enter = truth.symbol("c2_mapped_far_enter")
    section = truth.section(enter.section)
    raw = truth.section_bytes(enter.section)
    body = raw[enter.value - section.address:
               enter.value - section.address + enter.bytes]
    expected = bytes.fromhex("48da5aa940a282a000a3805ceaa3007afa6860")
    decoded = FIX.decode_low(0x40, 0x82)
    service = truth.symbol("c2_mapped_far_vm_code_load_converged")
    far = truth.section(SECTION)
    far_raw = truth.section_bytes(far.name)
    first_store = far_raw[0x32:0x37]
    candidate_end = far.address + far.bytes
    require(
        body == expected and enter.bytes == 19
        and service.value == 0x79DC
        and FIX.map_low(service.value, decoded) == 0x2B9DC
        and FIX.map_low(0x3185, decoded) == 0x3185
        and far.address == ARENA_START and far.bytes > 0
        and candidate_end <= ARENA_END
        and first_store == bytes.fromhex("a9048d00c0"),
        "linked candidate-derived MAP tuple or arena invariant drift")
    return {
        "status": "passed-primary-semantics-candidate-derived-tuple",
        "symbol": "c2_mapped_far_enter", "VMA": f"0x{enter.value:04X}",
        "bytes": body.hex(),
        "tuple": {"A": "0x40", "X": "0x82", "Y": "0x00", "Z": "0x80"},
        "decode": decoded, "service_entry_physical": "0x02B9DC",
        "block1_unchanged": True,
        "far_service": {"section": SECTION, "start": far.address,
            "candidate_derived_bytes": far.bytes,
            "candidate_derived_end_exclusive": candidate_end,
            "arena_end_exclusive": ARENA_END,
            "arena_capacity_bytes": ARENA_END - ARENA_START,
            "candidate_headroom_bytes": ARENA_END - candidate_end,
            "size_source": "emitted-candidate-section-table",
            "fixed_size_expectation": False},
        "first_descriptor_store": {"physical_PC": "0x02B8E4",
            "bytes": first_store.hex(), "effect": "STA $C000 <= $04"},
    }


def far_payload_gate(elf: Path) -> dict[str, Any]:
    truth = ElfTruth.read(elf, llvm_readobj=READOBJ, include_section_data=True)
    section = truth.section(SECTION)
    raw = truth.section_bytes(SECTION)
    start = truth.symbol("__lisp65_c2_mapped_far_service_load_start").value
    end = truth.symbol("__lisp65_c2_mapped_far_service_load_end").value
    candidate_end = section.address + section.bytes
    require(section.address == ARENA_START and section.bytes > 0
            and candidate_end <= ARENA_END
            and section.bytes == len(raw) == end - start,
            "linked candidate-derived far-payload extent/identity drift")
    return {"status": "passed-candidate-derived-far-payload-extent-identity",
        "section": SECTION, "VMA": f"0x{section.address:04x}",
        "LMA_start": f"0x{start:08x}", "LMA_end_exclusive": f"0x{end:08x}",
        "candidate_derived_bytes": len(raw),
        "candidate_derived_cpu_end_exclusive": candidate_end,
        "arena_capacity_bytes": ARENA_END - ARENA_START,
        "candidate_headroom_bytes": ARENA_END - candidate_end,
        "fixed_size_expectation": False,
        "size_source": "emitted-candidate-section-and-symbol-extents",
        "sha256": hashlib.sha256(raw).hexdigest()}


def validate_far_payload(value: dict[str, Any], elf: Path) -> None:
    require(value == far_payload_gate(elf)
            and value["fixed_size_expectation"] is False,
            "candidate-derived far-payload evidence drift")


def far_payload_mutations(value: dict[str, Any], elf: Path) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "restore-874-size-pin": lambda x: x.update(
            candidate_derived_bytes=874, fixed_size_expectation=True),
        "break-load-extent": lambda x: x.update(LMA_end_exclusive="0x0002bc1c"),
        "hide-headroom": lambda x: x.update(candidate_headroom_bytes=0),
        "move-arena-wall": lambda x: x.update(arena_capacity_bytes=1086),
        "dim-payload-identity": lambda x: x.update(sha256="0" * 64),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_far_payload(trial, elf)
        except TupleGateError:
            rejected.append(name)
    require(rejected == list(cases), "candidate-derived payload mutation survived")
    return rejected


def validate_linked_tuple(value: dict[str, Any], elf: Path) -> None:
    expected = linked_tuple_gate(elf)
    require(value == expected
            and value["tuple"] == {
                "A": "0x40", "X": "0x82", "Y": "0x00", "Z": "0x80"}
            and value["decode"]["mapped_low_half_blocks"] == [3]
            and value["decode"]["physical_offset"] == "0x24000"
            and value["far_service"]["fixed_size_expectation"] is False,
            "candidate-derived linked tuple evidence drift")


def linked_mutations(value: dict[str, Any], elf: Path) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "old-A": lambda x: x["tuple"].update(A="0x80"),
        "old-X": lambda x: x["tuple"].update(X="0x24"),
        "wrong-offset": lambda x: x["decode"].update(physical_offset="0x48000"),
        "wrong-block": lambda x: x["decode"].update(mapped_low_half_blocks=[1]),
        "wrong-entry": lambda x: x.update(service_entry_physical="0x079DC"),
        "mapped-block1": lambda x: x.update(block1_unchanged=False),
        "skip-descriptor-store": lambda x: x["first_descriptor_store"].update(
            bytes="0000000000"),
        "restore-874-size-pin": lambda x: x["far_service"].update(
            candidate_derived_bytes=874, fixed_size_expectation=True),
        "move-arena-wall": lambda x: x["far_service"].update(
            arena_end_exclusive=x["far_service"]["candidate_derived_end_exclusive"]),
        "hide-headroom": lambda x: x["far_service"].update(
            candidate_headroom_bytes=0),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate_linked_tuple(trial, elf)
        except TupleGateError:
            rejected.append(name)
    require(rejected == list(cases), "candidate-derived tuple mutation survived")
    return rejected


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = (inspect.getsource(linked_tuple_gate)
              + "\n" + inspect.getsource(far_payload_gate)) \
        if source_override is None else source_override
    tree = ast.parse(source)
    pins: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        operands = [node.left, *node.comparators]
        has_far_bytes = any(
            isinstance(item, ast.Attribute) and item.attr == "bytes"
            and isinstance(item.value, ast.Name)
            and item.value.id in ("far", "section")
            for item in operands)
        if has_far_bytes:
            pins.extend(item.value for item in operands
                        if isinstance(item, ast.Constant)
                        and isinstance(item.value, int) and item.value > 1)
    require(not pins and source.count("candidate_end <= ARENA_END") == 2
            and "far.bytes > 0" in source and "section.bytes > 0" in source,
            "tuple gate contains a pinned size or loses the capacity wall")
    return {"status": "PASS: far size candidate-derived, arena fixed",
            "fixed_size_constants": pins,
            "capacity_wall": {"start": ARENA_START, "end_exclusive": ARENA_END,
                              "bytes": ARENA_END - ARENA_START}}


def source_mutations() -> list[str]:
    source = (inspect.getsource(linked_tuple_gate)
              + "\n" + inspect.getsource(far_payload_gate))
    pinned = source.replace(
        "and far.address == ARENA_START and far.bytes > 0",
        "and far.address == ARENA_START and far.bytes == 874", 1)
    payload_pinned = source.replace(
        "and section.bytes == len(raw) == end - start",
        "and section.bytes == len(raw) == end - start == 874", 1)
    no_wall = source.replace("and candidate_end <= ARENA_END", "and True", 1)
    cases = {"restore-874-source-pin": pinned,
             "restore-874-payload-pin": payload_pinned,
             "remove-capacity-wall": no_wall}
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            source_gate(candidate)
        except TupleGateError:
            rejected.append(name)
    require(rejected == list(cases), "tuple source mutation survived")
    return rejected


def derive() -> dict[str, Any]:
    predecessor()
    gate = linked_tuple_gate(ELF)
    require(gate["far_service"]["candidate_derived_bytes"] == 1086
            and gate["far_service"]["arena_capacity_bytes"] == 1499
            and gate["far_service"]["candidate_headroom_bytes"] == 413,
            "frozen candidate size/capacity witness drift")
    payload = far_payload_gate(ELF)
    require(payload["candidate_derived_bytes"] == 1086
            and payload["arena_capacity_bytes"] == 1499
            and payload["candidate_headroom_bytes"] == 413,
            "frozen candidate payload/capacity witness drift")
    return {"format": "lisp65-c2.3-v2.1-candidate-derived-tuple-gate-v2",
        "recorded_on": RECORDED_ON,
        "status": "PASS: candidate-derived tuple gate ready for frozen replay",
        "tuple_gate": gate, "far_payload_gate": payload,
        "source_gate": source_gate(),
        "mutations_rejected": {"linked": linked_mutations(gate, ELF),
                               "far_payload": far_payload_mutations(payload, ELF),
                               "source": source_mutations()},
        "execution_witness": {"WPLTO_runs": 0, "product_links": 0,
            "cards_consumed": 0, "completion_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "authority": {"owner": authorization(),
            "predecessor_Final_Red": bind(PREDECESSOR),
            "frozen_ELF": bind(ELF), "driver": bind(DRIVER)},
        "claim_limit": "Verifier successor only; no product artifact is written."}


def record() -> None:
    require(not RECEIPT.exists(), "candidate-derived tuple receipt exists")
    RECEIPT.write_bytes(canonical(derive()))
    print("2.1 candidate-derived tuple/payload: PASS size=1086 capacity=1499 pin=none")


def check() -> None:
    require(load(RECEIPT) == derive(), "candidate-derived tuple receipt drift")
    print("2.1 candidate-derived tuple/payload: CHECK PASS mutations=10+5+3")


def selftest() -> None:
    value = derive()
    require(len(value["mutations_rejected"]["linked"]) == 10
            and len(value["mutations_rejected"]["far_payload"]) == 5
            and len(value["mutations_rejected"]["source"]) == 3,
            "candidate-derived tuple mutation closure drift")
    print("2.1 candidate-derived tuple/payload: SELFTEST PASS mutations=10+5+3")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    {"record": record, "check": check, "selftest": selftest}[
        parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
