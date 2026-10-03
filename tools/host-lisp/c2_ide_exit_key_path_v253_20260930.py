#!/usr/bin/env python3
"""2.5.3 successor of the IDE exit key-path source-authority check.

Only lib/ide-ui.lisp moved since the inspected 2.5.0 transport: the 2.5.3
single-buffer switch fix (ide-ui.lisp %ide-cycle-buffer-find keeps the current
buffer text when it is the only buffer) does not touch the ring, poll-key
primitive or ide-event-code path this check inspects. The producer, ring and
generated dispatch sources keep their inspected hashes; the real Lisp oracle
still loads the live lib/ide-ui.lisp. The predecessor tool stays immutable.
"""
import sys

import c2_ide_exit_key_path_20260928 as T

UI = 'lib/ide-ui.lisp'
UI_V253 = '4852f690659c81ff63755620cb27d3a8b28e9af433e72a8e65cc32e9ef725ab7'
T.SOURCE_GUARDS = {**T.SOURCE_GUARDS, UI: UI_V253}

if __name__ == "__main__":
    try:
        raise SystemExit(T.main())
    except (T.BASE.GateError, T.KEYMAP.KeymapError, OSError, ValueError, KeyError) as exc:
        print("IDE exit key path: FAIL: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
