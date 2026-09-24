"""Project Set-A resident functions onto the consumed plane; host only."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

import bytecode_p0_stdlib as S
import c2_v200_release_shape_pricing as P
import c2_full_emission as F
from v2_workbench_codemod import C2_RESIDENT_COMPILER_SEAM

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'build/transient-retirement-product-r1-preflight/setup-owned/static-plane/narrow-static'


def definitions(text):
    starts=list(re.finditer(r'^\(defun ([^\s()]+)',text,re.M))
    return {m[1]:text[m.start():starts[i+1].start() if i+1<len(starts) else len(text)]
            for i,m in enumerate(starts)}


def bind(p):
    p=p.resolve(); raw=p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    out=ap.parse_args().out.resolve();out.mkdir(parents=True,exist_ok=False)
    manifest=BASE/'stdlib-p0.manifest.json';m=json.loads(manifest.read_text())
    suite=json.loads((ROOT/m['suite']).read_text())
    candidate=json.loads(json.dumps(suite))
    authored=ROOT/'lib/dialect-v2/eval-runtime.lisp'
    before=definitions(subprocess.check_output(
        ['git','show','91cbb479:lib/dialect-v2/eval-runtime.lisp'],cwd=ROOT,text=True))
    after=definitions(authored.read_text())
    added=set(after)-set(before)
    changed={n for n in before.keys() & after.keys()
             if S.C.parse_all(before[n])!=S.C.parse_all(after[n])}
    assert added=={'%c2-definition-group-p','%c2-run-definition-group'}
    assert changed=={'%c2-run-expanded'} and not set(before)-set(after)
    owners=[(i,ROOT/p) for i,p in enumerate(suite['sources'])
            if '%c2-run-expanded' in definitions((ROOT/p).read_text())]
    assert len(owners)==1
    i,source=owners[0];text=source.read_text();consumed=definitions(text)
    for name in changed:
        assert S.C.parse_all(consumed[name])==S.C.parse_all(before[name]),name
        text=text.replace(consumed[name],after[name],1)
    text+='\n'+''.join(after[n] for n in sorted(added))
    projection=out/'eval-runtime-consumed.lisp';projection.write_text(text)
    candidate['sources'][i]=str(projection.relative_to(ROOT))
    candidate['functions']+=sorted(added)
    candidate['prebuilt_primitive_functions']=list(C2_RESIDENT_COMPILER_SEAM)
    for label,value in [('baseline',suite),('candidate',candidate)]:
        path=out/f'stdlib-{label}-suite.json'
        path.write_text(json.dumps(value,indent=2)+'\n')
        prefix=out/f'stdlib-{label}'/'stdlib-p0';prefix.parent.mkdir()
        S.emit_artifacts(str(path),S._read_suite(str(path)),str(prefix),
                         base_addr=int(m['base_addr'],0),artifact_role=m['artifact_role'])
    remake=out/'stdlib-baseline/stdlib-p0.manifest.json';rm=json.loads(remake.read_text())
    a,ab=P.entries(manifest);b,bb=P.entries(remake)
    assert a.keys()==b.keys() and len(ab)==len(bb)
    for k in ('literal_nodes','literal_index','literal_patches','relocation','exports'):
        assert m[k]==rm[k],k
    for n in a:
        for k in ('blob_offset','length','literals'):assert a[n][k]==b[n][k],(n,k)
    patches={i for p in m['literal_patches'] for i in (p['blob_offset'],p['blob_offset']+1)}
    assert {i for i,(x,y) in enumerate(zip(ab,bb)) if x!=y}<=patches
    target=out/'stdlib-candidate/stdlib-p0.manifest.json';ce,cb=P.entries(target)
    assert set(ce)-set(a)==added and not set(a)-set(ce)
    delta={n:ce.get(n,{}).get('length',0)-a.get(n,{}).get('length',0) for n in set(a)|set(ce)}
    assert sum(delta.values())==len(cb)-len(ab)
    assert max(e['length'] for e in ce.values())<=255
    result=dict(status='PASS: RESIDENT COMPOSITION, NOT NATIVE ACCEPTANCE',
        baseline=bind(manifest),authored=bind(authored),consumed=bind(source),
        projection=bind(projection),manifest=bind(target),baseline_relocation_equivalent=True,
        delta=dict(code_bytes=len(cb)-len(ab),functions={n:d for n,d in sorted(delta.items()) if d},
                   largest_object=max(e['length'] for e in ce.values())),
        added_functions=sorted(added),budget=dict(seed=0,final=0,product_link=0),
        remaining=['integrated native group/capacity witnesses',
                   'whole-card producer admission'])
    package=ROOT/'build/library-delivery-r1/raw/defstruct.manifest.json'
    pm=json.loads(package.read_text());ps=json.loads((ROOT/pm['suite']).read_text())
    ps['resident_suite']=str((ROOT/pm['suite']).parent/ps['resident_suite'])
    assert ps['sources']==['lib/defstruct.lisp']
    old_source=out/'defstruct-before.lisp'
    old_source.write_bytes(subprocess.check_output(
        ['git','show','91cbb479:lib/defstruct.lisp'],cwd=ROOT))
    package_manifests={}
    for label,src in [('baseline',old_source),('candidate',ROOT/'lib/defstruct.lisp')]:
        cfg=json.loads(json.dumps(ps));cfg['sources']=[str(src.relative_to(ROOT))]
        path=out/f'defstruct-{label}-suite.json';path.write_text(json.dumps(cfg,indent=2)+'\n')
        prefix=out/f'defstruct-{label}'/'defstruct';prefix.parent.mkdir()
        S.emit_artifacts(str(path),S._read_suite(str(path)),str(prefix),
                         base_addr=int(pm['base_addr'],0),artifact_role=pm['artifact_role'])
        package_manifests[label]=prefix.with_suffix('.manifest.json')
    pa,pab=P.entries(package);pb,pbb=P.entries(package_manifests['baseline'])
    # Host heap handles are relocation inputs, not delivered code. Prove the
    # same relocation population and byteidentical emitted C2I, never mask a
    # non-literal byte or accept size equality as source identity.
    pbm=json.loads(package_manifests['baseline'].read_text())
    assert pa.keys()==pb.keys() and len(pab)==len(pbb)
    for k in ('literal_nodes','literal_index','literal_patches','relocation','exports'):
        assert pm[k]==pbm[k],k
    for n in pa:
        for k in ('blob_offset','length','literals'):assert pa[n][k]==pb[n][k],(n,k)
    pp={i for p in pm['literal_patches'] for i in (p['blob_offset'],p['blob_offset']+1)}
    assert {i for i,(x,y) in enumerate(zip(pab,pbb)) if x!=y}<=pp
    old_image=F.emit_image('defstruct','DEFSTRUCT',package)
    remade_image=F.emit_image('defstruct','DEFSTRUCT',package_manifests['baseline'])
    assert old_image.code==remade_image.code and old_image.metadata==remade_image.metadata
    pc,pcb=P.entries(package_manifests['candidate'])
    assert pa.keys()==pc.keys()
    pdelta={n:pc[n]['length']-pa[n]['length'] for n in pa}
    assert sum(pdelta.values())==len(pcb)-len(pab)
    assert {n for n,d in pdelta.items() if d}=={'%defstruct-expansion'}
    result['package']=dict(baseline=bind(package),candidate=bind(package_manifests['candidate']),
        baseline_c2i_byteidentical=True,code_bytes_delta=len(pcb)-len(pab),
        largest_object=max(e['length'] for e in pc.values()),
        functions={n:d for n,d in pdelta.items() if d})
    result['total_bank2_delta']=len(cb)-len(ab)+len(pcb)-len(pab)
    currency_path=ROOT/'build/transient-retirement-r2/currency-proof.json'
    currency=json.loads(currency_path.read_text())
    assert currency['status']=='PASS'
    free=currency['free']['code']
    assert free==currency['measured']['limit']-currency['measured']['persistent_front']
    owner_path=ROOT/'config/storage-owner-manifest.json'
    floor=json.loads(owner_path.read_text())['floors']['user_code']
    projected=free-result['total_bank2_delta']
    result['user_code_projection']=dict(accepted_executed=free,
        candidate=projected, manifest_floor=floor, below_floor=max(0,floor-projected),
        currency=bind(currency_path), owners=bind(owner_path),
        claim='Projection only; no candidate native currency stop')
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
