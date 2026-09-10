#!/usr/bin/env python3
"""Validate/materialize the explicitly bound 2.2.0 native source projection.

No private receipt, predecessor ELF or card adapter is a producer input.
This module does not invoke a compiler and cannot claim a reproduction.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'config/c2-v220-public-native/manifest.json'
AUTHORITY = ROOT / 'config/c2-v220-public-build-authority.json'


def canonical(value):
    return (json.dumps(value, indent=2, sort_keys=True)+'\n').encode()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def local(name):
    path=Path(name)
    require(not path.is_absolute() and '..' not in path.parts, 'non-local input path')
    return ROOT/path


def bound(row):
    path=local(row['path'])
    require(path.is_file() and not path.is_symlink(), 'missing/aliased input: '+row['path'])
    raw=path.read_bytes()
    require(len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],
            'input identity drift: '+row['path'])
    return raw


def validate(value, authority):
    require(hashlib.sha256(canonical(value)).hexdigest()==authority['native_projection']['sha256'],
            'native projection differs from public build authority')
    require(value['release']==authority['release']=='2.2.0', 'wrong release')
    require(value['private_receipts_are_build_inputs'] is False, 'private build input')
    profile=bound(value['profile']).decode()
    expected=[line.split('=',1)[1].rsplit(':',1) for line in profile.splitlines()
              if line.startswith('input_sha256=')]
    observed=[]
    for row in value['sources']:
        raw=bound(row['source'])
        raw.decode('utf-8')
        require(b'\0' not in raw, 'binary native input')
        target=local(row['materialized_path'])
        require(target.suffix in ('.c','.s','.inc'), 'not a native source input')
        if row['kind']=='tracked-source':
            require(row['materialized_path']==row['source']['path'], 'tracked input renamed')
        else:
            require(row['kind']=='approved-consumed-source-projection'
                    and target.parent==ROOT/'build/retirement-repair-product-r2/wplto/generated-product-sources',
                    'generated input owner drift')
        observed.append([row['materialized_path'],hashlib.sha256(raw).hexdigest()])
    require(observed==expected and len({r[0] for r in observed})==len(observed),
            'input population/order differs from consumed profile')
    features=[line.split('=',1)[1].split(',') for line in profile.splitlines()
              if line.startswith('feature_defines=')]
    require(features==[value['features']], 'feature population drift')
    definitions=value['definitions']
    names=[d.split('=',1)[0] for d in definitions]
    require(len(names)==len(set(names)) and set(features[0])<=set(names), 'compiler feature closure drift')
    for row in value['linker_sources']:
        bound(row['source']).decode('utf-8')
        require(local(row['materialized_path']).suffix=='.ld', 'linker input kind drift')
    require(value['target_pair']==authority['raw_pair'], 'target pair differs from release authority')
    return dict(status='PASS: PUBLIC NATIVE SOURCE PROJECTION',
                translation_units=sum(r['translation_unit'] for r in value['sources']),
                inputs=len(observed),definitions=len(names),features=len(features[0]),
                generated=value['generated_translation_units'],compiler_invocations=0)


def check():
    return validate(json.loads(MANIFEST.read_bytes()),json.loads(AUTHORITY.read_bytes()))


def selftest():
    value=json.loads(MANIFEST.read_bytes());authority=json.loads(AUTHORITY.read_bytes())
    result=validate(value,authority)
    cases={}
    def case(name):
        cases[name]=copy.deepcopy(value);return cases[name]
    case('missing-input')['sources'].pop()
    v=case('duplicate-input');v['sources'].append(copy.deepcopy(v['sources'][0]))
    v=case('changed-source');v['sources'][0]['source']['sha256']='0'*64
    v=case('basename-instead-of-projection');r=next(r for r in v['sources'] if r['kind']!='tracked-source');r['source']['path']='src/'+Path(r['source']['path']).name
    case('old-release')['release']='2.1.0'
    case('partial-configuration')['definitions']=[d for d in value['definitions'] if not d.startswith('LISP65_INTERN_SERVICE_SLOT=')]
    case('wrong-overlay-slot')['definitions']=[d.replace('LISP65_ERROR_OVERLAY_SLOT=47','LISP65_ERROR_OVERLAY_SLOT=32') for d in value['definitions']]
    case('private-proof-input')['private_receipts_are_build_inputs']=True
    case('missing-linker')['linker_sources'].pop()
    case('foreign-target')['target_pair']['ELF']['sha256']='0'*64
    case('missing-feature')['features'].pop()
    case('escaped-input')['sources'][0]['source']['path']='../outside.c'
    rejected=[]
    for name,mutant in cases.items():
        try:validate(mutant,authority)
        except ValueError:rejected.append(name)
        else:raise ValueError('mutation survived: '+name)
    result['mutations_rejected']=rejected
    return result


def materialize():
    result=check();value=json.loads(MANIFEST.read_bytes())
    closure=json.loads((ROOT/'config/c2-v220-public-native/include-closure.json').read_bytes())
    for row in value['sources']+value['linker_sources']+closure['materialized']:
        target=local(row['materialized_path']);raw=bound(row['source'])
        if target.exists():
            require(target.read_bytes()==raw, 'refuse overwrite of another world: '+str(target))
        else:
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('check','selftest','materialize'))
    args=parser.parse_args()
    print(json.dumps({'check':check,'selftest':selftest,'materialize':materialize}[args.mode](),indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
