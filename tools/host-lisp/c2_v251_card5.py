#!/usr/bin/env python3
"""2.5.1 Card-5 successor of the sealed Backspace r6 route chain."""
import argparse,copy,json,hashlib
import c2_ide_exit_card5_r6_20260928 as R
ROOT=R.S.ROOT
K=R.H.H.H.H.K
V=R.H.H.H
K.ROUTES=dict(K.ROUTES,**{'block-26-build-integrity-check':'c2_v251_card5.py','c2-media-builder-closure-enumeration-check':'c2_v251_media_census.py'})
V.CHECK_HOST_ROUTES=copy.deepcopy(V.CHECK_HOST_ROUTES)
for targets in V.CHECK_HOST_ROUTES.values():
    for target,commands in targets.items():
        targets[target]=[c.replace('c2_ide_exit_card5_r6_20260928.py','c2_v251_card5.py').replace('c2_v250_keymap_ide_exit_20260928.py','c2_v251_keymap.py').replace('c2_v250_public_naming_ide_exit_20260928.py','c2_v251_public_naming.py').replace('c2_v250_bundle_docs_ide_exit_20260928.py','c2_v251_bundle_docs_gate.py').replace('c2_v210_bundle_docs_ide_exit_20260928.py','c2_v251_v210_bundle_docs.py') for c in commands]
V.CHECK_HOST_ROUTES['mk/gates.mk'].update({
 'v250-public-authority-check':['c2_v251_v250_release_era.py','c2_v250_reproduction_gate.py check'],
 'v251-public-authority-check':['c2_v251_public_product.py preflight','c2_v251_reproduction_gate.py check']})
V.CHECK_HOST_ROUTES['mk/workbench.mk']['v11-l-lite-keymap-check'].append('c2_v251_keymap_receipt.py check')
V.CHECK_HOST_ROUTES['mk/gates.mk']['c2-l-full-keymap-end-to-end-check'].append('c2_v251_keymap_receipt.py check')
V.CHECK_HOST_ROUTES['mk/gates.mk']['c2-media-builder-closure-enumeration-selftest']=['c2_v251_media_census.py selftest']
V.CHECK_HOST_ROUTES['mk/gates.mk']['c2-media-builder-closure-enumeration-check']=['c2_v251_media_census.py check']
HISTORY={'tools/host-lisp/c2_ide_exit_card5_r6_20260928.py': '2545dd15a0e6cc9bdecf9fd5e8a6ce92713f3935a9786c07653d53c277cc1b48', 'config/c2-ide-exit-card5-receipt-r6-backspace-20260928.json': '4eef92829a6a15f3eb7cef1f1e32a3cdfe62c84e662c656e07c253d67dddad0e'}
RECEIPT=ROOT/'config/c2-v251-card5-receipt.json'

def derive():
    for name,digest in HISTORY.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise ValueError('r6 predecessor drift: '+name)
    inherited=R.derive()
    names=['mk/gates.mk','mk/workbench.mk','tools/host-lisp/c2_v251_card5.py',
      'tools/host-lisp/c2_v251_keymap.py','tools/host-lisp/c2_v251_public_naming.py',
      'tools/host-lisp/c2_v251_bundle_docs_gate.py','tools/host-lisp/c2_v251_v210_bundle_docs.py',
      'tools/host-lisp/c2_v251_v250_release_era.py','tools/host-lisp/c2_v251_public_product.py',
      'tools/host-lisp/c2_v251_reproduction_gate.py','tools/host-lisp/c2_v251_media_census.py','config/c2-v251-media-census-receipt.json','config/c2-v251-keymap-receipt.json','config/c2-v251-bundle-docs.json',
      'config/c2-v251-public-naming-receipt.json','config/c2-v251-v210-bundle-docs-receipt.json']
    return dict(status='PASS',predecessor=HISTORY,inherited_r6=inherited,inputs=[R.S.bind(p) for p in names])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['build','check','selftest']);a=p.parse_args()
    data=R.S.canonical(derive())
    if a.action=='build':
        with RECEIPT.open('xb') as f:f.write(data)
    elif a.action=='check':R.S.require(RECEIPT.read_bytes()==data,'2.5.1 Card-5 drift')
    print('2.5.1 Card-5 '+a.action+': PASS')
