"""Verify complete scratch fault footprint and close the parked object proof."""
import ctypes as C
from pathlib import Path
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_shared_front_r2_20260926 as K

ROOT=P.ROOT
OUT=ROOT/'build/set-b-shared-front-close-r1'

def main():
    authority=S.require_auth();OUT.mkdir(exist_ok=False)
    proofs=[]
    for revision,expected in ((1,580),(2,626)):
        root=ROOT/f'build/set-b-shared-front-native-r{revision}';p=root/'receipt.json';r=P.load(p)
        text=sum(x['delta'] for x in r['changes'] if x['section'].startswith('.text.'))
        bss=sum(x['delta'] for x in r['changes'] if x['section'].startswith('.bss.'))
        assert (text,bss)==(expected,revision+2)
        assert ['c2_product_runtime.c','.lisp65_rt_c2append_reserve_persistent_code'] in r['unchanged_allocated_sections']
        for x in r['changes']:
            assert x['section'].startswith(('.text.c2_front_', '.text.c2_resolver_charged_front','.bss.c2_front_certificate')) or x['section'] in ('.text.vm_callprim','.lisp65_rt_c2append_retire_control','.lisp65_rt_c2append_retire_reset'),x
        for command in P.load(root/'commands.json'):
            assert command['exit']==command['dependencies']['exit']==0
            for item in command['dependencies']['inputs']:
                b=item['binding'];assert P.bind(ROOT/b['path'])==b
        proofs.append(dict(revision=revision,receipt=P.bind(p),text=text,BSS=bss,unchanged_sections=len(r['unchanged_allocated_sections'])))
    qr=ROOT/'build/set-b-shared-front-query-r2';q=P.load(qr/'receipt.json')
    assert q['row_count']==4554 and P.load(qr/'integration-gap-controls.json')==[]
    lib=qr/'fixture.so';d=C.CDLL(str(lib));d.invoke.restype=C.c_int16
    d.plane.argtypes=[C.POINTER(C.c_uint8)];d.configure.argtypes=[C.c_uint32,C.c_uint32,C.c_uint8]
    basepath=ROOT/'build/set-b-load-attribution-r1/definitions-2/before-load-c2d.bin'
    base=basepath.read_bytes();a=(C.c_uint8*65536).from_buffer_copy(base)
    count=int.from_bytes(base[16:18],'little');rows=[]
    allowed={184,185,*range(194,203)}
    for fault in range(1,count+2):
        for partial in (0,1,2):
            d.fixture_reset();d.plane(a);d.configure(fault,partial,1)
            before=bytes((C.c_uint8*304).in_dll(d,'lisp65_c2_phase_scratch'))
            assert d.invoke()==0
            after=bytes((C.c_uint8*304).in_dll(d,'lisp65_c2_phase_scratch'))
            differences=[i for i,(x,y) in enumerate(zip(before,after)) if x!=y]
            assert set(differences)<=allowed
            assert after[302:]==before[302:]
            if fault>1:assert after[202]==0
            else:assert after==before
            assert C.c_uint8.in_dll(d,'phase_owner').value==0 and d.state()==0
            assert C.c_uint32.in_dll(d,'allocations').value==0
            assert C.c_uint8.in_dll(d,'transport_latch').value==0
            assert C.c_uint8.in_dll(d,'c2_ready').value==1 and C.c_uint8.in_dll(d,'vm_status').value==93
            assert bytes((C.c_uint8*65536).in_dll(d,'arena'))==base
            rows.append(dict(fault=fault,partial=partial,changed_scratch_offsets=differences,
                owner_released=True,diagnostics_preserved=True,source_and_status_unchanged=True))
    assert len(rows)==2421
    P.write(OUT/'scratch-fault-rows.json',rows)
    P.write(OUT/'receipt.json',dict(status='PASS ISOLATED SHARED-SCANNER SUCCESSOR AND OBJECT ENVELOPE; PRODUCT INTEGRATION OPEN',
        driver=P.bind(Path(__file__)),source_authority=authority,execution_head='9a8f04cf',
        kernel=P.bind(K.OUT/'certificate.inc'),host=P.bind(qr/'receipt.json'),library=P.bind(lib),input=P.bind(basepath),
        prices=proofs,scratch_faults=P.bind(OUT/'scratch-fault-rows.json'),scratch_fault_rows=len(rows),
        predecessor=P.bind(ROOT/'build/set-b-scanner-reuse-audit-r1/receipt.json'),
        elf=P.bind(S.PRODUCT/'wplto/resident-island-seed.prg.elf'),
        medium=P.bind(ROOT/'build/set-b-seed-medium-r6/media-seed/set-b-comfort.d81'),
        selected_revision=2,ordinary_text=dict(new=626,previous=892,saving=266,available=784,remaining=158,projected_air=190,floor=32),
        high_BSS=dict(new=4,projected_air=6,floor=5,remaining=1),
        scanner=dict(changed=False,record=1743,limit=1792,air=49),
        inherited_prefix=dict(control_delta=83,reset_delta=-3,session_extent=6784,tail=1408,journal=72),
        hypothetical_resident_admission=1065,product_admitted=False,
        remaining=['Actual writer/raw-I/O hook closure','Decoder pending-front accumulation and recovery lifetime',
            'Install proposed abort hook before existing forced scratch releases','Real transport/fault-latch and exact BAD BYTECODE successors',
            'Cold INIT trace, native time, collector, stack and linked placement'],
        consumed=dict(seeds=5,finals=0,product_links=5),authorized_ceiling=dict(seeds=5,finals=1,product_links=5),
        this_commission=dict(native_object_compiles=8,dependency_calls=8,host_c_compiles=2,host_c_links=2,
            product_builds=0,product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0),
        limits='Object projection and actual C fixture only. Loader is stubbed; longjmp recovery explicitly supplies the proposed new hook. No integrated product runtime gate or native cold pass.',
        next_proposal='Host-only isolated source integration and object pricing of all writer hooks plus decoder accumulation, preserving this abort ordering; no product build/link/Seed/device.'))
    print('PASS r2: C4554 + scratch-lifetime2421 rows; text626, saving266, margin158; BSS4, margin1; product integration open')

if __name__=='__main__':main()
