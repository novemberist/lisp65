#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

export C2_DEFSTRUCT_HW_OUT=build/post-promotion/link71-defstruct-product-identity-hardware-replay-v2
export C2_DEFSTRUCT_IDENTITY_OUT=$C2_DEFSTRUCT_HW_OUT
export C2_DEFSTRUCT_IDENTITY_RECEIPT=tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-link71-defstruct-product-identity-hardware-v2-receipt.json
export C2_DEFSTRUCT_IDENTITY_REMOTE=L71IDF2.D81
export C2_DEFSTRUCT_HW_PY=tools/host-lisp/c2_defstruct_link71_product_identity_hw.py
export C2_DEFSTRUCT_HW_CONFIG=config/c2.2-defstruct-link71-product-identity-replay.json
export C2_DEFSTRUCT_HW_LABEL=Link-71-product-identity-v2
export C2_AUTO_MOUNT_MEDIA=1
export C2_PRESERVE_MOUNT_AFTER_FTP_RESET=1
exec sh scripts/c2-defstruct-link70-hw.sh "${1:-start}"
