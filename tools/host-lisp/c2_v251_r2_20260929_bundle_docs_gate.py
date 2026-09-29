#!/usr/bin/env python3
"""2026-09-27 successor: exact 2.5.1 docs and independent scope controls."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CONTRACT=ROOT/'config/c2-v251-r2-20260929-bundle-docs.json'
NOTES='docs/releases/2.5.1.md'
REQUIRED={NOTES,'README.md','docs/user-guide.md','docs/known-issues.md',
          'docs/language-reference.md','docs/generated/ide-keymap.md','docs/project-status.md','docs/README.md'}
TOKENS=('STRINGS Final','C-x q','Physical `C-x C-c`','3.24 M -> 1.58 M',
        '80 -> 39 ms','1,200–1,800 -> 53 reads/key','projected lane',
        'Continuation lines are not editable after Return','Up/Down always walk history',
        'Comfort multi-line strings now evaluate and display correctly',
        '2.5.0','workaround','pending the owner session','small Backspace tail change',
        '9978daa146b89cf71ad1d3f290d80cf74b197911e7854859f9e4aa9bb2fce441')

def claims(files):
    notes=' '.join(files[NOTES].decode().split())
    for token in TOKENS:
        if token not in notes:raise ValueError('release boundary absent: '+token)
    for name in ('README.md','docs/user-guide.md'):
        text=files[name].decode()
        if not all(t in text for t in ('starts in Comfort','(repl)','l65>','empty line','history intact')):
            raise ValueError('Comfort-default usage absent: '+name)
    issues=files['docs/known-issues.md'].decode()
    if not all(t in issues for t in ('Fixed in 2.5.1','3.24 M -> 1.58 M','Up/Down always walk','Pending device confirmation','does not reach the IDE')):
        raise ValueError('current issue boundary absent')

def validate(files,expected):
    if set(files)!=REQUIRED or set(expected)!=REQUIRED:raise ValueError('document population drift')
    for name,raw in files.items():
        if hashlib.sha256(raw).hexdigest()!=expected[name]:raise ValueError('document drift: '+name)
    claims(files)

def check(root,bundle=False):
    contract=json.loads(CONTRACT.read_bytes())
    if contract['release']!='2.5.1':raise ValueError('wrong release')
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
        trial=dict(files);trial[NOTES]=' '.join(trial[NOTES].decode().split()).encode().replace(token.encode(),b'REMOVED')
        try:claims(trial)
        except ValueError:count+=1
        else:raise ValueError('semantic control survived: '+token)
    for row in contract['bundle_sources']:
        path=root/(row['bundle_path'] if bundle else row['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('proof doc drift')
    print(f'v251 bundle docs: PASS documents={len(REQUIRED)} proof-documents={len(contract["bundle_sources"])} mutations={count}')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--bundle',action='store_true');a=p.parse_args();check(a.root,a.bundle)
