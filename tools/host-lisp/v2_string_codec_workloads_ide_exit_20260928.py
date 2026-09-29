"""IDE-exit successor: identical codec workloads, three new input hashes."""
import copy
import sys
import v2_string_codec_workloads as H
import ide_exit_successor_20260928 as S


def derive():
    current = H.measure()
    old = H.json.loads(H.DEFAULT_OUTPUT.read_bytes())
    expected = copy.deepcopy(old)
    changed = [before['path'] for before, after in zip(old['inputs'], current['inputs'])
               if before != after]
    S.require(changed == [
        'build/bytecode/dialect-v2/sources/lib/ide-keymap-generated.lisp',
        'build/bytecode/dialect-v2/sources/lib/ide-ui.lisp',
        'build/bytecode/dialect-v2/suites/p0-ide-core-lib.json'],
        'unexpected string-codec input drift')
    expected['inputs'] = current['inputs']
    H.compare_receipt(expected, current)
    return dict(measurement=current, changed_inputs=changed,
                inherited_selftest='v2_string_codec_workloads.selftest')

RECEIPT = 'config/v2-string-codec-workloads-receipt-ide-exit-20260928.json'
HISTORY = {'tools/host-lisp/v2_string_codec_workloads.py': 'e71903c9097e9551f1c62cb7f70798610815f4f2ef24dbed08cadf31735c5433', 'tests/bytecode/dialect-v2/evidence/capability-carrier/string-codec-workload-v240-receipt.json': '479f0d70601ef3972eb9eb08a04cc3d2f9c91d4fee515debf64efb2e3422c36d'}

if __name__ == '__main__':
    if sys.argv[1:] == ['selftest']:
        S.history(HISTORY)
        H.selftest()
    S.finish('v2-string-codec-workloads', derive, RECEIPT, HISTORY,
             (__file__, S.__file__, S.KEYMAP))
