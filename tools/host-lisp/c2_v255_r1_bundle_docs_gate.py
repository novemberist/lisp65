#!/usr/bin/env python3
"""2.5.5 candidate-time bundle documentation gate (r1); exact reviewed bytes and semantic negatives.

Successor of c2_v254_r2_bundle_docs_gate (immutable; the 2.5.4 ship-time gate). Modelled on the 2.5.4
candidate-time gate (c2_v254_r1_bundle_docs_gate): 2.5.5 is a release candidate whose Final is sealed and whose
device session has NOT happened. The claims below require that the note says "not published", keeps every
device and Before-Ship statement PENDING and states no hardware result; that every typing figure is named an
emulator measurement; that the measured table (2.5.4 against 2.5.5) and what stays slow are present; that the
garbage-collection stress gate is stated as FAIL by the committed rules, with the one-off `pending32` timeout as
an observation (a driver and emulator coincidence, once, not reproduced in seven runs, mechanism inferred), and is
not reworded into a pass; that the Seed halt and its continuation, the residue zeroing
and the correction of the published 2.5.4 REPL comparison (about 10 times, not 30 times) are stated. A ship-time
successor replaces this gate after the device session, as r2 replaced r1 in 2.5.4.
Documents: README, docs index, user guide, known issues, language reference, generated keymap, project status
and the 2.5.5 release note, pinned by the v255 r1 contract. The 2.5.4, 2.5.3, 2.5.2 and 2.5.1 notes and
development.md are pinned as additional documents; the 2.5.4 note carries its published-status line with the
dated correction and keeps its retained tokens (its published text is not edited); the retained 2.5.3, 2.5.2 and
2.5.1 claims are re-applied through the 2.5.4, 2.5.3 and 2.5.1 gates.
Import API: check(root, bundle=False), REQUIRED, NOTES.
"""
import argparse
import hashlib
import json
from pathlib import Path

import c2_v255_r1_common as S

ROOT = S.ROOT
CONTRACT = ROOT / 'config/c2-v255-r1-bundle-docs.json'
NOTES = 'docs/releases/2.5.5.md'
NOTES_254 = 'docs/releases/2.5.4.md'
REQUIRED = {NOTES, 'README.md', 'docs/user-guide.md', 'docs/known-issues.md', 'docs/language-reference.md',
            'docs/generated/ide-keymap.md', 'docs/project-status.md', 'docs/README.md'}
