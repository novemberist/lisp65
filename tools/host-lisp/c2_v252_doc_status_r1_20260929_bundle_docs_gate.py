"""Published 2.5.1 documentation status successor, prepared for the 2.5.2 chain."""
import argparse, json
from pathlib import Path
from unittest.mock import patch
import c2_v251_r2_20260929_bundle_docs_gate as H
import c2_v252_doc_status_r1_20260929_common as S
HISTORY={'tools/host-lisp/c2_v251_r2_20260929_bundle_docs_gate.py': '7a8847f88f4b996c87bce661f9eb32fd643c061de58df33c3e41df68e4926cff', 'config/c2-v251-r2-20260929-bundle-docs.json': '8e1289a732f21f7933e4e961f8d29dafac40d42ba06028b2b25e077c8b1c6fb8'}
CONTRACT=S.ROOT/'config/c2-v252-doc-status-r1-20260929-bundle-docs.json'
def check(root, bundle=False):
    S.history(HISTORY)
    contract=json.loads(CONTRACT.read_bytes())
    old=json.loads((S.ROOT/'config/c2-v251-r2-20260929-bundle-docs.json').read_bytes())
    if contract['bundle_sources']!=old['bundle_sources']: raise ValueError('proof population drift')
    if contract['predecessors']!=HISTORY: raise ValueError('contract ancestry drift')
    with patch.object(H,'CONTRACT',CONTRACT): H.check(root,bundle)
    for name, digest in contract['additional_documents'].items():
        if S.sha(name)!=digest: raise ValueError('additional document drift: '+name)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=S.ROOT);p.add_argument('--bundle',action='store_true');a=p.parse_args();check(a.root,a.bundle)
