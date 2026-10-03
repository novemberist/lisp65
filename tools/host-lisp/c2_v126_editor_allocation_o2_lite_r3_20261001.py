"""Third dated successor for 2.5.3 IDE source allocation (D2/D4 disk card).

The inherited allocation chain regenerates its scratch Workbench closure from
the undated config/v2-workbench-artifact-closure.json, whose M65D source suite
(tests/bytecode/libs/p0-m65d-lib.json) predates the dated r7/r8 suites. D2/D4
moves the remount check into %m65d-remount-finish, which may no longer be
private-inlined (rel8 range) and uses Buffer primitives, so that undated suite
cannot compile the 2.5.3 M65D source. This successor runs the unchanged r2
derivation against the dated product closure
config/v2-workbench-artifact-closure-disk-r8-20261001.json (the closure that
v2-workbench-codemod builds) and requires the complete r2 measurement to be
reproduced except for one asserted fact: the host IDE world interns the two
new M65D function names (%m65d-own-chain, %m65d-own-cmp), so the status-line
symbol budget reads 751/330 instead of 749/330 in the three screen proofs
(serial, coalesced_10, scroll) and only their screen hashes move with it. All
allocation, timing-route and remaining screen facts are byte-identical.
"""
import copy
import hashlib
from pathlib import Path
from unittest.mock import patch

import c2_v126_editor_allocation_o2_lite_r2_20260930 as R2
import o2_lite_consumers_20260929 as S
import v2_workbench_codemod as C
import v2_workbench_codemod_disk_r8_20261001 as G

RECEIPT = 'config/c2-v126-editor-allocation-o2-lite-receipt-r3-20261001.json'
CLOSURE = 'config/v2-workbench-artifact-closure-disk-r8-20261001.json'
SYMBOLS = (749, 751)
SCREENS = ('serial', 'coalesced_10', 'scroll')
HISTORY = {**R2.HISTORY, **{p: hashlib.sha256((S.ROOT / p).read_bytes()).hexdigest() for p in (
    'tools/host-lisp/c2_v126_editor_allocation_o2_lite_r2_20260930.py', R2.RECEIPT)}}


def derive():
    original = C._suite_output
    def suite_output(root, source):
        # Same generated interface as v2_workbench_codemod_disk_r8_20261001.
        if Path(source).name == G.SUITE:
            return root / 'suites/p0-m65d-lib.json'
        return original(root, source)
    with patch.object(C, 'DEFAULT_CLOSURE', S.ROOT / CLOSURE), patch.object(C, '_suite_output', suite_output):
        value = R2.derive()
    old = S.json.loads((S.ROOT / R2.RECEIPT).read_bytes())['current']
    expected = copy.deepcopy(old)
    screens = expected['current']['screen_semantics']
    for proof in SCREENS:
        row, now = screens[proof], value['current']['screen_semantics'][proof]
        S.S.require(row['status'].endswith(' -- %d/330' % SYMBOLS[0]), 'r2 symbol budget moved: ' + proof)
        S.S.require(now['status'] == row['status'][:-len('%d/330' % SYMBOLS[0])] + '%d/330' % SYMBOLS[1],
                    'symbol budget is not exactly +2: ' + proof)
        S.S.require(now['screen_sha256'] != row['screen_sha256'], 'screen hash did not follow the status line: ' + proof)
        row['status'], row['screen_sha256'] = now['status'], now['screen_sha256']
    S.S.require(value == expected, 'editor allocation measurement drift beyond the symbol budget')
    return dict(inherited=value, closure=S.S.bind(CLOSURE), symbol_budget=list(SYMBOLS), screens=list(SCREENS))


if __name__ == '__main__':
    S.finish('c2_v126_editor_allocation', derive, RECEIPT, HISTORY,
             (__file__, CLOSURE, G.__file__, *R2.INPUTS, R2.__file__, R2.H.__file__, R2.P.__file__, R2.Q.__file__))
