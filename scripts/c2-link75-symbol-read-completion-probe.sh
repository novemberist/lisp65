#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec python3 tools/host-lisp/c2_link75_symbol_read_completion_probe.py \
  "${1:-verify}"
