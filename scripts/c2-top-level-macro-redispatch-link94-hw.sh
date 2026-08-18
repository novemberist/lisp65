#!/bin/sh
# Link-94 trace/restoration row using the corrected no-live-FTP choreography.
set -eu
cd "$(dirname "$0")/.."

export CONFIG=config/c2-top-level-macro-redispatch-link94-device-session.json
export PY=tools/host-lisp/c2_top_level_macro_redispatch_link94_media.py
export OUT=${OUT:-build/c2.3/top-level-macro-redispatch-link94-device-session}
export SESSION_LABEL=Link-94
export PRODUCT_REMOTE=TRACE94.D81

exec scripts/c2-trace-core-abi-link93-hw.sh "$@"
