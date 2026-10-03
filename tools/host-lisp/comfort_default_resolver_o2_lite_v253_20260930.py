"""2.5.3 dated resolver successor: the nth domain change moves the compile summary.

lib/domain-tier1.lisp gained %nth-after-domain-check. The target Bank-2
compile of the resolver world therefore reports one more function/object, seven
more code bytes, 71 more ext bytes, 7 more directory bytes, two more literal
nodes/patches and 45 more steps. Every other projected resolver fact must stay
identical to the 2026-09-27 successor and to the 2026-09-28 r2 receipt. The
predecessor tools and receipts stay immutable.
"""
import copy
import re
import sys
from unittest.mock import patch

import comfort_default_resolver_o2_lite_20260929 as P
import comfort_default_resolver_strings_r2_20260928 as R
import o2_lite_consumers_20260929 as S
from strings_generated_r11_20260929 import current_generated
from strings_scratch_20260928 import scratch, normalized

H = R.H
RECEIPT = 'config/comfort-default-resolver-v253-20260930-receipt.json'
HISTORY = {**P.HISTORY,
           'tools/host-lisp/comfort_default_resolver_o2_lite_20260929.py': S.S.bind('tools/host-lisp/comfort_default_resolver_o2_lite_20260929.py')['sha256'],
           P.RECEIPT: S.S.bind(P.RECEIPT)['sha256']}
INPUTS = [row['path'] for row in S.json.loads((S.ROOT / P.RECEIPT).read_bytes())['inputs']]
R0927 = 'tests/bytecode/dialect-v2/evidence/architecture-blocks/library-require-resolver-comfort-default-successor-20260927.json'
R0928 = 'config/c2-require-resolver-receipt-strings-r2-20260928.json'
# Exact change of the three Bank-2 compile report lines, per field.
DELTAS = [dict(functions=1, objects=1, code_bytes=7, dir_bytes=7, steps=45),
          dict(objects=1, code_bytes=7, ext_bytes=71, dir_bytes=7),
          dict(objects=1, literal_nodes=2, literal_patches=2, steps=45)]


def projection(value):
    value = copy.deepcopy(value)
    value.pop('recorded_on')
    value['authority'].pop('gate')
    value['target_bank2_compile'].pop('manifest')
    def strip(x):
        if isinstance(x, dict):
            return {k: strip(a) for k, a in x.items() if k not in ('path', 'content')}
        if isinstance(x, list):
            return [strip(a) for a in x]
        if isinstance(x, str):
            return x.replace('build/post-promotion/require-resolver/l65i-v1', '@scratch/resolver')
        return x
    return strip(value)


def fields(line):
    return {k: int(v) for k, v in re.findall(r'(\w+)=(\d+)(?=\s|$)', line)}


def summary_moved(now, then):
    if len(now) != len(then) or len(now) != len(DELTAS):
        return False
    for a, b, delta in zip(now, then, DELTAS):
        fa, fb = fields(a), fields(b)
        if set(fa) != set(fb) or any(fa[k] != fb[k] + delta.get(k, 0) for k in fa):
            return False
        if re.sub(r'\d+', '#', a) != re.sub(r'\d+', '#', b):
            return False
    return True


def nth_equal(current, reference):
    a, b = projection(current), projection(reference)
    now = a['target_bank2_compile'].pop('summary')
    then = b['target_bank2_compile'].pop('summary')
    return a == b and summary_moved(now, then)


def derive():
    with S.suites():
        with scratch() as root, current_generated(root):
            with patch.object(H, 'SUCCESSOR_RECEIPT', root / 'receipt.json'), \
                 patch.object(H, 'BUILD', root / 'resolver'), \
                 patch.object(H, 'stable_recorded_on', lambda p: '2026-09-28'):
                R.S.require(H.main(record_successor=True) == 0, 'inherited resolver gate failed')
                value = H.load(H.SUCCESSOR_RECEIPT)
            current = normalized(value, root)
            old = H.load(S.ROOT / R0927)
            R.S.require(nth_equal(current, old), 'resolver semantic continuity drift')
            trial = copy.deepcopy(current)
            trial['claim_limit'] = 'unauthorized claim'
            R.S.require(not nth_equal(trial, old), 'resolver continuity mutation survived')
            trial = copy.deepcopy(current)
            trial['target_bank2_compile']['summary'][0] = trial['target_bank2_compile']['summary'][0].replace('steps=', 'steps=1')
            R.S.require(not nth_equal(trial, old), 'resolver summary-delta mutation survived')
    previous = S.json.loads((S.ROOT / R0928).read_bytes())
    R.S.require(nth_equal(current, previous.get('current', previous)),
                'resolver r2 receipt continuity drift')
    return current


if __name__ == '__main__':
    if len(sys.argv) == 1:
        sys.argv.append('check')
    S.finish('comfort_default_resolver', derive, RECEIPT, HISTORY,
             (__file__, P.__file__, *INPUTS, R.__file__))
