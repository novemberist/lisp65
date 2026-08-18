#!/bin/sh
# Link-95 trace/restoration row using the corrected no-live-FTP choreography.
set -eu
cd "$(dirname "$0")/.."

export CONFIG=config/c2-packed-callee-link95-device-session.json
export PY=tools/host-lisp/c2_link95_acceptance_media.py
export OUT=${OUT:-build/c2.3/packed-callee-link95-device-session}
export SESSION_LABEL=Link-95
export PRODUCT_REMOTE=TRACE95.D81

exec scripts/c2-trace-core-abi-link93-hw.sh "$@"
