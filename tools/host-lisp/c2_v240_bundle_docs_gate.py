#!/usr/bin/env python3
"""Check exact approved 2.4.0 documents in the actual source or bundle.

Successor of c2_v230_bundle_docs_gate.py (live mode). Besides the exact-file
seal and the README commands derived from the v240 build authority, semantic
controls pin the claims the owner's known-issues wording and the release
evidence boundary depend on, independently of the SHA seal.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
NOTES='docs/releases/2.4.0.md'
DOCS={'README.md','docs/user-guide.md','docs/known-issues.md',
      'docs/language-reference.md','docs/generated/ide-keymap.md',NOTES}
LAMBDA=('Anonymous `lambda` forms are supported inside `defun` bodies; at the top '
        'level they are refused with `VM: BAD BYTECODE`, the prompt recovers and '
        'nothing already defined is affected.')
WIPE=('In 2.3.0, a `defun` published from inside a running form (e.g. `eval` inside '
      '`dotimes`) is silently destroyed; the next call fails with `VM: BAD BYTECODE`; '
      'earlier definitions are intact.')
SESSION=('In 2.3.0, an error inside `eval` called from within a running form (e.g. '
         'inside `dotimes` or `let`) leaves the REPL without a prompt; reset required; '
         'nothing already defined is lost.')


def commands(authority):
    if authority['release']!='2.4.0':
        raise ValueError('wrong release authority')
    entry=authority['entry_point']
    if entry!='make workbench-product-v'+authority['release'].replace('.',''):
        raise ValueError('entry point not derived from release')
    return [entry+'-build',entry+'-verify']


def readme_commands(raw,authority):
    actual=re.findall(r'`(make workbench-product-v[0-9]+-(?:build|verify))`',raw.decode())
    if actual!=commands(authority):
        raise ValueError('README build commands differ from release authority')


def final_claims(files):
    text={p:' '.join(raw.decode().replace('**','').split()) for p,raw in files.items()}
    notes=text[NOTES]
    if ('ordinary text 1,209 bytes free against a floor of 32' not in notes
            or '`docs/planning/nested-error-recovery-final-report.md`' not in notes):
        raise ValueError('final reserve claim or its source citation differs')
    if ('RUN to the prompt 32.7 s (tool clock)' not in notes
            or 'they are not stopwatch readings' not in notes
            or '16.84 s (emulator)' not in notes):
        raise ValueError('device/emulator timing labels differ')
    unverified=notes.split('### Not verified on the device',1)
    if len(unverified)!=2 or not all(item in unverified[1] for item in (
            'RUN/STOP inside a running form','a cold power cycle','`C-x C-c`',
            'compile, save, reload and call')):
        raise ValueError('owner rows not verified on the device are not listed')
    if 'no claim is made about which public release first acquired' not in notes:
        raise ValueError('compile-string provenance boundary differs')
    issues=text['docs/known-issues.md']
    if LAMBDA not in issues:
        raise ValueError('owner-approved lambda wording differs')
    if WIPE not in issues or SESSION not in issues or issues.count('defect shipped in 2.3.0; fixed in 2.4.0')!=2:
        raise ValueError('fixed 2.3.0 defects are not recorded as fixed in 2.4.0')
    if '2.4.0 rows not yet verified on the device' not in issues:
        raise ValueError('owner rows absent from Known Issues')


def validate(files,expected,authority):
    if set(expected)!=DOCS or set(files)!=DOCS:
        raise ValueError('approved document population drift')
    for path,digest in expected.items():
        if hashlib.sha256(files[path]).hexdigest()!=digest:
            raise ValueError('approved document differs: '+path)
    readme_commands(files['README.md'],authority)
    final_claims(files)


def check(root,bundle=False):
    contract=json.loads((ROOT/'config/c2-v240-bundle-docs.json').read_bytes())
    authority=json.loads((ROOT/'config/c2-v240-public-build-authority.json').read_bytes())
    if contract['release']!='2.4.0':
        raise ValueError('wrong document release')
    files={p:(root/('docs/release-notes.md' if bundle and p==NOTES else p)).read_bytes()
           for p in DOCS}
    expected=contract['documents']
    validate(files,expected,authority)
    rejected=[]
    for path in sorted(DOCS):
        for kind in ('contract-omission','file-omission','change'):
            trial=dict(files);binding=dict(expected)
            if kind=='contract-omission':
                del binding[path];del trial[path]
            elif kind=='file-omission':
                del trial[path]
            else:
                trial[path]+=b'\nUnapproved claim\n'
            try:validate(trial,binding,authority)
            except ValueError:rejected.append(path+':'+kind)
            else:raise ValueError('document mutation survived: '+path+':'+kind)
    # Exercise command derivation independently of the outer exact SHA seal.
    for name,replacement in (('old-release','v230'),('unbound-next-release','v250')):
        mutated=files['README.md'].replace(b'v240',replacement.encode())
        try:readme_commands(mutated,authority)
        except ValueError:rejected.append('README:'+name)
        else:raise ValueError('command mutation survived: '+name)
    # Semantic controls run independently of the exact-file SHA seal.
    for name,path,old,new in (
        ('reserve','docs/releases/2.4.0.md','1,209','1,354'),
        ('source-citation',NOTES,'docs/planning/nested-error-recovery-final-report.md','unbound.md'),
        ('tool-clock-label',NOTES,'32.7 s (tool clock)','32.7 s'),
        ('emulator-label',NOTES,'16.84 s (emulator)','16.84 s'),
        ('run-stop-row-dropped',NOTES,'RUN/STOP inside a running form','RUN/STOP'),
        ('compile-string-provenance',NOTES,'no claim is made','a claim is made'),
        ('lambda-wording','docs/known-issues.md','the prompt recovers and','the prompt usually recovers and'),
        ('wipe-fixed','docs/known-issues.md','is silently destroyed; the next call','may be destroyed; the next call'),
        ('session-fixed','docs/known-issues.md','reset required;','reset optional;'),
        ('owner-rows','docs/known-issues.md','2.4.0 rows not yet verified on the device','2.4.0 device rows')):
        trial=dict(files)
        trial[path]=trial[path].replace(old.encode(),new.encode())
        if trial[path]==files[path]:raise ValueError('vacuous claim mutation: '+name)
        try:final_claims(trial)
        except ValueError:rejected.append('final-claims:'+name)
        else:raise ValueError('claim mutation survived: '+name)
    if bundle:
        for source in contract['bundle_sources']:
            if hashlib.sha256((root/source['bundle_path']).read_bytes()).hexdigest()!=source['sha256']:
                raise ValueError('bundled source differs: '+source['bundle_path'])
    return dict(status='PASS: ACTUAL 2.4.0 BUNDLE DOCUMENTS',files=len(files),
        mutations=rejected,mode='extracted-bundle' if bundle else 'actual-source',
        approval=contract['approval'],commands=commands(authority))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--bundle',action='store_true')
    args=parser.parse_args()
    print(json.dumps(check(args.root,args.bundle),indent=2))


if __name__=='__main__':main()
