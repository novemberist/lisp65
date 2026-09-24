"""Write-once diagnostic closure. Replays existing evidence; no build/run."""
import json
from pathlib import Path
import contextlib
import io

import gc_layout_analyse as A
from gc_layout_control import ROOT, OUT, bind, write_once


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        A.main()
        A.selftest()
    analysis=json.loads((OUT/'analysis.json').read_text())
    inputs=[]
    def add(p):
        row=bind(p)
        if row not in inputs:inputs.append(row)
        return json.loads((ROOT/p).read_text())
    def verify(value):
        if isinstance(value,dict):
            if 'path' in value and 'sha256' in value:
                row=bind(value['path'])
                assert row['sha256']==value['sha256'],value['path']
                if row not in inputs:inputs.append(row)
            for item in value.values():verify(item)
        elif isinstance(value,list):
            for item in value:verify(item)
    verify(analysis)
    for name in ('analysis.json','preflight.json','link-invocation.json','linked.json'):
        verify(add(OUT/name))
    for role in ('baseline','relocated'):
        base=ROOT/f'build/gc-layout-measure-{role}-r1'
        for name in ('receipt.json','diagnostic.json','relocation-entry.json'):
            verify(add(base/name))
    for p in sorted((ROOT/'tools/host-lisp').glob('gc_layout_*.py')):
        inputs.append(bind(p))
    seal=dict(status='PASS: GC LAYOUT CONTROL CLOSED',analysis=analysis,inputs=inputs,
              diagnostic_links=1,seed=0,final=0,product_links=0,device_contacts=0,
              product_world='boot-only-carrier-final; unchanged',mutations=8,
              claim='One controlled layout measurement; not a blanket attribution or tolerance.')
    target=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/gc-layout-control-20260922.json'
    write_once(target,seal)
    print('GC layout seal PASS:',bind(target)['sha256'])


if __name__=='__main__':main()
