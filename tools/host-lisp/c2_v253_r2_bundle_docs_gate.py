#!/usr/bin/env python3
"""2.5.3 bundle documentation gate; exact reviewed bytes and semantic negatives.

Successor of c2_v252_r1_bundle_docs_gate (immutable). Documents: README, docs
index, user guide, known issues, language reference, generated keymap, project
status and the 2.5.3 release note, pinned by the v253 contract. 2.5.3 is a
release candidate: the claims below require that the note says "not published"
and keeps every device/Before-Ship statement PENDING. The 2.5.2 note, the
2.5.1 note and development.md are pinned as additional documents; the retained
2.5.2 and 2.5.1 token claims are re-applied to those historical notes.
Import API: check(root, bundle=False), REQUIRED, NOTES.
"""
import argparse
import hashlib
import json
from pathlib import Path

import c2_v253_r2_common as S

ROOT = S.ROOT
CONTRACT = ROOT / 'config/c2-v253-r2-bundle-docs.json'
NOTES = 'docs/releases/2.5.3.md'
NOTES_252 = 'docs/releases/2.5.2.md'
REQUIRED = {NOTES, 'README.md', 'docs/user-guide.md', 'docs/known-issues.md', 'docs/language-reference.md',
            'docs/generated/ide-keymap.md', 'docs/project-status.md', 'docs/README.md'}
HISTORY = {
    'tools/host-lisp/c2_v252_r1_bundle_docs_gate.py':
        'ebf914ca6f2514a20a07c03873638256f5f6355255911d81012fe73a95bfc1a4',
    'config/c2-v252-r1-bundle-docs.json':
        'b937e7b64b78a86dae18e469ec9a88dd7703141355f248c927ae13ddddef102c',
}
TOKENS = ('**Status: release candidate, not published.**',
          'ccc08061b621f43ab4fde7f5a651045d4c87c247',
          '5eb056e03158578bb51edacbb9bd3064ea97a88b8d7613c1d0c052ae6a63d293',
          '7df9db67f16c7218e56c9e4b64dfc0ed512c43771c9c39d9ccd56ddc76e55c2f',
          'bb4a509f99fb539f2e1055bf4d6c7b5ac0b40205d6e96be837fe2f1dcf37d469',
          '36,559 to 36,899 bytes', '**+340 B**', '**+368 B**',
          '2,207 to 212 cells', '2,365 allocation-point root markers',
          'disk allocation inconsistent; disk not written', 'status 13',
          'There is no reclaim in this release.', '287-row cut-point matrix', 'm65d-disk-integrity-check',
          '## Fixed: the prompt returns after out of memory', 'repl-oom-recovery-check', 'lcc-nesting-ladder-check',
          '**Limit: a heap filled by data the program still holds cannot be released from the keyboard.**',
          '**A heap filled by data the program still holds cannot be released from the keyboard.**',
          '**Closures capturing a `let` variable at the Comfort prompt.**',
          '*** VM: OUT OF MEMORY', '*** VM: BAD BYTECODE',
          '*** WRONG ARGUMENT COUNT', '*** COMPILE FAILED%LCC-ERROR-INVALID-PARAMETER-LIST',
          'Comfort 79/79 and Backspace 7/7', '1,750,546,399', '1,146,728 cycles/key', '+1.40 %', 'blank cell',
          '**PENDING**', 'C-x Space', 'not guaranteed limits',
          'Ship and Publish need the owner')
# Whole-text negatives for the release candidate: no placeholder, no premature "published" claim, no Final r7 identity
# (r7 never shipped), no stale out-of-memory known issue.
FORBIDDEN = ('REPLACE_', 'FILL_', 'TODO', 'is published as the', 'Published on 2026-10',
             'Device results for 2.5.3: PASS', 'device session passed',
             'Out of memory can leave the prompt dead', 'planned first in 2.5.4',
             '47519653518f', 'abc9bb49db28', 'c1f5d8cf816485', '**+338 B**')
BOUNDARY = ('# lisp65 2.5.3 — current release boundary', 'releases/2.5.3.md',
            'The 2.5.2 and 2.5.1 text below is historical.', 'Device results for 2.5.3: PENDING',
            '*** COMPILE FAILED%LCC-ERROR-INVALID-PARAMETER-LIST', 'it is not published',
            'The published release is 2.5.2')
