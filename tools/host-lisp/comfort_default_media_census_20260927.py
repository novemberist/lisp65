"""Comfort default census successor. New builders are reconstruction fixtures; inherited mutations and historical receipts remain intact."""
import argparse
import copy
import hashlib
from pathlib import Path
import card_l_media_census_20260925 as K
P=K.P
HISTORY={'tools/host-lisp/card_l_media_census_20260925.py': '171a7ccd7e8f68c573c72993a85fa7b61a0bb5ad38f7a7fafd18346034cf2949', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-media-builder-closure-enumeration-card-l-20260925-receipt.json': '48bfa7d4e301702f9d23bcf6428c46a79108dbef1f50bdf78dc5aeb682c09a7d'}
ADDED={'tools/host-lisp/comfort_default_media.py','tools/host-lisp/comfort_default_medium.py','tools/host-lisp/set_b_seed_delivery_20260926.py'}

P.PREDECESSOR_RECEIPT=P.RECEIPT
P.RECEIPT=P.ARCH/'c2.3-media-builder-closure-enumeration-comfort-default-20260927-receipt.json'
P.REGISTERED=P.REGISTERED | ADDED
base_derive=P.derive
base_domain=P.domain

def domain(path):
    if path in ADDED:return 'sealed-library-or-reconstruction-fixture'
    return base_domain(path)
P.domain=domain

def history(rows):
    P.require(rows==HISTORY,'Comfort default census predecessor drift')

def derive():
    rows={path:hashlib.sha256((P.ROOT/path).read_bytes()).hexdigest() for path in HISTORY};history(rows)
    rejected=[]
    for path in rows:
        trial=dict(rows);trial[path]='0'*64
        try:history(trial)
        except P.EnumerationError:rejected.append('history:'+path)
        else:raise AssertionError('history mutation survived')
    value=base_derive()
    for path in sorted(ADDED):
        trial=copy.deepcopy(value);trial['builders']['observed'].pop(path)
        try:P.audit(trial)
        except P.EnumerationError:rejected.append('omit:'+path)
        else:raise AssertionError('builder omission survived')
    value['recorded_on']='2026-09-27'
    value['comfort_default_successor']=dict(predecessors=rows,mutations=rejected,
        driver=dict(path=Path(__file__).relative_to(P.ROOT).as_posix(),sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        medium_adoption='card_l_final.py: identity adoption without repack; not a structural builder')
    return value
P.derive=derive

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['record','check','selftest']);a=p.parse_args()
    value={'record':P.record,'check':P.check,'selftest':derive}[a.action]()
    print(f"Comfort default media census: {a.action.upper()} PASS builders={value['builders']['total']} inherited-mutations={len(value['mutations'])} successor-mutations={len(value['comfort_default_successor']['mutations'])}")
if __name__=='__main__':main()
