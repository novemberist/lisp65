#!/bin/sh
# Fresh v1.2.5 G5 from the exact sealed-R4/R5 medium.
set -eu
cd "$(dirname "$0")/.."

BASE=build/c2.2/v1.2.5-acceptance/r5 \
PY=tools/host-lisp/c2_v125_g5_hardware.py \
EXPECTED_BANNER='WORKBENCH 1.2.4' \
  exec scripts/c2-v121-g5-hw.sh "${1:-prepare}"
