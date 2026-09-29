"""Live IDE-exit allocation proof with untouched predecessor receipts."""
import copy
import c2_v126_editor_allocation_gate as H
import ide_exit_successor_20260928 as S


def derive():
    H.require(H.main(['selftest']) == 0, 'inherited allocation selftest failed')
    value = H.build_receipt(H.DEFAULT_CONTRACT, H.DEFAULT_SUITE, 4_000_000)
    H.require(value['status'] == 'passed', '; '.join(value['failures']))
    old = H.read_json(H.LIVE_RECEIPT)['current']
    # Only bound inputs and the status line's host symbol count may move.
    expected = copy.deepcopy(old)
    expected['inputs'] = value['inputs']
    for case in ('serial', 'coalesced_10', 'scroll'):
        before = expected['screen_semantics'][case]
        after = value['screen_semantics'][case]
        H.require(before['status'].rsplit(' -- ', 1)[0] ==
                  after['status'].rsplit(' -- ', 1)[0], 'editor status semantics regressed')
        for field in ('status', 'screen_sha256'):
            before[field] = after[field]
    H.verify_successor(expected, value)
    return dict(current=value, permitted_drift='input bindings and host symbol status count only')

RECEIPT = 'config/c2-v126-editor-allocation-receipt-ide-exit-20260928.json'
HISTORY = {'tools/host-lisp/c2_v126_editor_allocation_gate.py': 'bc91bf7f2240d500ac1ada3c7ad8460cc4082e456c3279cb52a12525f267537a', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2-v126-editor-allocation-gate-receipt.json': '72ddbce0b3d5f85ff71021c3d100a765dea3684dc184032848edff82cb86a3b6', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2-v126-editor-allocation-live-successor.json': 'e477992f3103a40b73611844c9e0194847dd06f323bb90a4c3745339cd9088d4'}


if __name__ == '__main__':
    S.finish('c2-v126-editor-allocation', derive, RECEIPT, HISTORY,
             (__file__, S.__file__, 'lib/ide-keymap-generated.lisp'))
