"""Price the linked Seed and attribute out-of-binding zero-page spill drift.

Stops qualification at the inventory boundary; no compile/link/guest run.
"""
import collections
from dataclasses import asdict
from pathlib import Path
import re
import subprocess
import set_b_producer as P
from elf_truth import ElfTruth

ROOT=P.ROOT
OUT=ROOT/'build/set-b-r1/step4-r4/inventory-halt-r1'
PATHS=[P.FINAL,ROOT/'build/set-b-product-r3/wplto/resident-island-seed.prg.elf']
WIDTH={'R_MOS_ADDR8':1,'R_MOS_ADDR16':2,'R_MOS_ADDR16_LO':1,'R_MOS_ADDR16_HI':1,'R_MOS_IMM8':1}
WITNESSES={'eval_init':2,'vm_buf_ensure_mine':4,'vm_buffer_call':2,'vm_run_inner':2}

def price(t):
    sec={s.name:s for s in t.sections};stem='.lisp65_c2_kernal_window.'
    end=lambda n:sec[n].address+sec[n].bytes
    return dict(text_bytes=sec['.text'].bytes,text_free=0xb3b0-end('.text'),text_floor=32,
        rodata_free=0xb98c-end('.rodata'),e000_free=8192-sum(s.bytes for s in t.sections if s.name.startswith(stem) or s.name=='.lisp65_c2_vectors'),
        e000_floor=54,capture_free=sec[stem+'profile_rodata'].address-end(stem+'input_capture_helper')+sec[stem+'state'].address-end(stem+'input_consumer'),
        capture_floor=57,helper_end=end(stem+'input_capture_helper'),helper_limit=sec[stem+'session_emitter_state'].address,
        consumer_end=end(stem+'input_consumer'),consumer_limit=sec[stem+'state'].address,
        high_bss_free=0xc000-t.symbol('__bss_end').value,low_frame_start=sec['.lisp65_vm_soft_frames_bss'].address,
        low_frame_end=end('.lisp65_vm_soft_frames_bss'),raw_input_start=sec['.lisp65_c2_input_raw_owner'].address,
        journal_start=t.symbol('__set_b_journal_start').value if '__set_b_journal_start' in t.symbols_by_name else None,
        journal_end=t.symbol('__set_b_journal_end').value if '__set_b_journal_end' in t.symbols_by_name else None,
        late_start=sec['.noinit.card_l_late'].address,late_bytes=sec['.noinit.card_l_late'].bytes,
        bank5_tail=0x60000-(end('.noinit.card_l_late')+10))

def instructions(path):
    cmd=[str(ROOT/'tools/llvm-mos/bin/llvm-objdump'),'-d',str(path)]
    done=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);assert done.returncode==0
    rows=collections.defaultdict(dict);section=None
    for line in done.stdout.splitlines():
        m=re.fullmatch(r'Disassembly of section (.+):',line)
        if m:section=m[1]
        m=re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+)+)(\S+)(.*)',line)
        if m and section:
            raw=bytes.fromhex(m[2]);rows[section][int(m[1],16)]=dict(address=int(m[1],16),bytes=raw.hex(),mnemonic=m[3],operand=m[4].strip())
    return rows,cmd,done.stdout

