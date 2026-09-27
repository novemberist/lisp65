"""Nested-error recovery gate 6: natural single-key and batched lanes within 1.02 of the 2.4.0 Final.

The row role "anchor" is the accepted retained-callable 2.4.0 Final.

Reads the fresh paired r6 observer receipt (anchor rows reproduced bracket for
bracket, candidate measured with the same observer binary), retains every
bracket and every collection, and requires equal screen-write populations.
"""
from collections import Counter
import json
from pathlib import Path

import native_cycle_stationary as N
from elf_truth import ElfTruth

ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT/'build/input-cost-natural-card-l-r1/receipt.json'
OUT = ROOT/'build/card-l-r1/latency-qualification.json'
CEILING = 1.02


def gate(ratio, screen_equal, gc):
    assert 0 < ratio <= CEILING, 'natural lane exceeds 1.02 of the 2.4.0 Final'
    assert screen_equal, 'screen-write population changed'
    assert gc['baseline'] == gc['candidate'], 'collection count changed'


def main():
    r = json.loads(RECEIPT.read_text())
    assert r['status'].startswith('PASS')
    inputs = [N.bind(RECEIPT)]
    lanes = {}

    def counts(binding):
        p = N.checked_binding(binding)
        inputs.append(N.bind(p))
        return Counter({(a[0], int(a[1])): int(a[2]) for line in p.read_text().splitlines()
                        if (a := line.split())[0] in ('P', 'D')})
    for cap in (1, 8):
        pair = {x['world']: x for x in r['rows'] if x['batch_cap'] == cap}
        observed = {}
        for role, row in pair.items():
            N.verify_completion(row)
            N.verify_trace(row)
            t = ElfTruth.read(N.checked_binding(row['ELF']), llvm_readobj=ROOT/'tools/llvm-mos/bin/llvm-readobj')
            gc = t.symbol('gc_collect').value
            samples = []
            for item in row['pc_samples']:
                d = counts(item['after'])
                d.subtract(counts(item['before']))
                assert all(v >= 0 for v in d.values())
                samples.append(dict(gc=d['P', gc], screen_writes=d['D', 11]))
            observed[role] = dict(samples=samples, cycles=sum(row['cycle_deltas']),
                                  brackets=len(row['cycle_deltas']), gc=sum(s['gc'] for s in samples),
                                  cycles_per_key=sum(row['cycle_deltas'])/40)
        screen_equal = [s['screen_writes'] for s in observed['baseline']['samples']] == \
            [s['screen_writes'] for s in observed['candidate']['samples']]
        gc = {k: v['gc'] for k, v in observed.items()}
        ratio = observed['candidate']['cycles']/observed['baseline']['cycles']
        gate(ratio, screen_equal, gc)
        lanes[str(cap)] = dict(ratio=ratio, ceiling=CEILING, worlds=observed, excluded_samples=[],
                               screen_writes_equal=screen_equal, collections=gc)
    controls = []
    for name, args in [('above-1.02', (1.020001, True, {'baseline': 1, 'candidate': 1})),
                       ('screen-write-change', (1.0, False, {'baseline': 1, 'candidate': 1})),
                       ('collection-change', (1.0, True, {'baseline': 1, 'candidate': 0}))]:
        try:
            gate(*args)
        except AssertionError:
            controls.append(name)
        else:
            raise AssertionError('negative control survived: '+name)
    value = dict(status='PASS: NATURAL LANES WITHIN 1.02 OF THE 2.4.0 FINAL', binding='Card L Seed 2026-09-25',
                 lanes=lanes, mutations_rejected=controls, inputs=inputs+[N.bind(Path(__file__))],
                 claim='Emulator cycle observation with one qualified observer; no device claim.')
    assert not OUT.exists()
    OUT.write_text(json.dumps(value, indent=2)+'\n')
    print(value['status'], {k: (v['ratio'], v['collections'],
                                 v['worlds']['baseline']['cycles_per_key'], v['worlds']['candidate']['cycles_per_key'])
                            for k, v in lanes.items()})


if __name__ == '__main__':
    import argparse
    from card_l_r1_common import worlds
    p=argparse.ArgumentParser();p.add_argument('--dry-run',action='store_true');a=p.parse_args()
    worlds()
    if a.dry_run:print('DRY RUN PASS: offline lane comparator; no emulator commands; ratio <=1.02, equal screen writes and GC counts')
    else:main()
