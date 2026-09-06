#!/usr/bin/env python3
"""Artifact-only F011 successor medium; never invokes a product build."""
from types import SimpleNamespace
from pathlib import Path
import f011_status_product_card as C
import block_26_vm_hardening_dwx_prefilter as M
import c2_bank2_composed_ownership as BANK
from elf_truth import ElfTruth
from evidence_era import stable_recorded_on

BUILD=C.ROOT/'build/v2.1/f011-status-media-r1'

def qualified_pair():
    C.configure()
    base=C.B.PREV.CARD.CARD2.R2.CARD.BASE.CHAIN.LINK.BASE
    scope,accept=C.load(base.SCOPE_RESULT),C.load(base.ACCEPTANCE_RESULT)
    C.require(scope['status']==accept['status']=='PASS','scope/acceptance incomplete')
    C.require(C.load(C.DIFFERENCE)['unexplained_members']==0,'attribution incomplete')
    proof=C.load(C.BUILD/'final-proof.json')
    C.require(proof['pair']==[C.bind(C.ELF),C.bind(C.PRG)],'final proof pair mismatch')
    t=ElfTruth.read(C.ELF,llvm_readobj=C.B.READOBJ)
    mapped=tuple((n,'__lisp65_c2_'+n.removeprefix('.lisp65_c2_')) for n in
                 ['.lisp65_c2_mapped_f011_cold','.lisp65_c2_mapped_far_service','.lisp65_c2_mapped_product_cold'])
    bank=BANK.derive(elf=C.ELF,plane=C.PLANE/'v6-semantics/bank2-static-code.bin',readobj=C.B.READOBJ,
          mapped_owners=mapped,placement_policy='map-page-top-derived',expected_vmas={n:t.section(n).address for n,_ in mapped})
    C.require(not bank['overlaps'],'composed bank overlap')
    status='PASS: F011 PRODUCT SCOPE AND ACCEPTANCE; DWX PENDING'
    value={'format':C.FORMAT,'recorded_on':stable_recorded_on(C.RECEIPT),'status':status,
       'authority':C.authority(),'preflight':C.bind(C.PREFLIGHT_RECEIPT),'invocation':C.bind(C.INVOCATION),
       'difference':C.bind(C.DIFFERENCE),'scope':C.bind(base.SCOPE_RESULT),'acceptance':C.bind(base.ACCEPTANCE_RESULT),
       'final_product':{'proof':C.bind(C.BUILD/'final-proof.json'),'composed_bank2':bank},
       'artifacts_after':{'ELF':C.bind(C.ELF),'PRG':C.bind(C.PRG)},
       'attempt_accounting':{'WPLTO_runs':1,'product_links':1,'device_contacts':0},
       'review_ready':False}
    C.RECEIPT.write_bytes(C.canonical(value))
    return status

def configure(status):
    C.configure()
    adapter=SimpleNamespace(BUILD=C.BUILD,WPLTO=C.WPLTO,PLANE=C.PLANE,PRG=C.PRG,ELF=C.ELF,
        RECEIPT=C.RECEIPT,STATUS=status,CARD2=C.B.PREV.CARD.CARD2,
        patch_card=C.configure,authority=lambda:{'commission':C.authority()})
    M.CARD=adapter;M.configure_card=C.configure
    for cls in [M.ProductCard,M.Adapter]:
        for key in ['BUILD','WPLTO','PLANE','PRG','ELF','RECEIPT','STATUS']:setattr(cls,key,getattr(adapter,key))
    M.ProductCard.LINK=adapter.CARD2.R2.CARD.BASE.CHAIN.LINK
    for key,value in {'BUILD':BUILD,'MEDIA_BUILD':BUILD/'media','WPLTO':BUILD/'media/inputs/wplto',
        'STATIC':BUILD/'media/inputs/static-plane','TARGET':BUILD/'media/canonical-product',
        'SHARED':BUILD/'media/shared-system','MEDIA_RECEIPT':BUILD/'media-receipt.json',
        'SESSION':BUILD/'not-a-device-session.json','MEDIA_STATUS':'PASS: F011 FOLLOW-UP PACKED MEDIUM',
        'MEDIA_FORMAT':'f011-followup-medium-v1','SESSION_FORMAT':'f011-prefilter-only-v1'}.items():setattr(M,key,value)

def run():
    status=qualified_pair();configure(status)
    before=[C.bind(C.ELF),C.bind(C.PRG)]
    product,packed=M.build_medium()
    C.require(before==[C.bind(C.ELF),C.bind(C.PRG)],'media producer changed frozen pair')
    print('F011 artifact-only product medium:',product)
if __name__=='__main__':run()
