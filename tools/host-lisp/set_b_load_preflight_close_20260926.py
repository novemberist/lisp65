"""Close both repair projections; retain the unresolved native cold gate."""
from collections import deque
from pathlib import Path
import re
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
from elf_truth import ElfTruth
from set_b_third_seed_inventory_halt_20260926 import instructions
ROOT=P.ROOT
OUT=ROOT/'build/set-b-load-preflight-close-r1'

def main():
    S.require_auth();OUT.mkdir(exist_ok=False)
    native=ROOT/'build/set-b-load-preflight-native-r2';obj=native/'candidate/c2_product_runtime.c.o'
    t=ElfTruth.read(obj,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj');section='.text.c2_resolver_charged_front'
    code,command,raw=instructions(obj);by=code[section]
    rel={r.offset:r for r in t.relocations if r.source_section==section}
    def successors(pc):
        row=by[pc];mn=row['mnemonic'];nxt=pc+len(bytes.fromhex(row['bytes']))
        if mn=='rts':return []
        if mn=='jmp':
            r=rel[pc+1];assert r.target==section,(pc,r)
            return [r.addend]
        if mn.startswith('b') and mn not in ('bit','brk'):
            target=int(re.search(r'\$([0-9a-f]+)',row['operand'])[1],16);return [nxt,target]
        return [nxt]
    # Row loop begins at 105 (arguments to the row reader) and finishes at
    # 24a (backedge to the counter test at fc). Bind both through opcodes and
    # the actual relocation; all alternative branches are allowed in BFS,
    # giving a lower bound even if their predicates cannot coexist.
    assert by[0x105]['mnemonic']=='ldx' and by[0x125]['mnemonic']=='jsr'
    assert rel[0x126].target=='c2_stream_c2d_read'
    assert by[0x24a]['mnemonic']=='jmp' and rel[0x24b].target==section and rel[0x24b].addend==0xfc
    queue=deque([(0x105,[])]);seen=set();path=None
    while queue:
        pc,prior=queue.popleft()
        if pc in seen:continue
        seen.add(pc);here=prior+[pc]
        if pc==0x24a:path=here;break
        for nxt in successors(pc):
            if nxt in by:queue.append((nxt,here))
    assert path and 0x125 in path
    P.write(OUT/'shortest-object-row-path.json',[by[x] for x in path])
    cost=P.load(ROOT/'build/set-b-load-preflight-cost-r1/receipt.json');count=sum(cost['entry_scan_counts'])
    np=P.load(native/'receipt.json');text=sum(r['delta'] for r in np['changes'] if r['section'].startswith('.text.'))
    assert text==687
    allowed={'.text.c2_resolver_charged_front','.text.vm_callprim','.lisp65_rt_c2append_retire_control','.lisp65_rt_c2append_retire_reset'}
    assert {r['section'] for r in np['changes']}==allowed
    changes={}
    commands=P.load(native/'commands.json')
    for unit in ('c2_product_runtime.c','vm.c'):
        rows={r['world']:{d['logical']:d['binding']['sha256'] for d in r['dependencies']['inputs']} for r in commands if r['unit']==unit}
        assert rows['before'].keys()==rows['candidate'].keys()
        changes[unit]=[k for k in rows['before'] if rows['before'][k]!=rows['candidate'][k]]
    assert set(changes['c2_product_runtime.c'])=={'generated/c2_product_runtime.c','generated/optional/set_b_retire_control.c','generated/optional/set_b_retire_reset.c'}
    assert changes['vm.c']==['generated/vm.c']
    receipts=[ROOT/'build'/p/'receipt.json' for p in ['set-b-load-preflight-pack-r1','set-b-load-preflight-cl-r1','set-b-load-preflight-native-pack-r1','set-b-load-preflight-native-cl-r1','set-b-load-preflight-query-r1']]
    for p in receipts:assert P.load(p)['status'].startswith('PASS:')
    old=P.load(ROOT/'build/set-b-load-preflight-cl-r1/rows.json');new=P.load(ROOT/'build/set-b-load-preflight-native-cl-r1/rows.json')
    assert [r[:4] for r in old if r[0]=='ROW']==[r[:4] for r in new if r[0]=='ROW']
    extent,tenants=P.late_partition();assert extent==6752
    projected_control=378+83;record=((projected_control+31)//32)*32;extra=record-tenants[1]['offset']
    P.write(OUT/'receipt.json',dict(status='HOST PREFLIGHT CLOSED; NATIVE COLD COST REMAINS AN ADMISSION HALT',driver=P.bind(Path(__file__)),authority=S.require_auth(),execution_head='519a1be2',proofs=[P.bind(p) for p in receipts],
        full_lisp_scan=P.bind(ROOT/'build/set-b-load-preflight-cost-r1/receipt.json'),native_object=P.bind(obj),native_proposal=P.bind(native/'receipt.json'),native_patch=P.bind(native/'authored.patch'),
        compiler_input_differences=changes,object_shortest_successful_row_instructions=len(path),row_executions_at_INIT=count,
        gross_object_instruction_floor=len(path)*count,gross_object_floor_ms=len(path)*count/40500,
        existing_margin_cycles=277701,object_projection_exceeds_margin=len(path)*count>277701,
        timing_limit='Non-LTO object instruction floor, not a bound on a not-built LTO product. Excludes reader/caller/GC costs and offsetting layout effects. No claim of cold acceptance or exact native runtime.',
        air=dict(resident_increment=text,existing_resident_admission=439,proposed_total_resident=439+text,text_before=816,text_projection=816-text,text_floor=32,e000_before=115,e000_floor=54,capture_before=105,capture_floor=57,no_object_delta_other_allocated_sections=len(np['unchanged_allocated_sections']),tenant_extent=extent+extra,tenant_tail=8192-extent-extra,control_record=record,reset_record=extent-tenants[-1]['offset']),
        delivery_rule='All tenant offsets after control shift by32; old fixed total8192 and journal remain. Fresh native tuple/catalog/Shelf CRCs require a later admitted product; no invented CRC values.',
        consumed=dict(seeds=5,finals=0,product_links=5),additional_product_budget_requested=False,
        this_commission=dict(product_builds=0,product_links=0,seeds=0,device_contacts=0,guest_launches=0,observer_builds=0,native_object_compiles=8,dependency_calls=8,canonical_lisp_compilations=4,host_C_compiles=1,host_C_links=1,SBCL_executions=2,discarded_reference_VM_attempts=3),
        next_step='Reduce query work/transport with a bounded batch form or another proved equivalence; price scratch/stack lifetime and preserve generation, size, code-domain, tombstone and failure checks. No last-entry shortcut, skipped roots or cold-bound waiver.'))
    print('CLOSED; object row floor',len(path),'instructions;',len(path)*count,'cycles vs margin277701; text projection',816-text)
if __name__=='__main__':main()
