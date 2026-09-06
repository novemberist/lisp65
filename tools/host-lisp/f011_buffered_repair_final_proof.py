#!/usr/bin/env python3
"""Read-only final ELF checks for the buffered F011 repair."""
import json
from pathlib import Path
import f011_buffered_repair_product_card as R
from elf_truth import ElfTruth
from f011_frame_emitted_semantics import NativeCPU
import f011_status_final_proof as F
import c2_bank2_composed_ownership as BANK
from evidence_era import stable_recorded_on

def startup_cache(t, skip_zero=False):
    m=NativeCPU();text=t.section('.text')
    m.mem[text.address:text.address+text.bytes]=t.section_bytes('.text')
    zp=t.section('.zp.bss');cache=t.symbol('f011_clock_verified')
    assert cache.section==zp.name and cache.bytes==1
    m.mem[zp.address:zp.address+zp.bytes]=b'\xa5'*zp.bytes
    site=t.symbol('__do_zero_zp_bss').value
    target=t.symbol('__zero_zp_bss').value
    assert bytes(m.mem[site:site+3])==b'\x20'+target.to_bytes(2,'little')
    if skip_zero:m.mem[site:site+3]=b'\xea'*3
    m.PC=t.symbol('_start').value;stop=t.symbol('__do_copy_zp_data').value
    steps=0
    while m.PC!=stop and steps<100000:m.step();steps+=1
    assert m.PC==stop,'startup zeroing path did not reach next stage'
    return {'cache_address':cache.value,'poison_before':0xa5,
            'after':m.mem[cache.value],'steps':steps,'skip_zero_mutation':skip_zero}

