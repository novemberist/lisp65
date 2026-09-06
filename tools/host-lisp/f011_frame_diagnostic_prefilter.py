#!/usr/bin/env python3
"""Diagnostic-only artifact medium and headless boot oracle. No Comfort claim."""
import argparse
import json
from pathlib import Path
import f011_frame_diagnostic_card as D
import f011_status_media as MEDIA
import dwx_retroactive_red_replay as R
import dwx_prefilter_blind_spot_contract as BLIND
from elf_truth import ElfTruth
from evidence_era import stable_recorded_on

BUILD=D.BUILD/'prefilter'
STATUS='DIAGNOSTIC SCOPE/INSTRUMENT PROOFS PASS; NOT DEVICE ACCEPTANCE'


def configure():
    D.configure();D.C.configure=D.configure
    pair={'ELF':D.C.bind(D.ELF),'PRG':D.C.bind(D.PRG)}
    base=D.C.B.PREV.CARD.CARD2.R2.CARD.BASE.CHAIN.LINK.BASE
    assert D.C.load(base.SCOPE_RESULT)['status']=='PASS'
    proof=D.C.load(D.BUILD/'final-proof.json')
    assert proof['pair']==list(pair.values()) and proof['status']=='PASS'
    for name in ('seed-to-final-attribution.json','predecessor-attribution.json'):
        assert D.C.load(D.BUILD/name)['unexplained_members']==0
    clock=D.C.load(D.BUILD/'emitted-clock-semantics.json')
    assert clock['pair']==list(pair.values()) and clock['status']=='PASS'
    BUILD.mkdir(exist_ok=True)
    admission=BUILD/'diagnostic-admission.json'
    admission.write_text(json.dumps({'status':STATUS,'artifacts_after':pair,
       'role':'DIAGNOSTIC-EVIDENCE-ONLY','release_eligible':False,'comfort_acceptance_eligible':False,
       'preflight':D.C.bind(D.PREFLIGHT_RECEIPT),
       'scope':D.C.bind(base.SCOPE_RESULT),'final_product':{'composed_bank2':proof['bank2']}},indent=2)+'\n')
    D.C.RECEIPT=admission
    # The inherited packer gets an explicit diagnostic status, never PASS
    # device acceptance; its pair field is only an artifact identity input.
    MEDIA.BUILD=BUILD
    MEDIA.configure(STATUS)
    MEDIA.M.CARD.RECEIPT=admission
    for obj in (MEDIA.M.ProductCard,MEDIA.M.Adapter):obj.RECEIPT=admission
    return MEDIA.M


def pack():
    before=[D.C.bind(D.ELF),D.C.bind(D.PRG)]
    m=configure();product,packed=m.build_medium()
    assert before==[D.C.bind(D.ELF),D.C.bind(D.PRG)]
    out=BUILD/'packed-diagnostic.json'
    out.write_text(json.dumps({'role':'DIAGNOSTIC-EVIDENCE-ONLY',
      'medium':D.C.bind(product),'pair':before,'packed':packed,
      'device_acceptance_claimed':False,'Comfort_claimed':False},indent=2)+'\n')
    print('DIAGNOSTIC MEDIUM PACKED',product,flush=True)


