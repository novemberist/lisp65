#!/usr/bin/env python3
"""Pack the reproduced 2.3.0 pair using only declared public source inputs."""
import hashlib
import json
from pathlib import Path
import shutil
import re

import c2_v230_public_product as C
import c2_v230_public_native as N
import c2_v230_public_overlays as O
import c2_v230_public_libraries as L
import c2_lite_canonical_product as CAN
import c2_lite_media_product as MEDIA
import c2_v160_refill_boundary_witness_media_repair as FACADE
import c2_v160_nested_map_swap_media as NESTED
import c2_packed_medium_transitive_closure as CLOSURE
import c2_packed_object_generation_coherence as COHERENCE
import c2_packed_symbolic_callee_closure as NAMES
import d81_persistence_fault as D81
from elf_truth import ElfTruth

ROOT=N.ROOT
PUBLIC=ROOT/'build/public-v2.3.0'
AUTHORITY=ROOT/'config/c2-v230-public-plane/media-authority.json'
PLANE=ROOT/'build/init-echo-product-r1-preflight/setup-owned/static-plane/narrow-static'


def identity(path):
    raw=path.read_bytes()
    return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def delivery_contract(authority):
    """One public delivery population, without a private predecessor receipt."""
    policy=authority['delivery']
    contract=json.loads(N.bound(policy['contract']))
    retired={name.upper() for name in policy['static_only']}
    N.require(len(retired)==len(policy['static_only']) and 'BUFFER' not in retired,
              'invalid retirement population')
    N.require(not retired & {n.upper() for n in policy['required_disk_packages']},
              'disk package retired')
    original=contract['media_entries']
    removed=[r for r in original if r['name'].upper() in retired]
    N.require({r['name'].upper() for r in removed}==retired,'unmatched retired role')
    contract['media_entries']=[r for r in original if r not in removed]
    removed_roles={r['artifact_role'] for r in removed}
    contract['artifact_roles']=[r for r in contract['artifact_roles'] if r not in removed_roles]
    contract['artifact_count']=len(contract['artifact_roles'])
    contract['media_entry_count']=len(contract['media_entries'])
    roles=[r['role_id'] for r in contract['media_entries']]
    N.require(roles==list(range(1,len(roles)+1)),'non-contiguous delivery roles')
    MEDIA.RECORDS=len(roles)
    MEDIA.DESCRIPTOR_BYTES=MEDIA.HEADER_BYTES+MEDIA.RECORD_BYTES*len(roles)
    return contract


def delivery_stager(authority,rows,out):
    """Exactly the admitted stager transformation; constants from these rows."""
    source=N.bound(authority['delivery']['source']).decode()
    roles=[r['role_id'] for r in rows]
    N.require(roles==list(range(1,len(rows)+1)),'stager role sequence')
    constants={'R3_DESCRIPTOR_BYTES':MEDIA.HEADER_BYTES+MEDIA.RECORD_BYTES*len(rows),
        'R3_DESCRIPTOR_RECORDS':len(rows),'R3_ROLE_LAST':max(roles),
        'R3_ROLE_MASK':sum(1<<(r-1) for r in roles)}
    begin=source.index('#ifdef LISP65_C2_LITE_MEDIA_STAGER\n')
    end=source.index('#elif defined(LISP65_SHIP_MEDIA_STAGER)',begin)
    block=source[begin:end]
    for name in constants:
        block,count=re.subn(r'(?m)^#define '+name+r' [^\n]+$',
            '#define '+name+' LISP65_DELIVERY_'+name,block)
        N.require(count==1,'stager constant population: '+name)
    generated=out/'delivery-stager-main.c'
    generated.write_text(source[:begin]+block+source[end:])
    header=out/'delivery-roles.h'
    header.write_text('/* Derived from selected delivery population. */\n'+''.join(
        '#define LISP65_DELIVERY_'+name+' '+str(value)+'u\n' for name,value in constants.items()))
    for path,key in ((generated,'expected_generated_source'),(header,'expected_generated_header')):
        N.require(identity(path)=={k:authority['delivery'][key][k] for k in ('bytes','sha256')},
                  'derived stager input differs: '+key)
    return generated,header,constants


