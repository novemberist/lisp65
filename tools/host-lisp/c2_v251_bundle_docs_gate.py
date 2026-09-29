#!/usr/bin/env python3
"""2026-09-27 successor: exact 2.5.1 docs and independent scope controls."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CONTRACT=ROOT/'config/c2-v251-bundle-docs.json'
NOTES='docs/releases/2.5.1.md'
REQUIRED={NOTES,'README.md','docs/user-guide.md','docs/known-issues.md',
          'docs/language-reference.md','docs/generated/ide-keymap.md','docs/project-status.md','docs/README.md'}
TOKENS=('Backspace Final','C-x q','Physical `C-x C-c`','−7/−19/−26 % at 10/40/70 chars',
        'settle window','Backspace **barely noticeably improved**','PASS on BS251.D81 after power cycle',
        '≈ 80 ms','about 70 %','code-object reloads','Pending owner confirmation',
        'Set B and Card L','owner accepted the named Comfort GC cost',
        'a2872fbd8aa53690da0fb7a7281bd2746497589a036c27fa3d7f302a8cafc445')

def claims(files):
    notes=' '.join(files[NOTES].decode().split())
    for token in TOKENS:
        if token not in notes:raise ValueError('release boundary absent: '+token)
    for name in ('README.md','docs/user-guide.md'):
        text=files[name].decode()
        if not all(t in text for t in ('starts in Comfort','(repl)','l65>','empty line','history intact')):
            raise ValueError('Comfort-default usage absent: '+name)
    issues=files['docs/known-issues.md'].decode()
    if not all(t in issues for t in ('2.5.1 release wording', 'Pending device confirmation', 'accepted this named GC cost','does not reach the IDE','Keystroke latency: about 80 ms per key', '70 % of it spent reloading', 'the owner found it barely noticeable')):
        raise ValueError('final wording boundary absent')

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
        trial=dict(files);trial[NOTES]=trial[NOTES].replace(token.encode(),b'REMOVED')
        try:claims(trial)
        except ValueError:count+=1
        else:raise ValueError('semantic control survived: '+token)
    for row in contract['bundle_sources']:
        path=root/(row['bundle_path'] if bundle else row['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('proof doc drift')
    print(f'v251 bundle docs: PASS documents={len(REQUIRED)} proof-documents={len(contract["bundle_sources"])} mutations={count}')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--bundle',action='store_true');a=p.parse_args();check(a.root,a.bundle)
