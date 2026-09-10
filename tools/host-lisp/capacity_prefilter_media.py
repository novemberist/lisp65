#!/usr/bin/env python3
"""84d6c1c2: derive diagnostic media from the unchanged renderer medium.

Only INIT text or the sealed library/index may be added. No product build,
materialization, replacement of product files, or Comfort entry is allowed.
"""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import subprocess

import renderer_native_session_media as M
import c2_v210_comfort_media_card as LIB
import c2_v210_comfort_display_repair as SEALED
from capacity_pc_histogram_tool import ROOT, OUT, bind
from evidence_era import stable_recorded_on

BUILD=OUT/'diagnostic-media'
ROW_CONTRACT=ROOT/'config/dwx-mirrored-prefilter-rows-contract.json'
INIT_CONTRACT=ROOT/'config/dwx-freezer-free-boot-variants-contract.json'

def write(p, v): p.write_text(json.dumps(v,indent=2)+'\n')

def c1541(image,*args):
    tool=shutil.which('c1541'); assert tool
    result=subprocess.run([tool,str(image),*args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    assert result.returncode==0,result.stdout.decode('utf-8',errors='backslashreplace')

def rows():
    value=json.loads(ROW_CONTRACT.read_text())
    result=[r for r in value['rows'] if r['state']=='ACTIVE']
    assert len({r['id'] for r in result})==len(result)==8
    assert all(r['device_counterpart'] and r['oracle']['type'] in ('framebuffer','stopped-memory') for r in result)
    row=next(r for r in result if r['id']=='library-require-over-packed-medium')
    assert row['input']=="(require 'repl-comfort)\n"
    return result

@contextmanager
def library_world(source, product_id):
    values=dict(PRODUCT_MANIFEST=M.OUT/'packed/readback-product/substitution-artifacts.json',
        PRODUCT_ELF=Path(M.pair()['elf']['path']), PRODUCT_D81=source,
        PRODUCT_BUILD_ID=product_id, BUILD=BUILD,
        MANIFEST=SEALED.MANIFEST, ARTIFACT=BUILD/'repl-comfort.l65s',
        INDEX=BUILD/'l65index', MEDIUM=BUILD/'library.d81', _c1541=c1541)
    previous={k:getattr(LIB,k) for k in values}
    try:
        for k,v in values.items(): setattr(LIB,k,v)
        yield
    finally:
        for k,v in previous.items(): setattr(LIB,k,v)

def check_members(source, candidate, additions):
    before=M.D81.visible_files(source.read_bytes()); after=M.D81.visible_files(candidate.read_bytes())
    assert set(after)==set(before)|set(additions)
    assert all(after[name]==raw for name,raw in before.items())
    assert all(after[name]==raw for name,raw in additions.items())
    return len(before)

def build(resume=False):
    M.check(); frozen=M.pair()
    source=Path(json.loads((M.OUT/'packed-receipt.json').read_text())['medium']['path'])
    original=bind(source)
    BUILD.mkdir(parents=True,exist_ok=resume)
    product_id,c2d=LIB.PAIR.product_world(source)
    media={}; init=json.loads(INIT_CONTRACT.read_text())
    absent=BUILD/'absent.d81'
    if not absent.exists(): shutil.copyfile(source,absent)
    assert absent.read_bytes()==source.read_bytes()
    media['absent']=dict(medium=bind(absent),added_files=[],product_files=check_members(source,absent,{}))
    for mode in ('valid','error'):
        record=init['init_payloads'][mode]; payload=ROOT/record['path']
        assert bind(payload)['sha256']==record['sha256']
        target=BUILD/('init-'+mode+'.d81')
        if not target.exists(): shutil.copyfile(source,target)
        if b'INIT.L65' not in M.D81.visible_files(target.read_bytes()):
            c1541(target,'-write',str(payload),'init.l65')
        media['init-'+mode]=dict(medium=bind(target),payload=bind(payload),
            product_files=check_members(source,target,{b'INIT.L65':payload.read_bytes()}),added_files=['INIT.L65'])
    with library_world(source,product_id):
        assert not LIB.MEDIUM.exists(),'inspect interrupted library pack before resuming'
        packed=LIB.build_medium()
        actual=M.D81.visible_files(LIB.MEDIUM.read_bytes())[b'REPL-COMFORT']
        assert actual==(SEALED.BUILD/'repl-comfort.l65s').read_bytes()
        closure=LIB.CLOSURE.derive(LIB.PRODUCT_MANIFEST,[LIB.MANIFEST])
        LIB.CLOSURE.require_closed(closure)
        candidate=LIB.F.emit_image('candidate','repl',LIB.MANIFEST)
        raw=LIB.F.emit_image('sealed','repl',SEALED.RAW)
        _,support,_=LIB._selected_support()
        ide=LIB.F.emit_image('ide','ide',LIB.product_ide_manifest())
        start,size=support['blob_offset'],support['length']
        assert candidate.code[:size]==ide.code[start:start+size] and candidate.code[size:]==raw.code
        media['library']=dict(medium=bind(LIB.MEDIUM),packed=packed,
            closure=closure,coherence='packed artifact byte-identical to sealed generation; support equals renderer object',
            library_manifest=bind(SEALED.MANIFEST),sealed_library=bind(SEALED.BUILD/'repl-comfort.l65s'),
            added_files=['L65INDEX','REPL-COMFORT'],comfort_entry=False,comfort_claim=False)
    projected=[]
    for row in rows():
        if row.get('medium')=='product-plus-packed-library': role='library'
        elif row['execution']=='bound-item3-valid-cold-boot': role='init-valid'
        elif row['execution']=='bound-item3-error-cold-boot': role='init-error'
        else: role='absent'
        projected.append(dict(id=row['id'],role=role,medium=media[role]['medium'],
            world=frozen,product_build_id=f'0x{product_id:08x}',stimulus_and_oracle=row,
            historical_results_inherited=False))
    assert M.pair()==frozen and bind(source)==original
    receipt=BUILD/'receipt.json'
    write(receipt,dict(status='DIAGNOSTIC MEDIA PACKED; EXECUTION PENDING',recorded_on=stable_recorded_on(receipt),
        authorization='84d6c1c2',source_product=original,world=frozen,
        row_authority=bind(ROW_CONTRACT),init_authority=bind(INIT_CONTRACT),
        media=media,rows=projected,product_compiles=0,product_links=0,device_contacts=0,
        product_medium_unchanged=True,comfort_entry=False,comfort_claim=False))
    print('DIAGNOSTIC MEDIA PASS rows=8 variants=4 product bytes unchanged')

def check():
    value=json.loads((BUILD/'receipt.json').read_text())
    assert value['world']==M.pair() and value['row_authority']==bind(ROW_CONTRACT)
    assert value['init_authority']==bind(INIT_CONTRACT)
    assert bind(ROOT/value['source_product']['path'])==value['source_product']
    assert [r['stimulus_and_oracle'] for r in value['rows']]==rows()
    for row in value['rows']:
        assert row['world']==M.pair() and row['medium']==value['media'][row['role']]['medium']
        assert bind(ROOT/row['medium']['path'])==row['medium']
    return value

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['build','check']);p.add_argument('--resume',action='store_true');a=p.parse_args()
    if a.action=='build': build(a.resume)
    else: check()
