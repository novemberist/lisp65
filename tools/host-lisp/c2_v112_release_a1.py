#!/usr/bin/env python3
"""Bind the v1.4.0 Phase-A full source-gate run and its dated side effects."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "build/c2.3/v1.4.0-release/a1/check-source-rerun.log"
CONTRACT = ROOT / "config/c2-v112-release-closure.json"
CLOSURE = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-release-closure-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-a1-source-gate-receipt.json"
)
BASE_COMMIT = "411c2506"
SIDE_EFFECTS: dict[str, set[str]] = {
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.3-ship-boot-inheritance-gate-receipt.json": {
        "/recorded_on",
    },
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.4-code-window-content-convergence-gate-receipt.json": {
        "/recorded_on",
    },
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.4-dma-content-consumption-broaden-once-sweep.json": {
        "/recorded_on",
    },
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-mapped-far-assembly-equivalence-receipt.json": {
        "/authorities/existing_convergence_receipt/sha256",
        "/recorded_on",
    },
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-stack-overlay-mapped-far-service-ownership-gate-receipt.json": {
        "/authorities/assembly_equivalence_receipt/sha256",
        "/authorities/convergence_receipt/sha256",
        "/authorities/dma_sweep_receipt/sha256",
        "/recorded_on",
    },
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.7-state-ownership-phase-c-receipt.json": {
        "/authorities/assembly_equivalence/sha256",
        "/authorities/mapped_ownership/sha256",
        "/recorded_on",
    },
}


class A1Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise A1Error(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def load_bytes(raw: bytes, label: str) -> dict[str, Any]:
    value = json.loads(raw.decode("utf-8"))
    require(isinstance(value, dict), f"JSON object required: {label}")
    return value


def git_bytes(commit: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    require(result.returncode == 0, f"historical authority absent: {commit}:{path}")
    return result.stdout


def changes(before: Any, after: Any, pointer: str = "") -> set[str]:
    if type(before) is not type(after):
        return {pointer or "/"}
    if isinstance(before, dict):
        result: set[str] = set()
        for key in sorted(set(before) | set(after)):
            child = pointer + "/" + key.replace("~", "~0").replace("/", "~1")
            if key not in before or key not in after:
                result.add(child)
            else:
                result.update(changes(before[key], after[key], child))
        return result
    if isinstance(before, list):
        return set() if before == after else {pointer or "/"}
    return set() if before == after else {pointer or "/"}


def get_pointer(value: dict[str, Any], pointer: str) -> Any:
    current: Any = value
    for raw in pointer[1:].split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        require(isinstance(current, dict) and key in current,
                f"JSON pointer absent: {pointer}")
        current = current[key]
    return current


def side_effect_rows() -> list[dict[str, Any]]:
    rows = []
    for path, expected in SIDE_EFFECTS.items():
        historical_raw = git_bytes(BASE_COMMIT, path)
        current_path = ROOT / path
        current_raw = current_path.read_bytes()
        historical = load_bytes(historical_raw, f"{BASE_COMMIT}:{path}")
        current = load_bytes(current_raw, path)
        actual = changes(historical, current)
        require(actual == expected,
                f"calendar side-effect vocabulary drift for {path}: {sorted(actual)}")
        for pointer in sorted(expected):
            before = get_pointer(historical, pointer)
            after = get_pointer(current, pointer)
            if pointer == "/recorded_on":
                require(before == "2026-08-05" and after == "2026-08-07",
                        f"non-calendar recorded_on drift: {path}")
            else:
                require(pointer.endswith("/sha256")
                        and isinstance(before, str) and len(before) == 64
                        and isinstance(after, str) and len(after) == 64,
                        f"non-binding cascade drift: {path}{pointer}")
                parent = pointer.rsplit("/", 1)[0]
                dependency = get_pointer(current, parent + "/path")
                require(after == sha((ROOT / dependency).read_bytes()),
                        f"current cascade SHA does not bind dependency: {path}{pointer}")
                require(before == sha(git_bytes(BASE_COMMIT, dependency)),
                        f"historical cascade SHA does not bind dependency: {path}{pointer}")
        rows.append({
            "path": path,
            "changed_json_pointers": sorted(actual),
            "before": {"commit": BASE_COMMIT, "bytes": len(historical_raw),
                       "sha256": sha(historical_raw)},
            "after": {"bytes": len(current_raw), "sha256": sha(current_raw)},
            "semantic_payload_equal_after_exact_date_binding_normalization": True,
        })
    return rows


def build() -> dict[str, Any]:
    log = LOG.read_text(encoding="utf-8")
    required = [
        "post-v1.2-housekeeping: PASS evidence=1843",
        "c2-v111-compiler-locality: PASS full=716->677s post-require=218->179s",
        "c2-v112-release-closure: PASS state=closure-only comfort=5 conditional=1 mutations=11",
        "c2-reset-domain-completeness: PASS executions=7 mutations=6 bytes=50816 c2j=64zero",
        "v11-surface-delivery-parity: PASS bound_names=105",
        "r6-g6-seal: REGISTERED SET PASS count=4",
        "workbench-ship selftest OK",
    ]
    require(all(row in log for row in required), "A1 required source-gate witness absent")
    require("make: ***" not in log
            and "FIRST RED:" not in log
            and "not remade because of errors" not in log,
            "A1 source-gate log contains an error")
    contract = load_bytes(CONTRACT.read_bytes(), CONTRACT.as_posix())
    require(contract.get("a1", {}).get("preferred_exception_list") == [],
            "A1 contract no longer prefers an empty exception list")
    closure = load_bytes(CLOSURE.read_bytes(), CLOSURE.as_posix())
    require(closure.get("status") == "passed-v1.12-release-closure-closure-only",
            "release closure was not green during A1")
    rows = side_effect_rows()
    return {
        "format": "lisp65-c2.3-v1.12-a1-source-gate-v1",
        "recorded_on": "2026-08-07",
        "status": "passed-check-source-empty-exception-list",
        "check_source": {
            "exit_code": 0,
            "exception_list": [],
            "required_witnesses": required,
            "log": bind(LOG),
        },
        "dated_write_side_effects": {
            "count": len(rows),
            "rows": rows,
            "classified_as_gate_exceptions": False,
            "tracked_receipts_restored_after_capture": True,
        },
        "authorities": {
            "contract": bind(CONTRACT),
            "closure": bind(CLOSURE),
            "driver": bind(Path(__file__).resolve()),
        },
        "accounting": {
            "product_bytes_changed": 0,
            "product_links": 0,
            "device_contacts": 0,
            "public_names_added": 0,
        },
        "claim_limit": (
            "Full Phase-A source hygiene and exact classification of six dated "
            "write side effects. No product, media, surface, link, device, Halt-1 "
            "or release claim."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write",))
    parser.parse_args()
    try:
        value = build()
        RECEIPT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
        print("c2-v112-release-a1: PASS check-source=green exceptions=0 "
              f"dated-side-effects={value['dated_write_side_effects']['count']}")
        return 0
    except (A1Error, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"c2-v112-release-a1: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
