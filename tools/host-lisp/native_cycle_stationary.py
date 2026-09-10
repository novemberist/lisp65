#!/usr/bin/env python3
"""c5b4a6f7 all-sample lanes and 42783302 character-plus-taken cutpoints.

Historical stationary receipts remain immutable. The filename is retained
for the existing gate; its live contract no longer drops sample zero.
"""
import argparse
import copy
import hashlib
import json
import tempfile
from pathlib import Path

AUTHORITY = 'c5b4a6f7'
CEILING = 1.02
ROOT = Path(__file__).resolve().parents[2]


def input_complete(screen_byte, expected_byte, taken, expected_taken):
    """42783302: a cursor write is not input completion."""
    return screen_byte == expected_byte and taken == expected_taken


def completion_selftest():
    assert input_complete(1, 1, 40, 40)
    cases = [('cursor-only', 0xa0, 39), ('cursor-after-take', 0xa0, 40),
             ('character-before-take', 1, 39), ('extra-take', 1, 41),
             ('wrong-character', 2, 40)]
    for _, char, taken in cases:
        assert not input_complete(char, 1, taken, 40)
    # Execute the historical predicate on the recorded kind of cursor write:
    # it accepts, whereas the live predicate rejects the same observation.
    assert 0xa0 != 0x20
    assert not input_complete(0xa0, 1, 39, 40)
    return [x[0] for x in cases] + ['old-any-write-mutant']


def verify_completion(row):
    assert row['completion_authority'] == '42783302'
    samples=row['completion_samples'];cap=row['batch_cap']
    assert len(samples)*cap==row['characters']
    assert row['initial_counters']==[0]*4
    for i,s in enumerate(samples):
        expected=(i+1)*cap
        assert s['index']==i*cap and s['expected_taken']==expected
        assert s['expected_screen_byte']==1 and s['counters']==[expected]*4
        assert input_complete(s['screen_byte'],1,s['counters'][3],expected)


def histogram_calls(binding, pc, primitive):
    counts={};dispatch={}
    for line in checked_binding(binding).read_text().splitlines():
        w=line.split()
        if w[0]=='P':counts[int(w[1])]=int(w[2])
        elif w[0]=='D':dispatch[int(w[1])]=int(w[2])
    return counts.get(pc,0),dispatch.get(primitive,0)


def validate_ready_state(state):
    assert state['authority']=='1536ef74'
    assert state['entry_calls']==1 and state['key_event_calls']==1
    assert state['paused_pc']==state['entry_pc']+1 and state['mode']==2
    assert state['prompt_cursor_byte']==0xa0 and state['counters']==[0]*4
    assert state['screen_calls_at_entry']>0
    assert state['screen_calls_before_injection']==state['screen_calls_at_entry']
    assert state['screen_calls_after_injection']==state['screen_calls_at_entry']


