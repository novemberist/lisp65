#!/usr/bin/env python3
"""Execute final native diagnostic bodies with explicit counter/MMIO models.

Functional byte execution only: no CPU timing, MAP, or physical spin-up claim.
The late-IRQ case withholds counter progress at the reader entry.
"""
import json
from pathlib import Path
import f011_frame_diagnostic_card as D
from elf_truth import ElfTruth
from cpu6502 import CPU, N, Z
from evidence_era import stable_recorded_on


class NativeCPU(CPU):
    def step(self):
        op = self.rd(self.PC)
        if op == 0x80:
            self.fetch(); self.branch(True)
        elif op in (0x5a,0xda):
            self.fetch(); self.push(self.Y if op==0x5a else self.X)
        elif op in (0x7a,0xfa):
            self.fetch(); value=self.pull()
            if op==0x7a:self.Y=value
            else:self.X=value
            self.set_zn(value)
        elif op in (0x64,0x9c):
            self.fetch(); self.wr(self.fetch() if op==0x64 else self.fetch16(),0)
        elif op in (0xb2,0x92):
            self.fetch(); address=self.rd16zp(self.fetch())
            if op==0xb2:self.A=self.rd(address); self.set_zn(self.A)
            else:self.wr(address,self.A)
        elif op==0x1a:
            self.fetch(); self.A=(self.A+1)&255; self.set_zn(self.A)
        elif op==0xe3:
            # Qualified Xemu cpu65.c case E3: base-page word increment.
            self.fetch(); address=self.fetch()
            value=(self.rd(address)|(self.rd((address+1)&255)<<8))+1
            value &= 65535
            self.wr(address,value&255);self.wr((address+1)&255,value>>8)
            self.set(N,value&0x8000);self.set(Z,value==0)
        else:super().step()


def execute(t, late_irq=False, mutant=False):
    m=NativeCPU()
    for name in ('.text','.lisp65_c2_mapped_f011_cold'):
        sec=t.section(name); data=t.section_bytes(name)
        m.mem[sec.address:sec.address+len(data)]=data
    entry=t.symbol('f011_read_at_far'); live=t.symbol('f011_frame_live')
    state=t.symbol('lisp65_f011_status_state')
    assert state.bytes==7
    if mutant:
        sec=t.section(entry.section); raw=t.section_bytes(sec.name)
        start=entry.value-sec.address
        needle=b'\x20'+live.value.to_bytes(2,'little')
        positions=[i for i in range(entry.bytes-2) if raw[start+i:start+i+3]==needle]
        assert len(positions)==1
        a=entry.value+positions[0];m.mem[a:a+3]=b'\xa9\x01\xea'
    steps=0; commands=[]; io_reads=[]; writes=[]
    rd=m.rd; wr=m.wr
    def read(a):
        if a in (0xff83,0xff84):
            frames=0 if late_irq else steps//1000
            return (frames >> (8 if a==0xff84 else 0))&255
        if a in (0xd082,0xd083):
            io_reads.append(a)
            return 0xaa if a==0xd083 else (0x62 if 0x40 in commands else 0xd0)
        return rd(a)
    def write(a,v):
        if a==0xd081:commands.append(v)
        if state.value<=a<state.value+7:writes.append([a-state.value,v])
        wr(a,v)
    m.rd=read;m.wr=write
    m.mem[2:4]=(0xb100).to_bytes(2,'little')
    m.A=1;m.X=0;m.PC=entry.value;m.push16(0x3ff)
    while m.PC!=0x400 and steps<12000000:
        m.step();steps+=1
    assert m.PC==0x400, 'native reader did not return within functional budget'
    record=bytes(m.mem[state.value:state.value+7])
    if not mutant:
        assert record[0]==(5 if late_irq else 1), record.hex()
        assert (0x20 in commands and 0x40 in commands)==(not late_irq)
        assert writes[-1][0]==0, 'tag must be published last'
        if late_irq:assert record[6]&7==0
        else:assert record[1:4]==bytes((0xd0,0x62,0xaa)) and record[6]&7==7
    return {'late_IRQ_counter_withheld':late_irq,'record_hex':record.hex(),
            'functional_steps':steps,'commands':commands,'status_reads':io_reads,
            'record_writes':writes,'return_AX':[m.A,m.X]}


def run():
    before=[D.C.bind(D.ELF),D.C.bind(D.PRG)]
    t=ElfTruth.read(D.ELF,llvm_readobj=D.C.B.READOBJ,include_section_data=True)
    good=execute(t); late=execute(t,True); mutant=execute(t,True,True)
    assert mutant['record_hex'][:2]!='05', 'clock-check-removal mutation did not discriminate'
    transitions=[]
    fn=t.symbol('f011_frame_publish');state=t.symbol('lisp65_f011_status_state')
    sec=t.section(fn.section)
    for prior in range(6):
        for incoming in (1,2,4,5):
            m=NativeCPU();data=t.section_bytes(sec.name)
            m.mem[sec.address:sec.address+len(data)]=data
            old=bytes((prior,0x11,0x22,0x33,0x44,0x55,0x66))
            sample=bytes((incoming,0xd0,0x62,0,0x34,0x12,7))
            m.mem[state.value:state.value+7]=old;m.mem[0x9000:0x9007]=sample
            m.mem[4:6]=(0x9000).to_bytes(2,'little');m.mem[0xd083]=0xaa
            m.PC=fn.value;m.push16(0x3ff)
            steps=0
            while m.PC!=0x400 and steps<300:m.step();steps+=1
            assert m.PC==0x400
            commit=prior==0 or (prior==1 and incoming>1)
            expected=bytes((incoming,0xd0,0x62,0xaa,0x34,0x12,7)) if commit else old
            actual=bytes(m.mem[state.value:state.value+7]);assert actual==expected
            transitions.append({'prior':prior,'incoming':incoming,'record':actual.hex()})
    out=D.BUILD/'emitted-clock-semantics.json'
    value={'role':'DIAGNOSTIC-EVIDENCE-ONLY','recorded_on':stable_recorded_on(out),
        'pair':before,'running_counter':good,'late_IRQ':late,'removed_clock_check':mutant,
        'publisher_transitions':transitions,
        'status':'PASS','claim_limit':'Final reader bytes under explicit MMIO/counter models; not actual boot IRQ order, MAP, or hardware timing'}
    assert before==[D.C.bind(D.ELF),D.C.bind(D.PRG)]
    out.write_text(json.dumps(value,indent=2)+'\n')
    print('FINAL READER: running counter, late IRQ, removed-check mutation PASS')

if __name__=='__main__':run()
