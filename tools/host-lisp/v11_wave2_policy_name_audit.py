#!/usr/bin/env python3
"""Bind the 17 policy-review names and the prepared 16-name revocation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/v11-wave2-policy-name-revocation.json"
MEASUREMENT = ROOT / "docs/planning/measurements/v1.1-prewave-measurements.json"
IDE_SOURCES = tuple(ROOT / f"lib/{name}" for name in (
    "ide-status.lisp",
    "ide-syntax.lisp",
    "ide-buffer.lisp",
    "ide-ui.lisp",
    "ide-disk.lisp",
))
IDE_SOURCE = ROOT / "lib/ide-ui.lisp"
IDE_DISK_SOURCE = ROOT / "lib/ide-disk.lisp"
MANIFESTS = tuple(ROOT / f"build/bytecode/dialect-v2/libs/{name}.manifest.json"
                  for name in ("ide", "idex", "m65d"))
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "v11-wave2-policy-name-audit-receipt.json"
)


class AuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def binding(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": rel(path), "bytes": len(data), "sha256": sha(data)}


def byte_cost(names: set[str]) -> int:
    return sum(len(name.encode("utf-8")) + 1 for name in names)


def defun_body(source: str, name: str, next_name: str) -> str:
    start = source.find(f"(defun {name} ")
    end = source.find(f"(defun {next_name} ", start + 1)
    require(start >= 0 and end > start, f"cannot isolate {name}")
    return source[start:end]


def collect() -> dict[str, Any]:
    contract = load(CONTRACT)
    measurement = load(MEASUREMENT)
    measured = measurement["measurements"]["3_export_only_interning"][
        "policy_review_candidates"
    ]
    expected = set(measured["names"])
    command_rows = contract["classification"]["command_tokens"]
    command_names = {row["name"] for row in command_rows}
    revoked = command_names | {contract["classification"]["private_state"]["name"]}
    retained = contract["classification"]["retained_kind_symbol"]["name"]
    require(len(expected) == measured["symbols"] == 17
            and measured["namepool_bytes"] == 191,
            "prewave policy-review baseline drift")
    require(len(command_rows) == len(command_names) == 15,
            "command token set must contain exactly 15 unique names")
    require(len({int(row["id"]) for row in command_rows}) == 15,
            "command token IDs must be unique")
    require(revoked | {retained} == expected and not revoked & {retained},
            "owner classification does not close all 17 names")
    require(byte_cost(revoked) == 182 and byte_cost({retained}) == 9,
            "namepool recovery arithmetic drift")
    require(len(contract["echo_cases"]) == 18
            and len(set(contract["echo_cases"])) == 18,
            "echo-case plan must contain 18 unique cases")

    sources = IDE_SOURCE.read_text(encoding="utf-8")
    disk_source = IDE_DISK_SOURCE.read_text(encoding="utf-8")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in IDE_SOURCES)
    launcher = defun_body(sources, "%ide-command-named", "%ide-execute-command-key")
    require("string-ref" in launcher and "intern" not in launcher.lower(),
            "M-x launcher is not direct String-to-ID")
    # Bind the launcher as it exists today.  In particular, the displayed
    # "save-buffer" command maps to command 1001; the internal write-file
    # token classified by this audit is a separate dispatcher datum and is
    # not an M-x spelling.
    launcher_ids = {
        "find-file": 1002,
        "save-buffer": 1001,
        "compile-load": 1008,
        "goto-line": 1012,
        "eval-buffer": 1014,
    }
    for displayed, wanted in launcher_ids.items():
        require(re.search(rf"\)\s+{wanted}(?:\s|\))", launcher) is not None,
                f"M-x launcher lost {displayed} numeric ID {wanted}")
    command_names_body = defun_body(sources, "ide-command-names", "%ide-command-named")
    for displayed in ("find-file", "save-buffer", "compile-load", "goto-line", "eval-buffer"):
        require(f'"{displayed}"' in command_names_body,
                f"M-x display String missing: {displayed}")

    occurrences = {}
    for name in sorted(revoked | {retained}):
        count = len(re.findall(re.escape(name), combined))
        require(count > 0, f"classified name absent from IDE sources: {name}")
        require(f"(defun {name} " not in combined,
                f"classified data token is unexpectedly a function: {name}")
        occurrences[name] = count
    require("(defun ide-buffers " in sources
            and "(quote *ide-buffers*)" in sources,
            "private buffer-state/value-cell seam drift")
    require("(function-kind (quote m65d-save)) (quote bytecode)" in disk_source,
            "1.1-G bytecode-kind seam drift")

    manifests = [load(path) for path in MANIFESTS]
    interned = set().union(*(set(item["cost"]["symbol_names"]) for item in manifests))
    require(expected <= interned, "current baseline no longer contains all 17 policy names")
    exported = set().union(*(set(item.get("exports", [])) |
                             set(item.get("late_bound_exports", [])) |
                             set(item.get("provides", [])) for item in manifests))
    require(not revoked & exported, "a revoked name is an exported library API")

    return {
        "format": "lisp65-v11-wave2-policy-name-audit-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-18",
        "status": "prepared-no-product-change-awaiting-wave2-repin",
        "claim_limit": contract["claim_limit"],
        "bindings": {
            "contract": binding(CONTRACT),
            "measurement": binding(MEASUREMENT),
            "ide_sources": [binding(path) for path in IDE_SOURCES],
            "manifests": [binding(path) for path in MANIFESTS],
        },
        "baseline": {
            "policy_review_names": sorted(expected),
            "symbols": 17,
            "namepool_bytes": 191,
            "all_present_in_current_standard_composition": True,
        },
        "owner_classification": {
            "revoked_after_wave2": sorted(revoked),
            "revoked_symbols": 16,
            "projected_namepool_recovery_bytes": 182,
            "retained": retained,
            "retained_namepool_bytes": 9,
            "source_occurrences": occurrences,
        },
        "m_x": {
            "mapping": "String-to-numeric-ID",
            "runtime_intern": False,
            "display_to_id": launcher_ids,
            "display_strings_unchanged": [
                "find-file", "save-buffer", "compile-load", "goto-line", "eval-buffer"
            ],
        },
        "implementation_plan": {
            "private_state": "reuse ide-buffers value cell under Lisp-2",
            "command_ids": command_rows,
            "echo_cases": contract["echo_cases"],
            "receipt_regeneration": contract["required_regeneration"],
            "product_identity_change_now": False,
            "product_identity_change_at_wave2_repin": True,
        },
    }


def write() -> dict[str, Any]:
    result = collect()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def check() -> dict[str, Any]:
    actual = load(RECEIPT)
    expected = collect()
    require(actual == expected, "policy-name audit receipt drift")
    return actual


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "check"))
    args = parser.parse_args()
    value = write() if args.command == "collect" else check()
    owner = value["owner_classification"]
    print("v11-wave2-policy-name-audit: PASS prepared "
          f"revoke={owner['revoked_symbols']} "
          f"namepool={owner['projected_namepool_recovery_bytes']} retained=bytecode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
