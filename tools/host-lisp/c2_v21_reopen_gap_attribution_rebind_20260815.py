#!/usr/bin/env python3
"""Loud dated rebind of the reopen-gap attribution after source growth."""

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

import c2_v21_dependency_invariant_golden as GOLD  # noqa: E402
import c2_v21_loading_libraries_progress_rebind as RING  # noqa: E402
import c2_v21_reopen_gap_dependency_attribution as ATTR  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
RECEIPT = ARCH / (
    "c2.3-v2.1-reopen-gap-attribution-rebind-20260815-receipt.json")
AUTHORIZATION = "2a327257"
FORMAT = "lisp65-c2.3-v2.1-reopen-gap-attribution-rebind-20260815-v1"
EXCLUDED = tuple(sorted((
    Path(GOLD.__file__).resolve(),
    Path(RING.__file__).resolve(),
    ROOT / "config/c2-v21-loading-libraries-stage-breadcrumb-contact.json",
    ROOT / "tools/host-lisp/c2_v21_loading_libraries_stage_breadcrumb_contact.py",
)))


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


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


def authority() -> dict[str, Any]:
    full = subprocess.run(
        ["git", "rev-parse", f"{AUTHORIZATION}^{{commit}}"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{full}:{name}"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().split()).lower()
    for token in ("ring contact authorized on the repaired medium",
                  "reopen_gap", "authorized loud, dated rebind"):
        require(token in text, f"reopen-gap rebind authority absent: {token}")
    return {"authority": "git-blob", "commit": full, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def with_diagnostic_sources_excluded(action: Callable[[], Any]) -> Any:
    original = ATTR.tracked_text_files
    before = original()
    require(all(path in before for path in EXCLUDED),
            "reopen-gap diagnostic exclusion identity drift")

    def active_contracts() -> list[Path]:
        result = [path for path in original() if path not in EXCLUDED]
        require(len(result) + len(EXCLUDED) == len(before)
                and not set(result) & set(EXCLUDED),
                "reopen-gap diagnostic exclusion grew or dimmed")
        return result

    ATTR.tracked_text_files = active_contracts
    try:
        return action()
    finally:
        ATTR.tracked_text_files = original


def current_attribution() -> dict[str, Any]:
    def build() -> dict[str, Any]:
        value = ATTR.derive()
        value["mutations_rejected"] = ATTR.mutations(value)
        return value
    return with_diagnostic_sources_excluded(build)


def semantic_projection(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": value["status"],
        "attribution": value["attribution"],
        "linker_classification": value["linker_classification"],
        "symbolic_runtime_consumers": value["dependency_inventory"]
            ["symbolic_runtime_consumers"],
        "absolute_runtime_consumers": value["dependency_inventory"]
            ["absolute_runtime_consumers"],
        "media_format": value["dependency_inventory"]["media_format"],
        "sibling_gap0": value["sibling_classification"][ATTR.GAP0],
        "sibling_gap1": value["sibling_classification"][ATTR.GAP1],
        "sibling_gap2": value["sibling_classification"][ATTR.GAP2],
        "mutations_rejected": value["mutations_rejected"],
    }


def derive() -> dict[str, Any]:
    historical = load(ATTR.RECEIPT)
    current = current_attribution()
    historical_projection = semantic_projection(historical)
    current_projection = semantic_projection(current)
    require(historical_projection == current_projection,
            "reopen-gap semantic conclusion changed during dated rebind")
    old_count = historical["dependency_inventory"]["active_pin_scan"][
        "tracked_text_files"]
    new_count = current["dependency_inventory"]["active_pin_scan"][
        "tracked_text_files"]
    require(new_count > old_count
            and current["attribution"]["outcome"] == "NOT-DEPENDED-UPON"
            and current["owner_disposition"] == historical["owner_disposition"],
            "reopen-gap rebind is not additive source growth")
    value = {
        "format": FORMAT, "recorded_on": "2026-08-15",
        "status": "PASS: LOUD DATED REOPEN-GAP ATTRIBUTION REBIND",
        "authority": {"owner": authority(),
            "historical_attribution": bind(ATTR.RECEIPT),
            "dependent_vma_golden": bind(GOLD.GOLDEN)},
        "source_scan": {"historical_tracked_files": old_count,
            "current_tracked_files": new_count,
            "diagnostic_sources_excluded": [
                path.relative_to(ROOT).as_posix() for path in EXCLUDED]},
        "semantic_projection": current_projection,
        "current_attribution_sha256": hashlib.sha256(
            canonical(current)).hexdigest(),
        "result": {"semantic_conclusion": "byteidentical",
            "historical_receipt_changed": False,
            "gap0": "derived", "gap1": "derived", "gap2": "fixed",
            "device_contacts": 0},
        "claim_limit": (
            "Loud source-inventory rebind only. The reviewed Golden and "
            "historical attribution remain byteidentical; no product, media, "
            "device, card or release claim is added."),
    }
    value["mutations"] = mutations(value)
    audit(value)
    return value


def audit(value: dict[str, Any]) -> None:
    require(
        value.get("status") ==
            "PASS: LOUD DATED REOPEN-GAP ATTRIBUTION REBIND"
        and value.get("result") == {"semantic_conclusion": "byteidentical",
            "historical_receipt_changed": False,
            "gap0": "derived", "gap1": "derived", "gap2": "fixed",
            "device_contacts": 0}
        and value.get("source_scan", {}).get("current_tracked_files", 0) >
            value.get("source_scan", {}).get("historical_tracked_files", 0)
        and len(value.get("source_scan", {}).get(
            "diagnostic_sources_excluded", [])) == len(EXCLUDED),
        "reopen-gap dated rebind drift")


def mutations(base: dict[str, Any]) -> list[str]:
    cases = {
        "rewrite-history": lambda x: x["result"].update(
            historical_receipt_changed=True),
        "change-gap0": lambda x: x["result"].update(gap0="fixed"),
        "change-gap2": lambda x: x["result"].update(gap2="derived"),
        "drop-diagnostic-exclusion": lambda x: x["source_scan"]
            ["diagnostic_sources_excluded"].pop(),
        "claim-device": lambda x: x["result"].update(device_contacts=1),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(base)
        mutate(trial)
        try:
            audit(trial)
        except RebindError:
            rejected.append(name)
    require(len(rejected) == len(cases), "reopen-gap rebind mutation survived")
    return sorted(rejected)


def record() -> dict[str, Any]:
    require(not RECEIPT.exists(), "reopen-gap dated rebind receipt exists")
    value = derive()
    RECEIPT.write_bytes(canonical(value))
    return value


def check() -> dict[str, Any]:
    value = load(RECEIPT)
    audit(value)
    require(value == derive(), "reopen-gap dated rebind reconstruction drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("record", "check", "selftest"))
    args = parser.parse_args()
    value = record() if args.action == "record" else (
        check() if args.action == "check" else derive())
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RebindError, ATTR.AttributionError, OSError, KeyError,
            ValueError, subprocess.CalledProcessError) as error:
        print(f"REOPEN-GAP DATED REBIND: {error}", file=sys.stderr)
        raise SystemExit(1)
