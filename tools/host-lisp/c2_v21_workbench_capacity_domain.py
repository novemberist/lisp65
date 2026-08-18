#!/usr/bin/env python3
"""Bind the F1 Workbench fixture to its named Golden capacity arena."""

from __future__ import annotations

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

import c2_f1_published_value_call_wplto as F1  # noqa: E402
import c2_v21_overlay59_transitive_attribution as OLD  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
PINNED_RED = ARCH / "c2.3-v2.1-pinned-constant-card-final-red.json"
PINNED_ATTRIBUTION = ARCH / (
    "c2.3-v2.1-pinned-constant-card-red-attribution-receipt.json")
OVERLAY_ATTRIBUTION = ARCH / (
    "c2.3-v2.1-overlay59-transitive-attribution-receipt.json")
RECEIPT = ARCH / "c2.3-v2.1-workbench-capacity-domain-receipt.json"
DRIVER = Path(__file__).resolve()
F1_DRIVER = Path(F1.__file__).resolve()
AUTHORIZATION = "b3f6adc2"
RECORDED_ON = "2026-08-14"


class DomainError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise DomainError(message)


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
    for token in ("checker conversion approved", "workbench boot overlay",
                  "named domain", "one card"):
        require(token in text, f"capacity-domain authorization absent: {token}")
    return authority


def historical_authority() -> dict[str, Any]:
    red = load(PINNED_RED)
    pinned = load(PINNED_ATTRIBUTION)
    overlay = load(OVERLAY_ATTRIBUTION)
    require(
        red.get("status") == "FINAL RED: sole pinned-constant card returns to owner"
        and red.get("retry_authorized") is False
        and pinned.get("status") ==
            "ATTRIBUTED FINAL RED: transitive F1 helper pins overlay-size ceiling"
        and pinned["new_final_red"]["historical_ceiling_bytes"] == 1792
        and overlay.get("status") == OLD.STATUS
        and overlay["capacity_answer"]["workbench_boot_domain"] == {
            "capacity_bytes": 2730, "candidate_bytes": 1851,
            "headroom_bytes": 879,
            "policy": "independent-alternate-overlay"},
        "historical capacity attribution drift",
    )
    historical_source = subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{F1_DRIVER.relative_to(ROOT)}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout.decode()
    require("min(1792, static_bytes)" in historical_source,
            "authorized historical F1 pin absent")
    return {"pinned_card_final_red": bind(PINNED_RED),
            "pinned_card_attribution": bind(PINNED_ATTRIBUTION),
            "overlay_attribution": bind(OVERLAY_ATTRIBUTION),
            "historical_F1_source": git_binding(AUTHORIZATION, F1_DRIVER)}


def terminal_replay() -> dict[str, Any]:
    historical = OLD.terminal_consumer_replay()
    capacity = F1.capacity_contract(
        "workbench-boot-overlay", ".lisp65_workbench_overlay")
    scratch = int(historical["actual_workbench_bytes"])
    require(
        historical["downstream_hidden_reds"] == 0
        and historical["predicates"]["scratch_under_misapplied_1792"] is False
        and capacity["bytes"] == 2730
        and 0 < scratch <= capacity["bytes"],
        "correct-domain terminal consumer replay red",
    )
    return {
        "status": "PASS: same terminal consumer green under named Workbench arena",
        "candidate_workbench_bytes": scratch,
        "capacity": capacity,
        "headroom_bytes": capacity["bytes"] - scratch,
        "six_record_and_CRC_checks": "passed-unchanged",
        "downstream_hidden_reds": historical["downstream_hidden_reds"],
        "historical_cross_domain_predicate_was_only_red": True,
    }


def derive() -> dict[str, Any]:
    source = F1.capacity_domain_source_gate()
    source_rejected = F1.capacity_domain_mutations()
    terminal = terminal_replay()
    return {
        "format": "lisp65-c2.3-v21-workbench-capacity-domain-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: F1 Workbench capacity comparison owned by named arena",
        "authority": {"authorization": authorization(),
            **historical_authority(), "current_F1_source": bind(F1_DRIVER),
            "VMA_golden": bind(F1.VMA_GOLDEN), "driver": bind(DRIVER)},
        "conversion": source,
        "terminal_consumer_replay": terminal,
        "mutations_rejected": source_rejected,
        "history": {"historical_receipts_rewritten": False,
            "runtime_slice_capacity_changed": False,
            "workbench_numeric_pin_introduced": False},
        "disposition": {"cards_authorized": 1, "cards_consumed": 0,
            "completion_allowed": False, "media_allowed": False,
            "device_allowed": False},
        "claim_limit": (
            "Host-only checker conversion and historical rebind. The sole "
            "authorized card has not yet run; no completion, media or device."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("status") ==
            "PASS: F1 Workbench capacity comparison owned by named arena"
        and value["conversion"]["arena"] == "workbench-boot-overlay"
        and value["conversion"]["capacity_bytes"] == 2730
        and value["terminal_consumer_replay"]["headroom_bytes"] == 879
        and value["terminal_consumer_replay"]["downstream_hidden_reds"] == 0
        and value["mutations_rejected"] == [
            "substitute-runtime-slice-arena", "pin-workbench-number",
            "drop-arena-identity", "drop-section-membership"]
        and value["history"] == {
            "historical_receipts_rewritten": False,
            "runtime_slice_capacity_changed": False,
            "workbench_numeric_pin_introduced": False}
        and value["disposition"]["cards_consumed"] == 0,
        "capacity-domain receipt red",
    )
    if verify:
        require(value == derive(), "capacity-domain receipt drift")


def receipt_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rename-domain": lambda x: x["conversion"].update(
            arena="runtime-overlay-slices"),
        "pin-number": lambda x: x["history"].update(
            workbench_numeric_pin_introduced=True),
        "change-runtime-cap": lambda x: x["history"].update(
            runtime_slice_capacity_changed=True),
        "erase-headroom": lambda x: x["terminal_consumer_replay"].update(
            headroom_bytes=0),
        "invent-downstream-red": lambda x: x["terminal_consumer_replay"].update(
            downstream_hidden_reds=1),
        "rewrite-history": lambda x: x["history"].update(
            historical_receipts_rewritten=True),
        "consume-card": lambda x: x["disposition"].update(cards_consumed=1),
        "allow-device": lambda x: x["disposition"].update(device_allowed=True),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=True)
        except DomainError:
            rejected.append(name)
    require(rejected == list(cases), "capacity-domain receipt mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "capacity-domain receipt exists")
    value = derive(); validate(value, verify=True)
    value["receipt_mutations_rejected"] = receipt_mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("2.1 Workbench capacity domain: PASS arena=2730 scratch=1851 "
          "headroom=879 mutations=12 card=0/1")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("receipt_mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == receipt_mutations(value),
            "capacity-domain receipt mutation set drift")
    print("2.1 Workbench capacity domain: CHECK PASS arena=workbench card=0/1")


def selftest() -> None:
    value = derive(); validate(value, verify=True); receipt_mutations(value)
    print("2.1 Workbench capacity domain: SELFTEST PASS mutations=12")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check", "selftest"),
            "usage: c2_v21_workbench_capacity_domain.py record|check|selftest")
    {"record": record, "check": check, "selftest": selftest}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DomainError, F1.ProbeError, OLD.AttributionError, OSError,
            ValueError, KeyError, json.JSONDecodeError,
            subprocess.SubprocessError) as error:
        print(f"2.1 Workbench capacity domain: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
