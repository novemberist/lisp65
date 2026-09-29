#!/usr/bin/env python3
"""Exact, reversible public comment normalization; frozen authority stays intact."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def policy():return json.loads((ROOT/'config/c2-v251-r2-20260929-public-normalization.json').read_text())
def identity(raw):return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def normalize(raw):
    p=policy();old='/'.join(p['old_line_parts']).encode();new=p['new_line'].encode()
    if identity(raw)==p['after']:return raw
    if identity(raw)!=p['before']:raise ValueError('normalization source drift')
    if raw.splitlines().count(old)!=1 or not old.startswith(b'/* suite: ') or not old.endswith(b' */'):
        raise ValueError('not the exact standalone comment')
    for line in (old,new):
        if b'\n' in line or b'\\' in line or b'*/' in line[:-2] or b'/*' in line[2:]:raise ValueError('unsafe comment substitution')
    result=raw.replace(old,new)
    if identity(result)!=p['after']:raise ValueError('normalization target drift')
    return result
def accepts(name,raw,expected):
    p=policy()
    rows=[p]+json.loads((ROOT/'config/c2-v251-r2-20260929-public-json-normalization.json').read_text())['rows']
    return any(name in r.get('paths',[r['path']]) and expected==r['before'] and identity(raw)==r['after'] for r in rows)