def verify_ready_trace(row):
    """Re-derive the reported readiness from ELF and the bound PC snapshots."""
    from elf_truth import ElfTruth
    ready=row['readiness'];validate_ready_state(ready)
    assert ready['ELF']['sha256']==row['ELF']['sha256']
    elf=checked_binding(row['ELF'])
    e=ElfTruth.read(elf,llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj',include_section_data=True)
    s=e.symbol('c2_kernal_input_take');sec=e.section(s.section)
    raw=e.section_bytes(s.section)[s.value-sec.address:s.value-sec.address+s.bytes]
    assert ready['entry_pc']==s.value and ready['entry_code']==raw.hex()
    assert raw[0]==0xaa and ready['paused_pc']==s.value+1
    ledger=json.loads((ROOT/'config/bytecode-abi-ledger.json').read_text())
    pids={x['canonical_name']:x['id'] for x in ledger['prim_identities']}
    assert ready['screen_primitive']==pids['screen-put-char'] and ready['key_primitive']==pids['key-event']
    snapshots=[checked_binding(ready[k]) for k in ('entry_snapshot','before_injection','after_injection')]
    assert snapshots[0].read_bytes()==snapshots[1].read_bytes()==snapshots[2].read_bytes(), 'guest execution between readiness and injection'
    rows=[line.split() for line in snapshots[0].read_text().splitlines()]
    assert rows[0][:2]==['H','1'], 'unarmed PC observer'
    entry_rows=[w for w in rows if w[0]=='P' and int(w[1])==s.value]
    assert len(entry_rows)==1 and list(map(int,entry_rows[0][2:]))==[1,0xaa,0], 'wrong or changed consumer opcode'
    entry,screen=histogram_calls(ready['entry_snapshot'],s.value,pids['screen-put-char'])
    _,key=histogram_calls(ready['entry_snapshot'],s.value,pids['key-event'])
    assert entry==ready['entry_calls']==1 and key==ready['key_event_calls']==1
    assert screen==ready['screen_calls_at_entry']


def readiness_selftest():
    good=dict(authority='1536ef74',entry_calls=1,key_event_calls=1,
        entry_pc=0x8000,paused_pc=0x8001,mode=2,prompt_cursor_byte=0xa0,counters=[0]*4,
        screen_calls_at_entry=308,screen_calls_before_injection=308,screen_calls_after_injection=308)
    validate_ready_state(good);rejected=[]
    for name,patch in [('injection-before-ready',dict(entry_calls=0)),
        ('visible-prompt-only',dict(entry_calls=0,key_event_calls=0,screen_calls_at_entry=280)),
        ('second-poll-not-first',dict(entry_calls=2,key_event_calls=2)),
        ('screen-write-before-injection',dict(screen_calls_before_injection=309)),
        ('screen-write-during-injection',dict(screen_calls_after_injection=309)),
        ('input-consumed-before-start',dict(counters=[1]*4)),
        ('wrong-input-mode',dict(mode=3))]:
        try:validate_ready_state(dict(good,**patch))
        except AssertionError:rejected.append(name)
        else:raise AssertionError(name)
    return rejected


def completed_cycle_trace(run_id, medium, characters, output, args, elf_binding, cap=1, pc_snapshot=None, require_ready=True):
    """Existing media only; bracket actual screen-character AND taken-event completion.

    A premature cursor watchpoint is resumed without injecting another key.
    This retains all intervening cycles and records every rejected cutpoint.
    """
    import time
    import dwx_retroactive_red_replay as R
    from elf_truth import ElfTruth
    assert cap in (1, 8) and 0 < characters < 256 and characters % cap == 0
    elf = checked_binding(elf_binding)
    truth = ElfTruth.read(elf, llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    counters = [truth.symbol('C2K_INPUT_EVENTS_'+n) for n in ('RAW','SEEN','STORED','TAKEN')]
    assert all(s.section == 'Absolute' for s in counters)
    assert [s.value for s in counters] == list(range(counters[0].value, counters[0].value+4))
    gc = truth.symbol('gc_runs'); assert gc.bytes == 2
    run = R.start_run(run_id, medium, output, args)
    try:
        m = run['monitor']; m.command('t1')
        start = R.find_input_start(m, 0x0800)
        initial = m.memory16(counters[0].value)[:4]
        assert initial == bytes(4), 'fresh input population must start at zero'
        ready=copy.deepcopy(getattr(m,'readiness',None))
        if require_ready:assert ready is not None and pc_snapshot is not None
        deltas=[]; targets=[]; samples=[]; collections=[]; pcs=[]
        for index in range(0, characters, cap):
            target=start+index+cap-1; expected=index+cap
            assert m.memory16(target)[0] in (0,0x20,0xa0)
            assert m.memory16(counters[3].value)[0] == index
            m.command(f'w {target:08x}')
            gc_before=m.memory16(gc.value).hex()
            pc_before=pc_snapshot(m,run,index,'before') if pc_snapshot else None
            if index==0 and ready is not None:
                entry_calls,screen_calls=histogram_calls(pc_before,ready['entry_pc'],ready['screen_primitive'])
                assert entry_calls==1
                ready['screen_calls_before_injection']=screen_calls
                ready['before_injection']=pc_before
            before=m.cycle_count()
            if cap==1: m.queue_one(ord('a'))
            else: m.command('~typehex '+(b'a'*cap).hex())
            if index==0 and ready is not None:
                injected=pc_snapshot(m,run,index,'injected')
                entry_calls,screen_calls=histogram_calls(injected,ready['entry_pc'],ready['screen_primitive'])
                assert entry_calls==1
                ready['screen_calls_after_injection']=screen_calls
                ready['after_injection']=injected
                validate_ready_state(ready)
            m.command('t0'); deadline=time.monotonic()+20
            rejected=[]; after=before
            while time.monotonic()<deadline:
                first=m.cycle_count(); time.sleep(.002); after=m.cycle_count()
                if first != after: continue
                char=m.memory16(target)[0]
                seen=m.memory16(counters[0].value)[:4]
                if input_complete(char, 1, seen[3], expected): break
                rejected.append(dict(screen_byte=char,counters=list(seen),cycles=after-before))
                assert seen[3] <= expected, 'extra input consumption'
                m.command('t0')
            else: raise AssertionError('character-plus-taken cutpoint timeout')
            assert after>before and seen==bytes([expected])*4
            pc_after=pc_snapshot(m,run,index,'after') if pc_snapshot else None
            pcs.append(dict(index=index,before=pc_before,after=pc_after))
            samples.append(dict(index=index,expected_taken=expected,expected_screen_byte=1,
                screen_byte=char,counters=list(seen),rejected_cutpoints=rejected))
            collections.append(dict(before=gc_before,after=m.memory16(gc.value).hex()))
            deltas.append(after-before);targets.append(f'0x{target:04X}')
        assert m.memory_range(start, characters) == bytes([1])*characters
        trace=dict(characters=characters,input_byte='0x61',screen_start=f'0x{start:04X}',
            screen_write_targets=targets,cycle_deltas=deltas,total_cycles=sum(deltas),
            mean_cycles_per_key=sum(deltas)/characters,minimum_cycles=min(deltas),maximum_cycles=max(deltas),
            completion_authority='42783302',completion_samples=samples,
            counter_symbols=[dict(name=s.name,address=s.value) for s in counters],
            initial_counters=list(initial),gc_counter=dict(symbol='gc_runs',address=gc.value,bytes=2,ELF=elf_binding['sha256']),
            gc_samples=collections,pc_samples=pcs,observer=bind(Path(__file__)))
        if ready is not None:trace['readiness']=ready
        path=run['dir']/'cycle-trace.json';path.write_text(json.dumps(trace,indent=2)+'\n')
        trace['outputs']=R.finish_run(run,m.screen());trace['artifact']=bind(path)
        return trace
    except BaseException:
        R.abort_run(run);raise


def population(rows):
    assert len(rows) == 4
    assert {(r['world'], r['batch_cap']) for r in rows} == {
        (w, c) for w in ('baseline', 'candidate') for c in (1, 8)}
    for r in rows:
        samples = r['cycle_deltas']
        assert len(samples) >= 2 and all(type(x) is int and x > 0 for x in samples)
        assert len(samples) * r['batch_cap'] == r['characters']
        assert sum(samples) == r['total_cycles']


def gc_delta(row, index):
    counter = row['gc_counter']
    assert counter['symbol'] == 'gc_runs' and counter['bytes'] == 2
    assert len(row['gc_samples']) == len(row['cycle_deltas'])
    sample = row['gc_samples'][index]
    before, after = (bytes.fromhex(sample[k]) for k in ('before', 'after'))
    assert len(before) == len(after) == 16
    return (int.from_bytes(after[:2], 'little')-
            int.from_bytes(before[:2], 'little')) % 65536


def witnessed_indices(rows, attribution):
    """An independently observed collection must disappear at this index on repeat.

    Stable same-index costs do not qualify. Both complete repeated worlds
    remain in the receipt, including deviations at any other indices.
    Filesystem/ELF provenance is checked by verify_attribution before use.
    """
    if attribution is None:
        return {1: set(), 8: set()}
    assert attribution['kind'] == 'gc-counter'
    repeat = attribution['repeat_rows'];population(repeat)
    assert attribution['observer']['sha256']
    result = {1: set(), 8: set()}
    for r in rows:
        rr = next(x for x in repeat if (x['world'], x['batch_cap']) ==
                  (r['world'], r['batch_cap']))
        for key in ('ELF', 'medium'):
            assert r[key]['sha256'] == rr[key]['sha256']
        assert r['characters'] == rr['characters']
        assert r['input_byte'] == rr['input_byte']
    for event in attribution['events']:
        cap, index = event['batch_cap'], event['index']
        assert cap in result and type(index) is int and index >= 0
        assert index not in result[cap]
        pair = {w: next(r for r in rows if r['world']==w and r['batch_cap']==cap)
                for w in ('baseline', 'candidate')}
        again = {w: next(r for r in repeat if r['world']==w and r['batch_cap']==cap)
                 for w in pair}
        assert index < len(pair['baseline']['cycle_deltas'])
        deltas = {w: gc_delta(r,index) for w,r in pair.items()}
        busy = [w for w,n in deltas.items() if 0 < n < 32768]
        assert len(busy)==1 and deltas[next(w for w in pair if w!=busy[0])]==0
        assert all(gc_delta(r,index)==0 for r in again.values())
        b,c = (again[w]['cycle_deltas'][index] for w in ('baseline','candidate'))
        assert abs(c-b)*200 <= b, 'same-index cost reproduces; no event exclusion'
        b,c = (pair[w]['cycle_deltas'][index] for w in ('baseline','candidate'))
        assert abs(c-b)*200 > b
        assert (c>b) == (busy[0]=='candidate'), 'counter does not explain cost direction'
        result[cap].add(index)
    assert any(result.values()) or attribution.get('repeat_events'), 'empty attribution is not a witness'
    return result


def derive(rows, attribution=None, *, _assess_repeat=True):
    population(rows)
    exclusions = witnessed_indices(rows, attribution)
    lanes = {}
    for cap in (1, 8):
        pair = {w: next(r for r in rows if r['world'] == w and r['batch_cap'] == cap)
                for w in ('baseline', 'candidate')}
        assert pair['baseline']['characters'] == pair['candidate']['characters']
        assert pair['baseline']['input_byte'] == pair['candidate']['input_byte']
        b,c = (pair[w]['cycle_deltas'] for w in ('baseline','candidate'))
        total = sum(b)
        deviations = [dict(index=i, baseline=x, candidate=y, delta=y-x,
                          absolute_fraction_of_baseline_lane=abs(y-x)/total,
                          witness=('gc-counter' if i in exclusions[cap] else None))
                      for i,(x,y) in enumerate(zip(b,c)) if abs(y-x)*200>x]
        kept = [i for i in range(len(b)) if i not in exclusions[cap]]
        assert kept, 'no paired samples remain'
        raw = sum(c)/total
        ratio = sum(c[i] for i in kept)/sum(b[i] for i in kept)
        unresolved = [d['index'] for d in deviations if
                      d['witness'] is None and abs(d['delta'])*100>total]
        lanes[str(cap)] = dict(excluded_sample_indices=sorted(exclusions[cap]),
            event_sample_count=len(exclusions[cap]), deviations=deviations,
            unattributed_large_indices=unresolved, all_samples_ratio=raw,
            ratio=ratio, retained_samples=len(kept),
            first_input_phase_cycles={w:r['cycle_deltas'][0] for w,r in pair.items()},
            boot_phase_delta=c[0]-b[0],
            status='PASS' if ratio<=CEILING and not unresolved else 'HALT_ATTRIBUTION')
    repeat_result = None
    if attribution is not None and _assess_repeat:
        reverse = None
        if attribution.get('repeat_events'):
            reverse = dict(kind=attribution['kind'], observer=attribution['observer'],
                           repeat_rows=rows, events=attribution['repeat_events'])
        repeat_result = derive(attribution['repeat_rows'], reverse, _assess_repeat=False)
    return dict(authority=AUTHORITY, ceiling=CEILING, lanes=lanes,
        ratios={k:v['ratio'] for k,v in lanes.items()},
        status='PASS' if all(v['status']=='PASS' for v in lanes.values()) and
        (repeat_result is None or repeat_result['status']=='PASS') else 'HALT_ATTRIBUTION',
        repeat_assessment=repeat_result,
        attribution=attribution,
        claim='Emulated CPU/DMA, all samples by default; exclusions require repeat plus independent GC evidence; no physical-keyboard claim')


def validate(rows, result):
    expected = derive(rows, result.get('attribution'))
    for key in expected:
        assert result[key] == expected[key], key


def verify_trace(row):
    """The fields being priced must be those in the SHA-bound raw trace."""
    item = row['artifact'];path = Path(item['path'])
    if not path.is_absolute(): path = ROOT/path
    assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256']
    raw = json.loads(path.read_text())
    for key in ('cycle_deltas', 'characters', 'total_cycles', 'input_byte'):
        assert row[key] == raw[key], key
    for key in ('screen_start', 'screen_write_targets'):
        if key in row: assert row[key] == raw[key], key
    for key in ('gc_counter', 'gc_samples', 'completion_authority', 'completion_samples', 'readiness',
                'counter_symbols', 'initial_counters'):
        if key in row: assert row[key] == raw[key], key
    if 'completion_authority' in row: verify_completion(row)
    if 'readiness' in row:verify_ready_trace(row)


def checked_binding(item):
    path = Path(item['path'])
    if not path.is_absolute(): path = ROOT/path
    assert bind(path)['sha256'] == item['sha256'], path
    return path


def verify_attribution(rows, attribution, readobj):
    """Close actual RAM-counter location through each unchanged world's ELF."""
    from elf_truth import ElfTruth
    assert readobj is not None, 'ELF authority reader required for exclusions'
    checked_binding(attribution['observer'])
    original_paths = {str(checked_binding(r['artifact'])) for r in rows}
    repeat_paths = {str(checked_binding(r['artifact'])) for r in attribution['repeat_rows']}
    assert original_paths.isdisjoint(repeat_paths), 'repeat must be a separate run'
    truths = {}
    for row in rows + attribution['repeat_rows']:
        verify_trace(row)
        elf = checked_binding(row['ELF']);checked_binding(row['medium'])
        if elf not in truths: truths[elf] = ElfTruth.read(elf, llvm_readobj=readobj)
        sym = truths[elf].symbol('gc_runs')
        assert row['gc_counter'] == dict(symbol='gc_runs', address=sym.value,
                                         bytes=sym.bytes, ELF=row['ELF']['sha256'])
        assert len(row['gc_samples']) == len(row['cycle_deltas'])
        for i in range(len(row['gc_samples'])): gc_delta(row,i)
    witnessed_indices(rows, attribution)


def selftest():
    completion_selftest()
    readiness_selftest()
    rows = []
    for world in ('baseline', 'candidate'):
        for cap in (1, 8):
            samples = [100000] * 40
            rows.append(dict(world=world, batch_cap=cap, cycle_deltas=samples,
                             characters=cap*len(samples), total_cycles=sum(samples),
                             ELF={'sha256':world}, medium={'sha256':world},
                             input_byte='0x61',
                             gc_counter=dict(symbol='gc_runs', bytes=2),
                             gc_samples=[dict(before='00'*16,after='00'*16) for _ in samples]))
    good = derive(rows); validate(rows, good)
    assert good['status'] == 'PASS' and all(x == 1 for x in good['ratios'].values())
    rejected = []
    def reject(label, fn):
        try: fn()
        except (AssertionError, KeyError): rejected.append(label)
        else: raise AssertionError(label+' survived')
    slower = copy.deepcopy(rows)
    for r in slower:
        if r['world']=='candidate':
            r['cycle_deltas'][:30] = [103000]*30
            r['total_cycles'] = sum(r['cycle_deltas'])
    slow = derive(slower)
    assert slow['status']=='HALT_ATTRIBUTION'
    assert all(v==1.0225 for v in slow['ratios'].values())
    reject('30-of-40-cost-filter', lambda: validate(slower,good))
    event_rows=copy.deepcopy(rows)
    event=next(r for r in event_rows if r['world']=='candidate' and r['batch_cap']==1)
    event['cycle_deltas'][8]=3300000;event['total_cycles']=sum(event['cycle_deltas'])
    event['gc_samples'][8]['after']='0100'+'00'*14
    assert derive(event_rows)['status']=='HALT_ATTRIBUTION'
    # A first-sample shift must no longer be dropped automatically either.
    first=copy.deepcopy(event_rows)
    r=next(r for r in first if r['world']=='candidate' and r['batch_cap']==1)
    r['cycle_deltas'][0],r['cycle_deltas'][8]=r['cycle_deltas'][8],r['cycle_deltas'][0]
    assert derive(first)['status']=='HALT_ATTRIBUTION'
    witness=dict(kind='gc-counter',observer={'sha256':'selftest'},repeat_rows=rows,
                 events=[dict(batch_cap=1,index=8)])
    witnessed=derive(event_rows,witness);validate(event_rows,witnessed)
    assert witnessed['status']=='PASS' and witnessed['lanes']['1']['excluded_sample_indices']==[8]
    hidden_repeat=copy.deepcopy(witness)
    r=next(r for r in hidden_repeat['repeat_rows'] if r['world']=='candidate' and r['batch_cap']==1)
    r['cycle_deltas'][20]=3300000;r['total_cycles']=sum(r['cycle_deltas'])
    assert derive(event_rows,hidden_repeat)['status']=='HALT_ATTRIBUTION'
    for label, mutate in (
        ('missing-witness',lambda x:x.pop('attribution')),
        ('silent-event-inclusion',lambda x:x['lanes']['1'].update(excluded_sample_indices=[])),
        ('silent-extra-exclusion',lambda x:x['lanes']['8'].update(excluded_sample_indices=[0]))):
        trial=copy.deepcopy(witnessed);mutate(trial)
        reject(label,lambda:validate(event_rows,trial))
    for label, mutate in (
        ('missing-observer',lambda x:x.pop('observer')),
        ('different-repeat-world',lambda x:x['repeat_rows'][0]['ELF'].update(sha256='wrong')),
        ('persistent-event',lambda x:x.update(repeat_rows=event_rows)),
        ('wrong-event-index',lambda x:x['events'][0].update(index=7))):
        trial=copy.deepcopy(witness);mutate(trial)
        reject(label,lambda:derive(event_rows,trial))
    no_counter=copy.deepcopy(event_rows)
    next(r for r in no_counter if r['world']=='candidate' and r['batch_cap']==1).pop('gc_samples')
    reject('missing-counter',lambda:derive(no_counter,witness))
    # A negative >1%-of-lane event also requires attribution, despite ratio <1.02.
    faster=copy.deepcopy(rows)
    r=next(r for r in faster if r['world']=='candidate' and r['batch_cap']==1)
    r['cycle_deltas'][9]=100;r['total_cycles']=sum(r['cycle_deltas'])
    assert derive(faster)['status']=='HALT_ATTRIBUTION'
    for key, value in (('ceiling', 1.03), ('status', 'RED')):
        bad = copy.deepcopy(good);bad[key] = value
        reject(key,lambda:validate(rows,bad))
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'trace.json'
        row = copy.deepcopy(rows[0]);path.write_text(json.dumps(row))
        row['artifact'] = bind(path);verify_trace(row)
        row['cycle_deltas'][1] += 1;row['total_cycles'] += 1
        reject('priced-fields-diverge-from-bound-trace',lambda:verify_trace(row))
        row = copy.deepcopy(rows[0]);row['artifact']=bind(path)
        row['gc_samples'][0]['after']='0100'+'00'*14
        reject('counter-fields-diverge-from-bound-trace',lambda:verify_trace(row))
    return rejected


def bind(path):
    return dict(path=str(path), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path);p.add_argument('--output', type=Path)
    p.add_argument('--selftest', action='store_true')
    p.add_argument('--attribution', type=Path)
    p.add_argument('--llvm-readobj', type=Path)
    args = p.parse_args()
    mutations = selftest()
    if args.selftest:
        print('native-cycle-stationary: PASS mutations='+str(len(mutations))+
              ' completion_mutations='+str(len(completion_selftest()))+
              ' readiness_mutations='+str(len(readiness_selftest())))
    if args.input:
        assert args.output and not args.output.exists(), 'never overwrite a measured receipt'
        old = json.loads(args.input.read_text())
        for row in old['rows']:
            verify_trace(row)
            verify_ready_trace(row)
        attribution = json.loads(args.attribution.read_text()) if args.attribution else None
        if attribution: verify_attribution(old['rows'],attribution,args.llvm_readobj)
        result = derive(old['rows'],attribution)
        result.update(rows=old['rows'], input=bind(args.input), adapter=bind(Path(__file__)),
                      mutations_rejected=mutations)
        validate(old['rows'], result)
        args.output.write_text(json.dumps(result, indent=2)+'\n')
        print(result['status'], result['ratios'])
        assert result['status'] == 'PASS'
    else:
        assert args.selftest


if __name__ == '__main__': main()
