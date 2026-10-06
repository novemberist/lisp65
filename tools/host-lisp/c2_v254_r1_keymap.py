#!/usr/bin/env python3
"""2.5.4 keymap entry point: the key extension seam (render seam only).

Delegates to the immutable c2_v253_r1_keymap (which delegates to the
immutable 2.5.2/2.5.1 chain and the pinned renderer
c2_ide_exit_keymap_20260928).  No key binding, contract row, generated test
case, hardware case or keymap document moves.  The only change is the
rendered lib/ide-keymap-generated.lisp: two generated functions gain the
extension fallback.

  %ide-prefix-command  unbound C-x + printable key -> EXTENSION_BASE + code
  %ide-command-route   command >= EXTENSION_BASE  -> EXTENSION_ROUTE

Bound C-x keys, control keys after C-x (prefix cancelled, nil) and every
built-in command route are unchanged.  lib/ide-ui.lisp dispatches route 14 to
%ide-extension-run, which looks the key up in the ide-bind-key registry.
Each seam must match the inherited rendering exactly once.
"""
import re
import sys
from unittest.mock import patch

import c2_v253_r1_keymap as K
import c2_v253_r1_common as C

HISTORY = {'tools/host-lisp/c2_v253_r1_keymap.py':
               '6d2c10b4af0b8952a659af08edf937efaed6d0bde2a68570da6ee0a2d6bfa9b0'}

EXTENSION_BASE = 1200
EXTENSION_ROUTE = 14

S = K.K.K.S          # pinned renderer module (c2_ide_exit_keymap_20260928)
ORIGINAL = S.render_lisp

PREFIX = re.compile(
    r'\(defun %ide-prefix-command \(code\)\n'
    r'  \(progn\n'
    r'    \(set-symbol-value \(quote ide-event-command\) nil\)\n'
    r'    \(%ide-keymap-lookup code \(quote (\([0-9 ]*\))\)\)\)\)\n')
ROUTE = re.compile(
    r'\(defun %ide-command-route \(command\)\n'
    r'  \(%ide-keymap-lookup command \(quote (\([0-9 ]*\))\)\)\)\n')


def _prefix(match):
    return ('(defun %ide-prefix-command (code)\n'
            '  (progn\n'
            '    (set-symbol-value (quote ide-event-command) nil)\n'
            '    ((lambda (command)\n'
            '       (if command\n'
            '           command\n'
            f'           (if (ide-printable-code-p code) (+ {EXTENSION_BASE} code) nil)))\n'
            f'     (%ide-keymap-lookup code (quote {match.group(1)})))))\n')


def _route(match):
    return ('(defun %ide-command-route (command)\n'
            f'  (if (< command {EXTENSION_BASE})\n'
            f'      (%ide-keymap-lookup command (quote {match.group(1)}))\n'
            f'      {EXTENSION_ROUTE}))\n')


def render_lisp(value):
    text = ORIGINAL(value)
    ids = [row['id'] for row in value['commands']]
    C.require(max(ids) < EXTENSION_BASE, 'built-in command id reaches the extension base')
    C.require(EXTENSION_ROUTE not in S.ROUTE_IDS.values(), 'extension route collides')
    text, n = PREFIX.subn(_prefix, text)
    C.require(n == 1, 'keymap prefix seam drift')
    text, n = ROUTE.subn(_route, text)
    C.require(n == 1, 'keymap route seam drift')
    return text


ORIGINAL_CASES = S.binding_cases
SHIFT_Q = 'ide-exit-cx-shift-q-does-not-exit'


def binding_cases(value, *, p0):
    """C-x Shift-Q still does not exit; it now yields the extension command
    1200+81 (route 14, "unknown command" while unbound).  Three seam cases
    are appended; every other case is inherited unchanged."""
    cases = ORIGINAL_CASES(value, p0=p0)
    key = 'expr' if p0 else 'input'
    hits = [c for c in cases if c['name'] == SHIFT_Q]
    C.require(len(hits) == 1 and hits[0]['expect'] in ('nil', 'NIL'),
              'keymap case seam drift')
    hits[0]['expect'] = str(EXTENSION_BASE + 81)
    cases.extend((
        {'name': 'ide-extension-cx-unbound-printable-command',
         key: S.sequence_expr([24, 102]), 'expect': str(EXTENSION_BASE + 102)},
        {'name': 'ide-extension-command-route',
         key: (f'(list (%ide-command-route {EXTENSION_BASE + 33})'
               f' (%ide-command-route {EXTENSION_BASE + 126}))'),
         'expect': f'({EXTENSION_ROUTE} {EXTENSION_ROUTE})'},
        {'name': 'ide-extension-clears-prefix',
         key: S.sequence_expr([24, 102])[:-1]
              + ' (symbol-value (quote ide-event-command)))',
         'expect': 'nil' if p0 else 'NIL'},
    ))
    return cases


def run(argv):
    C.history(HISTORY)
    with patch.object(S, 'render_lisp', render_lisp), \
            patch.object(S, 'binding_cases', binding_cases):
        return K.run(argv)


if __name__ == '__main__':
    raise SystemExit(run(sys.argv[1:]))
