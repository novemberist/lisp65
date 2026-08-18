#!/bin/sh
# Link-95 same-world trace/restoration row; delegates to the audited no-live-FTP runner.
set -eu
cd "$(dirname "$0")/.."

export CONFIG=config/c2-packed-callee-link95-world-bound-device-session.json
export PY=tools/host-lisp/c2_link95_world_bound_media.py
export OUT=${OUT:-build/c2.3/packed-callee-link95-world-bound-device-session}
export SESSION_LABEL=Link-95-world-bound
export PRODUCT_REMOTE=TR95WB.D81

exec scripts/c2-trace-core-abi-link93-hw.sh "$@"
