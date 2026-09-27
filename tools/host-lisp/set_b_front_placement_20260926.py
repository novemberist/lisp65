"""Read-only placement/lifetime analysis and arithmetic model; no compiler."""
from pathlib import Path
import random
import re
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
from elf_truth import ElfTruth
ROOT=P.ROOT
OUT=ROOT/'build/set-b-front-placement-r1'
LIMIT=60758

def main():
    authority=S.require_auth();OUT.mkdir(exist_ok=False)
    closure_path=ROOT/'build/set-b-r1/step4-r6/closure-r1/compiler-inputs.json'
    closure=P.load(closure_path);assert closure['root_count']==74
    bindings=[r['after'] for r in closure['roots']]+closure['sources']
    for b in bindings:assert P.bind(ROOT/b['path'])==b
    elf=S.PRODUCT/'wplto/resident-island-seed.prg.elf'
    truth=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    manifest_path=ROOT/'build/set-b-seed-medium-r6/media-seed/session-manifest.json'
    m=P.load(manifest_path);assert m['elf']['sha256']==P.bind(elf)['sha256']
    assert len(m['slices'])==63 and m['policy']['payload_alignment']==32
    align=lambda n:(n+31)//32*32
    selected={'.lisp65_rt_c2d_04':96,'.lisp65_rt_c2d_05a':352,
        '.lisp65_rt_c2d_05b':0,'.lisp65_rt_c2append_entries':0,
        '.lisp65_rt_c2append_journal_reconstruct':-10}
    owners=[]
    for name,cap in selected.items():
        sec=truth.section(name);record=next(r for r in m['slices'] if r['section']==name)
        assert sec.bytes==record['file_size'] and record['region_id']==0
        owners.append(dict(section=name,linked_bytes=sec.bytes,region=0,slot=record['id'],
            entry_offset=record['entry_offset'],delta_ceiling=cap,maximum_payload=sec.bytes+cap,
            slice_air_at_ceiling=1792-sec.bytes-cap,aligned_growth=align(sec.bytes+cap)-align(sec.bytes),
            interpretation='Binding ceiling only; not a measured code delta.'))
    growth=sum(r['aligned_growth'] for r in owners)
    assert (m['storage']['size'],growth,65536-m['storage']['size']-growth)==(65045,448,43)
    P.write(OUT/'capacity.json',dict(owners=owners,session_region0_before=65045,
        available=491,proposed_maximum_growth=growth,maximum_used=65493,remaining=43,
        region1=dict(used=m['overflow_storage']['used'],capacity=m['overflow_storage']['capacity']),
        catalog=dict(used=63,limit=64,new_records=0),
        limits='Same-order aligned repack arithmetic only; no image emitted, no CRC or identity invented. Region 3 retains prior control/reset projection. Other owner or padding drift must be charged before admission.'))
    runtime=(ROOT/'src/c2_product_runtime.c').read_text()
    decoder=(ROOT/'config/set-b-native/includes/c2-stream-decoder.c').read_text()
    from set_b_front_integration_r2_20260926 import function
    guard=function(runtime,'c2_append_source_domain_guard')
    phase=function(decoder,'c2_stream_phase_05a')
    cross=function(decoder,'c2_stream_phase_05b')
    assert 'c != &c2aw.append' in guard and 'c2_decode_active != c' in guard
    assert 'c2aw.staged' in guard and 'c2aw.length <= LISP65_C2_SESSION_BYTES - base' in guard
    tail=phase[phase.index('ec = r16(h + 10); lc = r16(h + 12); eo = r16(h + 14);')+len('ec = r16(h + 10); lc = r16(h + 12); eo = r16(h + 14);'):]
    assert not re.search(r'\bh\b',tail)
    assert 'at + length > r16(im + 16)' in phase and '!length' in phase
    for check in ('r16(de + 2) != (uint16_t)(r24(raw + 18) + at)',
        'r16(de + 4) != length','r16(de + 8) != c->generation'):assert check in cross
    rules={
        'src/c2_product_runtime.c':r'entry_cursor|record \+ (12|16)|c2_decode_from|c2_append_source_domain_guard|c2_append_run_stage_plan|raw \+ 18|code = c2aw|code = c2_u24|c2_front',
        'config/set-b-native/includes/c2-stream-decoder.c':r'entry_cursor|ec = r16\(h \+ 10\); lc|at \+ length|r16\(de|c2_stream_phase_05|c2_append_source_domain_guard',
        'config/set-b-native/includes/c2-stream-decoder.h':r'entry_cursor|c2_append_source_domain_guard|reserved|c2_root_cursor',
        'config/set-b-native/linker/c2-substitution.ld':r'ASSERT.*c2d_0[45]|NOCROSSREFS.*c2d_05a',
        'src/c2_bank2_code_domain.h':r'.'}
    witnesses=[]
    for name,pattern in rules.items():
        p=ROOT/name;lines=p.read_text().splitlines()
        witnesses.append(dict(source=P.bind(p),hits=[dict(line=i+1,text=x,context=lines[max(0,i-2):i+3]) for i,x in enumerate(lines) if re.search(pattern,x)]))
    P.write(OUT/'source-witnesses.json',witnesses)
    # Equality of source-derived and directory-derived fronts is conditional
    # on the retained 05b cross-binding and stable transaction-owned bytes.
    raw_path=ROOT/'build/set-b-load-attribution-r1/definitions-0/before-load-c2d.bin'
    raw=raw_path.read_bytes();u=lambda p:int.from_bytes(raw[p:p+2],'little')
    assert (u(12),u(16))==(8,804)
    images=[];entries=[];front=0
    for image in range(8):
        p=48+32*image;base=int.from_bytes(raw[p+18:p+21],'little');first,count=u(p+6),u(p+8)
        image_ends=[]
        for ordinal in range(first,first+count):
            e=2096+10*ordinal;at=u(e+2);length=u(e+4)
            relative=at-base
            assert raw[e]==image and u(e+8)==u(10) and relative>=0
            assert length>0 and relative+length<=u(p+21)
            candidate=base+relative+length
            assert candidate<=LIMIT and candidate==at+length
            image_ends.append(candidate);entries.append(dict(image=image,ordinal=ordinal,
                source_offset_reconstructed=relative,length=length,directory_end=at+length,model_end=candidate))
        front=max([front]+image_ends)
        images.append(dict(image=image,entries=count,first=first,execution_base=base,
            code_length=u(p+21),prefix_max=front))
    assert [images[i]['prefix_max'] for i in (5,6,7)]==[49758,50539,50691]
    P.write(OUT/'captured-front-model.json',dict(images=images,entries=entries,
        limits='Relative source offsets reconstructed from published directory/image data. No immutable Shelf reread or actual phase execution is claimed.'))
    # Every 16-bit absolute start, with boundary lengths; no 2^32 exhaustive claim.
    arithmetic=0
    for base in range(65536):
        room=LIMIT-base
        lengths={0,1,2,65535,max(0,min(65535,room)),max(0,min(65535,room+1))}
        for length in lengths:
            old=bool(length and base<=LIMIT and length<=LIMIT-base)
            new=bool(length and base+length<=LIMIT)
            assert old==new;arithmetic+=1
    assert 0xffffff+0xffffff+65535 < 2**32
    rng=random.Random(20260926);suffix_rows=[]
    for i in range(256):
        old=[rng.randrange(LIMIT+1) for _ in range(rng.randrange(1,20))]
        suffix=[rng.randrange(1,LIMIT+1) for _ in range(rng.randrange(0,20))]
        pending=max(old+suffix)
        assert pending==max(max(old),max(suffix,default=0))
        suffix_rows.append(dict(case=i,old_max=max(old),new_max=pending,empty_suffix=not suffix,
            transient_result=max(old),recovery_certified=False))
    P.write(OUT/'suffix-model.json',suffix_rows)
    controls=[
        dict(name='source coordinate is not execution coordinate',source_base=90000,execution_base=100,length=7,wrong=90007,correct=107),
        dict(name='image end can exceed greatest callable end',image_base=100,image_length=100,entry_offset=0,entry_length=7,wrong=200,correct=107),
        dict(name='initializing before context copy loses scanned old front',scanned_old=500,copied_stale=100,new_end=200,wrong=200,correct=500),
        dict(name='publication before 05b admits mismatched row',source_end=107,directory_end=108,required='05b refuses; no valid certificate'),
        dict(name='later row generation mismatch',generation=1,entry_generation=2,required='05b refuses; no valid certificate'),
        dict(name='abort after partial accumulation',pending=50691,required='invalidate; never undo from pending cursor')]
    for c in controls:
        if 'wrong' in c:assert c['wrong']!=c['correct']
    P.write(OUT/'counterexamples.json',controls)
    budget=277701;read_floor=8*(11*3-3)+4*(11*8-3)
    assert read_floor==580
    P.write(OUT/'receipt.json',dict(status='READ-ONLY PLACEMENT PLAN COMPLETE; CONDITIONAL TWO-OWNER FORM, COSTS UNMEASURED',
        driver=P.bind(Path(__file__)),source_authority=authority,execution_head='9a9789b1',
        compiler_authority=P.bind(closure_path),verified_compiler_roots=74,compiler_inputs=bindings,
        predecessor=P.bind(ROOT/'build/set-b-front-integration-close-r1/receipt.json'),
        elf=P.bind(elf),medium=P.bind(ROOT/'build/set-b-seed-medium-r6/media-seed/set-b-comfort.d81'),
        manifest=P.bind(manifest_path),captured_input=P.bind(raw_path),
        witnesses=P.bind(OUT/'source-witnesses.json'),capacity=P.bind(OUT/'capacity.json'),
        captured_model=P.bind(OUT/'captured-front-model.json'),suffix_model=P.bind(OUT/'suffix-model.json'),
        controls=P.bind(OUT/'counterexamples.json'),arithmetic_boundary_cases=arithmetic,
        captured_entries=804,suffix_cases=256,counterexamples=6,
        proposal=dict(initialize='After successful phase04 source guard, write c2aw.append.entry_cursor from record+12; existing guard has verified c == &c2aw.append. Boot retains phase02 zero.',
            accumulate='Phase05a after existing source-row validation; read 3-byte execution base into dead h[0..2] after ec/lc/eo capture; reuse at for 32-bit end; reject end>60758; update pending maximum. Keep05b exact.',
            storage='No added declared local array/scalar or BSS field; h already24 bytes and at already32 bits. Compiler spills and composed high-water unmeasured.',
            transported_calls_added=0,records_added=0,extra_data_reads_per_image=1,extra_data_bytes_per_image=3,
            entry_slice='Remove prior34-byte initialization insertion; preserve context copy and other body.',
            publication='Pending only. Existing 05b cross-binding, later phases, transaction end and physical success all precede certification. Transient suffix is discarded; recovery invalidates.'),
        cold=dict(conditional_images=8,conditional_entry_visits=804,new_base_calls=8,new_base_bytes=24,
            retained_query_header_calls=4,retained_query_header_bytes=32,
            data_copy_only_instruction_floor=read_floor,margin_cycles=budget,
            ceiling_cycles_per_row_if_all_other_costs_zero=(budget-read_floor)/804,
            max_additional_04_05a_payload_bytes_for_three_decodes=3*448,
            native_cycles=None,native_ms=None,warning='No timing acceptance. Includes neither mapping/reader overhead nor larger overlay CRC/copy/wipe, accumulator, hooks, VM, GC, stack or drift.'),
        cold_predecessor=P.bind(ROOT/'build/set-b-front-certificate-model-r1/receipt.json'),
        reader_floor_authority=P.bind(ROOT/'build/set-b-load-batch-close-r1/receipt.json'),
        remaining=['Exact object deltas and all-owner inventory','Integrated phase/hook/error/fault C fixtures',
            'Additional read fault ordering, exact error successors','Raw/I/O writer-domain binding and stable cross-phase input',
            'Aligned delivery packing and new CRC identities','Native cold/GC/stack/usage gates'],
        consumed=dict(seeds=5,finals=0,product_links=5),authorized_ceiling=dict(seeds=5,finals=1,product_links=5),
        this_commission=dict(native_object_compiles=0,dependency_calls=0,host_c_compiles=0,host_c_links=0,
            product_builds=0,product_links=0,seeds=0,finals=0,guest_runs=0,device_contacts=0,python_model_executions=1),
        product_admitted=False,limits='Source/ELF/manifest audit and Python arithmetic model only. No candidate code generated or compiled. Numerical ceilings are budgets, not measured estimates.',
        next_proposal='One isolated phase04/05a relocation form with matched object and packing gates first; if it fits, execute integrated semantic/fault fixtures. No product build/link/Seed/device.'))
    print('PLAN:04 cap+96,05a cap+352; region0 max65493/65536,43free;',arithmetic,'arithmetic cases;804 captured rows,256 suffix rows,6 controls; zero compiler calls')

if __name__=='__main__':main()
