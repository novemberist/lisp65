#!/usr/bin/env python3
"""Bind unchanged repaired Comfort to the qualified F011 successor, artifact-only."""
import argparse
from contextlib import contextmanager
from pathlib import Path
import f011_status_product_card as C
import f011_status_media as MEDIA
import c2_v210_comfort_media_card as BASE
import c2_v210_comfort_display_repair as REPAIR

BUILD=C.ROOT/'build/v2.1/f011-status-comfort-r1'
MEDIUM=BUILD/'lisp65-v2.1-f011-comfort.d81'
RECEIPT=BUILD/'packed-receipt.json'
RUNTIME=BUILD/'runtime-r2'
SEALED=REPAIR.BUILD

@contextmanager
def world():
    replacements={'PRODUCT_MANIFEST':C.PLANE/'product/substitution-artifacts.json',
       'PRODUCT_ELF':C.ELF,'PRODUCT_D81':MEDIA.BUILD/'media/shared-system/lisp65-product.d81',
       'BUILD':BUILD,'MANIFEST':SEALED/'repl-comfort.manifest.json',
       'ARTIFACT':BUILD/'repl-comfort.l65s','INDEX':BUILD/'l65index','MEDIUM':MEDIUM}
    old={k:getattr(BASE,k) for k in replacements}
    try:
        for k,v in replacements.items():setattr(BASE,k,v)
        yield
    finally:
        for k,v in old.items():setattr(BASE,k,v)

def packed():
    with world():
        files=BASE.V17.LIBMEDIA.L65I.D81.visible_files(MEDIUM.read_bytes())
        sealed=(SEALED/'repl-comfort.l65s').read_bytes()
        expected=BASE.V17.LIBMEDIA.measured(('repl-comfort','repl','repl',BASE.MANIFEST,()),(1,1),BASE.PRODUCT_BUILD_ID)[1]
        C.require(files[b'REPL-COMFORT']==sealed==expected,'Comfort packed generation changed')
        C.require(b'V16CORE' not in files,'duplicate editor on medium')
        closure=BASE.CLOSURE.derive(BASE.PRODUCT_MANIFEST,[BASE.MANIFEST])
        BASE.CLOSURE.require_closed(closure)
        candidate=BASE.F.emit_image('candidate','repl',BASE.MANIFEST)
        raw=BASE.F.emit_image('repair','repl',SEALED/'raw/repl-comfort.manifest.json')
        _,support,_=BASE._selected_support()
        ide=BASE.F.emit_image('ide','ide',BASE.product_ide_manifest())
        start,size=support['blob_offset'],support['length']
        C.require(candidate.code[:size]==ide.code[start:start+size] and candidate.code[size:]==raw.code,'support generation mismatch')
        mutant=bytearray(sealed);mutant[-1]^=1
        C.require(bytes(mutant)!=expected,'changed packed byte mutation survived')
        return {'closure':closure,'unchanged_repaired_artifact':C.bind(SEALED/'repl-comfort.l65s'),
                'product_support_identical':True,'changed_packed_byte_rejected':True,'v16core':False}

def check():
    value=C.load(RECEIPT)
    C.require(value['pair']==[C.bind(C.ELF),C.bind(C.PRG)],'successor pair drift')
    C.require(value['medium']==C.bind(MEDIUM) and value['packed']==packed(),'packed authority drift')
    product=C.load(C.RECEIPT)
    C.require(product['artifacts_after']=={'ELF':C.bind(C.ELF),'PRG':C.bind(C.PRG)},'unqualified successor')
    for key in ('scope','acceptance'):
        path=C.ROOT/product[key]['path']
        C.require(C.bind(path)==product[key] and C.load(path)['status']=='PASS','unqualified '+key)
    C.require(C.load(C.DIFFERENCE)['unexplained_members']==0,'unattributed successor')
    return MEDIUM,C.ELF

def build():
    C.require(not BUILD.exists(),'artifact producer is one-shot')
    MEDIA.qualified_pair()
    BUILD.mkdir(parents=True)
    before=[C.bind(C.ELF),C.bind(C.PRG)]
    with world():media=BASE.build_medium()
    C.require(before==[C.bind(C.ELF),C.bind(C.PRG)],'product changed during packing')
    C.RECEIPT.parent.mkdir(parents=True,exist_ok=True)
    RECEIPT.write_bytes(C.canonical({'pair':before,'medium':C.bind(MEDIUM),'media':media,'packed':packed(),
          'product_builds':0,'device_contacts':0,'status':'PACKED GATES PASS; DWX PENDING'}))
    check()
    print('F011 + unchanged Comfort packed gates PASS',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['build','check','run']);a=p.parse_args()
    if a.action=='build':build()
    elif a.action=='check':check()
    else:
        import dwx_comfort_resume as RUN
        result=RUN.execute(RUNTIME,calibrate_collection=True,successor_receipt=RECEIPT)
        C.require(result['status'].startswith('EXECUTED ROWS PASS'),result['status'])
