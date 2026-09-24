"""Seal the read-only outside-Append attribution and its budget hold."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import definition_set_a_outside_attribution as A
from elf_truth import ElfTruth

ROOT = A.ROOT
TARGET = ROOT/'tests/bytecode/dialect-v2/evidence/architecture-blocks/definition-set-a-outside-attribution.json'


def bind(path):
    path = path.resolve()
    data = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))


def receipt(directory):
    path = ROOT/directory/'receipt.json'
    result = json.loads(path.read_text())
    assert result['status'] == 'PASS'
    return result


def delta(receipt, tag, column=2):
    def values(binding):
        return Counter({int(w[1]): int(w[column]) for line in A.checked(binding).read_text().splitlines()
                        if (w := line.split()) and w[0] == tag})
    whole = receipt['whole']
    return A.subtract(values(whole['after']), values(whole['before']))


def main():
    assert not TARGET.exists(), 'never replace an attribution seal'
    roots = [
        'build/definition-set-a-emitter-before-5-r2/receipt.json',
        'build/definition-set-a-emitter-seed-5-r2/receipt.json',
        'build/definition-set-a-stages-before-5-r1/receipt.json',
        'build/definition-set-a-stages-seed-5-r2/receipt.json',
        'build/definition-set-a-prerequisites-r1/receipt.json',
        'build/definition-ledger-full-5-r2/receipt.json',
        'build/definition-set-a-ledger-5-r2/receipt.json',
    ]
    records = [json.loads((ROOT/p).read_text()) for p in roots]
    assert all(r['status'] == 'PASS' for r in records)
    b, s = records[2:4]
    stages = []
    labels = ['dispatch/registration and Lisp bridge', 'macro expansion excluding GC',
              'compilation excluding GC', 'native emission/install excluding Append and GC',
              'Append', 'GC, all inclusive native calls']
    for r in (b, s):
        values = A.subtract(A.counts(r['whole']['after'], 'K'), A.counts(r['whole']['before'], 'K'))
        assert sum(values.values()) == r['whole']['cycles']
        stages.append(values)
    before, after = stages
    rows = [dict(stage=labels[i], before=before[i], after=after[i], delta=after[i]-before[i]) for i in range(6)]
    original = receipt('build/definition-set-a-ledger-5-r2')
    pc_repeat = A.subtract(delta(s, 'C'), delta(original, 'C'))
    assert sum(pc_repeat.values()) == 91
    truth = ElfTruth.read(A.checked(s['elf']), llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
    poll = truth.symbol('c2_kernal_event_poll')
    assert all((0x4c2c <= pc <= 0x4c6c) or poll.value <= pc < poll.value + poll.bytes
               for pc, value in pc_repeat.items() if value)
    # Identical DMA; all 91 repeat cycles belong to the named event-poll PCs.
    assert sum(delta(s, 'T', 3).values()) == sum(delta(original, 'T', 3).values())
    assert b['whole']['cycles'] == records[0]['whole']['cycles'] == 1263886293
    assert records[1]['whole']['cycles'] == original['whole']['cycles'] == 818182246
    old = A.world('build/definition-ledger-full-5-r2')
    new = A.world('build/definition-set-a-ledger-5-r2')
    exact_delta = new['outside_exact'] - old['outside_exact']
    assert exact_delta == 116789185
    assert sum(row['delta'] for i,row in enumerate(rows) if i != 4)-91 == exact_delta
    calls = []
    for r in records[:2]:
        t = ElfTruth.read(A.checked(r['elf']), llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
        counts = delta(r, 'P')
        row = {}
        for name in ('gc_collect', 'c2_session_emit_add', 'rtov_crc_mem',
                     'vm_runtime_overlay_transaction_begin', 'vm_runtime_overlay_transaction_end'):
            row[name] = counts[t.symbol(name).value]
        calls.append(row)
    assert [r['gc_collect'] for r in calls] == [13,14]
    assert [r['c2_session_emit_add'] for r in calls] == [18,18]
    paths = set(roots)
    def consume(value):
        if isinstance(value, dict):
            if 'path' in value and 'sha256' in value:
                path = A.checked(value)
                paths.add(str(path.relative_to(ROOT)))
            for v in value.values(): consume(v)
        elif isinstance(value, list):
            for v in value: consume(v)
    for r in records: consume(r)
    for name in ('emitter_ledger', 'stage_ledger', 'outside_attribution', 'prerequisite_native', 'attribution_seal'):
        paths.add(f'tools/host-lisp/definition_set_a_{name}.py')
    for directory in ('definition-set-a-emitter-observer-r1','definition-set-a-stage-observer-r1'):
        for name in ('xemu/cpu65.c','xemu/definition_observer.h','build/bin/xmega65.native'):
            paths.add(f'build/{directory}/{name}')
    paths.update(('build/definition-ledger-r1/full-r2.py',
                  'build/definition-pricing-r4/native-helper-witness.py',
                  'src/c2_product_runtime.c','src/c2_session_emitter.c','src/vm_runtime_overlay.c',
                  'docs/planning/definition-set-a-outside-attribution.md'))
    result = dict(status='ATTRIBUTED; HOLD FOR REPAIR-SEED BUDGET', authority='81779edf',
                  product_builds_this_round=0, consumed_budget=dict(seed=1,final=0,link=0),
                  stages=rows, outside_exact_delta=exact_delta,
                  first_report_boundary_correction=17, cycles_per_second=40500000,
                  repeat_event_poll_delta=91,
                  repeat_pc_delta={hex(k):v for k,v in pc_repeat.items() if v},
                  counts=calls,
                  prerequisite_result='compile/save/load/use 7; later helper 42; 19 original work-media files unchanged',
                  proposed_scope='Native bounded authentication around emitter control work; no transaction across Lisp returns; price and abort proof before an authorized replacement Seed',
                  remaining=['repair decision/budget','native injected-abort control','both Lanes','matched GC','full check-source','Final/link'],
                  bindings=[bind(ROOT/p) for p in sorted(paths)])
    TARGET.write_text(json.dumps(result,indent=2)+'\n')
    print('SEALED',len(paths),'bindings; outside delta',exact_delta)


if __name__ == '__main__': main()
