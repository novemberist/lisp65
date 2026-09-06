#!/usr/bin/env python3
"""Bounded combined-C pricing; never run the product WPLTO/link producer."""
import json
import hashlib
from pathlib import Path
import subprocess

import f011_status_instrument_pricing as L
import f011_status_product_card as C
from elf_truth import ElfTruth
from evidence_era import stable_recorded_on

ROOT=L.ROOT
OUT=ROOT/'build/v2.1/f011-frame-instrument-pricing'
W=C.WPLTO
HEADER=ROOT/'tests/fixtures/f011-frame-witness-pricing.h'

def replace(s,a,b):
    assert s.count(a)==1, a[:80]
    return s.replace(a,b,1)

def sources():
    io=(ROOT/'src/io.c').read_text()
    io=replace(io,'#include "f011_status_witness.h"','#include "f011-frame-witness-pricing.h"')
    a=io.index('static LISP65_C2_MAPPED_F011_COLD_FN unsigned char f011_wait_not_busy(')
    b=io.index('/* F011 read of ONE',a)
    io=io[:a]+io[b:]
    io=replace(io,'''    unsigned char status;
    m65_io_enable();
    lisp65_f011_take_context();''','''    f011_status_record record={0};
    uint16_t start;
    m65_io_enable();
    if(!f011_frame_live()) {
        record.tag=F011_CLOCK_UNOBSERVED;
        f011_frame_publish(&record);
        return LISP65_F011_READ_FAILED;
    }
    record.validity=F011_CLOCK_INITIAL_VALID;
    lisp65_f011_take_context();''')
    a=io.index('    status = f011_wait_not_busy(20000u);')
    b=io.index('    *((volatile unsigned char *)0xD084)',a)
    io=io[:a]+'''    record.after_spin_d082=LISP65_F011_READ8(0xd082u);
'''+io[b:]
    command='    *((volatile unsigned char *)0xD081) = 0x40;'
    io=replace(io,command,'''    if(!f011_frame_sample(&start)) {
        record.tag=F011_CLOCK_UNOBSERVED;
        f011_frame_publish(&record);
        return LISP65_F011_READ_FAILED;
    }
'''+command)
    a=io.index('    status = f011_wait_not_busy(60000u);')
    b=io.index('    lisp65_f011_map_buffer();',a)
    io=io[:a]+'''    record.validity|=F011_READ_ISSUED;
    f011_frame_wait(&record,start);
    f011_frame_publish(&record);
    if(record.tag!=F011_FIRST_SUCCESS) return LISP65_F011_READ_FAILED;
'''+io[b:]
    main=replace((ROOT/'src/main.c').read_text(),'#include "f011_status_witness.h"','#include "f011-frame-witness-pricing.h"')
    return {'io.c':io,'main.c':main}

def flags():
    # Only in-memory configuration. No producer entrypoint is invoked.
    C.configure()
    identity=C.B.toolchain_identity()
    manifest=C.PLANE/'product/substitution-artifacts.json'
    artifact=json.loads(manifest.read_text())
    assert artifact['product_build_id_u32']==0x4a1713ab
    features=[x.split('=',1)[1] for x in (W/'resolved-profile.txt').read_text().splitlines() if x.startswith('feature_defines=')]
    assert len(features)==1 and features[0]
    defs=[*C.PRODUCT.definitions(artifact),*C.PRODUCT.scoped_probe_definitions(tuple(features[0].split(','))) ]
    f=['-Oz','-Wall','-ffile-compilation-dir=.','-fdebug-compilation-dir=.','-fcoverage-compilation-dir=.','-mllvm','-rng-seed=0',*[f'-D{x}' for x in defs]]
    for suffix in ['compiler-input-consumption.json','stdlib-input-consumption.json']:
        f+=json.loads((W/('lisp65-c2-substitution-linked.prg.'+suffix)).read_text())['actual_force_include_flags']
    for name in ['stage-config.h','runtime-overlay.prepare.h','resident-island.h','error-text-table.h','c2-kernal-window.generated.h']:
        f+=['-include',str((W/name).relative_to(ROOT))]
    for p in [ROOT/'src',ROOT/'scripts',ROOT/'build/c2.2/substitution',W,ROOT/'build/bytecode',HEADER.parent]:
        f+=['-I',str(p.relative_to(ROOT))]
    return f,identity,L.bind(manifest)

def main():
    authority=subprocess.check_output(['git','show','a78f6d78:docs/planning/v2.0.0-pre-plan.md'],cwd=ROOT)
    assert b'$20' in authority and b'$40' in authority and b'7-byte' in authority
    frozen={str(p):L.bind(p) for p in [C.ELF,C.PRG,W/'lisp65-c2-substitution-linked.prg.lto.o']}
    assert frozen[str(C.ELF)]['sha256']=='29d3ff462afc9c59ad9769fac8098ed0f02900d3c7cf5a37c89855b0444d9cc6'
    L.OUT=OUT; L.W=W
    OUT.mkdir(parents=True,exist_ok=True)
    f,identity,manifest=flags()
    L.write(OUT/'compile-flags.json',json.dumps(f,indent=2)+'\n')
    lanes={}
    for name,replacements in [('baseline',{}),('frontend-control',{x:(ROOT/'src'/x).read_text() for x in ['io.c','main.c']}),('successor',sources())]:
        print('bounded lane:',name,flush=True)
        lanes[name]=L.lane(name,replacements,f)
        if name=='frontend-control':
            assert lanes[name]['projection']==lanes['baseline']['projection'], 'frontend control not equal; no successor price'
    a=lanes['baseline']['projection']; b=lanes['successor']['projection']
    e=ElfTruth.read(C.ELF,llvm_readobj=L.READOBJ)
    calibration={}
    for name in ['main','f011_read_at_far','f011_status_observe','f011_wait_not_busy']:
        calibration[name]=dict(final_bytes=e.symbol(name).bytes, bounded_bytes=a['functions'][name]['bytes'],
                               bias=a['functions'][name]['bytes']-e.symbol(name).bytes)
    for p,v in frozen.items(): assert L.bind(Path(p))==v
    result=dict(format='f011-historical-sequence-frame-pricing-v1',recorded_on=stable_recorded_on(OUT/'receipt.json'),
                authority='a78f6d78',authority_sha256=hashlib.sha256(authority).hexdigest(),
                toolchain=identity,manifest=manifest,frozen=frozen,lanes=lanes,
                group_deltas={k:b['groups'][k]-a['groups'][k] for k in a['groups']},calibration=calibration,
                WPLTO=0,product_links=0,media=0,device_contacts=0,final_link_price=False,
                limits=['bounded combined-C codegen only; no final floor, abort or DWX proof',
                        'clock no-progress fuel is an instruction bound, not elapsed seconds',
                        '600-frame cap is nominal 12s at 50Hz or 10s at 60Hz; rate must be bound',
                        'sampler immediately before READ gives frame-quantized interval, not cycle-exact timing',
                        'added status/time samples perturb historical command spacing; no internal queue claim'])
    L.write(OUT/'receipt.json',json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['group_deltas','calibration','limits']},indent=2))

if __name__=='__main__': main()
