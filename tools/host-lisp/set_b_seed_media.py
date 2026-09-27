#!/usr/bin/env python3
"""Set B artifact-only pack adapter derived from Card L.

Dry run uses the accepted Card L executable with deterministic non-executable
stand-ins for seven tenants. It is transport evidence only, never a Seed.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
sys.dont_write_bytecode=True
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import runtime_overlay_bank as B
import set_b_producer as P
import card_l_seed_media as C
ROOT=P.ROOT
OUT=ROOT/'build/set-b-r1/step3/pack-dryrun'
BASE=ROOT/'build/card-l-seed-medium-r2'
SIZES=(1792,1792,1792,1792,1024)
def write(p,v):P.write(p,v)
def digest(raw):return hashlib.sha256(raw).hexdigest()

def dry_world(out):
    world=out/'world';shutil.copytree(BASE/'materialized',world,dirs_exist_ok=True)
    import d81_persistence_fault as D
    files=D.visible_files((BASE/'comfort/card-l-comfort.d81').read_bytes())
    for family in ['boot','session']:
        m=P.load(BASE/'media-seed'/f'{family}-manifest.json')
        m.pop('card_l_tuple',None)
        (world/m['storage']['file']).write_bytes(files[(family+'.bin').upper().encode()])
        write(world/f'runtime-overlays-{family}-final.json',m)
    return world

def dry_tenants():
    extent,tenants=P.late_partition()
    image=bytearray(8192);image[extent:]=bytes([0xa5])*(8192-extent);rows=[]
    for i,t in enumerate(tenants):
        # No relocation bytes are presented as executable code.
        payload=bytes((t['slot']+i)%256 for i in range(t['projected_bytes']))
        limit=tenants[i+1]['offset'] if i+1<len(tenants) else extent
        payload=payload.ljust(limit-t['offset'],b'\0')
        image[t['offset']:limit]=payload
        rows.append(dict(t,payload=payload,vma=0xc356,entry=0xc356))
    return bytes(image),rows

def boot_pack(world,out,data):
    m=P.load(world/'runtime-overlays-boot-final.json');raw=(world/m['storage']['file']).read_bytes()
    if digest(raw)!=m['storage']['sha256'] or len(m['slices']) not in (12,17):raise ValueError('Boot predecessor identity/population drift')
    if len(data)!=8192:raise ValueError('full late image required')
    items=[]
    for r in m['slices'][:12]:
        spec=B.SliceSpec(r['id'],r['name'],r['section'],r['start_symbol'],r['end_symbol'],r['entry_symbol'] or '',r['flags'],r['abi_version'],r['capability_mask'],data_only=bool(r['flags']&B.FLAG_DATA_ONLY),destination=r['vma'])
        items.append(B.ExtractedSlice(spec,r['vma'],r['end'],B.DATA_ENTRY_SENTINEL if spec.data_only else r['entry'],raw[r['file_offset']:r['file_offset']+r['file_size']]))
    cursor=0
    for i,size in enumerate(SIZES):
        spec=B.SliceSpec(12+i,f'set-b-image-{i}',f'.lisp65_set_b_image_{i}',f'set_b_image_{i}_start',f'set_b_image_{i}_end','',B.FLAG_BOOT|B.FLAG_DATA_ONLY,0,0,data_only=True,destination=0x1800)
        items.append(B.ExtractedSlice(spec,0x1800,0x1800+size,B.DATA_ENTRY_SENTINEL,data[cursor:cursor+size]));cursor+=size
    kw=dict(profile_build_id=m['profile_build_id'],expected_vma=m['policy']['common_vma'],max_slice_bytes=1792,format_version=4,main_source_base=B.BOOT_FAMILY_SOURCE_BASE,payload_alignment=256)
    image,overflow,parsed=B.build_region_images(items,**kw);assert not overflow
    out.mkdir(parents=True,exist_ok=True);path=out/'boot.bin';path.write_bytes(image)
    header=B.render_header(profile_build_id=m['profile_build_id'],format_version=4)
    value=B._manifest(profile=m['profile'],abi_contract=Path(m['abi']['contract']),abi_sha256=m['abi']['sha256'],elf=world/m['elf']['file'],image_path=path,overflow_image_path=out/'boot-region1.bin',header_path=out/'boot.h',image=image,overflow_image=overflow,header=header,parsed=parsed,slices=items,expected_vma=kw['expected_vma'],max_slice_bytes=1792,format_version=4,payload_alignment=256)
    B.validate_manifest(value,payload_alignment=256)
    placed=value['slices'][12:];assert placed[0]['source_address']==P.load(P.INPUTS)['attic']['address']
    assert b''.join(image[r['file_offset']:r['file_offset']+r['file_size']] for r in placed)==data
    (out/'boot.h').write_bytes(header);write(out/'boot-manifest.json',value)
    return image,value

def controls(image,manifest):
    first=manifest['slices'][12]['file_offset'];result={}
    for name in ['missing_record','corrupted_byte','displaced_256']:
        m=copy.deepcopy(manifest);raw=bytearray(image)
        if name=='missing_record':
            r=m['slices'].pop();raw[7]=16;raw[32+16*32:32+17*32]=bytes(32);raw[r['file_offset']:r['file_offset']+r['file_size']]=bytes(r['file_size'])
        elif name=='corrupted_byte':raw[first+100]^=1
        else:
            raw=raw[:first]+bytearray(256)+raw[first:]
            struct.pack_into('<I',raw,20,len(raw))
            for r in m['slices'][12:]:
                r['file_offset']+=256;r['source_address']+=256;at=32+r['id']*32
                struct.pack_into('<H',raw,at+4,r['source_address']&65535)
                raw[at+25]=(r['source_address']>>16)&15;raw[at+26]=(r['source_address']>>20)&255
        for r in m['slices']:
            data=raw[r['file_offset']:r['file_offset']+r['file_size']];r.update(crc16=B.crc16_ccitt_false(data),sha256=digest(data));struct.pack_into('<H',raw,32+r['id']*32+20,r['crc16'])
        raw=P.rebind_family(raw,m['slices'],b'');h=B.HEADER.unpack_from(raw);m['catalog'].update(slice_count=len(m['slices']),directory_crc16=h[12],header_crc16=h[13]);m['storage'].update(size=len(raw),sha256=digest(raw),crc16=B.crc16_ccitt_false(raw))
        result[name]=(raw,m)
    return result

def pack_disk(*args,**kwargs):
    C.OUT=OUT
    medium=C.pack_disk(*args,**kwargs)
    target=medium.with_name('set-b.d81');medium.rename(target)
    return target

def validate_session(raw,overflow,manifest,image):
    """Project only private region2 out; preserve all seven late records."""
    raw=bytearray(raw);rows=manifest['slices'];assert len(rows)==63 and rows[52]['region_id']==2
    for i in range(53,63):
        rec=bytearray(raw[32+i*32:32+(i+1)*32]);struct.pack_into('<H',rec,0,i-1);struct.pack_into('<H',rec,22,0);struct.pack_into('<H',rec,22,B.crc16_ccitt_false(rec));raw[32+(i-1)*32:32+i*32]=rec
    raw[32+62*32:32+63*32]=bytes(32);raw[7]=62;B._refresh_catalog_crcs(raw)
    return B.validate_region_images(raw,overflow,late_image=image,expected_build_id=manifest['profile_build_id'],expected_vma=0xc356,max_slice_bytes=1792,format_version=4,main_source_base=next(r['source_address']-r['file_offset'] for r in rows if r['region_id']==0),payload_alignment=32)

def run(world=None,base_medium=None,population=None,dry_run=True):
    global OUT
    if not dry_run:
        P.require_auth()
        if not all((world,base_medium,population)):
            raise ValueError('Seed media needs explicit admitted world, medium and population')
        OUT=P.HERE/'media-seed'
        if OUT.exists():raise ValueError('Seed media exists; no implicit overwrite')
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'tmp').mkdir(exist_ok=True)
    if dry_run:
        world=dry_world(OUT);image,tenants=dry_tenants()
        from elf_truth import ElfTruth
        m=P.load(world/'runtime-overlays-session-final.json');truth=ElfTruth.read(world/m['elf']['file'],llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
        sec=truth.section('.lisp65_rt_card_l_stage');stage=truth.section_bytes(sec.name);binding=truth.symbol('rtov_late_stage_binding');entry=truth.symbol('card_l_stage_entry')
        session,sm=P.bind_session_payload(world,OUT/'positive',image,tenants,stage,binding.value-sec.address,entry.value,dry_run=True)
        base_medium=BASE/'comfort/card-l-comfort.d81';population=BASE/'population/delivery-population.json'
    else:
        session,sm=P.bind_session(world,OUT/'positive');image=(OUT/'positive/set-b-tenants.bin').read_bytes()
    boot,bm=boot_pack(world,OUT/'positive',image)
    overflow=(world/sm['overflow_storage']['file']).read_bytes()
    parsed=validate_session(session,overflow,sm,image);assert len(parsed.slices)==62
    medium=pack_disk(base_medium,population,boot,OUT/'positive',world,bm,session,sm)
    control_results={}
    for name,(raw,m) in controls(boot,bm).items():
        target=OUT/'controls'/name;pack_disk(base_medium,population,raw,target,world,m,session,sm)
        assert B.crc16_ccitt_false(raw[bm['slices'][12]['file_offset']:bm['slices'][12]['file_offset']+8192])!=B.crc16_ccitt_false(image)
        write(target/'boot-manifest.json',m);control_results[name]='packed; full-image CRC differs; every touched record/header rebound'
    # The journal is reset by slot62: disk bytes cannot inject post-READY corruption.
    # A separate reviewer injection prescription is the faithful negative control.
    write(OUT/'controls/journal-corrupted.json',dict(name='journal corrupted',inject_after='READY=1, before next retirement dispatch',address=0x5de20,bytes_hex='a6',expected='READY=0; no user dispatch; no directory writes',executed=False,reason='journal magic is invalid; media alone cannot preserve it across slot62 reset'))
    write(OUT/'status.json',dict(dry_run=dry_run,status='PASS: HOST PACK/READBACK ONLY',boot_count=17,session_count=63,tenant_count=7,medium=str(medium.relative_to(ROOT)),image_sha256=digest(image),controls=control_results,journal_control='reviewer injection prescription; not executed',product_links=0,seed=False,executable_set_b=not dry_run))
    return medium

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['dry-run','seed']);p.add_argument('--world',type=Path);p.add_argument('--base-medium',type=Path);p.add_argument('--population',type=Path);a=p.parse_args()
    print(run(a.world,a.base_medium,a.population,a.mode=='dry-run'))
if __name__=='__main__':main()
