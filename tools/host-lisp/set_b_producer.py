#!/usr/bin/env python3
"""Set B source authority and extraction; no implicit product build.

Derived from card_l_producer: exact-context maintained-to-consumed projections,
reviewer commit admission, immutable ELF extraction and tuple CRC rebinding.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT/'build/set-b-r1'
AUTH = "7a4e43fa"
DIFF_BASE = "e40eb1854bd118f1d8e63778ca847ab9a482cf3a"
BASE = ROOT/'build/card-l-final-r1'
GEN = BASE/'wplto/generated-product-sources'
FINAL = BASE/'wplto/resident-island-seed.prg.elf'
FINAL_SHA = '7e57bc17f318dd22a6dbc0212fd5fde5b9598eaf645f4f98d6387e0c3f53f3b5'
INPUTS = ROOT/'config/set-b-native/set-b-inputs.json'
RECIPE = ROOT/'config/set-b-plane/native-recipe.json'
CLOSURE = ROOT/'config/set-b-native/include-closure.json'
# docs/planning/post-2.4.0-plan.md, "Set B step 3/3b", 2026-09-26:
# reviewer raised the resident bound for the replay-then-disarm safety logic.
RESIDENT_ADMISSION_LIMIT = 246
PROJECTION_RECEIPT = HERE/'step3/objects/summary-resident-246.json'
UNITS = ('c2_product_runtime.c', 'mem.c', 'vm.c', 'repl.c')
SOURCES = tuple('src/'+x for x in UNITS)

def load(p): return json.loads(p.read_text())
def bind(p):
    raw=p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
def write(p,d):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(d,indent=2)+'\n')
def authority_files():
    return sorted([str(p.relative_to(ROOT)) for folder in ('config/set-b-native','config/set-b-plane')
                   for p in (ROOT/folder).rglob('*') if p.is_file()]+list(SOURCES)+
        ['src/c2_product_runtime.h','src/mem.h','src/vm.h','src/optional/card_l_stage.c']+
        [str(p.relative_to(ROOT)) for p in (ROOT/'src/optional').glob('set_b_retire_*')]+
        ['tools/host-lisp/set_b_producer.py','tools/host-lisp/set_b_seed_media.py',
         'tools/host-lisp/runtime_overlay_bank.py'])
def require_auth():
    if AUTH == 'AUTH_PENDING':
        raise ValueError('Seed refused: reviewer authority commit required')
    commit=subprocess.check_output(['git','rev-parse',AUTH+'^{commit}'],cwd=ROOT,text=True).strip()
    for path in authority_files():
        old=subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)
        new=(ROOT/path).read_bytes()
        if path=='tools/host-lisp/set_b_producer.py':
            normal=lambda b:re.sub(rb'^AUTH = [^\n]+',b'AUTH = AUTH_POINTER',b,flags=re.M)
            old,new=normal(old),normal(new)
        if old != new: raise ValueError('uncommitted authority: '+path)
    return commit

def project_unit(unit):
    """Every maintained hunk must match exactly once in the Card L consumed TU."""
    text=(GEN/unit).read_text()
    diff=subprocess.check_output(['git','diff',DIFF_BASE,'--','src/'+unit],cwd=ROOT,text=True)
    parts=re.split(r'(^@@[^\n]*\n)',diff,flags=re.M)
    if len(parts)<3: raise ValueError('source hunk absent: '+unit)
    for i in range(2,len(parts),2):
        lines=parts[i].splitlines(True)
        before=''.join(x[1:] for x in lines if x[:1] in (' ','-'))
        after=''.join(x[1:] for x in lines if x[:1] in (' ','+'))
        if text.count(before)!=1: raise ValueError('projection context drift: '+unit)
        text=text.replace(before,after,1)
    return text

def configure(P):
    import card_l_producer as predecessor
    predecessor.configure(P)
    specs=load(RECIPE)['set_b']['tenant_specs']
    old=load(ROOT/'config/card-l-plane/native-recipe.json')['values']['SESSION_SLICE_SPECS']
    if P.SESSION_SLICE_SPECS not in (old,old+specs): raise ValueError('Card L population drift')
    P.SESSION_SLICE_SPECS=old+specs
    P.UNIQUE_SLICE_COUNT=71
    P.assert_unique_public_specs()
    P.linker_script=lambda **_kw:(ROOT/'config/set-b-native/linker/c2-substitution.ld').read_text()

def register_and_admit(P):
    old=load(ROOT/'config/card-l-plane/native-recipe.json')['values']['SESSION_SLICE_SPECS']
    specs=load(RECIPE)['set_b']['tenant_specs']
    if list(P.SESSION_SLICE_SPECS) not in (old,old+specs):
        raise ValueError('registration requires the Card L Session population')
    P.SESSION_SLICE_SPECS=old+specs
    P.UNIQUE_SLICE_COUNT=71
    P.assert_unique_public_specs()
REGISTER_SLICES = register_and_admit

def prepare_seed_commands(out):
    proof=load(BASE/'final-command-consumption.json')
    old=str((BASE/'wplto').relative_to(ROOT));new=str((out/'wplto').relative_to(ROOT))
    overrides=load(CLOSURE).get('command_header_overrides',{})
    commands=[[overrides.get(arg,arg.replace(old,new)) for arg in cmd] for cmd in proof['commands']]
    for cmd in commands:
        if '-c' in cmd:
            cmd+=['-DLISP65_SET_B']
    return commands

def prepare_world(out):
    """Copy sources and linker authority only; this function executes no command."""
    work=out/'wplto'
    shutil.copytree(BASE/'wplto',work,ignore=shutil.ignore_patterns('*.o','*.elf','*.prg','*.map','*.json','*.txt'),dirs_exist_ok=True)
    for unit in UNITS:(work/'generated-product-sources'/unit).write_text(project_unit(unit))
    for row in load(CLOSURE)['materialized']:
        shutil.copyfile(ROOT/row['source']['path'],work/row['materialized_path'])
    for p in (ROOT/'config/set-b-native/linker').rglob('*'):
        if p.is_file():shutil.copyfile(p,work/p.relative_to(ROOT/'config/set-b-native/linker'))
    commands=prepare_seed_commands(out);write(out/'commands.json',commands)
    return commands

def command_probe():
    if bind(FINAL)['sha256']!=FINAL_SHA: raise ValueError('Card L Final drift')
    m=load(INPUTS)
    if m['diff_base']!=DIFF_BASE or m['source']!=bind(ROOT/'src/optional/card_l_stage.c'):
        raise ValueError('source binding drift')
    for row in load(CLOSURE)['materialized']+load(CLOSURE).get('vendored_forced_headers',[]):
        if row['source']!=bind(ROOT/row['source']['path']):raise ValueError('include binding drift')
    out=HERE/'step3/command-preview'
    commands=prepare_world(out)
    revision=load(ROOT/'config/set-b-native/placement-revision.json')
    for unit in UNITS:
        if unit in revision['projection_sources']:
            row=revision['projection_sources'][unit]
            measured=ROOT/row['path']
            if bind(measured)!=row:raise ValueError('placement projection identity drift: '+unit)
        else:
            measured=HERE/'step3/objects'/(unit+'.new-sources')/unit
        if measured.read_text()!=project_unit(unit):raise ValueError('projection not measured: '+unit)
    c=load(PROJECTION_RECEIPT)
    if (c['halt'] or c['total']>RESIDENT_ADMISSION_LIMIT
            or any(v['bytes']>1792 for v in c['slices'])):raise ValueError('projection exceeds authority')
    write(out/'receipt.json',dict(authority=AUTH,diff_base=DIFF_BASE,commands=commands,
        sources=[bind(ROOT/p) for p in authority_files()],product_link=False,seed=False,
        status='SOURCE COMMAND PREVIEW ONLY',projection=c))
    return out

def late_partition():
    """One bound geometry for linked extraction and non-executable pack fixtures."""
    inputs=load(INPUTS);extent=inputs['aligned_extent'];tenants=inputs['tenants']
    if inputs['image']['size']!=8192 or not 0<extent<=8192 or extent%32:
        raise ValueError('late extent geometry drift')
    if [t['slot'] for t in tenants]!=list(range(56,63)) or tenants[0]['offset']!=0:
        raise ValueError('late tenant population drift')
    for i,t in enumerate(tenants):
        limit=tenants[i+1]['offset'] if i+1<len(tenants) else extent
        if (t['offset']%32 or not 0<=t['offset']<limit<=extent
                or t['source_address']!=0x5de80+t['offset'] or t['region']!=3
                or not 0<t['projected_bytes']<=limit-t['offset']<=1792):
            raise ValueError('late tenant geometry drift: '+t['name'])
    return extent,tenants

def extract_tenants(elf):
    from elf_truth import ElfTruth
    truth=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
    extent,tenants=late_partition()
    image=bytearray(8192);image[extent:]=bytes([0xa5])*(8192-extent);rows=[]
    for i,t in enumerate(tenants):
        section=truth.section(t['section']);entry=truth.symbol(t['entry_target'])
        if (truth.symbol(t['start_symbol']).value != section.address
                or truth.symbol(t['end_symbol']).value != section.address + section.bytes
                or truth.symbol(t['entry_symbol']).value != entry.value):
            raise ValueError('tenant extraction-symbol binding drift: '+t['name'])
        data=truth.section_bytes(t['section']);limit=tenants[i+1]['offset'] if i+1<len(tenants) else extent
        if section.address!=0xc356 or entry.section!=section.name or not 0<len(data)<=1792 or t['offset']+len(data)>limit:
            raise ValueError('linked tenant differs from admitted partition: '+t['name'])
        if not section.address<=entry.value<section.address+len(data):raise ValueError('tenant entry outside payload')
        code_bytes=len(data)
        # Charge and authenticate the entire reserved interval. This retains
        # canonical 32-byte packing even when linked code is smaller than its
        # object projection, without relaxing any catalog or CRC rule.
        data=data.ljust(limit-t['offset'],b'\0')
        image[t['offset']:limit]=data
        rows.append(dict(t,payload=data,code_bytes=code_bytes,vma=section.address,entry=entry.value))
    return bytes(image),rows

def rebind_family(raw, rows, overflow):
    """Refresh every touched record, overflow tuple, directory and header."""
    import runtime_overlay_bank as B
    raw=bytearray(raw)
    for r in rows:
        at=B.HEADER_SIZE+r['id']*B.ENTRY_SIZE
        rec=bytearray(raw[at:at+B.ENTRY_SIZE]);struct.pack_into('<H',rec,22,0)
        crc=B.crc16_ccitt_false(rec)
        if not crc:raise ValueError('zero record CRC')
        struct.pack_into('<H',rec,22,crc);raw[at:at+B.ENTRY_SIZE]=rec;r['record_crc16']=crc
    struct.pack_into('<HH',raw,28,len(overflow),B.crc16_ccitt_false(overflow) if overflow else 0)
    B._refresh_catalog_crcs(raw)
    return bytes(raw)

def bind_session_payload(world,out,image,tenants,stage,tuple_offset,stage_entry,*,dry_run=False):
    """Retain Card L main/overflow/private extents; fill unused catalog tail."""
    import runtime_overlay_bank as B
    m=copy.deepcopy(load(world/'runtime-overlays-session-final.json'))
    raw=bytearray((world/m['storage']['file']).read_bytes())
    overflow=(world/m['overflow_storage']['file']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=m['storage']['sha256'] or len(m['slices'])!=56:
        raise ValueError('expected exact 56-record Card L Session')
    if len(image)!=8192 or len(tenants)!=7:raise ValueError('full seven-tenant image required')
    if tuple_offset<0 or tuple_offset+4>len(stage):raise ValueError('stage tuple outside payload')
    if stage[tuple_offset:tuple_offset+4] != bytes(4):
        raise ValueError('expected the immutable ELF four-byte tuple placeholder')
    stage=bytearray(stage);struct.pack_into('<HH',stage,tuple_offset,8192,B.crc16_ccitt_false(image))
    r=m['slices'][55];extent=r['file_size']
    if len(stage)>extent:raise ValueError('stage exceeds inherited allocation')
    # Keep the predecessor allocation, including authenticated zero padding.
    stage.extend(bytes(extent-len(stage)));off=r['file_offset'];raw[off:off+extent]=stage
    r.update(entry=stage_entry,entry_offset=stage_entry-r['vma'],crc16=B.crc16_ccitt_false(stage),sha256=hashlib.sha256(stage).hexdigest())
    struct.pack_into('<H',raw,B.HEADER_SIZE+55*32+12,r['entry_offset']);struct.pack_into('<H',raw,B.HEADER_SIZE+55*32+20,r['crc16'])
    for t in tenants:
        payload=t['payload'];source=t['source_address'];entry=t['entry'];vma=t['vma'];slot=t['slot']
        if payload!=image[t['offset']:t['offset']+len(payload)] or not 0<len(payload)<=1792:raise ValueError('tenant image/record mismatch')
        rec=B.ENTRY.pack(slot,6,source&65535,len(payload),vma,len(payload),entry-vma,1,m['profile_build_id'],B.crc16_ccitt_false(payload),0,3|(5<<8),0)
        raw[B.HEADER_SIZE+slot*32:B.HEADER_SIZE+(slot+1)*32]=rec
        row=dict(id=slot,name=t['name'],section=t['section'],start_symbol=t['start_symbol'],end_symbol=t['end_symbol'],entry_symbol=t['entry_symbol'],flags=6,roles=B._roles(6),file_offset=t['offset'],file_size=len(payload),memory_size=len(payload),vma=vma,end=vma+len(payload),entry=entry,entry_offset=entry-vma,abi_version=1,slice_build_id=m['profile_build_id'],capability_mask=0,region_id=3,source_address=source,crc16=B.crc16_ccitt_false(payload),sha256=hashlib.sha256(payload).hexdigest())
        m['slices'].append(row)
    raw[7]=63;raw=rebind_family(raw,m['slices'],overflow)
    h=B.HEADER.unpack_from(raw);m['catalog'].update(slice_count=63,directory_crc16=h[12],header_crc16=h[13])
    m['storage'].update(file='session.bin',size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),crc16=B.crc16_ccitt_false(raw))
    m['late_storage']=dict(file='set-b-tenants.bin',address=0x5de80,size=8192,sha256=hashlib.sha256(image).hexdigest(),crc16=B.crc16_ccitt_false(image))
    out.mkdir(parents=True,exist_ok=True);(out/'session.bin').write_bytes(raw);(out/'set-b-tenants.bin').write_bytes(image)
    write(out/'session-manifest.json',m)
    write(out/'packing-provenance.json',dict(dry_run=dry_run,executable_set_b=not dry_run,stage_extent=extent,session_count=63,tuple_offset=tuple_offset))
    return raw,m

def bind_session(world,out):
    from elf_truth import ElfTruth
    m=load(world/'runtime-overlays-session-final.json');elf=world/m['elf']['file']
    image,tenants=extract_tenants(elf)
    truth=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
    sec=truth.section('.lisp65_rt_card_l_stage');binding=truth.symbol('rtov_late_stage_binding');entry=truth.symbol('card_l_stage_entry')
    if binding.section!=sec.name or binding.bytes!=4 or entry.section!=sec.name:raise ValueError('slot55 ownership')
    return bind_session_payload(world,out,image,tenants,truth.section_bytes(sec.name),binding.value-sec.address,entry.value)

def seed():
    require_auth()
    command_probe()
    out=HERE/'seed'
    if out.exists():raise ValueError('Seed exists; no implicit retry')
    out.mkdir();(HERE/'tmp').mkdir(exist_ok=True)
    commands=prepare_world(out)
    if len([c for c in commands if '-c' not in c])!=2:
        raise ValueError('expected one LLVM aggregation and one product link')
    write(out/'invocation.json',dict(authority=AUTH,diff_base=DIFF_BASE,commands_started=True))
    for i,cmd in enumerate(commands):
        Path(cmd[cmd.index('-o')+1]).parent.mkdir(parents=True,exist_ok=True)
        done=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,env={**os.environ,'TMPDIR':str(HERE/'tmp')})
        (out/f'command-{i:03d}.log').write_text(done.stdout+done.stderr)
        if done.returncode:raise ValueError(f'Seed stopped at command {i}; no implicit retry')
    elf=out/'wplto/resident-island-seed.prg.elf'
    image,tenants=extract_tenants(elf)
    (out/'set-b-tenants.bin').write_bytes(image)
    write(out/'linked.json',dict(authority=AUTH,elf=bind(elf),image=bind(out/'set-b-tenants.bin'),
        status='LINKED SEED; linked price/inventory and media gates pending'))
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['dry-run','command-probe','seed']);a=p.parse_args()
    if a.mode=='seed':seed()
    else:print(command_probe().relative_to(ROOT))
if __name__=='__main__':main()
