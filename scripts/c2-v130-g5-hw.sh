#!/bin/sh
# Fresh v1.3.0 G5 from the exact sealed-R4/R5 medium.
set -eu
cd "$(dirname "$0")/.."

BASE=build/c2.3/v1.3.0-acceptance/r5 \
PY=tools/host-lisp/c2_v130_g5_hardware.py \
EXPECTED_BANNER='WORKBENCH 1.3.0' \
  exec scripts/c2-v121-g5-hw.sh "${1:-prepare}"
