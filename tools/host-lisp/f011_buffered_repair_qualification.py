#!/usr/bin/env python3
"""Close executed F011/Comfort evidence and derive the physical session."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

import f011_buffered_repair_prefilter as P
import dwx_comfort_collection_calibration as CAL
from elf_truth import ElfTruth
from evidence_era import stable_recorded_on

C=P.C
OUT=C.ROOT/'config/v2.1-comfort-buffered-repair-device-session.json'
CHECK=C.BUILD/'qualification.json'
CHOICE=C.ROOT/'config/v2.1-comfort-coldstart-owner-choice.json'

def bound(value):
    assert C.C.bind(C.ROOT/value['path'])==value,'binding drift: '+value['path']

def display(frames):
    for name,prompt in [('C2-overclose','L65>'),('C3-abort','LISP65>'),('C3-reentry','L65>')]:
        lines=frames[name].splitlines()
        text='*** READER: UNMATCHED CLOSE PARENTHESIS' if name=='C2-overclose' else '*** VM: TYPE ERROR'
        assert text in lines and lines[-1].replace('{$A0}',' ').strip()==prompt
        assert lines.index(text)<len(lines)-1

def derive():
    P.configure();P.PACK.check()
    pair=[C.C.bind(C.ELF),C.C.bind(C.PRG)]
    native=C.C.load(C.BUILD/'final-native-proof.json')
    assert native['pair']==pair and native['status']=='PASS'
    assert len(native['native_status_rows'])==256
    for status,row in enumerate(native['native_status_rows']):
        assert row['status']==status and (row['return_value']==0)==((status&0xd8)==0x40)
        assert row['commands']==[0x20,0x40] and row['pre_READ_status_reads']==0
    assert native['bounded_owners']['all_floors_green']
    assert native['bounded_owners']['ordinary_BSS']['margin_bytes']>=5
    assert native['E000']['capture_watch_bytes']>=57
    assert native['clock_stopped']['return_value']==65535
    assert native['startup_cache']['poison_before']==0xa5 and native['startup_cache']['after']==0
    assert native['omitted_startup_zero_mutation']['after']==0xa5
    for name in ('seed-to-final-attribution.json','predecessor-attribution.json'):
        assert C.C.load(C.BUILD/name)['unexplained_members']==0
    runtime=P.PACK.RUNTIME;comfort=C.C.load(runtime/'receipt.json')
    assert comfort['status'].startswith('EXECUTED ROWS PASS') and comfort['product']==pair[0]
    assert comfort['medium']==C.C.bind(P.PACK.MEDIUM)
    for key in ('executor','calibration_executor','fork','successor_card','session_counterparts'):bound(comfort[key])
    for row in comfort['rows']:
        for key in ('framebuffer','evidence'):
            if key in row:bound(row[key])
    for value in comfort['outputs'].values():bound(value)
    clean=C.C.load(P.BUILD/'clean-boot-require/receipt.json')
    negative=C.C.load(P.BUILD/'corrupt-directory/receipt.json')
    for value in (clean,negative):
        assert value['status']=='PASS' and value['pair']==pair
        bound(value['medium'])
        for item in value['outputs'].values():bound(item)
    assert clean['clock']['raw'].startswith('01')
    negative_screen=P.RUN.ROWS.decoded_framebuffer((P.BUILD/'corrupt-directory/require-framebuffer.txt').read_text())
    assert '*** LOAD: CANNOT OPEN' in negative_screen and '\nNIL\n' not in negative_screen
    frames={n:P.RUN.ROWS.decoded_framebuffer((runtime/(n+'-framebuffer.txt')).read_text())
            for n in ('C2-overclose','C3-abort','C3-reentry')}
    display(frames)
    bad=dict(frames);bad['C3-abort']=bad['C3-abort'].replace('*** VM: TYPE ERROR','LISP65>TYPE ERROR')
    try:display(bad)
    except AssertionError:pass
    else:raise AssertionError('diagnostic overwrite mutation survived')
    t=ElfTruth.read(C.ELF,llvm_readobj=C.C.B.READOBJ,include_section_data=True)
    C.witness_absent(t)
    data=comfort['collection_calibration']
    session=P.RUN.load(P.COMFORT.SESSION)
    capture=next(r for r in session['rows'] if r['id']=='C4')['collection']
    model=CAL.model(t,C.ELF)
    samples=[(C.C.load(runtime/f'calibration-sample-{i}-typed.json'),
              C.C.load(runtime/f'calibration-sample-{i}-deleted.json')) for i in (1,2)]
    plan=json.loads(json.dumps(CAL.derive(data['origin'],samples,capture,model)))
    assert plan==data['plan']
    for key in ('origin','start'):CAL.verify_chain(data[key],model)
    CAL.validate_window(data['origin'],data['start'],data['end'])
    counters=bytes.fromhex(comfort['stopped']['capture']['raw'])
    events_per_pass=len(capture['pattern'])+capture['delete_events_per_pass']
    expected=((plan['warmup_passes']+plan['measured_passes'])*events_per_pass
              +len(capture['final_text'])+1)%256
    assert expected!=0 and counters==bytes([expected])*4 and comfort['stopped']['derived']['collections']>=1
    d5=comfort['stopped']['derived'];assert d5['free_slots']>=32 and d5['free_name_bytes']>=384
    assert comfort['stopped']['lisp65_symbol22_latch_state']['raw']=='0000000000'
    scope=C.C.load(C.WPLTO/'owner-scope-result.json');accept=C.C.load(C.BUILD/'artifact-acceptance.json')
    assert scope['status']==accept['status']=='PASS'
    seed=C.C.load(C.BUILD/'final-product-attempt.json')
    assert seed['seed_before']==seed['seed_after'] and seed['seed_rebuilds']==0 and seed['final_C_LTO_invocations']==1
    for item in seed['seed_after']:bound(item)
    value=dict(status='PRODUCT QUALIFICATION AND PACKED COMFORT PREFILTER GREEN; DEVICE PENDING',
        recorded_on=stable_recorded_on(CHECK),pair=pair,medium=C.C.bind(P.PACK.MEDIUM),
        final_native=C.C.bind(C.BUILD/'final-native-proof.json'),
        scope=C.C.bind(C.WPLTO/'owner-scope-result.json'),acceptance=C.C.bind(C.BUILD/'artifact-acceptance.json'),
        seed_attribution=C.C.bind(C.BUILD/'seed-to-final-attribution.json'),
        predecessor_attribution=C.C.bind(C.BUILD/'predecessor-attribution.json'),
        packed=C.C.bind(P.PACK.RECEIPT),comfort=C.C.bind(runtime/'receipt.json'),
        clean=C.C.bind(P.BUILD/'clean-boot-require/receipt.json'),
        negative=C.C.bind(P.BUILD/'corrupt-directory/receipt.json'),
        fork_requalification=C.C.bind(C.ROOT/'build/dwx/buffered-repair-three-patch-requalification-r3/receipt.json'),
        display_overwrite_mutation_rejected=True,collection_plan=plan,D5=d5,
        budget={'seed_WPLTO':1,'final_C_LTO':1,'product_links':1,'device_contacts':0},
        release_hold=True,physical_Coldstart_proven=False,Comfort_hardware_attribution=None)
    assert pair==[C.C.bind(C.ELF),C.C.bind(C.PRG)]
    return value,t,plan,capture

def session(value,t,plan,capture):
    choice=C.C.load(CHOICE)
    assert choice['format']=='lisp65-comfort-coldstart-owner-choice-v1'
    assert choice['variant']=='B' and choice['setup_availability_confirmed'] is True
    assert choice['power_off_minimum_seconds']==30
    assert choice['automatic_product_start_without_freezer'] is False
    assert choice['hardware_acceptance'] is False
    old=C.ROOT/'config/c2-v210-comfort-device-session.json'
    s=deepcopy(C.C.load(old))
    s.update(recorded_on=stable_recorded_on(OUT),status='BOUND; OWNER SELECTED B; RESTORE/READBACK AND CONTACT PENDING',
        owner_choice=C.C.bind(CHOICE),
        authority_commit='566c2e23',predecessor_binding=C.C.bind(old),
        world=dict(zip(('ELF','PRG'),value['pair'])),qualification=C.C.bind(CHECK),
        packed_gates=value['packed'],prefilter=value['comfort'],collection_binding=value['comfort'])
    s['media']['combined']=dict(value['medium'],remote_name='V21FIX.D81')
    s['choreography'].update(power_off_minimum_seconds=30,
        variant='B: power off at least 30 seconds, power on, owner Freezer mount, then product start',
        freezer_operations=1,
        setup_availability_confirmed=True,
        Freezer_mount_plus_warmstart_is_not_coldstart=True)
    del s['choreography']['fresh_restore_and_SHA_readback_before_each_qualifying_cold_boot']
    s['choreography']['fresh_restore_and_SHA_readback_before_each_qualifying_contact']=True
    s['rows'][0]['actions']=[
        'Freshly restore V21FIX.D81 on persistent SD and SHA-read it back before power off; a RAM upload cannot survive power loss.',
        'Switch off for at least 30 seconds, then on. No automatic product boot is expected.',
        'Owner mounts that exact V21FIX.D81 via Freezer, then starts the product by warmstart. No automated Freezer input.',
        'Observe banner and native prompt with silent INIT.L65 absence before loading any optional library.']
    for checkpoint in s['checkpoints']:
        for r in checkpoint['reads']:
            if 'symbol' in r:
                sym=t.symbol(r['symbol']);r.update(address=sym.value,bytes=34 if r['symbol']=='c2_symbol22_repl_buf' else sym.bytes)
            elif r.get('layout')==['raw','seen','stored','taken']:
                r['address']=t.symbol('C2K_INPUT_EVENTS_RAW').value
    c=s['rows'][5]['collection']
    c.update(warmup_passes=plan['warmup_passes'],passes=plan['measured_passes'],derivation=plan,
        observed_gc=[value['D5']['gc_runs_before'],value['D5']['gc_runs_before'],value['D5']['gc_runs_after']])
    assert c['pattern']==capture['pattern'] and c['delete_events_per_pass']==capture['delete_events_per_pass']
    per_pass=len(c['pattern'])+c['delete_events_per_pass']
    warm=plan['warmup_passes']*per_pass
    measured=plan['measured_passes']*per_pass+len(c['final_text'])+1
    c['event_arithmetic']={'warmup_physical_events':warm,
        'measured_physical_events_including_oracle_return':measured,
        'total_physical_events':warm+measured,'counter_modulus':256,
        'expected_each_modulo_256':(warm+measured)%256}
    c['expected_each_modulo_256']=(warm+measured)%256
    s['capture_acceptance']=(f"each row exact; GC-START counters {warm%256:02x}; "
        f"GC-END counters {(warm+plan['measured_passes']*per_pass)%256:02x}; "
        f"CAPTURE counters {(warm+measured)%256:02x}, all four equal and nonzero")
    s['rows'][-1]['D5']['prefilter_before_smoke_definitions_only']={k:value['D5'][k] for k in ('free_slots','free_name_bytes')}
    s['claim_scope']['excludes'].extend(['automatic product coldstart before Freezer/SD initialization',
        'physical F011 coldstart timing from variant B','release approval'])
    return s

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('emit','check'));a=p.parse_args()
    value,t,plan,capture=derive()
    if a.action=='emit':P.write(CHECK,value)
    else:assert C.C.load(CHECK)==value
    s=session(value,t,plan,capture)
    if a.action=='emit':P.write(OUT,s)
    else:assert C.C.load(OUT)==s
    print('BUFFERED REPAIR QUALIFICATION PASS; session rows=7; hardware=0',flush=True)

if __name__=='__main__':main()
