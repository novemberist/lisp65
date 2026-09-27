#!/usr/bin/env python3
"""Dated census successor with two checked public Comfort reproductions.

Predecessor active closure and 44 mutation requirements stay in force.
Qualification does not change the shipping/current builder selection.
"""
import argparse
import json
import copy
import hashlib
import comfort_default_media_census_20260927 as H
G=H.P

# Register the public source-based media successor independently.
ADDITIONS={'tools/host-lisp/c2_v250_public_media_reproduction.py'}
RESEARCH={'tools/host-lisp/card_l_seed_comfort_media_20260925.py',
          'tools/host-lisp/card_l_seed_delivery_20260925.py',
          'tools/host-lisp/card_l_seed_media.py',
          'tools/host-lisp/set_b_seed_delivery_20260926.py'}
G.REGISTERED=G.REGISTERED|ADDITIONS|RESEARCH
RECEIPT=G.ROOT/'config/c2-v250-media-census-receipt-repro-20260928.json'

HISTORY={'tools/host-lisp/comfort_default_media_census_20260927.py': '856024b6f15ef76bce31835f32f41c8967fe082b52949e305bb4cfda9aff9083', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-media-builder-closure-enumeration-comfort-default-20260927-receipt.json': 'a64b3096997f9ed84dcedda1b7ec124a1f3bec0db6456a1cb127d915da541ce4'}

def derive():
    actual={p:hashlib.sha256((G.ROOT/p).read_bytes()).hexdigest() for p in HISTORY}
    G.require(actual==HISTORY, 'dated census predecessor drift')
    result=H.derive()
    rejected=[]
    for path in sorted(ADDITIONS | (RESEARCH-G.REGISTERED)):
        trial=copy.deepcopy(result);trial['builders']['observed'].pop(path)
        try:G.audit(trial)
        except G.EnumerationError:rejected.append('omit:'+path)
        else:raise ValueError('builder omission survived')
    for path in HISTORY:
        trial=dict(actual);trial[path]='0'*64
        try:G.require(trial==HISTORY,'history mutation')
        except G.EnumerationError:rejected.append('history:'+path)
        else:raise ValueError('predecessor mutation survived')
    result['v250_successor']=dict(predecessors=actual,mutations=rejected)
    G.require(ADDITIONS<=set(result['builders']['registered_noncurrent']), 'unqualified builder promoted')
    import c2_v250_reproduction_gate as R
    result['v250_public_reproductions']=R.validate(json.loads(R.RECEIPT.read_text()))
    result['v250_candidate_disposition']='Two public-source reproductions byte-identical; release qualification only'
    result['recorded_on']='2026-09-27'
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('selftest','record','check'));a=p.parse_args()
    value=derive()
    if a.action=='record':
        G.require(not RECEIPT.exists(),'successor exists');RECEIPT.write_bytes(G.canonical(value))
    elif a.action=='check':G.require(RECEIPT.read_bytes()==G.canonical(value),'census successor drift')
    print('v250 media census: PASS builders='+str(value['builders']['total'])+' mutations='+str(len(value['mutations']))+'; public reproductions=2 PASS')

if __name__=='__main__':main()
