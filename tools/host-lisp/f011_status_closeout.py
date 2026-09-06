#!/usr/bin/env python3
"""Certify the stable checker tree, then bind the short RAM-only device row."""
import argparse
import subprocess
from pathlib import Path
import f011_status_product_card as C
import f011_status_comfort_prefilter as PACK
import f011_status_disk_prefilter as DISK
import f011_status_qualification_gate as Q
from elf_truth import ElfTruth
from evidence_era import stable_recorded_on

CERT=C.ARCH/'v2.1-f011-status-product-r1-source-certification.json'
FINAL=C.ARCH/'v2.1-f011-status-product-r1-qualification-receipt.json'
SESSION=C.ROOT/'config/v2.1-f011-status-device-session.json'
LOG=C.BUILD/'check-source-certification.log'

def git(*args):return subprocess.check_output(['git',*args],cwd=C.ROOT,text=True).strip()

def certify():
    C.require(not git('status','--porcelain'),'certification requires a clean tree')
    C.require(not CERT.exists() and not LOG.exists(),'certification is one-shot')
    before=git('rev-parse','HEAD^{tree}');commit=git('rev-parse','HEAD')
    with LOG.open('wb') as out:
        result=subprocess.run(['make','check-source'],cwd=C.ROOT,stdout=out,stderr=subprocess.STDOUT)
    C.require(result.returncode==0,'full check-source failed; see '+str(LOG))
    C.require(not git('status','--porcelain') and git('rev-parse','HEAD^{tree}')==before,'certification tree changed')
    CERT.write_bytes(C.canonical({'command':['make','check-source'],'exit_code':result.returncode,
       'source_commit':commit,'source_tree':before,'log':C.bind(LOG),'clean_before_and_after':True}))
    print('Full check-source certification PASS',flush=True)

def bind():
    cert=C.load(CERT);C.require(cert['exit_code']==0 and cert['clean_before_and_after'],'source certification absent')
    Q.verify_binding(cert['log']);Q.run()
    truth=ElfTruth.read(C.ELF,llvm_readobj=C.B.READOBJ)
    state=truth.symbol('lisp65_f011_status_state')
    value={'status':'PASS: F011 PRODUCT AND PACKED PREFILTER; DEVICE OBSERVATION PENDING',
       'recorded_on':stable_recorded_on(FINAL),'authority':C.authority(),
       'product_scope_acceptance':C.bind(C.RECEIPT),'attribution':C.bind(C.DIFFERENCE),
       'final_proof':C.bind(C.BUILD/'final-proof.json'),'packed':C.bind(PACK.RECEIPT),
       'comfort_runtime':C.bind(PACK.RUNTIME/'receipt.json'),
       'negative_directory':C.bind(DISK.BUILD/'corrupt-directory/receipt.json'),
       'boot_cycles':C.bind(DISK.BUILD/'boot/receipt.json'),'source_certification':C.bind(CERT),
       'pair':[C.bind(C.ELF),C.bind(C.PRG)],'medium':C.bind(PACK.MEDIUM),
       'budget':{'WPLTO':1,'product_links':1,'device_contacts':0},
       'comfort_hardware_attributed':False,'instrument_removal_default':True}
    FINAL.write_bytes(C.canonical(value))
    session={'format':'lisp65-v21-f011-status-device-session-v1','recorded_on':stable_recorded_on(SESSION),
       'authority':C.authority(),'qualification':C.bind(FINAL),'medium':dict(C.bind(PACK.MEDIUM),remote_name='V21F011.D81'),
       'product':C.bind(C.ELF),'status':'BOUND; NOT STARTED',
       'choreography':{'restore_and_SHA_readback_before_every_cold_boot':True,'freezer_operations':0,
         'physical_owner_keyboard_only_after_boot':True,'automated_input':False,'stops':1,'resumes':0,
         'F011_register_reads':False},
       'rows':[{'id':'F1','actions':['Freshly restore and SHA-readback the bound D81; cold boot.',
          'Observe WORKBENCH 2.0.0 and native lisp65>. If boot fails, stop; do not submit a form.']},
         {'id':'F2','form':"(require 'repl-comfort)",'actions':['Submit once; report the complete visible result.',
          'At return to the native prompt, touch no further key. Stop the CPU for F3. Do not enter Comfort.']},
         {'id':'F3','read_only':True,'raw_first':True,'reads':[{'symbol':state.name,'address':state.value,'bytes':state.bytes,
          'layout':['tag','raw_D082','raw_D083'],'authority':C.bind(C.ELF)}],
          'actions':['Seal the three raw RAM bytes before interpreting them. No F011-register read, resume or reset.']}],
       'tags':{'0':'unseen; not equivalent to success','1':'first success retained; no recorded failure',
           '2':'first completion-mask failure','3':'first spin-up timeout','4':'first read timeout'},
       'decision_table':{'tag-1-and-require-T':'no failure reproduced in this contact; retain the evidence boundary',
          'boot-not-complete':'do not infer tag semantics until execution of the boot reset is established; no require was submitted',
          'tag-1-but-load-failed':'failure outside recorded mask/timeout paths; further attribution, not Comfort blame',
          'tag-2':'compare the raw masked status with the bound core; hardware evidence governs the next decision',
          'tag-3-or-4':'timeout phase identified; do not interpret as a completed-read mask mismatch',
          'tag-0-or-inconsistent-record':'instrument coverage/readpoint unresolved; no no-failure claim'},
       'claim_limit':'F011 read diagnosis and error propagation only; Comfort remains unattributed; no release acceptance.'}
    SESSION.write_bytes(C.canonical(session))
    print('F011 qualification and short device session BOUND; no device touched',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['certify','bind']);a=p.parse_args()
    if a.action=='certify':certify()
    else:bind()
