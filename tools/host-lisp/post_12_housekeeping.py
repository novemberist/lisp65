#!/usr/bin/env python3
"""Verify the autonomous post-v1.2 housekeeping pass and write its receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
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
SEALED_COMMIT = "43cfeb94a8cc80c86b8ffd441f767d48ac53b297"
SEALED_SOURCE_SHA256 = (
    "02dc549d887b34011aa6965f5bf6f1f2854f9c1a1849dd6d0df1e0523099b503")
WITNESS_FORMAT = "lisp65-post-v1.2-housekeeping-witness-v2"
SEALED_ROWS = (
    "archived_legacy_fixtures", "baseline_commit", "claim_limit",
    "comment_go_forward", "elf_truth_migration", "format", "idea_store",
    "recorded_on", "status", "version",
)
LIVE_ROWS = {"bindings", "index_and_evidence"}


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


def repository_state_digest() -> str:
    """Bind tracked drift and non-ignored untracked files without changing them."""
    diff = subprocess.run(
        ["git", "diff", "--binary", "--no-ext-diff", "HEAD", "--"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(diff.returncode == 0,
            diff.stderr.decode(errors="replace").strip() or "git diff failed")
    others = subprocess.run(
        ["git", "ls-files", "-z", "--others", "--exclude-standard"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(
        others.returncode == 0,
        others.stderr.decode(errors="replace").strip()
        or "git ls-files for untracked files failed")

    digest = hashlib.sha256()
    digest.update(diff.stdout)
    for raw in sorted(item for item in others.stdout.split(b"\0") if item):
        relative = os.fsdecode(raw)
        path = ROOT / relative
        digest.update(raw)
        digest.update(b"\0")
        if path.is_symlink():
            digest.update(b"symlink\0")
            digest.update(os.fsencode(os.readlink(path)))
        elif path.is_file():
            digest.update(path.read_bytes())
        else:
            digest.update(b"non-file")
        digest.update(b"\0")
    return digest.hexdigest()


def require_repository_unchanged(before: str, after: str, label: str) -> None:
    require(
        after == before,
        f"{label} changed repository state while used as a read-only subcheck")


def run_gate(command: list[str], label: str) -> str:
    before = repository_state_digest()
    process = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(process.returncode == 0,
            f"{label} failed: {process.stdout.strip()}")
    after = repository_state_digest()
    require_repository_unchanged(before, after, label)
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


def collect_living() -> dict[str, Any]:
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
        "elf_truth_migration": migration,
        "comment_language": comments,
        "index_and_evidence": {
            "document_index": document_index,
            "promotion_register": promotion,
            **evidence_consistency(),
        },
        "archived_fixture_paths_present": len(ARCHIVED_FIXTURES),
        "active_old_path_references": len(stale),
        "idea_store_required_phrases": 5,
    }


def sealed_source() -> dict[str, Any]:
    relative = RECEIPT.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{SEALED_COMMIT}:{relative}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
    require(sha256(raw) == SEALED_SOURCE_SHA256,
            "sealed housekeeping source identity drift")
    source = json.loads(raw)
    return {"binding": {"authority": "git-blob", "commit": SEALED_COMMIT,
                         "path": relative, "bytes": len(raw),
                         "sha256": sha256(raw)},
            "witness": {name: source[name] for name in SEALED_ROWS}}


def validate_witness(value: dict[str, Any]) -> None:
    expected = sealed_source()
    require(set(value) == {"format", "version", "sealed_source", "witness"}
            and value.get("format") == WITNESS_FORMAT
            and value.get("version") == 2,
            "housekeeping witness schema admits living rows")
    require(not (set(value) & LIVE_ROWS)
            and not (set(value.get("witness", {})) & LIVE_ROWS),
            "living repository value persisted in sealed witness")
    require(value.get("sealed_source") == expected["binding"]
            and value.get("witness") == expected["witness"],
            "sealed housekeeping witness row drift")


def check() -> dict[str, Any]:
    require(RECEIPT.is_file(), "housekeeping witness missing")
    witness = json.loads(RECEIPT.read_text(encoding="utf-8"))
    validate_witness(witness)
    return {"witness": witness, "living": collect_living()}


def selftest() -> None:
    base = json.loads(RECEIPT.read_text(encoding="utf-8"))
    cases = []

    living = json.loads(json.dumps(base))
    living["bindings"] = {"verifier": {"sha256": "live"}}
    cases.append(living)

    changed = json.loads(json.dumps(base))
    changed["witness"]["status"] = "rewritten"
    cases.append(changed)

    rejected = 0
    for candidate in cases:
        try:
            validate_witness(candidate)
        except HousekeepingError:
            rejected += 1
    try:
        parse_args(["--write"])
    except HousekeepingError:
        rejected += 1
    require(rejected == 3, f"witness/derivation mutations accepted: {3-rejected}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    arguments = list(sys.argv[1:] if argv is None else argv)
    require("--write" not in arguments,
            "--write was removed: living housekeeping facts are derived")
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    return parser.parse_args(arguments)


def main() -> int:
    args = parse_args()
    if args.selftest:
        selftest()
        print("post-v1.2-housekeeping: SELFTEST PASS mutations=3 "
              "sealed-witness=pass living-persistence=forbidden write=removed")
        return 0
    value = check()
    print(
        "post-v1.2-housekeeping: PASS "
        "evidence="
        f"{value['living']['index_and_evidence']['tracked_json_receipts_excluding_this_receipt']} "
        "elf-consumers=6 archived-fixtures=2 witness=sealed living=derived")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HousekeepingError as error:
        print(f"post-v1.2-housekeeping: FAIL {error}")
        raise SystemExit(1)
