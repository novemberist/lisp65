#!/usr/bin/env python3
"""New A round authorized by 67ae5544; preserve the stopped r1 evidence."""
from pathlib import Path
import hashlib
import subprocess
import sys
import tempfile
import capacity_lever_a_product_card as P

ROOT,C,F,B,A=P.ROOT,P.C,P.F,P.B,P.A
REF='ecc51fa408e0ef2ead61ee6716d1e13f4c370a82'
AUTH='67ae5544'
BUILD=ROOT/'build/capacity/lever-a-product-r2'
PREFLIGHT=ROOT/'build/capacity/lever-a-product-r2-preflight'
ORIGINAL_CONFIGURE=P.configure
ORIGINAL_AUTHORITY=P.authority
ORIGINAL_GATE=P.source_gate
ORIGINAL_MATERIALIZE=P.materialize
ASM={
 'src/c2_kernal_window.s':('c2_backstop_rtov_busy','c2_backstop_rtov_loaded_len',
                         'lisp_toplevel_active','c2_backstop_pending_code'),
 'src/c2_boot_chain_commit.s':('vm_boot_overlay_status',),
}

def sources():
    import re
    result={}
    for name,targets in ASM.items():
        old=subprocess.check_output(['git','show',P.REF+':'+name],cwd=ROOT)
        new=subprocess.check_output(['git','show',REF+':'+name],cwd=ROOT)
        # HEAD may carry the predecessor or the exact landed correction.
        # A third form is never an admissible input.
        assert (ROOT/name).read_bytes() in (old,new), 'assembler source drift'
        projected=old
        for target in targets:
            projected,n=re.subn(rb'^[ \t]*\.zeropage[ \t]+'+target.encode()+rb'\n',b'',projected,flags=re.M)
            assert n==1
        assert projected==new,'non-commissioned assembler change'
        result[name]=new
    assert b'.zeropage\tmem_oom' in result['src/c2_boot_chain_commit.s']
    assert subprocess.check_output(['git','show',REF+':src/vm.c'],cwd=ROOT)==subprocess.check_output(
        ['git','show',P.REF+':src/vm.c'],cwd=ROOT)
    return result

def authority():
    value=ORIGINAL_AUTHORITY()
    value.update(patch_commit=REF,vm_patch_commit=P.REF,round='r2-after-ZP-contract-disposition',
        prior_round_consumed=dict(seed_WPLTO=1,final_C_LTO=0,product_links=0,host_images=0),
        gc_time_wall='required; no growth claim until measured on candidate')
    return value

def source_gate():
    value=ORIGINAL_GATE()
    value['base_adapter']=value.pop('adapter')
    value['adapter']=C.bind(Path(__file__))
    value.pop('only_changed_product_root')
    value['allowed_changed_product_roots']=['vm.c','c2_kernal_window.s','c2_boot_chain_commit.s']
    value['assembly_projection']={name:hashlib.sha256(raw).hexdigest() for name,raw in sources().items()}
    value['declared_removals']={name:list(targets) for name,targets in ASM.items()}
    return value

def materialize(out):
    mapping=ORIGINAL_MATERIALIZE(out)
    for name,raw in sources().items():
        target=out/'generated-product-sources'/Path(name).name
        target.write_bytes(raw)
        mapping[(ROOT/name).resolve()]=target
    return mapping

def profile(mapping=None):
    assert mapping
    by_name={p.name:p for p in mapping.values()}
    lines=A.PREDECESSOR['PROFILE'].read_text().splitlines()
    changes=[];population=[]
    for i,line in enumerate(lines):
        if not line.startswith('input_sha256='):continue
        name,previous=line.split('=',1)[1].rsplit(':',1)
        before=(ROOT/name).resolve()
        assert C.bind(before)['sha256']==previous,name
        target=(by_name.get(before.name,before) if '/generated-product-sources/' in name
                else mapping.get(before,before))
        digest=C.bind(target)['sha256']
        successor=((F.WPLTO/'generated-product-sources'/target.name).relative_to(ROOT).as_posix()
                   if target in mapping.values() else name)
        lines[i]=f'input_sha256={successor}:{digest}'
        population.append(dict(before=name,after=successor,sha256=digest))
        if digest!=previous:changes.append(dict(predecessor=name,successor=successor,before=previous,after=digest))
    assert {Path(r['predecessor']).name for r in changes}=={'vm.c','c2_kernal_window.s','c2_boot_chain_commit.s'}
    assert len(changes)==3 and len(population)==len({r['after'] for r in population})
    C.BOUND_PROFILE.write_text('\n'.join(lines)+'\n')
    assert A.features(C.BOUND_PROFILE)==A.features(A.PREDECESSOR['PROFILE'])
    return dict(predecessor=C.bind(A.PREDECESSOR['PROFILE']),successor=C.bind(C.BOUND_PROFILE),
                changes=changes,population=population,feature_authority=B.feature_authority())