def mapped_rows(truth):
    rows=[]
    for section in truth.sections:
        marker='__'+section.name.removeprefix('.')+'_load_start'
        if section.name.startswith('.lisp65_c2_mapped_') and truth.symbols_by_name.get(marker):
            start=truth.symbol(marker).value
            if start<0x30000:rows.append((start,truth.section_bytes(section.name),section.name))
    N.require(rows and len({start-truth.section(name).address for start,_,name in rows})==1,
              'mapped section population/offset drift')
    N.require(all((start-truth.section(name).address)%256==0 for start,_,name in rows),
              'mapped sections not page-congruent')
    return rows


def packed_gates(out,actual,prefix):
    """Rebind metadata only; compare every transported code byte first."""
    projection=out/'readback-product'
    shutil.copytree(PLANE/'product',projection)
    product=C.load(PLANE/'product/substitution-artifacts.json')
    inputs={r['materialized_path']:r for r in C.load(C.INPUTS)['inputs']}
    entries=[];offset=0
    for row in product['manifests']:
        key=Path(row['path']).name.removesuffix('.manifest.json')
        code=projection/(key+'.code.bin')
        raw=actual[b'CODE.BIN'][offset:offset+code.stat().st_size]
        N.require(raw==code.read_bytes(),'packed code differs: '+key)
        offset+=len(raw)
        # Source projection's path-only normalization is declared independently
        # of the historical binding retained by the compiler manifest.
        selected=inputs[row['path']]
        N.require(selected['consumed_provenance']==row,'manifest provenance mismatch')
        path=N.local(selected['materialized_path'])
        N.require(path.read_bytes()==N.bound(selected['source']),'manifest projection drift')
        row.clear();row.update(C.bind(path))
        value=C.load(path)
        entries.extend({'name':e['name'],'anonymous':bool(e.get('anonymous',False))}
                       for e in value['entries'])
    N.require(offset==len(prefix),'static code population extent mismatch')
    for role,row in product['artifacts'].items():
        path=projection/Path(row['path']).name
        N.require(identity(path)=={k:row[k] for k in ('bytes','sha256')},'artifact projection drift')
        row.clear();row.update(C.bind(path))
    product_path=projection/'substitution-artifacts.json'
    product_path.write_bytes(N.canonical(product))
    names=out/'packed-name-authority.json';names.write_bytes(N.canonical({'entries':entries}))
    NAMES.ANONYMOUS_AUTHORITY=names
    closure=CLOSURE.derive(product_path);CLOSURE.require_closed(closure)
    manifest=PLANE/'stdlib-p0.manifest.json'
    suite=C.load(ROOT/'config/c2-v200-public-plane/resident-interactive-stdlib-suite.json')
    suite['sources']=[str(N.local(p)) for p in C.load(manifest)['sources']]
    suite_path=out/'generation-suite.json';suite_path.write_bytes(N.canonical(suite))
    coherence=COHERENCE.derive(manifest,PLANE/'product/stdlib-p0.code.bin',suite_path,
                             (projection/'stdlib-p0.code.bin').read_bytes())
    COHERENCE.require_coherent(coherence)
    return dict(closure=closure,coherence=coherence)


