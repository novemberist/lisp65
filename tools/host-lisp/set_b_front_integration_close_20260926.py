"""Close the isolated integration at its measured overlay-envelope halt."""
from pathlib import Path
from dataclasses import asdict
import re
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_front_integration_r2_20260926 as I
import set_b_shared_front_r2_20260926 as K
from elf_truth import ElfTruth
from set_b_third_seed_inventory_halt_20260926 import price
ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-integration-close-r1'
NATIVE=ROOT/'build/set-b-front-integration-native-r1'

def main():
    authority=S.require_auth();OUT.mkdir(exist_ok=False)
    inputs=ROOT/'build/set-b-r1/step4-r6/closure-r1/compiler-inputs.json'
    closure=P.load(inputs);assert closure['root_count']==74
    bindings=[r['after'] for r in closure['roots']]+closure['sources']
    for b in bindings:assert P.bind(ROOT/b['path'])==b,b['path']
    r=P.load(NATIVE/'receipt.json');commands=P.load(NATIVE/'commands.json')
    assert len(commands)==6
    for row in commands:
        assert row['exit']==row['dependencies']['exit']==0
        for key in ('log','object'):assert P.bind(ROOT/row[key]['path'])==row[key]
        for d in row['dependencies']['inputs']:
            b=d['binding'];assert P.bind(ROOT/b['path'])==b
    changes={x['section']:x for x in r['changes']}
    assert (r['ordinary_text_delta'],r['high_bss_delta'])==(726,4)
    expected={'.lisp65_c2_kernal_window.c2_resident':36,
        '.lisp65_rt_c2append_entries':34,'.lisp65_rt_c2append_journal_reconstruct':-10,
        '.lisp65_rt_c2append_retire_control':83,'.lisp65_rt_c2append_retire_reset':-3,
        '.lisp65_rt_c2d_05b':270,'.rodata.vm_callprim':0}
    for n,d in expected.items():assert changes[n]['delta']==d
    for n in changes:assert n in expected or n.startswith(('.text.','.bss.c2_front_certificate.'))
    assert ['c2_product_runtime.c','.lisp65_rt_c2append_reserve_persistent_code'] in r['unchanged_allocated_sections']
    elf=S.PRODUCT/'wplto/resident-island-seed.prg.elf'
    t=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    geometry=price(t);assert (geometry['text_free'],geometry['high_bss_free'],geometry['e000_free'])==(816,10,115)
    owners=[]
    for n in expected:
        if n.startswith('.rodata.'):continue
        c=changes[n];s=t.section(n);projected=s.bytes+c['delta']
        owners.append(dict(section=n,object_before=c['before'],object_after=c['after'],delta=c['delta'],
            linked_before=asdict(s),projected=projected,
            limit=1792 if n.startswith('.lisp65_rt_') else None,
            projected_air=1792-projected if n.startswith('.lisp65_rt_') else None))
    failing=[x for x in owners if x['limit'] and x['projected_air']<0]
    assert [(x['section'],x['projected_air']) for x in failing]==[
        ('.lisp65_rt_c2append_entries',-13),('.lisp65_rt_c2d_05b',-133)]
    before=(ROOT/'src/c2_product_runtime.c').read_text()
    after=(I.OUT/'candidate/src/c2_product_runtime.c').read_text()
    source_rows=[]
    def check(name,condition):
        assert condition,name;source_rows.append(dict(check=name,pass_source_assertion=True))
    check('certificate helper unchanged from prior r2 C proof',K.HELPER in after)
    check('no new READY clearing operation',len(re.findall(r'c2_ready\s*=\s*0\b',before))==len(re.findall(r'c2_ready\s*=\s*0\b',after)))
    check('existing exact BADOPCODE assignments retained',before.count('vm_status = VM_BADOPCODE')==after.count('vm_status = VM_BADOPCODE'))
    check('reconstructed cursor not used as undo', 'w->append.entry_cursor = c2_runtime.entry_cursor;' not in after and 'w->append.entry_cursor = 0u;' in after)
    check('append pending max seeded from scanned low','w->append.entry_cursor = c2_u16(w->record + 12);' in after)
    check('transient pending max discarded for persistent certificate','if (transient) c2_runtime.entry_cursor = c2_u16(c2aw.record + 12);' in after)
    rec=I.function(after,'c2_product_abort_recover')
    check('recovery invalidates before retirement/release',rec.index('c2_front_abort();')<rec.index('c2_retire_run('))
    marker='c2_front_abort();\n    if (vm_runtime_overlay_abort_cleanup()'
    check('interrupt cleanup invalidates before loader cleanup',marker in after)
    staged=I.function(after,'c2_product_append_staged_result')
    check('staged result publishes after transaction end',staged.index('vm_runtime_overlay_transaction_end()')<staged.index('c2_front_publish('))
    install=I.function(after,'c2_product_install')
    pub=[m.start() for m in re.finditer('\\(void\\)c2_front_publish',install)]
    check('install has persistent and transient terminal publications',len(pub)==2 and all('vm_runtime_overlay_transaction_end()' in install[:p] for p in pub))
    vm=(I.OUT/'candidate/src/vm.c').read_text()
    check('poke store bracketed by raw notification',bool(re.search(r'c2_front_raw_write\(\);\s*\*\(volatile unsigned char \*\)\(uintptr_t\)address = \(unsigned char\)FIXVAL\(a\[2\]\);\s*c2_front_raw_write\(\);',vm)))
    P.write(OUT/'source-order-checks.json',dict(rows=source_rows,scope='Source assertions only, not executed lifecycle or exhaustive writer/raw-I/O proof.'))
    P.write(OUT/'owner-prices.json',dict(owners=owners,changed_sections=r['changes'],unchanged_sections=r['unchanged_allocated_sections'],linked_geometry=geometry))
    P.write(OUT/'receipt.json',dict(status='HALT: TWO OVERLAY OWNER ENVELOPES FAIL BEFORE INTEGRATED C QUALIFICATION',
        driver=P.bind(Path(__file__)),source_authority=authority,execution_head='6fcd8207',
        compiler_authority=P.bind(inputs),verified_compiler_roots=74,compiler_inputs=bindings,
        sources=P.bind(I.OUT/'binding.json'),native=P.bind(NATIVE/'receipt.json'),
        source_checks=P.bind(OUT/'source-order-checks.json'),owner_prices=P.bind(OUT/'owner-prices.json'),
        elf=P.bind(elf),medium=P.bind(ROOT/'build/set-b-seed-medium-r6/media-seed/set-b-comfort.d81'),
        predecessor=P.bind(ROOT/'build/set-b-shared-front-close-r1/receipt.json'),
        ordinary_text=dict(new=726,previous=626,integration_delta=100,projected_air=90,floor=32,remaining=58),
        high_BSS=dict(new=4,projected_air=6,floor=5,remaining=1),
        e000=dict(new=36,projected_air=79,floor=54,remaining=25),
        capture=dict(new=0,projected_air=105,floor=57,remaining=48),
        failing_owners=failing,scanner=dict(changed=False,record=1743,limit=1792,air=49),
        selected_revision=None,product_admitted=False,
        consumed=dict(seeds=5,finals=0,product_links=5),authorized_ceiling=dict(seeds=5,finals=1,product_links=5),
        this_commission=dict(native_object_compiles=6,dependency_calls=6,host_c_compiles=0,host_c_links=0,
            product_builds=0,product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0),
        limits='Matched non-LTO projections, not linked product sizes. Only source-order assertions ran; no integrated C semantic fixture, complete writer/raw-I/O closure, cold-time, stack, GC or product-error gate. Existing r2 helper proof is not qualification of these new callers.',
        next_proposal='Host-only read-only ownership/lifetime and capacity plan for moving or sharing the max accumulation and append initialization; prove transfer/call/scratch costs and preserve exact range/error checks before another isolated form. No product build/link/Seed/device.'))
    print('HALT decoder projected1925/1792 (-133), entries1805/1792 (-13); text margin58, BSS margin1, E000 margin25;',len(source_rows),'source assertions')

if __name__=='__main__':main()
