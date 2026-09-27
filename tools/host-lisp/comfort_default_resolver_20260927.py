"""Comfort default resolver provenance successor; same Option-A semantics; runtime and VM provenance include frozen Set B and mutations, fresh isolated receipt."""
import argparse
import copy
from pathlib import Path
import c2_require_resolver_gate as G
HISTORY={'tools/host-lisp/card_l_resolver_20260925.py': '8b4ac181decd835175a09d7cf117a7f147269f545ee24e2b10435f9edda1d7f3', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/library-require-resolver-card-l-successor-20260925.json': 'b94908303e346a0c33044aa6587fdeb20c1e71141c3d6065c126a8c8a747568e'}

PREDECESSOR=G.SUCCESSOR_RECEIPT.with_name('library-require-resolver-card-l-successor-20260925.json')
TARGET=PREDECESSOR.with_name('library-require-resolver-comfort-default-successor-20260927.json')
G.SUCCESSOR_RECEIPT=TARGET
G.__file__=__file__

def verify_history(rows):
    G.require(rows==HISTORY,'Comfort default resolver predecessor drift')

def projection(value):
    value=copy.deepcopy(value)
    value.pop('recorded_on')
    for key in ('runtime','gate','vm'):value['authority'].pop(key)
    return value

def continuity(value):
    G.require(projection(value)==projection(G.load(PREDECESSOR)), 'Comfort default resolver semantic drift')

def main(record=False):
    rows={path:G.sha_bytes((G.ROOT/path).read_bytes()) for path in HISTORY};verify_history(rows)
    for path in rows:
        trial=dict(rows);trial[path]='0'*64
        try:verify_history(trial)
        except G.GateError:pass
        else:raise AssertionError('history mutation survived')
    if record:
        G.require(not TARGET.exists(),'Comfort default receipt already exists')
        G.SUCCESSOR_RECEIPT=G.ROOT/'build/check-result-successors'/TARGET.name
        G.require(not G.SUCCESSOR_RECEIPT.exists(),'scratch receipt already exists')
    code=G.main(record_successor=record)
    if code:return code
    value=G.load(G.SUCCESSOR_RECEIPT);continuity(value)
    trial=copy.deepcopy(value);trial['claim_limit']='unauthorized claim'
    try:continuity(trial)
    except G.GateError:pass
    else:raise AssertionError('semantic mutation survived')
    print('Comfort default resolver: PASS historical-mutations=2 semantic-mutations=1 runtime/gate-only=1')
    return 0
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',nargs='?',default='check',choices=['record','check']);args=p.parse_args()
    raise SystemExit(main(args.action=='record'))
