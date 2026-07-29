#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

export C2_DEFSTRUCT_HW_OUT=${C2_DEFSTRUCT_HW_OUT:-build/post-promotion/link72-stz-semantics/hardware-session}
export C2_DEFSTRUCT_HW_PY=tools/host-lisp/c2_defstruct_link72_stz_hw.py
export C2_DEFSTRUCT_HW_CONFIG=config/c2.2-defstruct-link72-stz-hardware-session.json
export C2_DEFSTRUCT_HW_LABEL=Link-72-STZ
export C2_AUTO_MOUNT_MEDIA=${C2_AUTO_MOUNT_MEDIA:-0}
export C2_PRESERVE_MOUNT_AFTER_FTP_RESET=1
exec sh scripts/c2-defstruct-link70-hw.sh "${1:-start}"
