#!/usr/bin/env python3
"""Packed directory corruption and boot-cycle rows for the F011 successor."""
import argparse
from pathlib import Path
import time
import f011_status_comfort_prefilter as PACK
import f011_status_product_card as C
import dwx_retroactive_red_replay as R
import dwx_comfort_resume as COMFORT
import block_26_f011_dwx_prefilter as BOOT
import d81_persistence_fault as D81
from elf_truth import ElfTruth

BUILD=C.ROOT/'build/v2.1/f011-status-disk-prefilter-r1'

def fork():
    R.check()
    contract=R.load(R.CONTRACT_PATH)
    return R.verify_binding(contract['inputs']['cycle_probe_binary'],'qualified four-patch navigation fork')

def corrupt_directory():
    PACK.check()
    binary=fork()
    out=BUILD/'corrupt-directory';out.mkdir(parents=True,exist_ok=False)
    original=PACK.MEDIUM.read_bytes();image=bytearray(original)
    slot=next(s for s in D81.directory_slots(image) if s.record[5:21].rstrip(b'\xa0')==b'L65INDEX')
    offset=D81.sector_offset(slot.track,slot.sector)+slot.index*32+3
    image[offset]=81
    negative=out/'corrupt-index-directory.d81';negative.write_bytes(image)
    changed=[i for i,(a,b) in enumerate(zip(original,image)) if a!=b]
    C.require(changed==[offset],'directory corruption changed more than one byte')
    args=argparse.Namespace(xemu=binary,rom=BOOT.ROM,sd_image=BOOT.SD_IMAGE,timeout=90)
    run=R.start_run('corrupt-index',negative,out,args);m=run['monitor']
    truth=ElfTruth.read(C.ELF,llvm_readobj=C.B.READOBJ)
    status='UNPROVEN'
    try:
        before=m.screen()
        m.type_text("(require 'repl-comfort)\n")
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            screen=m.screen()
            if COMFORT.active(screen)=='LISP65>' and COMFORT.fresh_result(before,screen,'*** LOAD: CANNOT OPEN'):break
            time.sleep(.03)
        m.command('t1')
        (out/'oracle-framebuffer.txt').write_text(screen)
        addr=truth.section('.noinit.lisp65_f011_status').address
        raw=m.memory_range(addr,3);(out/'f011-record.bin').write_bytes(raw)
        C.require(COMFORT.active(screen)=='LISP65>' and COMFORT.fresh_result(before,screen,'*** LOAD: CANNOT OPEN'),
                  'corrupt directory did not raise LOAD_OPEN')
        C.require(not COMFORT.fresh_result(before,screen,'NIL'),'read failure became NIL')
        status='PASS'
    finally:
        outputs=R.finish_run(run)
        (out/'receipt.json').write_bytes(C.canonical({'status':status,'product':C.bind(C.ELF),
          'original_medium':C.bind(PACK.MEDIUM),'negative_medium':C.bind(negative),
          'corruption':{'directory_track':slot.track,'directory_sector':slot.sector,'file':'L65INDEX',
             'offset':offset,'old_start_track':original[offset],'new_start_track':81},
          'outputs':outputs,'device_claim':False}))
    print('corrupt directory -> LOAD_OPEN PASS',flush=True)

def boot_cycles():
    PACK.check();BOOT.XEMU=fork();BOOT.BUILD=BUILD/'boot'
    C.require(not BOOT.BUILD.exists(),'boot-cycle receipt is one-shot')
    rows=[]
    for repeat in range(3):
        for label,medium in [('before',PACK.SEALED/'lisp65-v2.1-comfort.d81'),('after',PACK.MEDIUM)]:
            rows.append(BOOT.run_to_framebuffer(label+str(repeat),medium,['LISP65>']))
    values={label:[r['emulated_CPU_DMA_cycles'] for r in rows if r['id'].startswith(label)] for label in ('before','after')}
    means={k:sum(v)/len(v) for k,v in values.items()}
    value={'rows':rows,'fork':C.bind(BOOT.XEMU),'cycles':values,'means':means,
       'delta_percent':(means['after']/means['before']-1)*100,
       'noise_ranges':{k:max(v)-min(v) for k,v in values.items()},
       'cutpoint':'first observed native prompt; monitor polling contributes reported sampling spread',
       'claim':'emulated CPU/DMA boot cycles only, not device or wall-clock latency'}
    (BOOT.BUILD/'receipt.json').write_bytes(C.canonical(value))
    print(value['delta_percent'],value['noise_ranges'],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['corrupt','boot']);a=p.parse_args()
    if a.action=='corrupt':corrupt_directory()
    else:boot_cycles()
