#!/bin/sh
# Prepare/verify the product-first Link-75 completion appointment.
set -eu
cd "$(dirname "$0")/.."
exec python3 tools/host-lisp/c2_link75_bundled_completion_prepare.py "${1:-prepare}"
