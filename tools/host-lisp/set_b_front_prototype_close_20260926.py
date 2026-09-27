"""Close the isolated prototype at its measured ordinary-text admission halt."""
from pathlib import Path
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_front_prototype_20260926 as K
import set_b_front_prototype_native_20260926 as N
import set_b_front_prototype_query_20260926 as Q

ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-prototype-close-r1'

def main():
    authority=S.require_auth();OUT.mkdir(exist_ok=False)
    n=P.load(N.OUT/'receipt.json');q=P.load(Q.OUT/'receipt.json')
    assert q['row_count']==4536 and q['partial_transport_rows']==2421
    assert K.HELPER in (N.OUT/'candidate/src/c2_product_runtime.c').read_text()
    assert K.HELPER in (N.OUT/'candidate/generated-product-sources/c2_product_runtime.c').read_text()
    assert K.HELPER in (Q.OUT/'fixture.c').read_text()
    changes=n['changes'];text=sum(r['delta'] for r in changes if r['section'].startswith('.text.'))
    bss=sum(r['delta'] for r in changes if r['section'].startswith('.bss.'))
    expected={'.text.c2_resolver_charged_front':764,'.text.c2_front_boot_reset':4,
        '.text.c2_front_begin':24,'.text.c2_front_abort':9,'.text.c2_front_raw_write':11,
        '.text.c2_front_publish':55,'.text.vm_callprim':25,
        '.bss.c2_front_certificate.0':1,'.bss.c2_front_certificate.1':1,'.bss.c2_front_certificate.2':1,
        '.lisp65_rt_c2append_retire_control':83,'.lisp65_rt_c2append_retire_reset':-3}
    assert {r['section']:r['delta'] for r in changes}==expected
    assert text==892 and bss==3
    for row in P.load(N.OUT/'commands.json'):
        assert row['exit']==row['dependencies']['exit']==0
        for dep in row['dependencies']['inputs']:
            binding=dep['binding'];assert P.bind(ROOT/binding['path'])==binding
    P.write(OUT/'receipt.json',dict(status='HALT: ISOLATED CERTIFICATE KERNEL EXCEEDS ORDINARY-TEXT OBJECT ENVELOPE',
        driver=P.bind(Path(__file__)),authority=authority,execution_head='117e925b',
        prototype=P.bind(K.OUT/'binding.json'),native=P.bind(N.OUT/'receipt.json'),query=P.bind(Q.OUT/'receipt.json'),
        predecessor=P.bind(ROOT/'build/set-b-front-certificate-close-r1/receipt.json'),
        elf=P.bind(S.PRODUCT/'wplto/resident-island-seed.prg.elf'),
        medium=P.bind(ROOT/'build/set-b-seed-medium-r6/media-seed/set-b-comfort.d81'),
        ordinary_text=dict(new_object_bytes=text,available_above_floor=784,shortfall=108,projected_air=-76,floor=32,
            hypothetical_resident_admission=439+text,admitted=False),
        high_BSS=dict(new_object_bytes=bss,projected_air=7,floor=5),
        inherited_prefix=dict(control_delta=83,reset_delta=-3,session_extent=6784,tail=1408,journal=72),
        unchanged_allocated_sections=len(n['unchanged_allocated_sections']),
        remaining=['Actual lifecycle/raw-I/O hooks and write closure','Decoder pending-front accumulation and lifetime',
            'Real INIT invalidation trace and native cold cost','Product collector, stack and exact-error usage successors','Final LTO placement'],
        next_proposal='Host-only read-only lifetime/owner plan for sharing the existing native scanner; require safe resident/overlay dispatch and independent scratch ownership before any implementation or product attempt.',
        consumed=dict(seeds=5,finals=0,product_links=5),authorized_ceiling=dict(seeds=5,finals=1,product_links=5),
        new_product_budget_requested=False,
        this_commission=dict(native_object_compiles=4,dependency_calls=4,host_c_compiles=1,host_c_links=1,
            product_builds=0,product_links=0,seeds=0,finals=0,device_contacts=0,guest_runs=0),
        limits='Non-LTO object projection, not a linked product size. Uninstalled hooks and accumulator are additional unpriced work. Host passing rows qualify only the isolated C protocol.'))
    print('HALT: resident892 > available784 by108; BSS3 fits; isolated C4536 PASS; no integration or product attempt')

if __name__=='__main__':main()
