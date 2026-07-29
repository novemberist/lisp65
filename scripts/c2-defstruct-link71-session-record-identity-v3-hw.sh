#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

export C2_DEFSTRUCT_HW_OUT=build/post-promotion/link71-defstruct-session-record-identity-hardware-replay-v3
export C2_DEFSTRUCT_SESS_OUT=$C2_DEFSTRUCT_HW_OUT
export C2_DEFSTRUCT_SESS_RECEIPT=tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-link71-defstruct-session-record-identity-hardware-v3-receipt.json
export C2_DEFSTRUCT_SESS_REMOTE=L71SES3.D81
export C2_DEFSTRUCT_HW_PY=tools/host-lisp/c2_defstruct_link71_session_record_identity_hw.py
export C2_DEFSTRUCT_HW_CONFIG=config/c2.2-defstruct-link71-session-record-identity-replay.json
export C2_DEFSTRUCT_HW_LABEL=Link-71-session-record-identity-v3
export C2_AUTO_MOUNT_MEDIA=1
export C2_PRESERVE_MOUNT_AFTER_FTP_RESET=1
exec sh scripts/c2-defstruct-link70-hw.sh "${1:-start}"
