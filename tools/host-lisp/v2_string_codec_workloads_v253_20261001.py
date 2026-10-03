"""2.5.3 string-codec workload successor; the r7 receipt stays immutable.

Successor of v2_string_codec_workloads_disk_r7_20260930. The 2.5.3 candidate
(nth domain helper, IDE fixes, D3 lossless load, D2/D4 ownership check with the
dated m65d suite r8) changes nine bound inputs of the codec workload world: the
generated domain-tier1, ide-buffer, ide-disk, ide-ui and m65-disk sources, the
generated ide-core, m65d and einsuite workbench suites, and the einsuite core
subset. The measured workloads (mini8, clip160, status), the status reference
and the scope must be reproduced exactly; every changed input must be the live
binding. The r7 source pins are checked in the sealed 2.5.2 source era
(era_replay_v253_20260930), as for the other 2.5.3 successors.
"""
import copy

import era_replay_v253_20260930 as R
import v2_string_codec_workloads_disk_r7_20260930 as P
import disk_r7_consumers_20260930 as S

H = P.H
RECEIPT = 'config/v2-string-codec-workloads-v253-20261001-receipt.json'
HISTORY = {**P.HISTORY, **{
    'tools/host-lisp/v2_string_codec_workloads_disk_r7_20260930.py': S.S.bind('tools/host-lisp/v2_string_codec_workloads_disk_r7_20260930.py')['sha256'],
    P.RECEIPT: S.S.bind(P.RECEIPT)['sha256']}}
CHANGED = [
    'build/bytecode/dialect-v2/sources/lib/domain-tier1.lisp',
    'build/bytecode/dialect-v2/sources/lib/ide-buffer.lisp',
    'build/bytecode/dialect-v2/sources/lib/ide-disk.lisp',
    'build/bytecode/dialect-v2/sources/lib/ide-ui.lisp',
    'build/bytecode/dialect-v2/sources/lib/m65-disk.lisp',
    'build/bytecode/dialect-v2/suites/p0-ide-core-lib.json',
    'build/bytecode/dialect-v2/suites/p0-m65d-lib.json',
    'build/bytecode/dialect-v2/suites/p0-stdlib-einsuite-core-workbench-subset.json',
    'tests/bytecode/stdlib/p0-stdlib-einsuite-core-subset.json',
]


def compare(old, current):
    S.require([r['path'] for r in old['inputs']] == [r['path'] for r in current['inputs']],
              'codec input population drift')
    changed = [a['path'] for a, b in zip(old['inputs'], current['inputs']) if a != b]
    S.require(changed == CHANGED, 'codec 2.5.3 input drift')
    for row in current['inputs']:
        if row['path'] in changed:
            S.require(row['sha256'] == S.S.bind(row['path'])['sha256'], 'codec current binding drift')
    expected = copy.deepcopy(old)
    expected['inputs'] = current['inputs']
    H.H.H.compare_receipt(expected, current)
    return changed


def derive():
    S.S.history(HISTORY)
    H.H.H.selftest()
    old = S.json.loads((S.ROOT / P.RECEIPT).read_bytes())['current']['measurement']
    current = H.H.H.measure()
    changed = compare(old, current)
    trials = []
    trial = copy.deepcopy(current); trial['inputs'].append(dict(path='unexpected', sha256='0' * 64)); trials.append(trial)
    trial = copy.deepcopy(current); trial['inputs'].pop(); trials.append(trial)
    trial = copy.deepcopy(current)
    i = next(i for i, r in enumerate(trial['inputs']) if r['path'] not in changed)
    trial['inputs'][i]['sha256'] = '0' * 64; trials.append(trial)
    trial = copy.deepcopy(current)
    i = next(i for i, r in enumerate(trial['inputs']) if r['path'] == 'build/bytecode/dialect-v2/sources/lib/m65-disk.lisp')
    trial['inputs'][i] = old['inputs'][i]; trials.append(trial)
    trial = copy.deepcopy(current); trial['workloads'][0]['ops'] += 1; trials.append(trial)
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
    R.pin_disk_r7_source_controls()
    S.finish('v2_string_codec_workloads', derive, RECEIPT, P, (__file__, P.__file__, H.__file__, R.__file__))
