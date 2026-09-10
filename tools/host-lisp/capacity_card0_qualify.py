#!/usr/bin/env python3
"""Qualify fresh row/world bindings and observer controls; no product build."""
import copy
import json
from pathlib import Path

import capacity_prefilter_media as MEDIA
import capacity_pc_population as POP
from capacity_pc_histogram_tool import BASE, OUT, ROOT, bind
from elf_truth import ElfTruth
from evidence_era import stable_recorded_on

CONTROL_R3={'init-l65-valid','init-l65-broken','composed-native-prompt-and-cursor','capture-counters-at-stopped-point'}

def validate(records,authority,instrument,base):
    expected={r['id']:r for r in authority['rows']}
    assert set(records)==set(expected),'omitted/foreign row'
    for name,lanes in records.items():
        assert set(lanes)=={'control','observed'}
        for lane,record in lanes.items():
            assert record['status']=='PASS' and record['error'] is None
            assert record['row']==expected[name],'row world/medium/contract mismatch'
            assert record['observer']==(lane=='observed')
            wanted=instrument['binary'] if lane=='observed' else base['binary']
            assert record['binary']['sha256']==wanted['sha256']
            assert not record['historical_results_inherited']
            assert not record['comfort_entry'] and not record['comfort_claim']
            assert not record['physical_keyboard_claim'] and not record['device_contacts']
            if lane=='observed':assert record['histogram'],'missing histogram'
            for item in [record['binary'],record['media_receipt'],*record['execution']['outputs'].values()]:
                assert bind(ROOT/item['path'])['sha256']==item['sha256'],'changed witness'
        a=lanes['control'];b=lanes['observed']
        for asset in ('rom','system_sd'):assert a[asset]==b[asset]
        get=lambda r:ROOT/r['execution']['outputs']['framebuffer']['path']
        assert get(a).read_bytes()==get(b).read_bytes(),'observer changed framebuffer oracle'
        if name=='capture-counters-at-stopped-point':
            assert a['stopped']['raw_bytes']==b['stopped']['raw_bytes']
            assert a['stopped']['all_equal'] and a['stopped']['all_nonzero']

