#!/usr/bin/env python3
"""2.5.2 bundle documentation gate; exact reviewed bytes and semantic negatives.

Successor of c2_v252_doc_status_r1_20260929_bundle_docs_gate (immutable).
Documents: README, docs index, user guide, known issues, language reference,
generated keymap, project status and the 2.5.2 release note, pinned by the
v252 contract. The inherited 2.5.1 usage/boundary claims still apply to the
retained historical text; new 2.5.2 claims are checked on the note and on the
2.5.2 boundary blocks. Import API: check(root, bundle=False), REQUIRED, NOTES.
"""
import argparse
import hashlib
import json
from pathlib import Path

import c2_v252_r1_common as S

ROOT = S.ROOT
CONTRACT = ROOT / 'config/c2-v252-r1-bundle-docs.json'
NOTES = 'docs/releases/2.5.2.md'
REQUIRED = {NOTES, 'README.md', 'docs/user-guide.md', 'docs/known-issues.md', 'docs/language-reference.md',
            'docs/generated/ide-keymap.md', 'docs/project-status.md', 'docs/README.md'}
HISTORY = {
    'tools/host-lisp/c2_v252_doc_status_r1_20260929_bundle_docs_gate.py':
        '333db753684bbdaaf2bcf946dbcd7d270181216bce592f071046baa4f41462c3',
    'config/c2-v252-doc-status-r1-20260929-bundle-docs.json':
        'f2aba8c068c96e769971553b198a2b09d87cd2295b4c9dbdbb58daa2d980711d',
}
TOKENS = ('[edit previous line]', 'Backspace to reopen the previous line', 'Up/Down still browse history',
          '32 pending continuation lines', '640 bytes', '250 characters', 'Ten history entries',
          '*** input limit', '*** history limit', '1,635,493', '1,130,909', '30.85% reduction',
          'emulator cycle measurements, not physical keyboard timings', 'erase its link to the next sector',
          'confirmed on a physical MEGA65 with a real disk', '*** VM: BAD BYTECODE', '255 bytes',
          'not included in 2.5.2', 'C-x q', 'RUN/STOP', '40.9 s')
FORBIDDEN = ('REPLACE_', 'FILL_', 'TODO', 'Continuation lines are not editable after Return', 'Final/device qualification is pending')
BOUNDARY = ('# lisp65 2.5.2 — current release boundary', '[edit previous line]', '1,635,493 to 1,130,909',
            'The 2.5.1 text below is historical.', 'releases/2.5.2.md')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def claims(files):
    notes = ' '.join(files[NOTES].decode().split())
    for token in TOKENS:
        S.require(token in notes, 'release boundary absent: ' + token)
    for token in FORBIDDEN:
        S.require(token not in notes, 'obsolete/placeholder release text: ' + token)
    for name in ('docs/user-guide.md', 'docs/known-issues.md'):
        text = files[name].decode()
        head = text.split('\n---\n', 1)[0]
        for token in BOUNDARY:
            S.require(token in head, '2.5.2 boundary block absent: ' + name + ': ' + token)
    for name in ('README.md', 'docs/user-guide.md'):
        text = files[name].decode()
        S.require(all(t in text for t in ('starts in Comfort', '(repl)', 'l65>', 'empty line', 'history intact')),
                  'Comfort-default usage absent: ' + name)
    for name in ('README.md', 'docs/README.md'):
        S.require('releases/2.5.2.md' in files[name].decode() and 'not yet Final' not in files[name].decode(),
                  '2.5.2 status line absent/stale: ' + name)


def validate(files, expected):
    S.require(set(files) == REQUIRED and set(expected) == REQUIRED, 'document population drift')
    for name, raw in files.items():
        S.require(sha(raw) == expected[name], 'document drift: ' + name)
    claims(files)