def execute(t,status,stopped=False,mutant=None,start_frame=0):
    m=NativeCPU()
    for name in ('.text','.lisp65_c2_mapped_f011_cold'):
        s=t.section(name);m.mem[s.address:s.address+s.bytes]=t.section_bytes(name)
    entry=t.symbol('f011_read_at_far');ready=t.symbol('f011_wait_clock_ready')
    if mutant=='skip-clock-proof':
        raw=bytes(m.mem[entry.value:entry.value+entry.bytes])
        needle=b'\x20'+ready.value.to_bytes(2,'little')
        assert raw.count(needle)==1
        a=entry.value+raw.index(needle);m.mem[a:a+3]=b'\xa9\x01\xea'
    elif mutant=='old-mask':
        s=t.symbol('f011_wait_complete');raw=bytes(m.mem[s.value:s.value+s.bytes])
        needle=bytes.fromhex('29 58');assert raw.count(needle)==1
        m.mem[s.value+raw.index(needle)+1]=0x5c
    elif mutant is not None:raise AssertionError(mutant)
    rd=m.rd;wr=m.wr;frame_reads=0;steps=0;commands=[];reads=[];maps=[]
    def read(a):
        nonlocal frame_reads
        if a in (0xff83,0xff84):
            if a==0xff83:frame_reads+=1
            n=start_frame if stopped else (start_frame+frame_reads//8)&65535
            return (n>>(8 if a==0xff84 else 0))&255
        if a==0xd082:
            reads.append((list(commands),a))
            return status
        assert a!=0xd087, 'DATA register read on buffered path'
        return rd(a)
    def write(a,v):
        if a==0xd081:commands.append(v)
        if a==0xd680:maps.append(v)
        wr(a,v)
    m.rd=read;m.wr=write
    m.mem[2:4]=(0xb100).to_bytes(2,'little')
    m.A=1;m.X=0;m.PC=entry.value;m.push16(0x3ff)
    while m.PC!=0x400 and steps<10000000:m.step();steps+=1
    assert m.PC==0x400,'native execution did not terminate'
    result=m.A|(m.X<<8)
    return dict(status=status,stopped=stopped,mutant=mutant,return_value=result,
                commands=commands,frame_reads=frame_reads,steps=steps,
                status_read_count=len(reads),pre_READ_status_reads=sum(0x40 not in c for c,a in reads),
                buffer_mapped=0x81 in maps)

def run():
    R.configure();R.C.configure=R.configure
    before=[R.C.bind(R.ELF),R.C.bind(R.PRG)]
    t=ElfTruth.read(R.ELF,llvm_readobj=R.C.B.READOBJ,include_section_data=True)
    R.witness_absent(t)
    startup=startup_cache(t);bad_startup=startup_cache(t,True)
    assert startup['after']==0 and bad_startup['after']==0xa5
    rows=[]
    for status in range(256):
        row=execute(t,status); expected=(status&0xd8)==0x40
        assert (row['return_value']==0)==expected,row
        assert row['buffer_mapped']==expected,row
        assert row['commands']==[0x20,0x40] and not row['pre_READ_status_reads'],row
        rows.append(row)
    stopped=execute(t,0x44,True)
    assert stopped['return_value']==65535 and stopped['commands']==[] and not stopped['buffer_mapped']
    wrap=execute(t,0xd0,start_frame=65534)
    assert wrap['return_value']==65535 and not wrap['buffer_mapped']
    bad_clock=execute(t,0x44,True,'skip-clock-proof')
    assert bad_clock['return_value']==0 and bad_clock['buffer_mapped']
    bad_mask=execute(t,0x44,False,'old-mask')
    assert bad_mask['return_value']==65535 and not bad_mask['buffer_mapped']
    text=t.section('.text');facade=t.section('.lisp65_c2_mapped_far_facade')
    reserve=facade.address-text.address-text.bytes;assert reserve>=32
    bss=t.section('.bss');raw=t.section('.lisp65_c2_input_raw_owner')
    bss_gap=raw.address-bss.address-bss.bytes;assert bss_gap>=5
    bounded=R.PACKED.bounded_owners(t)
    metadata=t.section('.lisp65_c2_symbol_metadata_bss')
    terminal=t.section('.lisp65_c2_terminal_return_raw_owner')
    regions=[terminal,bss,raw,metadata]
    assert terminal.section_type==raw.section_type=='SHT_NOBITS'
    for i,left in enumerate(regions):
        for right in regions[i+1:]:
            assert max(left.address,right.address)>=min(left.address+left.bytes,right.address+right.bytes)
    high_gap=0xc000-metadata.address-metadata.bytes
    assert high_gap>=5
    bounded['ordinary_BSS']={'low_reserve_bytes':bss_gap,'high_reserve_bytes':high_gap,
        'margin_bytes':min(bss_gap,high_gap),'floor_bytes':5,
        'logical_bytes':bss.bytes+metadata.bytes,'aggregate_is_not_capacity':True}
    bounded['raw_NOLOAD']=[dict(name=s.name,address=s.address,bytes=s.bytes) for s in (terminal,raw)]
    cold=t.section('.lisp65_c2_mapped_f011_cold');far=t.section('.lisp65_c2_mapped_far_service')
    assert cold.address+cold.bytes==far.address
    R.C.PREVIOUS.R2.ELF=R.ELF
    e000=R.C.PREVIOUS.R2.e000_capture_gate()
    graph=F.F011.R2.NESTING.linked_graph(R.ELF)
    assert 'f011_wait_complete' in graph['tenants']
    paths=F.F011.R2.NESTING.paths_to_map(graph,graph['tenants']);assert not paths
    bad_nesting=F.F011.R2.NESTING.paths_to_map(graph,['f011_wait_complete'],
        injected_edges={'f011_wait_complete':{'lisp_abort_code'}})
    assert bad_nesting
    mapped=tuple((n,'__lisp65_c2_'+n.removeprefix('.lisp65_c2_')) for n in (
        '.lisp65_c2_mapped_f011_cold','.lisp65_c2_mapped_far_service','.lisp65_c2_mapped_product_cold'))
    bank=BANK.derive(elf=R.ELF,plane=R.PLANE/'v6-semantics/bank2-static-code.bin',
        readobj=R.C.B.READOBJ,mapped_owners=mapped,placement_policy='map-page-top-derived',
        expected_vmas={n:t.section(n).address for n,_ in mapped})
    assert not bank['overlaps']
    out=R.BUILD/'final-native-proof.json'
    value=dict(status='PASS',recorded_on=stable_recorded_on(out),pair=before,
        native_status_rows=rows,clock_stopped=stopped,clock_wrap=wrap,
        startup_cache=startup,omitted_startup_zero_mutation=bad_startup,
        mutations=dict(skip_clock=bad_clock,old_mask=bad_mask,in_body_abort=bad_nesting),
        text_reserve=reserve,bss_reserve=bss_gap,bounded_owners=bounded,cold_bytes=cold.bytes,E000=e000,bank2=bank,
        ordinary_error_edges=F.error_edges(t),empty_witness_mutations=R.empty_witness_mutations(R.PRG),
        claim='executed final reader bytes with modeled MMIO/clock; not physical timing or first-boot IRQ proof')
    assert before==[R.C.bind(R.ELF),R.C.bind(R.PRG)]
    out.write_text(json.dumps(value,indent=2)+'\n')
    print('FINAL NATIVE/OWNER/NESTING PASS',reserve,bss_gap,'statuses',len(rows))

if __name__=='__main__':run()
