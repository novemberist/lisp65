"""Existing-Seed follow-up: isolated canonical Lisp/C2I packing, no product link."""
from pathlib import Path
import copy
import traceback
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import bytecode_p0_stdlib as L
import c2_full_emission as F
import c2_lite_v6_product_probe as V6
ROOT=P.ROOT
OUT=ROOT/'build/set-b-load-preflight-pack-r1'
BASE=ROOT/'build/input-anchor-r2/plane/stdlib-p0.manifest.json'
SUITE=ROOT/'build/input-anchor-r2/candidate-suite.json'
CAND=ROOT/'build/set-b-load-repair-proposal-r5/candidate/lib/stdlib-require.lisp'

def main():
    S.require_auth();OUT.mkdir(exist_ok=False)
    sources=[];prices={};images={};manifests={}
    for label in ('before','candidate'):
        suite=copy.deepcopy(L._read_suite(str(SUITE)))
        if label=='candidate':
            old=next(p for p in suite['sources'] if p.endswith('stdlib-require-consumed.lisp'))
            forms=lambda p:{f[1]:f for f in L.C.parse_all(Path(p).read_text()) if isinstance(f,list) and len(f)>3 and f[0]=='defun'}
            assert forms(ROOT/old)==forms(ROOT/'lib/stdlib-require.lisp')
            suite['sources']=[str(CAND) if p==old else p for p in suite['sources']]
            suite['functions']+=['%require-charged-row-end','%require-charged-front']
            suite.setdefault('tailcall_self',[]).append('%require-charged-front')
        dest=OUT/label;dest.mkdir();sp=dest/'suite.json';P.write(sp,suite)
        for raw in suite['sources']:
            p=Path(raw);p=p if p.is_absolute() else ROOT/p
            sources.append(P.bind(p))
        result=L.emit_artifacts(str(sp),suite,str(dest/'stdlib-p0'))
        mp=dest/'stdlib-p0.manifest.json';m=P.load(mp);manifests[label]=m
        im=F.emit_image('stdlib-p0','stdlib',mp);images[label]=im
        (dest/'code.bin').write_bytes(im.code);(dest/'metadata.bin').write_bytes(im.metadata)
        prices[label]=dict(code=len(im.code),entries=len(im.manifest['entries']),resolutions=len(im.descriptors),roots=sum(d.kind in V6.ROOT_KINDS for d in im.descriptors),metadata=len(im.metadata),literal_nodes=len(m['literal_nodes']),literal_slots=sum(e['lit_count'] for e in m['entries']))
        P.write(dest/'emitter-result.json',result)
    baseline=F.emit_image('stdlib-p0','stdlib',BASE)
    assert images['before'].code==baseline.code and images['before'].metadata==baseline.metadata,'canonical before projection differs from consumed stdlib'
    delta={k:prices['candidate'][k]-prices['before'][k] for k in prices['before']}
    # Bind all five unchanged static companions to the consumed plane census.
    census=ROOT/'build/nested-error-recovery-product-r1-preflight/setup-owned/static-plane/narrow-static/product/substitution-artifacts.json'
    companions=[]
    for row in P.load(census)['manifests'][1:]:
        p=ROOT/row['path'];assert P.bind(p)==row;companions.append(row)
    raw=(ROOT/'build/set-b-load-attribution-r1/definitions-0/before-load-c2d.bin').read_bytes()
    counts={k:int.from_bytes(raw[a:a+2],'little') for k,a in [('images',12),('entries',16),('resolutions',20),('roots',24)]}
    newcounts={k:v+delta.get(k,0) for k,v in counts.items()}
    entry_names={e['name']:e for e in manifests['before']['entries']};diff=[]
    for e in manifests['candidate']['entries']:
        old=entry_names.get(e['name']);d=e['length']-(old['length'] if old else 0)
        if d or old is None:diff.append(dict(name=e['name'],before=old['length'] if old else 0,after=e['length'],delta=d))
    code_end=50691+delta['code'];assert code_end<60758
    P.write(OUT/'receipt.json',dict(status='PASS: CANONICAL HOST LISP/C2I PACKING PROJECTION',driver=P.bind(Path(__file__)),authority=S.require_auth(),
        before_manifest=P.bind(BASE),suite=P.bind(SUITE),candidate=P.bind(CAND),source_bindings=sources,unchanged_companions=companions,
        before_code_and_metadata_byte_identical=True,prices=prices,delta=delta,code_object_changes=diff,
        post_INIT=dict(before=counts,candidate=newcounts,code_end=code_end,headroom=dict(images=64-newcounts['images'],entries=2048-newcounts['entries'],resolutions=4096-newcounts['resolutions'],roots=1536-newcounts['roots'],code=60758-code_end)),
        limits='Host compiler/emitter only. Derived product headers, native LTO layout, media identity and cold execution remain unbuilt. No new product plane is installed.',product_builds=0,product_links=0,seeds=0,device_contacts=0,host_lisp_compilations=2))
    print('PASS canonical packing',delta,flush=True)

if __name__=='__main__':
    try:main()
    except BaseException:
        if OUT.exists():(OUT/'failure.txt').write_text(traceback.format_exc())
        raise
