#!/usr/bin/env python3
"""Check exact approved 2.3.0 documents in the actual source or bundle."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[2]
DOCS={'README.md','docs/user-guide.md','docs/known-issues.md',
      'docs/language-reference.md','docs/generated/ide-keymap.md','docs/releases/2.3.0.md'}


def commands(authority):
    if authority['release']!='2.3.0':
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
    notes=text['docs/releases/2.3.0.md']
    sentence=('Against the immediate predecessor, the native prompt lanes read '
        '1.024× / 1.115× raw over all samples, with the accepted phase attribution '
        '(five collections in each world, one moved from boot into typing by 39 fewer '
        'startup allocations, per-key work within the bound), and '
        '1.005× / 1.010× in the same-phase reading.')
    if ('ordinary text 2,294 bytes free against a floor of 32' not in notes
            or sentence not in notes or '`docs/planning/init-echo-final-report.md`' not in notes):
        raise ValueError('final reserve/paired lane claim or source citation differs')
    for path in ('docs/releases/2.3.0.md','docs/user-guide.md','docs/known-issues.md'):
        if ('nested `load` from a loading source' not in text[path]
                or '`require` inside `INIT.L65` is supported' not in text[path]):
            raise ValueError('nested load and INIT require conflated: '+path)


def validate(files,expected,authority):
    if set(expected)!=DOCS or set(files)!=DOCS:
        raise ValueError('approved document population drift')
    for path,digest in expected.items():
        if hashlib.sha256(files[path]).hexdigest()!=digest:
            raise ValueError('approved document differs: '+path)
    readme_commands(files['README.md'],authority)
    final_claims(files)


def historical_files(contract, reader=None):
    commit=contract['historical_commit']
    if commit!='e94da0f1b3246924c9b261ba033279a78ae4c1b5':
        raise ValueError('historical 2.3.0 document era drift')
    if reader is None:
        reader=lambda revision,path:subprocess.check_output(
            ['git','show',revision+':'+path],cwd=ROOT)
    return {p:reader(commit,p) for p in DOCS}


def check(root,bundle=False,historical=False):
    contract=json.loads((ROOT/'config/c2-v230-bundle-docs.json').read_bytes())
    authority=json.loads((ROOT/'config/c2-v230-public-build-authority.json').read_bytes())
    if contract['release']!='2.3.0':
        raise ValueError('wrong document release')
    if historical and (bundle or root.resolve()!=ROOT.resolve()):
        raise ValueError('historical selection is not an export/bundle fallback')
    files=historical_files(contract) if historical else {
        p:(root/('docs/release-notes.md' if bundle and p=='docs/releases/2.3.0.md' else p)).read_bytes()
        for p in DOCS}
    expected=contract['documents']
    validate(files,expected,authority)
    rejected=[]
    if historical:
        drift=dict(contract);drift['historical_commit']='HEAD'
        try:historical_files(drift)
        except ValueError:rejected.append('historical:live-revision')
        else:raise ValueError('historical live revision survived')
        # Deliberately feed a live-successor document to the sealed reader.
        trial=dict(files)
        trial['docs/known-issues.md']+=b'\nLive successor issue, not a release-era document\n'
        try:validate(trial,expected,authority)
        except ValueError:rejected.append('historical:live-document')
        else:raise ValueError('historical live-document mutation survived')
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
    for name,replacement in (('old-release','v220'),('unbound-next-release','v240')):
        mutated=files['README.md'].replace(b'v230',replacement.encode())
        try:readme_commands(mutated,authority)
        except ValueError:rejected.append('README:'+name)
        else:raise ValueError('command mutation survived: '+name)
    # Semantic controls run independently of the exact-file SHA seal.
    for name,old,new in (
        ('pre-echo-reserve','2,294','2,314'),
        ('raw-reading-omitted','1.024× / 1.115×','omitted'),
        ('same-phase-reading-omitted','1.005× / 1.010×','omitted'),
        ('collection-count','five collections','four collections'),
        ('startup-allocation-count','39 fewer','38 fewer'),
        ('source-citation','docs/planning/init-echo-final-report.md','unbound.md'),
        ('nested-load-conflated','nested `load`','nested library load')):
        trial=dict(files)
        path='docs/releases/2.3.0.md'
        trial[path]=trial[path].replace(old.encode(),new.encode())
        if trial[path]==files[path]:raise ValueError('vacuous claim mutation: '+name)
        try:final_claims(trial)
        except ValueError:rejected.append('final-claims:'+name)
        else:raise ValueError('claim mutation survived: '+name)
    if bundle:
        source=contract['measurement_source']
        if hashlib.sha256((root/source['bundle_path']).read_bytes()).hexdigest()!=source['sha256']:
            raise ValueError('bundled measurement source differs')
    return dict(status='PASS: HISTORICAL 2.3.0 DOCUMENTS' if historical else 'PASS: ACTUAL 2.3.0 BUNDLE DOCUMENTS',files=len(files),
        mutations=rejected,mode='historical-release' if historical else ('extracted-bundle' if bundle else 'actual-source'),
        approval=contract['approval'],commands=commands(authority))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--bundle',action='store_true')
    parser.add_argument('--historical',action='store_true')
    args=parser.parse_args()
    print(json.dumps(check(args.root,args.bundle,args.historical),indent=2))


if __name__=='__main__':main()