STATUS_NOTE_252 = 'Published on 2026-09-30 as the [v2.5.2 GitHub release]'
# Retained 2.5.2 note claims (historical text, pinned as an additional document).
TOKENS_252 = ('[edit previous line]', 'Backspace to reopen the previous line', '1,635,493', '1,130,909',
              '30.85% reduction', '*** VM: BAD BYTECODE', 'C-x q', 'RUN/STOP', '40.9 s')


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
        head = ' '.join(text.split('\n---\n', 1)[0].split())
        for token in BOUNDARY:
            S.require(token in head, '2.5.3 boundary block absent: ' + name + ': ' + token)
        for token in FORBIDDEN:
            S.require(token not in head, 'premature publication/device claim in boundary: ' + name + ': ' + token)
    for name in ('README.md', 'docs/user-guide.md'):
        text = files[name].decode()
        S.require(all(t in text for t in ('starts in Comfort', '(repl)', 'l65>', 'empty line', 'history intact')),
                  'Comfort-default usage absent: ' + name)
    for name in ('README.md', 'docs/README.md', 'docs/project-status.md'):
        text = ' '.join(files[name].decode().split())
        S.require('releases/2.5.3.md' in text and 'release candidate' in text and 'not published' in text.replace(
            'is not yet published', 'not published') and 'not yet Final' not in text,
            '2.5.3 candidate status line absent/stale: ' + name)
        S.require('published baseline is **lisp65 2.5.2**' in text or name != 'README.md', 'published baseline line: ' + name)


def historical(root, bundle=False):
    """The 2.5.2 note keeps its tokens and carries the published-status line; the 2.5.1 gate still holds."""
    name = 'docs/release-notes-2.5.2.md' if bundle else NOTES_252
    path = root / name
    if bundle and not path.exists():
        return
    note = ' '.join(path.read_text().split())
    for token in TOKENS_252:
        S.require(token in note, '2.5.2 historical note token absent: ' + token)
    S.require(STATUS_NOTE_252 in note and 'fde9fb132e32dc71905b0efb98e227678a528695' in note,
              '2.5.2 published-status line absent')
    S.require('Final/device qualification is pending' not in note, '2.5.2 note contradicts its published status')


def validate(files, expected):
    S.require(set(files) == REQUIRED and set(expected) == REQUIRED, 'document population drift')
    for name, raw in files.items():
        S.require(sha(raw) == expected[name], 'document drift: ' + name)
    claims(files)


def contract():
    value = json.loads(CONTRACT.read_bytes())
    S.require(value['release'] == '2.5.3' and value['notes'] == NOTES, 'wrong release')
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
    for token in FORBIDDEN:
        for key in (NOTES, 'docs/known-issues.md'):
            trial = dict(files)
            trial[key] = trial[key].replace(b'\n---\n', ('\n' + token + '\n---\n').encode(), 1) \
                if key != NOTES else trial[key] + ('\n' + token + '\n').encode()
            try:
                claims(trial)
            except ValueError:
                count += 1
            else:
                raise ValueError('obsolete-text control survived: ' + token + ' in ' + key)
    for row in c['bundle_sources']:
        raw = (root / (row['bundle_path'] if bundle else row['path'])).read_bytes()
        S.require(len(raw) == row['bytes'] and sha(raw) == row['sha256'], 'proof document drift: ' + row['path'])
    if not bundle:
        for name, digest in c['additional_documents'].items():
            S.require(sha((root / name).read_bytes()) == digest, 'additional document drift: ' + name)
        historical(root)
        # Inherited 2.5.1-era semantic checks on the retained historical note/text.
        import c2_v251_r2_20260929_bundle_docs_gate as H251
        H251.claims({**{n: (root / n).read_bytes() for n in H251.REQUIRED - {H251.NOTES}},
                     H251.NOTES: (root / H251.NOTES).read_bytes()})
    result = dict(status='PASS', documents=len(REQUIRED), proof_documents=len(c['bundle_sources']),
                  mutations=count)
    print('v253 bundle docs: PASS documents=%d proof-documents=%d mutations=%d'
          % (len(REQUIRED), len(c['bundle_sources']), count))
    return result


def selftest():
    files = {n: b'document' for n in REQUIRED}
    files[NOTES] = ' '.join(TOKENS).encode()
    for n in ('docs/user-guide.md', 'docs/known-issues.md'):
        files[n] = ('\n'.join(BOUNDARY) + '\nstarts in Comfort (repl) l65> empty line history intact\n---\nold\n').encode()
    status = ' releases/2.5.3.md release candidate is not published'
    files['README.md'] = ('starts in Comfort (repl) l65> empty line history intact' + status +
                          ' published baseline is **lisp65 2.5.2**').encode()
    files['docs/README.md'] = status.encode()
    files['docs/project-status.md'] = status.encode()
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
    for token in FORBIDDEN:
        try:
            claims({**files, NOTES: files[NOTES] + (' ' + token).encode()})
        except ValueError:
            rejected += 1
        else:
            raise AssertionError('synthetic forbidden text survived: ' + token)
    return dict(status='PASS', synthetic_mutations=rejected)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--selftest', action='store_true')
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--bundle', action='store_true')
    a = p.parse_args()
    print(json.dumps(selftest() if a.selftest else check(a.root, a.bundle)))
