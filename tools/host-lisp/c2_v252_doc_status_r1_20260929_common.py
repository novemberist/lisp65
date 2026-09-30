"""Dated doc-status receipts; exclusive creation, immutable ancestry, no product claim."""
import argparse, hashlib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
def sha(path): return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
def history(expected):
    actual = {p: sha(p) for p in expected}
    if actual != expected: raise ValueError('immutable predecessor drift')
    for p in actual:
        trial = dict(actual); trial[p] = '0'*64
        if trial == expected: raise ValueError('history mutation survived')
    return actual

def finish(name, derive, predecessors, inputs):
    p=argparse.ArgumentParser(); p.add_argument('action', choices=('selftest','record','check')); a=p.parse_args()
    value=dict(format='lisp65-doc-status-successor-v1', date='2026-09-29',
               status='PASS', predecessor=history(predecessors), current=derive(),
               inputs={str(Path(n).relative_to(ROOT) if Path(n).is_absolute() else n): sha(n) for n in inputs},
               claim_limit='Documentation reconciliation only; no 2.5.2 Final or full check-host qualification')
    raw=(json.dumps(value,indent=2,sort_keys=True)+'\n').encode()
    path=ROOT/('config/c2-v252-doc-status-r1-20260929-'+name+'-receipt.json')
    if a.action=='record':
        with path.open('xb') as f: f.write(raw)
    elif a.action=='check' and path.read_bytes()!=raw: raise ValueError('successor receipt drift')
    print(name+': '+a.action+' PASS')
