#!/usr/bin/env python3
"""Public Comfort media successor of c2_v240_public_media.

Complete a freshly reproduced native pair; derive runtime families, compile
the cold stager and Comfort library, and require the exact Final D81.
"""
import hashlib
import json
from pathlib import Path
import shutil
import re

import c2_v240_public_product as C
import c2_v240_public_native as N
import c2_v240_public_overlays as O
import c2_v240_public_libraries as L
import c2_lite_canonical_product as CAN
import c2_lite_media_product as MEDIA
import c2_v160_refill_boundary_witness_media_repair as FACADE
import boot_only_carrier_elf_gate as CARRIER_ELF
import boot_only_carrier_prg as CARRIER_PRG
import c2_packed_medium_transitive_closure as CLOSURE
import c2_packed_object_generation_coherence as COHERENCE
import c2_packed_symbolic_callee_closure as NAMES
import d81_persistence_fault as D81
from elf_truth import ElfTruth

ROOT=N.ROOT
PUBLIC=ROOT/'build/public-v2.5.1'
AUTHORITY=ROOT/'config/c2-v251-r2-20260929-public-media-reproduction.json'
PLANE=ROOT/'build/nested-error-recovery-product-r1-preflight/setup-owned/static-plane/narrow-static'


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
    entries=[];offset=0
    for row in product['manifests']:
        value=C.load(N.local(row['path']))
        key=Path(row['path']).name.removesuffix('.manifest.json')
        code=projection/(key+'.code.bin')
        raw=actual[b'CODE.BIN'][offset:offset+code.stat().st_size]
        N.require(raw==code.read_bytes(),'packed code differs: '+key)
        offset+=len(raw)
        N.bound(row)
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
    manifest=N.local(product['manifests'][0]['path'])
    suite={'sources':C.load(manifest)['sources']}
    suite['sources']=[str(N.local(p)) for p in C.load(manifest)['sources']]
    suite_path=out/'generation-suite.json';suite_path.write_bytes(N.canonical(suite))
    coherence=COHERENCE.derive(manifest,PLANE/'product/stdlib-p0.code.bin',suite_path,
                             (projection/'stdlib-p0.code.bin').read_bytes())
    COHERENCE.require_coherent(coherence)
    return dict(closure=closure,coherence=coherence)


def pack_media(*,stager_fixture=None):
    authority=C.load(AUTHORITY)
    raw_pair=C.load(ROOT/'config/c2-v251-r2-20260929-public-replay.json')['raw_pair']
    raw_pair['profile']=C.load(N.MANIFEST)['profile']
    paths=C.artifact_paths();target=paths['PRG'];elf=paths['ELF']
    for role in ('ELF','profile'):
        N.require(identity(paths[role])=={k:raw_pair[role][k] for k in ('bytes','sha256')},
                  'native artifact differs before packing: '+role)
    N.require(identity(target)==authority['roles']['c2-resident-prg'],
              'completed resident PRG differs from the accepted materialization')
    out=PUBLIC/'media'
    N.require(not out.exists(),'media output must be fresh')
    out.mkdir(parents=True)
    completion=C.OUT
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
    linked=CARRIER_ELF.check(elf)
    extended_bytes=CARRIER_PRG.from_elf(elf,target.read_bytes(),publication_dir=completion)
    extended=out/'extended-resident.prg';extended.write_bytes(extended_bytes)
    N.require(identity(extended)==authority['extended_resident'],
              'HALT: extended resident PRG differs')
    staged,reset=MEDIA.stage_artifact_map(contract,{**roles,'c2-resident-prg':extended},write=True)
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
    libraries,entries=build_libraries(medium,authority['disk_label'],entries,library_id)
    MEDIA.D81.stamp_product_boot_marker(medium)
    normalize_replaced_file_tails(medium,authority)
    N.require(identity(medium)==authority['medium'],'HALT: reproduced D81 differs')
    actual=D81.visible_files(medium.read_bytes())
    N.require({name.decode():dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
               for name,raw in actual.items()}==authority['files'],'delivered file identities differ')
    gates=packed_gates(out,actual,prefix)
    result=dict(status=('PREFLIGHT ONLY' if stager_fixture else 'PASS: PUBLIC MEDIA BYTEIDENTICAL'),
        medium=C.bind(medium),roles={role:C.bind(path) for role,path in roles.items()},
        facade=facade,extended_resident=dict(C.bind(extended),linked=linked),
        boot_geometry=geometry,reset=reset,
        descriptor=parsed,mutations=mutations,domains=domains,stager=stager_gate,
        delivery_constants=constants,libraries=libraries,**gates)
    # Candidate-manifest artifact rows consumed by `workbench_product.py artifact`.
    result['artifacts']=[dict(role='product-d81',**C.bind(medium)),
                         dict(role='resident-prg',**C.bind(target)),
                         dict(role='extended-resident-prg',**C.bind(extended)),
                         dict(role='linked-product-elf',**C.bind(elf))]
    (out/'receipt.json').write_bytes(N.canonical(result))
    return result


