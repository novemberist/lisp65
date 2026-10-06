#!/usr/bin/env python3
"""2.5.4 keymap receipt: the key extension seam moves exactly three generated outputs.

Immutable predecessors: the 2.5.3 keymap-receipt successor, its receipt, the
2.5.3 keymap entry point and the 2.5.4 entry point's own ancestry.  The
inherited derivation cannot be re-run live: its generator check renders with
the pre-seam renderer.  Instead this successor

  * runs the 2.5.4 entry point (c2_v254_r1_keymap) selftest and check, i.e.
    the inherited generator selftest/check with the two render seams applied;
  * re-binds the exact file population of the 2.5.3 receipt and requires that
    exactly lib/ide-keymap-generated.lisp and the two generated keymap case
    files moved, every other file (contract, renderer, docs, read-line,
    extra/hardware cases) byte-identical;
  * requires the 2.5.3 receipt rows of the moved files to be the bytes the
    2.5.3 sealing commit carried (era binding).
"""
import copy

import evidence_era as E
import c2_v253_r1_keymap_receipt as H
import c2_v254_r1_common as S
import c2_v254_r1_keymap as K

HISTORY = {'tools/host-lisp/c2_v253_r1_keymap_receipt.py':
               'f469c9e360e0837a7e50bf919f91e113f2888040ea1da08c438a178639fd60f0',
           'config/c2-v253-r1-keymap-receipt.json':
               '99d9dd3124a2cf29ad9b8edcdb30139684e7a9e39d1b636642d9d5f9365b4108',
           'tools/host-lisp/c2_v253_r1_keymap.py':
               '6d2c10b4af0b8952a659af08edf937efaed6d0bde2a68570da6ee0a2d6bfa9b0'}
RECEIPT = 'config/c2-v254-r1-keymap-receipt.json'
MOVED = ['lib/ide-keymap-generated.lisp',
         'lib/tests/ide-keymap-eval-cases.generated.json',
         'tests/bytecode/libs/p0-ide-keymap-cases.generated.json']


def derive():
    S.history(K.HISTORY)
    S.history(HISTORY)
    for action in ('selftest', 'check'):
        S.require(K.run([action]) in (0, None), '2.5.4 keymap entry point ' + action + ' failed')
    old = S.json.loads((S.ROOT / H.RECEIPT).read_bytes())['current']
    rows = old['inherited']['inherited']['files']
    live = [S.bind(row['path']) for row in rows]
    changed = [a['path'] for a, b in zip(rows, live, strict=True) if a != b]
    S.require(changed == MOVED, 'keymap input population drift: ' + ', '.join(changed))
    for row in rows:
        if row['path'] in MOVED:
            S.require(row == E.era_bind(S.ERA_V253, row['path']), '2.5.3 receipt row is not the sealed era: ' + row['path'])
    expected = copy.deepcopy(rows)
    for row in expected:
        if row['path'] in MOVED:
            row.update(S.bind(row['path']))
    S.require(live == expected, 'keymap exact binding drift')
    return dict(files=live, moved=MOVED, predecessor_rows=[r for r in rows if r['path'] in MOVED],
                entry_point=S.bind('tools/host-lisp/c2_v254_r1_keymap.py'))


if __name__ == '__main__':
    S.finish('keymap-receipt-v254', derive, RECEIPT, HISTORY, (__file__, S.__file__, K.__file__, H.__file__))
