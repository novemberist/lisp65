#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

export C2_DEFSTRUCT_HW_OUT=build/post-promotion/link71-defstruct-header-crc-domain/hardware-session
export C2_DEFSTRUCT_HW_PY=tools/host-lisp/c2_defstruct_link71_hw.py
export C2_DEFSTRUCT_HW_CONFIG=config/c2.2-defstruct-link71-hardware-session.json
export C2_DEFSTRUCT_HW_LABEL=Link-71
exec sh scripts/c2-defstruct-link70-hw.sh "${1:-start}"
