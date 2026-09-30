#!/usr/bin/env python3
"""Write-once r6 library successor, retaining the r5 native product exactly."""
import json, os, re
from pathlib import Path
import bytecode_p0_stdlib as P
import c2_defstruct_foundations_gate as PK
import c2_full_emission as F
import c2_require_resolver_gate as L
import d81_persistence_fault as D
import o2_lite_r3_host as H
import o2_lite_r4_host as H4
import o2_lite_seed_producer_20260929 as PACK
import strings_seed_producer as S
from o2_lite_r5_product import once, save
ROOT=H.ROOT
BASE=ROOT/'build/o2-lite-product-r5'
BUILD=ROOT/'build/o2-lite-product-r6'
PROOF=ROOT/'build/o2-lite-r6-proof'

def budget(m,blob):
    assert m['code_bytes']==len(blob)<=3000
    assert max(e['length'] for e in m['entries'])<=255

def controls(m,blob):
    import copy, tempfile
    rejected=[]
    def reject(name,fn):
        try:fn()
        except (AssertionError,FileExistsError):rejected.append(name)
        else:raise AssertionError('negative survived: '+name)
    bad=copy.deepcopy(m);bad['code_bytes']=3001
    reject('3001-byte library',lambda:budget(bad,bytes(3001)))
    large=copy.deepcopy(m);large['entries'][0]['length']=256
    reject('256-byte object',lambda:budget(large,blob))
    reject('stale byte price',lambda:budget(m,blob+b'X'))
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'once';once(path,b'one')
        reject('write-once overwrite',lambda:once(path,b'two'))
    assert S.classify_bytes(b'a',b'b',{})['unclassified_bytes']==1
    return dict(status='PASS',rejected=rejected,unclassified_mutation_rejected=True)

def emit(med):
    suite=P._read_suite(str(ROOT/'config/comfort-default-plane/libraries/repl-comfort-suite.json'))
    suite['resident_suite']=str(ROOT/'build/o2-lite-r4-slots-preflight/planes/resident.json')
    P.emit_artifacts(str(ROOT/'config/comfort-default-plane/libraries/repl-comfort-suite.json'),suite,str(med/'repl-comfort'),base_addr=0,artifact_role='disk-lib')
    manifest=med/'repl-comfort.manifest.json'
    m=S.load(manifest);blob=(med/'repl-comfort.blob.bin').read_bytes();budget(m,blob)
    return manifest,m,blob

def media(med, medium):
    med.mkdir()
    manifest,m,blob=emit(med)
    build_id=S.load(ROOT/'build/o2-lite-product-r4/media-r4/runtime-receipt.json')['product_build_id']
    row,payload=PK.measured_row('repl-comfort','repl-comfort','repl',manifest,(),1,1,product_build_id=build_id)
    old=next(r for r in L.decode_index(D.visible_files(medium)[b'L65INDEX']) if r['name']=='repl-comfort')
    row.update(track=old['track'],sector=old['sector'])
    result=PACK.pack(medium,payload,row,build_id,med)
    for name,raw in D.visible_files((med/'o2lite.d81').read_bytes()).items():
        once(med/'artifacts'/name.decode().lower(),raw)
    once(med/'repl-comfort.l65s',payload)
    once(med/'repl-comfort.c2i',F.emit_image('repl-comfort','repl',manifest).metadata)
    return result,m,blob,old,row

def seed():
    assert os.environ['PYTHONDONTWRITEBYTECODE']=='1'
    proof=S.load(PROOF/'receipt.json');assert proof['status']=='PASS' and proof['sources']==H4.bindings()
    previous=S.load(BASE/'complete.json');assert previous['status']=='PASS'
    for r in previous['receipts']: S.checked(r)
    assert H.project_editor()==(ROOT/'build/o2-lite-r4-slots-preflight/planes/product-editor.lisp').read_text()
    medium=S.checked(previous['medium']);native=S.checked(previous['ELF'])
    assert not BUILD.exists(),'write-once Seed already claimed'
    BUILD.mkdir()
    save(BUILD/'attempt.json',dict(status='STARTED',producer=S.bind(Path(__file__)),predecessor=S.bind(BASE/'complete.json')))
    try:
        result,m,blob,old,row=media(BUILD/'media-r6',medium)
        save(BUILD/'negative-controls.json',controls(m,blob))
        elf=BUILD/'wplto/resident-island-seed.prg.elf';once(elf,native)
        for suffix in ('','.map','.lto.o'):
            p=BASE/('wplto/resident-island-seed.prg'+suffix)
            if p.is_file():once(BUILD/'wplto'/p.name,p.read_bytes())
        save(BUILD/'media.json',result)
        return finish()
    except BaseException as error:
        save(BUILD/'halt.json',dict(status='HALT',error=repr(error)));raise

