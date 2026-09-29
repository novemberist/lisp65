#!/usr/bin/env python3
"""Verify the immutable 2.5.0 authorities in release commit 9665f97f."""
import json
from unittest.mock import patch
import evidence_era as E
import c2_v250_public_product as P
import c2_v250_bundle_docs_gate as D
import c2_v250_reproduction_gate as R
COMMIT='9665f97f'
ROOT=P.ROOT

def main():
    paths=set()
    def visit(v):
        if isinstance(v,dict):
            if {'path','bytes','sha256'}<=set(v) and not v['path'].startswith('build/'):paths.add(v['path'])
            for x in v.values():visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    for name in ['config/c2-v250-public-build-authority.json','config/c2-v250-public-replay.json','config/c2-v250-public-media.json','config/c2-v250-reproductions.json','config/c2-v250-bundle-docs.json']:
        paths.add(name);visit(json.loads(E.era_blob(COMMIT,name)))
    paths.update(D.REQUIRED)
    with E.host_source_world(COMMIT,paths) as reads:
        result=P.preflight();D.check(ROOT);R.validate(json.loads(R.RECEIPT.read_text()))
    original=E.era_blob
    victim='config/comfort-default-native/sources/repl.c'
    def corrupt(commit,path):return original(commit,path)+(b'changed' if path==victim else b'')
    with patch.object(E,'era_blob',corrupt),E.host_source_world(COMMIT,paths):
        try:P.preflight()
        except ValueError:pass
        else:raise ValueError('corrupted historical source survived')
    print(json.dumps(dict(status='PASS',release_commit=COMMIT,historical_reads=len(reads),native=result,mutation_rejected=True),indent=2))
if __name__=='__main__':main()
