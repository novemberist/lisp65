#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Pack the accepted renderer reproductions; never compile or publish."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

import c2_v200_release_package as BASE
import c2_v210_bundle_docs_gate as DOCS
import public_export_population as EXPORT

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/release-v2.1.0'
TOP = 'lisp65-2.1.0'
RELEASE = 'v2.1.0'
VARIANT = 'v2.1-renderer-f011-native'
CLAIMS = {
    'banner': 'WORKBENCH 2.0.0',
    'device_boot': 'variant-B; off duration not independently timed; not autoboot-A',
    'native_smokes': ['0 2', '0 (9 2)', '0 98', '1 42'],
    'measured_D5': {'symbol_slots': 107, 'namepool_bytes': 1467},
    'recursion': '12 returns 12; 13 repeats E29; owner reset; not safe-depth guarantee',
    'printer': 'host-only; no new device claim',
    'F011': 'buffered completion mask D8/40; immediate READ; bounded wait; LOAD_OPEN propagation',
    'PCRel16': 'none in executable population; both forced failure gates executed',
    'typing_latency': 'no improvement claimed; no new capture measurement',
    'not_included': ['Comfort', 'trampoline', 'SP-floor', 'wrap-safe selector', 'Matcher/Blink', 'Tier 2'],
    'check_source': 'accepted historical Carrier-SHA-pin exception; not unconditional Exit 0',
}


def require(ok, why):
    if not ok:
        raise ValueError(why)


def read(path):
    return json.loads(path.read_text())


def record(path):
    return {'bytes': path.stat().st_size, 'sha256': BASE.sha(path)}


def git(repo, *args):
    return subprocess.check_output(['git', *args], cwd=repo).decode().strip()


def readme(product_set):
    return (f'''LISP65 WORKBENCH 2.1.0 PRODUCT RELEASE
====================================

This is a product release, not the 2.0.1 documentation-only update.
The qualified renderer/F011 product still displays WORKBENCH 2.0.0.
Product artifact set: {product_set}

Before use, run: python3 verify.py

media/lisp65-product.d81 is the read-only system medium;
media/lisp65-work.d81 is the blank writable work medium.
There is no INIT.L65 on the selected product medium.

Included: buffered F011 failure handling and the PCRel16 branch-class fix.
Measured loaded capacity: 107 symbol slots / 1,467 name bytes.
Comfort, trampoline, SP-floor, Matcher/Blink and Tier 2 are not included.
Deep recursion can still corrupt the hardware stack and require a reset.
No new typing-latency improvement or capture measurement is claimed.

The source package corrects private path metadata and the prebuilt host
shared library inherited by the 2.0.1 source archive. Existing releases
are unchanged; frozen serialized inputs are explicitly declared.
See docs/release-notes.md and docs/known-issues.md before use.
''').encode('ascii')


def validate_claims(manifest, text, notes):
    require(manifest['claims'] == CLAIMS, 'release claim boundary drift')
    require('2.1.0 PRODUCT RELEASE' in text and
            'not the 2.0.1 documentation-only update' in text and
            'still displays WORKBENCH 2.0.0' in text and
            '107 symbol slots / 1,467 name bytes' in text and
            'Comfort, trampoline, SP-floor, Matcher/Blink and Tier 2 are not included' in text,
            'README release classification drift')
    for term in ('2.0.1 source archive', 'private absolute path metadata',
                 'prebuilt\nhost shared library', 'Existing\nreleases are unchanged',
                 'variant B', 'not a documentation-only', 'not reported as an unconditional Exit 0'):
        require(term in notes, 'release notes boundary absent: ' + term)


