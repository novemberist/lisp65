#!/usr/bin/env python3
"""2.5.4 ship-time bundle documentation gate (r2); exact reviewed bytes and semantic negatives.

Successor of c2_v254_r1_bundle_docs_gate (immutable; the candidate-time gate, which required every device
statement to be PENDING and forbade hardware-result wording).  The device session passed on 2026-10-05 as a
manual owner session (docs/planning/release-2.5.4-device-report.md).  Ship-time wording, as r3 was for 2.5.3: the
documents say the device session PASSED and cite the device report; they state what was NOT done on the device
(large saves, out-of-memory rows, the $D703 check) and the three findings (type-ahead lost while the editor
opens, IDE typing slower than the REPL, slow remount); they state the host change (Final linked on Fedora 44,
reproductions on Fedora 45, byte-identical; merged bitcode host-dependent); they say "release candidate, not
published" and keep the Before-Ship record and the publication PENDING.  No document may claim publication, and
an open result marker may not remain.  The GC-stress session is stated as FAIL by the committed rules together
with the owner's acceptance of its memory cost (2026-10-06); no wording may turn it into a pass.
Documents: README, docs index, user guide, known issues, language reference, generated keymap, project status
and the 2.5.4 release note, pinned by the r2 contract.  The 2.5.3, 2.5.2 and 2.5.1 notes and development.md are
pinned as additional documents.  Import API: check(root, bundle=False), REQUIRED, NOTES.
"""
import argparse
import hashlib
import json
from pathlib import Path

import c2_v254_r1_common as S

ROOT = S.ROOT
CONTRACT = ROOT / 'config/c2-v254-r2-bundle-docs.json'
NOTES = 'docs/releases/2.5.4.md'
NOTES_253 = 'docs/releases/2.5.3.md'
REQUIRED = {NOTES, 'README.md', 'docs/user-guide.md', 'docs/known-issues.md', 'docs/language-reference.md',
            'docs/generated/ide-keymap.md', 'docs/project-status.md', 'docs/README.md'}
