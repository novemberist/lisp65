"""Fifth Seed media consumer: actual catalogs, late owner and preserved mutations."""
import argparse
from copy import deepcopy
from pathlib import Path
import set_b_producer as P
import set_b_fifth_seed_20260926 as S
import set_b_seed_readback_20260926 as R
import card_l_media_manifest_20260925 as K
ROOT=P.ROOT
HERE=ROOT/'build/set-b-seed-medium-r6'
RECEIPT=ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/set-b-media-manifest-receipt-20260926.json'


def validate(files,bm,sm,late):
    assert len(bm['slices'])==17 and len(sm['slices'])==63
    assert [r['id'] for r in bm['slices']]==list(range(17))
    assert [r['id'] for r in sm['slices']]==list(range(63))
    assert len(late)==8192 and files[b'BOOT.BIN'][0x4e00:0x6e00]==late
    return R.catalogs(files,bm,sm,late)


def derive():
    S.require_auth();prior=K.selftest()
    readback=P.load(HERE/'readback.json');assert readback['status']=='PASS: INDEPENDENT MEDIA READBACK'
    medium=HERE/'media-seed/set-b-comfort.d81'
    assert readback['medium']==P.bind(medium)
    assert readback['elf']['sha256']==P.load(S.PRODUCT/'linked.json')['elf']['sha256']
    assert readback['lisp_plane_byte_identical'] and readback['comfort_byte_identical']
    files=R.descriptor(HERE/'media-seed',medium)
    bm=P.load(HERE/'media-seed/boot-manifest.json');sm=P.load(HERE/'media-seed/session-manifest.json')
    late=(HERE/'media-seed/set-b-tenants.bin').read_bytes();rows=validate(files,bm,sm,late)
    trials=[]
    for family in ['boot','session']:
        for kind in ['old-count','missing-record','payload-corruption']:
            f=dict(files);b,s=deepcopy(bm),deepcopy(sm);m=b if family=='boot' else s
            if kind=='old-count':m['catalog']['slice_count']-=1
            elif kind=='missing-record':m['slices'].pop()
            else:
                name=b'BOOT.BIN' if family=='boot' else b'SESSION.BIN';v=bytearray(f[name]);v[-1]^=1;f[name]=bytes(v)
            trials.append((family+'-'+kind,f,b,s,late))
    for slot in range(56,63):
        s=deepcopy(sm);s['slices'][slot]['source_address']+=256
        trials.append(('late-source-'+str(slot),files,bm,s,late))
    b=deepcopy(bm);b['slices'][16]['record_crc16']^=1;trials.append(('record-crc',files,b,sm,late))
    wrong=bytearray(late);wrong[-1]^=1;trials.append(('late-tail',files,bm,sm,bytes(wrong)))
    rejected=[]
    for label,f,b,s,l in trials:
        try:validate(f,b,s,l)
        except AssertionError:rejected.append(label)
        else:raise AssertionError('surviving mutation '+label)
    return dict(status='PASS: SET B FIFTH SEED MEDIA CONSUMER',source_authority=S.require_auth(),catalogs=dict(boot=17,session=63),records=rows,
        inherited_mutations=prior,mutations=rejected,lisp_plane_unchanged=True,comfort_unchanged=True,
        inputs=[P.bind(p) for p in [medium,HERE/'readback.json',HERE/'media-seed/boot-manifest.json',HERE/'media-seed/session-manifest.json',HERE/'media-seed/set-b-tenants.bin',Path(__file__),Path(R.__file__),Path(K.__file__)]],product_links=0)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['prepare','check','selftest']);a=ap.parse_args();v=derive()
    if a.action=='prepare':assert not RECEIPT.exists();P.write(RECEIPT,v)
    elif a.action=='check':assert P.load(RECEIPT)==v
    print('Set B media consumer PASS 80 records; mutations',len(v['mutations']))
if __name__=='__main__':main()
