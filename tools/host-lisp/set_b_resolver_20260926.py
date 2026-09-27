"""Set B fifth-Seed resolver successor; historical derivation and mutations retained.
Prepared before the attempt; execution and receipt closure remain gates.
"""
import argparse
import copy
from pathlib import Path
import c2_require_resolver_gate as G
HISTORY={'tools/host-lisp/c2_require_resolver_gate.py': '2918b08e7aa52d4d146af9887d6af0cdde100c00f2727e43b33f51f8add231fb', 'tools/host-lisp/nested_error_recovery_resolver_successor.py': '0eeaaef23136f67fcf3104c059c4a2d8f599f32e231fec1d8315f21c2ce830c2', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/library-require-resolver-nested-error-recovery-successor-20260923.json': '859fa6eab9f0446b03d48f659f17bc433e2eff745e549573ea6572590b2cf754'}

HISTORY.update({'tools/host-lisp/card_l_resolver_20260925.py': '8b4ac181decd835175a09d7cf117a7f147269f545ee24e2b10435f9edda1d7f3', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/library-require-resolver-card-l-successor-20260925.json': 'b94908303e346a0c33044aa6587fdeb20c1e71141c3d6065c126a8c8a747568e'})
PREDECESSOR=G.SUCCESSOR_RECEIPT.with_name('library-require-resolver-card-l-successor-20260925.json')
TARGET=PREDECESSOR.with_name('library-require-resolver-set-b-successor-20260926.json')
G.SUCCESSOR_RECEIPT=TARGET
G.__file__=__file__

def verify_history(rows):
    G.require(rows==HISTORY,'Card L resolver predecessor drift')

def projection(value):
    value=copy.deepcopy(value)
    value.pop('recorded_on')
    for key in ('runtime','gate'):value['authority'].pop(key)
    return value

def continuity(value):
    G.require(projection(value)==projection(G.load(PREDECESSOR)), 'Card L resolver semantic drift')

def main(record=False):
    rows={path:G.sha_bytes((G.ROOT/path).read_bytes()) for path in HISTORY};verify_history(rows)
    for path in rows:
        trial=dict(rows);trial[path]='0'*64
        try:verify_history(trial)
        except G.GateError:pass
        else:raise AssertionError('history mutation survived')
    if record:
        G.require(not TARGET.exists(),'Card L receipt already exists')
        G.SUCCESSOR_RECEIPT=G.ROOT/'build/check-result-successors'/TARGET.name
        G.require(not G.SUCCESSOR_RECEIPT.exists(),'scratch receipt already exists')
    code=G.main(record_successor=record)
    if code:return code
    value=G.load(G.SUCCESSOR_RECEIPT);continuity(value)
    trial=copy.deepcopy(value);trial['claim_limit']='unauthorized claim'
    try:continuity(trial)
    except G.GateError:pass
    else:raise AssertionError('semantic mutation survived')
    print('Set B resolver: PASS historical-mutations=5 semantic-mutations=1 runtime/gate-only=1')
    return 0
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',nargs='?',default='check',choices=['record','check']);args=p.parse_args()
    raise SystemExit(main(args.action=='record'))
