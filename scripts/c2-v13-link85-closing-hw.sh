#!/bin/sh
# Commissioned one-contact Link-85 full-reset closing session.
set -eu
cd "$(dirname "$0")/.."

export PY=scripts/c2-v13-link85-closing-device.py
export DEPLOY=build/ship-builder/v13/link85-closing-device-session/deployment.json
export OUT=build/ship-builder/v13/link85-closing-device-session/run
export D1_ORDER=after-D3

exec scripts/c2-v13-closing-hw.sh "$@"
