#!/usr/bin/env python3
"""2.5.2 document population: prospective (working tree incl. untracked) and indexed.

Successor of c2_v251_r2_20260929_document_index; additionally requires the
2.5.2 release note and device report as current documents. Git index unchanged.
"""
import json
import subprocess
import document_index as D

REQUIRED_CURRENT = ('docs/releases/2.5.2.md', 'docs/planning/release-2.5.2-device-report.md')


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
            raise SystemExit('document-index v252: FAIL: required current document absent: ' + name)
    print(json.dumps(dict(status='PASS', scope='working tree including untracked reviewer files; Git index unchanged',
                          documents=len(paths), classes=result, required_current=list(REQUIRED_CURRENT)), indent=2))


if __name__ == '__main__':
    main()
