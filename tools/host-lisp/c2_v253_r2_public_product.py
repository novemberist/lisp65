#!/usr/bin/env python3
"""2.5.3 Final qualification and public-source reproduction.

preflight (private tree): public source authority + sealed Final binding,
  include authority, six-image plane regeneration, accepted-medium readback
  and layout reassembly, and a full media-recipe proof: in a fresh temporary
  directory under build/, all 20 D81 payloads are re-derived from the sealed
  Final ELF/PRG with public inputs only (including one cold-stager compile)
  and the D81 must equal 7df9db67 byte for byte. No product compile or link.
build (fresh exported public root only): c2_v253_r2_public_reproduction.
check: the retained reproduction receipt if present, else preflight.
"""
import argparse
import json
import shutil
import tempfile
from pathlib import Path

import c2_v253_r2_public_native as N

ROOT = N.ROOT
OUT = ROOT / 'build/public-v2.5.3'


def media_recipe_proof(stager_fixture=False):
    import c2_v253_r2_public_media_reproduction as MR
    a = N.load(N.AUTHORITY)
    work = Path(tempfile.mkdtemp(dir=ROOT / 'build', prefix='public-v253-preflight-'))
    try:
        pair = {}
        for role, name in (('ELF', 'resident-island-seed.prg.elf'), ('PRG', 'resident-island-seed.prg')):
            raw = N.bound(a['raw_pair'][role])
            (work / name).write_bytes(raw)
            pair[role] = work / name
        fixture = None
        if stager_fixture:
            import d81_persistence_fault as D
            fixture = work / 'autoboot.fixture'
            fixture.write_bytes(D.visible_files(N.bound(a['raw_pair']['D81']))[b'AUTOBOOT.C65'])
        result = MR.pack(pair['ELF'], pair['PRG'], work / 'media', stager_fixture=fixture)
        compiles = 0 if stager_fixture else 5
        summary = dict(status=result['status'], medium=dict(result['medium'], path='<temporary>'),
                       files=result['files'], stager=result['descriptor']['stager'].get('status', 'COMPILED'),
                       product_compiles=0, product_links=0, stager_and_host_abi_compiles=compiles,
                       scope='Final native pair as input; not a public reproduction')
        shutil.rmtree(work)
        return summary
    except BaseException:
        print('preflight media proof failed; diagnostics retained in ' + str(work))
        raise


def preflight(stager_fixture=False):
    result = dict(authority=N.check(private=True))
    import c2_v253_r2_public_includes as I
    import c2_v253_r2_public_plane as P
    import c2_v253_r2_public_overlays as O
    import c2_v253_r2_public_libraries as L
    import c2_v253_r2_public_media as M
    import c2_v253_r2_public_normalization as Z
    result['normalization'] = Z.selftest()
    result['includes'] = I.check()
    result['plane'] = P.check()
    for fam, t in O.policy()['families'].items():
        O.template_is_geometry(fam, t)
    result['libraries'] = L.check()
    result['media'] = M.check()
    result['media_controls'] = M.selftest()
    result['authority_controls'] = N.selftest()['mutations_rejected']
    result['media_recipe'] = media_recipe_proof(stager_fixture)
    ok = result['media_recipe']['status'] == 'PASS: PUBLIC MEDIA BYTEIDENTICAL'
    result['status'] = ('PASS: 2.5.3 FINAL IDENTITY, PUBLIC SOURCE AUTHORITY AND MEDIA RECIPE'
                        if ok else 'PREFLIGHT ONLY: stager fixture used')
    return result


def build():
    import c2_v253_r2_public_reproduction as R
    return R.build()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['preflight', 'check', 'build'])
    p.add_argument('--stager-fixture', action='store_true', help='preflight only: skip the cold-stager compile')
    a = p.parse_args()
    if a.mode == 'build':
        result = build()
    elif a.mode == 'check' and (OUT / 'reproduction.json').exists():
        import c2_v253_r2_public_reproduction as R
        result = R.check()
    else:
        result = preflight(a.stager_fixture)
    print(json.dumps(result, indent=2, default=str))
