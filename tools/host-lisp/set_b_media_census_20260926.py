"""Set B builder registration; unchanged structural grammar and predecessors."""
import argparse
import copy
from pathlib import Path
import card_l_media_census_20260925 as K
P=K.P
ADDED={'tools/host-lisp/set_b_seed_delivery_20260926.py'}
P.REGISTERED=P.REGISTERED|ADDED
P.PREDECESSOR_RECEIPT=P.RECEIPT
P.RECEIPT=P.ARCH/'c2.3-media-builder-closure-enumeration-set-b-20260926-receipt.json'
base_domain=P.domain
base_derive=P.derive

def domain(path):
    return 'sealed-library-or-reconstruction-fixture' if path in ADDED else base_domain(path)
P.domain=domain

def derive():
    value=base_derive();rejected=[]
    for path in sorted(ADDED):
        trial=copy.deepcopy(value);trial['builders']['observed'].pop(path)
        try:P.audit(trial)
        except P.EnumerationError:rejected.append(path)
        else:raise AssertionError('builder omission survived')
    value['set_b_successor']=dict(driver=dict(path=Path(__file__).relative_to(P.ROOT).as_posix(),sha256=K.hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),added=sorted(ADDED),mutations=rejected,classification='sealed reconstruction fixture; no qualification implied')
    return value
P.derive=derive

def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['record','check','selftest']);a=ap.parse_args()
    value={'record':P.record,'check':P.check,'selftest':derive}[a.action]()
    print('Set B census PASS',value['builders']['total'])
if __name__=='__main__':main()
