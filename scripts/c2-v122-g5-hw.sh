#!/bin/sh
# Fresh v1.2.2 G5 plus the independent informational G2 timing rows.
set -eu
cd "$(dirname "$0")/.."

BASE=build/c2.2/v1.2.2-acceptance/r5 \
PY=tools/host-lisp/c2_v122_g5_hardware.py \
G2_PY=tools/host-lisp/c2_v122_g2_hardware.py \
G2_CONTRACT=config/c2.2-v1.2.2-g2-symbol-value-cost-session.json \
  exec scripts/c2-v121-g5-hw.sh "${1:-prepare}"
