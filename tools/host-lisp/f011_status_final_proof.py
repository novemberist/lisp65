#!/usr/bin/env python3
"""Read-only emitted witness/error-edge and owner checks for the F011 card."""
from collections import deque
import json
import re
import subprocess
import f011_status_product_card as C
from elf_truth import ElfTruth
from cpu6502 import CPU
import c2_v200_symbol22_first_fault_product_card as LATCH
import block_26_f011_map_abort_repair_product_card as F011
from evidence_era import stable_recorded_on

OUT=C.BUILD/'final-proof.json'

def raw(t,name):
    s=t.symbol(name); sec=t.section(s.section)
    return t.section_bytes(sec.name)[s.value-sec.address:s.value-sec.address+s.bytes]

def observer(t):
    fn=t.symbol('f011_status_observe'); state=t.symbol('lisp65_f011_status_state')
    sec=t.section(fn.section)
    records=[]
    for before in range(5):
        for tag in range(1,5):
            m=CPU(); data=t.section_bytes(sec.name)
            m.mem[sec.address:sec.address+len(data)]=data
            m.mem[state.value:state.value+3]=bytes((before,0x33,0x44))
            m.mem[0xd083]=0x59; m.A=tag; m.X=0x63
            m.push16(0x0400-1); m.PC=fn.value
            writes=[]; reads=[]
            original_write=m.wr; original_read=m.rd
            def write(a,v):
                if state.value<=a<state.value+3:writes.append([a-state.value,v])
                original_write(a,v)
            def read(a):
                if 0xd080<=a<=0xd089: reads.append(a)
                return original_read(a)
            m.wr=write; m.rd=read
            steps=0
            while m.PC!=0x400 and steps<100:
                m.step(); steps+=1
            C.require(m.PC==0x400,'emitted observer did not return')
            commits=before==0 or (before==1 and tag>1)
            expected=bytes((tag,0x63,0x59)) if commits else bytes((before,0x33,0x44))
            got=bytes(m.mem[state.value:state.value+3])
            C.require(got==expected and reads==([0xd083] if commits else []),'emitted record transition/IO differs')
            C.require(not commits or writes==[[1,0x63],[2,0x59],[0,tag]],'tag not published last')
            records.append({'prior_tag':before,'incoming_tag':tag,'record':got.hex(),'steps':steps,'writes':writes,'status_reads':reads})
    return {'cases':records,'final_body_hex':raw(t,fn.name).hex(),'status':'PASS'}

def error_edges(t):
    text=t.section('.text'); data=t.section_bytes('.text')
    abort=t.symbol('lisp_abort_code').value
    edges=[]
    for r in t.relocations:
        if r.source_section!='.text' or r.target!='io_disk_read_sector':continue
        pc=r.offset-1
        if data[pc-text.address]!=0x20:continue
        m=CPU();m.mem[text.address:text.address+len(data)]=data
        m.A=0; m.PC=pc+3
        path=[]
        for _ in range(30):
            if m.PC==abort: break
            path.append(m.PC);m.step()
        C.require(m.PC==abort and m.A==0x12,'failed sector did not reach LOAD_OPEN from ordinary text')
        edges.append({'read_call':pc,'failure_path':path,'abort':abort,'error':m.A})
    C.require(len(edges)==2,'final ordinary read caller population changed')
    return edges

def boot_reset(t):
    fn=t.symbol('main');sec=t.section(fn.section);state=t.symbol('lisp65_f011_status_state')
    def execute(mutant=False):
        class BootCPU(CPU):
            # This prologue uses two documented 65C02 instructions absent
            # from the small NMOS helper core. Decode exactly these bytes;
            # no instruction is skipped and all other opcodes fail normally.
            def step(self):
                op=self.rd(self.PC)
                if op==0xda:
                    self.fetch();self.push(self.X)
                elif op==0x9c:
                    self.fetch();self.wr(self.fetch16(),0)
                else:super().step()
        m=BootCPU(); data=t.section_bytes(sec.name)
        m.mem[sec.address:sec.address+len(data)]=data
        m.mem[state.value]=0xa5;m.PC=fn.value
        m.mem[2:4]=(0xb900).to_bytes(2,'little')
        writes=[]
        for step in range(100):
            if m.mem[m.PC]==0x20:break
            if m.mem[m.PC:m.PC+3]==bytes((0x9c,state.value&255,state.value>>8)):
                writes.append(m.PC)
                if mutant:m.mem[m.PC:m.PC+3]=b'\xea\xea\xea'
            m.step()
        else:raise RuntimeError('boot reset did not reach first call')
        return m.mem[state.value],writes,m.PC
    value,writes,cut=execute()
    C.require(value==0 and len(writes)==1,'record tag not reset before first main call')
    C.require(execute(True)[0]==0xa5,'removed boot reset mutation survived')
    return {'tag_before':0xa5,'tag_after':value,'reset_store':writes[0],
            'first_call_cutpoint':cut,'removed_reset_rejected':True}