def main():
    OUT.mkdir(exist_ok=False)
    assert P.require_auth().startswith('7a4e43fa')
    ts=[ElfTruth.read(p,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True) for p in PATHS]
    old,new=ts;prices=[price(t) for t in ts]
    q=prices[1]
    assert q['text_free']>=32 and q['rodata_free']>=0 and q['e000_free']>=54 and q['capture_free']>=57
    assert q['helper_end']<=q['helper_limit'] and q['consumer_end']<=q['consumer_limit']
    assert q['low_frame_end']+5<=q['raw_input_start'] and q['high_bss_free']>=5 and q['bank5_tail']==374
    assert (q['journal_start'],q['journal_end'],q['late_start'],q['late_bytes'])==(0x5de20,0x5de68,0x5de80,8192)
    image,tenants=P.extract_tenants(PATHS[1]);assert image==(ROOT/'build/set-b-product-r3/set-b-tenants.bin').read_bytes()
    extent,_=P.late_partition();assert image[extent:]==bytes([0xa5])*(8192-extent)
    tenantrows=[]
    for t in tenants:
        assert t['payload'][t['code_bytes']:]==bytes(len(t['payload'])-t['code_bytes'])
        tenantrows.append(dict(slot=t['slot'],section=t['section'],offset=t['offset'],address=t['source_address'],
            code_bytes=t['code_bytes'],record_bytes=len(t['payload']),air=len(t['payload'])-t['code_bytes'],
            entry=t['entry'],vma=t['vma']))
    sectionrows=[]
    for name in dict.fromkeys([s.name for t in ts for s in t.sections]):
        sides=[t.section(name) if name in t.sections_by_name else None for t in ts]
        if 'SHF_ALLOC' not in (sides[1] or sides[0]).flags:continue
        sectionrows.append(dict(section=name,before=asdict(sides[0]) if sides[0] else None,after=asdict(sides[1]) if sides[1] else None))
    P.write(OUT/'price.json',dict(status='PASS: ACTUAL LINKED GEOMETRY; INVENTORY NOT ADMITTED',
        elfs=[P.bind(p) for p in PATHS],before=prices[0],after=q,tenants=tenantrows,sections=sectionrows,
        body_sum=sum(t['code_bytes'] for t in tenants),record_sum=sum(len(t['payload']) for t in tenants),
        delivery_padding=sum(len(t['payload'])-t['code_bytes'] for t in tenants),tail_bytes=8192-extent))
    disassemblies=[];decoded=[]
    for label,p in zip(['before','after'],PATHS):
        ins,cmd,raw=instructions(p);decoded.append(ins)
        dest=OUT/(label+'-disassembly.txt');dest.write_text(raw)
        disassemblies.append(dict(command=cmd,exit=0,output=P.bind(dest)))
    buf=[t.symbol('vm_buf_off') for t in ts]
    assert [(s.section,s.value,s.bytes) for s in buf]==[('.zp.bss',0x5c,2),('.bss',0xbb67,2)]
    rows=[];functiondeltas=[]
    for name,count in WITNESSES.items():
        found=[]
        for k,t in enumerate(ts):
            f=t.symbol(name);ins=decoded[k][f.section];hits=[]
            for rel in t.relocations:
                if rel.source_section!=f.section or not f.value<=rel.offset<f.value+f.bytes:continue
                sym=t.symbols[rel.target_symbol_index];address=sym.value+rel.addend
                if sym.section!=buf[k].section or not buf[k].value<=address<buf[k].value+buf[k].bytes:continue
                assert rel.relocation_type==('R_MOS_ADDR8' if k==0 else 'R_MOS_ADDR16')
                at=rel.offset-1;instruction=ins[at];raw=bytes.fromhex(instruction['bytes'])
                assert int.from_bytes(raw[1:],'little')==address
                hits.append(dict(instruction=instruction,relocation=asdict(rel),target='vm_buf_off',field_offset=address-buf[k].value))
            found.append(sorted(hits,key=lambda r:r['instruction']['address']))
        assert len(found[0])==len(found[1])==count,(name,len(found[0]),len(found[1]))
        for a,b in zip(*found):
            assert a['field_offset']==b['field_offset'] and a['instruction']['mnemonic']==b['instruction']['mnemonic']
            op=(bytes.fromhex(a['instruction']['bytes'])[0],bytes.fromhex(b['instruction']['bytes'])[0])
            assert op in [(0x86,0x8e),(0x84,0x8c),(0xa6,0xae)],op
            rows.append(dict(function=name,before=a,after=b,
                family='zero-page to absolute load/store, same register and symbolic field, one added operand byte'))
        a,b=[t.symbol(name) for t in ts];assert b.bytes-a.bytes==count
        functiondeltas.append(dict(name=name,before=asdict(a),after=asdict(b),extra_bytes=count,
            authored_body_change=False,full_function_equivalence='NOT CLAIMED; this receipt proves the ten widened accesses'))
    assert len(rows)==10
    # Native source change scope: function annotation + retirement additions,
    # not edits to these four existing bodies. Eval TU itself is identical.
    base_sources=P.BASE/'wplto/generated-product-sources'
    seed_sources=PATHS[1].parent/'generated-product-sources'
    assert (base_sources/'eval.c').read_bytes()==(seed_sources/'eval.c').read_bytes()
    def body(text,name):
        # Require a unique definition, then balance braces without changing text.
        m=list(re.finditer(r'\b'+re.escape(name)+r'\([^;{}]*\)\s*\{',text));assert len(m)==1,(name,len(m))
        start=m[0].end()-1;depth=0
        for i in range(start,len(text)):
            if text[i]=='{':depth+=1
            elif text[i]=='}':
                depth-=1
                if depth==0:return text[start:i+1]
        raise AssertionError(name)
    for name in ['vm_buf_ensure_mine','vm_buffer_call','vm_run_inner']:
        assert body((base_sources/'vm.c').read_text(),name)==body((seed_sources/'vm.c').read_text(),name)
    P.write(OUT/'inventory-halt.json',dict(status='HALT: ADDRESS-MODE DRIFT IN FOUR UNCHANGED FUNCTION BODIES',
        driver=P.bind(Path(__file__)),authority=P.require_auth(),elfs=[P.bind(p) for p in PATHS],
        source_inputs=[P.bind(p) for p in [base_sources/'eval.c',seed_sources/'eval.c',base_sources/'vm.c',seed_sources/'vm.c',
            ROOT/'src/optional/set_b_retire_common.h',ROOT/'docs/planning/set-b-carrier-plan.md']],
        named_plan_rule='Set B bound on Card L: any inventory difference outside the members halts and defers',
        zero_page_consumers=[asdict(new.symbol(n)) for n in ['c2r_gc_failed','c2r_boot_count']],
        displaced_object=[asdict(s) for s in buf],functions=functiondeltas,widened_accesses=rows,
        disassemblies=disassemblies,price=P.bind(OUT/'price.json'),
        scope='First bound inventory halt; no claim of complete inventory, full equivalence, runtime failure or data corruption',
        native_bytes_outside_authored_bodies=10,new_builds=0,new_links=0,media=0,emulator_runs=0,device_contacts=0,
        further_seed_required_for_review=False))
    print('HALT: linked geometry PASS; ten zero-page-to-absolute widenings in four unchanged functions need a binding decision')

if __name__=='__main__':main()
