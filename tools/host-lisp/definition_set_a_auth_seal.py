"""Seal replacement-Seed qualification, including its explicit holds."""
from pathlib import Path
import hashlib, json

ROOT=Path(__file__).resolve().parents[2]
TARGET=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/definition-set-a-auth-seed.json'
def bind(path):
    path=path.resolve();data=path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
roots=[
 'build/definition-set-a-auth-lifetime-r2/receipt.json',
 'build/definition-set-a-auth-projection-r1/receipt.json',
 'build/definition-set-a-product-r3-preflight/command-ready.json',
 'build/definition-set-a-product-r2/wplto/definition-set-a-seed-price.json',
 'build/definition-set-a-seed-medium-r2/packed-receipt.json',
 'build/definition-set-a-auth-five-ide-r1/receipt.json',
 'build/definition-set-a-auth-prerequisites-r1/receipt.json',
 'build/definition-set-a-auth-native-group-r1/receipt.json',
 'build/definition-set-a-auth-capacity-r1/receipt.json',
 'build/definition-set-a-auth-ledger-5-r2/receipt.json',
 'build/definition-set-a-auth-stages-seed-5-r1/receipt.json',
 'build/definition-set-a-auth-abort-r4/receipt.json',
 'build/definition-set-a-auth-native-natural-r1/receipt.json',
 'build/definition-set-a-auth-native-equal-phase-r1/receipt.json',
 'build/definition-set-a-r3/currency-proof.json',
 'build/definition-set-a-r3/gc-ledger/rows.json',
 'build/definition-set-a-r3/gc-attribution.json',
 'build/definition-set-a-r3/gc-charges.json',
 'build/definition-set-a-r3/gc-heap.json',
 'build/definition-set-a-r3/gc-root-difference.json',
 'build/definition-set-a-r3/gc-code-identity.json',
 'build/definition-set-a-r3/gc-closure.json',
 'build/definition-set-a-r3/allocation-attribution.json',
 'build/definition-set-a-r3/phase-decomposition.json',
 'build/definition-set-a-auth-alloc-before-5-r1/receipt.json',
 'build/definition-set-a-auth-alloc-seed-5-r1/receipt.json',
 'build/definition-set-a-auth-lane-gc-charges-r1/receipt.json',
]
for role in ('baseline','candidate'):
    for kind in ('equal','charges'):
        roots.append(f'build/definition-set-a-auth-gc-{kind}-{role}-0/receipt.json')
paths={ROOT/p for p in roots}
def consume(v):
    if isinstance(v,dict):
        if isinstance(v.get('path'),str) and isinstance(v.get('sha256'),str):
            p=ROOT/v['path'];b=bind(p)
            assert b['sha256']==v['sha256'],str(p)
            if 'bytes' in v:assert b['bytes']==v['bytes'],str(p)
            paths.add(p.resolve())
        for x in v.values():consume(x)
    elif isinstance(v,list):
        for x in v:consume(x)
def main():
    assert not TARGET.exists(),'never overwrite the seal'
    for p in roots:consume(json.loads((ROOT/p).read_text()))
    paths.update((ROOT/'tools/host-lisp').glob('definition_set_a_auth_*.py'))
    paths.add(ROOT/'docs/planning/definition-set-a-auth-seed-report.md')
    paths.update(ROOT/p for p in ('src/c2_product_runtime.c','src/c2_product_runtime.h','src/c2_session_emitter.c'))
    result=dict(status='REPLACEMENT SEED MEASURED; QUALIFICATION HOLD',authority='20e4aa49',
        consumed=dict(seed=2,final=0,link=0),remaining_budget=dict(seed=0,final=1,link=1),
        holds=['Matched-GC additional group-marker roots and net symbol: named-cost disposition not inferred',
               'Extra definition collection: net 25 Cons in grouped Lisp bridge, conditional cost disposition'],
        remaining=['full write-neutral check-source','Final/link and final-medium qualification'],
        native_abort='PASS, diagnostic real abort entry, restored free-text shim, foreign objects identical, 9/7/new group 42',
        bindings=[bind(p) for p in sorted(paths)])
    TARGET.write_text(json.dumps(result,indent=2)+'\n')
    print('SEALED',len(paths),'bindings; budget 2/0/0; Final/link held')
if __name__=='__main__':main()
