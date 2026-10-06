#!/usr/bin/env python3
"""2.5.4 successor of the IDE exit key-path source-authority check.

Two inspected inputs moved since the 2.5.3 successor: lib/ide-ui.lisp (E3
accepted-edit publication written in place in %ide-drain-pending, the key
extension seam in route 14 of %ide-dispatch-route-high and the C-x prefix
reset in %ide-init; no added private directory object) and the rendered lib/ide-keymap-generated.lisp (extension
fallback in %ide-prefix-command / %ide-command-route, rendered by
c2_v254_r1_keymap).  Neither touches the ring, the poll-key primitive, the
ide-event-code path or the C-x q binding this check inspects; C-x q still
yields 1015 on route 13.  The canonical generated output is the 2.5.4
rendering.  The predecessor tools stay immutable.
"""
import sys

import c2_v253_r1_common as C
import c2_ide_exit_key_path_v253_20260930 as P
import c2_v254_r1_keymap as K

HISTORY = {'tools/host-lisp/c2_ide_exit_key_path_v253_20260930.py':
               '9ad5c618f9881b4debac5599ab6110bd0385d72a0002a2b8fb88f2b516337d12'}
UI = 'lib/ide-ui.lisp'
UI_V254 = '27998b6195361d5fb2375b25ffe1a237a1e370a4d955753b050c8c55b4ca925a'

T = P.T
T.SOURCE_GUARDS = {**T.SOURCE_GUARDS, UI: UI_V254}


def main():
    C.history(HISTORY)
    T.KEYMAP.render_lisp = K.render_lisp
    T.KEYMAP.binding_cases = K.binding_cases
    return T.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (T.BASE.GateError, T.KEYMAP.KeymapError, OSError, ValueError, KeyError) as exc:
        print("IDE exit key path: FAIL: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
