#!/usr/bin/env python3
"""2.5.5 successor of the IDE exit key-path source-authority check.

Two inspected inputs moved since the 2.5.4 successor: lib/ide-ui.lisp (the
accessors of the key path written out as car/cdr; the loop stores the buffer
once at entry instead of before every key) and the rendered
lib/ide-keymap-generated.lisp (printable code before the base table, the
frequent routes first; rendered by c2_v255_r1_keymap).  Neither touches the
ring, the poll-key primitive, the ide-event-code / ide-event-modifiers calls
of ide-event-command (the inherited consumer mutations stay sharp) or the
C-x q binding this check inspects; C-x q still yields 1015 on route 13.  The
canonical generated output is the 2.5.5 rendering.  The predecessor tools stay
immutable.
"""
import sys

import c2_v253_r1_common as C
import c2_ide_exit_key_path_v254_r1 as P254
import c2_v255_r1_keymap as K

HISTORY = {'tools/host-lisp/c2_ide_exit_key_path_v254_r1.py':
               'fbcc4d70b3c9d6749ba81b4921a32c726b2db0595d9be2304bc50ce9a7eca264'}
UI = 'lib/ide-ui.lisp'
UI_V255 = '5da4be1f90eb726a5f77d4ce3a16cf3abe0174736b1f8676f5cdf2db70a39c16'

T = P254.T
T.SOURCE_GUARDS = {**T.SOURCE_GUARDS, UI: UI_V255}


def main():
    C.history(HISTORY)
    T.KEYMAP.render_lisp = K.render_lisp
    T.KEYMAP.binding_cases = P254.K.binding_cases
    return T.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (T.BASE.GateError, T.KEYMAP.KeymapError, OSError, ValueError, KeyError) as exc:
        print("IDE exit key path: FAIL: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
