#!/usr/bin/env python3
"""Two one-shot renderer reproductions; a failed attempt is never retried."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import c2_v200_public_clean_build as BASE
import public_export_population as EXPORT
import c2_v210_bundle_docs_gate as DOCS

AUTHORITY = Path('config/c2-v210-public-build-authority.json')
PAIR = {
    'ELF': (642492, 'c09d6e4d37a7e413133fc8541cc351e5cfc8274fefb7d3aaa325638f39391b2c'),
    'PRG': (41811, 'e05a242cfd81f2c72e00d695e682e8e5eb2f017baf50ec58f2933ebcfe2e2f23'),
}
COMMAND = ['make', '--no-print-directory', 'workbench-product-v210']


def require(value, message):
    if not value:
        raise RuntimeError(message)


def identity(path):
    require(path.is_file() and not path.is_symlink(), f'absent or linked file: {path}')
    raw = path.read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def validate_pair(rows):
    require(set(rows) == set(PAIR), 'raw pair population drift')
    for role, target in PAIR.items():
        row = rows[role]
        require((row['bytes'], row['sha256']) == target,
                f'HALT: {role} differs from the frozen renderer pair')


def run(args, cwd, env=None):
    return subprocess.check_output(args, cwd=cwd, env=env, stderr=subprocess.STDOUT).decode()


def lineage(repository, commit, public_main):
    # Both identities must resolve before a clone or compiler can run.
    selected = run(['git', 'rev-parse', f'{commit}^{{commit}}'], repository).strip()
    parent = run(['git', 'rev-parse', f'{public_main}^{{commit}}'], repository).strip()
    run(['git', 'merge-base', '--is-ancestor', parent, selected], repository)
    return selected, parent


def check_root(root):
    authority = json.loads((root/AUTHORITY).read_text())
    require(authority['release'] == 'v2.1.0'
            and authority['producer_preflight_complete'] is True
            and authority['private_evidence_is_build_input'] is False,
            'public renderer authority is not armed')
    validate_pair(authority['raw_pair'])
    wplto = root/'build/v2.1/renderer-branch-product-r1/wplto'
    rows = {'ELF': identity(wplto/'lisp65-c2-substitution-linked.prg.elf'),
            'PRG': identity(wplto/'lisp65-c2-substitution-linked.prg')}
    validate_pair(rows)
    manifest = json.loads((root/authority['candidate_manifest_path']).read_text())
    require(manifest['private_evidence_inputs'] == 0
            and manifest['artifact_count'] == 19
            and len(manifest['artifacts']) == 19, 'public role population drift')
    roles = {}
    for row in manifest['artifacts']:
        relative = Path(row['path'])
        require(not relative.is_absolute() and '..' not in relative.parts,
                'artifact escaped public checkout')
        require(row['role'] not in roles, 'duplicate artifact role')
        observed = identity(root/relative)
        require(observed == authority['sealed_roles'][row['role']]
                and observed == {k: row[k] for k in ('bytes','sha256')},
                'HALT: public artifact differs: '+row['role'])
        roles[row['role']] = {k: row[k] for k in ('role','name','bytes','sha256')}
    require(set(roles) == set(authority['sealed_roles']), 'omitted artifact role')
    return {'raw_pair': rows, 'artifacts': [roles[k] for k in sorted(roles)],
            'source_projection': BASE.public_source_projection(root)}


def qualify(repository, commit, public_main, toolchain, output):
    commit, parent = lineage(repository, commit, public_main)
    require(not output.exists(), 'one-shot release run already exists; no retry')
    exported = EXPORT.commit_blobs(repository, commit)
    export_receipt = EXPORT.audit_export(exported)
    export_receipt['mutations'] = EXPORT.selftest()
    authority = json.loads(run(['git','show',f'{commit}:{AUTHORITY}'], repository))
    require(authority['producer_preflight_complete'] is True,
            'source preflight must complete before either reproduction')
    validate_pair(authority['raw_pair'])
    output.mkdir(parents=True)
    (output/'export-population.json').write_text(json.dumps(export_receipt, indent=2, sort_keys=True)+'\n')
    # Exclusive invocation record is written before either build begins.
    with (output/'invocation.json').open('x') as handle:
        json.dump({'source_commit':commit,'public_main':parent,
                   'reproductions_maximum':2,'third_attempt':False,
                   'repair':False,'card_budget_consumption':False},handle,indent=2)
    results=[]
    for number, axis in enumerate(BASE.AXES,1):
        checkout=output/f'clean-{number}'
        env={**os.environ,'GIT_LFS_SKIP_SMUDGE':'1','PYTHONDONTWRITEBYTECODE':'1'}
        run(['git','clone','--no-local','--no-checkout',str(repository),str(checkout)],output,env)
        run(['git','checkout','--detach',commit],checkout,env)
        require(not (checkout/'build').exists(), 'clean clone contains build inputs')
        require(not (checkout/'tools/llvm-mos').exists(), 'toolchain unexpectedly bundled')
        (checkout/'tools/llvm-mos').symlink_to(toolchain,target_is_directory=True)
        document_facts=DOCS.facts(checkout)
        document_texts=DOCS.source_texts(checkout)
        document_result=DOCS.validate(document_texts,DOCS.TOP,document_facts)
        document_result['mutations_rejected']=DOCS.selftest(document_texts,document_facts)
        (output/f'docs-{number}.json').write_text(json.dumps(document_result,indent=2,sort_keys=True)+'\n')
        env.update({key:axis[key] for key in ('PYTHONHASHSEED','SOURCE_DATE_EPOCH','TZ')})
        env['LLVM_MOS_ROOT']=str(toolchain)
        started={'attempt':number,'source_commit':commit,'command':COMMAND,
                 'environment':{key:axis[key] for key in ('PYTHONHASHSEED','SOURCE_DATE_EPOCH','TZ','UMASK')}}
        with (output/f'attempt-{number}.json').open('x') as handle:
            json.dump(started,handle,indent=2)
        with (output/f'clean-{number}.log').open('x') as log:
            process=subprocess.run(COMMAND,cwd=checkout,env=env,stdout=log,
                stderr=subprocess.STDOUT,umask=int(axis['UMASK'],8))
        require(process.returncode==0,
                f'HALT: reproduction {number} exited {process.returncode}; no retry')
        result=check_root(checkout)
        if results:
            require(result==results[0]['result'], 'HALT: independent reproduction differs')
        results.append({'attempt':number,'result':result})
        (output/f'passed-{number}.json').write_text(json.dumps(results[-1],indent=2,sort_keys=True)+'\n')
    receipt={'format':'lisp65-v210-public-clean-build-v1','status':'PASS',
             'source_commit':commit,'public_main':parent,'builds':results,
             'private_evidence_inputs':0,'card_budget_consumption':False}
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print('PASS: two exact renderer reproductions; Publish remains closed')


def selftest():
    good={k:{'bytes':v[0],'sha256':v[1]} for k,v in PAIR.items()}
    validate_pair(good)
    mutants=[{}, {'ELF':good['ELF']},
             {**good,'PRG':{**good['PRG'],'sha256':'0'*64}},
             {**good,'ELF':{**good['ELF'],'bytes':good['ELF']['bytes']+1}}]
    for mutant in mutants:
        try:
            validate_pair(mutant)
        except RuntimeError:
            continue
        raise RuntimeError('pair mutation survived')
    print('PASS: raw-pair mutations=4; no build invoked')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('selftest','qualify','check-root'))
    parser.add_argument('--repository',type=Path)
    parser.add_argument('--commit')
    parser.add_argument('--public-main')
    parser.add_argument('--toolchain',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.action=='selftest':
        selftest()
    elif args.action=='check-root':
        print(json.dumps(check_root(args.repository.resolve()),indent=2))
    else:
        require(all((args.repository,args.commit,args.public_main,args.toolchain,args.output)),
                'all public reproduction authorities must be explicit')
        qualify(args.repository.resolve(),args.commit,args.public_main,
                args.toolchain.resolve(),args.output.resolve())


if __name__=='__main__':
    try:
        main()
    except (RuntimeError,subprocess.CalledProcessError) as error:
        print(str(error),file=sys.stderr)
        sys.exit(1)
