#!/usr/bin/env python3
"""Line-wrap successor of £, explicitly gated before its one seed."""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import plane_generated_data as DATA

import pound_quasiquote_product_card as Q
import consolidated_consumption_authority as WORLD
from evidence_era import stable_recorded_on

ROOT,C,F,B,A=Q.ROOT,Q.C,Q.F,Q.B,Q.A
BASE=ROOT/'build/pound-quasiquote-product-r1'
BASE_PREFLIGHT=ROOT/'build/pound-quasiquote-product-r1-preflight'
BUILD=ROOT/'build/line-wrap-product-r2'
PREFLIGHT=ROOT/'build/line-wrap-product-r2-preflight'
PLANE=PREFLIGHT/'setup-owned/static-plane/narrow-static'
E=ROOT/'build/line-wrap-r1'
AUTH='d7365831'
PLANE_AUTH='c5b4a6f7'
ORIGINAL_PLANE=ROOT/'build/line-wrap-product-r1-preflight/setup-owned/static-plane/narrow-static'
PATCH='ef09e9ec'
ORIGINAL_SOURCE_GATE=Q.source_gate
ORIGINAL_MATERIALIZE=Q.materialize
LEAF=C.B.PREV.CARD.CARD2.R2.CARD
STRIP=LEAF.BASE


def packed_properties(consumer_elf=None):
    product=PLANE/'product/substitution-artifacts.json'
    closure=STRIP.CLOSURE.derive(product);STRIP.CLOSURE.require_closed(closure)
    specs=STRIP.candidate_specs()
    lengths=[int(C.load(p)['code_bytes']) for _,_,p in specs]
    plane=(PLANE/'v6-semantics/bank2-static-code.bin').read_bytes()
    assert sum(lengths)==len(plane)==C.load(E/'plane.json')['plane_bytes']
    assert closure['object_count']==C.load(product)['entries']
    coherence=STRIP.COHERENCE.derive(specs[0][2],PLANE/'product/stdlib-p0.code.bin',None,plane[:lengths[0]])
    STRIP.COHERENCE.require_coherent(coherence)
    sources=STRIP.lifecycle_key_sources(specs);STRIP.validate_lifecycle_key_sources(sources)
    wall=STRIP.V19_CONSUMER.run_delivered_consumer(ROOT/sources['lifecycle_source']['path'],
        consumer_elf or (F.ELF if F.ELF.is_file() else BASE/'wplto/lisp65-c2-substitution-linked.prg.elf'),True)
    assert sources['active_sink_set']==['c2_kernal_input_take']
    assert wall['counters']==dict(raw=94,seen=94,stored=94,taken=94)
    return dict(closure=closure,generation_coherence=coherence,key_sources=sources,host_wall=wall,
        key_source_mutations_rejected=STRIP.lifecycle_key_source_mutations(sources),
        packed_plane=C.bind(PLANE/'v6-semantics/bank2-static-code.bin'))


def configuration_gate():
    """Keep F011/input/ownership checks; do not borrow v1.9 editor identity."""
    LEAF.configure()
    STRIP.CHAIN.setup_link_world()
    plane=C.load(F.PLANE_RECEIPT)
    assert 'hot_path' not in plane, 'historical byte-identity claim leaked into successor'
    assert plane['geometry']==STRIP.geometry()
    assert plane['product_world_identity']==world()
    packed=packed_properties()
    consumption=STRIP.CONSUMPTION.evaluate()
    registration=C.PRODUCT.f011_cold_inventory_registration()
    assert registration['selected'] is True
    assert registration['source']=='src/optional/c2_f011_cold_wrappers.s'
    assert registration['allocated']==['.lisp65_c2_mapped_f011_cold']
    return dict(status='PASS: LINE-WRAP COMMISSIONED PRELINK',plane=C.bind(F.PLANE_RECEIPT),
        packed=packed,product_world_identity=world(),F011_registration=registration,
        semantics=LEAF.semantic_source_gate(),editor_projection=C.bind(E/'projection.json'),
        known_pin_and_closure_population=consumption['prelink_authority'],
        authority_categories=sorted(consumption['consumption_cases']),
        mutations_rejected=world_mutations())


