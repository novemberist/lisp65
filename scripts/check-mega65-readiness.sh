#!/bin/sh
# Check whether the local MEGA65/xemu setup is ready for MEGA65 smoke tests.
# This intentionally does not start the emulator; the actual xemu PRG-test path lives
# in scripts/smoke-xmega65-prgtest.sh.
set -eu

XMEGA65_BIN="${XMEGA65:-xmega65}"
XEMU_DIR="${XEMU_MEGA65_DIR:-$HOME/.local/share/xemu-lgb/mega65}"
PY="${PYTHON:-python3}"
INT="tools/host-lisp/lisp64.py"
PRE="lisp/prelude.lsp"

if ! command -v "$XMEGA65_BIN" >/dev/null 2>&1; then
  echo "MEGA65 readiness failed: xmega65 binary not found: $XMEGA65_BIN" >&2
  exit 1
fi
echo "xmega65: $(command -v "$XMEGA65_BIN")"

if [ ! -d "$XEMU_DIR" ]; then
  echo "MEGA65 readiness failed: Xemu MEGA65 directory missing: $XEMU_DIR" >&2
  exit 1
fi
echo "xemu data: $XEMU_DIR"

for file in MEGA65.ROM CHARROM.M65 mega65.img; do
  if [ ! -s "$XEMU_DIR/$file" ]; then
    echo "MEGA65 readiness failed: missing or empty $XEMU_DIR/$file" >&2
    exit 1
  fi
  echo "asset: $file"
done

"$PY" "$INT" "$PRE" \
  lisp/lib-platform.lsp \
  lisp/lib-mega65hw.lsp \
  lisp/lib-platform-mega65.lsp \
  lisp/platform-mega65-tests.lsp

"$PY" "$INT" "$PRE" \
  lisp/lib-platform.lsp \
  lisp/lib-mega65hw.lsp \
  lisp/lib-platform-mega65-bank4.lsp \
  lisp/platform-mega65-bank4-tests.lsp

echo "MEGA65 readiness ok"
