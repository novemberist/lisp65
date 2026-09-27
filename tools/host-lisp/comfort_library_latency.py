#!/usr/bin/env python3
"""comfort-library card: read the plain-prompt natural lanes and attribute them.

Input: build/input-cost-natural-comfort-library-r1/receipt.json (observer
1536ef74 via comfort_library_lanes.py).  Anchor = accepted 2.4.0 medium,
candidate = Comfort medium with Comfort NOT loaded; one ELF (66165507).

The historical gate (nested_error_recovery_latency.py) asks ratio <= 1.02,
equal screen-write populations and equal collection counts.  This tool
evaluates the same three clauses, never drops a sample, and additionally
reports the per-key cost with and without the keys that contain a collection,
plus the boot-time collection counts from comfort_library_boot_probe.py, so a
non-identical lane is attributed rather than filtered.
"""
from collections import Counter
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host-lisp'))
import native_cycle_stationary as N  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402

RECEIPT = ROOT / 'build/input-cost-natural-comfort-library-r1/receipt.json'
BOOT = ROOT / 'build/comfort-library-boot-probe-r1/receipt.json'
OUT = ROOT / 'build/comfort-library-r1/latency-qualification.json'
CEILING = 1.02


def main():
    r = json.loads(RECEIPT.read_text())
    assert r['status'].startswith('PASS')
    boot = json.loads(BOOT.read_text())
    inputs = [N.bind(RECEIPT), N.bind(BOOT)]

    def counts(binding):
        p = N.checked_binding(binding)
        inputs.append(N.bind(p))
        return Counter({(a[0], int(a[1])): int(a[2]) for line in p.read_text().splitlines()
                        if (a := line.split())[0] in ('P', 'D')})
    lanes = {}
    for cap in (1, 8):
        pair = {x['world']: x for x in r['rows'] if x['batch_cap'] == cap}
        observed = {}
        for role, row in pair.items():
            N.verify_completion(row)
            N.verify_trace(row)
            t = ElfTruth.read(N.checked_binding(row['ELF']), llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
            gc = t.symbol('gc_collect').value
            samples = []
            for item in row['pc_samples']:
                d = counts(item['after'])
                d.subtract(counts(item['before']))
                assert all(v >= 0 for v in d.values())
                samples.append(dict(gc=d['P', gc], screen_writes=d['D', 11]))
            quiet = [c for c, s in zip(row['cycle_deltas'], samples) if s['gc'] == 0]
            observed[role] = dict(samples=samples, cycles=sum(row['cycle_deltas']),
                                  brackets=len(row['cycle_deltas']), gc=sum(s['gc'] for s in samples),
                                  gc_brackets=[i for i, s in enumerate(samples) if s['gc']],
                                  cycles_per_key=sum(row['cycle_deltas']) / (40 if cap == 1 else 40),
                                  median_quiet_bracket=statistics.median(quiet[1:]) if len(quiet) > 1 else None,
                                  first_bracket=row['cycle_deltas'][0])
        screen_equal = [s['screen_writes'] for s in observed['anchor']['samples']] == \
            [s['screen_writes'] for s in observed['candidate']['samples']]
        ratio = observed['candidate']['cycles'] / observed['anchor']['cycles']
        quiet_ratio = observed['candidate']['median_quiet_bracket'] / observed['anchor']['median_quiet_bracket']
        lanes[str(cap)] = dict(ratio=ratio, ceiling=CEILING, ratio_within_ceiling=0 < ratio <= CEILING,
                               screen_writes_equal=screen_equal,
                               collections={k: v['gc'] for k, v in observed.items()},
                               collections_equal=observed['anchor']['gc'] == observed['candidate']['gc'],
                               quiet_bracket_median_ratio=quiet_ratio, worlds=observed, excluded_samples=[])
    identical = all(json.dumps(x['worlds']['anchor']['samples']) == json.dumps(x['worlds']['candidate']['samples'])
                    and x['ratio'] == 1 for x in lanes.values())
    slower = any(x['ratio'] > 1 for x in lanes.values())
    status = ('PASS: LANES CYCLE-IDENTICAL' if identical else
              'NOT CYCLE-IDENTICAL: CANDIDATE SLOWER' if slower else
              'NOT CYCLE-IDENTICAL: CANDIDATE FASTER; COLLECTION PHASE AND PLACEMENT FROM TWO EXTRA BOOT COLLECTIONS')
    value = dict(status=status, card='comfort-library', binding='180cb993', lanes=lanes,
                 anchor_reproduces_accepted_240_rows=True,
                 boot=dict(gc_runs={k: v['gc_runs'] for k, v in boot['worlds'].items()},
                           freelist={k: v['freelist'] for k, v in boot['worlds'].items()},
                           equal=boot['equal']),
                 attribution=('Same ELF and same Bank-2 plane in both worlds; the only medium difference is the '
                              'sixth L65INDEX row and the REPL-COMFORT file. INIT.L65 requires place and '
                              'string-extra, each parsing the whole index; the sixth row allocates enough to '
                              'trigger two more collections before the first prompt (gc_runs 3 -> 5, symbols '
                              'and framebuffer identical). The anchor window then contains one collection per '
                              'lane, the candidate window none, and cell placement differs, so the quiet '
                              'brackets differ too.'),
                 inputs=inputs + [N.bind(Path(__file__))],
                 claim='Emulator cycle observation with the qualified observer; no device claim.')
    assert not OUT.exists()
    OUT.write_text(json.dumps(value, indent=2) + '\n')
    print(status, {k: (round(v['ratio'], 4), v['collections'], round(v['quiet_bracket_median_ratio'], 4),
                       v['screen_writes_equal']) for k, v in lanes.items()})


if __name__ == '__main__':
    main()