HISTORY = {
    'tools/host-lisp/c2_v254_r1_bundle_docs_gate.py':
        'f221e8e7da3b1bd9d3ab15b4fff91a85132ffaa497eb98381aa4f22a3b7337b3',
    'config/c2-v254-r1-bundle-docs.json':
        '3ffdf4a2748ef11e7c4de58c338df1bdfbc26a7556107bd03d1b0db71018a5c5',
}
TOKENS = ('**Status: release candidate, not published.**',
          '04294d56',
          '7b951eb9c92bc8797278903465b7483b3168a0eb935237a8f62ea3757f205244',
          '250fdc763ae9e5b04cf149a6f2a7a3aa9fb293ff8da58e9a703e0c601efaef5d',
          '7b70c025ef66de595e1d2c050e6d65d54ed9d34243c807c8faf4618fda8e5603',
          'build/card-254-final-r1', 'byte-identical to the Seed',
          '36,899 B, unchanged against 2.5.3',
          '## Changed: edit persistence in the IDE (E3)',
          '**Only the IDE path is protected.**',
          'A direct `m65d-save` call is **not** protected by the edit-persistence mechanism',
          '381,706 points and 52,091 multi-buffer points, 0 violations',
          'aborts inside native primitives, during garbage collection or at out-of-memory',
          '**The RUN/STOP stand-in is a monitor write to the break flag and is accepted for the emulator only**',
          'pressed the physical RUN/STOP key and re-entered the editor',
          'a stop in the middle of a key burst cannot be produced by hand',
          '`(ide-bind-key KEY FUNCTION)`', '**built-in keys cannot be overridden**', '`unknown command`',
          'save refused while a file loads',
          '*** result too deep, too large or circular', 'stay unbounded',
          '*** VM: BAD BYTECODE', '*** COMPILE FAILED%LCC-ERROR-INVALID-PARAMETER-LIST',
          '**No product failure.**', '**Three rows are not green, unchanged from 2.5.3.**',
          '`ide-buffer-switch-two-keys`', '`ide-save-100x20-keys`', '`oom-repl-global`',
          'Whether the emulator\'s DMA honours the bit is not shown',
          'Comfort 79 of 79', 'Backspace 7 of 7', '1,146,714 cycles/key',
          '253 B stored length against the 255 B limit',
          'one narrowly pinned reviewed class',
          '## Device session on a physical MEGA65', '**Passed on 2026-10-05**', 'release-2.5.4-device-report.md',
          'manual owner session', 'no tool-clock boot time and there are no automated device rows',
          '20 s to `Initializing`, then 22 s to `L65>`', '**5 s by the owner\'s stopwatch**', '37.7 s',
          '**Type-ahead while the editor opens is lost.**',
          '**Typing in the IDE editor is clearly slower than at the REPL.**',
          '**`(m65d-remount)` takes very long on the device**',
          'Not done on the device: the additional REPL rows, large saves (50x40, 100x20), the out-of-memory rows and the `$D703` check',
          '122.3 against 124.2 ms', '148.0 against 150.0 ms', '4.17 ms in both versions',
          'about 30 times slower per key than the REPL in both versions',
          'released the three findings as known limits for 2.5.4 on 2026-10-05',
          '## Garbage-collection stress session on the Final', '**By the committed rules the status of the gate is FAIL**',
          '**stall on a display defect that is identical in the 2.5.3 records**',
          'a constant +3 live cells and +88 arena bytes at every collection**', '43 of 1,070 cells (2.5.3: 46)',
          '**The owner accepted this memory cost on 2026-10-06 and approved publication of 2.5.4 with the gate recorded as it is (formally FAIL).**',
          'The gate is not reworded into a pass.',
          'the Final was linked with the Fedora 44 host tools', 'both reproductions ran with the Fedora 45 host tools',
          'host-dependent intermediate', 'byte-identical to the Final in both',
          'The Before-Ship record and publication are **PENDING**',
          'Ship and Publish are pre-approved by the owner for 2.5.4; neither has been done.')
# Whole-text negatives at ship time: no placeholder, draft or open-result marker, no premature "published" claim,
# no stale pending-device statement (the session passed).
FORBIDDEN = ('REPLACE_', 'FILL_', 'TODO', 'DRAFT', 'TO BE FILLED IN', 'is published as the', 'Published on 2026-10',
             'Device results for 2.5.4: PENDING', 'the device session has not happened', 'device session is pending',
             'Physical RUN/STOP row: **PENDING**', 'device measurement **PENDING**', 'Physical MEGA65 session by the owner: **PENDING**',
             'No hardware result is claimed', 'reproductions: **PENDING**',
             'gc-session: PASS', 'GC-stress session passed', 'This cost is put to the owner')
BOUNDARY = ('# lisp65 2.5.4 — current release boundary', 'releases/2.5.4.md',
            'The 2.5.3, 2.5.2 and 2.5.1 text below is historical.',
            'Device results for 2.5.4: PASSED on a physical MEGA65 on 2026-10-05',
            'planning/release-2.5.4-device-report.md', 'type-ahead typed while the IDE editor opens is lost',
            '`$D703` check were not done on the device',
            'direct `m65d-save` call is not protected', 'it is not published',
            'The published release is 2.5.3')