def survival(t, record_bytes=3, publisher='f011_status_observe'):
    LATCH.ELF=C.ELF
    graph=LATCH.final_call_graph(t)
    roots={'lisp_abort_code','lisp_abort_symbol','c2_product_abort_cleanup','c2_product_abort_recover','longjmp'}
    todo=deque(roots); reached=set()
    while todo:
        n=todo.popleft()
        if n in reached:continue
        reached.add(n);todo.extend(graph.get(n,()))
    state=t.symbol('lisp65_f011_status_state')
    refs=[]
    for r in t.relocations:
        if r.target!='lisp65_f011_status_state': continue
        owners=[s.name for s in t.symbols if s.symbol_type=='Function' and s.section==r.source_section and s.value<=r.offset-1<s.value+s.bytes]
        C.require(not set(owners)&reached,'abort closure references witness')
        C.require(set(owners)<= {'main',publisher} and owners,'unexpected witness reference owner')
        refs.append({'section':r.source_section,'offset':r.offset,'owners':owners})
    C.require(refs,'no emitted record users')
    # Reuse the existing raw-write closure, adding the LOAD_OPEN root to its
    # graph through the already-present lisp_abort_symbol entry.
    original=LATCH.final_call_graph
    def extended(truth):
        g=original(truth);g.setdefault('lisp_abort_symbol',set()).add('lisp_abort_code');return g
    LATCH.final_call_graph=extended
    try:
        closure=LATCH.abort_recovery_writer_gate(t,{'state':(state.value,state.value+record_bytes),'payload':(state.value,state.value+record_bytes)},None)
        try:LATCH.abort_recovery_writer_gate(t,{'state':(state.value,state.value+record_bytes),'payload':(state.value,state.value+record_bytes)},'injected-record-wipe')
        except RuntimeError: mutation=True
        else: mutation=False
    finally:LATCH.final_call_graph=original
    C.require(mutation,'injected abort writer survived')
    overlay=t.symbol('__lisp65_workbench_runtime_overlay_vma_param').value
    C.require(state.value+record_bytes<=overlay or state.value>=overlay+0x700,'record overlaps runtime wipe')
    return {'closure':closure,'symbol_references':refs,'wipe':[overlay,overlay+0x700],
            'injected_writer_rejected':mutation,'read_cutpoint':'after abort cleanup/recovery and prompt; no subsequent disk read'}

def run():
    C.configure();before=[C.bind(C.ELF),C.bind(C.PRG)]
    t=ElfTruth.read(C.ELF,llvm_readobj=C.B.READOBJ,include_section_data=True)
    old=ElfTruth.read(C.OLD_ELF,llvm_readobj=C.B.READOBJ,include_section_data=True)
    state=t.symbol('lisp65_f011_status_state'); owner=t.section(state.section); bss=t.section('.bss'); input_owner=t.section('.lisp65_c2_input_raw_owner')
    C.require(owner.name=='.noinit.lisp65_f011_status' and owner.section_type=='SHT_NOBITS' and owner.bytes==state.bytes==3 and owner.address==state.value==bss.address+bss.bytes,'NOLOAD ownership mismatch')
    reserve=input_owner.address-owner.address-owner.bytes
    text=t.section('.text');facade=t.section('.lisp65_c2_mapped_far_facade')
    text_reserve=facade.address-text.address-text.bytes
    C.require(reserve>=5 and text_reserve>=32,'final owner floor failed')
    cold=t.section('.lisp65_c2_mapped_f011_cold'); far=t.section('.lisp65_c2_mapped_far_service')
    C.require(cold.address+cold.bytes==far.address and cold.address>=0x6000,'cold owner adjacency/floor failed')
    island=t.section('.lisp65_resident_island'); C.require(island.bytes<=old.section(island.name).bytes,'Island grew without price')
    for s in old.sections:
        if s.name.startswith('.lisp65_c2_kernal_window.') or s.name in ['.lisp65_c2_vectors','.lisp65_c2_fixed_zp','.lisp65_c2_fixed_bank0_hot_bss','.lisp65_c2_terminal_return_raw_owner','.lisp65_c2_input_raw_owner','.lisp65_c2_symbol_metadata_bss']:
            n=t.section(s.name);C.require((s.address,s.bytes)==(n.address,n.bytes),'protected owner changed: '+s.name)
    C.PREVIOUS.R2.ELF=C.ELF
    e000=C.PREVIOUS.R2.e000_capture_gate()
    graph=F011.R2.NESTING.linked_graph(C.ELF)
    C.require('f011_status_observe' in graph['tenants'],'observer not in mapped population')
    paths=F011.R2.NESTING.paths_to_map(graph,graph['tenants'])
    C.require(not paths,'mapped observer closure nests MAP')
    mutant=F011.R2.NESTING.paths_to_map(graph,['f011_status_observe'],injected_edges={'f011_status_observe':{'lisp_abort_code'}})
    C.require(mutant,'in-body abort mutation survived')
    value={'format':'f011-final-emission-proof-v1','recorded_on':stable_recorded_on(OUT),
           'pair':before,'text_reserve':text_reserve,'BSS_record_reserve':reserve,
           'cold_bytes':cold.bytes,'island_bytes':island.bytes,'E000':e000,
           'record_owner':{'start':state.value,'bytes':state.bytes,'type':owner.section_type},
           'observer':observer(t),'boot_reset':boot_reset(t),
           'ordinary_error_edges':error_edges(t),'survival':survival(t),
           'nesting_paths':paths,'abort_mutation_paths':mutant,
           'attribution_scope_acceptance_DWX':'not claimed by this proof'}
    C.require(before==[C.bind(C.ELF),C.bind(C.PRG)],'read-only proof changed pair')
    OUT.write_bytes(C.canonical(value));print(json.dumps({k:value[k] for k in ['text_reserve','BSS_record_reserve','cold_bytes','record_owner']},indent=2))
if __name__=='__main__':run()
