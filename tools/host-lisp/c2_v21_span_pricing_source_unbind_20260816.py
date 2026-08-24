#!/usr/bin/env python3
"""Detach Link-111 span pricing from the living root-fix sources."""

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

import c2_v21_span_verification_pricing as PRICING  # noqa: E402
import c2_v21_full_span_convergence as FULL_SPAN  # noqa: E402
import c2_v21_probe_oracle_root_fix as ROOT_FIX  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
RECEIPT = ARCH / (
    "c2.3-v2.1-span-pricing-source-unbind-20260816-receipt.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "bbfcfade"
FORMAT = "lisp65-c2.3-v2.1-span-pricing-source-unbind-v1"
STATUS = "PASS: HISTORICAL-SPAN-PRICING-DETACHED-FROM-LIVE-SOURCES"
HISTORICAL_RECEIPT_SHA256 = (
    "2aa04b329c010e53252e95af4424a60d24c0497b8c45170aefbbcf0acb2608e6")
HISTORICAL_FULL_SPAN_SHA256 = (
    "c497c108d4334ceec0ece960c4559cb10f6ef0181f91950718ce05bfcb3d5dfb")


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
    value = git_bind(AUTHORIZATION, PLAN)
    raw = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode().lower()
    text = " ".join(raw.replace("*", "").split())
    for token in ("historical receipts witness their own world",
                  "they never gate the living one"):
        require(token in text,
                f"historical source-unbind authority absent: {token}")
    return value


def historical_pricing() -> dict[str, Any]:
    binding = bind(PRICING.RECEIPT)
    require(binding["sha256"] == HISTORICAL_RECEIPT_SHA256,
            "historical span-pricing receipt was rewritten")
    value = load(PRICING.RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    PRICING.validate(value)
    require(rejected == PRICING.mutations(value),
            "historical span-pricing mutations drift")
    return {
        "receipt": binding,
        "receipt_sha256": binding["sha256"],
        "status": value["status"],
        "DMA_source": value["authority"]["DMA_source"],
        "EXT_source": value["authority"]["EXT_source"],
        "checker": value["authority"]["checker"],
        "receipt_rewritten": False,
        "claims_changed": False,
    }


def historical_full_span() -> dict[str, Any]:
    binding = bind(FULL_SPAN.RECEIPT)
    require(binding["sha256"] == HISTORICAL_FULL_SPAN_SHA256,
            "historical full-span receipt was rewritten")
    value = load(FULL_SPAN.RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    FULL_SPAN.validate(value)
    require(rejected == FULL_SPAN.mutations(value),
            "historical full-span mutations drift")
    return {
        "receipt": binding,
        "receipt_sha256": binding["sha256"],
        "status": value["status"],
        "DMA_source": value["authority"]["DMA_source"],
        "linker": value["authority"]["linker"],
        "receipt_rewritten": False,
        "claims_changed": False,
    }


def derive() -> dict[str, Any]:
    old = historical_pricing()
    old_full_span = historical_full_span()
    live = load(ROOT_FIX.RECEIPT)
    current_dma = bind(PRICING.DMA)
    current_mem = bind(PRICING.MEM)
    require(
        live.get("status") == ROOT_FIX.STATUS
        and live["authority"]["DMA"] == current_dma
        and live["authority"]["mem"] == current_mem
        and old["DMA_source"]["path"] == current_dma["path"]
        and old["EXT_source"]["path"] == current_mem["path"]
        and old["DMA_source"]["sha256"] != current_dma["sha256"]
        and old["EXT_source"]["sha256"] != current_mem["sha256"]
        and old_full_span["DMA_source"] == old["DMA_source"]
        and old_full_span["linker"]["sha256"] !=
            bind(Path(PRODUCT.__file__))["sha256"],
        "historical/living span source boundary drift")
    value = {
        "format": FORMAT,
        "recorded_on": "2026-08-16",
        "status": STATUS,
        "authority": {
            "standing_owner_clause": authorization(),
            "historical_receipt": bind(PRICING.RECEIPT),
            "living_root_fix": bind(ROOT_FIX.RECEIPT),
            "driver": bind(DRIVER),
        },
        "historical": old,
        "historical_full_span": old_full_span,
        "living": {
            "DMA_source": current_dma,
            "EXT_source": current_mem,
            "acceptance_authority": "nine-reader MAP-CPU root-fix receipt",
            "historical_sources_are_live_predicates": False,
            "reader_count": ROOT_FIX.source_contract()["reader_count"],
            "linker": bind(Path(PRODUCT.__file__)),
        },
        "execution_accounting": {
            "WPLTO_runs": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0,
        },
        "claim_limit": (
            "Authority-only source unbind. Historical evidence, pricing and "
            "claims remain byteidentical; living semantics are owned by the "
            "MAP-CPU root-fix gates."),
    }
    validate(value)
    value["mutations_rejected"] = mutations(value)
    return value


def validate(value: dict[str, Any]) -> None:
    old = value["historical"]
    old_full_span = value["historical_full_span"]
    live = value["living"]
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and old["receipt_sha256"] == HISTORICAL_RECEIPT_SHA256
        and old["receipt_rewritten"] is False
        and old["claims_changed"] is False
        and old_full_span["receipt_sha256"] == HISTORICAL_FULL_SPAN_SHA256
        and old_full_span["receipt_rewritten"] is False
        and old_full_span["claims_changed"] is False
        and old["DMA_source"]["sha256"] != live["DMA_source"]["sha256"]
        and old["EXT_source"]["sha256"] != live["EXT_source"]["sha256"]
        and old_full_span["linker"]["sha256"] != live["linker"]["sha256"]
        and live["historical_sources_are_live_predicates"] is False
        and live["reader_count"] == 9
        and value["execution_accounting"] == {
            "WPLTO_runs": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0},
        "span-pricing source-unbind drift")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-history": lambda x: x["historical"].update(
            receipt_rewritten=True),
        "change-claim": lambda x: x["historical"].update(
            claims_changed=True),
        "rewrite-full-span-history": lambda x: x[
            "historical_full_span"].update(receipt_rewritten=True),
        "change-full-span-claim": lambda x: x[
            "historical_full_span"].update(claims_changed=True),
        "restore-DMA-live-predicate": lambda x: x["living"].update(
            historical_sources_are_live_predicates=True),
        "collapse-DMA-worlds": lambda x: x["living"].update(
            DMA_source=x["historical"]["DMA_source"]),
        "collapse-EXT-worlds": lambda x: x["living"].update(
            EXT_source=x["historical"]["EXT_source"]),
        "collapse-linker-worlds": lambda x: x["living"].update(
            linker=x["historical_full_span"]["linker"]),
        "lose-reader": lambda x: x["living"].update(reader_count=8),
        "invent-link": lambda x: x["execution_accounting"].update(
            product_links=1),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value)
        trial.pop("mutations_rejected", None)
        mutate(trial)
        try:
            validate(trial)
        except UnbindError:
            rejected.append(name)
    require(rejected == list(cases),
            "span-pricing source-unbind mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    value = derive()
    if action == "record":
        require(not RECEIPT.exists(), "span-pricing source-unbind receipt exists")
        RECEIPT.write_bytes(canonical(value))
    elif action == "check":
        recorded = load(RECEIPT)
        recorded_linker = recorded["living"].pop("linker")
        current_linker = value["living"].pop("linker")
        recorded_driver = recorded["authority"].pop("driver")
        current_driver = value["authority"].pop("driver")
        require(recorded_linker["path"] == current_linker["path"]
                and recorded_driver["path"] == current_driver["path"]
                and recorded == value,
                "span-pricing source-unbind receipt stale")
    else:
        require(len(value["mutations_rejected"]) == 10,
                "span-pricing source-unbind mutation count drift")
    print(f"span-pricing source unbind: PASS action={action} mutations=10")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (UnbindError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"span-pricing source unbind: RED: {error}", file=sys.stderr)
        raise SystemExit(2)
