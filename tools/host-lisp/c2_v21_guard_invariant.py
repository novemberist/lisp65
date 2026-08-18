#!/usr/bin/env python3
"""Bind the CPU-reader guard to span/window non-overlap before a card."""

from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v21_cpu_transport_card as CPU  # noqa: E402
import c2_v21_wrapper_contract_replacement_red_attribution as ATTR  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
BUILD = ROOT / "build/c2.3/v2.1-wrapper-contract-replacement-card/wplto"
ELF = BUILD / "lisp65-c2-substitution-linked.prg.elf"
MAP = BUILD / "lisp65-c2-substitution-linked.prg.map"
FINAL_RED = ARCH / "c2.3-v2.1-wrapper-contract-replacement-card-final-red.json"
ATTRIBUTION = ATTR.RECEIPT
RECEIPT = ARCH / "c2.3-v2.1-guard-invariant-receipt.json"
DRIVER = Path(__file__).resolve()
CPU_SOURCE = Path(CPU.__file__).resolve()
AUTHORIZATION = "32ce1bc8"
RECORDED_ON = "2026-08-14"
FORMAT = "lisp65-c2.3-v2.1-guard-invariant-v1"


class GuardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GuardError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


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
    for token in ("reader span must not overlap", "$2277", "$5000",
                  "one card"):
        require(token in text, f"guard-invariant authorization absent: {token}")
    return authority


def predecessor() -> dict[str, Any]:
    red = load(FINAL_RED)
    attribution = load(ATTRIBUTION)
    ATTR.validate({key: value for key, value in attribution.items()
                   if key != "mutations_rejected"}, verify=True)
    require(
        red.get("status") ==
            "FINAL RED: wrapper-contract replacement returns to owner"
        and red.get("retry_authorized") is False
        and attribution.get("root_cause", {}).get("class") ==
            "LINKED-GUARD-PINS-READER-TO-WRONG-ADDRESS-DOMAIN"
        and attribution["root_cause"]["reader"]["address"] == "0x2277"
        and attribution["root_cause"]["mapped_window"]["reader_overlaps"] is False,
        "guard-invariant predecessor drift")
    return {"final_red": bind(FINAL_RED), "attribution": bind(ATTRIBUTION)}


def function(source: str, name: str) -> ast.FunctionDef:
    rows = [node for node in ast.walk(ast.parse(source, filename=str(CPU_SOURCE)))
            if isinstance(node, ast.FunctionDef) and node.name == name]
    require(len(rows) == 1, f"unique {name} absent")
    return rows[0]


def source_gate(source: str) -> dict[str, Any]:
    guard = function(source, "linked_transport_gate")
    calls = [node for node in ast.walk(guard)
             if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name)
             and node.func.id == "reader_span_is_disjoint"]
    require(len(calls) == 1, "linked guard does not assert span/window non-overlap")
    require("reader.value >= 0x8000" not in source,
            "linked guard retains high-address proxy")
    helper = function(source, "reader_span_is_disjoint")
    returns = [node for node in ast.walk(helper) if isinstance(node, ast.Return)]
    require(len(returns) == 1, "span/window helper shape drift")
    return {"guard_calls_real_invariant": True, "high_address_proxy_count": 0,
            "window": {"start": "0x4000", "end_exclusive": "0x6000"}}


def controls() -> dict[str, Any]:
    size = 166
    require(CPU.reader_span_is_disjoint(0x2277, size),
            "positive 0x2277 control rejected")
    negative_rejected: list[str] = []
    for name, address, span in (
            ("reader-at-0x5000", 0x5000, size),
            ("reader-straddles-0x4000", 0x3FF0, 0x20)):
        if not CPU.reader_span_is_disjoint(address, span):
            negative_rejected.append(name)
    require(negative_rejected == [
        "reader-at-0x5000", "reader-straddles-0x4000"],
        "guard negative control survived")
    return {"positive_accepted": {"address": "0x2277", "bytes": size},
            "negative_rejected": negative_rejected}


