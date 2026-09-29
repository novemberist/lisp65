#!/usr/bin/env python3
"""Bind 2.5.1 keymap generator, all generated outputs and immutable predecessor."""
import argparse,hashlib,json
import c2_v251_r2_20260929_keymap as K
from unittest.mock import patch
ROOT=K.S.ROOT
RECEIPT=ROOT/'config/c2-v251-r2-20260929-keymap-receipt.json'

def derive():
    K.H.history_check()
    with patch.object(K.S,'render_docs',K.render_docs),patch.object(K.H.H,'render_docs',K.render_docs):
        K.H.H.selftest(K.S.load_contract())
        K.S.main(['check'])
    names=['tools/host-lisp/c2_v251_r2_20260929_keymap.py','tools/host-lisp/c2_v251_r2_20260929_keymap_receipt.py','tools/host-lisp/c2_v250_keymap_ide_exit_20260928.py','tools/host-lisp/c2_ide_exit_keymap_20260928.py', 'config/v11-l-lite-keymap.json', 'lib/ide-keymap-generated.lisp','lib/stdlib-read-line.lisp','lib/tests/ide-keymap-eval-cases.generated.json','tests/bytecode/libs/p0-ide-keymap-cases.generated.json','tests/bytecode/libs/p0-ide-keymap-extra-cases.generated.json','tests/bytecode/dialect-v2/ide/l-lite-hardware-cases.generated.json','docs/generated/ide-keymap.md']
    return dict(status='PASS',files=[dict(path=n,bytes=(ROOT/n).stat().st_size,sha256=hashlib.sha256((ROOT/n).read_bytes()).hexdigest()) for n in names])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['record','check']);a=p.parse_args()
    raw=(json.dumps(derive(),indent=2,sort_keys=True)+'\n').encode()
    if a.action=='record':
        with RECEIPT.open('xb') as f:f.write(raw)
    elif raw!=RECEIPT.read_bytes():raise ValueError('2.5.1 keymap receipt drift')
    print('2.5.1 keymap receipt '+a.action+': PASS')
