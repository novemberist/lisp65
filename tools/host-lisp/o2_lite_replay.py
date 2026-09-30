#!/usr/bin/env python3
"""r6 Final replay preparation and media-only adapter. Never invokes Seed."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import sys
from o2_lite_final import Driver, encoded, require, save

ROOT = Path(__file__).resolve().parents[2]
SEED = 'build/o2-lite-product-r6'
NATIVE = 'build/o2-lite-r4-slots-preflight/native'
PREP = 'build/o2-lite-final-prep-r6b'
FINAL = 'build/o2-lite-final-r1'


def write_guard(out,event,args):
    """Audit inherited media helpers' filesystem mutations before they occur."""
    if event == 'open' and isinstance(args[0], (str, bytes)):
        path = Path(os.fsdecode(args[0])).resolve()
        if args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            require(path.is_relative_to(out), 'media write outside Final: '+str(path))
    if event in ('os.remove', 'os.mkdir', 'os.rmdir', 'os.chmod', 'os.utime', 'os.truncate'):
        if not isinstance(args[0], int):
            path=Path(args[0])
            fd=args[-1] if len(args)>1 and isinstance(args[-1],int) else -1
            if not path.is_absolute() and fd>=0 and event!='os.truncate':
                path=Path(os.readlink('/proc/self/fd/'+str(fd)))/path
            require(path.resolve().is_relative_to(out), 'media mutation outside Final')
    if event in ('os.rename', 'os.link', 'os.symlink'):
        require(all(Path(p).resolve().is_relative_to(out) for p in args[:2]), 'media move outside Final')


def selftest():
    import subprocess
    from unittest.mock import patch
    with patch.object(subprocess,'run',side_effect=AssertionError('offline only')), patch.object(subprocess,'check_output',side_effect=AssertionError('offline only')):
        d=Driver(SEED,'build/offline-source-never-admitted',PREP+'/replay.json','0'*64,FINAL)
        d.replay_sha256=d.bind(d.replay)['sha256']
        d.source=lambda:dict(head='SYNTHETIC, NOT SEALED',sealed_run=d.run,source={},source_log={})
        d.git=lambda *a:d.replay if a[0]=='ls-files' else ''
        a=d.admit()
        require(len(a['commands'])==75 and len(a['pairs'])==4,'replay population')
        write_guard(ROOT/FINAL,'open',(str(ROOT/FINAL/'media/test'), 'w',os.O_WRONLY))
        rejected=[]
        for event,args in [('open',(str(ROOT/SEED/'test'),'w',os.O_WRONLY)),
                           ('os.remove',(str(ROOT/SEED/'test'),)),
                           ('os.rename',(str(ROOT/FINAL/'test'),str(ROOT/SEED/'test')))]:
            try:write_guard(ROOT/FINAL,event,args)
            except ValueError:rejected.append(event)
            else:raise AssertionError('write escaped Final')
        return dict(status='PASS',actual_r6_input_bindings=len(a['input_bindings']),native_commands=75,
                    write_isolation_negative_controls=rejected,source_admission='MOCKED; reviewer sealed check still required',
                    product_commands=0,git_commands=0)


def media(out):
    out=ROOT/out
    require(out==ROOT/FINAL,'unexpected Final output')
    sys.addaudithook(lambda event,args:write_guard(out,event,args))
    import o2_lite_r6_product as P
    import strings_seed_producer as S
    for suffix in ('','.elf','.lto.o'):
        name='wplto/resident-island-seed.prg'+suffix
        require((out/name).read_bytes()==(ROOT/SEED/name).read_bytes(),'replayed native drift')
    previous=S.load(P.BASE/'complete.json')
    result,*_=P.media(out/'media',S.checked(previous['medium']))
    require((out/'media/o2lite.d81').read_bytes()==(ROOT/SEED/'media-r6/o2lite.d81').read_bytes(),'Final D81 differs')
    save(out/'media/readback.json',result)


