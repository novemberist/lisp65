"""2.5.3 r2 string-codec workload successor: re-pin after the lib/lcc.lisp P5
fixpoint fix and the matching allow_omitted_defuns declarations in the bound
einsuite suites.

The v253 derivation runs unchanged: the same nine inputs differ from the r7
receipt, every changed input is the live binding, and the measured workloads
(mini8, clip160, status), the status reference and the scope are reproduced
exactly.  Additionally the measured workloads must equal the v253 receipt's
(asserted); only bound suite bytes moved.  The v253 tool and receipt stay immutable.
"""
import era_replay_v253_20260930 as R
import v2_string_codec_workloads_v253_20261001 as V

S, P, H = V.S, V.P, V.H
RECEIPT = 'config/v2-string-codec-workloads-v253-r2-20261001-receipt.json'
HISTORY = V.HISTORY


def derive():
    value = V.derive()
    old = S.json.loads((S.ROOT / V.RECEIPT).read_bytes())['current']
    S.require(value['changed_inputs'] == old['changed_inputs'] and
              {k: v for k, v in value['measurement'].items() if k != 'inputs'} ==
              {k: v for k, v in old['measurement'].items() if k != 'inputs'},
              'codec measurement moved (r2 is a re-pin only)')
    return value


if __name__ == '__main__':
    R.pin_disk_r7_source_controls()
    S.finish('v2_string_codec_workloads', derive, RECEIPT, V, (__file__, V.__file__, P.__file__, H.__file__, R.__file__))
