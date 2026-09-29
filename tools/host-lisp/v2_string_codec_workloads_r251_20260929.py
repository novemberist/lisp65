"""2.5.1 codec successor: four input changes, identical measured behavior."""
import argparse
import copy
from pathlib import Path
import v2_string_codec_workloads_ide_exit_20260928 as H

S = H.S
RECEIPT = 'config/v2-string-codec-workloads-receipt-r251-r2-20260929.json'
HISTORY = {'tools/host-lisp/v2_string_codec_workloads_ide_exit_20260928.py': '416ed374e282b2c468e63caf65f7309f906f2b06b0b5515c9ac67f71ed4a7bc7', 'config/v2-string-codec-workloads-receipt-ide-exit-20260928.json': '094005d39d2714ec6713df2077ed19e0491ea3272401d7eb2348ca5946659810'}
# The generated tree (build/bytecode/dialect-v2) is freshly re-emitted by
# v2-workbench-codemod before this check; these are the inputs changed by the
# IDE-exit, list-walks and string cards (sealed check-host r3 on bd55b65a).
CHANGED_INPUTS = [
    'build/bytecode/dialect-v2/sources/lib/ide-keymap-generated.lisp',
    'build/bytecode/dialect-v2/sources/lib/ide-ui.lisp',
    'build/bytecode/dialect-v2/sources/lib/sexp-depth.lisp',
    'build/bytecode/dialect-v2/suites/p0-ide-core-lib.json',
    'build/bytecode/dialect-v2/suites/p0-stdlib-einsuite-core-workbench-subset.json',
    'tests/bytecode/stdlib/p0-stdlib-einsuite-core-subset.json',
]


def compare(old, current):
    S.require([r['path'] for r in old['inputs']] ==
              [r['path'] for r in current['inputs']],
              'string-codec input population drift')
    changed = [a['path'] for a, b in zip(old['inputs'], current['inputs']) if a != b]
    S.require(changed == CHANGED_INPUTS, 'unexpected string-codec input drift')
    expected = copy.deepcopy(old)
    expected['inputs'] = current['inputs']
    H.H.compare_receipt(expected, current)
    return changed


def derive():
    S.history(H.HISTORY)
    current = H.H.measure()
    old = H.H.json.loads(H.H.DEFAULT_OUTPUT.read_bytes())
    changed = compare(old, current)
    return dict(measurement=current, changed_inputs=changed,
                inherited_selftest='v2_string_codec_workloads.selftest')


def selftest():
    H.H.selftest()
    current = derive()['measurement']
    old = H.H.json.loads(H.H.DEFAULT_OUTPUT.read_bytes())
    mutations = []
    trial = copy.deepcopy(current)
    trial['inputs'].append(dict(path='unexpected-input', sha256='0' * 64))
    mutations.append(trial)
    trial = copy.deepcopy(current)
    trial['inputs'] = trial['inputs'][:-1]
    mutations.append(trial)
    trial = copy.deepcopy(current)
    unchanged = next(i for i, r in enumerate(old['inputs']) if r['path'] not in CHANGED_INPUTS)
    trial['inputs'][unchanged]['sha256'] = '0' * 64
    mutations.append(trial)
    trial = copy.deepcopy(current)
    changed = next(i for i, r in enumerate(old['inputs']) if r['path'] in CHANGED_INPUTS)
    trial['inputs'][changed] = old['inputs'][changed]
    mutations.append(trial)
    trial = copy.deepcopy(current)
    trial['workloads'][0]['ops'] += 1
    mutations.append(trial)
    for trial in mutations:
        try:
            compare(old, trial)
        except (ValueError, H.H.WorkloadError):
            pass
        else:
            raise ValueError('codec successor mutation survived')


def finish(name, derive, receipt, history, inputs, test=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('selftest', 'build', 'check'))
    action = parser.parse_args().action
    actual = {p: S.bind(p)['sha256'] for p in history}
    S.require(actual == history, 'immutable predecessor drift')
    if action == 'selftest' and test:
        test()
    value = dict(format='lisp65-' + name + '-r251-successor-v1',
                 date='2026-09-29', status='PASS',
                 predecessor=dict(commit='2757ec77', sha256=actual),
                 current=derive(), inputs=[S.bind(p) for p in sorted(set(inputs))],
                 product_links=0, device_contacts=0, xemu_runs=0,
                 claim_limit='Host source proof; no new product or device qualification')
    raw = S.canonical(value)
    path = S.ROOT / receipt
    if action == 'build':
        with path.open('xb') as stream:
            stream.write(raw)
    elif action == 'check':
        S.require(path.read_bytes() == raw, name + ' successor receipt drift')
    print(name + ': ' + action.upper() + ' PASS')


if __name__ == '__main__':
    finish('v2-string-codec-workloads', derive, RECEIPT, HISTORY,
           (__file__, H.__file__, S.__file__, S.KEYMAP), selftest)
