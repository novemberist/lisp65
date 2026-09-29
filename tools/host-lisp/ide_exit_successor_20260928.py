"""Shared exclusive receipt and immutable predecessor checks for IDE exit."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from evidence_era import era_blob

ROOT = Path(__file__).resolve().parents[2]
ERA = 'efcf258f'
KEYMAP_ERA = '9665f97f7a37951364303ea13db91c92bffa9e7a'
KEYMAP = 'config/v11-l-lite-keymap.json'


def canonical(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def bind(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def history(expected):
    actual = {p: bind(p)['sha256'] for p in expected}
    def validate(rows):
        require(rows == expected, 'IDE-exit predecessor drift')
    validate(actual)
    for path in actual:
        require(hashlib.sha256(era_blob(ERA, path)).hexdigest() == expected[path],
                'predecessor escaped sealing era: ' + path)
        trial = dict(actual)
        trial[path] = '0' * 64
        try:
            validate(trial)
        except ValueError:
            pass
        else:
            raise ValueError('predecessor mutation survived: ' + path)
    return dict(commit=ERA, sha256=actual, mutations_rejected=len(actual))


def finish(name, derive, receipt, history_rows, inputs=()):
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('selftest', 'build', 'check'))
    action = parser.parse_args().action
    predecessor = history(history_rows)
    current = derive()
    value = dict(format='lisp65-' + name + '-ide-exit-successor-v1',
                 date='2026-09-28', status='PASS', predecessor=predecessor,
                 current=current, inputs=[bind(p) for p in sorted(set(inputs))],
                 product_links=0, device_contacts=0, xemu_runs=0,
                 claim_limit='Host source proof; no new product or device qualification')
    data = canonical(value)
    path = ROOT / receipt
    if action == 'build':
        with path.open('xb') as stream:
            stream.write(data)
    elif action == 'check':
        require(path.read_bytes() == data, name + ' successor receipt drift')
    print(name + ': ' + action.upper() + ' PASS')
