#!/usr/bin/env python3
"""Verify and resolve evidence-preserving Git transport rewrites."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LEGACY = ROOT / "config/history-transport-rewrite.json"
CURRENT = ROOT / "config/history-transport-map-20260718.json"
ASSETS = ROOT / "config/evidence-archive-assets.json"
PUSH_RECEIPT = (
    ROOT
    / "tests/bytecode/dialect-v2/evidence/post-release/"
    "history-transport-rewrite-push-receipt.json"
)
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")


class RewriteError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RewriteError(message)


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RewriteError(f"cannot load {label}: {exc}") from exc
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        raise RewriteError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def git_json(commit: str, path: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(git("show", f"{commit}:{path}"))
    except json.JSONDecodeError as exc:
        raise RewriteError(f"cannot load {label}: {exc}") from exc
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def commit_exists(value: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{value}^{{commit}}"], cwd=ROOT,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    return result.returncode == 0


def mapping() -> dict[str, str]:
    result: dict[str, str] = {}
    if LEGACY.is_file():
        legacy = load(LEGACY, "legacy transport contract")
        rows = legacy.get("mapping", [])
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    old, new = row.get("old_commit"), row.get("new_commit")
                    if isinstance(old, str) and isinstance(new, str):
                        result[old] = new
    if CURRENT.is_file():
        current = load(CURRENT, "current transport map")
        rows = current.get("mapping", [])
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    old, new = row.get("old_commit"), row.get("new_commit")
                    if isinstance(old, str) and isinstance(new, str):
                        result[old] = new
    return result


def resolve_commit(value: str) -> str:
    """Resolve a recording-time evidence identity to its current transport ID."""
    if SHA40.fullmatch(value) is None:
        return value
    aliases = mapping()
    seen: set[str] = set()
    while value in aliases:
        require(value not in seen, "transport alias cycle")
        seen.add(value)
        value = aliases[value]
    return value


def verify() -> dict[str, Any]:
    value = load(CURRENT, "current transport map")
    require(value.get("format") == "lisp65-history-transport-map-v2", "format drift")
    require(value.get("version") == 2, "version drift")
    require(value.get("status") == "owner-approved-complete", "status drift")
    require(value.get("decision_date") == "2026-07-18", "decision date drift")
    require(
        value.get("reason") == "archives-to-release-assets-and-remove-oversized-git-blobs",
        "reason drift",
    )
    require(
        value.get("removed_path_rules") == ["*.tar.gz", "docs/reference/mega65-book.pdf"],
        "removed path rules drift",
    )
    require(value.get("asset_registry") == "config/evidence-archive-assets.json", "asset registry drift")
    require(
        value.get("claims") == {
            "archive_bytes_changed": False,
            "git_transport_ids_changed": True,
            "old_commit_ids_resolve_via_this_map": True,
            "product_bytes_changed": False,
            "semantic_history_changed": False,
        },
        "claim drift",
    )
    rows = value.get("mapping")
    require(isinstance(rows, list) and rows, "transport mapping missing")
    require(value.get("changed_commit_count") == len(rows), "mapping count drift")
    old_ids: list[str] = []
    new_ids: list[str] = []
    for index, row in enumerate(rows):
        require(
            isinstance(row, dict) and set(row) == {"new_commit", "old_commit"},
            f"mapping[{index}] schema drift",
        )
        old, new = row["old_commit"], row["new_commit"]
        require(SHA40.fullmatch(old) is not None and SHA40.fullmatch(new) is not None, "mapping SHA drift")
        require(old != new, f"mapping[{index}] is not a rewrite")
        old_ids.append(old)
        new_ids.append(new)
    require(old_ids == sorted(set(old_ids)), "old commit mapping order/uniqueness drift")
    require(len(new_ids) == len(set(new_ids)), "new commit mapping is not one-to-one")
    recording = value.get("recording_head")
    transport = value.get("transport_head")
    require(SHA40.fullmatch(str(recording)) is not None, "recording head malformed")
    require(SHA40.fullmatch(str(transport)) is not None, "transport head malformed")
    require(resolve_commit(str(recording)) == transport, "recording head alias drift")
    require(commit_exists(str(transport)), "transport head unavailable")
    require(
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", str(transport), "HEAD"], cwd=ROOT,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        ).returncode == 0,
        "transport head is not an ancestor of HEAD",
    )
    assets = load(ASSETS, "archive asset registry")
    require(assets.get("recording_head_before_transport_rewrite") == recording, "asset recording head drift")
    require(assets.get("transport_head_after_archive_removal") == transport, "asset transport head drift")
    push_receipt = load(PUSH_RECEIPT, "history rewrite push receipt")
    closure = push_receipt.get("closure_commit")
    require(SHA40.fullmatch(str(closure)) is not None, "rewrite closure commit malformed")
    require(commit_exists(str(closure)), "rewrite closure commit unavailable")
    frozen_assets = git_json(
        str(closure), "config/evidence-archive-assets.json",
        "rewrite-time archive asset registry",
    )
    require(
        frozen_assets.get("archive_count") == 39
        and frozen_assets.get("archive_bytes") == 8210842025,
        "rewrite-time asset totals drift",
    )
    frozen_rows = {
        row["path"]: row for row in frozen_assets.get("archives", [])
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }
    current_rows = {
        row["path"]: row for row in assets.get("archives", [])
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }
    require(len(frozen_rows) == 39, "rewrite-time archive inventory drift")
    require(
        all(current_rows.get(path) == row for path, row in frozen_rows.items()),
        "rewrite-time archive asset changed or disappeared",
    )
    require(
        assets.get("archive_count", 0) >= frozen_assets["archive_count"]
        and assets.get("archive_bytes", 0) >= frozen_assets["archive_bytes"],
        "archive inventory is not append-only",
    )
    legacy = load(LEGACY, "legacy transport contract")
    require(legacy.get("format") == "lisp65-history-transport-rewrite-v1", "legacy contract drift")
    for index, row in enumerate(legacy.get("mapping", [])):
        require(resolve_commit(row["old_commit"]) == resolve_commit(row["new_commit"]), f"legacy alias[{index}] drift")
    refs = value.get("rewritten_refs")
    require(isinstance(refs, list) and refs, "rewritten ref inventory missing")
    for index, row in enumerate(refs):
        require(
            isinstance(row, dict) and set(row) == {"new_object", "ref"}
            and isinstance(row["ref"], str) and SHA40.fullmatch(row["new_object"]) is not None,
            f"rewritten_refs[{index}] drift",
        )
        require(commit_exists(row["new_object"]), f"rewritten ref target unavailable: {row['ref']}")
    return {
        "mapped": len(rows),
        "recording": recording,
        "transport": transport,
        "refs": len(refs),
        "archives": assets["archive_count"],
        "bytes": assets["archive_bytes"],
        "rewrite_archives": frozen_assets["archive_count"],
    }


def install_replace_refs() -> int:
    aliases = mapping()
    missing = sorted({
        resolve_commit(new) for new in aliases.values()
        if not commit_exists(resolve_commit(new))
    })
    require(
        not missing,
        "complete branch/tag object graph required before alias bootstrap; "
        "run git fetch origin '+refs/heads/*:refs/remotes/origin/*' --tags "
        f"(missing={len(missing)} first={missing[0] if missing else 'none'})",
    )
    installed = 0
    for old, new in sorted(aliases.items()):
        target = resolve_commit(new)
        require(SHA40.fullmatch(old) is not None, f"invalid alias {old}")
        current = subprocess.run(
            ["git", "show-ref", "--hash", f"refs/replace/{old}"], cwd=ROOT,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
        )
        if current.returncode == 0 and current.stdout.strip() == target:
            continue
        git("update-ref", f"refs/replace/{old}", target)
        installed += 1
    print(
        f"history-transport-rewrite: REPLACE REFS PASS aliases={len(aliases)} "
        f"installed={installed}"
    )
    return installed


def main(argv: list[str] | None = None) -> int:
    try:
        args = sys.argv[1:] if argv is None else argv
        require(args in ([], ["verify"], ["install-replace-refs"]), "usage: history_transport_rewrite.py [verify|install-replace-refs]")
        if args == ["install-replace-refs"]:
            install_replace_refs()
        result = verify()
    except (RewriteError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"history-transport-rewrite: FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "history-transport-rewrite: PASS "
        f"mapped={result['mapped']} refs={result['refs']} archives={result['archives']} "
        f"rewrite-archives={result['rewrite_archives']} "
        f"bytes={result['bytes']} recording={str(result['recording'])[:12]} "
        f"transport={str(result['transport'])[:12]} semantic-delta=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
