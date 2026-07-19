#!/bin/sh
# Wave-3 fail-fast pre-smoke. It is deliberately receipt-less and may never
# create promotion proof objects. Its only job is to find new-surface failures before
# the expensive R3/R4/R5/R6 chain.
set -eu

if [ "${1:-}" != "--list" ]; then
    echo "usage: $0 --list" >&2
    echo "receipt output is forbidden; run the listed actions interactively" >&2
    exit 2
fi

cat <<'EOF'
Wave-3 receipt-less hardware pre-smoke (stop on the first mismatch):
  1. Start the exact staged probe candidate and confirm its build identity.
  2. In the editor, press C-x Space; confirm that the mark is set.
  3. Press an unknown C-x sequence, then type a printable character; confirm
     that the character inserts and the prefix is no longer sticky.
  4. Use M-x goto-line with a three-digit line number; confirm no truncation.
  5. Enter a two-character M-x prefix; confirm it is rejected, then enter the
     full command name and confirm it succeeds.
  6. Modify the active B4 buffer, press C-x C-c, run (edit), and confirm the
     buffer contents survived the editor exit.
  7. Start a long evaluation, press RUN/STOP, and confirm the stopped message
     and a usable REPL. Confirm idle RUN/STOP does not open the editor.
No case receipt is produced. A mismatch stops staging before the seal chain.
EOF
