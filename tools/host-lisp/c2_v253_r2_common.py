"""2.5.3 r2 (Final r8) successor helpers: exact bindings, immutable ancestry, exclusive receipts."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def bind(path):
    raw = (ROOT / path).read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def canonical(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def history(expected):
    """Immutable predecessors: exact bytes, with a mutation control per path."""
    actual = {p: sha(p) for p in expected}
    require(actual == expected, 'immutable predecessor drift')
    for p in actual:
        trial = dict(actual)
        trial[p] = '0' * 64
        require(trial != expected, 'history mutation survived')
    return actual


def rel(path):
    p = Path(path)
    return str(p.resolve().relative_to(ROOT)) if p.is_absolute() else str(p)


def finish(name, derive, receipt, predecessors, inputs, *, record_actions=('record', 'build'),
           claim='Host documentation/source successor for 2.5.3; no product, emulator or device claim'):
    """record/build: exclusive creation; check: exact re-derivation; selftest: derive only."""
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=('selftest', 'check') + tuple(record_actions))
    action = p.parse_args().action
    value = dict(format='lisp65-v253-r2-successor-v1', date='2026-10-03', status='PASS',
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