HISTORY = {
    'tools/host-lisp/c2_v254_r2_bundle_docs_gate.py':
        '8fec1a4241075f0b0b2b4cedac0204f6eeb9479415d8e11a5f116efe7e2c1c79',
    'config/c2-v254-r2-bundle-docs.json':
        'd72a80c3730572ae48ebfc4aa2847c2ad63621516c6aa88bca639a713316eaf7',
}
TOKENS = ('**Status: release candidate, not published.**',
          'f6333f4a',
          '592b2c71c30901d2bb9599d2324678be5cd910865fbbfaf888c5d28ecb2e701f',
          '4f0b76ad395ed861da104960859b8d9416750a00684dd4826a1193b14245523b',
          '2776060ce564c6a16254a2736fb0cac8dec27f35e0d87b6188e3b622034abcb4',
          'build/card-255-final-r1', 'byte-identical to the Seed',
          '36,899 B, unchanged against 2.5.4',
          '**The Seed halted after its link and was continued without a second link.**',
          'one narrowly pinned reviewed class', 'the code generator\'s reason is not known',
          'Only the `ide` image changes against 2.5.4', '15,223 → 15,081 B (−142 B)',
          'the same Fedora 45 host and one set of pinned host tools',
          '## Changed: typing in the IDE editor',
          '1,955 VM instructions, 359 code-object reads and 95 heap cells in 2.5.4; 921, 145 and 39 in 2.5.5',
          'Per-key cells fall from 95 to 39', '`c2-v255-editor-key-cost-check`',
          '74,442 points', '127,914 points', '0 violations',
          'The proof tool of 2.5.4 was blind in the `run` shape',
          'aborts inside native primitives, during garbage collection or at out-of-memory are not covered by it',
          'A direct `m65d-save` call is still not protected',
          '## Measured typing cost (emulator)', '**This is an emulator measurement, not a device timing.**',
          '| Insert, column 1 | 124.2 ms | 57.3 ms | 0.461 |', '| Insert, column 20 | 137.1 ms | 57.3 ms | 0.418 |',
          '| Insert, column 39 | 150.0 ms | 57.3 ms | 0.382 |', '| Insert, line 20 | 153.5 ms | 57.1 ms | 0.372 |',
          '| Backspace, column 20 | 119.7 ms | 60.4 ms | 0.505 |',
          '| Return, 30 characters | 462.9 ms | 416.3 ms | 0.899 |', '| Burst of 8 keys | 687 ms | 244 ms | 0.355 |',
          '| REPL, key to visible glyph | 14.0 ms | 14.0 ms | 1.000 |',
          '5 garbage collections instead of 9', '67 ms per key instead of 152 ms',
          '**A garbage collection still costs about 120 ms**', 'about twice the cost of a key',
          '**The first key after entering the editor costs about 90 ms more**',
          '**Return is hardly faster:** 416 ms',
          '**Type-ahead typed while the editor is still opening is lost**',
          '**`(m65d-remount)` takes very long**',
          'draws it over the rows above',
          '**The `$D703` (DMA format) check has not been done on hardware.**',
          '## Correction of a published 2.5.4 statement',
          '**the REPL glyph is visible 14.0 ms after the key is consumed**',
          '**about 10 times slower than the REPL, not 30 times**',
          'The text of the published v2.5.4 GitHub release is not edited',
          '## Residue zeroing on the medium', '729 bytes of the 2.5.4 medium', '`residue-zeroing.json`',
          'needs no byte of the 2.5.4 medium', '`AUTOBOOT.C65` is six bytes shorter than in 2.5.4',
          '**No product failure.**', 'The 14 new behaviour rows for lever L2', '**Every 2.5.4 row keeps its status.**',
          '**Three rows are not green, unchanged from 2.5.4 and 2.5.3:**',
          '`ide-buffer-switch-two-keys`', '`ide-save-100x20-keys`', '`oom-repl-global`',
          'Comfort 79 of 79', 'Backspace 7 of 7',
          'accepted for the emulator only', 'whether the emulator\'s DMA honours the bit is not shown',
          '## Garbage-collection stress session', '**By the committed rules the status of the gate is FAIL**',
          'The gate is not reworded into a pass.', 'There is no regression against 2.5.4.',
          'ended in a breakpoint timeout at collection 471',
          '**Observation, a coincidence of driver and emulator, not a product stall:**',
          '**It happened once and was not reproduced in seven runs:**',
          'The mechanism is inferred from those records; it was not provoked deliberately',
          '**No scenario covers the IDE editor under forced collection**',
          '43 of 1,070 cells',
          '## Device session on a physical MEGA65', 'No hardware result is claimed in this note.',
          'Two clean public-source reproductions: **PENDING**',
          'Physical MEGA65 session by the owner: **PENDING**',
          'The owner\'s word for Ship and Publish of 2.5.5: **PENDING**; neither has been done.',
          '## Next cards', 'A dedicated self-insert path', 'The repaint after Return',
          'A native code-object cache, after the kernel diet', 'A standing two-state class for the instruction pair')
# Whole-text negatives for the release candidate: no placeholder or draft marker, no premature "published" claim,
# no hardware result (the device session has not happened), no pass wording for the GC gate.
FORBIDDEN = ('REPLACE_', 'FILL_', 'TODO', 'DRAFT', 'TO BE FILLED IN', 'is published as the', 'Published on 2026-10',
             'Device results for 2.5.5: PASS', 'device session passed', 'passed on a physical MEGA65',
             'measured on the device', 'owner\'s stopwatch', 'faster on the device',
             'gc-session: PASS', 'GC-stress session passed', 'about 30 times slower than the REPL in both')
