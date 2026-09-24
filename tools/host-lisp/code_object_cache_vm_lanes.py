"""Fresh VM lanes tied by re-emission to the final packed Stdlib population."""
import json,sys,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];E=Path(__file__).parent
sys.path.insert(0,str(ROOT/'tools/host-lisp'))
import c2_v160_input_service_time_pricing as P
from types import SimpleNamespace
from code_object_cache_producer import bind
Q=SimpleNamespace(C=SimpleNamespace(load=lambda p:json.loads(p.read_text()),bind=bind,
    canonical=lambda v:(json.dumps(v,indent=2)+'\n').encode()),
    BASE_PREFLIGHT=ROOT/'build/put-kit-product-r4-preflight',
    PLANE=ROOT/'build/code-object-cache-product-r3-preflight/setup-owned/static-plane/narrow-static')
OUT=ROOT/'build/code-object-cache-vm-lanes-r1';OUT.mkdir(exist_ok=False)
rows=[];emissions=[]
for role,plane,medium in [('baseline',Q.BASE_PREFLIGHT/'setup-owned/static-plane/narrow-static','build/put-kit-seed-medium-r1'),
                          ('candidate',Q.PLANE,'build/code-object-cache-seed-medium-r1')]:
    source=Path(Q.C.load(plane/'stdlib-p0.manifest.json')['suite']);suite=P.P0._read_suite(str(source))
    prefix=OUT/role/'stdlib-p0'
    manifest=Q.C.load(plane/'stdlib-p0.manifest.json')
    P.P0.emit_artifacts(str(source),suite,str(prefix),base_addr=int(manifest['base_addr'],16))
    bound=[]
    for suffix in ('.blob.bin','.ext.bin','.dir.bin'):
        a=Path(str(prefix)+suffix);b=plane/('stdlib-p0'+suffix)
        assert a.read_bytes()==b.read_bytes(),(role,suffix)
        bound.append(dict(emitted=Q.C.bind(a),selected=Q.C.bind(b)))
    packed=Q.C.load(ROOT/medium/'packed-receipt.json')
    assert packed['closure']['failures']==packed['coherence']['failures']==[]
    emissions.append(dict(world=role,suite=Q.C.bind(source),equal_population=bound,packed=Q.C.bind(ROOT/medium/'packed-receipt.json')))
    suite['cases']=[dict(name='native-input-lane',expr='(%native-read-line)',expect=json.dumps('a'*40),
                         key_events=[97]*40+[13],max_steps=1000000)]
    (heap,names,code,flags,resident,bundle,directory,cases,entries,inliner)=P.P0._compile_suite(suite)
    macros=P.P0._macro_symbol_objs(heap,{},resident);abi,ledger=P.P0._suite_abi(suite)
    for cap in (1,8):
        h=heap.clone()
        for tag in ('key','shift','control','meta'):h.intern(tag)
        vm=P.TimingVM(heap=h,directory=directory,macro_symbols=macros,max_steps=1000000,
            max_call_args=suite.get('max_call_args'),key_events=[97]*40+[13],abi_profile=abi,abi_ledger=ledger,batch_cap=cap)
        answer=vm.run(directory[h.intern(entries[0])],[]);assert h.obj_to_text(answer)==json.dumps('a'*40)
        points=[step for label,step in vm.boundaries if label=='private-2'];assert len(points)>=2
        first,last=points[0],points[-1]
        rows.append(dict(world=role,batch_cap=cap,steps=last-first,steps_per_key=(last-first)/40,
            screen_cells_per_key=sum(first<=s<last for s in vm.screen_steps)/40,boundaries=vm.boundaries))
def qualify(rows):
    ratios={str(cap):next(r['steps'] for r in rows if r['world']=='candidate' and r['batch_cap']==cap)/
                        next(r['steps'] for r in rows if r['world']=='baseline' and r['batch_cap']==cap) for cap in (1,8)}
    assert all(x<=1.02 for x in ratios.values());return ratios
ratios=qualify(rows);mutations=[]
for cap in (1,8):
    trial=copy.deepcopy(rows);base=next(r['steps'] for r in trial if r['world']=='baseline' and r['batch_cap']==cap)
    next(r for r in trial if r['world']=='candidate' and r['batch_cap']==cap)['steps']=base*1.03
    try:qualify(trial)
    except AssertionError:mutations.append('three-percent-lane-'+str(cap))
    else:raise AssertionError('VM wall mutation survived')
value=dict(status='PASS',rows=rows,ratios=ratios,ceiling=1.02,emission_proofs=emissions,mutations_rejected=mutations,
    harness=Q.C.bind(Path(P.__file__)),driver=Q.C.bind(Path(__file__)),
    claim='Actual nine-cell indented native entry, same stimulus on both selected populations. Not the historical unindented 902-step fixture; no device claim.')
(OUT/'receipt.json').write_bytes(Q.C.canonical(value));print('PASS',ratios,[(r['world'],r['batch_cap'],r['steps_per_key']) for r in rows])

