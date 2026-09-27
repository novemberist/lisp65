"""Set B placement revision: two non-LTO objects, no product link or Seed."""
import difflib
import json
from pathlib import Path
import shutil
import subprocess
from dataclasses import asdict
import set_b_producer as P
from elf_truth import ElfTruth
import boot_name_index_link_preprobe as L

ROOT=P.ROOT
OUT=ROOT/'build/set-b-placement-r1'
PREVIEW=ROOT/'build/set-b-r1/step4-r3/command-preview'
OLD='C2_KERNAL_RESIDENT uint8_t c2_overlay_call('
NEW='''/* Set B shares gap1 with vm_c2d_byte; both remain in the mapped window.
 * This moves code away from the fixed Comfort capture boundary. */
#ifdef LISP65_SET_B
__attribute__((section(".lisp65_c2_kernal_window.reopen_gap1")))
#else
C2_KERNAL_RESIDENT
#endif
uint8_t c2_overlay_call('''

def main():
    assert not OUT.exists(), 'Preserve previous probe'
    OUT.mkdir()
    P.write(OUT/'start.json',dict(authority=P.require_auth(),driver=P.bind(Path(__file__)),
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        owner_word='Dann fahr bitte direkt fort: proposed host-only placement revision',
        product_links=0,seeds=0,finals=0,device_contacts=0))
    src=ROOT/'src/c2_product_runtime.c'
    original=src.read_text();assert original.count(OLD)==1
    revised=original.replace(OLD,NEW,1)
    (OUT/'runtime-placement.patch').write_text(''.join(difflib.unified_diff(
        original.splitlines(True),revised.splitlines(True),
        fromfile='a/src/c2_product_runtime.c',tofile='b/src/c2_product_runtime.c')))
    commands=P.load(PREVIEW/'commands.json')
    cc=next(c for c in commands if '-c' in c and Path(c[c.index('-c')+1]).name=='c2_product_runtime.c')
    measured={};rows=[]
    for label in ['before','after']:
        tree=OUT/label/'generated-product-sources'
        shutil.copytree(PREVIEW/'wplto/generated-product-sources',tree)
        generated=tree/'c2_product_runtime.c'
        text=generated.read_text();assert text.count(OLD)==1
        if label=='after':generated.write_text(text.replace(OLD,NEW,1))
        obj=OUT/label/'runtime.o'
        command=[str(tree.relative_to(ROOT)) if a==str((PREVIEW/'wplto/generated-product-sources').relative_to(ROOT)) else a for a in cc]
        command[command.index('-c')+1]=str(generated.relative_to(ROOT))
        command[command.index('-o')+1]=str(obj.relative_to(ROOT))
        command+=['-fno-lto']
        assert '-c' in command
        done=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        log=OUT/label/'compile.txt';log.write_text(done.stdout+done.stderr)
        rows.append(dict(label=label,command=command,exit=done.returncode,source=P.bind(generated),log=P.bind(log)))
        P.write(OUT/'compile-receipt.json',dict(driver=P.bind(Path(__file__)),compiles=rows,product_links=0))
        assert done.returncode==0,done.stderr
        rows[-1]['object']=P.bind(obj)
        measured[label]=ElfTruth.read(obj,llvm_readobj=L.LLVM_READOBJ,include_section_data=True)
        print(label,'object compiled',flush=True)
    P.write(OUT/'compile-receipt.json',dict(driver=P.bind(Path(__file__)),compiles=rows,product_links=0))
    before,after=measured['before'],measured['after']
    a=before.symbol('c2_overlay_call');b=after.symbol('c2_overlay_call')
    assert a.section=='.lisp65_c2_kernal_window.c2_resident'
    assert b.section=='.lisp65_c2_kernal_window.reopen_gap1'
    assert a.bytes==b.bytes==40
    assert before.section_bytes(a.section)[a.value:a.value+a.bytes]==after.section_bytes(b.section)[b.value:b.value+b.bytes]
    symbols_before={s.name:s for s in before.symbols if s.symbol_type=='Function' and s.bytes}
    symbols_after={s.name:s for s in after.symbols if s.symbol_type=='Function' and s.bytes}
    assert symbols_before.keys()==symbols_after.keys()
    differences=[]
    for n,s in symbols_before.items():
        t=symbols_after[n]
        if (s.section,s.bytes)!=(t.section,t.bytes):differences.append(dict(name=n,before=asdict(s),after=asdict(t)))
    assert [r['name'] for r in differences]==['c2_overlay_call'], differences
    sections_before={s.name:s.bytes for s in before.sections if 'SHF_ALLOC' in s.flags}
    sections_after={s.name:s.bytes for s in after.sections if 'SHF_ALLOC' in s.flags}
    deltas={s:sections_after.get(s,0)-sections_before.get(s,0) for s in sections_before.keys()|sections_after.keys()
            if sections_after.get(s,0)!=sections_before.get(s,0)}
    assert deltas=={a.section:-40,b.section:40},deltas
    old=P.load(ROOT/'build/set-b-r1/step4-r2/link-preprobe/receipt.json')['objects']
    new=[OUT/'after/runtime.o' if Path(p).name=='005-c2_product_runtime.c.o' else ROOT/p for p in old]
    edge=L.e000_low_edges_receipt(new,[ROOT/p for p in old])
    P.write(OUT/'e000-edges.json',edge)
    assert edge['status']=='PASS',edge['new_findings_keys']
    # External reference set cannot gain an unresolved symbol under this move.
    u=lambda t:{s.name for s in t.symbols if s.section=='Undefined'}
    assert u(before)==u(after)
    actual=P.load(ROOT/'build/set-b-r1/step4-r3/halt-attribution/receipt.json')
    projection=P.load(P.PROJECTION_RECEIPT)
    tenants=[];offset=0
    for t in actual['tenants']:
        projected=next(r['bytes'] for r in projection['slices'] if r['slot']==t['slot'])
        budget=max(t['bytes'],projected)
        interval=(budget+16+15)&~15
        tenants.append(dict(slot=t['slot'],old_offset=t['offset'],offset=offset,interval=interval,
            last_lto_bytes=t['bytes'],non_lto_bytes=projected,budget_bytes=budget,air=interval-budget,
            source_address=0x5de80+offset))
        offset+=interval
    assert offset==6656 and 8192-offset==1536
    P.write(OUT/'proposal.json',dict(status='PASS: OBJECT PLACEMENT PROPOSAL; LINKED GATES PENDING',
        compile_receipt=P.bind(OUT/'compile-receipt.json'),edge_receipt=P.bind(OUT/'e000-edges.json'),
        patch=P.bind(OUT/'runtime-placement.patch'),function_changes=differences,section_deltas=deltas,
        same_helper_instruction_bytes=True,same_undefined_symbols=True,
        projection_basis=P.bind(ROOT/'build/set-b-r1/step4-r3/halt-attribution/receipt.json'),
        projected_capture=dict(helper_end=0xfd26-40,helper_boundary=0xfd22,helper_margin=36,
            gap1_bytes=89+40,consumer_end=0xff1d+40,consumer_boundary=0xff80,consumer_margin=59,
            capture_total_free=105,capture_floor=57,e000_total_free=115,e000_floor=54,
            reopening_debit=89+129+96+9,reopening_cap=450),
        tenants=tenants,reserved_extent=offset,tail_bytes=8192-offset,
        new_slot_count=0,new_bss=0,new_code_bytes=0,product_links=0,seeds=0,finals=0,device_contacts=0))
    print('PASS: move 40 bytes within E000; no new call edges; seven tenants with >=16 bytes interval air',flush=True)

if __name__=='__main__':main()