def derive() -> dict[str, Any]:
    source = CPU_SOURCE.read_text(encoding="utf-8")
    linked = CPU.linked_transport_gate(ELF, MAP)
    reader = linked["reader"]
    require(reader["address"] == "0x2277"
            and reader["end_exclusive"] == "0x231d"
            and reader["bytes"] == 166 and reader["section"] == ".text",
        "frozen candidate no longer carries priced reader")
    require(linked["mapped_window"] == "0x4000..0x5fff",
            "frozen candidate MAP window drift")
    return {
        "format": FORMAT, "recorded_on": RECORDED_ON,
        "status": "HOST-GREEN: linked guard asserts reader/window non-overlap",
        "rule": "A guard asserts the invariant it protects, never a proxy.",
        "authority": {"authorization": authorization(), **predecessor(),
                      "frozen_ELF": bind(ELF), "frozen_map": bind(MAP),
                      "CPU_wrapper": bind(CPU_SOURCE), "driver": bind(DRIVER)},
        "source_gate": source_gate(source), "controls": controls(),
        "real_ELF_gate": linked,
        "execution_accounting": {"cards_consumed": 0, "WPLTO_runs": 0,
            "product_links": 0, "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Host-only guard correction; no product card has run.",
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("status") ==
            "HOST-GREEN: linked guard asserts reader/window non-overlap"
        and value.get("rule") ==
            "A guard asserts the invariant it protects, never a proxy."
        and value.get("source_gate", {}).get("high_address_proxy_count") == 0
        and value.get("controls", {}).get("positive_accepted") == {
            "address": "0x2277", "bytes": 166}
        and value.get("controls", {}).get("negative_rejected") == [
            "reader-at-0x5000", "reader-straddles-0x4000"]
        and value.get("real_ELF_gate", {}).get("reader", {}).get("address") ==
            "0x2277"
        and value.get("execution_accounting") == {"cards_consumed": 0,
            "WPLTO_runs": 0, "product_links": 0, "media_builds": 0,
            "device_contacts": 0},
        "guard-invariant receipt weakened")
    if verify:
        require(value == derive(), "guard-invariant authority drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "reject-priced-0x2277": lambda x: x["controls"].update(
            positive_accepted=None),
        "accept-reader-at-0x5000": lambda x: x["controls"].update(
            negative_rejected=["reader-straddles-0x4000"]),
        "restore-high-address-proxy": lambda x: x["source_gate"].update(
            high_address_proxy_count=1),
        "hide-real-ELF-gate": lambda x: x["real_ELF_gate"]["reader"].update(
            address="0x8000"),
        "spend-card": lambda x: x["execution_accounting"].update(
            cards_consumed=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=True)
        except GuardError:
            rejected.append(name)
    source = CPU_SOURCE.read_text(encoding="utf-8")
    proxy = source.replace(
        "reader_span_is_disjoint(reader.value, reader.bytes)",
        "reader.value >= 0x8000", 1)
    try:
        source_gate(proxy)
    except GuardError:
        rejected.append("source-uses-proxy-instead-of-invariant")
    expected = list(cases) + ["source-uses-proxy-instead-of-invariant"]
    require(rejected == expected, "guard-invariant mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "guard-invariant receipt exists")
    value = derive(); validate(value, verify=True)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 guard invariant: PASS reader=2277 window=4000..5fff card=0/1")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == mutations(value), "guard-invariant mutation drift")
    print("2.1 guard invariant: CHECK PASS positive=2277 negative=5000")


def selftest() -> None:
    source_gate(CPU_SOURCE.read_text(encoding="utf-8"))
    result = controls()
    require(result["positive_accepted"]["address"] == "0x2277",
            "guard-invariant selftest drift")
    print("2.1 guard invariant: SELFTEST PASS span/window")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check", "selftest"),
            "usage: c2_v21_guard_invariant.py record|check|selftest")
    {"record": record, "check": check, "selftest": selftest}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GuardError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"2.1 guard invariant: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
