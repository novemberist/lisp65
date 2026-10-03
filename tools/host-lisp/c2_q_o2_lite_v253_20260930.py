"""2.5.3 dated C2-Q successor: the nth domain change moves the measurement.

lib/domain-tier1.lisp gained %nth-after-domain-check. Every C2-Q world that
loads the list tier therefore carries one more object, seven more code bytes
and 45 more steps; nothing else may move. Baseline and candidate must move
identically (the +1451 byte Comfort price, the tracked Q cases and the oracle
are unchanged). The 2026-09-29 receipt and predecessor tools stay immutable;
the full new measurement is pinned in its own receipt.
"""
import copy
import re

import c2_q_o2_lite_20260929 as P
import c2_q_strings_r2_20260928 as H
import o2_lite_consumers_20260929 as S

RECEIPT = 'config/c2-q-v253-20260930-receipt.json'
HISTORY = {**P.HISTORY, 'tools/host-lisp/c2_q_o2_lite_20260929.py': S.S.bind('tools/host-lisp/c2_q_o2_lite_20260929.py')['sha256'],
           P.RECEIPT: S.S.bind(P.RECEIPT)['sha256']}
INPUTS = [row['path'] for row in S.json.loads((S.ROOT / P.RECEIPT).read_bytes())['inputs']]
NTH_OBJECTS, NTH_CODE_BYTES, NTH_STEPS = 1, 7, 45


def stripped(value):
    value = copy.deepcopy(value)
    for side in ('baseline', 'candidate'):
        for key in ('code_bytes', 'objects', 'manifest'):
            value['artifacts'][side].pop(key)
    execution = value['artifacts']['execution']
    execution['observations'].pop('sha256')
    execution.pop('source_stdout')
    return value


def numbers(text):
    return [int(n) for n in re.findall(r'\d+', text)]


def nth_continuity(current, expected):
    S.S.require(stripped(current) == stripped(expected),
                'C2-Q measurement moved beyond the nth domain change')
    for side in ('baseline', 'candidate'):
        now, then = current['artifacts'][side], expected['artifacts'][side]
        S.S.require(now['objects'] == then['objects'] + NTH_OBJECTS
                    and now['code_bytes'] == then['code_bytes'] + NTH_CODE_BYTES,
                    'C2-Q ' + side + ' world price is not the nth successor delta')
    now, then = current['artifacts'], expected['artifacts']
    S.S.require(now['candidate']['objects'] - now['baseline']['objects']
                == then['candidate']['objects'] - then['baseline']['objects']
                and now['candidate']['code_bytes'] - now['baseline']['code_bytes']
                == then['candidate']['code_bytes'] - then['baseline']['code_bytes'],
                'C2-Q candidate price over baseline moved')
    new_out, old_out = (x['execution']['source_stdout'] for x in (now, then))
    S.S.require(len(new_out) == len(old_out) == 3, 'C2-Q source report shape drift')
    for a, b in zip(new_out, old_out):
        S.S.require(len(numbers(a)) == len(numbers(b)), 'C2-Q source report field drift')
    steps = [numbers(row)[-1] - numbers(old)[-1] for row, old in ((new_out[0], old_out[0]), (new_out[2], old_out[2]))]
    S.S.require(steps == [NTH_STEPS, NTH_STEPS], 'C2-Q step delta is not the nth successor delta')
    return current


def derive():
    with S.suites():
        current = H.derive()
    old = S.json.loads((S.ROOT / 'config/c2-q-receipt-strings-r2-20260928.json').read_bytes())
    return nth_continuity(current, old.get('current', old))


if __name__ == '__main__':
    S.finish('c2_q', derive, RECEIPT, HISTORY, (__file__, P.__file__, *INPUTS, H.__file__))