BOUNDARY = ('# lisp65 2.5.5 — current release boundary', 'releases/2.5.5.md',
            'The 2.5.4, 2.5.3, 2.5.2 and 2.5.1 text below is historical.', 'Device results for 2.5.5: PENDING',
            'emulator measurements, not device timings', 'about 120 ms', 'every twelfth key',
            'direct `m65d-save`', 'it is not published', 'The published release is 2.5.4')
STATUS_NOTE_254 = 'Published on 2026-10-06 as the [v2.5.4 GitHub release]'
PUBLIC_MAIN_254 = 'bdaf2dd96a6bf77d7a02cccdf0db148cefe914a1'
CORRECTION_254 = ('**Correction, 2026-10-07:**', 'the REPL glyph is visible 14.0 ms after the key is consumed',
                  'about 10 times slower than the REPL, not "about 30 times"',
                  'The text of the published GitHub release is not edited')
# Retained 2.5.4 note claims (historical text, pinned as an additional document; the published wording stays,
# including the two superseded figures, which the first line corrects).
TOKENS_254 = ('7b951eb9c92bc8797278903465b7483b3168a0eb935237a8f62ea3757f205244',
              '250fdc763ae9e5b04cf149a6f2a7a3aa9fb293ff8da58e9a703e0c601efaef5d',
              '## Changed: edit persistence in the IDE (E3)', '**Only the IDE path is protected.**',
              '`(ide-bind-key KEY FUNCTION)`', 'save refused while a file loads',
              '## Device session on a physical MEGA65', '**Passed on 2026-10-05**', 'release-2.5.4-device-report.md',
              '## Garbage-collection stress session on the Final',
              '**By the committed rules the status of the gate is FAIL**',
              '4.17 ms in both versions', 'about 30 times slower per key than the REPL in both versions')


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
            S.require(token in head, '2.5.5 boundary block absent: ' + name + ': ' + token)
        for token in FORBIDDEN:
            S.require(token not in head, 'premature publication/device claim in boundary: ' + name + ': ' + token)
    known = ' '.join(files['docs/known-issues.md'].decode().split('\n---\n', 1)[0].split())
    for token in ('about 10 times slower than the REPL, not 30 times', 'recorded as FAIL by the committed rules',
                  'was not reproduced in seven repeats', 'The published GitHub release text is not edited'):
        S.require(token in known, '2.5.5 known-issues statement absent: ' + token)
    for name in ('README.md', 'docs/user-guide.md'):
        text = files[name].decode()
        S.require(all(t in text for t in ('starts in Comfort', '(repl)', 'l65>', 'empty line', 'history intact')),
                  'Comfort-default usage absent: ' + name)
    for name in ('README.md', 'docs/README.md', 'docs/project-status.md'):
        text = ' '.join(files[name].decode().split())
        S.require('releases/2.5.5.md' in text and 'release candidate' in text and 'not published' in text.replace(
            'is not yet published', 'not published').replace('**not published**', 'not published')
            and 'not yet Final' not in text and 'TO BE FILLED IN' not in text,
            '2.5.5 candidate status line absent/stale: ' + name)
        S.require('published baseline is **lisp65 2.5.4**' in text or name != 'README.md', 'published baseline line: ' + name)
    status = ' '.join(files['docs/project-status.md'].decode().split())
    for token in ('## 2.5.5 release candidate', '## 2.5.4 published', 'about 10 times slower than the REPL, not 30 times',
                  'corrected on 2026-10-07 from "about 30 times"', 'Measured in the emulator, not on the device',
                  'recorded as FAIL by the committed rules'):
        S.require(token in status, '2.5.5 project-status statement absent: ' + token)
    S.require('the editor about 30 times slower than the REPL in both)' not in status,
              'the uncorrected 2.5.4 REPL comparison is still in the project status')


