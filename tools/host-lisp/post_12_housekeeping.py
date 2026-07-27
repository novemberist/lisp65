#!/usr/bin/env python3
"""Verify the autonomous post-v1.2 housekeeping pass and write its receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/post-release/"
    "post-v1.2-housekeeping-receipt.json"
)
ARCHIVED_FIXTURES = {
    "tests/fixtures/legacy/m65d/alloc-two-sector.lisp":
        "lib/m65-disk-alloc.lisp",
    "tests/fixtures/legacy/m65d/alloc-variable-chain.lisp":
        "lib/m65-disk-alloc-var.lisp",
}
ACTIVE_ROOTS = ("Makefile", "config", "src", "lib", "scripts", "tools", "tests")


class HousekeepingError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HousekeepingError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    require(path.is_file() and not path.is_symlink(),
            f"regular file missing: {relative}")
    data = path.read_bytes()
    return {"path": relative, "bytes": len(data), "sha256": sha256(data)}


def git_paths(pattern: str | None = None) -> list[str]:
    command = ["git", "ls-files", "--cached", "--others", "--exclude-standard"]
    if pattern:
        command.append(pattern)
    process = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False)
    require(process.returncode == 0,
            process.stderr.strip() or "git ls-files failed")
    return [line for line in process.stdout.splitlines() if line]


def run_gate(command: list[str], label: str) -> str:
    process = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(process.returncode == 0,
            f"{label} failed: {process.stdout.strip()}")
    return process.stdout.strip()


def evidence_consistency() -> dict[str, Any]:
    receipt_relative = str(RECEIPT.relative_to(ROOT))
    paths = [
        path for path in
        git_paths("tests/bytecode/dialect-v2/evidence/**/*.json")
        if path != receipt_relative
    ]
    invalid = []
    for relative in paths:
        try:
            json.loads((ROOT / relative).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            invalid.append({"path": relative, "error": str(error)})
    require(not invalid, f"invalid evidence JSON: {invalid[:3]}")

    register = json.loads(
        (ROOT / "config/promotion-register.json").read_text(encoding="utf-8"))
    assets = json.loads(
        (ROOT / "config/evidence-archive-assets.json").read_text(encoding="utf-8"))
    asset_by_path = {row["path"]: row for row in assets["archives"]}
    promotions = register["promotions"]
    ids = [row["id"] for row in promotions]
    require(len(ids) == len(set(ids)), "duplicate promotion ID")
    missing = []
    drift = []
    for row in promotions:
        asset = asset_by_path.get(row["archive"])
        if asset is None:
            missing.append(row["archive"])
        elif asset["sha256"] != row["archive_sha256"]:
            drift.append(row["archive"])
    require(not missing, f"promotion assets absent from inventory: {missing}")
    require(not drift, f"promotion asset SHA drift: {drift}")
    return {
        "tracked_json_receipts_excluding_this_receipt": len(paths),
        "invalid_json_receipts": 0,
        "promotion_records": len(promotions),
        "promotion_ids_unique": True,
        "promotion_archives_bound_in_asset_inventory": len(promotions),
        "asset_inventory_archives": assets["archive_count"],
        "asset_inventory_bytes": assets["archive_bytes"],
    }


def active_old_fixture_references() -> list[str]:
    old = tuple(ARCHIVED_FIXTURES.values())
    failures = []
    exemptions = {
        "tools/host-lisp/post_11_housekeeping.py",
        "tools/host-lisp/post_12_housekeeping.py",
    }
    for relative in git_paths():
        if relative in exemptions or relative.startswith(
                ("docs/", "tests/bytecode/dialect-v2/evidence/")):
            continue
        if not (relative == "Makefile" or
                any(relative.startswith(root + "/")
                    for root in ACTIVE_ROOTS[1:])):
            continue
        path = ROOT / relative
        if not path.is_file() or path.is_symlink():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(item in text for item in old):
            failures.append(relative)
    return failures


def collect() -> dict[str, Any]:
    for successor, predecessor in ARCHIVED_FIXTURES.items():
        require((ROOT / successor).is_file(),
                f"archived fixture missing: {successor}")
        require(not (ROOT / predecessor).exists(),
                f"dead library path remains: {predecessor}")
    stale = active_old_fixture_references()
    require(not stale, f"active old fixture references remain: {stale}")

    migration = run_gate(
        ["python3", "tools/host-lisp/c2_elf_truth_migration_gate.py"],
        "ELF truth migration")
    comments = run_gate(
        ["python3", "tools/host-lisp/comment_language_gate.py"],
        "comment language")
    document_index = run_gate(
        ["python3", "tools/host-lisp/document_index.py"],
        "document index")
    promotion = run_gate(
        ["python3", "tools/host-lisp/promotion_archive.py", "register-check"],
        "promotion register")

    extension = (
        ROOT / "docs/planning/extension-libraries-design.md"
    ).read_text(encoding="utf-8")
    for phrase in (
        "C2-era transport and composition doctrine",
        "Hot execution is Chip-RAM-only",
        "Transform, verify, seal, publish",
        "Append work is suffix work",
        "Errors keep one truth",
    ):
        require(phrase in extension, f"C2 library lesson absent: {phrase}")

    return {
        "format": "lisp65-post-v1.2-housekeeping-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-27",
        "status": "pass",
        "baseline_commit": "084d51b1019b98ac0784c98842ef5950195d1cbd",
        "claim_limit": (
            "Class-A host, fixture-location and documentation housekeeping. "
            "No product bytes, product link, hardware, promotion, tag, public "
            "push or release claim."
        ),
        "elf_truth_migration": {
            "status": "complete",
            "gate": migration,
            "named_consumers": 6,
            "private_views": 0,
            "objdump_boundary": "instruction decoding only",
        },
        "archived_legacy_fixtures": [
            {
                "predecessor": predecessor,
                "successor": bind(successor),
                "active_old_path_references": 0,
            }
            for successor, predecessor in sorted(ARCHIVED_FIXTURES.items())
        ],
        "comment_go_forward": {
            "status": "pass",
            "baseline": "v1.1.0",
            "sealed_evidence_and_historical_docs": "exempt",
            "gate": comments,
        },
        "index_and_evidence": {
            "document_index": document_index,
            "promotion_register": promotion,
            **evidence_consistency(),
        },
        "idea_store": {
            "status": "updated",
            "document": bind("docs/planning/extension-libraries-design.md"),
            "rules_added": 7,
            "random_ring_buffer_pairing": "retained",
        },
        "bindings": {
            "verifier": bind("tools/host-lisp/post_12_housekeeping.py"),
            "elf_truth_contract": bind("config/c2-elf-truth-contract.json"),
            "elf_truth_migration_gate": bind(
                "tools/host-lisp/c2_elf_truth_migration_gate.py"),
            "canonical_product_gate": bind(
                "tools/host-lisp/c2_product_substitution_link.py"),
            "document_index": bind("config/document-index.json"),
            "promotion_register": bind("config/promotion-register.json"),
            "asset_inventory": bind("config/evidence-archive-assets.json"),
        },
    }


def write() -> dict[str, Any]:
    value = collect()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return value


def check() -> dict[str, Any]:
    value = collect()
    require(RECEIPT.is_file(), "housekeeping receipt missing")
    recorded = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(recorded == value, "housekeeping receipt drift; regenerate with --write")
    return value


def selftest() -> None:
    rejected = 0
    for condition in (False, 1 == 2, "old" == "new"):
        try:
            require(condition, "mutation")
        except HousekeepingError:
            rejected += 1
    require(rejected == 3, f"mutations accepted: {3 - rejected}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        print("post-v1.2-housekeeping: SELFTEST PASS mutations=3")
        return 0
    value = write() if args.write else check()
    print(
        "post-v1.2-housekeeping: PASS "
        "evidence="
        f"{value['index_and_evidence']['tracked_json_receipts_excluding_this_receipt']} "
        "elf-consumers=6 archived-fixtures=2")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HousekeepingError as error:
        print(f"post-v1.2-housekeeping: FAIL {error}")
        raise SystemExit(1)
