"""Close fourth-Seed relocation ownership and consumed compiler-root identity."""
from dataclasses import asdict
from pathlib import Path
import collections
import subprocess
import sys
sys.dont_write_bytecode=True
import set_b_producer as P
import set_b_fourth_seed_20260926 as S
from set_b_fourth_inventory_20260926 import PATHS,AUTHORED,HASHES
from elf_truth import ElfTruth
ROOT=P.ROOT
INV=S.OUT/'inventory-r1'
OUT=S.OUT/'closure-r1'


def main():
    OUT.mkdir(exist_ok=False)
    assert [P.bind(p)['sha256'] for p in PATHS]==HASHES
    proof=P.load(INV/'receipt.json');assert proof['complete_inventory']
    funcs=P.load(INV/'instructions/function-instructions.json')
    other=P.load(INV/'allocated/remaining-relocations.json')['rows']
    ledger=[]
    for k,p in enumerate(PATHS):
        t=ElfTruth.read(p,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj');assigned={}
        def put(r,why):assigned[(r['source_section'],r['offset'])]=why
        for f in funcs:
            if f['status']=='PASS':
                for w in f['witnesses']:
                    for r in w['relocations'][k]:put(r['relocation'],'proved paired instruction expression')
            else:
                o=f['before' if k==0 else 'after'];assert o['name'] in AUTHORED
                for r in t.relocations:
                    if r.source_section==o['section'] and o['value']<=r.offset<o['value']+o['bytes']:put(asdict(r),'authored four-reader correction: '+o['name'])
        for r in other:
            v=r.get('before' if k==0 else 'after')
            if v and r.get('equivalent'):put(v,'proved data expression')
        for r in t.relocations:
            if r.relocation_type=='R_MOS_ADDR_ASCIZ':put(asdict(r),'proved BASIC SYS encoding')
            assert (r.source_section,r.offset) in assigned,('unclassified relocation',k,r)
        rows=[dict(relocation=asdict(r),family=assigned[(r.source_section,r.offset)]) for r in t.relocations]
        P.write(OUT/('before-relocations.json' if k==0 else 'after-relocations.json'),rows)
        ledger.append(dict(count=len(rows),families=dict(collections.Counter(r['family'] for r in rows))))
    old=P.load(ROOT/'build/set-b-product-r3/commands.json');new=P.load(S.PRODUCT/'commands.json')
    assert [[a.replace('build/set-b-product-r3','build/set-b-product-r4') for a in c] for c in old]==new
    roots=[];dep=[]
    for i,(a,b) in enumerate(zip(old,new)):
        if '-c' not in b:continue
        before=ROOT/a[a.index('-c')+1];after=ROOT/b[b.index('-c')+1]
        # All compilation roots are unchanged; four textual includes are the
        # sole native body edits, and the placement header is derived data.
        assert before.read_bytes()==after.read_bytes()
        roots.append(dict(index=i,before=P.bind(before),after=P.bind(after)))
        if after.name not in ('c2_product_runtime.c','card_l_stage.c'):continue
        c=b.copy();j=c.index('-o');del c[j:j+2];c.remove('-c');c+=['-M','-MT','root']
        run=subprocess.run(c,cwd=ROOT,capture_output=True,text=True);assert run.returncode==0,run.stderr
        path=OUT/(after.name+'.dependencies.txt');path.write_text(run.stdout+run.stderr)
        dependencies=run.stdout.replace('\\\n',' ').split(':',1)[1].split()
        rows=[P.bind((ROOT/d).resolve()) for d in dict.fromkeys(dependencies)]
        dep.append(dict(command_index=i,command=c,exit=run.returncode,log=P.bind(path),dependencies=rows))
    assert len(roots)==74 and len(dep)==2
    P.write(OUT/'compiler-inputs.json',dict(status='PASS',root_count=74,roots=roots,changed_owner_dependency_closure=dep,
        authority=S.require_auth(),sources=[P.bind(ROOT/p) for p in S.authority_files()]))
    P.write(OUT/'receipt.json',dict(status='PASS: COMPLETE FOURTH SEED INVENTORY',complete_inventory=True,
        unclassified_bytes=0,unclassified_relocations=0,seed=P.bind(PATHS[1]),source_authority=S.require_auth(),
        driver=P.bind(Path(__file__)),instruction_inventory=P.bind(INV/'receipt.json'),
        predecessor_closure=P.bind(ROOT/'build/set-b-r1/step4-r4/inventory-closure-r1/receipt.json'),
        relocations=ledger,compiler_inputs=P.bind(OUT/'compiler-inputs.json'),builds=0,links=0,guest_qualified=False))
    print('PASS: complete fourth Seed inventory; both relocation directions;74 unchanged roots',flush=True)

if __name__=='__main__':main()