def authorities(product, receipt, commit):
    authority = read(product / 'config/c2-v210-public-build-authority.json')
    clean = read(receipt)
    selected = read(product / authority['candidate_manifest_path'])
    require(clean['format'] == 'lisp65-v210-public-clean-build-resumed-v1' and clean['status'] == 'PASS',
            'two-reproduction receipt not accepted format')
    require(clean['second_compilation_commit'] == commit and
            clean['first_product_rebuilds'] == 0 and clean['public_writes'] == 0,
            'reproduction identity/accounting drift')
    require(authority['release'] == RELEASE and authority['selected_variant'] == VARIANT and
            selected['format'] == 'lisp65-v2.1-public-selected-product-v1' and
            selected['status'] == 'passed-public-source-selected-v2.1-renderer-f011-native' and
            selected['artifact_count'] == 19 and selected['artifact_set_sha256'] ==
            authority['sealed_product_artifact_set_sha256'], 'selected renderer world drift')
    rows = selected['artifacts']
    require(len(rows) == 19 and {r['role'] for r in rows} == set(BASE.ROLE_PATHS), '19-role population drift')
    for side in ('first', 'second'):
        require(clean[side]['raw_pair'] == authority['raw_pair'], 'raw renderer pair drift: ' + side)
        require(sorted(clean[side]['artifacts'], key=lambda r:r['role']) ==
                sorted([{k:r[k] for k in ('role','name','bytes','sha256')} for r in rows], key=lambda r:r['role']),
                'role reproduction drift: ' + side)
    for row in rows:
        path = product / row['path']
        require(path.is_file() and not path.is_symlink() and record(path) ==
                {k:row[k] for k in ('bytes','sha256')} ==
                {k:authority['sealed_roles'][row['role']][k] for k in ('bytes','sha256')},
                'artifact bytes drift: '+row['role'])
    return authority, clean, selected


