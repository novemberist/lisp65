#!/bin/sh
set -eu

remote=${1:-github}
branch=${2:-codex/ship-v4-remediation}
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"

if test -n "$(git status --porcelain)"; then
    echo "push-github-verified: FAIL: working tree is not clean" >&2
    exit 1
fi
if ! command -v git-lfs >/dev/null 2>&1; then
    echo "push-github-verified: FAIL: git-lfs is required" >&2
    exit 1
fi

python3 tools/host-lisp/history_transport_rewrite.py
git lfs fsck
git push "$remote" "HEAD:refs/heads/$branch"

local_sha=$(git rev-parse HEAD)
remote_sha=$(git ls-remote --heads "$remote" "refs/heads/$branch" | awk '{print $1}')
if test "$local_sha" != "$remote_sha"; then
    echo "push-github-verified: FAIL: local=$local_sha remote=${remote_sha:-ABSENT}" >&2
    exit 1
fi
echo "push-github-verified: PASS remote=$remote branch=$branch sha=$local_sha"
