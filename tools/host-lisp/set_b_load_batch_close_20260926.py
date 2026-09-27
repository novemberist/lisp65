"""Close batch-query price and bind the unchanged reader's copy-loop floor."""
from pathlib import Path
import re
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_load_batch_native_20260926 as N
import set_b_load_preflight_native_r2_20260926 as OLD
from elf_truth import ElfTruth
from set_b_third_seed_inventory_halt_20260926 import instructions, price

ROOT = P.ROOT
OUT = ROOT/'build/set-b-load-batch-close-r1'


def main():
    S.require_auth(); OUT.mkdir(exist_ok=False)
    elf = S.PRODUCT/'wplto/resident-island-seed.prg.elf'
    truth = ElfTruth.read(elf, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    code, command, raw = instructions(elf)
    begin = truth.symbol('__lisp65_c2_map_cpu_hot_begin')
    end = truth.symbol('__lisp65_c2_map_cpu_hot_end')
    by = code[begin.section]
    mapper = truth.symbol('c2_map_cpu_read')
    assert (mapper.value, begin.value, end.value) == (0x2295, 0x2300, 0x2354)
    loop = [0x2303,0x2305,0x2307,0x2309,0x230d,0x230f,
            0x2313,0x2315,0x2317,0x2319,0x231b]
    expected = ['b10e','9106','e60e','d002','e606','d002',
                'c608','f01b','a50f','c960','d0e6']
    assert [by[pc]['bytes'] for pc in loop] == expected
    # Both pointer increments take their shorter no-carry branch. The final
    # byte branches to restore after BEQ; all other bytes execute 3 more ops.
    assert [by[pc]['mnemonic'] for pc in loop] == [
        'lda','sta','inc','bne','inc','bne','dec','beq','lda','cmp','bne']
    final = loop[:8]
    P.write(OUT/'copy-paths.json', dict(nonfinal=[by[pc] for pc in loop],
                                     final=[by[pc] for pc in final],
                                     mapping_range=[by[pc] for pc in by if begin.value<=pc<end.value]))
    timings = ROOT/'build/input-cost-attribution-r6/xemu/xemu/cpu65_mega65_timings.h'
    costs = [int(x) for x in re.search(r'#define TIMINGS_65GS_FAST\s+\{([^}]+)\}', timings.read_text())[1].split(',')]
    assert len(costs) == 256 and min(costs) >= 1
    costs_used = {by[pc]['bytes'][:2]:costs[int(by[pc]['bytes'][:2],16)] for pc in loop}
    old_cost = ROOT/'build/set-b-load-preflight-cost-r1/receipt.json'
    populations = P.load(old_cost)['entry_scan_counts']
    assert populations == [785,801,801,804]
    transports=[]
    for count in populations:
        chunks=[60]*(count//6)+([10*(count%6)] if count%6 else [])
        lengths=[8]+chunks
        transports.append(dict(entries=count,lengths=lengths,calls=len(lengths),
            bytes=sum(lengths),copy_instruction_floor=sum(11*n-3 for n in lengths)))
    P.write(OUT/'INIT-transports.json',transports)
    calls=sum(r['calls'] for r in transports)
    bytes_read=sum(r['bytes'] for r in transports)
    floor=sum(r['copy_instruction_floor'] for r in transports)
    assert (calls,bytes_read,floor)==(537,31942,349751)
    native=P.load(N.OUT/'receipt.json')
    changes={r['section']:r for r in native['changes']}
    assert set(changes)=={'.text.c2_resolver_charged_front','.text.vm_callprim',
        '.lisp65_rt_c2append_retire_control','.lisp65_rt_c2append_retire_reset'}
    resident=changes['.text.c2_resolver_charged_front']['delta']+changes['.text.vm_callprim']['delta']
    assert resident==853
    geometry=price(truth);assert geometry['text_free']==816
    comparisons=[]
    for name in ['lib/stdlib-require.lisp','src/vm.c','src/optional/set_b_retire_control.c','src/optional/set_b_retire_reset.c']:
        a=OLD.OUT/'candidate'/name;b=N.OUT/'candidate'/name
        assert a.read_bytes()==b.read_bytes(),name
        comparisons.append(dict(before=P.bind(a),candidate=P.bind(b),byte_identical=True))
    a=OLD.OUT/'candidate/src/c2_product_runtime.c';b=N.OUT/'candidate/src/c2_product_runtime.c'
    assert a.read_text().replace(OLD.HELPER,N.HELPER)==b.read_text()
    deps=P.load(N.OUT/'commands.json');input_changes={}
    for unit in ('c2_product_runtime.c','vm.c'):
        worlds={r['world']:{d['logical']:d['binding']['sha256'] for d in r['dependencies']['inputs']} for r in deps if r['unit']==unit}
        assert worlds['before'].keys()==worlds['candidate'].keys()
        input_changes[unit]=[k for k in worlds['before'] if worlds['before'][k]!=worlds['candidate'][k]]
    assert set(input_changes['c2_product_runtime.c'])=={'generated/c2_product_runtime.c','generated/optional/set_b_retire_reset.c','generated/optional/set_b_retire_control.c'}
    assert input_changes['vm.c']==['generated/vm.c']
    stack=[]
    for name,folder,want in [('scalar',OLD.OUT,17),('batch',N.OUT,68)]:
        obj=folder/'candidate/c2_product_runtime.c.o'
        t=ElfTruth.read(obj,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
        ins,_,_=instructions(obj);section='.text.c2_resolver_charged_front';rows=ins[section]
        rel={r.offset:r for r in t.relocations if r.source_section==section}
        assert [rel[n].target for n in (2,6,8,12)]==['__rc0','__rc0','__rc1','__rc1']
        assert rows[0]['mnemonic']=='clc' and rows[3]['mnemonic']==rows[9]['mnemonic']=='adc'
        lo=bytes.fromhex(rows[3]['bytes'])[1];hi=bytes.fromhex(rows[9]['bytes'])[1]
        frame=65536-(lo+256*hi);assert frame==want
        stack.append(dict(form=name,object=P.bind(obj),software_frame=frame,
                          prefix=[rows[pc] for pc in rows if pc<=0x18]))
    P.write(OUT/'stack-objects.json',stack)
    proof=ROOT/'build/set-b-load-batch-query-r1/receipt.json';q=P.load(proof)
    assert q['status'].startswith('PASS:') and q['row_count']==2725
    reused=[ROOT/'build/set-b-load-preflight-native-pack-r1/receipt.json',
            ROOT/'build/set-b-load-preflight-native-cl-r1/receipt.json']
    for p in reused:assert P.load(p)['status'].startswith('PASS:')
    P.write(OUT/'receipt.json',dict(status='HALT: BATCH QUERY EXCEEDS OBJECT AIR AND UNCHANGED-READER COPY COST',
        driver=P.bind(Path(__file__)),source_authority=S.require_auth(),execution_head='d8719dc4',
        elf=P.bind(elf),native=P.bind(N.OUT/'receipt.json'),patch=P.bind(N.OUT/'authored.patch'),
        semantic_proof=P.bind(proof),prior_cost=P.bind(old_cost),reused_receipts=[P.bind(p) for p in reused],
        byte_identity_comparisons=comparisons,compiler_input_differences=input_changes,
        copy_paths=P.bind(OUT/'copy-paths.json'),timing_table=P.bind(timings),opcode_base_costs=costs_used,
        transport_rows=P.bind(OUT/'INIT-transports.json'),reader_calls=calls,reader_bytes=bytes_read,
        copy_instruction_floor=floor,copy_cycles_at_one_cycle_per_instruction=floor,
        copy_ms_at_40_5MHz=floor/40500,cold_margin_cycles=277701,cold_margin_ms=277701/40500,
        timing_scope='Bound existing ELF byte-copy loop for proposed lengths. Ignores setup, mapping, carry/crossing work, row validation, VM, GC and offsetting product changes. No new native runtime or LTO layout claim.',
        air=dict(resident_query=828,vm_dispatch=25,resident_increment=resident,
            text_before=816,text_projection=816-resident,text_floor=32,shortfall_to_floor=69,
            hypothetical_resident_admission=439+resident,other_allocated_sections_identical=len(native['unchanged_allocated_sections']),
            e000_before=115,e000_floor=54,capture_before=105,capture_floor=57,high_bss_before=10,high_bss_floor=5,
            control_object_delta=83,reset_object_delta=-3,control_record=480,reset_record=256,tenant_extent=6784,tenant_tail=1408),
        scratch=dict(automatic_buffer=60,buffer_frame_offset=8,software_frame=68,scalar_frame=17,
            hardware_saved_registers=4,read_limit=64,callee_lifetime='Synchronous reader; no escape, overlay/window pointer or allocation across scan; buffer dead before cons.',
            linked_stack_top=truth.symbol('__stack').value,
            runtime_reservation=truth.symbol('__lisp65_workbench_required_runtime_stack').value,
            boot_reservation=truth.symbol('__lisp65_workbench_required_boot_stack').value,
            limitation='Local frame priced only; complete caller/callee stack high-water and unmapped destination must pass a later linked gate. No new linked-stack safety claim.'),
        this_commission=dict(product_builds=0,product_links=0,seeds=0,finals=0,device_contacts=0,guest_launches=0,
            native_object_compiles=4,dependency_calls=4,host_c_compiles=1,host_c_links=1,canonical_lisp_compilations=0,SBCL_executions=0),
        consumed=dict(seeds=5,finals=0,product_links=5),additional_product_budget_requested=False,
        next_proposal='Host-only design of fewer complete scans using a precisely invalidated validation certificate; first prove coverage of every writer, refusal, retirement and reset before code or a Seed. If no proof fits, return to owner with the quantified gate conflict; do not silently weaken validation or cold bounds.'))
    print('HALT: text projection',816-resident,'floor32; copy floor',floor,'cycles',floor/40500,'ms; frame68; 2725 host rows PASS')


if __name__=='__main__':
    main()
