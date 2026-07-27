#!/bin/sh
# Link-60 C1 cutpoints 3/4; cutpoints 1/2 retain accepted evidence.
set -eu

expect_cutpoint=0
for arg in "$@"; do
  if [ "$expect_cutpoint" -eq 1 ]; then
    case "$arg" in
      1|2)
        echo "cutpoints 1 and 2 already have accepted evidence; this appointment runs 3 and 4" >&2
        exit 2
        ;;
    esac
  fi
  if [ "$arg" = "--cutpoint" ]; then
    expect_cutpoint=1
  else
    expect_cutpoint=0
  fi
done

C2_C1_FREEZER_OUT=build/c2.2/c1-freezer-hardware-link60-cutpoints3-4-NONPROMOTABLE
C2_C1_FREEZER_PY=tools/host-lisp/c2_c1_freezer_hw_fixture_link60.py
export C2_C1_FREEZER_OUT C2_C1_FREEZER_PY
exec "$(dirname "$0")/c2-c1-freezer-hw.sh" "$@"
