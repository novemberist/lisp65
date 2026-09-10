#!/usr/bin/env python3
"""Portable source preparation for the frozen 2.2.0 product.

The predecessor card graph is deliberately not imported. The source and
layout projection is a declared public input, not a private proof receipt.
Compilation remains locked until the complete release preflight is bound.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

import c2_v220_public_native as N
import c2_product_substitution_link as P
from elf_truth import ElfTruth

ROOT=Path(__file__).resolve().parents[2]
INPUTS=ROOT/'config/c2-v220-public-plane/inputs.json'
RECIPE=ROOT/'config/c2-v220-public-plane/native-recipe.json'
OUT=ROOT/'build/retirement-repair-product-r2/wplto'
ORIGINAL_INVENTORY=P.final_section_inventory_expectation
ORIGINAL_WITNESS=P.f011_status_inventory_registration
ORIGINAL_FINAL_CHECK=P.final_section_inventory_check
ORIGINAL_PATCH=P.patch_verifier_binding_table
ORIGINAL_TOTAL=P.total_publish_last_gate


def witness_absent(truth):
    section=truth.section('.noinit.lisp65_f011_status')
    N.require(section.bytes==0,'disabled witness allocated bytes')
    N.require(not any(s.name=='lisp65_f011_status_state' or
        (s.section==section.name and s.symbol_type=='Object') for s in truth.symbols),
        'disabled witness has state')
    N.require(not any(r.source_section==section.name or
        r.target=='lisp65_f011_status_state' for r in truth.relocations),
        'disabled witness has relocations')


def final_inventory_check(target):
    witness_absent(ElfTruth.read(Path(str(target)+'.elf'),llvm_readobj=P.TOOLCHAIN/'llvm-readobj'))
    return ORIGINAL_FINAL_CHECK(target)


def verifier_address(target):
    truth=ElfTruth.read(Path(str(target)+'.elf'),llvm_readobj=P.TOOLCHAIN/'llvm-readobj')
    section=truth.section(P.VERIFIER_BINDING_SECTION)
    N.require(section.bytes==P.runtime_binding_bytes(),'verifier binding extent drift')
    return section.address


def patch_binding(out,target,*args,**kwargs):
    address=verifier_address(target)
    kwargs['expected_base']=address
    P.VERIFIER_BINDING_BASE=P.LINK60_VERIFIER_BINDING_BASE=address
    value=ORIGINAL_PATCH(out,target,*args,**kwargs)
    N.require(value['address']==value['expected_address']==address,'binding address consumer drift')
    return value


def total_binding(out,target,*args,**kwargs):
    kwargs['expected_verifier_base']=verifier_address(target)
    return ORIGINAL_TOTAL(out,target,*args,**kwargs)


def artifact_paths():
    return {'PRG':OUT/'lisp65-c2-substitution-linked.prg',
            'ELF':OUT/'lisp65-c2-substitution-linked.prg.elf',
            'profile':OUT/'resolved-profile.txt'}


def qualify_native_pair():
    expected=load(N.AUTHORITY)['raw_pair']
    actual={role:bind(path) for role,path in artifact_paths().items()}
    for role,row in actual.items():
        N.require((row['bytes'],row['sha256'])==(expected[role]['bytes'],expected[role]['sha256']),
                  'HALT: reproduced native artifact differs: '+role)
    return actual


def load(path):
    return json.loads(path.read_bytes())


def bind(path):
    raw=path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def decode(value):
    if isinstance(value,dict):
        if set(value)=={'path'}:return N.local(value['path'])
        return {key:decode(item) for key,item in value.items()}
    if isinstance(value,list):return [decode(item) for item in value]
    return value


def materialize_inputs():
    N.materialize()
    inputs=load(INPUTS)
    N.require(inputs['private_evidence_is_build_input'] is False,'private input selected')
    for row in inputs['inputs']:
        raw=N.bound(row['source']);target=N.local(row['materialized_path'])
        N.require(not raw.startswith(b'\x7fELF'),'prebuilt native artifact selected')
        if target.exists():N.require(target.read_bytes()==raw,'refuse existing world overwrite: '+str(target))
        else:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)


def configure():
    native=load(N.MANIFEST);N.check()
    recipe=load(RECIPE)
    for name,value in recipe['values'].items():
        value=decode(value);kind=recipe['value_types'][name]
        if kind=='tuple':value=tuple(value)
        elif kind=='set':value=set(value)
        setattr(P,name,value)
    P.ROOT=ROOT
    P.BOUND_SCRIPT_INCLUDE_DIRECTORY=OUT/'generated-product-sources'
    if P.LINK60_FINAL_GEOMETRY:
        P.FIXED_BLOCK_LEAF.configure_link60_geometry()
    if P.DERIVED_FIXED_BANK0_CODE_LAYOUT:
        P.FIXED_BLOCK_LEAF.configure_candidate_derived_code_layout()
    P.PRODUCT_ARTIFACTS_MANIFEST_RESOLVER=None
    P.COMPILER_CONSUMED_STATIC_HEADER_RESOLVER=None
    sources=[str(N.local(row['materialized_path'])) for row in native['sources'] if row['translation_unit']]
    P.source_list=lambda _features=():list(sources)
    # Keep the two actual manifest-driven definitions dynamic. All other
    # definitions are explicit product geometry, not proof-derived defaults.
    scoped=P.scoped_probe_definitions(tuple(native['features']))
    base=[item for item in native['definitions'] if item not in scoped]
    N.require(len(base)+len(scoped)==len(native['definitions']),'definition partition drift')
    def definitions(artifacts):
        replacements={
            'LISP65_C2_PRODUCT_BUILD_ID':str(artifacts['product_build_id_hex'])+'UL',
            'LISP65_C2_PRODUCT_SHELF_BYTES':str(artifacts['artifacts']['shelf']['bytes'])+'UL'}
        return [item.split('=',1)[0]+'='+replacements[item.split('=',1)[0]]
                if item.split('=',1)[0] in replacements else item for item in base]
    P.definitions=definitions
    P._full_map_final_section_owners=lambda:decode(recipe['owners'])
    P.configure_compiler_consumed_feature_profile(N.local(native['profile']['path']),native['profile'],tuple(native['features']))
    manifest=load(P.PRODUCT_ARTIFACTS_MANIFEST)
    N.require(P.definitions(manifest)+list(scoped)==native['definitions'],'configured definitions differ from consumed authority')
    # Resolve the actual data consumers from the selected manifest as a pair,
    # never update a SHA while retaining another world's path.
    P.INITIAL_C2D=N.local(manifest['artifacts']['initial_c2d']['path'])
    P.PRODUCT_SHELF=N.local(manifest['artifacts']['shelf']['path'])
    for role in ('initial_c2d','shelf'):N.bound(manifest['artifacts'][role])
    import consolidated_consumption_authority as consumption
    consumption.configure_output_root_resolvers({
        'public-reproduction-identity:'+role:path for role,path in artifact_paths().items()})
    script='\n'.join(N.local(row['materialized_path']).read_text() for row in native['linker_sources'])
    def empty_witness():
        result=ORIGINAL_WITNESS()
        N.require(not result['selected'],'diagnostic witness selected')
        N.require('.noinit.lisp65_f011_status' in script,'empty witness declaration absent')
        result.update(names=['.noinit.lisp65_f011_status'],record_bytes=0)
        return result
    P.f011_status_inventory_registration=empty_witness
    def inventory():
        result=ORIGINAL_INVENTORY()
        additions=[]
        for spec in P.SESSION_SLICE_SPECS:
            name=spec.split(':')[2]
            if name not in result['names'] and name not in additions:
                N.require(name in script,'session owner missing from linker source')
                additions.extend([name,'.rela'+name])
        for name in re.findall(r'^\s*(\.noinit\.card2b_carrier_\w+)\s',script,re.M):
            if name not in result['names'] and name not in additions:additions.append(name)
        result['names']+=additions
        result['expected_names']=len(result['names'])
        result['added_by_configured_profile']+=additions
        return result
    P.final_section_inventory_expectation=inventory
    P.final_section_inventory_check=final_inventory_check
    P.patch_verifier_binding_table=patch_binding
    P.total_publish_last_gate=total_binding
    import c2_v220_public_overlays as overlays
    overlays.install()
    return native,manifest


def prepare():
    N.require(not OUT.exists(),'source preparation requires an independent empty build root')
    materialize_inputs()
    native,manifest=configure()
    # Force-inclusion does not satisfy repl.c's ordinary quoted include.
    # Supply the same selected bytes in the established include directory.
    selected=N.bound(P.COMPILER_CONSUMED_STDLIB_HEADER_BINDING)
    compatibility=ROOT/'build/c2.2/substitution/stdlib-p0.h'
    compatibility.parent.mkdir(parents=True,exist_ok=True)
    if compatibility.exists():
        N.require(compatibility.read_bytes()==selected,'include compatibility header belongs to another world')
    else:compatibility.write_bytes(selected)
    profile=OUT/'resolved-profile.txt'
    profile.write_bytes(N.bound(native['profile']))
    os.environ.update(LISP65_LTO_RNG_SEED='0',LISP65_LTO_THREADS='1',
        LISP65_DETERMINISTIC_OBJECTS='1',LISP65_LLVM_LINK='/usr/bin/llvm-link',LISP65_DISABLE_LINK_ASLR='1')
    standard=OUT/'runtime-overlay.prepare-standard.h'
    prepared=OUT/'runtime-overlay.prepare.h'
    island=OUT/'resident-island.prepare.h'
    error=OUT/'error-text-table.h'
    P.tool('runtime_overlay_bank.py','prepare','--abi-contract',str(profile),
           '--header',str(standard),'--profile',P.PROFILE,'--format-version',str(P.RUNTIME_OVERLAY_FORMAT_VERSION))
    P.render_prepared_family_header(standard,prepared)
    P.tool('resident_island.py','prepare','--abi-contract',str(profile),'--header',str(island))
    build_id=int(hashlib.sha256(profile.read_bytes()).hexdigest()[:8],16)
    P.tool('error_text_table.py','prepare','--spec',str(ROOT/'config/error-texts.json'),
           '--profile','workbench','--build-id',hex(build_id),'--header',str(error),'--binary',str(OUT/'error-text-table.bin'))
    stage=OUT/'stage-config.h'
    stage.write_text('\n'.join(['#ifndef LISP65_WORKBENCH_OVERLAY_STAGE_H',
        '#define LISP65_WORKBENCH_OVERLAY_STAGE_H','#define LISP65_BOOT_OVERLAY_STAGE_BANK 0x05u',
        '#define LISP65_BOOT_OVERLAY_STAGE_OFF 0x8500u',
        f'#define LISP65_BOOT_OVERLAY_PROFILE_BUILD_ID 0x{build_id:08x}UL','#endif','']))
    (OUT/'c2-kernal-window.generated.h').write_bytes(P.kernal_header_values(P.KERNAL_CRC_BINDING_SENTINEL,'0'*64))
    result=dict(status='SOURCE PREPARED; COMPILATION NOT AUTHORIZED BY THIS RECEIPT',
        compiler_invocations=0,source_projection=bind(N.MANIFEST),recipe=bind(RECIPE),
        headers=[bind(path) for path in (stage,prepared,island,error)],
        ordinary_stdlib_include=bind(compatibility),
        native_inputs=N.check(),manifest=bind(P.PRODUCT_ARTIFACTS_MANIFEST))
    (OUT/'public-source-prepared.json').write_bytes(N.canonical(result))
    return result


def command_preflight(*,header_overrides=None,target_name='resident-island-seed.prg'):
    """Exercise the real command constructor while executing no commands."""
    native,manifest=configure()
    prepared=load(OUT/'public-source-prepared.json')
    headers=header_overrides or [N.local(row['path']) for row in prepared['headers']]
    for row in prepared['headers']:N.bound(row)
    commands=[]
    class CapturedLink(Exception):pass
    old_run,old_link=P.run,P.run_link_with_exact_orphan_wrapper
    def record(argv,**kwargs):
        N.require(Path(argv[0]).name in ('mos-mega65-clang','llvm-link'),'unexpected preflight command')
        commands.append(list(argv));return ''
    def link(_out,_target,argv):
        commands.append(list(argv));raise CapturedLink()
    os.environ.update(LISP65_LTO_RNG_SEED='0',LISP65_LTO_THREADS='1',
        LISP65_DETERMINISTIC_OBJECTS='1',LISP65_LLVM_LINK='/usr/bin/llvm-link',LISP65_DISABLE_LINK_ASLR='1')
    # The inspection uses a distinct object directory; a real reproduction
    # must not mistake these empty directories for compiled objects.
    sequence=1
    while (OUT/f'.public-command-preflight-{sequence}').exists():sequence+=1
    objects=OUT/f'.public-command-preflight-{sequence}'
    P.run,P.run_link_with_exact_orphan_wrapper=record,link
    try:
        try:P.compile_link(OUT,target_name,headers,manifest,
                           probe_definitions=tuple(native['features']),
                           deterministic_object_directory=objects)
        except CapturedLink:pass
        else:raise ValueError('command preflight never reached the link constructor')
    finally:P.run,P.run_link_with_exact_orphan_wrapper=old_run,old_link
    N.require(len(commands)==sum(r['translation_unit'] for r in native['sources'])+2,
              'compiler/merge/link command population drift')
    result=dict(status='PASS: REAL COMMAND CONSTRUCTORS, NO COMMAND EXECUTED',
                commands=commands,compiler_invocations=0,link_invocations=0,
                source_projection=bind(N.MANIFEST),recipe=bind(RECIPE))
    (OUT/f'public-command-preflight-{sequence}.json').write_bytes(N.canonical(result))
    return dict(status=result['status'],commands=len(commands),compiler_invocations=0,
                receipt=str((OUT/f'public-command-preflight-{sequence}.json').relative_to(ROOT)))


def public_preflight():
    authority=load(N.AUTHORITY)
    N.require(authority['producer_preflight_complete'] is True,'public producer preflight not closed')
    bindings=authority['producer_inputs']
    required={str(path.relative_to(ROOT)) for path in
              (INPUTS,RECIPE,ROOT/'config/c2-v220-public-plane/media-authority.json',
               ROOT/'config/c2-v220-public-plane/libraries/libraries.json')}
    N.require(required<=set(row['path'] for row in bindings),'public consumer binding population incomplete')
    N.require(len(bindings)==len({row['path'] for row in bindings}),'duplicate public input binding')
    for row in bindings:N.bound(row)
    inputs=load(INPUTS)
    N.require(inputs['bootstrap_export_contract_pending'] is False,'bootstrap provenance not closed')
    for row in inputs['inputs']:N.bound(row['source'])
    result=N.check()
    result['public_producer_inputs']=len(bindings)
    return result


def build():
    """One independent 1/1/1 reproduction, with a terminal failure marker."""
    public_preflight()
    N.require(not OUT.exists(),'HALT: reproduction output already exists; no automatic retry')
    prepare()
    native,manifest=configure()
    prepared=load(OUT/'public-source-prepared.json')
    headers=[N.local(row['path']) for row in prepared['headers']]
    state=dict(status='STARTED',seed_wplto=0,final_c_lto=0,product_link=0)
    receipt=OUT/'public-reproduction.json'
    def record(phase):
        state['phase']=phase;receipt.write_bytes(N.canonical(state))
    try:
        import c2_v220_public_includes as includes
        state['seed_include_gate']=includes.check()
        state['seed_wplto']=1;record('seed-invoked')
        seed=P.compile_link(OUT,'resident-island-seed.prg',headers,manifest,
                            probe_definitions=tuple(native['features']))
        seed_elf=Path(str(seed)+'.elf');expected=load(N.AUTHORITY)['raw_pair']['ELF']
        N.require({k:bind(seed_elf)[k] for k in ('bytes','sha256')}==
                  {k:expected[k] for k in ('bytes','sha256')},
                  'HALT: seed ELF differs from accepted seed/final identity')
        record('seed-byteidentical')
        island=OUT/'resident-island.h'
        P.tool('resident_island.py','materialize','--elf',str(seed_elf),
            '--nm',str(P.TOOLCHAIN/'llvm-nm'),'--objcopy',str(P.TOOLCHAIN/'llvm-objcopy'),
            '--abi-contract',str(artifact_paths()['profile']),'--header',str(island))
        final_headers=[headers[0],headers[1],island,headers[3],OUT/'c2-kernal-window.generated.h']
        state['final_include_gate']=includes.check(headers=final_headers,target_name='lisp65-c2-substitution-linked.prg')
        state['final_c_lto']=state['product_link']=1;record('final-invoked')
        final=P.compile_link(OUT,'lisp65-c2-substitution-linked.prg',final_headers,manifest,
                             probe_definitions=tuple(native['features']))
        record('final-emitted')
        P.finish_single_link(OUT,final,artifact_paths()['profile'])
        state['native_pair']=qualify_native_pair();record('native-pair-byteidentical')
        import c2_v220_public_media as media
        state['media']=media.pack()['medium']
        state['status']='PASS: REPRODUCED PAIR AND MEDIUM BYTEIDENTICALLY'
        record('complete')
    except BaseException as error:
        state['status']='HALT';state['error']=str(error)
        receipt.write_bytes(N.canonical(state))
        raise
    return state


def check():
    public_preflight()
    pair=qualify_native_pair()
    receipt=load(OUT/'public-reproduction.json')
    N.require(receipt['status']=='PASS: REPRODUCED PAIR AND MEDIUM BYTEIDENTICALLY'
        and (receipt['seed_wplto'],receipt['final_c_lto'],receipt['product_link'])==(1,1,1),
        'completed reproduction receipt absent')
    N.require(receipt['native_pair']==pair,'native pair receipt drift')
    import c2_v220_public_media as media
    packed=load(media.PUBLIC/'media/receipt.json')
    expected=load(media.AUTHORITY)
    N.require(packed['status']=='PASS: PUBLIC MEDIA BYTEIDENTICAL','fixture is not a reproduction')
    N.require(set(packed['roles'])==set(expected['roles']),'packed role population drift')
    for role,row in packed['roles'].items():
        N.bound(row)
        N.require({k:row[k] for k in ('bytes','sha256')}==expected['roles'][role],
                  'packed role differs: '+role)
    N.bound(packed['medium'])
    N.require({k:packed['medium'][k] for k in ('bytes','sha256')}==expected['medium'],
              'medium differs from target')
    return dict(status='PASS: REPRODUCED ARTIFACTS VERIFIED',pair=pair,medium=packed['medium'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('prepare','command-preflight','preflight','build','check'))
    args=parser.parse_args()
    print(json.dumps({'prepare':prepare,'command-preflight':command_preflight,
                      'preflight':public_preflight,'build':build,'check':check}[args.mode](),indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
