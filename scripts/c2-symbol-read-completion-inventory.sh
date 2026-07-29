#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec python3 tools/host-lisp/c2_symbol_read_completion_inventory.py "$@"
