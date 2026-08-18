#!/usr/bin/env python3
"""Detach historical phase-02a receipts from the living assembler source."""

from __future__ import annotations

import argparse
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

import c2_v20_phase02a_attribution as ATTR  # noqa: E402
import c2_v20_phase02a_site_result as SITE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
LIVE_SOURCE = ROOT / "src/c2_mapped_far_convergence.s"
PRECEDENT = ARCH / (
    "c2.3-v2.0-mapped-far-return-source-unbind-phase9-20260815-receipt.json")
RECEIPT = ARCH / (
    "c2.3-v2.0-phase02a-source-unbind-20260816-receipt.json")
DRIVER = Path(__file__).resolve()
GATES = ROOT / "mk/gates.mk"
AUTHORIZATION = "bbfcfade"
RECORDED_ON = "2026-08-16"
ATTR_SHA256 = "49bb0fb031905e2829ced621449314e00a56dbc7dc3721666ebb536fabde8b5d"
SITE_SHA256 = "70581a966909a18b4465bd3b9d5b9a0fa37ef41414621ef4df6dd74a117d122d"
HISTORICAL_ASM_SHA256 = (
    "697fcc294e30512ccf62255f80ae79c3a75d9bd0ef6bc79c5f920903effcb166")
LIVE_ASM_SHA256 = (
    "2d1f4ebfe8d1cd61e9c6df261b2f57f7d7580f79b6271f545b68620caf0e83f6")


class UnbindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise UnbindError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
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
    authority = git_bind(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{authority['commit']}:{authority['path']}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().split())
    for token in ("phase-02a source unbind approved",
                  "evidence and claims stay byteidentical history",
                  "historical receipts witness their own world",
                  "they never gate the living one"):
        require(token in text, f"phase-02a source-unbind authority absent: {token}")
    return authority


def historical_receipts() -> tuple[dict[str, Any], dict[str, Any]]:
    require(bind(ATTR.RECEIPT)["sha256"] == ATTR_SHA256,
            "historical phase-02a attribution was rewritten")
    require(bind(SITE.RECEIPT)["sha256"] == SITE_SHA256,
            "historical phase-02a site result was rewritten")
    attribution = load(ATTR.RECEIPT)
    site = load(SITE.RECEIPT)
    ATTR.validate(attribution)
    ATTR.selftest(attribution)
    SITE.validate(site)
    SITE.selftest(site)
    require(attribution["authority"]["assembler"]["sha256"] ==
            HISTORICAL_ASM_SHA256
            and site["authority"]["assembler"]["sha256"] ==
            HISTORICAL_ASM_SHA256,
            "historical phase-02a assembler identity drift")
    return attribution, site


def source_gate(source_override: str | None = None) -> dict[str, Any]:
    source = GATES.read_text(encoding="utf-8") \
        if source_override is None else source_override
    old_commands = (
        "python3 tools/host-lisp/c2_v20_phase02a_attribution.py selftest",
        "python3 tools/host-lisp/c2_v20_phase02a_attribution.py check",
        "python3 tools/host-lisp/c2_v20_phase02a_site_result.py selftest",
        "python3 tools/host-lisp/c2_v20_phase02a_site_result.py check",
    )
    require(not any(command in source for command in old_commands),
            "historical phase-02a receipt still gates the living source")
    command = (
        "python3 tools/host-lisp/c2_v20_phase02a_source_unbind_20260816.py check")
    require(source.count(command) >= 2,
            "phase-02a source-unbind successor is absent from the live gates")
    return {"status": "PASS: historical phase-02a gates are receipt-only",
            "historical_live_source_commands": 0,
            "successor_check_commands": source.count(command)}


def derive() -> dict[str, Any]:
    attribution, site = historical_receipts()
    live = bind(LIVE_SOURCE)
    require(live["sha256"] == LIVE_ASM_SHA256
            and live["sha256"] != HISTORICAL_ASM_SHA256,
            "authorized living phase-9/full-span source identity drift")
    gate = source_gate()
    return {
        "format": "lisp65-c2.3-v20-phase02a-source-unbind-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: historical phase-02a receipts detached from living source",
        "authority": {"owner": authorization(),
            "historical_attribution": bind(ATTR.RECEIPT),
            "historical_site_result": bind(SITE.RECEIPT),
            "source_unbind_precedent": bind(PRECEDENT),
            "living_source": live, "driver": bind(DRIVER)},
        "historical": {
            "attribution_status": attribution["status"],
            "site_result_status": site["status"],
            "assembler_sha256": HISTORICAL_ASM_SHA256,
            "receipts_rewritten": False,
            "claims_changed": False},
        "living": {"assembler": live,
            "historical_source_is_live_predicate": False,
            "acceptance_authority": "phase-9/full-span successor gates"},
        "live_gate": gate,
        "result": {"product_work": 0, "device_contacts": 0,
            "D2_authorization_changed": False},
        "claim_limit": (
            "Historical receipt/source closure only. No historical evidence "
            "or claim changed; no WPLTO, link, media or device action."),
    }


def validate(value: dict[str, Any]) -> None:
    require(
        value.get("status") ==
            "PASS: historical phase-02a receipts detached from living source"
        and value["historical"]["receipts_rewritten"] is False
        and value["historical"]["claims_changed"] is False
        and value["living"]["historical_source_is_live_predicate"] is False
        and value["historical"]["assembler_sha256"] !=
            value["living"]["assembler"]["sha256"]
        and value["live_gate"]["historical_live_source_commands"] == 0
        and value["result"] == {"product_work": 0, "device_contacts": 0,
                                "D2_authorization_changed": False},
        "phase-02a historical source-unbind drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-historical-receipts": lambda x: x["historical"].update(
            receipts_rewritten=True),
        "change-historical-claims": lambda x: x["historical"].update(
            claims_changed=True),
        "restore-live-source-predicate": lambda x: x["living"].update(
            historical_source_is_live_predicate=True),
        "collapse-source-worlds": lambda x: x["living"].update(
            assembler={**x["living"]["assembler"],
                       "sha256": x["historical"]["assembler_sha256"]}),
        "restore-historical-gate": lambda x: x["live_gate"].update(
            historical_live_source_commands=1),
        "run-product-work": lambda x: x["result"].update(product_work=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except UnbindError:
            rejected.append(name)
    require(rejected == list(cases), "phase-02a source-unbind mutation survived")
    return rejected


def write() -> None:
    require(not RECEIPT.exists(), "phase-02a source-unbind receipt exists")
    value = derive(); validate(value)
    value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("phase-02a source unbind: PASS historical=2 living=successor mutations=6")


def check() -> None:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    validate(value)
    expected = derive(); validate(expected)
    require(value == expected and rejected == mutations(value),
            "phase-02a source-unbind receipt drift")
    print("phase-02a source unbind: CHECK PASS history=unchanged live=detached")


def selftest() -> None:
    value = derive(); validate(value)
    require(len(mutations(value)) == 6, "phase-02a source-unbind mutation drift")
    old_gate = GATES.read_text(encoding="utf-8").replace(
        "python3 tools/host-lisp/c2_v20_phase02a_source_unbind_20260816.py check",
        "python3 tools/host-lisp/c2_v20_phase02a_attribution.py check", 1)
    try:
        source_gate(old_gate)
    except UnbindError:
        pass
    else:
        raise UnbindError("historical live-source gate mutation survived")
    print("phase-02a source unbind: SELFTEST PASS mutations=7")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    {"write": write, "check": check, "selftest": selftest}[
        parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"phase-02a source unbind: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
