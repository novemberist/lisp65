#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Check and materialize the curated lisp65 public source snapshot."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "config" / "public-export-policy.json"

PRIVATE_PATH_RE = re.compile(
    rb"(?:/(?:home|Users)/[A-Za-z0-9._-]+/|[A-Za-z]:\\Users\\[^\\\s]+)",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(rb"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
SECRET_RES = {
    "private key": re.compile(
        rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    ),
    "GitHub token": re.compile(
        rb"(?<![A-Za-z0-9_])(?:gh[pousr]_[A-Za-z0-9_]{20,}|"
        rb"github_pat_[A-Za-z0-9_]{20,})"
    ),
    "AWS access key": re.compile(rb"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])"),
    "OpenAI key": re.compile(
        rb"(?<![A-Za-z0-9_-])sk-(?:proj-)?[A-Za-z0-9_-]{20,}"
        rb"(?![A-Za-z0-9_-])"
    ),
    "Anthropic key": re.compile(
        rb"(?<![A-Za-z0-9_-])sk-ant-[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])"
    ),
    "Slack token": re.compile(
        rb"(?<![A-Za-z0-9-])xox[baprs]-[A-Za-z0-9-]{10,}"
        rb"(?![A-Za-z0-9-])"
    ),
    "Google API key": re.compile(
        rb"(?<![A-Za-z0-9_-])AIza[0-9A-Za-z_-]{30,}(?![A-Za-z0-9_-])"
    ),
}


class PolicyError(RuntimeError):
    """Raised when the candidate violates the public-export policy."""


def load_policy(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        policy = json.load(handle)
    if policy.get("format") != "lisp65-public-export-policy-v1":
        raise PolicyError(f"unsupported policy format in {path}")
    return policy


def tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    return sorted(
        item.decode("utf-8", "surrogateescape")
        for item in result.stdout.split(b"\0")
        if item
    )


def matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def selected_paths(policy: dict) -> list[str]:
    included = policy["include"]
    excluded = policy["exclude"]
    return [
        path
        for path in tracked_paths()
        if matches(path, included) and not matches(path, excluded)
    ]


def scan_data(path: str, data: bytes, policy: dict) -> list[str]:
    errors: list[str] = []
    gates = policy["gates"]

    if len(data) > gates["maximum_file_bytes"]:
        errors.append(
            f"file exceeds {gates['maximum_file_bytes']} bytes: {path} ({len(data)})"
        )
    if gates["forbid_git_lfs_pointers"] and data.startswith(
        b"version https://git-lfs.github.com/spec/v1\n"
    ):
        errors.append(f"Git LFS pointer selected: {path}")
    if gates["forbid_elf_binaries"] and data.startswith(b"\x7fELF"):
        errors.append(f"ELF binary selected: {path}")

    if b"\0" in data[:8192]:
        return errors

    if gates["forbid_private_absolute_paths"] and PRIVATE_PATH_RE.search(data):
        errors.append(f"private absolute path found: {path}")

    if gates["forbid_non_fixture_email_addresses"]:
        allowed = {item.lower() for item in gates["allowed_email_domains"]}
        for match in EMAIL_RE.finditer(data):
            domain = match.group(1).decode("ascii", "ignore").lower()
            if domain not in allowed:
                errors.append(f"non-fixture email address found: {path}")
                break

    if gates["forbid_high_confidence_secret_patterns"]:
        for label, pattern in SECRET_RES.items():
            if pattern.search(data):
                errors.append(f"{label} pattern found: {path}")

    return errors


def scan_path(path: str, policy: dict) -> list[str]:
    full = ROOT / path
    if not full.is_file():
        return [f"selected path is not a regular file: {path}"]
    return scan_data(path, full.read_bytes(), policy)


def check(policy: dict) -> list[str]:
    paths = selected_paths(policy)
    errors: list[str] = []
    selected = set(paths)

    for required in policy["required"]:
        if required not in selected:
            errors.append(f"required path is not selected: {required}")

    for path in paths:
        errors.extend(scan_path(path, policy))

    if not paths:
        errors.append("public export selected no files")
    return errors


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_commit(policy: dict) -> str:
    """Return the newest commit that changed any exported path.

    Private-only status and evidence commits must not move public snapshot
    provenance when the exported tree itself is byte-identical.
    """
    paths = selected_paths(policy)
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", *paths],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    if not result:
        raise PolicyError("cannot identify a commit for the exported paths")
    return result


def worktree_is_clean(policy: dict) -> bool:
    """Return whether the exported closure, rather than private state, is clean."""
    paths = selected_paths(policy)
    for args in (("diff", "--quiet", "--"), ("diff", "--cached", "--quiet", "--")):
        result = subprocess.run(["git", *args, *paths], cwd=ROOT, check=False)
        if result.returncode not in {0, 1}:
            raise PolicyError(f"cannot inspect exported worktree closure: git {' '.join(args)}")
        if result.returncode == 1:
            return False
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout.split(b"\0")
    return not any(
        matches(name, policy["include"]) and not matches(name, policy["exclude"])
        for raw in untracked
        if raw
        for name in [raw.decode("utf-8", "surrogateescape")]
    )


def materialize(policy: dict, destination: Path, allow_dirty: bool) -> None:
    errors = check(policy)
    if errors:
        raise PolicyError("\n".join(errors))
    if not allow_dirty and not worktree_is_clean(policy):
        raise PolicyError("refusing to export a dirty public closure")
    if destination.exists() and any(destination.iterdir()):
        raise PolicyError(f"destination is not empty: {destination}")

    destination.mkdir(parents=True, exist_ok=True)
    manifest_files = []
    for relative in selected_paths(policy):
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        manifest_files.append(
            {
                "path": relative,
                "bytes": source.stat().st_size,
                "sha256": sha256(source),
            }
        )

    tree_digest = hashlib.sha256()
    for item in manifest_files:
        tree_digest.update(item["path"].encode("utf-8"))
        tree_digest.update(b"\0")
        tree_digest.update(item["sha256"].encode("ascii"))
        tree_digest.update(b"\n")

    manifest = {
        "format": "lisp65-public-source-manifest-v1",
        "source_commit": source_commit(policy),
        "source_tree_clean": worktree_is_clean(policy),
        "file_count": len(manifest_files),
        "tree_sha256": tree_digest.hexdigest(),
        "files": manifest_files,
    }
    (destination / "PUBLIC-SOURCE-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify_snapshot(root: Path) -> list[str]:
    manifest_path = root / "PUBLIC-SOURCE-MANIFEST.json"
    if not manifest_path.is_file():
        return [f"public source manifest not found: {manifest_path}"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"cannot read public source manifest: {error}"]
    if manifest.get("format") != "lisp65-public-source-manifest-v1":
        return ["unsupported public source manifest format"]

    errors: list[str] = []
    tree_digest = hashlib.sha256()
    for item in manifest.get("files", []):
        relative = item.get("path", "")
        path = root / relative
        if not relative or not path.is_file():
            errors.append(f"manifest file missing: {relative}")
            continue
        actual_sha = sha256(path)
        actual_bytes = path.stat().st_size
        if actual_sha != item.get("sha256") or actual_bytes != item.get("bytes"):
            errors.append(f"manifest binding mismatch: {relative}")
        tree_digest.update(relative.encode("utf-8"))
        tree_digest.update(b"\0")
        tree_digest.update(actual_sha.encode("ascii"))
        tree_digest.update(b"\n")
    if tree_digest.hexdigest() != manifest.get("tree_sha256"):
        errors.append("public source tree digest mismatch")
    if len(manifest.get("files", [])) != manifest.get("file_count"):
        errors.append("public source manifest file count mismatch")
    return errors


def compare_snapshot(policy: dict, root: Path) -> list[str]:
    """Compare a public checkout with a freshly materialized private export."""
    if not worktree_is_clean(policy):
        return ["refusing to compare from a dirty public closure"]

    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="lisp65-public-compare-") as temp:
        expected = Path(temp)
        materialize(policy, expected, allow_dirty=False)
        errors.extend(verify_snapshot(root))

        expected_paths = selected_paths(policy) + ["PUBLIC-SOURCE-MANIFEST.json"]
        for relative in expected_paths:
            wanted = expected / relative
            actual = root / relative
            if not actual.is_file():
                errors.append(f"public checkout file missing: {relative}")
            elif wanted.read_bytes() != actual.read_bytes():
                errors.append(f"private/public byte drift: {relative}")

        if (root / ".git").is_dir():
            result = subprocess.run(
                ["git", "ls-files", "-z"],
                cwd=root,
                check=True,
                stdout=subprocess.PIPE,
            )
            tracked = {
                item.decode("utf-8", "surrogateescape")
                for item in result.stdout.split(b"\0")
                if item
            }
            wanted = set(expected_paths)
            for relative in sorted(wanted - tracked):
                errors.append(f"public checkout path is not tracked: {relative}")
            for relative in sorted(tracked - wanted):
                errors.append(f"unexpected tracked public path: {relative}")

    return errors


def selftest(policy: dict) -> list[str]:
    cases = {
        "private-path": b"path=/home/" + b"alex/private/file\n",
        "email": b"owner=person" + b"@example.com\n",
        "lfs": b"version https://git-lfs.github.com/spec/v1\n",
        "elf": b"\x7fELF" + b"\0" * 32,
        "github-token": b"ghp_" + b"A" * 30,
        "aws-key": b"AKIA" + b"A" * 16,
        "openai-key": b"sk-proj-" + b"A" * 30,
        "slack-token": b"xoxb-" + b"1" * 20,
        "google-key": b"AIza" + b"A" * 32,
    }
    errors: list[str] = []
    for label, data in cases.items():
        if not scan_data(f"selftest-{label}", data, policy):
            errors.append(f"negative self-test was not rejected: {label}")
    if scan_data("selftest-safe", b"user=selftest@example.invalid\n", policy):
        errors.append("safe fixture email was rejected")

    with tempfile.TemporaryDirectory(prefix="lisp65-public-manifest-") as temp:
        root = Path(temp)
        fixture = root / "fixture.txt"
        fixture.write_text("public snapshot fixture\n", encoding="utf-8")
        digest = sha256(fixture)
        tree_digest = hashlib.sha256()
        tree_digest.update(b"fixture.txt\0" + digest.encode("ascii") + b"\n")
        manifest = {
            "format": "lisp65-public-source-manifest-v1",
            "file_count": 1,
            "tree_sha256": tree_digest.hexdigest(),
            "files": [
                {"path": "fixture.txt", "bytes": fixture.stat().st_size, "sha256": digest}
            ],
        }
        (root / "PUBLIC-SOURCE-MANIFEST.json").write_text(
            json.dumps(manifest) + "\n", encoding="utf-8"
        )
        if verify_snapshot(root):
            errors.append("valid manifest fixture was rejected")
        fixture.write_text("manipulated\n", encoding="utf-8")
        if not verify_snapshot(root):
            errors.append("manifest mutation self-test was not rejected")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("check", "list", "export", "verify", "compare", "selftest"),
        help="operation to perform",
    )
    parser.add_argument("destination", nargs="?", type=Path)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="permit a non-publishable smoke export from a dirty tree",
    )
    args = parser.parse_args()

    try:
        policy = load_policy(args.policy.resolve())
        if args.command == "list":
            print("\n".join(selected_paths(policy)))
            return 0
        if args.command == "check":
            errors = check(policy)
            if errors:
                raise PolicyError("\n".join(errors))
            paths = selected_paths(policy)
            total = sum((ROOT / path).stat().st_size for path in paths)
            print(f"public export policy: passed ({len(paths)} files, {total} bytes)")
            return 0
        if args.command == "selftest":
            errors = selftest(policy)
            if errors:
                raise PolicyError("\n".join(errors))
            print("public export self-test: passed (10 rejection classes)")
            return 0
        if args.command == "verify":
            root = args.destination.resolve() if args.destination else ROOT
            errors = verify_snapshot(root)
            if errors:
                raise PolicyError("\n".join(errors))
            print(f"public source manifest: passed ({root})")
            return 0
        if args.command == "compare":
            if args.destination is None:
                parser.error("compare requires a public checkout")
            root = args.destination.resolve()
            errors = compare_snapshot(policy, root)
            if errors:
                raise PolicyError("\n".join(errors))
            print(f"private/public snapshot comparison: passed ({root})")
            return 0
        if args.destination is None:
            parser.error("export requires a destination")
        materialize(policy, args.destination.resolve(), args.allow_dirty)
        print(f"public export written to {args.destination.resolve()}")
        return 0
    except (OSError, subprocess.CalledProcessError, PolicyError) as error:
        print(f"public export policy: failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
