#!/usr/bin/env python3
"""Fresh renderer-world execution of the eight authorized diagnostic rows.

Reuses the existing headless transport and guest oracles, never historical
execution receipts. The optional histogram snapshot runs only after CPU stop.
"""
import argparse
import copy
import hashlib
import json
import os
import re
from pathlib import Path

import capacity_prefilter_media as MEDIA
import dwx_mirrored_prefilter_rows as ROWS
from capacity_pc_histogram_tool import ROOT, OUT, bind
from evidence_era import stable_recorded_on

def execute(row_id, observer, attempt):
    authority=MEDIA.check()
    selected=next(r for r in authority['rows'] if r['id']==row_id)
    row=copy.deepcopy(selected['stimulus_and_oracle'])
    row.setdefault('input','')
    assert row['input']!='(repl)\n'
    instrument=json.loads((OUT/'instrument-build.json').read_text())
    base=json.loads((ROOT/'build/dwx/xemu-buffered-repair-three-patch-r2/dwx-xemu-cycle-probe-adapter.json').read_text())
    identity=instrument['binary'] if observer else base['binary']
    binary=ROOT/identity['path']; assert bind(binary)['sha256']==identity['sha256']
    output=OUT/'mirrored'/attempt/('observed' if observer else 'control')/row_id
    output.mkdir(parents=True)
    histogram=output/'pc-stopped.txt'
    if observer: os.environ['LISP65_DWX_PC_OUTPUT']=str(histogram)
    else: os.environ.pop('LISP65_DWX_PC_OUTPUT',None)
    args=argparse.Namespace(xemu=binary,
        rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
        sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')),timeout=300)
    original=ROWS.Monitor
    snapshots=[]
    class Monitor(original):
        def type_text(self, text):
            if text: return super().type_text(text)
        def wait_screen(self, required, timeout=12):
            return super().wait_screen(required,timeout=max(timeout,60))
        def command(self, command, *args, **kwargs):
            response=super().command(command,*args,**kwargs)
            if command=='t1' and observer:
                saved=super().command('~pcsave')
                assert 'DWX PC save: 0' in saved,saved
                assert histogram.is_file()
                snapshots.append(bind(histogram))
            return response
    ROWS.Monitor=Monitor
    result=None; stopped=None; error=None
    try:
        result,stopped=ROWS.run_headless(row,ROOT/selected['medium']['path'],output,args)
        screen=Path(result['outputs']['framebuffer']['path'])
        text=ROWS.decoded_framebuffer(screen.read_text())
        if row_id=='init-l65-valid':
            # Banner graphics can share the remainder of the first screen row;
            # the device counterpart requires one visible 17 before the banner,
            # not an otherwise empty framebuffer row.
            assert len(re.findall(r'(?<![0-9])17(?![0-9])',text))==1
            assert text.index('17')<text.index('WORKBENCH 2.0.0')
        if observer:
            assert len(snapshots)==1 and snapshots[0]==bind(histogram)
            header=histogram.read_text().splitlines()[0].split()
            assert header[0]=='H' and header[1]=='1' and int(header[2])>0
        MEDIA.check()
    except BaseException as exc:
        error=repr(exc)
        raise
    finally:
        ROWS.Monitor=original
        receipt=output/'receipt.json'
        receipt.write_text(json.dumps(dict(recorded_on=stable_recorded_on(receipt),
            status='RED' if error else 'PASS',error=error,row=selected,
            binary=bind(binary),rom=dict(sha256=hashlib.sha256(args.rom.read_bytes()).hexdigest()),
            system_sd=dict(sha256=hashlib.sha256(args.sd_image.read_bytes()).hexdigest()),
            media_receipt=bind(MEDIA.BUILD/'receipt.json'),executor=bind(Path(__file__)),
            transport_executor=bind(Path(ROWS.__file__)),observer=observer,
            execution=result,stopped=stopped,histogram=snapshots[-1] if snapshots else None,
            historical_results_inherited=False,comfort_entry=False,comfort_claim=False,
            physical_keyboard_claim=False,gc_crossing_claim=False,device_contacts=0),indent=2)+'\n')
    print(row_id,'observed' if observer else 'control','PASS',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('row',choices=[r['id'] for r in MEDIA.rows()])
    p.add_argument('--observer',action='store_true');p.add_argument('--attempt',default='r1')
    a=p.parse_args();execute(a.row,a.observer,a.attempt)