def boot():
    packed=D.C.load(BUILD/'packed-diagnostic.json')
    medium=D.ROOT/packed['medium']['path']
    assert D.C.bind(medium)==packed['medium']
    BLIND.validate_contract(BLIND.load_json(BLIND.CONTRACT_PATH))
    R.check()
    contract=R.load(R.CONTRACT_PATH)
    binary=R.verify_binding(contract['inputs']['cycle_probe_binary'],'qualified fork')
    out=BUILD/'boot-r1';out.mkdir()
    args=argparse.Namespace(xemu=binary,rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
        sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')),timeout=90)
    run=R.start_run('diagnostic',medium,out,args)
    m=run['monitor'];m.command('t1')
    screen=m.screen();decoded=R.ROWS.decoded_framebuffer(screen)
    t=ElfTruth.read(D.ELF,llvm_readobj=D.C.B.READOBJ)
    state=t.symbol('lisp65_f011_status_state')
    record=m.memory_range(state.value,state.bytes)
    good=('WORKBENCH 2.0.0' in decoded and 'LISP65>' in decoded
          and 'CANNOT OPEN' not in decoded and record[0]==1)
    outputs=R.finish_run(run,screen)
    receipt={'status':'PREFILTER GREEN' if good else 'PREFILTER RED',
       'role':'DIAGNOSTIC-EVIDENCE-ONLY','record_hex':record.hex(),
       'record_address':state.value,'outputs':outputs,'medium':packed['medium'],
       'fork':R.bind(binary),'blind_spot_contract':R.bind(BLIND.CONTRACT_PATH),
       'device_counterpart':'diagnostic first cold-start read, then RAM record; no typing',
       'oracle':'whole framebuffer banner/native prompt plus stopped RAM record',
       'claim_limit':'Only this diagnostic sequence boots in Xemu. No physical spin-up, power-off interval, clock rate, Comfort or device acceptance.'}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'],record.hex(),flush=True)
    assert good, 'diagnostic boot oracle failed; no device admission'


def receipt():
    """Seal completed evidence without implying device or release approval."""
    D.configure();D.C.configure=D.configure
    pair=[D.C.bind(D.ELF),D.C.bind(D.PRG)]
    scope=D.WPLTO/'owner-scope-result.json'
    acceptance=D.BUILD/'artifact-acceptance.json'
    assert D.C.load(scope)['status']==D.C.load(acceptance)['status']=='PASS'
    proof=D.C.load(D.BUILD/'final-proof.json')
    clock=D.C.load(D.BUILD/'emitted-clock-semantics.json')
    assert proof['pair']==clock['pair']==pair
    packed=D.C.load(BUILD/'packed-diagnostic.json')
    boot_result=D.C.load(BUILD/'boot-r1/receipt.json')
    assert packed['pair']==pair and boot_result['status']=='PREFILTER GREEN'
    assert packed['medium']==boot_result['medium']
    assert D.C.bind(D.ROOT/packed['medium']['path'])==packed['medium']
    for name in ('seed-to-final-attribution.json','predecessor-attribution.json'):
        assert D.C.load(D.BUILD/name)['unexplained_members']==0
    evidence=[scope,acceptance,D.BUILD/'final-proof.json',
        D.BUILD/'emitted-clock-semantics.json',
        D.BUILD/'seed-to-final-attribution.json',D.BUILD/'predecessor-attribution.json',
        D.BUILD/'final-product-invocation.json',D.BUILD/'final-product-attempt.json',
        D.BUILD/'artifact-completion.json',BUILD/'packed-diagnostic.json',
        BUILD/'boot-r1/receipt.json']
    value={'format':'f011-frame-diagnostic-completion-v1',
        'recorded_on':stable_recorded_on(D.RECEIPT),
        'status':'DIAGNOSTIC SCOPE, ARTIFACT ACCEPTANCE AND PREFILTER GREEN',
        'pair':pair,'medium':packed['medium'],'evidence':[D.C.bind(p) for p in evidence],
        'record':{'address':proof['record_owner']['address'],
                  'bytes':7,'emulator_hex':boot_result['record_hex']},
        'owners':{'text_reserve':proof['text_reserve'],
                  'record_reserve':proof['record_reserve'], 'E000':proof['E000']},
        'budget_this_final_stage':{'C_LTO_and_product_link':1,
                                  'seed_compiles':0,'seed_links':0,'device_contacts':0},
        'claim_boundary':{'diagnostic_only':True,'release_eligible':False,
                          'Comfort_acceptance':False,'physical_spinup_measured':False},
        'full_check_source_claimed':False,
        'full_check_source_note':'See report for full-run disposition; this receipt is not a full-test certificate.'}
    D.RECEIPT.write_bytes(D.C.canonical(value))
    print('DIAGNOSTIC RECEIPT',D.RECEIPT)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['pack','boot','receipt'])
    action=p.parse_args().action
    if action=='pack':pack()
    elif action=='boot':boot()
    else:receipt()
