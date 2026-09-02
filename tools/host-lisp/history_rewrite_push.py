#!/usr/bin/env python3
"""Atomically publish the owner-approved archive-history transport rewrite."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "config/history-rewrite-push-plan-20260718.json"
RECEIPT = ROOT / "tests/bytecode/dialect-v2/evidence/post-release/history-transport-rewrite-push-receipt.json"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class PushError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PushError(message)


def run(*args: str, capture: bool = True) -> str:
    result = subprocess.run(
        list(args), cwd=ROOT, text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        raise PushError(result.stderr.strip() or f"command failed: {' '.join(args)}")
    return result.stdout.strip() if capture else ""


def remote_refs(remote: str) -> dict[str, str]:
    refs: dict[str, str] = {}
    for line in run("git", "ls-remote", "--heads", "--tags", remote).splitlines():
        object_id, ref = line.split()
        if not ref.endswith("^{}"):
            refs[ref] = object_id
    return refs


def mirror_remote(preferred: str) -> str:
    names = run("git", "remote").splitlines()
    if preferred in names:
        return preferred
    matches = []
    for name in names:
        url = run("git", "remote", "get-url", name)
        if re.search(r"(?:github\.com[:/])novemberist/lisp65-proof(?:\.git)?$", url):
            matches.append(name)
    require(len(matches) == 1, "private proof mirror remote is unavailable or ambiguous")
    return matches[0]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_sha(commit: str, path: str) -> str:
    data = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    require(data.returncode == 0, f"cannot read historical binding: {path}")
    return hashlib.sha256(data.stdout).hexdigest()


def load() -> dict[str, Any]:
    value = json.loads(PLAN.read_text(encoding="utf-8"))
    require(value.get("format") == "lisp65-history-rewrite-push-plan-v1", "format drift")
    require(value.get("version") == 1 and value.get("status") == "owner-approved-ready", "status drift")
    require(value.get("decision_date") == "2026-07-18", "decision date drift")
    rows = value.get("refs")
    require(isinstance(rows, list) and len(rows) == value.get("expected_ref_count") == 13, "ref count drift")
    names: list[str] = []
    for index, row in enumerate(rows):
        require(
            isinstance(row, dict)
            and set(row) == {"new_transport_object", "old_remote_object", "ref", "transport_base"},
            f"ref[{index}] schema drift",
        )
        require(row["ref"].startswith(("refs/heads/", "refs/tags/")), f"ref[{index}] namespace")
        require(SHA_RE.fullmatch(row["old_remote_object"]) is not None, f"ref[{index}] old SHA")
        require(SHA_RE.fullmatch(row["transport_base"]) is not None, f"ref[{index}] base SHA")
        require(row["new_transport_object"] == "HEAD" or SHA_RE.fullmatch(row["new_transport_object"]) is not None, f"ref[{index}] new SHA")
        names.append(row["ref"])
    require(names == sorted(set(names)), "push refs are not sorted and unique")
    return value


def gate(command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT, check=False)
    require(result.returncode == 0, f"pre-push gate failed: {' '.join(command)}")


def publish() -> dict[str, Any]:
    value = load()
    require(not run("git", "status", "--porcelain"), "working tree must be clean")
    gate([sys.executable, "tools/host-lisp/history_transport_rewrite.py", "install-replace-refs"])
    gate([sys.executable, "tools/host-lisp/evidence_archive_assets.py", "remote-check"])
    gate([sys.executable, "tools/host-lisp/evidence_archive_assets.py", "history-size-gate"])
    gate([sys.executable, "tools/host-lisp/promotion_archive.py", "register-check"])
    remote = value["remote"]
    before = remote_refs(remote)
    rows = value["refs"]
    expected_names = {row["ref"] for row in rows}
    require(set(before) == expected_names, "remote ref set changed since rewrite authorization")
    head = run("git", "rev-parse", "HEAD")
    command = ["git", "push", "--atomic", remote]
    expected_after: dict[str, str] = {}
    for row in rows:
        ref = row["ref"]
        require(before.get(ref) == row["old_remote_object"], f"remote lease drift: {ref}")
        source = head if row["new_transport_object"] == "HEAD" else row["new_transport_object"]
        require(
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", row["transport_base"], source],
                cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            ).returncode == 0,
            f"transport base is not preserved: {ref}",
        )
        command.append(f"--force-with-lease={ref}:{row['old_remote_object']}")
        command.append(f"{source}:{ref}")
        expected_after[ref] = source
    push = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    require(push.returncode == 0, push.stderr.strip() or "atomic rewrite push failed")
    after = remote_refs(remote)
    require(after == expected_after, "post-push remote ref equality failed")
    lfs = run("git", "lfs", "push", "--dry-run", remote, "HEAD")
    require(not lfs, "pending Git LFS objects remain")
    branch = value["branch"]
    run("git", "update-ref", f"refs/remotes/{remote}/{branch}", head)
    run("git", "branch", f"--set-upstream-to={remote}/{branch}", branch)
    return {"remote": remote, "branch": branch, "head": head, "refs": after}


def verify_receipt() -> None:
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(value.get("format") == "lisp65-history-rewrite-push-receipt-v1", "receipt format drift")
    require(value.get("version") == 1 and value.get("status") == value.get("result") == "passed", "receipt status drift")
    require(value.get("decision_date") == "2026-07-18" and value.get("remote") == "github", "receipt authority drift")
    require(value.get("branch_ref") == "refs/heads/codex/post-1.0-docs-cleanup", "receipt branch drift")
    require(value.get("remote_head") == value.get("closure_commit") == "aa0c90a2565d05384c81b80a09d78f45a966b1e5", "receipt closure drift")
    require(value.get("recording_head") == "0f7ba4d34d2f1508458ced081eabbbe6e6c6d504", "receipt recording head drift")
    require(value.get("transport_base") == "6fb5a3d0170f02a31fbd4a24cc6146319cb79062", "receipt transport base drift")
    require(value.get("transport_map") == "config/history-transport-map-20260718.json" and value.get("transport_map_sha256") == sha(ROOT / value["transport_map"]), "receipt transport map drift")
    require(value.get("push_plan") == "config/history-rewrite-push-plan-20260718.json" and value.get("push_plan_sha256") == sha(ROOT / value["push_plan"]), "receipt push plan drift")
    assets = value.get("archive_assets")
    require(isinstance(assets, dict) and assets.get("inventory") == "config/evidence-archive-assets.json", "receipt asset binding drift")
    require(
        assets.get("inventory_sha256")
        == git_sha(value["closure_commit"], assets["inventory"]),
        "receipt asset inventory SHA drift",
    )
    require(assets.get("archive_count") == 39 and assets.get("archive_bytes") == 8210842025 and assets.get("remote_asset_count") == 40, "receipt asset totals drift")
    require(assets.get("remote_digest_check") == "passed", "receipt remote asset claim drift")
    gates = value.get("gates")
    require(isinstance(gates, dict) and gates.get("atomic_force_with_lease") == "passed-13-of-13", "receipt atomic push drift")
    require(gates.get("local_remote_ref_equality") == "passed-13-of-13" and gates.get("semantic_delta") == 0, "receipt equality/semantic drift")
    observed = value.get("observed_refs")
    require(isinstance(observed, dict) and len(observed) == value.get("ref_count") == 13, "receipt ref inventory drift")
    require(observed.get(value["branch_ref"]) == value["remote_head"], "receipt branch observation drift")
    for ref, object_id in observed.items():
        require(ref.startswith(("refs/heads/", "refs/tags/")) and SHA_RE.fullmatch(object_id) is not None, f"receipt ref drift: {ref}")
        require(run("git", "cat-file", "-e", f"{object_id}^{{object}}") == "", f"receipt object unavailable: {ref}")
    current = remote_refs(mirror_remote(value["remote"]))
    require(value["branch_ref"] in current, "receipt branch disappeared remotely")
    require(
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", value["closure_commit"], current[value["branch_ref"]]],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        ).returncode == 0,
        "receipt closure commit is not on the current remote branch",
    )
    print(
        "history-rewrite-push: RECEIPT PASS "
        f"refs={value['ref_count']} remote_head={value['remote_head']} current={current[value['branch_ref']]}"
    )


def main() -> int:
    try:
        if sys.argv[1:] == ["verify-receipt"]:
            verify_receipt()
            return 0
        require(sys.argv[1:] in ([], ["publish"]), "usage: history_rewrite_push.py publish|verify-receipt")
        result = publish()
    except (OSError, UnicodeError, json.JSONDecodeError, PushError) as exc:
        print(f"history-rewrite-push: FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "format": "lisp65-history-rewrite-push-result-v1",
        "status": "passed",
        "remote": result["remote"],
        "branch": result["branch"],
        "remote_head": result["head"],
        "ref_count": len(result["refs"]),
        "refs": result["refs"],
        "sync": "local-and-remote-refs-equal",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
