#!/usr/bin/env python3
"""Derive the fixed-resident function and CALLPRIM population from final ELF.

Shared dispatch body ranges stay shared. Counts are observations, never a
claim that a zero-count function is dead or safe to move to an overlay.
"""
import json
import re
import subprocess
from collections import defaultdict

from capacity_pc_histogram_tool import ROOT, OUT, ELF, ELF_SHA, bind
from elf_truth import ElfTruth
from evidence_era import stable_recorded_on
import capacity_prefilter_media as MEDIA

def main():
    assert bind(ELF)['sha256'] == ELF_SHA
    truth = ElfTruth.read(ELF, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj', include_section_data=True)
    sec = truth.section('.text'); raw = truth.section_bytes('.text')
    functions = [s for s in truth.symbols if s.section == '.text' and s.symbol_type == 'Function' and s.bytes]
    assert functions
    counts = defaultdict(int); dispatch = defaultdict(int); mismatches = []; traces = []
    inputs=[]
    for group in ('native', 'recursion-known-issue', 'printer-known-issue'):
        receipt = OUT/'observed/r2'/group/'receipt.json'
        record = json.loads(receipt.read_text())
        assert record['error'] is None and all(r['passed'] for r in record['rows'])
        inputs.append((receipt,record['rows'][-1]['histogram'],dict(group=group)))
    for row in MEDIA.check()['rows']:
        receipt=OUT/'mirrored/r2/observed'/row['id']/'receipt.json'
        record=json.loads(receipt.read_text())
        assert record['status']=='PASS' and record['row']==row and record['observer']
        assert not record['historical_results_inherited'] and not record['comfort_entry']
        inputs.append((receipt,record['histogram'],dict(row=row)))
    for receipt,histogram,context in inputs:
        trace=ROOT/histogram['path']
        assert bind(trace)['sha256']==histogram['sha256']
        traces.append(dict(receipt=bind(receipt),trace=bind(trace),**context))
        for line in trace.read_text().splitlines():
            words = line.split()
            if words[0] == 'D': dispatch[int(words[1])] += int(words[2])
            elif words[0] == 'P':
                pc, count, opcode, changed = map(int, words[1:])
                if sec.address <= pc < sec.address+sec.bytes:
                    if changed or raw[pc-sec.address] != opcode: mismatches.append(dict(pc=pc, opcode=opcode, changed=changed))
                    counts[pc] += count
    assert not mismatches, ('resident code changed or wrong identity', mismatches[:10])
    residual=[]
    for pc,count in sorted(counts.items()):
        owners=[s for s in functions if s.value<=pc<s.value+s.bytes]
        assert len({(s.value,s.bytes) for s in owners})<=1,('partially overlapping function owners',pc,[s.name for s in owners])
        if count and not owners:
            labels=[s for s in truth.symbols if s.section=='.text' and s.value<=pc]
            nearest=max((s.value for s in labels),default=None)
            residual.append(dict(pc=pc,instructions=count,nearest_labels=[s.name for s in labels if s.value==nearest]))
    rows = [dict(name=s.name, address=s.value, bytes=s.bytes,
        instructions=sum(counts[a] for a in range(s.value,s.value+s.bytes)),
        observed_pcs=sum(counts[a]>0 for a in range(s.value,s.value+s.bytes))) for s in functions]
    physical=[]
    for address,size in sorted({(s.value,s.bytes) for s in functions}):
        physical.append(dict(address=address,bytes=size,aliases=[s.name for s in functions if (s.value,s.bytes)==(address,size)],
            instructions=sum(counts[a] for a in range(address,address+size))))
    disasm = subprocess.check_output([str(ROOT/'tools/llvm-mos/bin/llvm-objdump'), '-d',
        '--disassemble-symbols=vm_callprim', str(ELF)], text=True)
    instructions = {}
    for line in disasm.splitlines():
        match = re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+)+)\s*(\w+)\s*(.*)', line)
        if match:
            address = int(match[1],16); code = bytes.fromhex(match[2])
            instructions[address] = (code, match[3], match[4])
    vm = truth.symbol('vm_callprim')
    tables = [(a,int.from_bytes(code[1:3],'little')) for a,(code,mn,op) in instructions.items()
              if code[0] == 0x7c and vm.value <= a < vm.value+128]
    assert tables, 'dispatch-table entrance absent'
    jump, table = min(tables)
    limits = [(a,code[1]) for a,(code,mn,op) in instructions.items() if code[0]==0xc9 and a<jump]
    assert len(limits)==1, 'PID bound absent/ambiguous'
    limit = limits[0][1]
    # Verify the sampled entry A really survives as the dispatch PID. This is
    # a symbolic trace of the emitted prologue, not an ABI assumption by name.
    a='PID';x='X';y='Y';stack=[];memory={};pc=vm.value;visited=set()
    while pc!=jump:
        assert pc not in visited,'prologue cycle';visited.add(pc)
        code,mn,op=instructions[pc];nxt=pc+len(code);opcode=code[0]
        if opcode==0x48:stack.append(a)
        elif opcode==0x68:a=stack.pop()
        elif opcode==0x5a:stack.append(y)
        elif opcode==0xa5:a=memory.get(code[1],('memory',code[1]))
        elif opcode==0xa4:y=memory.get(code[1],('memory',code[1]))
        elif opcode==0xa6:x=memory.get(code[1],('memory',code[1]))
        elif opcode==0xa0:y=code[1]
        elif opcode==0x85:memory[code[1]]=a
        elif opcode==0x86:memory[code[1]]=x
        elif opcode==0x69:a=('sum',a,code[1])
        elif opcode==0x0a:a=('twice',a)
        elif opcode==0xaa:x=a
        elif opcode==0x88:y=('minus-one',y)
        elif opcode in (0x18,0x91):pass
        elif opcode==0xc9:assert a=='PID' and code[1]==limit
        elif opcode==0x90:nxt+=int.from_bytes(code[1:],'little',signed=True)
        else:raise AssertionError(('unresolved dispatch prologue',hex(pc),code.hex()))
        pc=nxt
    assert a=='PID' and x==('twice','PID'),'entry PID does not select table index'
    sections = [s for s in truth.sections if s.address <= table and table+limit*2<=s.address+s.bytes and 'SHF_ALLOC' in s.flags]
    assert len(sections)==1, 'jump-table byte owner absent/ambiguous'
    table_bytes = truth.section_bytes(sections[0].name)[table-sections[0].address:table-sections[0].address+limit*2]
    entries = {pid:int.from_bytes(table_bytes[pid*2:pid*2+2],'little') for pid in range(limit)}
    def pointer(table_address, index):
        address = table_address+index*2
        owners=[s for s in truth.sections if s.address<=address and address+2<=s.address+s.bytes and 'SHF_ALLOC' in s.flags]
        assert len(owners)==1, 'nested table owner absent/ambiguous'
        data=truth.section_bytes(owners[0].name)
        return int.from_bytes(data[address-owners[0].address:address-owners[0].address+2],'little')
    def nested_targets(pid, entry, pc, code):
        before = raw[max(0,pc-sec.address-16):pc-sec.address]
        table_address = int.from_bytes(code[1:3],'little')
        # Shared zero-argument primitive block: preserve PID in A, then
        # CLC / ADC #offset / ASL / TAX. All prefix instructions are checked.
        prefix=raw[entry-sec.address:pc-sec.address]
        if len(prefix)==12 and prefix[:4]==bytes.fromhex('a6 18 f0 03') and prefix[4]==0x4c and prefix[7:9]==bytes.fromhex('18 69') and prefix[-2:]==bytes.fromhex('0a aa'):
            return [pointer(table_address, (pid+prefix[9]) & 255)]
        # Arity dispatch: LDA nargs / CMP #bound / BCC +3 / JMP fail /
        # ASL / TAX. Enumerate every admitted arity, not just observed ones.
        p=before[-11:]
        if len(p)==11 and p[:3]==bytes.fromhex('a5 18 c9') and p[4:7]==bytes.fromhex('90 03 4c') and p[-2:]==bytes.fromhex('0a aa'):
            return [pointer(table_address,n) for n in range(p[3])]
        return None
    primitive_rows = []; unresolved = []
    for pid, entry in entries.items():
        pending=[entry]; body=set(); exits=set()
        while pending:
            pc=pending.pop()
            if pc in body: continue
            if not vm.value <= pc < vm.value+vm.bytes: exits.add(pc); continue
            if pc not in instructions: unresolved.append(dict(pid=pid,pc=pc,reason='missing instruction')); continue
            body.add(pc); code,mn,op=instructions[pc]; nxt=pc+len(code)
            if mn in ('rts','rti','brk'): continue
            if mn=='jmp':
                if code[0]!=0x4c:
                    targets=nested_targets(pid,entry,pc,code) if code[0]==0x7c else None
                    if targets is None: unresolved.append(dict(pid=pid,pc=pc,reason='indirect branch in body'))
                    else: pending.extend(targets)
                else: pending.append(int.from_bytes(code[1:3],'little'))
            elif mn in ('bcc','bcs','beq','bne','bmi','bpl','bvc','bvs','bra'):
                pending.append(nxt+int.from_bytes(code[-1:],'little',signed=True))
                if mn!='bra': pending.append(nxt)
            else: pending.append(nxt)
        primitive_rows.append(dict(pid=pid, entry=entry, entries_observed=dispatch[pid],
            body_pcs=sorted(body), body_bytes=sum(len(instructions[a][0]) for a in body),
            observed_body_instructions=sum(counts[a] for a in body), exits=sorted(exits)))
    assert not unresolved,unresolved
    assert all(pid<limit for pid,count in dispatch.items() if count),'out-of-population observed primitive'
    result = dict(recorded_on=stable_recorded_on(OUT/'population.json'),
        status='POPULATION DERIVED; QUALIFICATION IN CARD0 RECEIPT',
        product=bind(ELF), traces=traces, scope='fixed resident .text; dynamic overlay lifetimes excluded',
        functions=rows, function_count=len(rows),
        text_section_bytes=sec.bytes,function_symbol_bytes=sum(s.bytes for s in functions),
        physical_function_ranges=physical,physical_function_bytes=sum(r['bytes'] for r in physical),
        executed_without_sized_function=residual,
        not_observed=[r['name'] for r in rows if not r['instructions']],
        callprim=dict(address=vm.value,bytes=vm.bytes,table=table,limit=limit,entries=primitive_rows,unresolved=unresolved,
            sampled_A_is_PID=True,prologue_pcs=sorted(visited)),
        limits=['not observed on these rows is not unused or movable',
            'shared dispatch body counts cannot be charged exclusively to one PID',
            'identical-address Function aliases share one physical range; symbol sizes are not additive capacity',
            'expected-failure rows are not successful-use coverage',
            'startup/assembly PCs without sized Function symbols are separately listed, not priced as cold functions',
            'no physical keyboard, wall-clock, hardware or window-lifetime claim'])
    (OUT/'population.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(functions=len(rows),not_observed=len(result['not_observed']),pid_entries=limit,unresolved=len(unresolved))))

if __name__ == '__main__': main()
