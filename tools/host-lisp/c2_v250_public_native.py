#!/usr/bin/env python3
"""Qualify the Comfort-default source authority; no reproduction claim."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
AUTHORITY=ROOT/'config/c2-v250-public-build-authority.json'
MANIFEST=ROOT/'config/comfort-default-native/manifest.json'
def canonical(v):return (json.dumps(v,indent=2,sort_keys=True)+'\n').encode()
def require(ok,message):
    if not ok:raise ValueError(message)
def local(name):
    p=Path(name);require(not p.is_absolute() and '..' not in p.parts,'non-local path');return ROOT/p
def bound(row):
    p=local(row['path']);require(p.is_file() and not p.is_symlink(),'missing/aliased input: '+row['path'])
    raw=p.read_bytes()
    import c2_v250_public_normalization as Z
    require(Z.identity(raw)=={k:row[k] for k in ('bytes','sha256')} or Z.accepts(row['path'],raw,{k:row[k] for k in ('bytes','sha256')}),'input identity drift: '+row['path']);return raw
def validate(a):
    require(a['release']=='2.5.0','release drift')
    expected={str(p.relative_to(ROOT)) for d in ('config/comfort-default-native','config/comfort-default-plane') for p in (ROOT/d).rglob('*') if p.is_file()}|{'lib/repl-comfort-v250.lisp','lib/comfort-state-address.lisp'}
    rows=a['source_authorities'];require({r['path'] for r in rows}==expected and len(rows)==len(expected),'source authority population drift')
    for row in rows+a['inherited_authorities']:bound(row)
    manifest=json.loads(bound(a['native_projection']))
    for row in manifest['replacements']:bound(row['source'])
    for row in manifest['linker']:bound(row)
    require(a['raw_pair']['ELF']['sha256']=='d555f01fbac51bb5fbc035b2b595e95e3c8e3bedc584c87112bca8b073e31444','wrong Final ELF')
    # Ancestor identities inside overlays describe lineage, not this product.
    return dict(status='PASS: COMFORT-DEFAULT SOURCE AUTHORITY',inputs=len(rows),compiler_invocations=0,public_reproduction=False)
def check():return validate(json.loads(AUTHORITY.read_text()))
def selftest():
    a=json.loads(AUTHORITY.read_text());result=validate(a)
    trials=[]
    v=copy.deepcopy(a);v['source_authorities'].pop();trials.append(v)
    v=copy.deepcopy(a);v['source_authorities'][0]['sha256']='0'*64;trials.append(v)
    v=copy.deepcopy(a);v['raw_pair']['ELF']['sha256']='66165507';trials.append(v)
    for v in trials:
        try:validate(v)
        except ValueError:pass
        else:raise ValueError('authority mutation survived')
    return dict(result,mutations_rejected=len(trials))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['check','selftest']);a=p.parse_args();print(json.dumps(globals()[a.mode](),indent=2))
