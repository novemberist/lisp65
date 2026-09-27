"""Card 5 dated successor for Card L check-source routing; predecessors are immutable."""
import argparse
import json
from pathlib import Path
import block_26_build_integrity_card as P

ROOT=P.ROOT
PREDECESSOR=P.RECEIPT
RECEIPT=PREDECESSOR.parent/'block-2.6-card5-build-integrity-card-l-receipt-20260925.json'
ROUTES={
    'storage-owner-preflight-check':'card_l_storage_owner_20260925.py',
    'c2-lite-v6-roots-fronts-product-profile-check':'card_l_media_manifest_20260925.py',
    'block-26-build-integrity-check':'card_l_card5_20260925.py',
}

def routing(text):
    import re
    for target,tool in ROUTES.items():
        m=re.search(r'^'+re.escape(target)+r':[^\n]*\n((?:\t[^\n]*\n)+)',text,re.M)
        assert m and f'tools/host-lisp/{tool} check' in m[1], 'successor routing drift: '+target
    assert 'tools/host-lisp/storage_owner_preflight.py --elf' not in text
    assert 'tools/host-lisp/c2_lite_v6_roots_fronts_product_profile.py check' not in text
    assert 'tools/host-lisp/block_26_build_integrity_card.py check' not in text

def selftest():
    inherited=P.selftest();text=(ROOT/'mk/gates.mk').read_text();routing(text)
    rejected=[]
    for target,tool in ROUTES.items():
        trial=text.replace(f'tools/host-lisp/{tool} check',f'tools/host-lisp/withdrawn_{tool} check')
        assert trial!=text
        try:routing(trial)
        except AssertionError:rejected.append(target+'-predecessor-route')
        else:raise AssertionError('routing mutation survived')
    print('Card L Card 5: SELFTEST PASS routing-mutations=3')
    return dict(inherited=inherited,routing=rejected)

def derive():
    facts=P.validate(P.source_texts(ROOT));mutations=selftest()
    paths=[ROOT/p for p in P.source_texts(ROOT)]+[ROOT/'tools/host-lisp'/n for n in
        ['make_recipe_value.py','toolchain_external.py','r6_g6.py','block_26_build_integrity_card.py',*ROUTES.values()]]
    return dict(format='lisp65-card5-card-l-successor-v1',status='passed',date='2026-09-25',
        predecessor=dict(path=str(PREDECESSOR.relative_to(ROOT)),sha256=P.sha(PREDECESSOR)),facts=facts,
        mutation_suite=mutations,inputs=[dict(path=str(p.relative_to(ROOT)),sha256=P.sha(p)) for p in paths],
        product_builds=0,product_links=0,device_contacts=0)

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['selftest','prepare','check']);a=p.parse_args()
    if a.action=='selftest':selftest();return
    value=derive()
    if a.action=='prepare':assert not RECEIPT.exists();RECEIPT.write_bytes(P.canonical(value))
    else:assert RECEIPT.read_bytes()==P.canonical(value),'Card 5 successor drift'
    print('Card L Card 5: CHECK PASS routes=3 product-builds=0')
if __name__=='__main__':main()
