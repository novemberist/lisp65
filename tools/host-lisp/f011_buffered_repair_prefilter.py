#!/usr/bin/env python3
"""Artifact-only repaired F011 medium and bounded packed-byte runtime checks."""
import argparse
import json
from pathlib import Path
import time

import f011_buffered_repair_product_card as C
import f011_status_media as MEDIA
import f011_status_comfort_prefilter as PACK
import dwx_retroactive_red_replay as RUN
import dwx_comfort_resume as COMFORT
import d81_persistence_fault as D81
from elf_truth import ElfTruth
from evidence_era import stable_recorded_on

BUILD=C.BUILD/'packed-prefilter'
FORK=C.ROOT/'build/dwx/buffered-repair-three-patch-requalification-r2'

def write(path,value):
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')

def qualify():
    C.configure();C.C.configure=C.configure
    scope=C.WPLTO/'owner-scope-result.json';accept=C.BUILD/'artifact-acceptance.json'
    assert C.C.load(scope)['status']==C.C.load(accept)['status']=='PASS'
    proof=C.C.load(C.BUILD/'final-native-proof.json')
    pair=[C.C.bind(C.ELF),C.C.bind(C.PRG)]
    assert proof['pair']==pair and proof['native_status_rows'][0x44]['return_value']==0
    for filename in ('seed-to-final-attribution.json','predecessor-attribution.json'):
        assert C.C.load(C.BUILD/filename)['unexplained_members']==0
    difference=C.C.load(C.BUILD/'predecessor-attribution.json')
    write(C.DIFFERENCE,difference)
    status='PASS: F011 PRODUCT SCOPE AND ACCEPTANCE; DWX PENDING'
    write(C.RECEIPT,dict(status=status,recorded_on=stable_recorded_on(C.RECEIPT),
        authority=C.authority(),preflight=C.C.bind(C.PREFLIGHT_RECEIPT),
        artifacts_after=dict(zip(('ELF','PRG'),pair)),scope=C.C.bind(scope),acceptance=C.C.bind(accept),
        difference=C.C.bind(C.DIFFERENCE),final_product={'composed_bank2':proof['bank2']},
        budget={'seed_WPLTO':1,'final_C_LTO':1,'product_links':1,'device_contacts':0},
        review_ready=False))
    return status

def configure():
    C.configure();C.C.configure=C.configure
    MEDIA.BUILD=BUILD/'product'
    MEDIA.qualified_pair=qualify
    PACK.BUILD=BUILD/'comfort'
    PACK.MEDIUM=PACK.BUILD/'lisp65-v2.1-f011-comfort.d81'
    PACK.RECEIPT=PACK.BUILD/'packed-receipt.json'
    PACK.RUNTIME=PACK.BUILD/'runtime'

def pack():
    assert not BUILD.exists(),'artifact packing is one-shot'
    BUILD.mkdir()
    configure();status=qualify();MEDIA.configure(status)
    before=[C.C.bind(C.ELF),C.C.bind(C.PRG)]
    MEDIA.M.build_medium()
    PACK.build()
    assert before==[C.C.bind(C.ELF),C.C.bind(C.PRG)]
    print('REPAIRED PRODUCT + UNCHANGED COMFORT PACKED',flush=True)

def runtime(corrupt=False):
    configure();PACK.check()
    fork=C.C.load(FORK/'receipt.json')
    assert fork['status']=='PASS: THREE-PATCH FORK REQUALIFIED' and fork['reproduced_reds']==3
    manifest=C.C.load(C.ROOT/fork['manifest']['path'])
    assert C.C.bind(C.ROOT/fork['manifest']['path'])['sha256']==fork['manifest']['sha256']
    binary=Path(manifest['binary']['path'])
    assert RUN.sha256(binary)==manifest['binary']['sha256']
    out=BUILD/('corrupt-directory' if corrupt else 'clean-boot-require')
    out.mkdir()
    medium=PACK.MEDIUM
    mutation=None
    if corrupt:
        original=medium.read_bytes();image=bytearray(original)
        slot=next(s for s in D81.directory_slots(image) if s.record[5:21].rstrip(b'\xa0')==b'L65INDEX')
        offset=D81.sector_offset(slot.track,slot.sector)+slot.index*32+3
        image[offset]=81
        assert [i for i,(a,b) in enumerate(zip(original,image)) if a!=b]==[offset]
        medium=out/'corrupt-directory.d81';medium.write_bytes(image)
        mutation={'offset':offset,'before':original[offset],'after':81}
    args=argparse.Namespace(xemu=binary,rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
        sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')),timeout=90)
    t=ElfTruth.read(C.ELF,llvm_readobj=C.C.B.READOBJ)
    C.witness_absent(t)
    run=RUN.start_run('directory' if corrupt else 'clean',medium,out,args);m=run['monitor']
    good=False;clock={}
    try:
        before=m.screen();(out/'boot-framebuffer.txt').write_text(before)
        assert 'WORKBENCH 2.0.0' in RUN.ROWS.decoded_framebuffer(before)
        assert 'CANNOT OPEN' not in RUN.ROWS.decoded_framebuffer(before)
        m.command('t1')
        verified=m.memory_range(t.symbol('f011_clock_verified').value,1)
        frames=m.memory_range(0xff83,2)
        (out/'boot-clock-raw.bin').write_bytes(verified+frames)
        assert verified==b'\x01','first-read clock progress cache not set'
        clock={'verified_address':t.symbol('f011_clock_verified').value,'raw':(verified+frames).hex(),
            'meaning':'fresh emulator boot reached prompt through emitted initial clock-progress guard; no physical-clock claim'}
        m.command('t0');m.type_text("(require 'repl-comfort)\n")
        wanted='*** LOAD: CANNOT OPEN' if corrupt else 'T'
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            screen=m.screen()
            if COMFORT.active(screen)=='LISP65>' and COMFORT.fresh_result(before,screen,wanted):break
            time.sleep(.03)
        m.command('t1');screen=m.screen()
        (out/'require-framebuffer.txt').write_text(screen)
        good=COMFORT.active(screen)=='LISP65>' and COMFORT.fresh_result(before,screen,wanted)
        if corrupt: good=good and not COMFORT.fresh_result(before,screen,'NIL')
    finally:
        outputs=RUN.finish_run(run)
        write(out/'receipt.json',dict(status='PASS' if good else 'RED',
            pair=[C.C.bind(C.ELF),C.C.bind(C.PRG)],medium=C.C.bind(medium),
            fork_requalification=C.C.bind(FORK/'receipt.json'),clock=clock,mutation=mutation,
            outputs=outputs,device_acceptance_claimed=False))
    assert good,'packed runtime row failed'
    print('PACKED DIRECTORY ERROR PASS' if corrupt else 'PACKED BOOT/CLOCK/REQUIRE PASS',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('pack','boot','corrupt','comfort'))
    a=p.parse_args()
    if a.action=='pack':pack()
    elif a.action=='comfort':
        configure();PACK.check()
        result=COMFORT.execute(PACK.RUNTIME,calibrate_collection=True,successor_receipt=PACK.RECEIPT)
        assert result['status'].startswith('EXECUTED ROWS PASS'),result['status']
    else:runtime(a.action=='corrupt')