def pack(*,stager_fixture=None):
    C.qualify_native_pair()
    authority=C.load(AUTHORITY)
    out=PUBLIC/'media'
    N.require(not out.exists(),'media output must be fresh')
    out.mkdir(parents=True)
    completion=out/'completion';shutil.copytree(C.OUT,completion)
    paths=C.artifact_paths();target=completion/paths['PRG'].name;elf=completion/paths['ELF'].name
    predecessors=NESTED.materialize_candidate_publish_predecessors(completion,target,elf)
    address,facade_bytes=FACADE.facade_truth(elf)
    _,offset=FACADE.prg_span(target,address,len(facade_bytes))
    before=paths['PRG'].read_bytes();after=target.read_bytes()
    N.require(len(before)==len(after) and before[:offset]==after[:offset] and
        before[offset+len(facade_bytes):]==after[offset+len(facade_bytes):] and
        after[offset:offset+len(facade_bytes)]==facade_bytes,'unexpected PRG materialization delta')
    facade=FACADE.packed_facade_gate(target,elf)
    CAN.ARTIFACTS=out/'artifacts';CAN.ARTIFACTS.mkdir()
    boot,geometry=CAN.build_boot_stage(elf,paths['profile'])
    truth=ElfTruth.read(elf,llvm_readobj=C.P.TOOLCHAIN/'llvm-readobj',include_section_data=True)
    mapped=mapped_rows(truth)
    payload,source,_,_,_=O.payload(elf);mapped.append((source,payload,O.SECTION));mapped.sort()
    prefix=(PLANE/'v6-semantics/bank2-static-code.bin').read_bytes()
    image=bytearray(max(start+len(raw) for start,raw,_ in mapped)-0x20000)
    image[:len(prefix)]=prefix;cursor=0x20000+len(prefix)
    for start,raw,name in mapped:
        N.require(cursor<=start and start+len(raw)<=0x30000,'mapped owner overlap: '+name)
        image[start-0x20000:start-0x20000+len(raw)]=raw;cursor=start+len(raw)
    code=CAN.ARTIFACTS/'bank2-static-code.bin';code.write_bytes(image)
    roles={'linked-product-elf':elf,'c2-resident-prg':target,
        'c2-bank2-static-code-plane':code,'c2d-v6-code-plane':PLANE/'v6-semantics/initial.c2d-v6.bin',
        'c2-two-record-boot-stage':boot,'resolved-profile':paths['profile'],
        'c2-session-family-region-0':completion/'runtime-overlays-session-final.bin',
        'c2-session-family-region-1':completion/'runtime-overlays-session-final-region1.bin',
        'c2-product-shelf':PLANE/'product/product-shelf-v4-direct.bin',
        'c2-boot-family':completion/'runtime-overlays-boot-final.bin',
        'c2-kernal-window':completion/'c2-product-kernal-window.bin'}
    for role,path in roles.items():N.require(identity(path)==authority['roles'][role],'media role differs: '+role)
    MEDIA.BUILD=out
    contract=delivery_contract(authority)
    staged,reset=MEDIA.stage_artifact_map(contract,roles,write=True)
    rows=MEDIA.media_rows(contract,staged)
    descriptor,build_id=MEDIA.make_descriptor(rows,int(identity(paths['profile'])['sha256'][:8],16))
    desc=out/'boot.id';desc.write_bytes(descriptor)
    parsed=MEDIA.parse_descriptor(descriptor,build_id,rows)
    mutations=MEDIA.mutation_gate(descriptor,build_id,rows)
    domains=MEDIA.stage_domain_gate(rows)
    stager=out/'autoboot.c65'
    generated,header,constants=delivery_stager(authority,rows,out)
    if stager_fixture is None:
        old_source=MEDIA.STAGER_C
        try:
            MEDIA.STAGER_C=generated
            stager_gate=MEDIA.compile_stager(build_id,rows,build_dir=out,stager=stager,
                stager_map=Path(str(stager)+'.map'),compile_defines=(
                    *authority['stager_defines'],'-Iscripts','-include',str(header)))
        finally:
            MEDIA.STAGER_C=old_source
    else:
        N.require(identity(stager_fixture)==authority['roles']['cold-stager'],'preflight stager differs')
        shutil.copyfile(stager_fixture,stager)
        stager_gate={'status':'FIXTURE ONLY; NOT A REPRODUCTION'}
    roles.update({'boot-descriptor':desc,'cold-stager':stager})
    N.require(set(roles)==set(authority['roles']),'media role population differs')
    for role,path in roles.items():N.require(identity(path)==authority['roles'][role],'media role differs: '+role)
    medium=out/'lisp65-product.d81'
    entries=[(stager,'autoboot.c65'),(desc,'boot.id'),*[(r['path'],r['name']) for r in rows]]
    library_id=int.from_bytes((PLANE/'v6-semantics/initial.c2d-v6.bin').read_bytes()[44:48],'little')
    libraries,entries=L.build(medium,authority['disk_label'],entries,library_id)
    MEDIA.D81.stamp_product_boot_marker(medium)
    N.require(identity(medium)==authority['medium'],'HALT: reproduced D81 differs')
    actual=D81.visible_files(medium.read_bytes())
    N.require({name.decode():dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
               for name,raw in actual.items()}==authority['files'],'delivered file identities differ')
    gates=packed_gates(out,actual,prefix)
    result=dict(status=('PREFLIGHT ONLY' if stager_fixture else 'PASS: PUBLIC MEDIA BYTEIDENTICAL'),
        medium=C.bind(medium),roles={role:C.bind(path) for role,path in roles.items()},
        facade=facade,predecessors=predecessors,boot_geometry=geometry,reset=reset,
        descriptor=parsed,mutations=mutations,domains=domains,stager=stager_gate,
        delivery_constants=constants,libraries=libraries,**gates)
    (out/'receipt.json').write_bytes(N.canonical(result))
    return result
