#!/bin/sh
# Create a short-lived Claude worktree from origin/main.
#
# Usage:
#   scripts/create-claude-worktree.sh <topic>
#
# Example:
#   scripts/create-claude-worktree.sh ide-scroll-diagnosis
#
# This creates:
#   ../lisp65-work/claude-ide-scroll-diagnosis
# on branch:
#   claude/ide-scroll-diagnosis
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <topic-slug>" >&2
  echo "example: $0 ide-scroll-diagnosis" >&2
  exit 2
fi

topic="$1"
case "$topic" in
  *[!A-Za-z0-9._-]*|'')
    echo "error: topic must contain only A-Z, a-z, 0-9, dot, underscore or dash" >&2
    exit 2
    ;;
esac

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PARENT=$(cd "$ROOT/.." && pwd)
WORK_ROOT="$PARENT/lisp65-work"
WORKTREE="$WORK_ROOT/claude-$topic"
BRANCH="claude/$topic"

cd "$ROOT"

if [ -e "$WORKTREE" ]; then
  echo "error: worktree path already exists: $WORKTREE" >&2
  exit 1
fi

if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  echo "error: branch already exists: $BRANCH" >&2
  exit 1
fi

mkdir -p "$WORK_ROOT"
git fetch origin
git worktree add "$WORKTREE" -b "$BRANCH" origin/main

cat <<EOF
Claude worktree ready:
  path:   $WORKTREE
  branch: $BRANCH

Next:
  cd "$WORKTREE"
  git status --short --branch

After Codex integrates the branch:
  git -C "$ROOT" worktree remove "$WORKTREE"
EOF
