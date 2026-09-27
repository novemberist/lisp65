"""Card L R1 dated Card-5 successor; inherited integrity mutations, one
withdrawn-route mutation per route, and one SHA mutation per predecessor.
Predecessor tools/receipts are immutable; no product build or link.
"""
import argparse
from pathlib import Path
import card_l_card5_20260925 as K
P=K.P
ROOT=K.ROOT
K.ROUTES={'storage-owner-preflight-check': 'card_l_storage_owner_20260925.py', 'c2-lite-v6-roots-fronts-product-profile-check': 'card_l_media_manifest_20260925.py', 'block-26-build-integrity-check': 'card_l_card5_r1_3_20260925.py', 'c2-v20-map-tuple-d1-e25-check': 'card_l_d1_e25_20260925.py', 'c2-require-prior-append-option-a-check': 'card_l_option_a_20260925.py', 'c2-media-builder-closure-enumeration-check': 'card_l_media_census_20260925.py'}
HISTORY={'tools/host-lisp/card_l_card5_r1_2_20260925.py': 'b4201540cc92d6c7865da88999f4ddee40914a5cb45ffa0c1d81ca3fc82164de', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/block-2.6-card5-build-integrity-card-l-r1-2-receipt-20260925.json': 'bc4527f66602cb2a796fc2c30a0164cf7072e77d3910b82bce31306e1556b668'}
RECEIPT=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/block-2.6-card5-build-integrity-card-l-r1-3-receipt-20260925.json'

def history(rows):
    assert rows==HISTORY, 'Card-5 predecessor drift'

def derive():
    rows={path:P.sha(ROOT/path) for path in HISTORY};history(rows)
    for path in rows:
        trial=dict(rows);trial[path]='0'*64
        try:history(trial)
        except AssertionError:pass
        else:raise AssertionError('predecessor mutation survived')
    facts=P.validate(P.source_texts(ROOT)); inherited=P.selftest()
    text=(ROOT/'mk/gates.mk').read_text();K.routing(text)
    rejected=[]
    for target,tool in K.ROUTES.items():
        trial=text.replace('tools/host-lisp/'+tool+' check','tools/host-lisp/withdrawn_'+tool+' check')
        assert trial!=text
        try:K.routing(trial)
        except AssertionError:rejected.append(target)
        else:raise AssertionError('route mutation survived')
    paths=list(P.source_texts(ROOT))+list(HISTORY)+['tools/host-lisp/'+n for n in K.ROUTES.values()]
    return dict(format='card-l-r1-card5-successor-v1',date='2026-09-25',status='passed',
        predecessor=rows,facts=facts,mutation_suite=dict(inherited=inherited,routing=rejected,history=len(rows)),
        inputs=[dict(path=p,sha256=P.sha(ROOT/p)) for p in sorted(set(paths))],product_builds=0,product_links=0,device_contacts=0)

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','check','selftest']);a=p.parse_args();value=derive()
    if a.action=='prepare':assert not RECEIPT.exists();RECEIPT.write_bytes(P.canonical(value))
    elif a.action=='check':assert RECEIPT.read_bytes()==P.canonical(value),'Card-5 successor drift'
    print(f'Card L R1 Card 5: {a.action.upper()} PASS routes={len(K.ROUTES)} history-mutations={len(HISTORY)} product-builds=0')
if __name__=='__main__':main()