def contract():
    value = json.loads(CONTRACT.read_bytes())
    S.require(value['release'] == '2.5.2' and value['notes'] == NOTES, 'wrong release')
    S.require(value['predecessors'] == HISTORY, 'contract ancestry drift')
    return value


def check(root, bundle=False):
    S.history(HISTORY)
    c = contract()
    files = {p: (root / ('docs/release-notes.md' if bundle and p == NOTES else p)).read_bytes() for p in REQUIRED}
    validate(files, c['documents'])
    count = 0
    for name in files:
        for trial in ({**files, name: files[name] + b'changed'}, {k: v for k, v in files.items() if k != name}):
            try:
                validate(trial, c['documents'])
            except ValueError:
                count += 1
            else:
                raise ValueError('document mutation survived: ' + name)
    for token in TOKENS + BOUNDARY[:1]:
        trial = dict(files)
        key = NOTES if token in TOKENS else 'docs/user-guide.md'
        trial[key] = ' '.join(trial[key].decode().split()).encode().replace(token.encode(), b'REMOVED') \
            if key == NOTES else trial[key].replace(token.encode(), b'REMOVED')
        try:
            claims(trial)
        except ValueError:
            count += 1
        else:
            raise ValueError('semantic control survived: ' + token)
    for token in FORBIDDEN[3:]:
        trial = dict(files)
        trial[NOTES] += ('\n' + token + '\n').encode()
        try:
            claims(trial)
        except ValueError:
            count += 1
        else:
            raise ValueError('obsolete-text control survived: ' + token)
    for row in c['bundle_sources']:
        raw = (root / (row['bundle_path'] if bundle else row['path'])).read_bytes()
        S.require(len(raw) == row['bytes'] and sha(raw) == row['sha256'], 'proof document drift: ' + row['path'])
    if not bundle:
        for name, digest in c['additional_documents'].items():
            S.require(sha((root / name).read_bytes()) == digest, 'additional document drift: ' + name)
    # Inherited 2.5.1-era semantic checks on the retained historical note/text.
    import c2_v251_r2_20260929_bundle_docs_gate as H251
    if not bundle:
        H251.claims({**{n: (root / n).read_bytes() for n in H251.REQUIRED - {H251.NOTES}},
                     H251.NOTES: (root / H251.NOTES).read_bytes()})
    result = dict(status='PASS', documents=len(REQUIRED), proof_documents=len(c['bundle_sources']),
                  mutations=count)
    print('v252 bundle docs: PASS documents=%d proof-documents=%d mutations=%d'
          % (len(REQUIRED), len(c['bundle_sources']), count))
    return result


def selftest():
    files = {n: b'document' for n in REQUIRED}
    files[NOTES] = ' '.join(TOKENS).encode()
    for n in ('docs/user-guide.md', 'docs/known-issues.md'):
        files[n] = ('\n'.join(BOUNDARY) + '\nstarts in Comfort (repl) l65> empty line history intact\n---\nold\n').encode()
    files['README.md'] = b'starts in Comfort (repl) l65> empty line history intact releases/2.5.2.md'
    files['docs/README.md'] = b'releases/2.5.2.md'
    expected = {n: sha(raw) for n, raw in files.items()}
    validate(files, expected)
    rejected = 0
    for n in REQUIRED:
        for trial in ({**files, n: files[n] + b'bad'}, {k: v for k, v in files.items() if k != n}):
            try:
                validate(trial, expected)
            except ValueError:
                rejected += 1
            else:
                raise AssertionError('synthetic mutation survived')
    for token in TOKENS:
        try:
            claims({**files, NOTES: files[NOTES].replace(token.encode(), b'')})
        except ValueError:
            rejected += 1
        else:
            raise AssertionError('synthetic token survived: ' + token)
    return dict(status='PASS', synthetic_mutations=rejected)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--selftest', action='store_true')
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--bundle', action='store_true')
    a = p.parse_args()
    print(json.dumps(selftest() if a.selftest else check(a.root, a.bundle)))