def prepare():
    """Freeze conservative closure, plus explicit historical-reference copies.

    This inventories files only. Review the resulting recipe before committing.
    It does not compile, link, emit media, or invoke an emulator.
    """
    from o2_lite_final import bindings
    d = Driver(SEED, 'build/o2-lite-check-source-r1', PREP+'/replay.json', '0'*64, FINAL)
    dest = ROOT/PREP
    dest.mkdir(exist_ok=False)
    commands = d.load(NATIVE+'/command-proof.json')['commands']
    # Native output references include exactly two linker option payloads.
    commands = d.rebase(commands, {'build/o2-lite-product-r4/wplto':FINAL+'/wplto'}, allowed_seed='build/o2-lite-product-r4')
    # Store the recipe in Seed coordinates; Final performs the same reversible projection.
    commands = [[x.replace(FINAL+'/wplto', SEED+'/wplto') for x in c] for c in commands]
    save(dest/'commands.json', dict(commands=commands, inherited=d.bind(NATIVE+'/command-proof.json')))
    media_commands = [[str(Path(sys.executable).resolve()), '-B', 'tools/host-lisp/o2_lite_replay.py', 'media', FINAL]]
    save(dest/'media-commands.json',dict(commands=media_commands))
    # Persisted r6 all-file readback is rechecked, not invented from status alone.
    import d81_persistence_fault as D
    a=(ROOT/SEED/'media-r6/o2lite.d81').read_bytes()
    b=(ROOT/'build/o2-lite-product-r4/media-r4/o2lite.d81').read_bytes()
    D.validate_bam(a)
    recorded=d.load(SEED+'/media.json')
    files=D.visible_files(a)
    require(recorded['status']=='PASS' and recorded['unclassified_bytes']==0,'r6 readback status')
    require({n.decode():dict(bytes=len(v),sha256=__import__('hashlib').sha256(v).hexdigest(),unchanged=v==D.visible_files(b)[n]) for n,v in files.items()}==recorded['files'],'r6 file readback')
    save(dest/'readback.json',dict(status='PASS',every_file_read_back=True,unclassified_bytes=0,
                                  medium=d.bind(SEED+'/media-r6/o2lite.d81')))
    rows = {}
    # Conservatively pin full local Python helper population and product inputs;
    # generated native include trees and media authorities are pinned as well.
    roots = ['tools/host-lisp', 'lib', 'src', 'config', 'scripts',
             'tools/llvm-mos/lib', 'tools/llvm-mos/mos-platform',
             'build/nested-error-recovery-seed-medium-r1/packed', 'build/multiline-lite-r2', NATIVE,
             'build/o2-lite-r4-slots-preflight/planes', 'build/o2-lite-product-r4', 'build/o2-lite-product-r5', SEED,
             'build/strings-final-r1', 'build/strings-r7/seed/plane/candidate']
    for root in roots:
        for p in sorted((ROOT/root).rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc' and p != ROOT/'config/document-index.json':
                name=str(p.relative_to(ROOT)); rows[name]=d.bind(name)
    # Follow every JSON binding, retaining conflicting historical references via
    # byte-exact snapshots. No reference is silently rebound to current bytes.
    historical = {}
    pending = [rows[p] for p in (SEED+'/seed.json', 'build/o2-lite-product-r4/complete.json', NATIVE+'/command-ready.json', NATIVE+'/include-closure.json')]
    seen = set()
    while pending:
        row=pending.pop()
        key=(row['path'],row['sha256'])
        if key in seen: continue
        seen.add(key)
        value=json.loads((ROOT/row['path']).read_text())
        for ref in bindings(value):
            name=ref['path']
            if Path(name).is_absolute():
                require(Path(name).is_relative_to(ROOT), 'external receipt reference: '+name)
                name=str(Path(name).relative_to(ROOT))
            if not (ROOT/name).is_file():
                raise ValueError('missing reference: '+name)
            actual=d.bind(name)
            if actual['sha256'] != ref['sha256']:
                copies=[r for r in rows.values() if r['sha256']==ref['sha256'] and r['bytes']==ref.get('bytes',r['bytes'])]
                require(copies, 'no exact historical snapshot: '+name)
                historical[name+'@'+ref['sha256']]=copies[0]
                continue
            rows[name]=actual
            if name.endswith('.json'):pending.append(actual)
    for name in ('commands.json','media-commands.json','readback.json'):
        rows[PREP+'/'+name]=d.bind(PREP+'/'+name)
    for name in ('build/o2-lite-device-r1/tools/l252.py','build/lite-throughput-probe-r1/probe4.py'):
        rows[name]=d.bind(name)
    tools=[]
    for name in sorted({c[0] for c in commands+media_commands} | {str(ROOT/'tools/llvm-mos/bin/llvm-readobj'),str(ROOT/'tools/llvm-mos/bin/llvm-objdump'),str(ROOT/'tools/llvm-mos/bin/llvm-objcopy'),str(ROOT/'tools/llvm-mos/bin/ld.lld'),str(Path(shutil.which('cc')).resolve()),'/usr/bin/setarch'}):
        p=Path(name); raw=p.read_bytes()
        import hashlib
        tools.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    arts={role:d.bind(SEED+'/'+name) for role,name in [('ELF','wplto/resident-island-seed.prg.elf'),('PRG','wplto/resident-island-seed.prg'),('LTO','wplto/resident-island-seed.prg.lto.o'),('D81','media-r6/o2lite.d81')]}
    manifest=dict(format='o2-lite-replay-r6',seed_dir=SEED,closure_complete=True,
        seed_receipt=d.bind(SEED+'/seed.json'),inputs=list(rows.values()),historical_references=historical,
        consumed_inputs=[p for p in rows if p.startswith(('tools/host-lisp/','lib/','src/','config/',NATIVE+'/candidate-inputs/',NATIVE+'/plane/','scripts/','tools/llvm-mos/lib/','tools/llvm-mos/mos-platform/','build/nested-error-recovery-seed-medium-r1/packed/','build/multiline-lite-r2/'))],
        non_product_deltas=[],receipts=[d.bind(SEED+'/complete.json'),d.bind('build/o2-lite-product-r4/complete.json')],
        commands=commands,commands_receipt=d.bind(PREP+'/commands.json'),tools=tools,
        media_commands=media_commands,media_commands_receipt=d.bind(PREP+'/media-commands.json'),
        output_prefixes={SEED+'/wplto':FINAL+'/wplto',SEED+'/media-r6':FINAL+'/media'},
        artifacts=arts,gates=[d.bind(SEED+'/'+p) for p in ('seed.json','media.json','runtime-identity.json','host/receipt.json')],
        media_readback=PREP+'/readback.json',final_media_readback=FINAL+'/media/readback.json',
        native_authority=d.bind(NATIVE+'/command-proof.json'),producer=d.bind('tools/host-lisp/o2_lite_r4_product.py'),
        r6_producer=d.bind('tools/host-lisp/o2_lite_r6_product.py'),
        audit='Conservative full trees plus recursive receipt bindings. r4 native replay; r6 re-emits the repaired library with identical native artifacts. Media adapter writes only private Final acceptance and media trees.')
    save(dest/'replay.json',manifest)
    return d.bind(PREP+'/replay.json')


if __name__=='__main__':
    require(__debug__ and os.environ.get('PYTHONDONTWRITEBYTECODE')=='1','assertions/bytecode policy')
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','media','selftest']);p.add_argument('out',nargs='?')
    a=p.parse_args()
    print(json.dumps(prepare() if a.mode=='prepare' else selftest() if a.mode=='selftest' else media(a.out),indent=2))
