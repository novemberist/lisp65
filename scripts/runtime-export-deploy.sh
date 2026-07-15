#!/bin/sh
# AP8.2.3 standalone Runtime Export G4/G5 entry point.
#
# The Make targets use this thin entry point as the same operator-facing path
# used for G5.  The Python contract verifies the sealed package and its
# manifest-bound symbol oracle before G5 can touch m65.  G4 remains a read-only
# offline plan.
set -eu

cd "$(dirname "$0")/.."
exec python3 tools/host-lisp/runtime_export_hw_oracle.py deploy "$@"