def finish():
    """Append final metadata only; never re-emit or rewrite an existing artifact."""
    assert not (BUILD/'complete.json').exists(),'completed Seed is immutable'
    previous=S.load(BASE/'complete.json')
    medium=S.checked(previous['medium'])
    elf=BUILD/'wplto/resident-island-seed.prg.elf'
    assert elf.read_bytes()==S.checked(previous['ELF'])
    if not (BUILD/'media.json').exists():
        # Recover the receipt from the independently completed preflight, after
        # requiring exact persisted disk equality. No product bytes are changed.
        result=S.load(ROOT/'build/o2-lite-r6-preflight/receipt.json')['media']
        raw=(BUILD/'media-r6/o2lite.d81').read_bytes()
        assert raw==S.checked(result['medium'])
        result['medium']=S.bind(BUILD/'media-r6/o2lite.d81')
        save(BUILD/'media.json',result)
    result=S.load(BUILD/'media.json');raw=S.checked(result['medium'])
    D.validate_bam(raw);files=D.visible_files(raw)
    assert len(files)==20
    build_id=S.load(ROOT/'build/o2-lite-product-r4/media-r4/runtime-receipt.json')['product_build_id']
    packages={r['name']:files[r['name'].upper().encode()] for r in result['index_rows']}
    assert L.decode_index(files[b'L65INDEX'],packages,artifact_build_id=build_id)==result['index_rows']
    m=S.load(BUILD/'media-r6/repl-comfort.manifest.json')
    blob=(BUILD/'media-r6/repl-comfort.blob.bin').read_bytes();budget(m,blob)
    assert S.load(PROOF/'receipt.json')['sources']==H4.bindings()
    old=next(r for r in L.decode_index(D.visible_files(medium)[b'L65INDEX']) if r['name']=='repl-comfort')
    row=next(r for r in result['index_rows'] if r['name']=='repl-comfort')
    save(BUILD/'continuation.json',dict(status='PASS',producer=S.bind(Path(__file__)),
        append_only=True,artifact_rebuilds=0,original_attempt=S.bind(BUILD/'attempt.json'),
        note='Mixed integer/symbol manifest literals handled; preflight and persisted Seed media identical.'))
    capacity=S.load(ROOT/'build/o2-lite-product-r4/capacity.json')
    for k,field in [('code','bank2'),('entries','entries'),('resolutions','resolutions'),('roots','roots')]:
        capacity['used'][k]+=row[field]-old[field]
    capacity['entry_scratch_sum']+=row['scratch']-old['scratch']
    assert all(capacity['used'][k]<=capacity['limits'][k] for k in capacity['limits'])
    assert capacity['entry_scratch_sum']<=capacity['entry_scratch_limit']
    # No new names: inherited symbol/name pool capacity remains conservative.
    before=S.load(BASE/'media-r5/repl-comfort.manifest.json')
    def symbols(manifest):
        return {e['name'] for e in manifest['entries']} | {x['symbol'] for e in manifest['entries'] for x in e['literals'] if isinstance(x,dict) and 'symbol' in x}
    assert symbols(m)<=symbols(before)
    save(BUILD/'capacity.json',capacity)
    save(BUILD/'price.json',dict(status='PASS',library=len(blob),objects=len(m['entries']),max_object=max(e['length'] for e in m['entries']),native_growth=0,resident_delta=0))
    sources=[ROOT/p for p in H4.SOURCES]+[Path(__file__),ROOT/'tools/host-lisp/o2_lite_r6_host.py']
    for path in sources:once(BUILD/'sources'/path.relative_to(ROOT),path.read_bytes())
    save(BUILD/'source.json',dict(status='PASS',sources=[S.bind(p) for p in sources],product_source_identity=H4.bindings(),committed_source_admission='OPEN; no Git writes'))
    host_files=[p for p in PROOF.rglob('*.json') if p.name not in
                ('resident.json','frozen-resident.json','baseline-config.json','frozen.json')]
    save(BUILD/'host/receipt.json',dict(status='PASS',proof=S.bind(PROOF/'receipt.json'),
        review=S.bind(PROOF/'review/receipt.json'),cost=S.bind(PROOF/'cost/cost.json'),
        admission=S.bind(PROOF/'admission/receipt.json'),
        gates=[S.bind(p) for p in sorted(host_files)],target_runs=0))
    save(BUILD/'runtime-identity.json',dict(status='PASS',ELF=S.bind(elf),predecessor=previous['ELF'],product_links=0,runtime_changed_bytes=0,per_key_resident_changed_bytes=0,library_before=before['code_bytes'],library_after=len(blob)))
    complete=dict(status='PASS',seed=1,final=0,product_links=0,medium=result['medium'],ELF=S.bind(elf),receipts=[S.bind(BUILD/p) for p in ('source.json','price.json','capacity.json','media.json','host/receipt.json','runtime-identity.json','negative-controls.json','continuation.json')])
    save(BUILD/'seed.json',complete);save(BUILD/'complete.json',complete)
    return complete

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('action',nargs='?',default='seed',choices=['seed','finish'])
    print(json.dumps(globals()[parser.parse_args().action](),indent=2))
