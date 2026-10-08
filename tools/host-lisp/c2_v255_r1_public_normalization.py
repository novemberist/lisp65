#!/usr/bin/env python3
"""Exact, reversible 2.5.5 public comment normalization (2.5.5 Final stdlib-p0.h).

The two identical frozen copies of stdlib-p0.h carry one standalone comment
naming a private checkout path. Export replaces exactly that comment; the
public build proves identical preprocessor tokens. No other byte changes.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / 'config/c2-v255-r1-public-normalization.json'


def policy():
    return json.loads(POLICY.read_text())


def identity(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def old_line(p=None):
    p = policy() if p is None else p
    return '/'.join(p['old_line_parts']).encode()


def normalize(raw, p=None):
    p = policy() if p is None else p
    old, new = old_line(p), p['new_line'].encode()
    if identity(raw) == p['after']:
        return raw
    if identity(raw) != p['before']:
        raise ValueError('normalization source drift')
    if raw.splitlines().count(old) != 1 or not old.startswith(b'/* suite: ') or not old.endswith(b' */'):
        raise ValueError('not the exact standalone comment')
    for line in (old, new):
        if b'\n' in line or b'\\' in line or b'*/' in line[:-2] or b'/*' in line[2:]:
            raise ValueError('unsafe comment substitution')
    result = raw.replace(old, new)
    if identity(result) != p['after']:
        raise ValueError('normalization target drift')
    return result


def denormalize(raw, p=None):
    """Inverse used only by the public build's token-identity proof."""
    p = policy() if p is None else p
    if identity(raw) != p['after']:
        raise ValueError('inverse normalization source drift')
    result = raw.replace(p['new_line'].encode(), old_line(p))
    if identity(result) != p['before']:
        raise ValueError('inverse normalization target drift')
    return result


def accepts(name, raw, expected):
    """Bound row `expected` (pre-export identity) accepts its exported form."""
    p = policy()
    return name in p['paths'] and expected == p['before'] and identity(raw) == p['after']


def selftest():
    p = policy()
    raw = (ROOT / p['paths'][0]).read_bytes()
    if identity(raw) == p['after']:
        raw = denormalize(raw, p)
    out = normalize(raw, p)
    assert denormalize(out, p) == raw and normalize(out, p) == out
    rejected = 0
    for trial in (raw + b' ', raw.replace(b'/* suite: ', b'/* Suite: ', 1)):
        try:
            normalize(trial, p)
        except ValueError:
            rejected += 1
    assert rejected == 2, 'normalization mutation survived'
    return dict(status='PASS', paths=len(p['paths']), mutations_rejected=rejected)


if __name__ == '__main__':
    print(json.dumps(selftest(), indent=2))
