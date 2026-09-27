"""Read-only attribution of the replacement link halt; no build/link/retry."""
import re
import subprocess
from pathlib import Path
from elf_truth import ElfTruth
import set_b_producer as P

ROOT=P.ROOT
OUT=ROOT/'build/set-b-r1/step4-r3/halt-attribution'
WORLD=ROOT/'build/set-b-product-r2/wplto'

def main():
    OUT.mkdir(exist_ok=False)
    assert not (WORLD/'resident-island-seed.prg.elf').exists()
    assert not (WORLD/'resident-island-seed.prg').exists()
    log=WORLD.parent/'command-075.log'
    assert 'Comfort input capture helper escaped its final-image-derived hole' in log.read_text()
    mapped=WORLD/'resident-island-seed.prg.map'
    sections={}
    for line in mapped.read_text().splitlines():
        m=re.fullmatch(r'\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\d+ (\.\S+)',line)
        if m:
            vma,lma,size=(int(m[i],16) for i in (1,2,3))
            assert m[4] not in sections
            sections[m[4]]=dict(address=vma,load_address=lma,bytes=size,end=vma+size)
    reader=ROOT/'tools/llvm-mos/bin/llvm-readobj'
    obj=WORLD/'resident-island-seed.prg.lto.o'
    base=ElfTruth.read(P.FINAL,llvm_readobj=reader,include_section_data=True)
    new=ElfTruth.read(obj,llvm_readobj=reader,include_section_data=True)
    stem='.lisp65_c2_kernal_window.'
    resident=stem+'c2_resident'
    oldsymbols={s.name:s.bytes for s in base.symbols if s.section==resident and s.bytes}
    newsymbols={s.name:s.bytes for s in new.symbols if s.section==resident and s.bytes}
    changes=[dict(name=n,before=oldsymbols.get(n,0),after=newsymbols.get(n,0),
                  delta=newsymbols.get(n,0)-oldsymbols.get(n,0))
             for n in sorted(oldsymbols.keys()|newsymbols.keys()) if oldsymbols.get(n,0)!=newsymbols.get(n,0)]
    growth=new.section(resident).bytes-base.section(resident).bytes
    assert sum(r['delta'] for r in changes)==growth==31
    assert {r['name'] for r in changes}=={'c2_overlay_call','c2_product_gc_mark_roots'}
    helper=sections[stem+'input_capture_helper'];main=sections[stem+'input_capture_main']
    boundary=sections[stem+'session_emitter_state']
    assert helper['bytes']==112 and helper['address']==main['end']
    assert helper['end']-boundary['address']==4 and boundary['bytes']==0
    oldhelper=base.section(stem+'input_capture_helper')
    assert base.section(stem+'session_emitter_state').address==boundary['address']
    assembly=WORLD/'.canonical-objects-resident-island-seed/054-c2_kernal_input_capture.s.o'
    oldassembly=P.BASE/'wplto/.canonical-objects-resident-island-seed/054-c2_kernal_input_capture.s.o'
    assert assembly.read_bytes()==oldassembly.read_bytes()
    assert sections[resident]['bytes']==new.section(resident).bytes
    tenants=[];ts=P.load(P.INPUTS)['tenants']
    for i,t in enumerate(ts):
        section=sections[t['section']];part=new.section(t['section'])
        assert section['bytes']==part.bytes and section['address']==0xc356
        limit=ts[i+1]['offset'] if i+1<len(ts) else 6528
        tenants.append(dict(slot=t['slot'],section=t['section'],offset=t['offset'],
            bytes=part.bytes,interval=limit-t['offset'],air=limit-t['offset']-part.bytes,
            fit=t['offset']+part.bytes<=limit))
    assert [r['slot'] for r in tenants if not r['fit']]==[59,61]
    disassembly=[]
    for label,path in [('card-l',P.FINAL),('replacement-lto',obj)]:
        cmd=[str(ROOT/'tools/llvm-mos/bin/llvm-objdump'),'-dr','--section='+resident,str(path)]
        done=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        assert done.returncode==0,done.stderr
        dest=OUT/(label+'-resident-disassembly.txt');dest.write_text(done.stdout+done.stderr)
        disassembly.append(dict(command=cmd,exit=done.returncode,output=P.bind(dest)))
    P.write(OUT/'receipt.json',dict(status='HALT ATTRIBUTED; NO EXECUTABLE SEED',
        authority=P.require_auth(),driver=P.bind(Path(__file__)),
        inputs=[P.bind(p) for p in [log,mapped,obj,P.FINAL,assembly,oldassembly,P.INPUTS,
            ROOT/'config/set-b-native/linker/c2-substitution.ld',reader,
            ROOT/'tools/llvm-mos/bin/llvm-objdump',ROOT/'tools/host-lisp/elf_truth.py']],
        evidence_scope='Failed-link map layout and LTO object, not accepted linked product evidence',
        resident_growth=growth,resident_symbol_changes=changes,
        capture_helper=dict(before_address=oldhelper.address,before_bytes=oldhelper.bytes,
            before_end=oldhelper.address+oldhelper.bytes,after=helper,fixed_boundary=boundary,
            before_margin=boundary['address']-oldhelper.address-oldhelper.bytes,after_margin=-4,
            unchanged_input_object=True,actual_live_data_collision_proven=False),
        tenants=tenants,disassembly=disassembly,
        selected_sections={n:sections[n] for n in [resident,stem+'reopen_gap0',stem+'input_capture_main',
            stem+'input_capture_helper',stem+'session_emitter_state',stem+'profile_rodata',
            stem+'input_consumer',stem+'state','.text','.rodata','.bss']},
        additional_builds=0,additional_links=0,emulator_runs=0,device_contacts=0))
    print('HALT: resident +31; unchanged helper exceeds fixed fence by 4; tenants 59 and 61 each exceed source interval by 4')

if __name__=='__main__':main()
