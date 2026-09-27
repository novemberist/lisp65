"""Matched Set B reader repair object projection; no native link or Seed.

Candidate stays under build. The four retirement overlays execute at C356,
not in the separately delivered E000 slab whose calls require fixed vectors.
"""
import argparse
from dataclasses import asdict
import difflib
from pathlib import Path
import shutil
import subprocess
import sys
sys.dont_write_bytecode = True
import set_b_producer as P
from elf_truth import ElfTruth

ROOT=P.ROOT
BASE=ROOT/'build/set-b-product-r3'
NAMES=('commit_a','commit_b','commit_c','reset')
SECTIONS={'.lisp65_rt_c2append_retire_'+n for n in ('prepare','move','final','reset')}


def main(out, reuse=None):
    if reuse:
        shutil.copytree(reuse,out)
        truths={label:ElfTruth.read(out/label/'005-c2_product_runtime.c.o',
            llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True) for label in ('before','after')}
        P.write(out/'analysis-successor.json',dict(prior=P.bind(reuse/'compile-receipt.json'),
            driver=P.bind(Path(__file__)),new_compiles=0,reason='NOBITS has size, not file bytes'))
    else:
        out.mkdir(parents=True,exist_ok=False)
        P.write(out/'start.json',dict(head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            authority=P.require_auth(),scope='owner continuation: host-only repair design and object price',
            product_links=0,seeds=0,observer_builds=0,device_contacts=0,driver=P.bind(Path(__file__))))
        originals={n:(ROOT/f'src/optional/set_b_retire_{n}.c').read_text() for n in NAMES}
        revised={}
        for n,s in originals.items():
            lines=s.splitlines(True)
            decl=[line for line in lines if '__asm__("c2_facade_runtime_overlay_exec")' in line]
            assert len(decl)==1
            s=s.replace(decl[0],'').replace('c2r_map_read(', 'c2_map_cpu_read(').replace('c2r_reset_read(', 'c2_map_cpu_read(')
            if n=='commit_a':
                old='if(!rc_read(RJ,j,72u))return C2_STREAM_ERR_C2D;'
                new='''/* Keep each synchronous MAP read within the admitted 64-byte bound. */
     if(!rc_read(RJ,j,64u) || !rc_read(RJ+64u,j+64u,8u))return C2_STREAM_ERR_C2D;'''
                assert s.count(old)==1;s=s.replace(old,new)
            revised[n]=s
        patch=''.join(''.join(difflib.unified_diff(originals[n].splitlines(True),revised[n].splitlines(True),
            fromfile=f'a/src/optional/set_b_retire_{n}.c',tofile=f'b/src/optional/set_b_retire_{n}.c')) for n in NAMES)
        (out/'authored.patch').write_text(patch)
        commands=P.load(BASE/'commands.json')
        cc=next(c for c in commands if '-c' in c and c[c.index('-c')+1].endswith('/c2_product_runtime.c'))
        srcdir=BASE/'wplto/generated-product-sources'
        truths={};compiles=[]
        for label in ('before','after'):
            tree=out/label/'generated-product-sources';shutil.copytree(srcdir,tree)
            (tree/'optional').mkdir(exist_ok=True)
            # Copy the exact included optional closure; local quote includes win
            # over -I src. All unchanged optional files remain byte-identical.
            for source in (ROOT/'src/optional').iterdir():
                if source.is_file():shutil.copyfile(source,tree/'optional'/source.name)
            if label=='after':
                for n,s in revised.items():(tree/f'optional/set_b_retire_{n}.c').write_text(s)
            obj=out/label/'005-c2_product_runtime.c.o'
            command=[str(tree.relative_to(ROOT)) if a==str(srcdir.relative_to(ROOT)) else a for a in cc]
            command[command.index('-c')+1]=str((tree/'c2_product_runtime.c').relative_to(ROOT))
            command[command.index('-o')+1]=str(obj.relative_to(ROOT))
            command+=['-fno-lto']
            assert '-c' in command and not any(a.startswith('-Wl,') for a in command)
            done=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            log=out/label/'compile.txt';log.write_text(done.stdout+done.stderr)
            row=dict(label=label,command=command,exit=done.returncode,log=P.bind(log))
            compiles.append(row);P.write(out/'compile-receipt.json',dict(driver=P.bind(Path(__file__)),compiles=compiles,product_links=0))
            assert done.returncode==0,done.stderr
            row['object']=P.bind(obj)
            truths[label]=ElfTruth.read(obj,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
            print(label,'compiled',flush=True)
        P.write(out/'compile-receipt.json',dict(driver=P.bind(Path(__file__)),compiles=compiles,product_links=0))
    a,b=truths['before'],truths['after']
    sa={s.name:s for s in a.sections if 'SHF_ALLOC' in s.flags}
    sb={s.name:s for s in b.sections if 'SHF_ALLOC' in s.flags}
    assert sa.keys()==sb.keys()
    def relocs(t,s):return [(r.offset,r.relocation_type,r.target,r.addend) for r in t.relocations if r.source_section==s]
    changes=[];unchanged=[]
    for name in sorted(sa):
        changed=(sa[name].bytes!=sb[name].bytes or (sa[name].section_type!='SHT_NOBITS' and a.section_bytes(name)!=b.section_bytes(name)) or relocs(a,name)!=relocs(b,name))
        if changed:
            assert name in SECTIONS,(name,'change outside four readers')
            changes.append(dict(section=name,before=sa[name].bytes,after=sb[name].bytes,delta=sb[name].bytes-sa[name].bytes,
                relocations_before=relocs(a,name),relocations_after=relocs(b,name)))
        else:unchanged.append(name)
    assert {r['section'] for r in changes}==SECTIONS
    undefined=lambda t:{s.name for s in t.symbols if s.section=='Undefined'}
    assert undefined(b)==undefined(a) # reader already used by c2_product_entry_read
    assert undefined(a)-undefined(b)==set() # legacy facade still used elsewhere
    target_edges=[asdict(r) for r in b.relocations if r.target=='c2_map_cpu_read' and r.source_section in SECTIONS]
    assert len(target_edges)==4 and {r['source_section'] for r in target_edges}==SECTIONS
    assert all(r['relocation_type']=='R_MOS_ADDR16' for r in target_edges)
    old_edges=[asdict(r) for r in a.relocations if r.source_section in SECTIONS and r.target=='c2_facade_runtime_overlay_exec']
    assert len(old_edges)==4
    assert not [r for r in b.relocations if r.source_section in SECTIONS and r.target=='c2_facade_runtime_overlay_exec']
    for label in ('before','after'):
        cmd=[str(ROOT/'tools/llvm-mos/bin/llvm-objdump'),'-dr',str(out/label/'005-c2_product_runtime.c.o')]
        (out/label/'disassembly.txt').write_text(subprocess.check_output(cmd,text=True))
    linked=ElfTruth.read(BASE/'wplto/resident-island-seed.prg.elf',llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    slots=[('control',56,448),('scan_a',57,1568),('scan_b',58,1408),('prepare',59,992),('move',60,1408),('final',61,640),('reset',62,256)]
    tenants=[];cursor=0
    for name,slot,extent in slots:
        sec='.lisp65_rt_c2append_retire_'+name
        before=sa[sec].bytes;after=sb[sec].bytes;lto=linked.sections_by_name[sec][0].bytes
        delta=after-before;projection=lto+delta
        # Same conservative rule: worse of actual+delta and non-LTO size,
        # with at least 16 bytes interval reserve and canonical 32-byte alignment.
        budget=max(projection,after);proposed=max(extent,(budget+16+31)&~31)
        tenants.append(dict(slot=slot,owner=name,object_before=before,object_after=after,object_delta=delta,
            seed_lto=lto,lto_projection=projection,budget=budget,old_extent=extent,proposed_extent=proposed,
            offset=cursor,air_over_budget=proposed-budget,air_over_projection=proposed-projection))
        cursor+=proposed
    assert cursor<=8192
    report=dict(status='PASS: HOST OBJECT REPAIR PROPOSAL; NO PRODUCT LINK',driver=P.bind(Path(__file__)),
        patch=P.bind(out/'authored.patch'),seed=P.bind(BASE/'wplto/resident-island-seed.prg.elf'),
        compile_receipt=P.bind(out/'compile-receipt.json'),changes=changes,unchanged_allocated_sections=unchanged,
        target_edges=target_edges,old_edges=old_edges,tenants=tenants,tenant_extent=cursor,tenant_tail=8192-cursor,
        e000_sections_unchanged=[s for s in unchanged if s.startswith('.lisp65_c2_kernal_window.')],
        new_bss_bytes=0,new_slots=0,product_links=0,seeds=0,finals=0,device_contacts=0,
        limits='Matched non-LTO projection only. Exact LTO layout, selector return offsets, floors, MAP hot-page bound, stack destinations and all executed gates remain link gates.')
    P.write(out/'receipt.json',report)
    print('PASS: four reader owners; tenant extent',cursor,'tail',8192-cursor,flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--reuse',type=Path);args=ap.parse_args()
    main(args.out.resolve(),args.reuse.resolve() if args.reuse else None)
