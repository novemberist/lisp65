#!/usr/bin/env python3
"""2.5.1 documentation successor; program and test-case generation unchanged."""
import sys
from unittest.mock import patch
import c2_v250_keymap_ide_exit_20260928 as H
S=H.S
OLD='The C-x q source successor awaits product, emulator and device acceptance.'
NEW='C-x q passed IDE-exit Final and virtual-keyboard device rows; physical keys remain an owner row.'
original=S.render_docs

def render_docs(value):
    text=original(value)
    if text.count(OLD)!=1:raise ValueError('keymap documentation seam drift')
    return text.replace(OLD,NEW)

if __name__=='__main__':
    H.history_check()
    with patch.object(S,'render_docs',render_docs),patch.object(H.H,'render_docs',render_docs):
        if sys.argv[1:]==['selftest']:H.H.selftest(S.load_contract())
        raise SystemExit(S.main(sys.argv[1:]))
