"""Owner-authorized read-path correction: fresh admission, one fifth Seed.

The historical producer stays byte-identical. Its exact functions execute in
an explicit namespace with only authority and output paths rebound. No retry.
"""
import argparse
import copy
import hashlib
import inspect
from pathlib import Path
import re
import shutil
import subprocess
import traceback
import set_b_producer as P
import boot_name_index_link_preprobe as L
import runtime_overlay_bank as B
import set_b_seed_media as M
from elf_truth import ElfTruth

ROOT=P.ROOT
AUTH='e0ea5447'
OUT=ROOT/'build/set-b-r1/step4-r6'
PRODUCT=ROOT/'build/set-b-product-r5'
REV=ROOT/'config/set-b-native/transaction-revision.json'
SEAL=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/set-b-transaction-boundary-repair-20260926.json'


def authority_files():
    return sorted(set(P.authority_files()+[str(Path(__file__).relative_to(ROOT)),
        'tools/host-lisp/set_b_transaction_final_20260926.py',
        'config/set-b-native/qualification-successors.json']))


def require_auth():
    assert AUTH!='AUTH_PENDING','Source authority commit not bound'
    commit=subprocess.check_output(['git','rev-parse',AUTH+'^{commit}'],cwd=ROOT,text=True).strip()
    for name in authority_files():
        old=subprocess.check_output(['git','show',commit+':'+name],cwd=ROOT)
        new=(ROOT/name).read_bytes()
        if name==str(Path(__file__).relative_to(ROOT)):
            norm=lambda b:re.sub(rb'^AUTH=[^\n]+',b'AUTH=POINTER',b,flags=re.M)
            old,new=norm(old),norm(new)
        assert old==new,('authority drift',name)
    return commit


def namespace():
    ns=dict(vars(P));ns.update(require_auth=require_auth,AUTH=AUTH,RESIDENT_ADMISSION_LIMIT=439,PROJECTION_RECEIPT=ROOT/'config/set-b-native/resident-439.json',authority_files=authority_files);transforms=[]
    for name,old,new in [('command_probe',"out=HERE/'step3/command-preview'","out=ROOT/'build/set-b-r1/step4-r6/command-preview'"),
        ('seed',"out=HERE/'seed'","out=ROOT/'build/set-b-product-r5'")]:
        source=inspect.getsource(getattr(P,name));assert source.count(old)==1
        source=source.replace(old,new,1);path=OUT/(name+'-executed.py')
        if path.exists():assert path.read_text()==source
        else:path.write_text(source)
        exec(compile(source,str(path),'exec'),ns)
        transforms.append(dict(function=name,before=old,after=new,executed=P.bind(path)))
    return ns,transforms