def prepare(product, receipt, output, source_repository, amendment_path):
    product = product.resolve()
    source_repository = source_repository.resolve()
    compiled_commit = git(product, 'rev-parse', 'HEAD')
    commit = git(source_repository, 'rev-parse', 'HEAD')
    require(not git(product, 'status', '--porcelain', '--untracked-files=no'), 'selected clean-2 source dirty')
    require(not git(source_repository, 'status', '--porcelain', '--untracked-files=no'), 'source archive checkout dirty')
    authority, clean, selected = authorities(product, receipt, compiled_commit)
    amendment = read(amendment_path)
    require(amendment['status']=='PASS' and amendment['route']=='C' and
            amendment['before_commit']==compiled_commit and amendment['after_commit']==commit and
            amendment['reproduction_receipt']==record(receipt), 'metadata amendment identity drift')
    changed='config/c2-v210-public-build-authority.json'
    require(git(source_repository,'diff','--name-only',compiled_commit,commit)==changed,
            'another source change rides on metadata correction')
    corrected=read(source_repository/changed)
    require({k:v for k,v in corrected.items() if k!='selected_media_sha256'} ==
            {k:v for k,v in authority.items() if k!='selected_media_sha256'} and
            corrected['selected_media_sha256']==authority['sealed_roles']['product-d81']['sha256'],
            'metadata amendment changes another field or wrong medium')
    authority=corrected
    BASE.TOP = BASE.COMMON.TOP = TOP
    BASE.COMMON.SOURCE_EPOCH = 1788739200  # fixed 2026-09-07 UTC; not wall-clock time
    output.mkdir(parents=True, exist_ok=True)
    require(not any(output.iterdir()), 'output already populated; check existing assets, do not overwrite')
    projection = amendment['source_projection']
    entries = BASE.source_entries(source_repository, commit, {
        'public_source_tree_sha256': projection['tree_sha256'],
        'public_source_manifest_sha256': projection['manifest_sha256']})
    blobs = EXPORT.commit_blobs(source_repository, commit)
    export = EXPORT.audit_export(blobs)
    export['mutations'] = EXPORT.selftest()
    # Public receipt is an explicit projection, not a rewritten original receipt.
    public_clean = {
        'format': 'lisp65-v210-release-reproduction-projection-v1', 'status': 'PASS',
        'source_commit': commit, 'original_receipt': record(receipt),
        'first_compilation_commit': clean['first_compilation_commit'],
        'second_compilation_commit': compiled_commit,
        'first_source_projection': clean['first']['source_projection'],
        'second_source_projection': clean['second']['source_projection'],
        'archive_source_projection': projection,
        'metadata_only_successor': {k:amendment[k] for k in
            ('authorization','before_commit','after_commit','only_changed_path','only_changed_field',
             'before_authority_sha256','after_authority_sha256','before_field','after_field','claim')},
        'metadata_amendment_receipt':record(amendment_path),
        'first_raw_pair': clean['first']['raw_pair'], 'second_raw_pair': clean['second']['raw_pair'],
        'artifacts': clean['second']['artifacts'],
        'artifact_set_sha256': selected['artifact_set_sha256'],
        'consumer_preflight': clean['consumer_preflight'],
        'claim': clean['claim'], 'first_product_rebuilds': 0,
        'accounting': {'seed_WPLTO':2,'final_C_LTO':2,'product_links':2,'third_attempt':False},
        'release_card_budget_consumption': False,
    }
    device_path = ROOT / ('tests/bytecode/dialect-v2/evidence/architecture-blocks/'
                          'v2.1-renderer-native-device-session-receipt.json')
    device = read(device_path)
    require(device['medium']['sha256'] == authority['selected_media_sha256'] and
            device['D5']['free'] == {'slots':107,'name_bytes':1467}, 'device medium/capacity drift')
    for role in ('elf','prg'):
        require({k:device['pair'][role][k] for k in ('bytes','sha256')} == authority['raw_pair'][role.upper()],
                'device pair identity drift')
    public_device = {'format':'lisp65-v210-device-public-projection-v1',
        'original_receipt':record(device_path),'session_authority':device['authority'],
        'ship_authority':'77859cc0', 'raw_pair':authority['raw_pair'],
        'medium':{k:device['medium'][k] for k in ('bytes','sha256')},
        'D5':device['D5'],'observed_frames':device['observed_frames'],
        'claim_limits':device['claim_limits'], 'evidence_classes':device['evidence_classes']}
    verifier = BASE.VERIFIER.decode().replace('2.0.0','2.1.0').replace(
        'v2.0-tier1-lossless-native-editor-stripped', VARIANT)
    start = verifier.index('claims = value.get("claims", {})')
    end = verifier.index('print(f"lisp65', start)
    verifier = verifier[:start] + 'if value.get("claims") != '+repr(CLAIMS)+': fail("claim boundary drift")\n' + verifier[end:]
    f = DOCS.facts(source_repository)
    docs_mutations = DOCS.selftest(DOCS.source_texts(source_repository), f)
    manifests, archives, checks = [], [], []
    for suffix in ('a','b'):
        stage = OUT / ('package-stage-'+suffix) / TOP
        require(not stage.exists(), 'stage exists; no silent replacement: '+str(stage))
        stage.mkdir(parents=True)
        rows = []
        for row in selected['artifacts']:
            target = BASE.ROLE_PATHS[row['role']]
            BASE.COMMON.write_file(stage,target,(product/row['path']).read_bytes(),
                                   0o644 if row['role']=='work-d81' else 0o444)
            rows.append({**{k:row[k] for k in ('role','name','bytes','sha256')},'ship_path':target})
        for role, target in DOCS.DOCS.items():
            source = 'docs/releases/2.1.0.md' if role == 'release' else target
            BASE.COMMON.write_file(stage,target,(source_repository/source).read_bytes(),0o444)
        for target, value in [('proof/reproductions.json',public_clean),('proof/device-session.json',public_device)]:
            BASE.COMMON.write_file(stage,target,BASE.canonical(value),0o444)
        BASE.COMMON.write_file(stage,'README-FIRST.txt',readme(selected['artifact_set_sha256']),0o444)
        BASE.COMMON.write_file(stage,'verify.py',verifier.encode(),0o555)
        files = BASE.COMMON.file_inventory(stage)
        manifest = {'format':'lisp65-v2.1.0-release-package-v1','release':RELEASE,
            'status':'prepared-awaiting-owner-publication','release_authorized':False,
            'selected_variant':VARIANT,'source_commit':commit,'prepared_on':'2026-09-07',
            'product':{'artifact_count':19,'artifacts':rows,
                       'artifact_set_sha256':selected['artifact_set_sha256'],
                       'product_build_id':selected['product_build_id'],
                       'profile_build_id':selected['profile_build_id'],
                       'user_headroom':CLAIMS['measured_D5']},
            'clean_build':public_clean,'claims':CLAIMS,'files':files,
            'package_set_sha256':BASE.COMMON.package_set_sha(files)}
        BASE.COMMON.write_file(stage,'manifest.json',BASE.canonical(manifest),0o444)
        texts = {k:(stage/n).read_text() for k,n in DOCS.DOCS.items()}
        docs = DOCS.validate(texts,stage.name,f)
        validate_claims(manifest,(stage/'README-FIRST.txt').read_text(),texts['release'])
        checks.append({'stage':suffix,'offline':BASE.COMMON.verify_product(stage),'docs':docs})
        pa, sa = OUT/f'{TOP}-product-{suffix}.tar.gz', OUT/f'{TOP}-source-{suffix}.tar.gz'
        BASE.COMMON.deterministic_tar_gz(BASE.COMMON.tar_entries_from_directory(stage),pa)
        BASE.COMMON.deterministic_tar_gz(entries,sa)
        BASE.COMMON.verify_product_archive(pa)
        BASE.COMMON.verify_source_archive(sa)
        EXPORT.compare_archive(blobs,EXPORT.archive_blobs(sa.read_bytes(),TOP+'/'),commit)
        manifests.append(manifest); archives.append((pa,sa))
    require(manifests[0]==manifests[1] and all(archives[0][i].read_bytes()==archives[1][i].read_bytes()
            for i in (0,1)), 'independent package staging/packing differs')
    assets = {f'{TOP}.tar.gz':archives[0][0].read_bytes(),f'{TOP}-source.tar.gz':archives[0][1].read_bytes(),
              f'{TOP}-manifest.json':BASE.canonical(manifests[0]),
              f'{TOP}-clean-build-receipt.json':BASE.canonical(public_clean)}
    identities = []
    for name, raw in assets.items():
        path=output/name; path.write_bytes(raw)
        require(path.read_bytes()==raw,'asset readback differs: '+name)
        identities.append({'name':name,**record(path)})
    BASE.COMMON.verify_product_archive(output/f'{TOP}.tar.gz')
    EXPORT.compare_archive(blobs,EXPORT.archive_blobs((output/f'{TOP}-source.tar.gz').read_bytes(),TOP+'/'),commit)
    # Execute sharp package-claim controls independently of document-version controls.
    mutations=[]
    for name in ('Comfort','capacity','old-README','missing-package-correction'):
        m=copy.deepcopy(manifests[0]); t=readme(selected['artifact_set_sha256']).decode(); n=texts['release']
        if name=='Comfort':m['claims']['not_included'].remove('Comfort')
        if name=='capacity':m['claims']['measured_D5']['symbol_slots']=108
        if name=='old-README':t=t.replace('2.1.0 PRODUCT RELEASE','2.0.1 DOCUMENTATION UPDATE')
        if name=='missing-package-correction':n=n.replace('private absolute path metadata','metadata')
        try:validate_claims(m,t,n)
        except ValueError:mutations.append(name)
        else:raise ValueError('claim mutation survived: '+name)
    result={'format':'lisp65-v210-before-publish-v1','status':'PASS; awaiting owner Publish',
        'authorization':'8e47363c','source_commit':commit,'assets':identities,
        'product_double_pack':'byte-identical','source_double_pack':'byte-identical',
        'stage_checks':checks,'docs_mutations':docs_mutations,'claim_mutations':mutations,
        'public_export':export,'source_archive_comparison':'exact 3278 committed files plus derived manifest',
        'reproduction_receipt':record(receipt),'new_product_builds':0,'public_writes':0,
        'required_owner_word':'Publish'}
    (OUT/'v2.1.0-before-publish.json').write_bytes(BASE.canonical(result))
    print(json.dumps({'status':result['status'],'source_commit':commit,'assets':identities},indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check',action='store_true')
    p.add_argument('--product-root',type=Path)
    p.add_argument('--clean-receipt',type=Path)
    p.add_argument('--source-repository',type=Path,required=True)
    p.add_argument('--metadata-amendment',type=Path)
    p.add_argument('--output',type=Path,default=OUT/'publish')
    a=p.parse_args()
    if a.check:
        check(a.output,a.source_repository)
    else:
        require(all((a.product_root,a.clean_receipt,a.metadata_amendment)), 'prepare requires product, clean receipt and amendment')
        prepare(a.product_root,a.clean_receipt,a.output,a.source_repository,a.metadata_amendment)


def check(output, repository):
    expected=read(OUT/'v2.1.0-before-publish.json')
    require({p.name for p in output.iterdir()}=={r['name'] for r in expected['assets']}, 'four-asset population drift')
    for row in expected['assets']:
        require(record(output/row['name'])=={k:row[k] for k in ('bytes','sha256')}, 'asset readback drift: '+row['name'])
    manifest=read(output/f'{TOP}-manifest.json')
    clean=read(output/f'{TOP}-clean-build-receipt.json')
    require(manifest['clean_build']==clean and manifest['source_commit']==expected['source_commit']==clean['source_commit'],
            'cross-asset source or reproduction binding differs')
    BASE.COMMON.TOP=TOP
    blobs=EXPORT.commit_blobs(repository,expected['source_commit'])
    EXPORT.compare_archive(blobs,EXPORT.archive_blobs((output/f'{TOP}-source.tar.gz').read_bytes(),TOP+'/'),expected['source_commit'])
    source_check=EXPORT.audit_export(blobs)
    checks=[]
    with tempfile.TemporaryDirectory(prefix='lisp65-v210-final-readback-') as raw:
        with tarfile.open(output/f'{TOP}.tar.gz') as archive:
            # This locally generated, SHA-checked archive binds read-only modes.
            # Python's data filter adds owner-write permission and would alter
            # the very mode witness being checked. Match the established gate.
            archive.extractall(raw,filter='fully_trusted')
        stage=Path(raw)/TOP
        require(read(stage/'manifest.json')==manifest, 'embedded manifest differs from asset')
        checks.append(BASE.COMMON.verify_product(stage))
        texts={k:(stage/n).read_text() for k,n in DOCS.DOCS.items()}
        DOCS.validate(texts,TOP,DOCS.facts(repository))
        validate_claims(manifest,(stage/'README-FIRST.txt').read_text(),texts['release'])
        # Corrupt only the temporary extracted copy, not any release asset.
        target=stage/next(r['ship_path'] for r in manifest['product']['artifacts'] if r['role']=='c2-resident-prg')
        original=target.read_bytes();target.chmod(0o644)
        target.write_bytes(original[:-1]+bytes([original[-1]^1]))
        run=subprocess.run(['python3','verify.py'],cwd=stage,capture_output=True,text=True)
        require(run.returncode!=0 and 'product drift: c2-resident-prg' in run.stderr, 'artifact mutation survived offline verifier')
        checks.append('rejected extracted product byte mutation')
    result={'status':'PASS','assets':expected['assets'],'source_commit':expected['source_commit'],
            'checks':checks,'public_export_files':source_check.get('file_count',len(blobs)),
            'source_comparison':'exact committed population and bytes plus derived manifest',
            'public_writes':0,'required_owner_word':'Publish'}
    (OUT/'v2.1.0-final-readback.json').write_bytes(BASE.canonical(result))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
