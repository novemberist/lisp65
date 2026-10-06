"""Fifth dated successor for IDE source allocation: 2.5.4 E3 re-baseline.

2.5.4 E3 (accepted-edit publication) makes ide-split-line copy the typing
cache instead of consuming it, so an abort can never truncate a published
line.  The wrap key of the allocation workload (Return at the cached column)
therefore pays exactly one line copy (79 cells).  Reviewer decision F1:
accept and re-baseline here, asserting exactly that delta:

  serial/wrap        145 -> 224 cells, worst-phase collections 1 -> 2
  coalesced_10/wrap  122 -> 201 cells, worst-phase collections 1 -> 2
  plain keys (both routes) and the scroll allocations unchanged

The inherited contract must report exactly the six wrap failures above and
nothing else; the re-baselined contract (wrap limits = the measured 224 / 201
cells, wrap collections <= 2; plain limits and plain collections <= 1 as
before) must pass.  Against the r3 measurement (which r4 reproduced) every
other moved fact is asserted exactly: the three bound IDE inputs (ide-buffer,
ide-ui, generated IDE suite), scroll route instructions +4 per row (the
render path gained the publish check), and the host IDE world status line
751/330 -> 754/330 (+3 interned names; the publication and the key-seam
dispatch are written in place, so no private helper name is added) with the
three screen hashes following it.  The r4 tool
and receipt stay immutable.  The O2-lite source pin is the 2.5.4 live pin.
"""
import copy
import hashlib
from pathlib import Path
from unittest.mock import patch

import o2_lite_consumers_v254_20261003 as V254
import c2_v126_editor_allocation_o2_lite_r4_20261001 as R4

R3 = R4.R3
S, R2, G = R3.S, R3.R2, R3.G
A = R2.H.H.H   # c2_v126_editor_allocation_gate
RECEIPT = 'config/c2-v126-editor-allocation-o2-lite-receipt-r5-20261003.json'
HISTORY = {**R4.HISTORY, **{p: hashlib.sha256((S.ROOT / p).read_bytes()).hexdigest() for p in (
    'tools/host-lisp/c2_v126_editor_allocation_o2_lite_r4_20261001.py', R4.RECEIPT)}}
WRAP = {'serial': (145, 224), 'coalesced_10': (122, 201)}
WRAP_ROW = 78
COLLECTIONS = (1, 2)
SCROLL_INSTRUCTIONS = 4
SYMBOLS = (751, 754)
SCREENS = ('serial', 'coalesced_10', 'scroll')
INPUTS = ('editor_buffer', 'editor_ui', 'generated_product_ide_suite')
INHERITED_FAILURES = [f'{route}/wrap: {what}' for route, (_, now) in WRAP.items() for what in (
    f'mean {now:.3f} > 191', f'max {now} > 193', f'worst collections {COLLECTIONS[1]} > {COLLECTIONS[0]}')]


def rebaselined(contract):
    value = copy.deepcopy(contract)
    for route, (_, now) in WRAP.items():
        value['routes'][route]['wrap'].update(maximum_mean_allocations=now, maximum_single_key_allocations=now)
    return value


def evaluate_v254(original):
    def evaluate(contract, routes):
        failures = original(contract, routes)
        S.S.require(failures == INHERITED_FAILURES, 'E3 allocation delta is not exactly the wrap line copy: ' + repr(failures))
        relaxed = rebaselined(contract)
        plain = copy.deepcopy(relaxed)
        for route in WRAP:
            plain['routes'][route].pop('wrap')
        wrap = copy.deepcopy(relaxed)
        wrap['maximum_collections_on_any_single_key_for_any_incoming_phase'] = COLLECTIONS[1]
        for route, classes in list(wrap['routes'].items()):
            wrap['routes'][route] = {k: v for k, v in classes.items() if k == 'wrap'}
            if not wrap['routes'][route]:
                wrap['routes'].pop(route)
        return original(plain, routes) + original(wrap, routes)
    return evaluate


def expected_live(old):
    """The live gate value implied by an old value plus exactly the E3 delta."""
    value = copy.deepcopy(old)
    for route, (before, now) in WRAP.items():
        summary = value['routes'][route]['allocations']['wrap']
        S.S.require(summary == dict(count=1, sum=before, minimum=before, median=before, maximum=before, mean=float(before)),
                    'predecessor wrap summary moved: ' + route)
        summary.update(sum=now, minimum=now, median=now, maximum=now, mean=float(now))
        row = value['routes'][route]['rows'][WRAP_ROW]
        S.S.require(row['class'] == 'wrap' and row['allocations'] == before and
                    row['collections_for_worst_incoming_phase'] == COLLECTIONS[0], 'predecessor wrap row moved: ' + route)
        row.update(allocations=now, collections_for_worst_incoming_phase=COLLECTIONS[1])
    for row in value['routes']['scroll']['rows']:
        row['instructions'] += SCROLL_INSTRUCTIONS
    return value


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
    with patch.object(A, 'evaluate', evaluate_v254(A.evaluate)), \
         patch.object(A, 'build_receipt', build_receipt), patch.object(A, 'verify_successor', verify_successor), \
         patch.object(R3.C, 'DEFAULT_CLOSURE', S.ROOT / R3.CLOSURE), patch.object(R3.C, '_suite_output', suite_output):
        value = R2.derive()
    old = S.json.loads((S.ROOT / R3.RECEIPT).read_bytes())['current']['inherited']
    expected = copy.deepcopy(old)
    current = expected['current']
    current.update(expected_live(current))
    for name in INPUTS:
        now = value['current']['inputs'][name]
        S.S.require(current['inputs'][name] != now, 'bound IDE input did not move: ' + name)
        current['inputs'][name] = now
    for proof in SCREENS:
        row, now = current['screen_semantics'][proof], value['current']['screen_semantics'][proof]
        S.S.require(row['status'].endswith(' -- %d/330' % SYMBOLS[0]), 'r3 symbol budget moved: ' + proof)
        S.S.require(now['status'] == row['status'][:-len('%d/330' % SYMBOLS[0])] + '%d/330' % SYMBOLS[1],
                    'symbol budget is not exactly +%d: %s' % (SYMBOLS[1] - SYMBOLS[0], proof))
        S.S.require(now['screen_sha256'] != row['screen_sha256'], 'screen hash did not follow the status line: ' + proof)
        row['status'], row['screen_sha256'] = now['status'], now['screen_sha256']
    S.S.require(value == expected, 'editor allocation measurement drift beyond the E3 re-baseline')
    return dict(inherited=value, closure=S.S.bind(R3.CLOSURE), symbol_budget=list(SYMBOLS), screens=list(SCREENS),
                rebaseline=dict(wrap_cells={k: list(v) for k, v in WRAP.items()}, wrap_collections=list(COLLECTIONS),
                                inherited_failures=INHERITED_FAILURES, scroll_instructions_per_row=SCROLL_INSTRUCTIONS))


if __name__ == '__main__':
    V254.install()
    S.finish('c2_v126_editor_allocation', derive, RECEIPT, HISTORY,
             (__file__, V254.__file__, R3.CLOSURE, G.__file__, *R2.INPUTS, R2.__file__, R2.H.__file__, R2.P.__file__,
              R2.Q.__file__, R3.__file__, R4.__file__))
