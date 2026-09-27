"""Capacity readback from delivered Card L catalogs, not pre-pack intermediates."""
import json
import re
from pathlib import Path
import set_b_producer as P
import slice_capacity_preflight_20260924 as C
OUT=P.ROOT/'build/set-b-r1/step4-r2/capacity-delivered'
BASE=P.ROOT/'build/card-l-seed-medium-r2'

def main():
    OUT.mkdir(exist_ok=False);world=OUT/'world';world.mkdir()
    paths=[]
    for family in ['boot','session']:
        p=BASE/'media-seed'/f'{family}-manifest.json';m=P.load(p)
        assert m['catalog']['slice_count']==(17 if family=='boot' else 56)
        P.write(world/f'runtime-overlays-{family}-final.json',m);paths.append(P.bind(p))
    profile=(BASE/'materialized/resolved-profile.txt').read_text()
    for key,value in [('session_family_slice_count',56),('boot_family_slice_count',17),('slice_count_unique',64)]:
        profile,count=re.subn(r'(?m)^'+key+r'=.*$',key+'='+str(value),profile)
        assert count==1,(key,count)
    (world/'resolved-profile.txt').write_text(profile)
    assert C.main(['--medium',str(world),'--out',str(OUT/'dated')])==0
    w=C.PRE.load_world(world)
    assert w['families']['session']['region0']['free']==491
    assert C.directory_step(56,7)==0
    P.write(OUT/'receipt.json',dict(status='PASS',inputs=paths,driver=P.bind(Path(__file__)),
        predecessor_intermediate_receipt='build/set-b-r1/step4-r2/capacity/slice-capacity-preflight-20260924.json',
        correction='Earlier probe used pre-pack 55/12 catalogs; this successor uses delivered 56/17 catalogs. Original receipt retained.',
        projection=dict(session_before=56,session_after=63,boot=17,session_free_after=1,
            directory_growth=C.directory_step(56,7),region0_free=491,region1_free=140,region2_free=872,
            region3_capacity=8192,journal_owner_bytes=96,journal_bytes=72),
        unique_policy='64 unique before; 71 after is the bound source spec population, not a shared 64 runtime cap; Session 63 and Boot 17 separately. Region3/slot proof supplements legacy tool without weakening it.',
        seed_invocations=0,product_links=0))
if __name__=='__main__':main()
