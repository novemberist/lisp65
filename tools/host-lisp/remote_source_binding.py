#!/usr/bin/env python3
"""Bind new evidence to a source commit already present on the private mirror."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from history_transport_rewrite import resolve_commit


ROOT = Path(__file__).resolve().parents[2]
FORMAT = "lisp65-evidence-remote-source-binding-v1"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IMPLEMENTATION_RECEIPT = ROOT / "tests/bytecode/dialect-v2/evidence/post-release/remote-source-binding-gate-receipt.json"


class RemoteBindingError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RemoteBindingError(message)


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        raise RemoteBindingError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def committed_bytes(commit: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        raise RemoteBindingError(f"cannot read receipt authority: {path}")
    return result.stdout


def mirror_remote(preferred: str) -> str:
    names = git("remote").splitlines()
    if preferred in names:
        return preferred
    matches = []
    for name in names:
        url = git("remote", "get-url", name)
        if re.search(r"(?:github\.com[:/])novemberist/lisp65-proof(?:\.git)?$", url):
            matches.append(name)
    require(len(matches) == 1, "private proof mirror remote is unavailable or ambiguous")
    return matches[0]


def validate(value: Any, source_commit: str) -> dict[str, Any]:
    require(isinstance(value, dict), "remote source binding must be an object")
    require(set(value) == {
        "branch_ref", "format", "relation", "remote", "remote_head",
        "remote_transport_head", "source_commit", "source_transport_commit", "version",
    }, "remote source binding schema drift")
    require(value.get("format") == FORMAT and value.get("version") == 1, "remote source binding format drift")
    require(value.get("remote") == "github", "remote source binding authority drift")
    branch_ref = value.get("branch_ref")
    require(isinstance(branch_ref, str) and branch_ref.startswith("refs/heads/") and len(branch_ref) > 11, "remote branch ref drift")
    require(value.get("source_commit") == source_commit and SHA_RE.fullmatch(source_commit) is not None, "remote source identity drift")
    require(SHA_RE.fullmatch(str(value.get("source_transport_commit"))) is not None, "source transport identity drift")
    require(SHA_RE.fullmatch(str(value.get("remote_head"))) is not None, "remote head identity drift")
    require(SHA_RE.fullmatch(str(value.get("remote_transport_head"))) is not None, "remote transport head identity drift")
    require(value.get("relation") == "source-commit-is-remote-ancestor", "remote relation drift")
    return value


def capture(source_commit: str, *, remote: str = "github", branch: str | None = None) -> dict[str, Any]:
    require(SHA_RE.fullmatch(source_commit) is not None, "source commit must be a full SHA-1")
    source_transport = resolve_commit(source_commit)
    require(git("rev-parse", f"{source_transport}^{{commit}}") == source_transport, "source transport commit unavailable")
    if branch is None:
        branch = git("branch", "--show-current")
    require(bool(branch) and not branch.startswith("refs/"), "evidence recording requires a named local branch")
    branch_ref = f"refs/heads/{branch}"
    remote_name = mirror_remote(remote)
    rows = git("ls-remote", "--heads", remote_name, branch_ref).splitlines()
    require(len(rows) == 1, f"remote branch is unavailable or ambiguous: {branch_ref}")
    remote_head, observed_ref = rows[0].split()
    require(observed_ref == branch_ref and SHA_RE.fullmatch(remote_head) is not None, "remote head response drift")
    remote_transport = resolve_commit(remote_head)
    require(git("rev-parse", f"{remote_transport}^{{commit}}") == remote_transport, "remote transport head unavailable")
    require(
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", source_transport, remote_transport], cwd=ROOT,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        ).returncode == 0,
        f"evidence source commit is not present on {remote_name}/{branch}",
    )
    return validate({
        "format": FORMAT,
        "version": 1,
        "remote": remote,
        "branch_ref": branch_ref,
        "remote_head": remote_head,
        "remote_transport_head": remote_transport,
        "source_commit": source_commit,
        "source_transport_commit": source_transport,
        "relation": "source-commit-is-remote-ancestor",
    }, source_commit)


def selftest() -> None:
    source = "1" * 40
    value = {
        "format": FORMAT,
        "version": 1,
        "remote": "github",
        "branch_ref": "refs/heads/test",
        "remote_head": "2" * 40,
        "remote_transport_head": "2" * 40,
        "source_commit": source,
        "source_transport_commit": source,
        "relation": "source-commit-is-remote-ancestor",
    }
    validate(value, source)
    for label, mutation in (
        ("remote-head", {**value, "remote_head": "2" * 39}),
        ("source", {**value, "source_commit": "3" * 40}),
        ("relation", {**value, "relation": "unchecked"}),
    ):
        try:
            validate(mutation, source)
        except RemoteBindingError:
            continue
        raise RemoteBindingError(f"selftest accepted {label} mutation")
    print("remote-source-binding: SELFTEST PASS mutations=3")


def receipt_check() -> None:
    try:
        value = json.loads(IMPLEMENTATION_RECEIPT.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RemoteBindingError(f"cannot read implementation receipt: {exc}") from exc
    require(isinstance(value, dict), "implementation receipt must be an object")
    source = value.get("source_commit")
    require(
        value.get("format") == "lisp65-remote-source-binding-implementation-receipt-v1"
        and value.get("version") == 1 and value.get("status") == "passed"
        and value.get("recorded_on") == "2026-07-18"
        and isinstance(source, str) and SHA_RE.fullmatch(source) is not None
        and value.get("result") == "passed",
        "implementation receipt identity drift",
    )
    binding = validate(value.get("remote_source_binding"), source)
    require(binding["remote_head"] == source, "implementation receipt was not recorded at its source head")
    live = capture(source)
    require(live["branch_ref"] == binding["branch_ref"], "implementation receipt branch drift")
    rows = value.get("authorities")
    require(isinstance(rows, list) and len(rows) == 6, "implementation authority inventory drift")
    observed_paths: list[str] = []
    for row in rows:
        require(
            isinstance(row, dict) and set(row) == {"path", "sha256"}
            and isinstance(row["path"], str)
            and isinstance(row["sha256"], str) and SHA256_RE.fullmatch(row["sha256"]) is not None,
            "implementation authority row drift",
        )
        digest = hashlib.sha256(committed_bytes(source, row["path"])).hexdigest()
        require(digest == row["sha256"], f"implementation authority SHA drift: {row['path']}")
        observed_paths.append(row["path"])
    require(observed_paths == sorted(set(observed_paths)), "implementation authorities must be sorted and unique")
    require(value.get("emission") == {
        "promotion_manifest": "lisp65-promotion-archive-v3",
        "hardware_acceptance_manifest_version": 2,
        "field": "remote_source_binding.remote_head",
        "source_must_already_be_remote": True,
    }, "implementation emission contract drift")
    negative = value.get("negative_tests")
    require(
        isinstance(negative, dict) and len(negative) == 6
        and all(result is True for result in negative.values()),
        "implementation negative-test receipt drift",
    )
    transport = value.get("transport_gates")
    require(
        isinstance(transport, dict)
        and transport.get("git_blob_limit_bytes") == 50_000_000
        and transport.get("archive_suffix_rejected_from_index_and_history") == ".tar.gz"
        and transport.get("branch_ref_equality") == "passed"
        and transport.get("complete_tag_ref_equality") == "passed"
        and transport.get("tag_count") == 4,
        "implementation transport-gate receipt drift",
    )
    for key, path in (
        ("pre_commit_hook_sha256", ".githooks/pre-commit"),
        ("pre_push_hook_sha256", ".githooks/pre-push"),
        ("verified_push_script_sha256", "scripts/push-github-verified.sh"),
    ):
        require(
            transport.get(key) == hashlib.sha256(committed_bytes(source, path)).hexdigest(),
            f"implementation transport authority drift: {path}",
        )
    require(value.get("immutability") == {
        "historical_archives_amended": 0,
        "historical_missing_fields": "accepted-only-in-pre-policy-manifest-versions",
    }, "implementation immutability claim drift")
    print(
        "remote-source-binding: RECEIPT PASS "
        f"source={source} remote_head={binding['remote_head']} authorities={len(rows)} tags=4"
    )


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: remote_source_binding.py selftest|receipt-check|SOURCE_COMMIT", file=sys.stderr)
        return 2
    try:
        if sys.argv[1] == "selftest":
            selftest()
            return 0
        if sys.argv[1] == "receipt-check":
            receipt_check()
            return 0
        value = capture(sys.argv[1])
    except (OSError, UnicodeError, ValueError, RemoteBindingError) as exc:
        print(f"remote-source-binding: FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
