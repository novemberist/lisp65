#!/usr/bin/env python3
"""One-shot diagnostic producer. Never a release/Comfort candidate.

The diagnostic io/main replacements are producer-owned generated sources;
ordinary src/ remains the previous product. No default enables this world.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import f011_status_product_card as C
import f011_frame_instrument_pricing as PRICE
import f011_frame_instrument_semantics as SEM
from evidence_era import stable_recorded_on

ROOT=C.ROOT
OLD={n:getattr(C,n) for n in ['BUILD','PREFLIGHT','PLANE','ELF','PRG','PROFILE','PLANE_RECEIPT']}
ORIGINAL_CONFIGURE=C.configure
ORIGINAL_LD=C.PRODUCT.full_map_platform_c_ld
ORIGINAL_INVENTORY=C.PRODUCT.f011_status_inventory_registration
BUILD=ROOT/'build/v2.1/f011-frame-diagnostic-r1'
PREFLIGHT=ROOT/'build/v2.1/f011-frame-diagnostic-r1-preflight'
PLANE=PREFLIGHT/'setup-owned/static-plane/narrow-static'
WPLTO=BUILD/'wplto'
ELF=WPLTO/'lisp65-c2-substitution-linked.prg.elf'
PRG=WPLTO/'lisp65-c2-substitution-linked.prg'
PROFILE=WPLTO/'resolved-profile.txt'
BOUND_PROFILE=PREFLIGHT/'bound-feature-profile.txt'
INVOCATION=PREFLIGHT/'diagnostic-invocation.json'
AUTHORIZATION='3fa20fbb'
PLAN_HEADER='## v2.1'
FORMAT='f011-frame-diagnostic-r1'
STATUS='DIAGNOSTIC ONLY; NOT A CANDIDATE'
DRIVER=Path(__file__).resolve()
REPORT=ROOT/'docs/planning/v2.1-f011-frame-diagnostic-report.md'
for n in ['PLANE_RECEIPT','PREFLIGHT_RECEIPT','SOURCE_PREFLIGHT','PRELINK_RED','DIFFERENCE','RECEIPT']:
    globals()[n]=C.ARCH/(FORMAT+'-'+n.lower().replace('_','-')+'.json')
GENERATOR=None
RECORD_BYTES=7

def authority():
    raw=subprocess.check_output(['git','show',f'{AUTHORIZATION}:docs/planning/v2.0.0-pre-plan.md'],cwd=ROOT)
    assert b'diagnostic' in raw.lower() and b'not a candidate' in raw.lower()
    assert C.bind(OLD['ELF'])['sha256']=='29d3ff462afc9c59ad9769fac8098ed0f02900d3c7cf5a37c89855b0444d9cc6'
    return dict(commit=AUTHORIZATION,plan_sha256=hashlib.sha256(raw).hexdigest(),
                role='DIAGNOSTIC-EVIDENCE-ONLY',release_eligible=False,comfort_acceptance_eligible=False,
                predecessor=dict(ELF=C.bind(OLD['ELF']),PRG=C.bind(OLD['PRG'])),
                budget=dict(WPLTO=1,product_links=1,device_contacts=0))

def materialize(out):
    mapping=GENERATOR(out)
    replacements=PRICE.sources()
    dest=out/'generated-product-sources'
    for name,text in replacements.items():
        p=dest/name
        p.write_text(text)
        mapping[(ROOT/'src'/name).resolve()]=p
    (dest/PRICE.HEADER.name).write_bytes(PRICE.HEADER.read_bytes())
    return mapping

def profile(mapping=None):
    assert mapping is not None
    generated={p.name:p for p in mapping.values()}
    lines=OLD['PROFILE'].read_text().splitlines()
    changed=[]
    for i,line in enumerate(lines):
        if not line.startswith('input_sha256='): continue
        name,oldsha=line.split('=',1)[1].split(':',1)
        original=ROOT/name
        if name in ('src/io.c','src/main.c') or '/generated-product-sources/' in name:
            p=generated.get(original.name,OLD['BUILD']/'wplto/generated-product-sources'/original.name)
            successor=str((WPLTO/'generated-product-sources'/p.name).relative_to(ROOT))
        else:
            p=original; successor=name
        sha=C.bind(p)['sha256']
        lines[i]=f'input_sha256={successor}:{sha}'
        if sha!=oldsha: changed.append(name)
    assert 'src/io.c' in changed and 'src/main.c' in changed
    BOUND_PROFILE.write_text('\n'.join(lines)+'\n')
    return dict(predecessor=C.bind(OLD['PROFILE']),successor=C.bind(BOUND_PROFILE),
                changed_authored_roots=[],changed_generated_roots=changed,
                diagnostic_source_transforms=['src/io.c','src/main.c'],
                header_roots=[C.bind(PRICE.HEADER)],feature_count=len(C.B.bound_features()))

def source_gate():
    SEM.main()
    p=json.loads((PRICE.OUT/'receipt.json').read_text())
    assert p['lanes']['baseline']['projection']==p['lanes']['frontend-control']['projection']
    assert p['lanes']['successor']['projection']['groups']['noinit_record']==RECORD_BYTES
    for name,data in PRICE.sources().items():
        bound=PRICE.OUT/'successor'/name
        assert bound.read_text()==data, 'diagnostic source differs from priced form'
    # Record extent is consumed from the bound emitted pricing microobject,
    # not copied from a prose claim. Final linker assertion checks it again.
    header=PRICE.HEADER.read_text()
    assert 'lisp_abort' not in header and 'map_enter' not in header and 'map_leave' not in header
    return dict(role='DIAGNOSTIC ONLY',pricing=C.bind(PRICE.OUT/'receipt.json'),
                semantics=C.bind(PRICE.OUT/'host-semantics-r2.json'),header=C.bind(PRICE.HEADER),
                record_bytes=RECORD_BYTES,product_sources_unchanged=True,
                final_elf_proof=False)

def configure():
    global GENERATOR
    for n in ['BUILD','PREFLIGHT','PLANE','WPLTO','ELF','PRG','PROFILE','BOUND_PROFILE','INVOCATION',
              'AUTHORIZATION','PLAN_HEADER','FORMAT','STATUS','DRIVER','REPORT',
              'PLANE_RECEIPT','PREFLIGHT_RECEIPT','SOURCE_PREFLIGHT','PRELINK_RED','DIFFERENCE','RECEIPT']:
        setattr(C,n,globals()[n])
    for n,v in OLD.items(): setattr(C,'OLD_'+n,v)
    C.DIRECT=()
    C.authority=authority; C.materialize_bound_profile=profile; C.source_gate=source_gate
    ORIGINAL_CONFIGURE()
    C.B.HEADER_ROOTS=(str(PRICE.HEADER.relative_to(ROOT)),)
    link=C.B.PREV.CARD.CARD2.R2.CARD.BASE.CHAIN.LINK
    if GENERATOR is None: GENERATOR=link.materialize_candidate_sources
    link.materialize_candidate_sources=materialize
    def linker_script():
        s=ORIGINAL_LD()
        needle='SIZEOF(.noinit.lisp65_f011_status) == 3'
        assert s.count(needle)==1
        return s.replace(needle,f'SIZEOF(.noinit.lisp65_f011_status) == {RECORD_BYTES}')
    def inventory():
        v=ORIGINAL_INVENTORY()
        v.update(record_bytes=RECORD_BYTES,authority='explicit diagnostic record extent from priced object',
                 header=C.bind(PRICE.HEADER),role='DIAGNOSTIC-EVIDENCE-ONLY')
        return v
    C.PRODUCT.full_map_platform_c_ld=linker_script
    C.PRODUCT.f011_status_inventory_registration=inventory

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('action',choices=['preflight','produce','_produce','_scope'])
    action=ap.parse_args().action
    configure()
    C.configure=configure
    if action=='preflight':
        C.preflight()
    elif action=='produce':
        C.produce()
    else:
        C.B.child(action)

if __name__=='__main__': main()
