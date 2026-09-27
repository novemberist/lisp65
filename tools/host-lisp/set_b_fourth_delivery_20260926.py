"""Fourth Seed delivery/readback successor; reuse the linked ELF only.

Historical delivery and readback tools remain immutable. Every runtime-link
path remains forbidden. Four cold delivery stager links are separately priced.
"""
import argparse
import inspect
from pathlib import Path
import traceback
import set_b_producer as P
import set_b_fourth_seed_20260926 as S
import set_b_seed_delivery_20260926 as D
import set_b_seed_readback_20260926 as R
ROOT=P.ROOT
OUT=ROOT/'build/set-b-seed-medium-r5'
SHA='2ba1deb4004ee7115dc673f29395ff1a0a7f91a437ff1f8d3b45d4fd197f9919'
OLD='1eb22d5282acae5e39c1a1ea37bd749d6e524c9fb45005791b298a26bb5b71cf'


def main(mode):
    parent=D if mode=='deliver' else R
    src=inspect.getsource(parent.main)
    assert src.count(OLD)==1;src=src.replace(OLD,SHA)
    replacements=[dict(before=OLD,after=SHA)]
    if mode=='deliver':
        for a,b in [("build/set-b-r1/step4-r4/inventory-closure-r1/receipt.json","build/set-b-r1/step4-r5/closure-r1/receipt.json"),
                    ('P.require_auth()','S.require_auth()'),('current source 7a4e43fa','current source 958a7d2a')]:
            assert src.count(a)==1;src=src.replace(a,b);replacements.append(dict(before=a,after=b))
    proof=S.OUT/('delivery-'+mode+'-executed.py');assert not proof.exists();proof.write_text(src)
    P.write(S.OUT/('delivery-'+mode+'-invocation.json'),dict(driver=P.bind(Path(__file__)),parent=P.bind(Path(parent.__file__)),
        executed=P.bind(proof),replacements=replacements,seed=P.bind(S.PRODUCT/'wplto/resident-island-seed.prg.elf'),product_links=0))
    ns=dict(vars(parent));ns.update(S=S,SEED=S.PRODUCT/'wplto',OUT=OUT,__file__=__file__)
    exec(compile(src,str(proof),'exec'),ns)
    try:ns['main'](*([OUT] if mode=='deliver' else []))
    except Exception:
        if OUT.exists():P.write(OUT/(mode+'-failure.json'),dict(status='HALT',error=traceback.format_exc(),driver=P.bind(Path(__file__))))
        raise

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['deliver','readback']);a=ap.parse_args();main(a.mode)
