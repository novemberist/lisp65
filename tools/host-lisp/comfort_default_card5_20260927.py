"""Comfort default dated Card-5 successor; inherited integrity mutations, one
withdrawn-route mutation per route, and one SHA mutation per predecessor.
Predecessor tools/receipts are immutable; no product build or link.
"""
import argparse
from pathlib import Path
import card_l_card5_20260925 as K
P=K.P
ROOT=K.ROOT
K.ROUTES={'storage-owner-preflight-check': 'card_l_storage_owner_20260925.py', 'c2-lite-v6-roots-fronts-product-profile-check': 'card_l_media_manifest_20260925.py', 'block-26-build-integrity-check': 'comfort_default_card5_20260927.py', 'c2-v20-map-tuple-d1-e25-check': 'comfort_default_d1_e25_20260927.py', 'c2-require-prior-append-option-a-check': 'comfort_default_option_a_20260927.py', 'c2-media-builder-closure-enumeration-check': 'comfort_default_media_census_20260927.py'}
HISTORY={'tools/host-lisp/card_l_card5_r1_3_20260925.py': 'd2b0bdc48c5037c62bcefeb095db7e9d0c73bb091de5b3d218bfe4a5b6efa01d', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/block-2.6-card5-build-integrity-card-l-r1-3-receipt-20260925.json': 'e5cbbed4a961980b5c9745c51bb9a827135a7376717dcfa283f258d1b89b52b6'}
RECEIPT=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/block-2.6-card5-build-integrity-comfort-default-receipt-20260927.json'

def history(rows):
    assert rows==HISTORY, 'Card-5 predecessor drift'

MAKE_ROUTES={
    'c2-elf-truth-migration-check': 'comfort_default_elf_truth_20260927.py',
    'c2-linked-format-decoder-closure-check': 'comfort_default_linked_format_20260927.py',
}

def make_routing(text):
    import re
    for target, tool in MAKE_ROUTES.items():
        match=re.search(r'^'+re.escape(target)+r':[^\n]*\n((?:\t[^\n]*\n)+)',text,re.M)
        assert match and f'tools/host-lisp/{tool} check' in match[1], 'Makefile successor route drift: '+target

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
    make_text=(ROOT/'Makefile').read_text();make_routing(make_text)
    for target,tool in MAKE_ROUTES.items():
        trial=make_text.replace('tools/host-lisp/'+tool+' check','tools/host-lisp/withdrawn_'+tool+' check')
        try:make_routing(trial)
        except AssertionError:rejected.append(target)
        else:raise AssertionError('Makefile route mutation survived')
    paths=['tools/host-lisp/'+n for n in MAKE_ROUTES.values()]+list(P.source_texts(ROOT))+list(HISTORY)+['tools/host-lisp/'+n for n in K.ROUTES.values()]
    return dict(format='comfort-default-card5-successor-v1',date='2026-09-27',status='passed',
        predecessor=rows,facts=facts,mutation_suite=dict(inherited=inherited,routing=rejected,history=len(rows)),
        inputs=[dict(path=p,sha256=P.sha(ROOT/p)) for p in sorted(set(paths))],product_builds=0,product_links=0,device_contacts=0)

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','check','selftest']);a=p.parse_args();value=derive()
    if a.action=='prepare':assert not RECEIPT.exists();RECEIPT.write_bytes(P.canonical(value))
    elif a.action=='check':assert RECEIPT.read_bytes()==P.canonical(value),'Card-5 successor drift'
    print(f'Comfort default Card 5: {a.action.upper()} PASS routes={len(K.ROUTES)+len(MAKE_ROUTES)} history-mutations={len(HISTORY)} product-builds=0')
if __name__=='__main__':main()
