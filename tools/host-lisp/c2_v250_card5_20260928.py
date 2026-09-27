#!/usr/bin/env python3
"""Dated Card-5 successor, preserving the historical runtime build lifecycle.

The v250 direct producer is an additional candidate entry. Existing Make
lifecycles and the v240 runtime guide commands remain unchanged.
"""
import argparse
import hashlib
import json
import comfort_default_card5_r2_20260927 as H
G=H.P
H.K.ROUTES = dict(H.K.ROUTES, **{
    "block-26-build-integrity-check": "c2_v250_card5_20260928.py",
    "c2-media-builder-closure-enumeration-check": "c2_v250_media_census_20260928.py",
})

RECEIPT=G.ROOT/'config/c2-v250-card5-receipt-public-era-20260928.json'

CHECK_HOST_ROUTES = {
    'mk/gates.mk': {
        'v240-public-native-check': ['c2_v240_release_preflight_20260928.py'],
        'public-naming-audit-selftest': ['c2_v250_public_naming_20260928.py selftest'],
        'public-naming-audit-check': ['c2_v250_public_naming_20260928.py check'],
    },
    'mk/workbench.mk': {
        'v11-l-lite-keymap-check': ['c2_v250_keymap_20260928.py selftest',
                                  'c2_v250_keymap_20260928.py check'],
    },
}

def check_host_routing(texts):
    import re
    for path, targets in CHECK_HOST_ROUTES.items():
        for target, commands in targets.items():
            match = re.search(r'^' + re.escape(target) + r':[^\n]*\n((?:\t[^\n]*\n)+)',
                              texts[path], re.M)
            for command in commands:
                G.require(match and 'tools/host-lisp/' + command in match[1],
                          'v250 check-host route drift: ' + target + ': ' + command)

def derive():
    inherited=H.derive();facts=inherited['facts'];mutations=inherited['mutation_suite']
    texts={path:(G.ROOT/path).read_text() for path in CHECK_HOST_ROUTES}
    check_host_routing(texts)
    rejected=[]
    for path, targets in CHECK_HOST_ROUTES.items():
        for target, commands in targets.items():
            for command in commands:
                trial=dict(texts)
                trial[path]=trial[path].replace('tools/host-lisp/'+command,
                                               'tools/host-lisp/withdrawn_'+command)
                try:check_host_routing(trial)
                except G.CardError:rejected.append(target+': '+command)
                else:raise ValueError('v250 check-host route mutation survived')
    mutations['v250_check_host_routing']=rejected
    authority=G.ROOT/'config/c2-v250-public-build-authority.json'
    value=json.loads(authority.read_bytes())
    G.require(value['release']=='2.5.0' and value['raw_pair']['ELF']['sha256']==
        'd555f01fbac51bb5fbc035b2b595e95e3c8e3bedc584c87112bca8b073e31444',
        'Comfort-default runtime authority drift')
    import c2_v250_reproduction_gate as R
    reproduction=R.validate(json.loads(R.RECEIPT.read_text()))
    names=set(R.CONFIGS)|{str(R.RECEIPT.relative_to(G.ROOT))}|set(G.source_texts(G.ROOT))|{str(authority.relative_to(G.ROOT)),
        'tools/host-lisp/block_26_build_integrity_card.py','tools/host-lisp/c2_v250_card5_20260928.py',
        'tools/host-lisp/c2_v250_public_product.py',
        'tools/host-lisp/c2_v240_release_preflight_20260928.py',
        'tools/host-lisp/c2_v250_public_naming_20260928.py',
        'config/c2-v250-public-naming-receipt-20260928.json',
        'tools/host-lisp/c2_v250_keymap_20260928.py'}
    return dict(format='lisp65-block-2.6-card5-v250-successor-20260927',status='passed',
                facts=facts,mutation_suite=mutations,inherited_comfort_default=inherited,inputs=[dict(path=p,sha256=G.sha(G.ROOT/p)) for p in sorted(names)],
                candidate_entry=value['entry_point'],public_reproductions=reproduction,product_builds=0,product_links=0,device_contacts=0)

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('selftest','build','check'));a=p.parse_args()
    if a.action=='selftest':
        derive();print('v250 Card-5 SELFTEST PASS: inherited=13 routes=9 check-host-routes=5 predecessor-controls=2');return
    value=G.canonical(derive())
    if a.action=='build':
        G.require(not RECEIPT.exists(),'successor receipt already exists');RECEIPT.write_bytes(value)
    else:G.require(RECEIPT.read_bytes()==value,'Card-5 successor drift')
    print('v250 Card-5 2026-09-27: PASS')


HISTORY = {'tools/host-lisp/comfort_default_card5_r2_20260927.py': '633366bde7a0ec71cdc56265af2f5e51328c7af8f759f89a1688cd6cfdf0d6d2', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/block-2.6-card5-build-integrity-comfort-default-r2-receipt-20260927.json': '616c3c796578fea765723bc01a88a0cb8dfc37e322ad19479aa18cd3ea81ea43'}
def history_check():
    import hashlib
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    def validate(rows):
        if rows != HISTORY:raise ValueError('successor predecessor drift')
    rows={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in HISTORY}
    validate(rows)
    for p in rows:
        bad=dict(rows);bad[p]='0'*64
        try:validate(bad)
        except ValueError:pass
        else:raise ValueError('predecessor mutation survived')
history_check()

if __name__=='__main__':main()
