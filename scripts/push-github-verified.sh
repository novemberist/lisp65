#!/bin/sh
set -eu

remote=${1:-github}
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
branch=${2:-$(git branch --show-current)}

if test -n "$(git status --porcelain)"; then
    echo "push-github-verified: FAIL: working tree is not clean" >&2
    exit 1
fi
if test -z "$branch"; then
    echo "push-github-verified: FAIL: detached HEAD requires an explicit branch" >&2
    exit 1
fi

python3 tools/host-lisp/history_transport_rewrite.py install-replace-refs
python3 tools/host-lisp/history_rewrite_push.py verify-receipt
python3 tools/host-lisp/evidence_archive_assets.py remote-check
python3 tools/host-lisp/evidence_archive_assets.py index-size-gate
python3 tools/host-lisp/evidence_archive_assets.py history-size-gate
python3 tools/host-lisp/promotion_archive.py register-check
git push "$remote" "HEAD:refs/heads/$branch"
git push "$remote" --tags

local_sha=$(git rev-parse HEAD)
remote_sha=$(git ls-remote --heads "$remote" "refs/heads/$branch" | awk '{print $1}')
if test "$local_sha" != "$remote_sha"; then
    echo "push-github-verified: FAIL: local=$local_sha remote=${remote_sha:-ABSENT}" >&2
    exit 1
fi
local_tags=$(git show-ref --tags --dereference | LC_ALL=C sort)
remote_tags=$(git ls-remote --tags "$remote" | awk '{print $1 " " $2}' | LC_ALL=C sort)
if test "$local_tags" != "$remote_tags"; then
    echo "push-github-verified: FAIL: local and remote tag refs differ" >&2
    echo "local tags:" >&2
    printf '%s\n' "$local_tags" >&2
    echo "remote tags:" >&2
    printf '%s\n' "$remote_tags" >&2
    exit 1
fi
tag_count=$(git show-ref --tags | wc -l | tr -d ' ')
if command -v git-lfs >/dev/null 2>&1; then
    lfs_pending=$(git lfs push --dry-run "$remote" HEAD)
    if test -n "$lfs_pending"; then
        echo "push-github-verified: FAIL: pending Git LFS objects" >&2
        exit 1
    fi
fi
echo "push-github-verified: PASS remote=$remote branch=$branch remote_head=$remote_sha tags=$tag_count sync=branch-and-tag-refs-equal"
