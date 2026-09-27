#!/usr/bin/env python3
"""Dated v240 historical control; never an export/bundle fallback."""
import hashlib
import json
import subprocess
import c2_v240_bundle_docs_gate as G

REVISION='9f8927a24ec0920a6a54c1d9a2b15867f693a104'

def read(path):
    return subprocess.check_output(['git','show',REVISION+':'+path],cwd=G.ROOT)

def main():
    contract=json.loads(read('config/c2-v240-bundle-docs.json'))
    authority=json.loads(read('config/c2-v240-public-build-authority.json'))
    files={p:read(p) for p in G.DOCS}
    G.validate(files,contract['documents'],authority)
    changed=0
    for path in G.DOCS:
        live=(G.ROOT/path).read_bytes()
        if live!=files[path]:
            trial=dict(files);trial[path]=live
            try:G.validate(trial,contract['documents'],authority)
            except ValueError:changed+=1
            else:raise ValueError('live successor accepted as historical bytes')
    if not changed:raise ValueError('no falling live-document control')
    print('v240 era 2026-09-27: PASS historical documents=6 live controls='+str(changed))


HISTORY = {'tools/host-lisp/c2_v240_bundle_docs_gate.py': '67a7071d169cae7fef59d4eb6b556118c35efb443ef6c8d26a32758772110adc', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/comfort-default-final-20260927.json': 'c2638932f98fe4742394d01d05ff907358db307d97239500477f52ebe8397112'}
def history_check():
    import hashlib
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    def validate(rows):
        if rows != HISTORY:raise ValueError('successor predecessor drift')
    rows={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in HISTORY}
    validate(rows)
    for p in rows:
        bad=dict(rows);bad[p]='0'*64
        try:validate(bad)
        except ValueError:pass
        else:raise ValueError('predecessor mutation survived')
history_check()

if __name__=='__main__':main()
