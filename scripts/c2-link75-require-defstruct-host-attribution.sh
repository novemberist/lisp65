#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec python3 tools/host-lisp/c2_link75_require_defstruct_host_attribution.py "$@"