def build_libraries(medium,label,entries,build_id):
    """Final's INIT, six packages, then index order; public package inputs only."""
    import c2_v251_r2_20260929_public_libraries as comfort
    import c2_require_resolver_gate as index_codec
    import c2_defstruct_foundations_gate as F
    import subprocess
    authority=C.load(L.AUTHORITY)
    out=medium.parent/'libraries';out.mkdir()
    comfort.build(out/'comfort')
    package=out/'comfort/repl-comfort.manifest.json'
    rows=[];files=[];payloads={}
    specs=[(r['name'],r['shelf'],N.local(r['manifest']['path']),tuple(r['dependencies'])) for r in authority['libraries']]
    specs.append(('repl-comfort','repl',package,()))
    for name,shelf,manifest,deps in specs:
        row,data=F.measured_row(name,name,shelf,manifest,deps,1,1,product_build_id=build_id)
        p=out/name;p.write_bytes(data);rows.append(row);files.append((p,name));payloads[name]=data
    index=out/'l65index';index.write_bytes(index_codec.encode_index(rows))
    init=ROOT/'config/comfort-default-plane/libraries/INIT.L65'
    entries=[*entries,(init,'init.l65'),*files,(index,'l65index')]
    # Reserve the inherited shelf extent first. Strings grows this existing
    # chain by one sector using the accepted ascending first-free allocator.
    # Only emitted product bytes supply payloads; no retained D81 is read.
    baseline=C.load(ROOT/'config/c2-v250-public-media-reproduction.json')['files']
    shelf=next(p for p,n in entries if n.upper()=='SHELF.BIN')
    payload=shelf.read_bytes()
    scaffold=out/'shelf-allocation-prefix.bin'
    scaffold.write_bytes(payload[:baseline['SHELF.BIN']['bytes']])
    reserved=[(scaffold if n.upper()=='SHELF.BIN' else p,n) for p,n in entries]
    MEDIA.build_d81(medium,label,reserved);MEDIA.D81.stamp_product_boot_marker(medium)
    # Exact accepted transaction algorithm; keep existing sectors and append
    # the first free sector. The final tail is normalized below.
    import strings_seed_producer as replacement
    ledger={}
    medium.write_bytes(replacement.replace_file(medium.read_bytes(),'shelf.bin',payload,ledger))
    locators=index_codec.d81_locators(medium);rows=[]
    for name,shelf,manifest,deps in specs:
        row,data=F.measured_row(name,name,shelf,manifest,deps,*locators[name],product_build_id=build_id)
        N.require(data==payloads[name],'package locator changed payload');rows.append(row)
    index.write_bytes(index_codec.encode_index(rows))
    for cmd in (['c1541',str(medium),'-delete','l65index'],['c1541',str(medium),'-write',str(index),'l65index']):
        subprocess.run(cmd,cwd=ROOT,check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    N.require(index_codec.d81_locators(medium)==locators,'index replacement moved files')
    mutations=index_codec.mutation_gate(index.read_bytes(),payloads,artifact_build_id=build_id)
    return dict(status='PASS: SIX PUBLIC PACKAGES',rows=rows,mutations=mutations),entries


def pack(paths):
    """Complete the freshly compiled pair through the public v240 successor."""
    import c2_v251_r2_20260929_public_native as public
    N.bound=public.bound
    C.prepare();C.configure()
    materialize_plane()
    native=C.load(N.MANIFEST)
    profile=C.OUT/'resolved-profile.txt';profile.write_bytes(N.bound(native['profile']))
    for role,suffix in (('PRG',''),('ELF','.elf')):
        shutil.copyfile(paths[role],C.OUT/('lisp65-c2-substitution-linked.prg'+suffix))
    shutil.copyfile(Path(str(paths['PRG'])+'.map'),Path(str(C.artifact_paths()['PRG'])+'.map'))
    C.complete(C.artifact_paths()['PRG'])
    return pack_media()['medium']


def materialize_plane():
    authority=C.load(ROOT/'config/c2-v251-r2-20260929-public-plane/inputs.json')
    for row in authority['files']:N.bound(row)
    for row in authority['inputs']:
        target=N.local(row['materialized_path']);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(N.bound(row['source']))


def normalize_replaced_file_tails(medium,authority):
    """The IDE/Backspace replacement writer zero-filled changed files' last sectors.

    c1541 leaves unused tail bytes. Reproduce the accepted writer's padding
    from file identities and chain lengths, never from a retained disk image.
    """
    baseline=C.load(ROOT/'config/c2-v250-public-media-reproduction.json')['files']
    changed={name for name,row in authority['files'].items() if row!=baseline[name]}
    raw=bytearray(medium.read_bytes());before=D81.visible_files(raw);rows=[]
    for slot in D81.directory_slots(raw):
        record=slot.record
        if not record[2]:continue
        name=record[5:21].rstrip(b'\xa0').decode()
        if name not in changed:continue
        track,sector=D81.file_chain(raw,record)[-1]
        at=D81.sector_offset(track,sector);end=at+1+raw[at+1]
        N.require(raw[at]==0 and at+2<=end<=at+256,'invalid final sector')
        rows.append(dict(name=name,offset=end,bytes=at+256-end))
        raw[end:at+256]=bytes(at+256-end)
        if name=='L65INDEX':
            # c1541 reused its first-sector buffer for the shorter second
            # sector of the inherited index. Re-encode that public index;
            # later file replacements preserve its unused bytes.
            import c2_require_resolver_gate as index_codec
            inherited=C.load(ROOT/'config/c2-v250-public-media.json')
            encoded=index_codec.encode_index(inherited['packages'])
            used=end-(at+2)
            N.require(len(encoded)==len(before[b'L65INDEX'])==320,'index extent drift')
            raw[end:at+256]=encoded[used:254]
        elif name=='AUTOBOOT.C65':
            # Walks shortened the stager by four bytes without clearing its
            # old final footer; Strings preserves that replacement slack.
            stager=before[b'AUTOBOOT.C65']
            removed=baseline[name]['bytes']-len(stager)
            N.require(removed==4,'stager shrink extent drift')
            raw[end:end+removed]=stager[-removed:]
    N.require(D81.visible_files(raw)==before,'tail normalization changed file content')
    D81.validate_bam(raw);medium.write_bytes(raw)
    (medium.parent/'tail-normalization.json').write_bytes(N.canonical(dict(
        status='PASS',rule='Zero padding of replaced files, as accepted replace_file/chain_sector writer',rows=rows)))
