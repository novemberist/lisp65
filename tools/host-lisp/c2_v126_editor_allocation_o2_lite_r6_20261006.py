"""Sixth dated successor for IDE source allocation: 2.5.5 typing card.

2.5.5 makes typing in the IDE editor cheaper (printable code before the keymap
tables, frequent routes first, accessors of the key path written out, the loop
stores the buffer once at entry).  For THIS gate -- allocation of ide-step and
ide-render per key, and the scroll route -- that changes nothing in the
contract numbers:

  serial / coalesced_10, plain and wrap keys: every allocation row unchanged
      (plain 37 cells, wrap 224 / 201 cells, worst-phase collections as in r5)
  scroll allocations unchanged; scroll route VM instructions FEWER per row:
      -24, -24, -24, -245, -24 (measured; the written-out accessors and the
      reordered route table)

So the r5 contract (the E3 re-baseline) is inherited without any change of a
limit; nothing is loosened.  Against the r5 measurement every moved fact is
asserted exactly: the two bound IDE inputs that moved (ide-buffer, ide-ui; the
generated IDE suite did NOT move) and the five scroll instruction counts.  The
per-key cost that the card is about (calls, code-object reads, the per-key
store of the loop) is not measured here; see
c2_v255_editor_key_cost_20261006.py.  The r5 tool and receipt stay immutable.
The O2-lite source pin is the 2.5.4 live pin (the six Comfort sources do not
move in 2.5.5).
"""
import copy
import hashlib
from pathlib import Path
from unittest.mock import patch

import c2_v126_editor_allocation_o2_lite_r5_20261003 as R5

V254, R4, R3 = R5.V254, R5.R4, R5.R3
S, R2, G, A = R5.S, R5.R2, R5.G, R5.A
RECEIPT = 'config/c2-v126-editor-allocation-o2-lite-receipt-r6-20261006.json'
HISTORY = {**R5.HISTORY, **{p: hashlib.sha256((S.ROOT / p).read_bytes()).hexdigest() for p in (
    'tools/host-lisp/c2_v126_editor_allocation_o2_lite_r5_20261003.py', R5.RECEIPT)}}
SCROLL_INSTRUCTIONS = (-24, -24, -24, -245, -24)
MOVED_INPUTS = ('editor_buffer', 'editor_ui')
UNMOVED_INPUTS = ('generated_product_ide_suite',)


def scroll_delta(value):
    rows = value['routes']['scroll']['rows']
    S.S.require(len(rows) == len(SCROLL_INSTRUCTIONS), 'scroll row population moved')
    for row, delta in zip(rows, SCROLL_INSTRUCTIONS):
        row['instructions'] += delta
    return value


def expected_live(old):
    """The live gate value implied by an r3-era value: the r5 (E3) delta, then exactly the 2.5.5 scroll delta."""
    return scroll_delta(R5.expected_live(old))


def derive():
    flag = {}
    build, verify = A.build_receipt, A.verify_successor

    def build_receipt(*args, **kwargs):
        result = build(*args, **kwargs)
        flag['built'] = True
        return result

    def verify_successor(actual, expected):
        if not flag.get('built'):
            return verify(actual, expected)   # inherited selftest mutations stay sharp
        return verify(expected_live(actual), expected)
    original = R3.C._suite_output

    def suite_output(root, source):
        if Path(source).name == G.SUITE:
            return root / 'suites/p0-m65d-lib.json'
        return original(root, source)
    with patch.object(A, 'evaluate', R5.evaluate_v254(A.evaluate)), \
         patch.object(A, 'build_receipt', build_receipt), patch.object(A, 'verify_successor', verify_successor), \
         patch.object(R3.C, 'DEFAULT_CLOSURE', S.ROOT / R3.CLOSURE), patch.object(R3.C, '_suite_output', suite_output):
        value = R2.derive()
    old = S.json.loads((S.ROOT / R5.RECEIPT).read_bytes())['current']['inherited']
    expected = copy.deepcopy(old)
    current = expected['current']
    scroll_delta(current)
    for name in MOVED_INPUTS:
        now = value['current']['inputs'][name]
        S.S.require(current['inputs'][name] != now, 'bound IDE input did not move: ' + name)
        current['inputs'][name] = now
    for name in UNMOVED_INPUTS:
        S.S.require(current['inputs'][name] == value['current']['inputs'][name], 'bound IDE input moved: ' + name)
    S.S.require(value == expected, 'editor allocation measurement drift beyond the 2.5.5 scroll instruction delta')
    for route in ('serial', 'coalesced_10', 'scroll'):
        S.S.require(value['current']['routes'][route]['allocations'] == old['current']['routes'][route]['allocations'],
                    'allocation summary moved: ' + route)
    for index in range(len(SCROLL_INSTRUCTIONS)):          # each scroll row is asserted for itself
        trial = copy.deepcopy(value)
        trial['current']['routes']['scroll']['rows'][index]['instructions'] += 1
        S.S.require(trial != expected, 'scroll mutation survived')
    return dict(inherited=value, closure=S.S.bind(R3.CLOSURE),
                rebaseline=dict(allocations='unchanged against r5 (no contract limit changes)',
                                scroll_instructions_delta_per_row=list(SCROLL_INSTRUCTIONS),
                                moved_inputs=list(MOVED_INPUTS), unmoved_inputs=list(UNMOVED_INPUTS)))


if __name__ == '__main__':
    V254.install()
    S.finish('c2_v126_editor_allocation', derive, RECEIPT, HISTORY,
             (__file__, R5.__file__, V254.__file__, R3.CLOSURE, G.__file__, *R2.INPUTS, R2.__file__, R2.H.__file__, R2.P.__file__,
              R2.Q.__file__, R3.__file__, R4.__file__))
