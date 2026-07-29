#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

export C2_DEFSTRUCT_HW_OUT=${C2_DEFSTRUCT_HW_OUT:-build/post-promotion/link73-vm-codebuf-owner/hardware-session}
export C2_DEFSTRUCT_HW_PY=tools/host-lisp/c2_defstruct_link73_vm_codebuf_owner_hw.py
export C2_DEFSTRUCT_HW_CONFIG=config/c2.2-defstruct-link73-vm-codebuf-owner-hardware-session.json
export C2_DEFSTRUCT_HW_LABEL=Link-73-owner
export C2_AUTO_MOUNT_MEDIA=${C2_AUTO_MOUNT_MEDIA:-0}
export C2_PRESERVE_MOUNT_AFTER_FTP_RESET=1
exec sh scripts/c2-defstruct-link70-hw.sh "${1:-start}"
