#!/usr/bin/env python3
"""2.5.4 document population: prospective (working tree incl. untracked) and indexed.

Successor of c2_v253_r1_document_index (immutable); requires the 2.5.4 release note as a
current document. The device report and Before-Ship record are listed in
REQUIRED_CURRENT_LATER and become required only when the reviewer has written
and indexed them (they are PENDING before the device session). Git index unchanged.
"""
import json
import subprocess
import document_index as D

REQUIRED_CURRENT = ('docs/releases/2.5.4.md',)
REQUIRED_CURRENT_LATER = ('docs/planning/release-2.5.4-before-ship.md', 'docs/planning/release-2.5.4-device-report.md')


def main():
    raw = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', 'docs'],
                                  cwd=D.ROOT)
    paths = tuple(sorted({p.decode() for p in raw.split(b'\0') if p.endswith(b'.md')}))
    index = D.load_index(D.DEFAULT_INDEX)
    result = D.validate_index(index, paths)
    D.verify_files(D.ROOT, paths)
    classes = {r['path']: r['class'] for r in index['documents']}
    for name in REQUIRED_CURRENT:
        if name not in paths or classes.get(name) != 'current':
            raise SystemExit('document-index v254: FAIL: required current document absent: ' + name)
    later = [n for n in REQUIRED_CURRENT_LATER if n in paths]
    for name in later:
        if classes.get(name) is None:
            raise SystemExit('document-index v254: FAIL: later document present but not indexed: ' + name)
    print(json.dumps(dict(status='PASS', scope='working tree including untracked reviewer files; Git index unchanged',
                          documents=len(paths), classes=result, required_current=list(REQUIRED_CURRENT),
                          pending_not_yet_present=[n for n in REQUIRED_CURRENT_LATER if n not in paths]), indent=2))


if __name__ == '__main__':
    main()