def preflight():
    assert not OUT.exists() and not PRODUCT.exists(),'Fresh output required'
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT),'Commit before preflight'
    OUT.mkdir(parents=True)
    try:
        auth=require_auth();revision=P.load(REV);allowed=set(revision['authored_sources'])|{
            'config/set-b-native/set-b-inputs.json','config/set-b-native/set-b-placement.h','config/set-b-native/include-closure.json','config/set-b-native/placement-revision.json','config/set-b-native/qualification-successors.json'}
        checked=[];changes=[];seal=P.load(SEAL)
        for row in seal['inputs']+[r['copy'] for r in seal['receipt_copies']]:
            actual=P.bind(ROOT/row['path'])
            if actual!=row:
                name=str((ROOT/row['path']).resolve().relative_to(ROOT))
                assert name in allowed,('unadmitted predecessor drift',name)
                old=subprocess.check_output(['git','show','95d36be5:'+name],cwd=ROOT)
                assert hashlib.sha256(old).hexdigest()==row['sha256']
                target=OUT/'previous-source'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(old)
                changes.append(dict(before=row,after=actual,preserved=P.bind(target)))
            else:checked.append(actual)
        # Authoritative candidate bytes are precisely the already priced patch.
        for name in revision['authored_sources']:
            expected=ROOT/'build/set-b-transaction-proposal-r1/candidate'/name
            assert (ROOT/name).read_bytes()==expected.read_bytes(),name
        for row in P.load(P.INPUTS)['sources']:assert P.bind(ROOT/row['path'])==row
        extent,tenants=P.late_partition();assert extent==6752
        header=(ROOT/'config/set-b-native/set-b-placement.h').read_text()
        for t in tenants:
            assert f'#define SET_B_{t["slot"]}_OFFSET 0x{t["offset"]:04X}u' in header
        image,rows=M.dry_tenants()
        items=[B.ExtractedSlice(B.SliceSpec(i,t['name'],t['section'],t['start_symbol'],t['end_symbol'],t['entry_symbol'],6,1,0,region_id=3),0xc356,0xc356+len(t['payload']),0xc356,t['payload']) for i,t in enumerate(rows)]
        raw,overflow,parsed=B.build_region_images(items,profile_build_id=0x94ad170b,expected_vma=0xc356,max_slice_bytes=1792,format_version=4,payload_alignment=32)
        assert parsed.late_image==image and not overflow and image[extent:]==bytes([0xa5])*1440
        (OUT/'fixture-catalog.bin').write_bytes(raw);(OUT/'fixture-late.bin').write_bytes(image)
        ns,transforms=namespace();preview=ns['command_probe']()
        commands=P.load(preview/'commands.json');normalized=[]
        for c in commands:
            c=list(c)
            if '-c' in c:
                assert c[-1]=='-DLISP65_SET_B';flag=c.pop();c.insert(c.index('-c'),flag)
            normalized.append(c)
        proof=preview/'wplto/command-proof.json';P.write(proof,dict(commands=normalized))
        baseline=OUT/'baseline-proof';baseline.mkdir()
        P.write(baseline/'command-proof.json',P.load(P.BASE/'final-command-consumption.json'))
        shutil.copyfile(P.BASE/'wplto/c2-substitution.ld',baseline/'c2-substitution.ld')
        shutil.copytree(P.BASE/'wplto/full-map-linker',baseline/'full-map-linker')
        print('Fresh symbol and E000 object admission',flush=True)
        link=L.run_preprobe(proof,OUT/'link-preprobe',baseline/'command-proof.json')
        assert link['status']=='PASS',link['new_findings']
        edge=L.e000_low_edges_receipt([ROOT/p for p in link['objects']],sorted((OUT/'link-preprobe/baseline/objects').glob('*.o')))
        P.write(OUT/'e000-edges.json',edge);assert edge['status']=='PASS',edge['new_findings_keys']
        runtime=next(ROOT/p for p in link['objects'] if Path(p).name=='005-c2_product_runtime.c.o')
        truth=ElfTruth.read(runtime,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
        prices=[]
        for i,t in enumerate(tenants):
            size=truth.section(t['section']).bytes
            limit=tenants[i+1]['offset'] if i+1<len(tenants) else extent
            interval=limit-t['offset']
            expected=ElfTruth.read(ROOT/'build/set-b-transaction-proposal-r1/after/005-c2_product_runtime.c.o',llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj').section(t['section']).bytes
            assert size==expected and size<=interval-16,(t['name'],size,expected)
            prices.append(dict(slot=t['slot'],object_bytes=size,interval=interval))
        assert truth.symbol('c2_retire_run').bytes+truth.symbol('c2_retire_call').bytes==348
        P.write(OUT/'admission.json',dict(status='PASS',authority=auth,driver=P.bind(Path(__file__)),
            predecessor=P.bind(SEAL),unchanged_bindings=checked,admitted_changes=changes,revision=P.bind(REV),
            transformations=transforms,sources=[P.bind(ROOT/p) for p in authority_files()],
            command_preview=P.bind(preview/'commands.json'),symbol_probe=P.bind(OUT/'link-preprobe/receipt.json'),
            e000_probe=P.bind(OUT/'e000-edges.json'),prices=prices,extent=extent,tail=1440,
            product_links=0,seeds=0,exact_linked_inventory='PENDING'))
        print('PASS fresh admission; fifth Seed remains unconsumed',flush=True)
    except Exception as e:
        P.write(OUT/'preflight-halt.json',dict(status='HALT',error=str(e),traceback=traceback.format_exc(),product_links=0,seeds=0))
        raise


def seed():
    assert not PRODUCT.exists() and not (OUT/'seed-invocation.json').exists(),'No implicit Seed retry'
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT),'Commit before execution'
    auth=require_auth();admission=P.load(OUT/'admission.json');assert admission['status']=='PASS'
    for row in admission['sources']:assert P.bind(ROOT/row['path'])==row
    ns,transforms=namespace()
    P.write(OUT/'seed-invocation.json',dict(authority=auth,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        driver=P.bind(Path(__file__)),admission=P.bind(OUT/'admission.json'),transformations=transforms,
        attempt=5,cumulative_seed_ceiling=5,cumulative_product_link_ceiling=5,retry=False))
    try:
        ns['seed']()
        P.write(OUT/'seed-result.json',dict(status='PASS: LINKED AND EXTRACTED; INVENTORY AND EXECUTION PENDING',retry=False))
        print('PASS fifth Seed linked and extracted',flush=True)
    except Exception as e:
        P.write(OUT/'seed-result.json',dict(status='HALT',error=str(e),traceback=traceback.format_exc(),retry=False))
        raise

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['preflight','seed']);a=ap.parse_args()
    preflight() if a.mode=='preflight' else seed()
