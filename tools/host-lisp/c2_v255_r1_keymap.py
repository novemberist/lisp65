#!/usr/bin/env python3
"""2.5.5 keymap entry point: editor typing speed (render seams only).

Delegates to the immutable c2_v254_r1_keymap (key extension seam) and through
it to the pinned renderer chain.  No key binding, contract row, generated test
case, hardware case or keymap document moves; every key still maps to the same
command and every command to the same route.  Only the rendered
lib/ide-keymap-generated.lisp changes, in two generated functions:

  ide-event-command    a printable code (32..126) is the insert command 1110
                       BEFORE the base table is searched (the base table binds
                       no printable code; checked here)
  %ide-command-route   the routes of insert, Backspace, Return and the cursor
                       keys stand first in the route table (a literal list)

Why: every iteration of %ide-keymap-lookup is a full tail call, and a call
reloads the code object (build/scope-editor-typing-r1/report.txt).  A plain
character searched 24 base entries and 23 routes before it was inserted.
Each seam must match the inherited rendering exactly once.
"""
import re
import sys
from unittest.mock import patch

import c2_v254_r1_keymap as K
import c2_v253_r1_common as C

HISTORY = {'tools/host-lisp/c2_v254_r1_keymap.py':
               '15f3cd2760339256b5779091e6a7c3cec9a94cb1047c1322033d62ca51af39cc'}

INSERT = 1110
ROUTE_FRONT = (1110, 1101, 1109, 1106, 1107, 1108, 1003)

S = K.S              # pinned renderer module (c2_ide_exit_keymap_20260928)
INHERITED = K.render_lisp

EVENT_OLD = '''                    ((lambda (command)
                       (if command
                           command
                           (if (and (>= code 32)
                                    (<= code 126))
                               1110
                               nil)))
                     (%ide-base-command code))))))
'''
EVENT_NEW = '''                    (if (and (>= code 32)
                             (<= code 126))
                        1110
                        (%ide-base-command code))))))
'''
ROUTE = re.compile(r'(\(%ide-keymap-lookup command \(quote \()([0-9 ]+)(\)\)\))')
BASE = re.compile(r'\(defun %ide-base-command \(code\)\n  \(%ide-keymap-lookup code \(quote \(([0-9 ]+)\)\)\)\)\n')


def _route(match):
    numbers = [int(x) for x in match.group(2).split()]
    pairs = list(zip(numbers[0::2], numbers[1::2]))
    table = dict(pairs)
    C.require(len(table) == len(pairs) and all(k in table for k in ROUTE_FRONT),
              'keymap route table drift')
    order = list(ROUTE_FRONT) + [k for k, _ in pairs if k not in ROUTE_FRONT]
    return match.group(1) + ' '.join(f'{k} {table[k]}' for k in order) + match.group(3)


def render_lisp(value):
    text = INHERITED(value)
    base = BASE.search(text)
    C.require(base is not None and len(BASE.findall(text)) == 1, 'keymap base table drift')
    codes = [int(x) for x in base.group(1).split()][0::2]
    C.require(not any(32 <= code <= 126 for code in codes),
              'a printable code is bound in the base table; the printable test must not come first')
    C.require(text.count(EVENT_OLD) == 1, 'keymap event seam drift')
    text = text.replace(EVENT_OLD, EVENT_NEW)
    text, n = ROUTE.subn(_route, text)
    C.require(n == 1, 'keymap route seam drift')
    return text


def run(argv):
    C.history(HISTORY)
    with patch.object(K, 'render_lisp', render_lisp):
        return K.run(argv)


if __name__ == '__main__':
    raise SystemExit(run(sys.argv[1:]))
