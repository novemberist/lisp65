"""Reviewer-only cold boot ledger: 2.4.0 Final versus Card L Seed."""
import argparse
import json
import os
from card_l_r1_common import ROOT, worlds, preview, arguments, N, R

INSTRUMENT=ROOT/'build/card-l-boot-instrument-r2/instrument.json'

def main():
    p=argparse.ArgumentParser();p.add_argument('--dry-run',action='store_true');p.add_argument('--attempt',default='r2');a=p.parse_args()
    canonical=worlds();identity=json.loads(INSTRUMENT.read_text())
    for w, expected in zip(identity['worlds'],canonical):
        for key in ('ELF','medium'):assert w[key]==expected[key]
        N.checked_binding(w['binary'])
    for key in ('configuration','parent'):N.checked_binding(identity[key])
    out=ROOT/f'build/card-l-native-boot-{a.attempt}'
    if a.dry_run:
        for w in identity['worlds']:preview(w,out/w['role'],'boot',300)
        print('DRY RUN PASS: prompt identity, carrier writes=0, stack>=0xce00; Initializing/banner-return cycle ledger; no emulator launched')
        return
    out.mkdir(exist_ok=False)
    prior=R.ProbeMonitor
    class Monitor(prior):
        def wait_screen(self,required,timeout=20):return super().wait_screen(required,timeout=180)
    R.ProbeMonitor=Monitor
    rows=[]
    for w in identity['worlds']:
        d=out/w['role'];d.mkdir()
        os.environ['LISP65_BOOT_LEDGER']=str(d/'boot.txt')
        os.environ['LISP65_CARRIER_WATCH']=str(d/'writes.txt')
        run=None
        try:
            run=R.start_run('boot',N.checked_binding(w['medium']),d,arguments(w,300))
            prompt=run['monitor'].screen();(d/'prompt.txt').write_text(prompt)
            assert 'LISP65>' in R.ROWS.decoded_framebuffer(prompt)
            events={}
            for line in (d/'boot.txt').read_text().splitlines():
                f=line.split()
                if f[0]=='E':events.setdefault(int(f[1]),int(f[2]))
            assert {0,10,11}<=events.keys()
            writes=(d/'writes.txt').read_text().splitlines()
            assert len(writes)==1 and writes[0].startswith('END ')
            _,low,count=writes[0].split();assert int(low)>=0xce00 and int(count)==0
            rows.append(dict(world=w,stack_low=int(low),carrier_writes=int(count),
                initializing_cycles=events[10]-events[0],prompt_cycles=events[11]-events[0],
                prompt_boundary='ELF-derived banner-return, followed by live prompt identity check',
                prompt=N.bind(d/'prompt.txt'),ledger=N.bind(d/'boot.txt'),writes=N.bind(d/'writes.txt')))
        finally:
            if run:R.finish_run(run)
    assert N.checked_binding(rows[0]['prompt']).read_bytes()==N.checked_binding(rows[1]['prompt']).read_bytes()
    for row in rows:print(row['world']['role'],row['initializing_cycles'],row['prompt_cycles'],hex(row['stack_low']))
    # Preserve raw cycle deltas; wall-clock conversion is a reviewer decision.
    result=dict(status='PASS: PROMPT IDENTITY, ZERO CARRIER WRITES, STACK FLOOR',rows=rows,
        delta_cycles={k:rows[1][k]-rows[0][k] for k in ('initializing_cycles','prompt_cycles')},instrument=N.bind(INSTRUMENT))
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
