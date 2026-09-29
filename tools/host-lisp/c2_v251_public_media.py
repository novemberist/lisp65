#!/usr/bin/env python3
"""Read back the bound Final medium; reconstruct through its accepted builder."""
import argparse
import json
from pathlib import Path
import c2_v251_public_native as N
import d81_persistence_fault as D81
AUTHORITY=N.ROOT/'config/c2-v251-public-media.json'
def check():
    a=json.loads(AUTHORITY.read_text());raw=N.bound(a['medium']);N.bound(a['native_elf']);N.bound(a['builder'])
    N.require(a['medium']['sha256']=='a2872fbd8aa53690da0fb7a7281bd2746497589a036c27fa3d7f302a8cafc445','wrong product D81')
    D81.validate_bam(raw);actual=D81.visible_files(raw)
    files={n.decode():dict(bytes=len(b),sha256=N.hashlib.sha256(b).hexdigest()) for n,b in actual.items()}
    N.require(files==a['files'],'Final medium file drift')
    N.require(actual[b'INIT.L65']==N.bound(a['init']),'wrong INIT')
    import c2_require_resolver_gate as L
    packages={r['name']:actual[r['name'].upper().encode()] for r in a['packages']}
    import comfort_library_medium as C
    bid=a['product_build_id']
    N.require(L.decode_index(actual[b'L65INDEX'],packages,artifact_build_id=bid)==a['packages'],'index drift')
    mutations=L.mutation_gate(actual[b'L65INDEX'],packages,artifact_build_id=bid)
    return dict(status='PASS: ACCEPTED FINAL MEDIUM READBACK',files=len(files),packages=len(packages),mutations=mutations,public_reproduction=False)
def pack_public(paths):
    """Fresh source-build consumer; no retained medium is used as input."""
    import c2_v251_public_media_reproduction as R
    return R.pack(paths)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['check']);p.parse_args()
    print(json.dumps(check(),indent=2))
