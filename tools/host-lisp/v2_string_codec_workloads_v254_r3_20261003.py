"""2.5.4 r3 string-codec workload successor; the v253 r2 receipt stays immutable.

The 2.5.4 cards change seven bound inputs of the codec workload world: the
generated domain-tier1 and stdlib-lists sources (mapcan), ide-buffer, ide-disk,
ide-ui and the rendered ide-keymap-generated source (E3, key seam, save fix A),
and the generated ide-core suite.  Every changed input must be the live
binding.  The measured workloads, the status reference and the scope must be
reproduced exactly except for one measured fact: the mini8 workload (a
minibuffer "Find file" round trip through the IDE loop) runs 9 more VM ops,
the E3 publication check in %ide-drain-pending; heap churn, result and screen
are unchanged.  The r7 source pins are checked in the sealed 2.5.2 world
(era_replay_v254_20261003.pin_disk_r7_source_controls); the O2-lite source pin
for the live world is the 2.5.4 pin.
"""
import copy

import era_replay_v254_20261003 as R
import o2_lite_consumers_v254_20261003 as V254
import v2_string_codec_workloads_v253_r2_20261001 as R2

V = R2.V
S, P, H = V.S, V.P, V.H
RECEIPT = 'config/v2-string-codec-workloads-v254-r3-20261003-receipt.json'
HISTORY = {**R2.HISTORY,
           'tools/host-lisp/v2_string_codec_workloads_v253_r2_20261001.py':
               S.S.bind('tools/host-lisp/v2_string_codec_workloads_v253_r2_20261001.py')['sha256'],
           R2.RECEIPT: S.S.bind(R2.RECEIPT)['sha256']}
CHANGED = [
    'build/bytecode/dialect-v2/sources/lib/domain-tier1.lisp',
    'build/bytecode/dialect-v2/sources/lib/ide-buffer.lisp',
    'build/bytecode/dialect-v2/sources/lib/ide-disk.lisp',
    'build/bytecode/dialect-v2/sources/lib/ide-keymap-generated.lisp',
    'build/bytecode/dialect-v2/sources/lib/ide-ui.lisp',
    'build/bytecode/dialect-v2/sources/lib/stdlib-lists.lisp',
    'build/bytecode/dialect-v2/suites/p0-ide-core-lib.json',
]
OPS = {'mini8': 9}


def compare(old, current):
    S.require([r['path'] for r in old['inputs']] == [r['path'] for r in current['inputs']],
              'codec input population drift')
    changed = [a['path'] for a, b in zip(old['inputs'], current['inputs']) if a != b]
    S.require(changed == CHANGED, 'codec 2.5.4 input drift: ' + ', '.join(changed))
    for row in current['inputs']:
        if row['path'] in changed:
            S.require(row['sha256'] == S.S.bind(row['path'])['sha256'], 'codec current binding drift')
    expected = copy.deepcopy(old)
    expected['inputs'] = current['inputs']
    for row in expected['workloads']:
        row['ops'] += OPS.get(row['id'], 0)
    H.H.H.compare_receipt(expected, current)
    return changed


def derive():
    S.S.history(HISTORY)
    H.H.H.selftest()
    old = S.json.loads((S.ROOT / R2.RECEIPT).read_bytes())['current']['measurement']
    current = H.H.H.measure()
    changed = compare(old, current)
    trials = []
    trial = copy.deepcopy(current); trial['inputs'].pop(); trials.append(trial)
    trial = copy.deepcopy(current)
    i = next(i for i, r in enumerate(trial['inputs']) if r['path'] not in changed)
    trial['inputs'][i]['sha256'] = '0' * 64; trials.append(trial)
    trial = copy.deepcopy(current)
    i = next(i for i, r in enumerate(trial['inputs']) if r['path'] == CHANGED[3])
    trial['inputs'][i] = old['inputs'][i]; trials.append(trial)
    trial = copy.deepcopy(current); trial['workloads'][0]['ops'] += 1; trials.append(trial)
    trial = copy.deepcopy(current); trial['workloads'][0]['ops'] -= OPS['mini8']; trials.append(trial)
    trial = copy.deepcopy(current); trial['status_reference'] = None; trials.append(trial)
    for trial in trials:
        try:
            compare(old, trial)
        except (ValueError, H.H.H.WorkloadError):
            pass
        else:
            raise ValueError('codec mutation survived')
    return dict(measurement=current, changed_inputs=changed, mutations_rejected=len(trials))


if __name__ == '__main__':
    V254.route_children()
    V254.install()
    R.pin_disk_r7_source_controls()
    S.finish('v2_string_codec_workloads', derive, RECEIPT, R2,
             (__file__, R2.__file__, V.__file__, P.__file__, H.__file__, R.__file__, V254.__file__))
