#!/usr/bin/env python3
"""2026-09-27 successor: exact 2.5.0 docs and independent scope controls."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CONTRACT=ROOT/'config/c2-v250-bundle-docs.json'
NOTES='docs/releases/2.5.0.md'
REQUIRED={NOTES,'README.md','docs/user-guide.md','docs/known-issues.md',
          'docs/language-reference.md','docs/generated/ide-keymap.md','docs/project-status.md'}
TOKENS=('Comfort-default Final','960 Bank-2','l65>','lisp65>','(repl)',
        'empty line','+8 s','+12 live cells','+2.1%','five more boot collections',
        'Set B and Card L are NOT','Ship and Publish are delegated', 'accepted this named GC cost',
        'Pending device confirmation', 'physical RUN/STOP',
        '137bfa51589f096eb715bc1e71c66196b79a365db65c1373696ea82f04dc34e5')

def claims(files):
    notes=' '.join(files[NOTES].decode().split())
    for token in TOKENS:
        if token not in notes:raise ValueError('release boundary absent: '+token)
    for name in ('README.md','docs/user-guide.md'):
        text=files[name].decode()
        if not all(t in text for t in ('starts in Comfort','(repl)','l65>','empty line','history intact')):
            raise ValueError('Comfort-default usage absent: '+name)
    issues=files['docs/known-issues.md'].decode()
    if not all(t in issues for t in ('2.5.0 release wording', 'Pending device confirmation', 'accepted this named GC cost','does not reach the IDE','Backspace latency')):
        raise ValueError('final wording boundary absent')

def validate(files,expected):
    if set(files)!=REQUIRED or set(expected)!=REQUIRED:raise ValueError('document population drift')
    for name,raw in files.items():
        if hashlib.sha256(raw).hexdigest()!=expected[name]:raise ValueError('document drift: '+name)
    claims(files)

def check(root,bundle=False):
    contract=json.loads(CONTRACT.read_bytes())
    if contract['release']!='2.5.0':raise ValueError('wrong release')
    files={p:(root/('docs/release-notes.md' if bundle and p==NOTES else p)).read_bytes() for p in REQUIRED}
    validate(files,contract['documents']);count=0
    for name in files:
        trial=dict(files);trial[name]+=b'changed'
        try:validate(trial,contract['documents'])
        except ValueError:count+=1
        else:raise ValueError('changed document survived')
        trial=dict(files);del trial[name]
        try:validate(trial,contract['documents'])
        except ValueError:count+=1
        else:raise ValueError('omitted document survived')
    for token in TOKENS:
        trial=dict(files);trial[NOTES]=trial[NOTES].replace(token.encode(),b'REMOVED')
        try:claims(trial)
        except ValueError:count+=1
        else:raise ValueError('semantic control survived: '+token)
    for row in contract['bundle_sources']:
        path=root/(row['bundle_path'] if bundle else row['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('proof doc drift')
    print('v250 bundle docs: PASS documents=7 proof-documents=2 mutations='+str(count))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--bundle',action='store_true');a=p.parse_args();check(a.root,a.bundle)
