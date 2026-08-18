#!/bin/sh
# Link-96 guarded defstruct row; delegates launch/forms to the audited no-live-FTP runner.
set -eu
cd "$(dirname "$0")/.."

ACTION=${1:-}
export CONFIG=config/c2-terminal-return-guard-link96-device-session.json
export PY=tools/host-lisp/c2_terminal_return_guard_media.py
export OUT=${OUT:-build/c2.3/terminal-return-guard-link96-device-session-r2}
export SESSION_LABEL=Link-96-terminal-return-guard
export PRODUCT_REMOTE=TRG96R2.D81

if [ "$ACTION" != capture-guard ]; then
  if [ "$ACTION" = dry-run ]; then
    python3 "$PY" check
    python3 tools/host-lisp/c2_live_repl_ftp_crossing_gate.py check
    echo "STAGE: cold BASIC -> one FTP lifetime uploads/readbacks both D81s -> product mount last"
    echo "BOOT: helper exits -> 45s zero-access boot -> exact banner/prompt"
    echo "OWNER: Freezer-mount TRACELIB.D81 on drive 8, return with F3"
    echo "ROWS: three physical forms, each quiet to its floor, one postcondition screen"
    echo "READBACK: one final stop, then physical Bank-0 0xB582..0xB591"
    echo "RULE: zero FTP invocations after product boot"
    exit 0
  fi
  exec scripts/c2-trace-core-abi-link93-hw.sh "$@"
fi

TOOLS=${TOOLS:-tools/m65tools}
DEVICE=${DEVICE:-/dev/ttyUSB1}
M65=$TOOLS/m65
TIMEOUT=${TIMEOUT:-60}
[ -x "$M65" ] && [ -c "$DEVICE" ] || {
  echo "MEGA65 tool/device unavailable" >&2; exit 3;
}
[ -e "$OUT/rows-complete" ] || {
  echo "Link-96 point rows are not complete" >&2; exit 3;
}
python3 "$PY" check
mkdir -p "$OUT"
timeout --kill-after=2s "${TIMEOUT}s" "$M65" -l "$DEVICE" -H \
  --memsave "0x0000b582:0x0000b592=$OUT/terminal-return-guard.bin"
python3 - "$OUT/terminal-return-guard.bin" <<'PY'
from pathlib import Path
import sys
raw = Path(sys.argv[1]).read_bytes()
assert len(raw) == 16, f"guard readback length drift: {len(raw)}"
assert raw[0] == 0, f"guard remained armed: {raw[0]:02x}"
for transfer in range(4):
    tag, live, shadow = raw[4 + transfer * 3:7 + transfer * 3]
    assert tag in (0, 1, 2, 3), f"guard tag invalid: {tag:02x}"
    if tag == 0:
        assert live == shadow == 0, "untagged guard record carries values"
print("Link-96 guard readback:", raw.hex(),
      "working-shadow:", raw[1:4].hex())
PY
python3 tools/host-lisp/c2_terminal_return_guard_device_result.py record
echo "LINK-96 POINT ROW AND GUARD READBACK COMPLETE; CPU STOPPED."