def main():
    authority=MEDIA.check()
    instrument=json.loads((OUT/'instrument-build.json').read_text())
    base=json.loads((BASE/'dwx-xemu-cycle-probe-adapter.json').read_text())
    assert len(base['patches'])==3,'base fork patch population changed'
    proof=OUT/'observer-proof/receipt.json';proof_data=json.loads(proof.read_text())
    assert proof_data['instrument']==bind(OUT/'instrument-build.json')
    assert len([m for m in proof_data['mutations'] if m['expected_failure']])==8
    records={};receipts=[]
    for row in authority['rows']:
        name=row['id'];records[name]={}
        for lane in ('control','observed'):
            attempt='r3' if lane=='control' and name in CONTROL_R3 else 'r2'
            p=OUT/'mirrored'/attempt/lane/name/'receipt.json'
            records[name][lane]=json.loads(p.read_text());receipts.append(bind(p))
    validate(records,authority,instrument,base)
    # Executed mutations exercise the same complete admission function.
    mutations=[]
    for case in ('omitted-row','foreign-medium','foreign-world','inherited-result','comfort-entry','foreign-observer','missing-trace'):
        mutant=copy.deepcopy(records);name=next(iter(mutant));r=mutant[name]['observed']
        if case=='omitted-row':del mutant[name]
        elif case=='foreign-medium':r['row']['medium']['sha256']='0'*64
        elif case=='foreign-world':r['row']['world']['elf']['sha256']='0'*64
        elif case=='inherited-result':r['historical_results_inherited']=True
        elif case=='comfort-entry':r['comfort_entry']=True
        elif case=='foreign-observer':r['binary']['sha256']='0'*64
        elif case=='missing-trace':r['histogram']=None
        try:validate(mutant,authority,instrument,base)
        except AssertionError as exc:mutations.append(dict(name=case,rejected=str(exc) or case))
        else:raise AssertionError('mutation survived: '+case)
    POP.main()
    population=json.loads((OUT/'population.json').read_text())
    truth=ElfTruth.read(POP.ELF,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    state=[]
    for name,lanes in records.items():
        values={}
        for symbol in ('nsym','npool'):
            s=truth.symbol(symbol);pair=[]
            for lane in ('control','observed'):
                memory=ROOT/lanes[lane]['execution']['outputs']['memory']['path']
                raw=memory.read_bytes()[s.value:s.value+s.bytes];assert len(raw)==s.bytes
                pair.append(raw.hex())
            assert pair[0]==pair[1],(name,symbol,pair)
            values[symbol]=dict(address=s.value,raw=pair[0],used=int.from_bytes(bytes.fromhex(pair[0]),'little'))
        state.append(dict(row=name,state=values,framebuffer_byte_identical=True))
    receipt=OUT/'card0-receipt.json'
    receipt.write_text(json.dumps(dict(recorded_on=stable_recorded_on(receipt),
        status='CARD 0 REVIEW READY',authorization='84d6c1c2',world=authority['world'],
        qualifier=bind(Path(__file__)),population_tool=bind(Path(POP.__file__)),
        unchanged_product_medium=authority['source_product'],diagnostic_media=bind(MEDIA.BUILD/'receipt.json'),
        observer_proof=bind(proof),base_patch_set=base['patches'],diagnostic_patch=proof_data['diagnostic_patch'],
        row_receipts=receipts,rows=authority['rows'],neutrality=state,admission_mutations=mutations,
        population=bind(OUT/'population.json'),functions=population['function_count'],
        not_observed=population['not_observed'],primitive_entries=population['callprim']['limit'],
        observed_primitive_entries=sum(r['entries_observed']>0 for r in population['callprim']['entries']),
        product_builds=0,product_links=0,device_contacts=0,comfort_entry=False,comfort_claim=False,
        limits=population['limits']+['queue injection is not physical keyboard timing',
            'capture row proves queue conservation, not a collection crossing',
            'guest oracles/state and additive observer source are neutral; host elapsed time is not',
            'window ownership and call-graph/lifetime attribution remain card 1 obligations']),indent=2)+'\n')
    report=OUT/'card0-report.md'
    lines=['# Capacity card 0 — review report','',
        'Authorization: `84d6c1c2`. All eight active mirrored rows executed afresh on renderer-derived diagnostic media. No historical DWX result was inherited.',
        '', '## World and consumption','',
        f"Product ELF: `{authority['world']['elf']['sha256']}`.",
        f"Product PRG: `{authority['world']['prg']['sha256']}`.",
        f"Unchanged product medium: `{authority['source_product']['sha256']}`.",
        'Zero product compiles, links, or device contacts. Four diagnostic media variants add only INIT text or the sealed library/index. `repl-comfort` was required solely as a load witness; no `(repl)` entry and no Comfort claim.',
        '', '## Fresh row controls','',
        '| Row | Diagnostic medium SHA-256 | Result |','|---|---|---|']
    lines.extend(f"| {r['id']} | `{r['medium']['sha256']}` | observer/control PASS; framebuffer byte-identical |" for r in authority['rows'])
    capture=records['capture-counters-at-stopped-point']['observed']['stopped']
    lines+=['',f"Capture stopped-RAM record: `{capture['raw_bytes']}`; equal and nonzero in both lanes. Queue conservation is witnessed; neither a GC crossing nor physical keyboard behavior is claimed.",
        'All eight controls also agree on final `nsym` and `npool`. The valid INIT witness shows one `17` before the banner; the broken variant returns a type error and live prompt.',
        '', '## Instrument and population','',
        'The unchanged qualified three-patch fork is the control. The diagnostic fork adds the separately SHA-bound PC-observer patch; the historical EQ patch is not applied. 320 C/header sources are byte-identical; CPU observation is additive, UART changes add only explicit host snapshot/reset commands, and the generated build identity is attributed. Counter updates touch host state only and do not change guest cycle accounting. Host elapsed time is not neutral.',
        'Eight compiled and executed counter mutations reject omitted PC/PID counts, MAP aliases, hypervisor execution, missing arming, changed opcodes, ignored wraps and counter overflow. Seven admission mutations reject omitted rows, foreign media/world/fork, inherited results, Comfort entry and missing traces.',
        f"The population covers {population['function_count']} sized `.text` Function symbols, {len(population['physical_function_ranges'])} distinct physical ranges, and all {population['callprim']['limit']} CALLPRIM entries ({sum(r['entries_observed']>0 for r in population['callprim']['entries'])} observed). Entry-A/PID preservation and body ranges derive from emitted instructions; zero unresolved dispatch branches.",
        f"Important correction for pricing: 38,384 bytes is the sum of symbol sizes, including folded aliases. The physical sized-function ranges occupy {population['physical_function_bytes']:,} bytes inside the {population['text_section_bytes']:,}-byte `.text` section. The {len(population['executed_without_sized_function'])} observed PCs outside sized Function symbols are listed separately with their nearest labels, not silently omitted.",
        f"{len(population['not_observed'])} function symbols were not observed across the eight fresh rows plus the three renderer-native diagnostic groups. This is not dead-code evidence and not a reclaim price. Shared primitive bodies and aliases are never additive capacity. Mapped/window lifetimes and call-graph attribution remain card 1's obligations.",
        '', '## Local adapter corrections','',
        'The first packing attempt encountered PETSCII in c1541 stdout; binary-output handling fixed the host adapter and the interrupted diagnostic pack was verified before resuming. Initial boot-row attempts incorrectly queued an empty input and used a repository-only path binder for external ROM/SD paths. They were not promoted. A too-strict INIT assertion required an otherwise empty row despite banner graphics sharing its suffix; the corrected witness requires exactly one visible 17 before the banner. The affected control was rerun. All accepted executions and attempts are explicit in the receipt; no product change accompanied these corrections.',
        '', '## Verification and limits','',
        '`capacity_observer_proof.py` and `capacity_card0_qualify.py` pass. This report does not claim a new full `check-source`, release qualification, window mechanism, hardware timing, or Comfort acceptance. Removal/default: this observer exists only in the separate diagnostic fork; the product and normal three-patch fork remain unchanged.',
        '', 'Evidence: `card0-receipt.json`, `population.json`, `observer-proof/receipt.json`, and the per-row receipts referenced there.']
    report.write_text('\n'.join(lines)+'\n')
    print('CARD 0 REVIEW READY: eight fresh rows, eight control pairs, zero product consumption')

if __name__=='__main__':main()