def authority():
    raw=subprocess.check_output(['git','show',AUTH+':docs/planning/v2.0.0-pre-plan.md'],cwd=ROOT)
    assert b'line-wrap-card@ef09e9ec' in raw and b'budget 1/1/1' in raw
    assert b'all-sample ratio' in raw and b'no exclusion' in raw.lower()
    pair={n:C.bind(BASE/'wplto'/p) for n,p in (
        ('ELF','lisp65-c2-substitution-linked.prg.elf'),
        ('PRG','lisp65-c2-substitution-linked.prg'),('PROFILE','resolved-profile.txt'))}
    assert pair['ELF']['sha256']=='e948ea210f6298d21e1b70cf02e81b87b160a862c095d6013ff149b30e0a3206'
    assert pair['PRG']['sha256']=='2144e8df0ed8770c61b31fc71d3f24f468415587c80629049813229a2ec44480'
    return dict(commit=AUTH,patch_commit=PATCH,plan_sha256=hashlib.sha256(raw).hexdigest(),
                predecessor=pair,budget=dict(seed_WPLTO=2,final_C_LTO=1,product_links=1,
                host_images=3,device_contacts=0),conversion_seed_allowance=1,
                acceptance='both VM/native lanes, GC-time wall, every owner; physical rows need Owner word')


def world():
    base=WORLD.derive_product_world_identity(selected_plane=BASE_PREFLIGHT/'setup-owned/static-plane/narrow-static')
    emission=C.load(E/'plane.json')
    assert emission['status']=='PASS: SIX-ROLE LIBRARY SUCCESSOR; NO PRODUCT BUILD'
    assert emission['baseline_blob_identical'] and emission['authority']==PLANE_AUTH
    for path,key in (('product/substitution-artifacts.json','product'),('v6-semantics/bank2-static-code.bin','bank2')):
        actual=C.bind(PLANE/path)
        assert all(actual[k]==emission[key][k] for k in ('sha256','bytes'))
    selected=WORLD._plane_world(PLANE)
    assert selected['product_build_id']==emission['product_build_id']
    assert selected['banner']==base['bound_release_world']['banner']
    registered=WORLD.register_commissioned_product_world(name='line-wrap-r2',world=selected,
        evidence=[C.bind(E/p) for p in ('plane.json','projection.json','stdlib-read-line-native.lisp',
                                      'domain-tier1-sealed.lisp')])
    base.update(selected_plane_world=selected,commissioned_successor=registered)
    WORLD.validate_product_world_identity(base)
    return base


def world_mutations():
    value=world();rejected=WORLD.product_world_mutations(value)
    for label,mutate in (
        ('successor-registration-omitted',lambda x:x.pop('commissioned_successor')),
        ('successor-evidence-omitted',lambda x:x['commissioned_successor']['evidence'].pop()),
        ('successor-name-changed',lambda x:x['commissioned_successor'].update(name='other')),
        ('old-release-selected',lambda x:x.update(selected_plane_world=WORLD._plane_world(
            BASE_PREFLIGHT/'setup-owned/static-plane/narrow-static')))):
        trial=deepcopy(value);mutate(trial)
        try:WORLD.validate_product_world_identity(trial)
        except (WORLD.AuthorityError,KeyError):rejected.append(label)
        else:raise AssertionError(label)
    return [dict(name=n,result='rejected-before-WPLTO') for n in rejected]


