"""Card L resolver provenance successor (2026-09-25, authority 50ffcc9c).
Runs unchanged resolver mutations inside isolated option-a fixtures. Only
runtime/gate bindings and creation date may differ from nested-error recovery.
Mutation matrix: inherited source/index/capacity and three successor mutations;
one corrupted SHA per historical input; changed semantic claim rejected.
Record writes a fresh scratch receipt, never a predecessor.
"""
import argparse
import copy
from pathlib import Path
import c2_require_resolver_gate as G
HISTORY={'tools/host-lisp/c2_require_resolver_gate.py': '2918b08e7aa52d4d146af9887d6af0cdde100c00f2727e43b33f51f8add231fb', 'tools/host-lisp/nested_error_recovery_resolver_successor.py': '0eeaaef23136f67fcf3104c059c4a2d8f599f32e231fec1d8315f21c2ce830c2', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/library-require-resolver-nested-error-recovery-successor-20260923.json': '859fa6eab9f0446b03d48f659f17bc433e2eff745e549573ea6572590b2cf754'}

PREDECESSOR=G.SUCCESSOR_RECEIPT
TARGET=PREDECESSOR.with_name('library-require-resolver-card-l-successor-20260925.json')
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
    print('Card L resolver: PASS historical-mutations=3 semantic-mutations=1 runtime/gate-only=1')
    return 0
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',nargs='?',default='check',choices=['record','check']);args=p.parse_args()
    raise SystemExit(main(args.action=='record'))
