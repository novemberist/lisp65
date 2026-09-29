"""Backspace source seam and exclusive receipts; history stays in its own era."""
import hashlib
import subprocess
from unittest.mock import patch
import ide_exit_successor_20260928 as S
from evidence_era import era_blob

ROOT = S.ROOT
AUTH = 'd9df3cf9'
ERA = '95d9d69e'
SOURCE = 'lib/stdlib-read-line.lisp'
OLD = '(nthcdr next-position (cdr head))'
NEW = '(cdr before)'


def transform(text):
    from v2_workbench_codemod import _top_level_forms
    cuts = [(a, b) for a, b in _top_level_forms(text)
            if text[a:b].startswith('(defun %rl-cut ')]
    S.require(len(cuts) == 1, 'cut definition population drift')
    a, b = cuts[0]
    S.require(text[a:b].count(OLD) == 1, 'backspace seam drift')
    return text[:a] + text[a:b].replace(OLD, NEW) + text[b:]


def source_proof():
    import dirty_anchor_transform as A
    import evidence_era as E
    anchor_tool = 'tools/host-lisp/dirty_anchor_transform.py'
    S.require(era_blob(ERA, anchor_tool) == (ROOT/anchor_tool).read_bytes(), 'dirty-anchor predecessor tool drift')
    with E.host_source_world('9180bb33'):
        A.check_authored(ROOT, 'e2b7189b')
    old = era_blob(ERA, SOURCE).decode()
    S.require(old.encode() == era_blob('9180bb33', SOURCE), 'IDE-exit inherited anchor source drift')
    current = (ROOT / SOURCE).read_text()
    expected = transform(old)
    def validate(text):
        S.require(text == expected, 'Backspace source is not the one-expression successor')
    validate(current)
    S.require(era_blob(AUTH, SOURCE) == current.encode(), 'Backspace authority drift')
    for mutant in (old, expected.replace('next-length 2', 'next-length 3')):
        if mutant == expected:
            mutant = expected + '; foreign change\n'
        try:
            validate(mutant)
        except ValueError:
            pass
        else:
            raise ValueError('source mutation survived')
    return dict(authority=AUTH, predecessor=ERA, source=S.bind(SOURCE),
                anchor=dict(source_commit='9180bb33', predecessor='e2b7189b',
                            transform=S.bind(anchor_tool), seams=4, historical_check='PASS'),
                predecessor_sha256=hashlib.sha256(old.encode()).hexdigest(),
                removed=OLD, replacement=NEW, mutations_rejected=2)


def finish(name, derive, receipt, history, inputs=()):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('selftest', 'build', 'check'))
    action = parser.parse_args().action
    with patch.object(S, 'ERA', ERA):
        predecessor = S.history(history)
    value = dict(format='lisp65-' + name + '-backspace-successor-v1',
                 date='2026-09-28', status='PASS', predecessor=predecessor,
                 current=dict(source=source_proof(), proof=derive()),
                 inputs=[S.bind(p) for p in sorted(set((*inputs, __file__, SOURCE)))],
                 product_links=0, device_contacts=0, xemu_runs=0,
                 claim_limit='Host source proof; no new product or device qualification')
    data = S.canonical(value)
    path = ROOT / receipt
    if action == 'build':
        with path.open('xb') as stream:
            stream.write(data)
    elif action == 'check':
        S.require(path.read_bytes() == data, name + ' successor receipt drift')
    print(name + ': ' + action.upper() + ' PASS')
