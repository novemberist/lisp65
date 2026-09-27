"""Card L census successor (2026-09-25), following Comfort's v31 registration.
The three seed producers are sealed reconstruction/diagnostic fixtures; this
registration does not promote them to current-qualified product producers.
card_l_final.py adopts the same medium without repack and is not a builder
under the unchanged structural grammar. Mutation matrix: all 44 inherited
mutations, omission of each new builder, corruption of each predecessor SHA.
"""
import argparse
import copy
import hashlib
from pathlib import Path
import c2_media_builder_closure_enumeration as P
HISTORY={'tools/host-lisp/c2_media_builder_closure_enumeration.py': 'af152981dd8cfc123d423ad219bac80e5b4ad1fa7f47e8ec30a3545552f7ac04', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-media-builder-closure-enumeration-v31-receipt.json': 'ca5a262266eb3ceee39237a8f711c31222432d7ea1c625c758fab4fb9949dbd0'}

ADDED={
    'tools/host-lisp/card_l_seed_media.py',
    'tools/host-lisp/card_l_seed_delivery_20260925.py',
    'tools/host-lisp/card_l_seed_comfort_media_20260925.py',
}
P.PREDECESSOR_RECEIPT=P.RECEIPT
P.RECEIPT=P.ARCH/'c2.3-media-builder-closure-enumeration-card-l-20260925-receipt.json'
P.REGISTERED=P.REGISTERED | ADDED
base_derive=P.derive
base_domain=P.domain

def domain(path):
    if path in ADDED:return 'sealed-library-or-reconstruction-fixture'
    return base_domain(path)
P.domain=domain

def history(rows):
    P.require(rows==HISTORY,'Card L census predecessor drift')

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
    value['recorded_on']='2026-09-25'
    value['card_l_successor']=dict(predecessors=rows,mutations=rejected,
        driver=dict(path=Path(__file__).relative_to(P.ROOT).as_posix(),sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        medium_adoption='card_l_final.py: identity adoption without repack; not a structural builder')
    return value
P.derive=derive

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['record','check','selftest']);a=p.parse_args()
    value={'record':P.record,'check':P.check,'selftest':derive}[a.action]()
    print(f"Card L media census: {a.action.upper()} PASS builders={value['builders']['total']} inherited-mutations={len(value['mutations'])} successor-mutations={len(value['card_l_successor']['mutations'])}")
if __name__=='__main__':main()
