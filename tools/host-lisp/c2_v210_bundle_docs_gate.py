#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Check the actual 2.1 bundle documents against the selected source world."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess

from c2_v201_bundle_docs_gate import inline_names, named_absence_subjects

DOCS={'release':'docs/release-notes.md','guide':'docs/user-guide.md',
      'reference':'docs/language-reference.md','issues':'docs/known-issues.md',
      'keymap':'docs/generated/ide-keymap.md'}
TOP='lisp65-2.1.0'
RESIDENT_SOURCES=('src/eval.c','src/vm.c','src/interrupt.c')
RELEASE_DOC_COMMIT='f61ee9e00e644e797a9567fab7d96d4ea00bb27e'


def resident_sources(root, authority, expected):
    """Released native projection, not the current development product.

    A source export has no private Git history: its actual files must match.
    In the working repository use the frozen commit selected by the public
    release authority. Missing Git objects are errors, never a live fallback.
    """
    commit=authority['frozen_native_source_commit']
    require(re.fullmatch(r'[0-9a-f]{40}',commit),'invalid frozen source commit')
    exported={name:(root/name).read_bytes() for name in RESIDENT_SOURCES}
    matches=all(hashlib.sha256(raw).hexdigest()==expected[name] for name,raw in exported.items())
    source={}
    for name in RESIDENT_SOURCES:
        if not matches and (root/'.git').exists():
            source[name]=subprocess.check_output(['git','show',commit+':'+name],cwd=root)
        else:
            source[name]=exported[name]
    def check(values):
        require(set(values)==set(RESIDENT_SOURCES),'resident source population drift')
        for name,raw in values.items():
            require(hashlib.sha256(raw).hexdigest()==expected[name],
                    'not the released renderer source world: '+name)
    check(source)
    rejected=[]
    for name in RESIDENT_SOURCES:
        for mutation in ('byte-change','omission'):
            trial=dict(source)
            if mutation=='byte-change':trial[name]+=b'\n'
            else:del trial[name]
            try:check(trial)
            except ValueError:rejected.append(name+':'+mutation)
            else:raise ValueError('resident source mutation survived: '+name)
    return source,{'commit':commit,'mode':'exported-files' if matches else 'frozen-git-projection',
        'bindings':[{'path':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
                    for name,raw in source.items()], 'mutations_rejected':rejected}


def require(ok, message):
    if not ok: raise ValueError(message)


def facts(root):
    bindings=[]
    def read(name):
        p=root/name; raw=p.read_bytes()
        bindings.append({'path':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
        return raw.decode()
    def load(name):return json.loads(read(name))
    meta=load('config/c2-v210-document-metadata.json')
    require(meta['delivery']=='host metadata only; requires medium projection','metadata delivery claim drift')
    names={r['name'] for r in meta['records']}
    require(len(names)==len(meta['records']),'metadata population ambiguous')
    authority=load('config/c2-v210-public-build-authority.json')
    require(authority['release']=='v2.1.0','wrong product world')
    profile=read('config/c2-v210-renderer-profile.txt')
    expected=dict(line.removeprefix('input_sha256=').rsplit(':',1)
                  for line in profile.splitlines() if line.startswith('input_sha256='))
    sources,source_era=resident_sources(root,authority,expected)
    evaluator=sources['src/eval.c'].decode()
    base='config/c2-v200-public-plane/'
    resident=load(base+'static-plane/stdlib-p0.manifest.json')
    delivered=set(resident['functions'])
    for p in sorted((root/base/'sources').glob('*.lisp')):
        delivered.update(re.findall(r'^\(defmacro\s+([^\s()]+)',read(p.relative_to(root).as_posix()),re.M))
    require(authority['delivered_library_roles']==['ide','idex','m65d'],'library role population drift')
    for role in authority['delivered_library_roles']:
        image=root/base/'external-images'/(role+'.ext.bin')
        target=authority['sealed_roles']['library-'+role]
        require(len(image.read_bytes())==target['bytes'] and hashlib.sha256(image.read_bytes()).hexdigest()==target['sha256'],
                'library bytes differ: '+role)
        delivered.update(load(base+'external-manifests/libs-'+role+'.manifest.json')['functions'])
    registry=load('config/v2-native-function-registry.json')
    delivered.update(r['name'] for r in registry['entries'])
    delivered.update(re.findall(r'WORKBENCH_BOOTNAME\([^,]+,\s*"([^"]+)"\)',evaluator))
    runtime=read('config/runtime-core.mk')
    match=re.search(r'^RUNTIME_CORE_ENTRY\s*:?=\s*(\S+)',runtime,re.M)
    require(match,'runtime entry authority absent');delivered.add(match[1])
    errors=load('config/error-code-contract.json')['codes']
    keys=load('config/v11-l-lite-keymap.json')['bindings']
    examples=load('config/ship-builder-v1.json')['gates']['samples']
    for name in examples:
        read('examples/ship/'+name+'/project.l65p')
    tier=read(base+'sources/24-domain-tier1.lisp')
    tier_names=[n for n in re.findall(r'^\(defun\s+([^\s()]+)',tier,re.M) if not n.startswith('%')]
    return {'names':sorted(names),'outside':sorted(names-delivered),
        'errors':len(errors),'active_errors':sum(r['presentation']=='active-text' for r in errors),
        'exact_arities':sum(r['arity']['status']=='exact-code-object' for r in meta['records']),
        'unresolved_arities':sum(r['arity']['status']=='unresolved' for r in meta['records']),
        'key_bindings':len(keys),'examples':examples,'tier1_names':tier_names,
        'D5':authority['measured_capacity'],'bindings':bindings,'resident_source_era':source_era}


def validate(texts, top, f):
    require(set(texts)==set(DOCS) and top==TOP,'document population or archive root drift')
    for role,marker in {'release':'# WORKBENCH 2.1.0','guide':'# lisp65 2.1.0 User Guide',
        'reference':'**lisp65 2.1.0**','issues':'lisp65 2.1.0','keymap':'bundled with lisp65 2.1.0'}.items():
        require(marker in texts[role],'document version drift: '+role)
    guide=texts['guide'];release=texts['release'];reference=texts['reference'];issues=texts['issues']
    require('`'+TOP+'`' in guide,'extraction directory drift')
    names=set(f['names']); documented=inline_names(guide+'\n'+reference)
    require(names<=documented,'metadata names undocumented: '+repr(sorted(names-documented)))
    start=reference.index('### Names outside the 2.1.0 medium')
    end=reference.index('\n## List-domain errors',start)
    absence='\n'.join(line for line in reference[start:end].splitlines()
                      if line.startswith('- ') or line.startswith('  `'))
    start=issues.index('| Package | Names it would publish |');end=issues.index('\n\n',start)
    outside=inline_names(absence+'\n'+issues[start:end]) & names
    require(outside==set(f['outside']),'medium absence population differs')
    claimed=set().union(*(named_absence_subjects(t) for t in texts.values())) & names
    require(claimed<=outside,'delivered name described as absent')
    expected=[f"maps {f['errors']} stable error codes",f"{f['active_errors']} codes reachable",
        f"exact arity for {f['exact_arities']} of its {len(names)} entries; {f['unresolved_arities']}",
        f"contains {f['key_bindings']} bindings",
        f"{f['D5']['free_symbols']} free symbol slots and {f['D5']['free_name_bytes']:,} free name bytes"]
    require(all(s in guide for s in expected),'derived document number drift')
    require(len(f['examples'])==5 and 'The five supplied examples' in guide
            and all('`'+n+'`' in guide for n in f['examples']),'example population drift')
    require('historical 2.0.0 acceptance' in guide and 'raw = seen = stored = taken = 138' in guide,
            'historical capture attribution missing')
    require('138' not in release,'historical capture promoted into current release')
    require(f"{f['D5']['free_symbols']} symbol slots and {f['D5']['free_name_bytes']:,} name bytes" in release,
            'release measured D5 drift')
    require('WORKBENCH 2.0.0' in release and '**not included**' in release
            and 'Comfort, its trampoline, and the hardware-stack floor' in release,
            'release product boundary drift')
    return {'status':'PASS','version':'2.1.0','archive_root':top,
            'documented_names':len(names),'outside_medium':sorted(outside),'number_pins':f}


def source_texts(root):
    return {k:(root/('docs/releases/2.1.0.md' if k=='release' else n)).read_text() for k,n in DOCS.items()}


def historical_texts(root):
    """Explicit private regression fixture; never used by export/bundle mode."""
    paths={k:('docs/releases/2.1.0.md' if k=='release' else n) for k,n in DOCS.items()}
    sealed={k:subprocess.check_output(
        ['git','show',RELEASE_DOC_COMMIT+':'+n],cwd=root) for k,n in paths.items()}
    expected={k:hashlib.sha256(raw).hexdigest() for k,raw in sealed.items()}
    def check(values):
        require(set(values)==set(expected),'historical document population drift')
        for k,raw in values.items():
            require(hashlib.sha256(raw).hexdigest()==expected[k],
                    'historical document escaped release era: '+k)
    check(sealed)
    trial=dict(sealed);trial['guide']=(root/DOCS['guide']).read_bytes()
    # Exercise a divergent live draft even on a checkout of the release itself.
    if trial['guide']==sealed['guide']:trial['guide']+=b'\nLIVE-DRAFT-MUTATION\n'
    try:check(trial)
    except ValueError:pass
    else:raise ValueError('live guide mutation survived historical binding')
    return {k:raw.decode() for k,raw in sealed.items()}, {
        'commit':RELEASE_DOC_COMMIT,'bindings':[
            {'path':paths[k],'bytes':len(raw),'sha256':expected[k]} for k,raw in sealed.items()],
        'mutations_rejected':['historical-gate-consumes-live-guide']}


def selftest(texts, f):
    validate(texts,TOP,f)
    cases=[('stale-version','guide','# lisp65 2.1.0','# lisp65 2.0.1'),
           ('wrong-directory','guide','`lisp65-2.1.0`','`lisp65-wrong`'),
           ('name-omitted','reference','`runtime-main`','runtime-main'),
           ('absence-lie','issues','| `buffer` |','| `car` | `car` |\n| `buffer` |'),
           ('error-count','guide','maps 63 stable','maps 62 stable'),
           ('arity-count','guide','exact arity for 103','exact arity for 102'),
           ('keymap-count','guide','contains 41 bindings','contains 40 bindings'),
           ('D5-count','release','107 symbol slots','106 symbol slots'),
           ('capture-era','guide','historical 2.0.0 acceptance','current acceptance')]
    rejected=[]
    for name,role,old,new in cases:
        trial=copy.deepcopy(texts);require(old in trial[role],'mutation fixture absent: '+name)
        trial[role]=trial[role].replace(old,new)
        try:validate(trial,TOP,f)
        except ValueError:rejected.append(name)
        else:raise ValueError('mutation survived: '+name)
    try:validate(texts,'lisp65-2.0.1',f)
    except ValueError:rejected.append('archive-root')
    else:raise ValueError('archive root mutation survived')
    return rejected


def main():
    p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,default=Path.cwd())
    p.add_argument('--bundle',type=Path);p.add_argument('--receipt',type=Path)
    p.add_argument('--historical-release-docs',action='store_true');a=p.parse_args()
    require(not (a.historical_release_docs and a.bundle),'historical mode cannot certify an actual bundle')
    f=facts(a.source_root)
    era=None
    if a.historical_release_docs:texts,era=historical_texts(a.source_root)
    else:texts=source_texts(a.source_root)
    mutations=selftest(texts,f)
    if a.bundle:
        texts={k:(a.bundle/n).read_text() for k,n in DOCS.items()}
    result=validate(texts,a.bundle.name if a.bundle else TOP,f);result['mutations_rejected']=mutations
    if era:result['historical_documents']=era
    if a.receipt:a.receipt.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print('PASS: bundle docs 2.1.0; names=%d outside=%d mutations=%d' %
          (result['documented_names'],len(f['outside']),len(mutations)))


if __name__=='__main__':main()