def configure():
    P.BUILD,P.PREFLIGHT,P.AUTHORIZATION=BUILD,PREFLIGHT,AUTH
    P.authority,P.source_gate,P.materialize,P.profile=authority,source_gate,materialize,profile
    ORIGINAL_CONFIGURE()
    for module in (F,C,C.B):
        module.DRIVER=Path(__file__).resolve()
        module.FORMAT='capacity-lever-a-r2'

def final_product():
    """One final C/LTO/link, replaying but never rebuilding the frozen seed."""
    import capacity_disk_window_media as media
    configure()
    evidence=ROOT/'build/capacity/lever-a-r1'
    price=C.load(evidence/'r2-seed-price.json')
    assert price['text_gain']>0 and price['text_reserve']>=price['text_floor']
    zp=C.load(evidence/'r2-zp-proof.json');assert zp['status']=='PASS'
    lanes=C.load(evidence/'r2-lanes.json')
    gc_path=ROOT/'build/capacity/lever-a-gc-seed-r2/receipt.json'
    gc=C.load(gc_path);assert gc['status']=='PASS'
    seed=F.WPLTO/'resident-island-seed.prg'
    paths=[Path(str(seed)+s) for s in ('','.elf','.lto.o','.map')]
    frozen=[C.bind(p) for p in paths]
    assert frozen==C.load(PREFLIGHT/'seed-attempt.json')['artifacts']
    for value in (price,zp,lanes):assert value['seed']['sha256']==frozen[1]['sha256']
    assert all(r['ELF']['sha256']==frozen[1]['sha256'] for r in gc['rows'] if r['world']=='candidate')
    prerequisites=[evidence/n for n in ('r2-seed-price.json','r2-zp-proof.json','r2-lanes.json')]+[gc_path]
    for value in (price,zp,lanes):
        item=value['seed'];assert C.bind(ROOT/item['path'])['sha256']==item['sha256']
    source_gate()
    assert not subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=ROOT)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    assert head==subprocess.check_output(['git','rev-parse','@{upstream}'],cwd=ROOT).decode().strip()
    stamp=BUILD/'final-product-invocation.json'
    assert not stamp.exists() and not F.PRG.exists() and not F.ELF.exists()
    original=B.PRODUCT.compile_link
    B.PRODUCT.overlay_pack_family=media.pack_family
    B.PRODUCT._validate_family_artifact=media.validate
    B.PRODUCT._family_identity_negative_selftest=media.negative
    media.FINAL=F.WPLTO
    materializer=B.LEAF.materialize_candidate_sources
    existing=F.WPLTO/'generated-product-sources'
    calls=[]
    def reuse(out):
        with tempfile.TemporaryDirectory(dir=BUILD,prefix='final-source-check-') as tmp:
            mapping=materializer(Path(tmp))
            digest=lambda directory:{p.name:C.bind(p)['sha256'] for p in directory.iterdir() if p.is_file()}
            assert digest(existing)==digest(Path(tmp)/'generated-product-sources')
            return {s:existing/p.name for s,p in mapping.items()}
    def finish(out,name,headers,artifacts,**kwargs):
        assert out==F.WPLTO and frozen==[C.bind(p) for p in paths]
        calls.append(name)
        if name==seed.name:
            assert calls==[seed.name]
            B.PRODUCT.final_section_inventory_gate(out,seed)
            B.PRODUCT.lto_partition_metadata_gate(out,seed)
            return seed
        assert calls==[seed.name,F.PRG.name]
        return original(out,name,headers,artifacts,**kwargs)
    stamp.write_bytes(C.canonical(dict(authority=authority(),commit=head,seed=frozen,
        prerequisites=[C.bind(p) for p in prerequisites],seed_rebuilds=0,
        budget=dict(seed_WPLTO=1,final_C_LTO=1,product_links=1))))
    B.LEAF.materialize_candidate_sources=reuse
    B.PRODUCT.compile_link=finish
    try:
        try:C.B.child('_produce')
        except SystemExit as stop:assert stop.code==0
    finally:
        B.LEAF.materialize_candidate_sources=materializer
        B.PRODUCT.compile_link=original
        after=[C.bind(p) for p in paths]
        (BUILD/'final-product-attempt.json').write_bytes(C.canonical(dict(calls=calls,
            seed_before=frozen,seed_after=after,ELF_present=F.ELF.exists(),PRG_present=F.PRG.exists(),
            seed_rebuilds=0,final_C_LTO_invocations=int(F.PRG.name in calls))))
        assert frozen==after

def main():
    B.configure=A.configure=configure
    if sys.argv[1:]==['preflight']:
        A.preflight()
        for path,role in ((F.PLANE_RECEIPT,'plane'),(F.PREFLIGHT_RECEIPT,'preflight')):
            value=C.load(path);assert value['authority']==authority()
            value['format']='capacity-lever-a-r2-'+role
            path.write_bytes(C.canonical(value))
        print('A r2 preflight PASS: three source roots, no new product invocation')
    elif sys.argv[1:]==['seed']:
        B.produce_seed()
    elif sys.argv[1:]==['final-product']:
        final_product()
    else:raise SystemExit('Choose preflight, seed, or qualified final-product')

if __name__=='__main__':main()
