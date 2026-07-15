#!/bin/sh
# Run xmega65 with timeout hardening and token-based cleanup.
#
# Usage:
#   scripts/xmega65-safe-run.sh TOKEN TIMEOUT_SECONDS EMULATOR [xmega65 args...]
#
# TOKEN must be a unique string present in the xmega65 command line, typically
# the absolute -dumpmem or -screenshot path for this smoke.  Cleanup also owns
# a token-matching podman wrapper: distrobox xmega65 can exit while leaving its
# podman exec stopped and holding the container storage locks.
set -eu

if [ "$#" -lt 3 ]; then
  echo "usage: $0 token timeout-seconds emulator [args...]" >&2
  exit 2
fi

ROOT=$(cd "$(dirname "$0")/.." && pwd)
token="$1"
timeout_seconds="$2"
emulator="$3"
shift 3

cleanup() {
  python3 "$ROOT/scripts/kill-xmega65-by-token.py" "$token" >&2 || true
}

on_signal() {
  code="$1"
  cleanup
  exit "$code"
}

trap cleanup EXIT
trap 'on_signal 129' HUP
trap 'on_signal 130' INT
trap 'on_signal 143' TERM

kill_after="${XMEGA65_KILL_AFTER:-5s}"

set +e
if timeout --help 2>/dev/null | grep -q -- '--kill-after'; then
  timeout --kill-after="$kill_after" "$timeout_seconds" "$emulator" "$@"
else
  timeout "$timeout_seconds" "$emulator" "$@"
fi
status=$?
set -e

cleanup
trap - EXIT HUP INT TERM
exit "$status"
