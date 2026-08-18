#!/usr/bin/env python3
"""Loudly rebind the MAP-tuple fixture from registry cardinality to identity."""

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

import c2_v20_map_tuple_fix_replacement_card as M  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.1-cpu-transport-work-plan.md"
RECEIPT = ARCH / (
    "c2.3-v2.0-map-tuple-fixture-scope-rebind-2026-08-14.json")
DRIVER = Path(__file__).resolve()
AUTHORIZATION = "b3f6adc2"
RECORDED_ON = "2026-08-14"


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
    for token in ("map-tuple fixture red", "loud, dated rebind",
                  "exactly one source-owner scope"):
        require(token in text, f"MAP-tuple fixture rebind authorization absent: {token}")
    return authority


def historical() -> dict[str, Any]:
    value = load(M.FINAL_RED)
    require(
        value.get("status") == "FINAL RED: replacement card returns to owner"
        and value.get("retry_authorized") is False
        and value.get("owner_disposition_required") is True,
        "historical MAP-tuple replacement result drift",
    )
    return value


def derive() -> dict[str, Any]:
    historical()
    gate = M.single_implementation_gate()
    rejected = M.single_implementation_mutations()
    scope = M.BASE.source_scope_gate()["selected"]["scopes"]
    require(len(scope) >= 2 and len([row for row in scope if row["selected"]]) == 1,
            "current source-owner registry fixture shape drift")
    return {
        "format": "lisp65-c2.3-v20-map-tuple-fixture-scope-rebind-v1",
        "recorded_on": RECORDED_ON,
        "status": "PASS: MAP-tuple fixture selects owner identity, not registry cardinality",
        "authority": {"authorization": authorization(),
            "historical_final_red": bind(M.FINAL_RED),
            "historical_driver": git_binding(AUTHORIZATION, M.DRIVER),
            "current_driver": bind(M.DRIVER), "rebind_driver": bind(DRIVER)},
        "change": {"historical_receipt_rewritten": False,
            "semantic_MAP_tuple_claim_changed": False,
            "old_fixture_assumption": "registry contains exactly one scope",
            "current_fixture_contract": "exactly one selected owner identity",
            "unrelated_scope_count": len(scope) - 1},
        "current_gate": gate,
        "mutations_rejected": rejected,
        "claim_limit": (
            "Fixture-only loud rebind. Historical MAP-tuple evidence remains "
            "unchanged; this authorizes no card, media or device action."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("status") ==
            "PASS: MAP-tuple fixture selects owner identity, not registry cardinality"
        and value["change"]["historical_receipt_rewritten"] is False
        and value["change"]["semantic_MAP_tuple_claim_changed"] is False
        and value["current_gate"]["selected_successor_copies"] == 1
        and value["mutations_rejected"] == [
            "select-unrelated-scope", "drop-selected-owner",
            "duplicate-selected-body"],
        "MAP-tuple fixture rebind receipt red",
    )
    if verify:
        require(value == derive(), "MAP-tuple fixture rebind drift")


def receipt_mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "rewrite-history": lambda x: x["change"].update(
            historical_receipt_rewritten=True),
        "change-MAP-claim": lambda x: x["change"].update(
            semantic_MAP_tuple_claim_changed=True),
        "restore-cardinality-pin": lambda x: x["change"].update(
            current_fixture_contract="registry contains exactly one scope"),
        "drop-owner": lambda x: x["current_gate"].update(
            selected_successor_copies=0),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=True)
        except RebindError:
            rejected.append(name)
    require(rejected == list(cases), "MAP-tuple rebind mutation survived")
    return rejected


def record() -> None:
    require(not RECEIPT.exists(), "MAP-tuple fixture rebind exists")
    value = derive(); validate(value, verify=True)
    value["receipt_mutations_rejected"] = receipt_mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("MAP-tuple fixture rebind: PASS selected=1 unrelated=1 mutations=7")


def check() -> None:
    value = load(RECEIPT)
    rejected = value.pop("receipt_mutations_rejected", None)
    validate(value, verify=True)
    require(rejected == receipt_mutations(value),
            "MAP-tuple fixture rebind mutation set drift")
    print("MAP-tuple fixture rebind: CHECK PASS identity-not-cardinality")


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in ("record", "check"),
            "usage: c2_v20_map_tuple_fixture_scope_rebind_20260814.py record|check")
    {"record": record, "check": check}[sys.argv[1]]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RebindError, M.ReplacementCardError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"MAP-tuple fixture rebind: FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
