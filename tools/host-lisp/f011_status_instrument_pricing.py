#!/usr/bin/env python3
"""Bounded host pricing: no product WPLTO/link, media or device commands."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from elf_truth import ElfTruth
from evidence_era import stable_recorded_on

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/v2.1/f011-status-instrument-pricing'
W=ROOT/'build/2.6/card6-small-hardening-dma-tuple-repair-product-r3/wplto'
ELF=W/'lisp65-c2-substitution-linked.prg.elf'
HEADER=ROOT/'tests/fixtures/f011-status-instrument.h'
CLANG=ROOT/'tools/llvm-mos/bin/mos-mega65-clang'
READOBJ=Path('/usr/bin/llvm-readobj')
AUTH='f0c467cd'

def bind(p):
    b=p.read_bytes()
    return {'path':str(p.relative_to(ROOT)), 'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def write(p,b):
    p.parent.mkdir(parents=True,exist_ok=True)
    if isinstance(b,str): b=b.encode()
    if p.exists():
        if p.read_bytes()!=b: raise RuntimeError(f'cached artifact drift: {p}')
    else: p.write_bytes(b)
def run(cmd):
    p=subprocess.run([str(x) for x in cmd],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode: raise RuntimeError(p.stderr.decode(errors='replace'))
    return p.stdout
def replace(s,old,new):
    if s.count(old)!=1: raise RuntimeError('source seam drift: '+old[:80])
    return s.replace(old,new,1)

def io_successor(s):
    s=replace(s,'#include "f011_context.h"', '#include "f011_context.h"\n#define LISP65_F011_INSTRUMENT_BODY\n#include "f011-status-instrument.h"')
    s=replace(s,'''    while (fuel--) {
        if (!(LISP65_F011_READ8(0xd082u) & LISP65_F011_STATUS_BUSY))
            return 1;
    }
    return 0;''','''    unsigned char status = LISP65_F011_STATUS_BUSY;
    while (fuel--) {
        status = LISP65_F011_READ8(0xd082u);
        if (!(status & LISP65_F011_STATUS_BUSY)) return status;
    }
    return status;''')
    s=replace(s,'    if (!f011_wait_not_busy(20000u)) return LISP65_F011_READ_FAILED;', '''    status = f011_wait_not_busy(20000u);
    if (status & LISP65_F011_STATUS_BUSY) {
        f011_status_observe(F011_SPINUP_TIMEOUT, status);
        return LISP65_F011_READ_FAILED;
    }''')
    s=replace(s,'    if (!f011_wait_not_busy(60000u)) return LISP65_F011_READ_FAILED;', '''    status = f011_wait_not_busy(60000u);
    if (status & LISP65_F011_STATUS_BUSY) {
        f011_status_observe(F011_READ_TIMEOUT, status);
        return LISP65_F011_READ_FAILED;
    }''')
    s=replace(s,'''        LISP65_F011_STATUS_READ_COMPLETE)
        return LISP65_F011_READ_FAILED;''','''        LISP65_F011_STATUS_READ_COMPLETE) {
        f011_status_observe(F011_MASK_FAILURE, status);
        return LISP65_F011_READ_FAILED;
    }
    f011_status_observe(F011_FIRST_SUCCESS, status);''')
    return s

def main_successor(s):
    return replace(s,'int main(void) {', '''#include "f011-status-instrument.h"
int main(void) {
    lisp65_f011_status_state.tag = F011_UNSEEN;''')

def flags():
    # Configure ONLY Python producer authorities, never execute build drivers.
    import block_26_small_hardening_dma_tuple_repair_product_card as R
    import c2_product_substitution_link as P
    R.configure(); R.R2.configure(); R.BASE.configure_stack()
    R.BASE.PREV.CARD.CARD2.R2.CARD.configure()
    identity=R.BASE.toolchain_identity()
    manifest=ROOT/'build/2.6/card6-small-hardening-dma-tuple-repair-product-r3-preflight/setup-owned/static-plane/narrow-static/product/substitution-artifacts.json'
    artifacts=json.loads(manifest.read_text())
    assert artifacts['product_build_id_u32']==0x4a1713ab
    features=[x.split('=',1)[1] for x in (W/'resolved-profile.txt').read_text().splitlines() if x.startswith('feature_defines=')]
    assert len(features)==1
    defs=[*P.definitions(artifacts),*P.scoped_probe_definitions(tuple(features[0].split(','))) ]
    f=['-Oz','-Wall','-ffile-compilation-dir=.','-fdebug-compilation-dir=.','-fcoverage-compilation-dir=.','-mllvm','-rng-seed=0',*[f'-D{x}' for x in defs]]
    for suffix in ['compiler-input-consumption.json','stdlib-input-consumption.json']:
        f+=json.loads((W/('lisp65-c2-substitution-linked.prg.'+suffix)).read_text())['actual_force_include_flags']
    for name in ['stage-config.h','runtime-overlay.prepare.h','resident-island.h','error-text-table.h','c2-kernal-window.generated.h']:
        f+=['-include',str((W/name).relative_to(ROOT))]
    for p in [ROOT/'src',ROOT/'scripts',ROOT/'build/c2.2/substitution',W,ROOT/'build/bytecode',HEADER.parent]:
        f+=['-I',str(p.relative_to(ROOT))]
    return f,identity,bind(manifest)

def projection(obj):
    e=ElfTruth.read(obj,llvm_readobj=READOBJ)
    secs={x.name:x.bytes for x in e.sections if x.name and not x.name.startswith('.rela')}
    syms={x.name:{'bytes':x.bytes,'section':x.section} for x in e.symbols if x.name and x.symbol_type=='Function' and x.section!='Undefined'}
    groups={
        'text':sum(v for k,v in secs.items() if k=='.text' or k.startswith('.text.')),
        'f011_cold':sum(v for k,v in secs.items() if k.startswith('.lisp65_c2_mapped_f011_cold')),
        'island':sum(v for k,v in secs.items() if k.startswith('.lisp65_resident_island')),
        'e000':sum(v for k,v in secs.items() if k.startswith('.lisp65_c2_kernal')),
        'noinit_record':secs.get('.noinit.lisp65_f011_status',0),
    }
    return {'sections':secs,'functions':syms,'groups':groups}

def lane(name,replacements,f):
    d=OUT/name
    d.mkdir(parents=True,exist_ok=True)
    objects=sorted((W/'.canonical-objects-lisp65-c2-substitution-linked').glob('[0-9][0-9][0-9]-*.c.o'))
    assert len(objects)==46
    inputs=[]
    for obj in objects:
        filename=obj.name[4:-2]
        if filename in replacements:
            s=d/filename; b=d/obj.name
            write(s,replacements[filename])
            if not b.exists(): run([CLANG,*f,'-c',s.relative_to(ROOT),'-o',b.relative_to(ROOT)])
            inputs.append(b)
        else: inputs.append(obj)
    bc=d/'combined-c.bc'; asm=d/'combined-c.s'; ob=d/'combined-c.o'
    if not bc.exists(): run(['/usr/bin/llvm-link',*inputs,'-o',bc])
    if not asm.exists(): run([CLANG,'-target','mos','-Oz','-x','ir','-S',bc,'-o',asm])
    if not ob.exists(): run([CLANG,'-c',asm,'-o',ob])
    return {'object':bind(ob),'projection':projection(ob),'replaced_sources':sorted(replacements)}

def build():
    assert bind(ELF)['sha256']=='f02d6997e33ae6c1059be1a9f81711d219f430c26e3144772124fd9a979366cf'
    authority=run(['git','show',AUTH+':docs/planning/v2.0.0-pre-plan.md'])
    assert b'Witness the first read whether or not it fails' in authority
    OUT.mkdir(parents=True,exist_ok=True)
    frozen={str(p):bind(p) for p in [ELF,W/'lisp65-c2-substitution-linked.prg',W/'lisp65-c2-substitution-linked.prg.lto.o']}
    f,toolchain,manifest=flags()
    write(OUT/'compile-flags.json',json.dumps(f,indent=2)+'\n')
    io=run(['git','show',AUTH+':src/io.c']).decode()
    main=run(['git','show',AUTH+':src/main.c']).decode()
    successor=io_successor(io)
    write(OUT/'prototype-io.c',successor)
    write(OUT/'prototype-main.c',main_successor(main))
    lanes={}
    for name,replacements in [
        ('baseline',{}),
        ('frontend-control',{'io.c':io,'main.c':main}),
        ('combined-successor',{'io.c':successor,'main.c':main_successor(main),'vm.c':(ROOT/'src/vm.c').read_text()})]:
        print('bounded codegen:',name,flush=True)
        lanes[name]=lane(name,replacements,f)
    assert lanes['baseline']['projection']==lanes['frontend-control']['projection'],'frontend reconstruction did not reproduce predecessor codegen'
    a=lanes['baseline']['projection']; b=lanes['combined-successor']['projection']
    differences={k:b['groups'][k]-a['groups'][k] for k in a['groups']}
    changed={k:{'before':a['functions'].get(k),'after':b['functions'].get(k)} for k in sorted(set(a['functions'])|set(b['functions'])) if a['functions'].get(k)!=b['functions'].get(k)}
    e=ElfTruth.read(ELF,llvm_readobj=READOBJ)
    calibration={}
    for name in ['f011_read_at_far','f011_wait_not_busy','io_disk_read_sector_link_far','vm_callprim','main']:
        s=e.symbol(name); baseline=a['functions'][name]['bytes']
        calibration[name]={'final_bytes':s.bytes,'bounded_baseline_bytes':baseline,'observed_bias':baseline-s.bytes}
    bs=e.section('.bss'); raw=e.section('.lisp65_c2_input_raw_owner')
    placement={'formula':'ADDR(.bss)+SIZEOF(.bss)','predecessor_start':bs.address+bs.bytes,'record_bytes':3,
               'remaining_before_raw_input':raw.address-(bs.address+bs.bytes+3),'floor':5}
    assert placement['remaining_before_raw_input']>=5
    for p,x in frozen.items(): assert bind(Path(p))==x,'frozen product changed'
    result={'format':'f011-status-instrument-bounded-pricing-v1','recorded_on':stable_recorded_on(OUT/'receipt.json'),
        'authority':AUTH,'authority_plan_sha256':hashlib.sha256(authority).hexdigest(),
        'toolchain':toolchain,'product_manifest':manifest,'predecessor':bind(ELF),
        'lanes':lanes,'group_deltas':differences,'changed_functions':changed,'calibration':calibration,
        'state_placement_projection':placement,'prototype_header':bind(HEADER),
        'product_wplto':0,'product_links':0,'media':0,'device_contacts':0,
        'final_link_price':False,'boot_cycle_measurement':None,
        'limits':['Combined-C relocatable codegen is not final link; per-function measured bias is reported, not universally subtracted.',
                  'State interval is projected from predecessor; final NOLOAD owner, abort survival and all floors remain to prove.',
                  'No boot-cycle neutrality or device status claim is made by pricing.']}
    write(OUT/'receipt.json',json.dumps(result,indent=2)+'\n')
    print(json.dumps({'group_deltas':differences,'calibration':calibration,'placement':placement},indent=2))

if __name__=='__main__':
    build()
