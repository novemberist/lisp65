#!/usr/bin/env python3
"""2.5.5 keymap receipt: the typing levers move exactly one generated output.

Immutable predecessors: the 2.5.4 keymap-receipt successor, its receipt and
the 2.5.4 keymap entry point.  The inherited derivation cannot be re-run live:
its generator check renders with the 2.5.4 renderer.  Instead this successor

  * runs the 2.5.5 entry point (c2_v255_r1_keymap) selftest and check, i.e.
    the inherited generator selftest/check with the 2.5.5 render seams applied
    (printable code before the base table, the frequent routes first);
  * re-binds the exact file population of the 2.5.4 receipt and requires that
    exactly lib/ide-keymap-generated.lisp moved; every other file (contract,
    renderers, docs, read-line, all generated case files) is byte-identical:
    no key binding, no test case and no document changes;
  * requires the 2.5.4 receipt row of the moved file to be the bytes the
    2.5.4 sealing commit carried (era binding).
"""
import copy

import evidence_era as E
import c2_v254_r1_keymap_receipt as H
import c2_v255_r1_common as S
import c2_v255_r1_keymap as K

HISTORY = {'tools/host-lisp/c2_v254_r1_keymap_receipt.py':
               '31ef6ddbc6d6b3eb22921348347e1f1999bdfb384a4681e25a2eec63f0b05fb3',
           'config/c2-v254-r1-keymap-receipt.json':
               '4566c6f49ede584d4e869768e0aefc1e540e398083264fcdc7245c4828533a7f',
           'tools/host-lisp/c2_v254_r1_keymap.py':
               '15f3cd2760339256b5779091e6a7c3cec9a94cb1047c1322033d62ca51af39cc'}
RECEIPT = 'config/c2-v255-r1-keymap-receipt.json'
MOVED = ['lib/ide-keymap-generated.lisp']


def derive():
    S.history(K.HISTORY)
    S.history(HISTORY)
    for action in ('selftest', 'check'):
        S.require(K.run([action]) in (0, None), '2.5.5 keymap entry point ' + action + ' failed')
    rows = S.json.loads((S.ROOT / H.RECEIPT).read_bytes())['current']['files']
    live = [S.bind(row['path']) for row in rows]
    changed = [a['path'] for a, b in zip(rows, live, strict=True) if a != b]
    S.require(changed == MOVED, 'keymap input population drift: ' + ', '.join(changed))
    for row in rows:
        if row['path'] in MOVED:
            S.require(row == E.era_bind(S.ERA_V254, row['path']), '2.5.4 receipt row is not the sealed era: ' + row['path'])
    expected = copy.deepcopy(rows)
    for row in expected:
        if row['path'] in MOVED:
            row.update(S.bind(row['path']))
    S.require(live == expected, 'keymap exact binding drift')
    return dict(files=live, moved=MOVED, predecessor_rows=[r for r in rows if r['path'] in MOVED],
                entry_point=S.bind('tools/host-lisp/c2_v255_r1_keymap.py'))


if __name__ == '__main__':
    S.finish('keymap-receipt-v255', derive, RECEIPT, HISTORY, (__file__, S.__file__, K.__file__, H.__file__))