def historical(root, bundle=False):
    """The 2.5.4 note keeps its tokens and carries the published-status line with the dated correction."""
    name = 'docs/release-notes-2.5.4.md' if bundle else NOTES_254
    path = root / name
    if bundle and not path.exists():
        return
    note = ' '.join(path.read_text().split())
    for token in TOKENS_254:
        S.require(token in note, '2.5.4 historical note token absent: ' + token)
    S.require(STATUS_NOTE_254 in note and PUBLIC_MAIN_254 in note, '2.5.4 published-status line absent')
    S.require(note.startswith('> ' + STATUS_NOTE_254), '2.5.4 published-status line is not the first line')
    first = ' '.join(path.read_text().split('\n', 1)[0].split())
    for token in CORRECTION_254:
        S.require(token in first, '2.5.4 correction absent from the status line: ' + token)


def validate(files, expected):
    S.require(set(files) == REQUIRED and set(expected) == REQUIRED, 'document population drift')
    for name, raw in files.items():
        S.require(sha(raw) == expected[name], 'document drift: ' + name)
    claims(files)


def contract():
    value = json.loads(CONTRACT.read_bytes())
    S.require(value['release'] == '2.5.5' and value['notes'] == NOTES, 'wrong release')
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
        # Inherited 2.5.3-note, 2.5.2-note and 2.5.1-era semantic checks on the retained historical notes/text.
        import c2_v254_r2_bundle_docs_gate as H254
        H254.historical(root)
        import c2_v253_r3_bundle_docs_gate as H253
        H253.historical(root)
        import c2_v251_r2_20260929_bundle_docs_gate as H251
        H251.claims({**{n: (root / n).read_bytes() for n in H251.REQUIRED - {H251.NOTES}},
                     H251.NOTES: (root / H251.NOTES).read_bytes()})
    result = dict(status='PASS', documents=len(REQUIRED), proof_documents=len(c['bundle_sources']),
                  mutations=count)
    print('v255 r1 bundle docs: PASS documents=%d proof-documents=%d mutations=%d'
          % (len(REQUIRED), len(c['bundle_sources']), count))
    return result


def selftest():
    files = {n: b'document' for n in REQUIRED}
    files[NOTES] = ' '.join(TOKENS).encode()
    known = ('about 10 times slower than the REPL, not 30 times recorded as FAIL by the committed rules '
             'was not reproduced in seven repeats The published GitHub release text is not edited')
    for n in ('docs/user-guide.md', 'docs/known-issues.md'):
        files[n] = ('\n'.join(BOUNDARY) + '\n' + known +
                    '\nstarts in Comfort (repl) l65> empty line history intact\n---\nold\n').encode()
    status = ' releases/2.5.5.md release candidate is not published'
    files['README.md'] = ('starts in Comfort (repl) l65> empty line history intact' + status +
                          ' published baseline is **lisp65 2.5.4**').encode()
    files['docs/README.md'] = status.encode()
    files['docs/project-status.md'] = (
        status + ' ## 2.5.5 release candidate ## 2.5.4 published about 10 times slower than the REPL, not 30 times '
        'corrected on 2026-10-07 from "about 30 times" Measured in the emulator, not on the device '
        'recorded as FAIL by the committed rules').encode()
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
    for token in ('about 10 times slower than the REPL, not 30 times', 'recorded as FAIL by the committed rules'):
        for n in ('docs/known-issues.md', 'docs/project-status.md'):
            try:
                claims({**files, n: files[n].replace(token.encode(), b'')})
            except ValueError:
                rejected += 1
            else:
                raise AssertionError('synthetic status statement survived: ' + token + ' in ' + n)
    try:
        claims({**files, 'docs/project-status.md': files['docs/project-status.md'] +
                b' the editor about 30 times slower than the REPL in both)'})
    except ValueError:
        rejected += 1
    else:
        raise AssertionError('uncorrected REPL comparison survived')
    return dict(status='PASS', synthetic_mutations=rejected)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--selftest', action='store_true')
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--bundle', action='store_true')
    a = p.parse_args()
    print(json.dumps(selftest() if a.selftest else check(a.root, a.bundle)))
