#!/usr/bin/env python3
"""Loud plan-authority successor after the service-end disposition."""

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

import c2_v21_phase9_domain_split_source_rebind_20260815 as PREV  # noqa: E402
import c2_v21_phase9_service_end_dependency_attribution as ATTR  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
RECEIPT = ARCH / (
    "c2.3-v2.1-phase9-domain-split-source-rebind-20260816-receipt.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "b1dd0379"


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


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


def authority() -> dict[str, Any]:
    value = git_binding(AUTHORIZATION, PLAN)
    text = subprocess.run(
        ["git", "show", f"{value['commit']}:{value['path']}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout.decode().lower()
    require("dependency check, then reclassify" in text
            and "artifact-only replay" in text,
            "service-end disposition authority absent")
    return value


def validate(value: dict[str, Any]) -> None:
    require(
        value.get("status")
            == "PASS: LOUD SERVICE-END PLAN-AUTHORITY SOURCE REBIND"
        and value.get("semantic_projection") == {
            "ABI_gate_domains_changed": False,
            "far_service_source_changed": False,
            "product_artifacts_changed": False,
            "WPLTO_runs": 0,
            "service_end_class": "freight-derived",
            "service_load_end_class": "freight-derived"},
        "service-end source rebind drift")


def derive() -> dict[str, Any]:
    previous = load(PREV.RECEIPT)
    rejected = previous.pop("mutations_rejected", None)
    PREV.validate(previous)
    require(rejected == PREV.mutations(previous),
            "predecessor domain-split receipt mutation drift")
    attribution = load(ATTR.RECEIPT)
    attr_rejected = attribution.pop("mutations_rejected", None)
    attribution.get("authority", {}).pop("pre_rebind", None)
    ATTR.validate(attribution)
    require(attr_rejected == ATTR.mutations(attribution),
            "service-end attribution receipt drift")
    value = {
        "format": "lisp65-c2.3-v21-phase9-service-end-source-rebind-v1",
        "recorded_on": "2026-08-16",
        "status": "PASS: LOUD SERVICE-END PLAN-AUTHORITY SOURCE REBIND",
        "authority": {"owner": authority(), "previous_rebind": bind(PREV.RECEIPT),
            "service_end_attribution": bind(ATTR.RECEIPT),
            "ABI_contract": bind(PREV.ABI_CONTRACT),
            "ABI_gate": bind(PREV.ABI_GATE), "far_source": bind(PREV.FAR_SOURCE),
            "driver": bind(DRIVER)},
        "semantic_projection": {"ABI_gate_domains_changed": False,
            "far_service_source_changed": False,
            "product_artifacts_changed": False, "WPLTO_runs": 0,
            "service_end_class": "freight-derived",
            "service_load_end_class": "freight-derived"},
        "claim_limit": "Loud authority successor only; no product work.",
    }
    validate(value)
    return value


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "change-ABI-domains": lambda x: x["semantic_projection"].update(
            ABI_gate_domains_changed=True),
        "change-far-source": lambda x: x["semantic_projection"].update(
            far_service_source_changed=True),
        "change-product": lambda x: x["semantic_projection"].update(
            product_artifacts_changed=True),
        "run-WPLTO": lambda x: x["semantic_projection"].update(WPLTO_runs=1),
        "restore-fixed-end": lambda x: x["semantic_projection"].update(
            service_end_class="fixed")}
    rejected: list[str] = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "service-end source rebind mutation survived")
    return rejected


def build() -> None:
    require(not RECEIPT.exists(), "service-end source rebind receipt exists")
    value = derive(); value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("phase-9 service-end source rebind: PASS product-change=0 WPLTO=0")


def rebind() -> None:
    value = load(RECEIPT)
    old_rejected = value.pop("mutations_rejected", None)
    value.get("authority", {}).pop("pre_rebind", None)
    expected = derive()
    comparison = deepcopy(expected)
    comparison["authority"]["service_end_attribution"] = value[
        "authority"]["service_end_attribution"]
    comparison["authority"]["driver"] = value["authority"]["driver"]
    require(value == comparison and old_rejected is not None,
            "service-end source rebind moved more than successor authorities")
    expected["authority"]["pre_rebind"] = {
        "service_end_attribution": value["authority"][
            "service_end_attribution"],
        "driver": value["authority"]["driver"]}
    semantic = deepcopy(expected); semantic["authority"].pop("pre_rebind")
    expected["mutations_rejected"] = mutations(semantic)
    RECEIPT.write_bytes(canonical(expected))
    print("phase-9 service-end source rebind: REBIND PASS product-change=0")


def check() -> None:
    value = load(RECEIPT); rejected = value.pop("mutations_rejected", None)
    value.get("authority", {}).pop("pre_rebind", None)
    require(value == derive() and rejected == mutations(value),
            "service-end source rebind receipt drift")
    print("phase-9 service-end source rebind: CHECK PASS product-change=0")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "rebind", "check"))
    {"build": build, "rebind": rebind,
     "check": check}[parser.parse_args().action]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