STATUS_NOTE_253 = 'Published on 2026-10-03 as the [v2.5.3 GitHub release]'
PUBLIC_MAIN_253 = 'bf9d7c0c4eaeccdd5a4b0265b9e3f3e3b000d387'
# Retained 2.5.3 note claims (historical text, pinned as an additional document).
TOKENS_253 = ('5eb056e03158578bb51edacbb9bd3064ea97a88b8d7613c1d0c052ae6a63d293',
              '7df9db67f16c7218e56c9e4b64dfc0ed512c43771c9c39d9ccd56ddc76e55c2f',
              '## Fixed: the prompt returns after out of memory', 'disk allocation inconsistent; disk not written',
              'There is no reclaim in this release.', '*** VM: OUT OF MEMORY', '*** VM: BAD BYTECODE',
              '## Device session on a physical MEGA65', 'release-2.5.3-device-report.md', 'passed on 2026-10-03',
              'took several minutes', 'C-x Space')


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
            S.require(token in head, '2.5.4 boundary block absent: ' + name + ': ' + token)
        for token in FORBIDDEN:
            S.require(token not in head, 'premature publication/device claim in boundary: ' + name + ': ' + token)
    for name in ('README.md', 'docs/user-guide.md'):
        text = files[name].decode()
        S.require(all(t in text for t in ('starts in Comfort', '(repl)', 'l65>', 'empty line', 'history intact')),
                  'Comfort-default usage absent: ' + name)
    for name in ('README.md', 'docs/README.md', 'docs/project-status.md'):
        text = ' '.join(files[name].decode().split())
        S.require('releases/2.5.4.md' in text and 'release-2.5.4-device-report.md' in text
                  and 'release candidate' in text and 'device session passed' in text
                  and 'not published' in text.replace('is not yet published', 'not published').replace(
                      '**not published**', 'not published')
                  and 'not yet Final' not in text and 'TO BE FILLED IN' not in text,
            '2.5.4 candidate status line absent/stale: ' + name)
        S.require('published baseline is **lisp65 2.5.3**' in text or name != 'README.md', 'published baseline line: ' + name)


def historical(root, bundle=False):
    """The 2.5.3 note keeps its tokens and carries the published-status line; the 2.5.2/2.5.1 gates still hold."""
    name = 'docs/release-notes-2.5.3.md' if bundle else NOTES_253
    path = root / name
    if bundle and not path.exists():
        return
    note = ' '.join(path.read_text().split())
    for token in TOKENS_253:
        S.require(token in note, '2.5.3 historical note token absent: ' + token)
    S.require(STATUS_NOTE_253 in note and PUBLIC_MAIN_253 in note, '2.5.3 published-status line absent')
    S.require(note.startswith('> ' + STATUS_NOTE_253), '2.5.3 published-status line is not the first line')


def validate(files, expected):
    S.require(set(files) == REQUIRED and set(expected) == REQUIRED, 'document population drift')
    for name, raw in files.items():
        S.require(sha(raw) == expected[name], 'document drift: ' + name)
    claims(files)


def contract():
    value = json.loads(CONTRACT.read_bytes())
    S.require(value['release'] == '2.5.4' and value['notes'] == NOTES, 'wrong release')
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
        # Inherited 2.5.2-note and 2.5.1-era semantic checks on the retained historical notes/text.
        import c2_v253_r3_bundle_docs_gate as H253
        H253.historical(root)
        import c2_v251_r2_20260929_bundle_docs_gate as H251
        H251.claims({**{n: (root / n).read_bytes() for n in H251.REQUIRED - {H251.NOTES}},
                     H251.NOTES: (root / H251.NOTES).read_bytes()})
    result = dict(status='PASS', documents=len(REQUIRED), proof_documents=len(c['bundle_sources']),
                  mutations=count)
    print('v254 r2 bundle docs: PASS documents=%d proof-documents=%d mutations=%d'
          % (len(REQUIRED), len(c['bundle_sources']), count))
    return result


def selftest():
    files = {n: b'document' for n in REQUIRED}
    files[NOTES] = ' '.join(TOKENS).encode()
    for n in ('docs/user-guide.md', 'docs/known-issues.md'):
        files[n] = ('\n'.join(BOUNDARY) + '\nstarts in Comfort (repl) l65> empty line history intact\n---\nold\n').encode()
    status = (' releases/2.5.4.md planning/release-2.5.4-device-report.md release candidate device session passed'
              ' is not published')
    files['README.md'] = ('starts in Comfort (repl) l65> empty line history intact' + status +
                          ' published baseline is **lisp65 2.5.3**').encode()
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
