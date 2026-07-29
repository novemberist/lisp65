#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec python3 tools/host-lisp/c2_link75_real_require_resolver_host.py "$@"
