"""Positive activation on the fifth Seed with the existing qualified observer."""
import argparse
import inspect
from pathlib import Path
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_seed_boot_20260926 as B
ROOT=P.ROOT


def main(out,role):
    source=inspect.getsource(B.main)
    old='build/set-b-product-r3/wplto/resident-island-seed.prg.elf';new='build/set-b-product-r5/wplto/resident-island-seed.prg.elf'
    assert source.count(old)==1;source=source.replace(old,new)
    proof=S.OUT/'boot-executed.py'
    if proof.exists():assert proof.read_text()==source
    else:proof.write_text(source)
    P.write(S.OUT/('boot-'+role+'-invocation.json'),dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(B.__file__)),
        executed=P.bind(proof),replacements=[dict(before=old,after=new)],medium_root='build/set-b-seed-medium-r6',product_links=0))
    ns=dict(vars(B));ns.update(MEDIAROOT=ROOT/'build/set-b-seed-medium-r6',__file__=__file__)
    exec(compile(source,str(proof),'exec'),ns);ns['main'](out,role)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--role',choices=['baseline','candidate'],required=True);a=ap.parse_args();main(a.out.resolve(),a.role)
