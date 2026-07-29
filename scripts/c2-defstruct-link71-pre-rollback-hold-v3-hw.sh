#!/bin/sh
# Mount is reset into place first; later product load must preserve it.
set -eu
cd "$(dirname "$0")/.."
export C2_PRE_ROLLBACK_OUT=build/post-promotion/link71-defstruct-header-crc-domain/pre-rollback-hold-v3-mount-preserved-NONPROMOTABLE
export C2_PRE_ROLLBACK_PY=tools/host-lisp/c2_defstruct_link71_pre_rollback_hold_v3.py
export C2_PRESERVE_MOUNT_AFTER_FTP_RESET=1
exec sh scripts/c2-defstruct-link71-pre-rollback-hold-v2-hw.sh "$@"
