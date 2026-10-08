"""2.5.5 r4 string-codec workload successor; the v254 r3 receipt stays immutable.

The 2.5.5 typing card changes three bound inputs of the codec workload world:
the generated ide-buffer, ide-ui and ide-keymap-generated sources (accessors of
the key path written out, printable code before the keymap tables, the loop
stores the buffer once at entry).  Every changed input must be the live
binding; every other input, the generated ide-core suite included, is
unchanged.  The measured workloads, the status reference and the scope must be
reproduced exactly except for two measured facts, both FEWER VM ops, which is
what the card is for:

  mini8   (a minibuffer "Find file" round trip through the IDE loop)   -170 ops
  clip160 (the 160-column clipboard workload)                           -48 ops

Heap churn, results and screens are unchanged.  The r7 source pins are checked
in the sealed 2.5.2 world (era_replay_v254_20261003.pin_disk_r7_source_controls);
the O2-lite source pin for the live world is the 2.5.4 pin (the six Comfort
sources do not move in 2.5.5).
"""
import copy

import era_replay_v254_20261003 as R
import o2_lite_consumers_v254_20261003 as V254
import v2_string_codec_workloads_v254_r3_20261003 as R3

V = R3.V
S, P, H = V.S, V.P, V.H
RECEIPT = 'config/v2-string-codec-workloads-v255-r4-20261006-receipt.json'
HISTORY = {**R3.HISTORY,
           'tools/host-lisp/v2_string_codec_workloads_v254_r3_20261003.py':
               S.S.bind('tools/host-lisp/v2_string_codec_workloads_v254_r3_20261003.py')['sha256'],
           R3.RECEIPT: S.S.bind(R3.RECEIPT)['sha256']}
CHANGED = [
    'build/bytecode/dialect-v2/sources/lib/ide-buffer.lisp',
    'build/bytecode/dialect-v2/sources/lib/ide-keymap-generated.lisp',
    'build/bytecode/dialect-v2/sources/lib/ide-ui.lisp',
]
OPS = (-170, -48)       # workload 0, workload 1 of the receipt; every other workload: 0


def compare(old, current):
    S.require([r['path'] for r in old['inputs']] == [r['path'] for r in current['inputs']],
              'codec input population drift')
    changed = [a['path'] for a, b in zip(old['inputs'], current['inputs']) if a != b]
    S.require(changed == CHANGED, 'codec 2.5.5 input drift: ' + ', '.join(changed))
    for row in current['inputs']:
        if row['path'] in changed:
            S.require(row['sha256'] == S.S.bind(row['path'])['sha256'], 'codec current binding drift')
    expected = copy.deepcopy(old)
    expected['inputs'] = current['inputs']
    for row, delta in zip(expected['workloads'], OPS):
        row['ops'] += delta
    H.H.H.compare_receipt(expected, current)
    return changed


def derive():
    S.S.history(HISTORY)
    H.H.H.selftest()
    old = S.json.loads((S.ROOT / R3.RECEIPT).read_bytes())['current']['measurement']
    current = H.H.H.measure()
    changed = compare(old, current)
    trials = []
    trial = copy.deepcopy(current); trial['inputs'].pop(); trials.append(trial)
    trial = copy.deepcopy(current)
    i = next(i for i, r in enumerate(trial['inputs']) if r['path'] not in changed)
    trial['inputs'][i]['sha256'] = '0' * 64; trials.append(trial)
    trial = copy.deepcopy(current)
    i = next(i for i, r in enumerate(trial['inputs']) if r['path'] == CHANGED[1])
    trial['inputs'][i] = old['inputs'][i]; trials.append(trial)
    trial = copy.deepcopy(current); trial['workloads'][0]['ops'] += 1; trials.append(trial)
    trial = copy.deepcopy(current); trial['workloads'][0]['ops'] -= OPS[0]; trials.append(trial)
    trial = copy.deepcopy(current); trial['workloads'][1]['ops'] -= OPS[1]; trials.append(trial)
    trial = copy.deepcopy(current); trial['workloads'][2]['ops'] += 1; trials.append(trial)
    trial = copy.deepcopy(current); trial['status_reference'] = None; trials.append(trial)
    for trial in trials:
        try:
            compare(old, trial)
        except (ValueError, H.H.H.WorkloadError):
            pass
        else:
            raise ValueError('codec mutation survived')
    return dict(measurement=current, changed_inputs=changed, ops_delta=list(OPS),
                workloads_moved=[current['workloads'][i]['id'] for i in range(len(OPS))], mutations_rejected=len(trials))


if __name__ == '__main__':
    V254.route_children()
    V254.install()
    R.pin_disk_r7_source_controls()
    S.finish('v2_string_codec_workloads', derive, RECEIPT, R3,
             (__file__, R3.__file__, V.__file__, P.__file__, H.__file__, R.__file__, V254.__file__))