def source_gate():
    inherited=ORIGINAL_SOURCE_GATE()
    for p in ('lib/stdlib-read-line.lisp','lib/repl-comfort.lisp',
              'tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json'):
        assert (ROOT/p).read_bytes()==subprocess.check_output(['git','show',PATCH+':'+p],cwd=ROOT)
    assert not subprocess.check_output(['git','diff','75f26afc','--name-only','--','src'],cwd=ROOT)
    from native_cycle_stationary import selftest
    wrap=C.load(E/'projected-wrap-tests.json')
    assert wrap['status']=='PASS' and len(wrap['cases'])==4
    for row in wrap['results']:
        role=row['role']
        assert C.bind(E/(role+'-wrap-suite.json'))['sha256']==row['suite_sha256']
        assert C.bind(E/(role+'-wrap-suite.log'))['sha256']==row['log_sha256']
        assert (row['exit_code']==0)==(role=='candidate')
    return dict(status='PASS: LINE-WRAP ONLY; NATIVE SOURCES UNCHANGED',
                generated_data_gate=C.bind(Path(DATA.__file__)),
                inherited_pound_sources=inherited,projection=C.bind(E/'projection.json'),
                plane=C.bind(E/'plane.json'),cycle_mutations=selftest(),
                native_wrap_contracts=C.bind(E/'projected-wrap-tests.json'),
                prepared_sources=[C.bind(ROOT/p) for p in ('lib/stdlib-read-line.lisp','lib/repl-comfort.lisp')])


def materialize(out):
    mapping=ORIGINAL_MATERIALIZE(out)
    derived,proof=DATA.derive(BASE_PREFLIGHT/'setup-owned/static-plane/narrow-static',PLANE,
        BASE/'wplto/generated-product-sources',out/'world-data-derivation',C.bind)
    for name,source in derived.items():
        targets=[p for p in mapping.values() if p.name==name]
        assert len(targets)==1
        targets[0].write_bytes(source.read_bytes())
    DATA.crc_tables(out/'generated-product-sources/c2-stream-phase-02a.c',PLANE)
    (out/'world-data-consumers.json').write_bytes(C.canonical(proof))
    return mapping


def profile(mapping=None):
    assert mapping
    by_name={p.name:p for p in mapping.values()}
    lines=(BASE/'wplto/resolved-profile.txt').read_text().splitlines()
    population=[];changes=[]
    parents={p.parent.parent for p in mapping.values()}
    assert len(parents)==1
    proof=C.load(next(iter(parents))/'world-data-consumers.json')
    permitted=set(proof['changed_members'])
    for i,line in enumerate(lines):
        if not line.startswith('input_sha256='):continue
        name,digest=line.split('=',1)[1].rsplit(':',1)
        before=(ROOT/name).resolve();assert C.bind(before)['sha256']==digest
        target=by_name.get(before.name,before) if '/generated-product-sources/' in name else mapping.get(before,before)
        current=C.bind(target)['sha256']
        if current!=digest:
            assert target.name in permitted, 'uncommissioned native source change: '+name
            changes.append(dict(name=target.name,before=digest,after=current))
        successor=(F.WPLTO/'generated-product-sources'/target.name).relative_to(ROOT).as_posix() if target in mapping.values() else name
        lines[i]=f'input_sha256={successor}:{current}'
        population.append(dict(before=name,after=successor,sha256=current))
    C.BOUND_PROFILE.write_text('\n'.join(lines)+'\n')
    assert A.features(C.BOUND_PROFILE)==A.features(A.PREDECESSOR['PROFILE'])
    assert {r['name'] for r in changes}==permitted
    return dict(predecessor=C.bind(BASE/'wplto/resolved-profile.txt'),successor=C.bind(C.BOUND_PROFILE),
                changes=changes,population=population,world_data=proof,feature_authority=B.feature_authority())


