"""Finish the object-only placement review with matched probe object identities."""
from pathlib import Path
import subprocess
from dataclasses import asdict
from elf_truth import ElfTruth
import set_b_producer as P
import boot_name_index_link_preprobe as L

ROOT=P.ROOT
PROBE=ROOT/'build/set-b-placement-r1'
OUT=PROBE/'review-r2'

def main():
    OUT.mkdir(exist_ok=False)
    compile_receipt=P.load(PROBE/'compile-receipt.json')
    for row in compile_receipt['compiles']:
        for key in ['source','object','log']:assert P.bind(ROOT/row[key]['path'])==row[key]
    old=P.load(ROOT/'build/set-b-r1/step4-r2/link-preprobe/receipt.json')['objects']
    worlds={label:[PROBE/label/'runtime.o' if Path(p).name=='005-c2_product_runtime.c.o' else ROOT/p for p in old]
            for label in ['before','after']}
    # The era gate keys noise by object basename. Both compiled sides now use
    # runtime.o, avoiding the first invocation's mismatched basename false red.
    edge=L.e000_low_edges_receipt(worlds['after'],worlds['before'])
    P.write(OUT/'e000-edges.json',edge)
    assert edge['status']=='PASS',edge['new_findings_keys']
    truths={label:ElfTruth.read(PROBE/label/'runtime.o',llvm_readobj=L.LLVM_READOBJ,include_section_data=True)
            for label in ['before','after']}
    before,after=truths['before'],truths['after']
    a=before.symbol('c2_overlay_call');b=after.symbol('c2_overlay_call')
    assert a.bytes==b.bytes==40
    assert a.section=='.lisp65_c2_kernal_window.c2_resident'
    assert b.section=='.lisp65_c2_kernal_window.reopen_gap1'
    assert before.section_bytes(a.section)[a.value:a.value+a.bytes]==after.section_bytes(b.section)[b.value:b.value+b.bytes]
    allocated=lambda t:{s.name:s.bytes for s in t.sections if 'SHF_ALLOC' in s.flags}
    sa,sb=allocated(before),allocated(after)
    deltas={n:sb.get(n,0)-sa.get(n,0) for n in sa.keys()|sb.keys() if sb.get(n,0)!=sa.get(n,0)}
    assert deltas=={a.section:-40,b.section:40},deltas
    functions=lambda t:{s.name:(s.bytes,s.section) for s in t.symbols if s.symbol_type=='Function' and s.bytes}
    fa,fb=functions(before),functions(after);assert fa.keys()==fb.keys()
    assert [n for n in fa if fa[n]!=fb[n]]==['c2_overlay_call']
    undefined=lambda t:{s.name for s in t.symbols if s.section=='Undefined'}
    assert undefined(before)==undefined(after)
    disassemblies=[]
    for label in truths:
        cmd=[str(ROOT/'tools/llvm-mos/bin/llvm-objdump'),'-dr',str(PROBE/label/'runtime.o')]
        done=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);assert done.returncode==0
        dest=OUT/(label+'-runtime-disassembly.txt');dest.write_text(done.stdout+done.stderr)
        disassemblies.append(dict(command=cmd,exit=done.returncode,output=P.bind(dest)))
    actual=P.load(ROOT/'build/set-b-r1/step4-r3/halt-attribution/receipt.json')
    projection=P.load(P.PROJECTION_RECEIPT);tenants=[];offset=0
    for t in actual['tenants']:
        projected=next(r['bytes'] for r in projection['slices'] if r['slot']==t['slot'])
        budget=max(t['bytes'],projected);interval=(budget+31)&~15
        tenants.append(dict(slot=t['slot'],old_offset=t['offset'],offset=offset,interval=interval,
            last_lto_bytes=t['bytes'],non_lto_bytes=projected,budget_bytes=budget,air=interval-budget,
            source_address=0x5de80+offset))
        offset+=interval
    assert offset==6656
    s=actual['selected_sections'];stem='.lisp65_c2_kernal_window.'
    helper_end=s[stem+'input_capture_helper']['end']-b.bytes
    consumer_end=s[stem+'input_consumer']['end']+b.bytes
    gap1_before=s[stem+'input_consumer']['address']-(s[stem+'profile_rodata']['end'])
    free1=s[stem+'profile_rodata']['address']-helper_end
    free2=s[stem+'state']['address']-consumer_end
    assert (free1,free2)==(46,59)
    P.write(OUT/'proposal.json',dict(status='PASS: OBJECT PLACEMENT PROPOSAL; LINKED GATES PENDING',
        driver=P.bind(Path(__file__)),compile_receipt=P.bind(PROBE/'compile-receipt.json'),
        preserved_false_red=P.bind(PROBE/'e000-edges.json'),edge_receipt=P.bind(OUT/'e000-edges.json'),
        correction='Matched runtime.o basename on both sides; all first-run apparent new edges are baseline noise. No edge exception or rule change.',
        function_before=asdict(a),function_after=asdict(b),function_count=len(fa),section_deltas=deltas,
        patch=P.bind(PROBE/'runtime-placement.patch'),disassemblies=disassemblies,
        same_helper_instruction_bytes=True,same_undefined_symbols=True,
        projection_basis=P.bind(ROOT/'build/set-b-r1/step4-r3/halt-attribution/receipt.json'),
        projected_capture=dict(helper_end=helper_end,helper_boundary=s[stem+'session_emitter_state']['address'],
            helper_margin=s[stem+'session_emitter_state']['address']-helper_end,
            gap1_bytes=gap1_before+b.bytes,consumer_end=consumer_end,
            consumer_boundary=s[stem+'state']['address'],consumer_margin=free2,
            capture_total_free=free1+free2,capture_floor=57,
            reopening_debit=s[stem+'reopen_gap0']['bytes']+gap1_before+b.bytes+96+9,reopening_cap=450),
        tenants=tenants,reserved_extent=offset,tail_bytes=8192-offset,
        new_slot_count=0,new_bss=0,new_code_bytes=0,object_compiles=2,product_links=0,seeds=0,finals=0,device_contacts=0))
    print('PASS: byte-identical 40-byte helper moved within E000; zero new E000 edges; backing extent 6656, tail 1536',flush=True)

if __name__=='__main__':main()
