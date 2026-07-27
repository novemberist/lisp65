#!/bin/sh
# One Link-66 appointment: defun witness, C1 Cutpoints 3/4, then measurements.
set -eu

C2_C1_FREEZER_OUT=build/c2.2/c1-bundled-session-hardware-link66-NONPROMOTABLE
C2_C1_FREEZER_PY=tools/host-lisp/c2_c1_bundled_session_hw_fixture_link66.py
C2_C1_BUNDLED_SESSION=1
export C2_C1_FREEZER_OUT C2_C1_FREEZER_PY C2_C1_BUNDLED_SESSION
exec "$(dirname "$0")/c2-c1-freezer-hw.sh" "$@"