def configure():
    Q.BASE,Q.BASE_PREFLIGHT=BASE,BASE_PREFLIGHT
    Q.BUILD,Q.PREFLIGHT=BUILD,PREFLIGHT
    Q.authority,Q.profile,Q.source_gate=authority,profile,source_gate
    Q.materialize=materialize
    LEAF.product_world_identity=world
    LEAF.configuration_gate=configuration_gate
    STRIP.packed_properties=packed_properties
    emitted=C.load(E/'plane.json')
    assert emitted['bank2']['sha256']==C.bind(PLANE/'v6-semantics/bank2-static-code.bin')['sha256']
    LEAF.EXTENT=emitted['plane_bytes']
    Q.configure()
    for module in (F,C,C.B):
        module.DRIVER=Path(__file__).resolve();module.AUTHORIZATION=AUTH
        module.FORMAT='line-wrap-r1';module.STATUS='PENDING: LINE-WRAP QUALIFICATION'
        module.REPORT=ROOT/'docs/planning/line-wrap-product-report.md'


def preflight():
    assert not BUILD.exists() and not (PREFLIGHT/'candidate-invocation.json').exists()
    if not PLANE.exists():shutil.copytree(ORIGINAL_PLANE,PLANE)
    for source in ORIGINAL_PLANE.rglob('*'):
        if source.is_file():assert source.read_bytes()==(PLANE/source.relative_to(ORIGINAL_PLANE)).read_bytes()
    profile_path=PREFLIGHT/'bound-feature-profile.txt'
    if not profile_path.exists():shutil.copyfile(BASE/'wplto/resolved-profile.txt',profile_path)
    for name in ('projected-ownership-contract.json','projected-full-map-authority.json'):
        target=PREFLIGHT/name
        if not target.exists():shutil.copyfile(BASE_PREFLIGHT/name,target)
        assert target.read_bytes()==(BASE_PREFLIGHT/name).read_bytes()
    # Install the successor world before any inherited configuration consumer.
    configure()
    plane=C.load(BASE_PREFLIGHT/'plane-receipt.json')
    plane.pop('hot_path',None)
    plane['editor_projection']=C.bind(E/'projection.json')
    plane.update(format='line-wrap-r1-plane',recorded_on=stable_recorded_on(F.PLANE_RECEIPT),
        status='PASS: COMMISSIONED SIX-ROLE LINE-WRAP WORLD',authority=authority(),
        product=C.bind(PLANE/'product/substitution-artifacts.json'),
        profile=C.bind(PLANE/'candidate-profile.json'),contract=C.bind(PLANE/'c2-lite-execution-contract.json'),
        header=C.bind(PLANE/'c2_lite_static_plane.h'),bank2=C.bind(PLANE/'v6-semantics/bank2-static-code.bin'),
        geometry=LEAF.BASE.geometry(),
        manifests=[C.bind(p) for _,_,p in LEAF.BASE.CHAIN.candidate_specs()],
        product_world_identity=world(),mutations_rejected=world_mutations())
    F.PLANE_RECEIPT.write_bytes(C.canonical(plane))
    toolchain=C.B.toolchain_identity()
    configuration=LEAF.configuration_gate()
    mapping=Q.materialize(Path(tempfile.mkdtemp(prefix='bound-native-',dir=PREFLIGHT)))
    bindings=profile(mapping)
    value=dict(format='line-wrap-r1-preflight',recorded_on=stable_recorded_on(F.PREFLIGHT_RECEIPT),
        authority=authority(),world=world(),toolchain=toolchain,profile=bindings,
        configuration=configuration,source_population=B.source_population(),
        semantic=source_gate(),instrument_registry=C.PRODUCT.f011_status_inventory_registration(),
        accounting=dict(seed_WPLTO=0,final_C_LTO=0,product_links=0))
    F.PREFLIGHT_RECEIPT.write_bytes(C.canonical(value))
    print('Line-wrap preflight PASS; no product compiler invoked')


def main():
    B.configure=A.configure=configure
    if sys.argv[1:]==['preflight']:preflight()
    elif sys.argv[1:]==['seed']:B.produce_seed()
    elif sys.argv[1:]==['world-selftest']:
        print('line-wrap world: PASS mutations='+str(len(world_mutations())))
    else:raise SystemExit('Choose preflight, seed, or world-selftest; no implicit final link')


if __name__=='__main__':main()
