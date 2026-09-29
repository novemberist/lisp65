#!/usr/bin/env python3
"""Register the 2.5.1 public media producer; retain the prior census and controls."""
import argparse,copy,json,hashlib
import c2_v250_media_census_20260928 as H
import c2_v251_r2_20260929_reproduction_gate as R
G=H.G
ADDED={'tools/host-lisp/c2_v251_r2_20260929_public_media_reproduction.py'}
G.REGISTERED=G.REGISTERED|ADDED|{'tools/host-lisp/c2_v251_public_media_reproduction.py'}
RECEIPT=G.ROOT/'config/c2-v251-r2-20260929-media-census-receipt.json'
HISTORY={'tools/host-lisp/c2_v250_media_census_20260928.py': 'd3451e9a86bbe7731e2e149d5c1f063f0197b28b1d27765890493142697a9081', 'config/c2-v250-media-census-receipt-repro-20260928.json': '5c9f1cefb35f97fa1ac4048ab5bc02377a4c76700be44dc0a0ba850acc5041f3'}

def derive():
    G.require({p:hashlib.sha256((G.ROOT/p).read_bytes()).hexdigest() for p in HISTORY}==HISTORY,'v250 census predecessor drift')
    v=H.derive()
    rejected=[]
    for name in ADDED:
        trial=copy.deepcopy(v);trial['builders']['observed'].pop(name)
        try:G.audit(trial)
        except G.EnumerationError:rejected.append(name)
        else:raise ValueError('2.5.1 builder omission survived')
    v['v251_successor']=dict(history=HISTORY,mutations=rejected,reproductions=R.validate(json.loads(R.RECEIPT.read_text())))
    return v
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['record','selftest','check']);a=p.parse_args()
    raw=G.canonical(derive())
    if a.action=='record':
        with RECEIPT.open('xb') as f:f.write(raw)
    elif a.action=='check':G.require(RECEIPT.read_bytes()==raw,'2.5.1 media census drift')
    print('2.5.1 media census '+a.action+': PASS')
