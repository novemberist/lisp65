"""2.5.5 r1 successor helpers: the 2.5.4 r1 helpers with a 2.5.5 receipt header.

The 2.5.4 sealing commit (ERA_V254, the published 2.5.4 journal head) is the
source world that 2.5.4-era bindings are compared with; living files stay live.
"""
import argparse
import json

import c2_v254_r1_common as P

ROOT, require, sha, bind, canonical, history, rel = (
    P.ROOT, P.require, P.sha, P.bind, P.canonical, P.history, P.rel)
ERA_V254 = '45c2e5d2ef3bc91f82301f03562522435cc1c5e5'
CLAIM = 'Host source successor for 2.5.5; no product, emulator or device claim'


def finish(name, derive, receipt, predecessors, inputs, *, record_actions=('record', 'build'), claim=CLAIM):
    """record/build: exclusive creation; check: exact re-derivation; selftest: derive only."""
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=('selftest', 'check') + tuple(record_actions))
    action = p.parse_args().action
    value = dict(format='lisp65-v255-r1-successor-v1', date='2026-10-06', status='PASS',
                 predecessor=history(predecessors), current=derive(),
                 inputs=[bind(rel(n)) for n in sorted(set(map(rel, inputs)))], claim_limit=claim)
    raw = canonical(value)
    path = ROOT / receipt
    if action in record_actions:
        with path.open('xb') as stream:
            stream.write(raw)
    elif action == 'check':
        require(path.read_bytes() == raw, name + ' successor receipt drift')
    print(name + ': ' + action + ' PASS')
    return value


__all__ = ['ROOT', 'ERA_V254', 'require', 'sha', 'bind', 'canonical', 'history', 'rel', 'finish', 'json']
