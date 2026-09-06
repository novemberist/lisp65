#!/usr/bin/env python3
"""Bounded B3-1 transport discrimination; evidence, not admission."""
import argparse
import json
from pathlib import Path
import time
import dwx_retroactive_red_replay as R

def main():
    p=argparse.ArgumentParser();p.add_argument('--xemu',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.xemu=a.xemu.resolve();a.out=a.out.resolve();a.out.mkdir()
    a.rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM'))
    a.sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img'));a.timeout=60
    row=R.load(R.CONTRACT_PATH)['rows'][1]
    medium=R.verify_binding(row['product_medium'],'sealed B3-1')
    run=R.start_run('b31-probe',medium,a.out,a);m=run['monitor'];trace=[]
    def sample(label):
        trace.append(dict(label=label,screen=m.screen(),ring=m.memory16(0xff8d).hex(),
            counters=m.memory16(0xbcfc).hex(),cpu=m.command('r')))
    try:
        sample('before-one-event')
        m.type_text(row['stimulus'])
        for i in range(12):
            time.sleep(1);sample('after-'+str(i+1))
        m.command('t1');sample('stopped')
    finally:
        (a.out/'raw-trace.json').write_text(json.dumps(trace,indent=2)+'\n')
        outputs=R.finish_run(run)
        (a.out/'receipt.json').write_text(json.dumps(dict(binary=R.bind(a.xemu),
            medium=R.bind(medium),stimulus=row['stimulus'],outputs=outputs,
            admission_claim=False),indent=2)+'\n')

if __name__=='__main__':main()
