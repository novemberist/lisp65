#!/bin/sh
# Cutpoints 2..4 with a memory-driven hold; cutpoint 1 is already accepted.
set -eu

expect_cutpoint=0
for arg in "$@"; do
  if [ "$expect_cutpoint" -eq 1 ] && [ "$arg" = "1" ]; then
    echo "cutpoint 1 is already accepted; this appointment runs 2..4" >&2
    exit 2
  fi
  if [ "$arg" = "--cutpoint" ]; then
    expect_cutpoint=1
  else
    expect_cutpoint=0
  fi
done

C2_C1_FREEZER_OUT=build/c2.2/c1-freezer-memory-hold-hardware-link58-attempt5-NONPROMOTABLE
C2_C1_FREEZER_PY=tools/host-lisp/c2_c1_freezer_memory_hold_hw_fixture.py
export C2_C1_FREEZER_OUT C2_C1_FREEZER_PY
exec "$(dirname "$0")/c2-c1-freezer-hw.sh" "$@"
