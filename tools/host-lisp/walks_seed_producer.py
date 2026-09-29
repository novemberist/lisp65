#!/usr/bin/env python3
"""Write-once editor-walks producer. No implicit retry or Final.

command-probe is budget-free and requires committed, clean authority.
seed emits the candidate and replays exactly 75 commands (one product link).
price, inventory and media are separate artifact-only acceptance stages.
--selftest uses synthetic inputs only and never invokes product commands.
"""
import argparse
import copy
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
AUTH = 'c8c20a64'
HERE = ROOT / 'build/walks-r3/seed'
BUILD = ROOT / 'build/walks-product-r1'
FINAL = ROOT / 'build/backspace-final-r1'
RECIPE = FINAL / 'final-invocation.json'
PLANE = ROOT / 'build/backspace-product-r1/plane/candidate'
KEYMAP = ROOT / 'lib/ide-keymap-generated.lisp'
import walks_successor_20260928 as WALKS
BASE_MEDIA_SHA = 'a2872fbd8aa53690da0fb7a7281bd2746497589a036c27fa3d7f302a8cafc445'
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')
PRIORITY = ['nice', '-n', '18', 'ionice', '-c3']


# Plane growth bound (reviewer decision 2026-09-28): +400 aggregate Bank-2 bytes
# for the measured +374 (CODE.BIN +207, SHELF.BIN +167). Native budget is
# zero except the exact, separately proven main shrink below.
PLANE_BOUND = 400

def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def bind(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                bytes=len(raw), sha256=sha(raw))


def checked(row):
    path = ROOT / row['path']
    actual = bind(path)
    assert all(actual[k] == row[k] for k in ('bytes', 'sha256') if k in row), row
    return path.read_bytes()


def load(path):
    return json.loads(Path(path).read_text())


def once(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(raw, str):
        raw = raw.encode()
    if path.exists():
        assert path.read_bytes() == raw, f'write-once mismatch: {path}'
    else:
        path.write_bytes(raw)


def save(path, value):
    once(path, json.dumps(value, indent=2, sort_keys=True) + '\n')


def save_suite(path, value):
    # disk_files order is the virtual D81 directory order, including the
    # historical reserved first slot. Sorting it changes behavioral fixtures.
    once(path, json.dumps(value, indent=2) + '\n')


def git(*args):
    return subprocess.check_output(PRIORITY + ['git', *args], cwd=ROOT, env=ENV).decode().strip()


def run(command, log):
    command = PRIORITY + list(map(str, command))
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('xb') as stream:
        result = subprocess.run(command, cwd=ROOT, env=ENV, stdout=stream,
                                stderr=subprocess.STDOUT)
    assert result.returncode == 0, f'command exit {result.returncode}: {log}'
    return log.read_bytes()


def snapshot(path, rows):
    path = Path(path).resolve()
    row = bind(path)
    target = HERE / 'inputs' / path.relative_to(ROOT)
    once(target, checked(row))
    rows[str(path)] = dict(source=row, restored=bind(target))
    return target


def authority():
    subprocess.run(PRIORITY + ['git', 'merge-base', '--is-ancestor', AUTH, 'HEAD'],
                   cwd=ROOT, env=ENV, check=True)
    assert not git('status', '--porcelain', '--untracked-files=normal'), 'tree must be clean; reviewer must commit preparation first'
    assert git('ls-files', '--error-unmatch', 'tools/host-lisp/walks_seed_producer.py'), 'reviewer must commit producer first'
    allowed = {
        'tools/host-lisp/c2_v16_defstruct_phase_a_walks_20260928.py',
        'config/c2-v16-defstruct-phase-a-receipt-walks-20260928.json',
        'tools/host-lisp/c2_v251_public_authority_walks_20260928.py',
        'config/c2-v251-public-authority-receipt-walks-20260928.json',
        'config/c2-v160-comfort-repl-receipt-walks-20260928.json',
        'config/c2-v160-hybrid-capacity-receipt-walks-20260928.json',
        'config/c2-v160-hybrid-receipt-walks-20260928.json',
        'config/c2-v251-card5-receipt-walks-20260928.json',
        'config/c2-v251-keymap-receipt-walks-20260928.json',
        'config/walks-stdlib-artifacts-receipt-20260928.json',
        'docs/planning/post-2.4.0-plan.md',
        'mk/gates.mk',
        'mk/workbench.mk',
        'tools/host-lisp/c2_v160_comfort_repl_walks_20260928.py',
        'tools/host-lisp/c2_v160_hybrid_capacity_walks_20260928.py',
        'tools/host-lisp/c2_v160_hybrid_walks_20260928.py',
        'tools/host-lisp/c2_v251_card5_walks_20260928.py',
        'tools/host-lisp/c2_v251_keymap_receipt_walks_20260928.py',
        'tools/host-lisp/stdlib_artifacts_walks_20260928.py',
        'tools/host-lisp/walks_seed_producer.py',
        'tools/host-lisp/walks_successor_20260928.py',
    }
    changed = set(git('diff', '--name-only', AUTH, 'HEAD').splitlines())
    # Reviewer device reports and their index rows are documentation, not
    # product authority (added 2026-09-28 after the IDE-exit device session).
    doc_only = {c for c in changed if c.startswith('docs/planning/') and c.endswith('-device-report.md')}
    doc_only |= {'config/document-index.json'} & changed
    assert changed - doc_only <= allowed, ('unreviewed authority drift', sorted(changed - doc_only - allowed))
    # Concurrent device-status documentation is not product authority.
    plan = 'docs/planning/post-2.4.0-plan.md'
    # The rolling plan journal is documentation; seals bind reports and
    # receipts, never the plan (standing rule), so its drift is admitted.
    WALKS.source_proof()
    assert KEYMAP.read_bytes() == subprocess.check_output(
        PRIORITY + ['git','show',AUTH+':lib/ide-keymap-generated.lisp'],cwd=ROOT,env=ENV)


def command_probe():
    authority()
    assert not BUILD.exists(), 'product root already exists'
    assert not HERE.exists(), 'probe receipt root already exists'
    import backspace_final as CLOSED
    from evidence_era import era_blob
    assert era_blob('726c2941','tools/host-lisp/backspace_final.py') == (ROOT/'tools/host-lisp/backspace_final.py').read_bytes(), 'Backspace Final closing authority drift'
    for path,digest in CLOSED.RECEIPTS.items():
        assert sha((ROOT/path).read_bytes()) == digest, ('closed Backspace receipt drift',path)
    final = load(RECIPE)
    identities = load(FINAL/'final-identity.json')
    base_native = {role: row['final'] for role,row in zip(('ELF','LTO','PRG'),identities['artifacts'],strict=True)}
    for row in base_native.values(): checked(row)
    assert base_native['ELF']['sha256'] == BASE_ELF_SHA
    base_media = identities['media'][0]['final']
    assert base_media['sha256'] == BASE_MEDIA_SHA
    checked(base_media)
    old_commands = load(ROOT/final['seed_commands']['path'])['commands']
    original_commands = final['commands']
    expected = [[a.replace('build/backspace-product-r1/wplto/','build/backspace-final-r1/wplto/') for a in c] for c in old_commands]
    assert original_commands == expected and len(expected)==75, 'Final/Seed command chain drift'
    assert any('-DLISP65_C2_BANK2_CODE_LIMIT=60758' in c for c in original_commands), 'frozen static owner capacity absent'
    HERE.mkdir(parents=True)
    old_derived=load(ROOT/'build/backspace-r3/seed/derived-inputs.json')
    input_map={r['path']:r for r in final['input_bindings']}
    selected=old_derived['all_generated']+[old_derived['generated']]
    selected += [r for r in final['input_bindings'] if r['path'].startswith('tools/llvm-mos/')]
    native=[]
    for row in {r['path']:r for r in selected}.values():
        assert input_map[row['path']]==row, ('Final native binding drift',row['path'])
        raw=checked(row)
        target=HERE/'native-inputs'/row['path']
        once(target,raw)
        native.append(dict(source=row, original=row['path'],restored=bind(target)))
    prefix=str((HERE/'native-inputs').relative_to(ROOT))+'/'
    def rebase(a):
        a=a.replace('build/backspace-final-r1/wplto/',str(BUILD.relative_to(ROOT))+'/wplto/')
        for old in ('build/backspace-r3/seed/candidate-inputs/','build/backspace-r3/seed/derived/'):
            a=a.replace(old,prefix+old)
        return a
    commands=[[rebase(a) for a in c] for c in original_commands]
    save(HERE/'baseline-command-proof.json',dict(status='COMMAND PROBE ONLY',commands=commands))
    rows={};manifests=[]
    product=load(PLANE/'product/substitution-artifacts.json')
    assert product==load(ROOT/'build/backspace-r3/seed/plane-price.json')['after_product'], 'accepted plane identity drift'
    for row in product['manifests']:
        checked(row)
        path=ROOT/row['path'];target=snapshot(path,rows);manifests.append(str(target))
        m=load(path);blob=Path(m['blob'])
        assert sha(blob.read_bytes())==m['blob_sha256']
        snapshot(blob,rows)
    stdlib=load(manifests[0]);visited={}
    def suite(path):
        path=Path(path).resolve()
        if str(path) in visited:return
        target=snapshot(path,rows);value=load(target);visited[str(path)]=str(target)
        for source in value.get('sources',[]):snapshot(ROOT/source,rows)
        for key in ('resident_suites','cases_from_suites','extends'):
            deps=value.get(key,[])
            if isinstance(deps,str):deps=[deps]
            for dep in deps:suite(ROOT/dep)
        if value.get('resident_suite'):suite(ROOT/value['resident_suite'])
    suite(stdlib['suite'])
    editors=[p for p in stdlib['sources'] if p.endswith('/projected-product-editor.lisp')]
    assert len(editors)==1
    old_editor=editors[0]
    projected=WALKS.transform(Path(old_editor).read_text())
    from v2_workbench_codemod import _top_level_forms
    from bytecode_p0_stdlib import C
    def cut(text):
        return next(C.parse_one(text[a:b]) for a,b in _top_level_forms(text) if text[a:b].startswith('(defun %rl-cut '))
    assert cut(projected)==cut((ROOT/WALKS.SOURCE).read_text()), 'product cut differs from authority'
    once(HERE/'projected-product-editor.lisp',projected)
    for path in (RECIPE,FINAL/'final-identity.json',PLANE/'product/substitution-artifacts.json',KEYMAP,ROOT/WALKS.SOURCE):snapshot(path,rows)
    for name in ('CODE.BIN','SHELF.BIN','C2D.BIN'):snapshot(PLANE/name,rows)
    for path in (ROOT/'build/nested-error-recovery-seed-medium-r1/packed').iterdir():
        if path.is_file() and path.suffix in ('.json','.c','.h'):snapshot(path,rows)
    for path in sorted((FINAL/'media').rglob('*')):
        if path.is_file():snapshot(path,rows)
    packages=load(FINAL/'media/runtime-receipt.json')['packages']
    for package in packages:
        checked(package['manifest']);path=ROOT/package['manifest']['path'];snapshot(path,rows)
        m=load(path);snapshot(ROOT/m['blob'],rows)
    media=load(ROOT/'build/backspace-r3/seed/media.json')
    import d81_persistence_fault as D
    files=D.visible_files(checked(base_media))
    assert {n.decode():dict(bytes=len(v),sha256=sha(v)) for n,v in files.items()}==media['files']
    preflight_path=ROOT/'config/walks-stdlib-artifacts-receipt-20260928.json'
    preflight=load(preflight_path)
    assert preflight['source']['authority']==AUTH
    checked(preflight['source']['source'])
    ready=dict(preflight_plane=bind(preflight_path),plane_admission=preflight['current']['plane']['price_status'],status='PASS: COMMAND PROBE ONLY',authority=AUTH,execution_head=git('rev-parse','HEAD'),
        driver=bind(Path(__file__)),base_native=base_native,base_media=base_media,native=native,
        closure=list(rows.values()),manifests=manifests,suites=visited,stdlib_suite=stdlib['suite'],
        old_editor=old_editor,projected_editor=bind(HERE/'projected-product-editor.lisp'),
        media_authority=dict(medium=base_media,files=media['files'],packages=packages,builder=bind(Path(__file__))),
        tools=[bind(p) for p in sorted((ROOT/'tools/host-lisp').glob('*.py')) if p!=Path(__file__).resolve()],
        commands=bind(HERE/'baseline-command-proof.json'),
        reach=dict(stdlib_header='regenerate manifest-derived blob/literal counts; preserve every ordinal and ABI field',
                   static_code_header='regenerate extent from paired six-image emission',
                   native=['product build ID','shelf length','directory CRC16 tables','static code bytes','stdlib blob bytes']),
        budget=dict(seed=0,final=0,product_link=0))
    save(HERE/'command-ready.json',ready)
    return dict(status=ready['status'],native_inputs=len(native),frozen_commands=len(commands),budget=ready['budget'])


def verify_ready(*, acceptance=False):
    ready = load(HERE / 'command-ready.json')
    authority()
    assert ready['authority'] == AUTH
    verify_seed_driver(ready['driver'], acceptance=acceptance)
    checked(ready['projected_editor'])
    for row in ready['native']:
        checked(row['restored'])
    for row in ready['closure']:
        checked(row['source'])
        checked(row['restored'])
    for row in ready['tools']:
        checked(row)
    for row in ready['base_native'].values():
        checked(row)
    checked(ready['base_media'])
    checked(ready['commands'])
    checked(ready['preflight_plane'])
    return ready


# The linked Seed keeps its original driver receipt after reviewer repair.
SEED_DRIVER_COMMIT = 'a148be098c62280cc8eadd212e2d163e36a8aa6b'


def verify_seed_driver(row, *, acceptance):
    if acceptance:
        assert row['path'] == 'tools/host-lisp/walks_seed_producer.py'
        frozen = subprocess.check_output(PRIORITY + ['git', 'show',
            SEED_DRIVER_COMMIT + ':' + row['path']], cwd=ROOT, env=ENV)
        assert len(frozen) == row['bytes'] and sha(frozen) == row['sha256']
    else:
        checked(row)


def accepted_price_path():
    # Never overwrite the original HALT receipt. Its exact binding is part
    # of this one-pair repair; a second evaluation has its own write-once file.
    original = HERE / 'price.json'
    assert sha(original.read_bytes()) == HALTED_PRICE_SHA, 'original price drift'
    return HERE / 'price-proven-drift.json'


def emit_stdlib(ready, restored, out, side):
    suite_paths={p:out/('suite-'+sha(p.encode())[:12]+'.json') for p in ready['suites']}
    for original,target in suite_paths.items():
        value=load(restored[original])
        value['sources']=[restored[str((ROOT/p).resolve())] for p in value.get('sources',[])]
        if side=='candidate':
            value['sources']=[str(ROOT/ready['projected_editor']['path']) if p==restored[ready['old_editor']] else p for p in value['sources']]
        for key in ('resident_suites','cases_from_suites','extends'):
            if key in value:
                old=value[key]
                value[key]=str(suite_paths[str((ROOT/old).resolve())]) if isinstance(old,str) else [str(suite_paths[str((ROOT/p).resolve())]) for p in old]
        if value.get('resident_suite'):value['resident_suite']=str(suite_paths[str((ROOT/value['resident_suite']).resolve())])
        save_suite(target,value)
    command=[sys.executable,'-B','tools/host-lisp/bytecode_p0_stdlib.py','--check','--emit-artifacts',str(out/'stdlib-p0'),str(suite_paths[ready['stdlib_suite']])]
    save(out/'command.json',PRIORITY+command)
    run(command,out/'emission.log')


def emit_planes(ready):
    import c2_full_emission as F
    import c2_substitution_artifacts as SUB
    import c2_lite_v6_product_probe as V6
    from v11_function_metadata_ide_exit_20260928 import idex_projection
    restored={str(ROOT/r['source']['path']):str(ROOT/r['restored']['path']) for r in ready['closure']}
    compiled={}
    for side in ('baseline','candidate'):
        out=BUILD/'plane'/side;out.mkdir(parents=True)
        emit_stdlib(ready,restored,out,side)
        specs=[]
        for key,frozen in zip(('stdlib-p0','ide','idex','m65d','buffer','lcc'),ready['manifests'],strict=True):
            path=out/(key+'.manifest.json')
            if key!='stdlib-p0':
                value=load(frozen);value['blob']=restored[str((ROOT/value['blob']).resolve())];save(path,value)
            specs.append((key,'stdlib' if key=='stdlib-p0' else key,path))
        SUB.BUILD,SUB.SPECS=out/'product',tuple(specs)
        product=SUB.build();V6.PRODUCT_IDENTITY=SUB.BUILD/'substitution-artifacts.json'
        images=[F.emit_image(*spec) for spec in specs]
        V6.STATIC_CODE_BYTES=sum(len(i.code) for i in images)
        plane,geometry=V6.static_plane(images)
        for name,raw in [('CODE.BIN',bytes(plane.code[:plane.code_low])),('C2D.BIN',bytes(plane.c2d)),('SHELF.BIN',(SUB.BUILD/'product-shelf-v4-direct.bin').read_bytes())]:once(out/name,raw)
        compiled[side]=dict(product=product,geometry=geometry,images=images,manifest=load(out/'stdlib-p0.manifest.json'))
    base,new=compiled['baseline'],compiled['candidate']
    expected={name:PLANE/name for name in ('CODE.BIN','C2D.BIN','SHELF.BIN')}
    for name,path in expected.items():
        assert (BUILD/'plane/baseline'/name).read_bytes()==Path(restored[str(path)]).read_bytes(),('baseline reproduction',name)
    a,b=base['manifest'],new['manifest']
    blobs=[Path(m['blob']).read_bytes() for m in (a,b)]
    frozen=load(ready['manifests'][0]);frozen_blob=Path(restored[str(Path(frozen['blob']).resolve())]).read_bytes()
    assert idex_projection(a,blobs[0])==idex_projection(frozen,frozen_blob)
    changed=[]
    for x,y in zip(a['entries'],b['entries'],strict=True):
        assert x['name']==y['name']
        if x['name'] not in (*WALKS.SHARED,'%read-line-loop'):
            assert x['literals']==y['literals'],'foreign stdlib literal change'
        def code(m,blob,e):
            raw=bytearray(blob[e['blob_offset']:e['blob_offset']+e['length']])
            for p in m['literal_patches']:
                at=p['blob_offset']-e['blob_offset']
                if 0<=at<len(raw):raw[at:at+2]=b'\0\0'
            return bytes(raw)
        if code(a,blobs[0],x)!=code(b,blobs[1],y):changed.append(x['name'])
    assert set(changed)==set((*WALKS.SHARED,'%read-line-loop'))
    assert 0 < len(blobs[1])-len(blobs[0]) <= 256
    for x,y in zip(base['images'][1:],new['images'][1:],strict=True):
        assert x.code==y.code and x.metadata==y.metadata, x.key
    for key in ('entries','roots','images'):
        assert base['geometry'][key]==new['geometry'][key],('owner population drift',key)
    deltas={name:(BUILD/'plane/candidate'/name).stat().st_size-(BUILD/'plane/baseline'/name).stat().st_size for name in expected}
    result=dict(status='PASS',baseline_exact=True,changed_objects=changed,ordinary_bytecode_delta=len(blobs[1])-len(blobs[0]),
        plane_deltas=deltas,total_growth=sum(deltas.values()),bound=256,
        bank2_static_capacity=60758,bank2_static_free_after=60758-new['geometry']['code_bytes'],
        before_geometry=base['geometry'],after_geometry=new['geometry'],before_product=base['product'],after_product=new['product'],
        loader_content_before=idex_projection(a,blobs[0]),loader_content_after=idex_projection(b,blobs[1]),
        artifacts=[bind(BUILD/'plane'/side/name) for side in ('baseline','candidate') for name in expected])
    save(HERE/'plane-price.json',result)
    assert result['total_growth']<=PLANE_BOUND,'plane growth exceeds +%d bytes'%PLANE_BOUND
    assert result['bank2_static_free_after']>=0,'static owner capacity exceeded'
    return result


def derived_commands(ready, plane):
    import runtime_overlay_bank as BANK
    commands = load(HERE / 'baseline-command-proof.json')['commands']
    source = ROOT / commands[29][commands[29].index('-c') + 1]
    original = source.read_text()
    projected = original
    changes = []
    for name, file, offset in [('shelf', 'SHELF.BIN', 32), ('c2d', 'C2D.BIN', None)]:
        raw = [(BUILD / 'plane' / side / file).read_bytes() for side in ('baseline', 'candidate')]
        if offset is None:
            offset = struct.unpack_from('<H', raw[0], 28)[0]
            assert offset == struct.unpack_from('<H', raw[1], 28)[0]
        values = [[BANK.crc16_ccitt_false(data[offset+i*32:offset+(i+1)*32]) for i in range(6)] for data in raw]
        def emitted(crcs):
            return 'c2_phase02a_' + name + '_crc16:\\n' + '\\n'.join(f'.short 0x{x:04x}' for x in crcs) + '\\n'
        old, new = map(emitted, values)
        assert projected.count(old) == 1, name
        projected = projected.replace(old, new)
        changes.append(dict(table=name, before=values[0], after=values[1]))
    target = HERE / 'derived' / source.relative_to(HERE / 'native-inputs')
    # Keep quoted decoder includes at their frozen locations through -I.
    once(target, projected)
    before, after = plane['before_product'], plane['after_product']
    replacements = {str(source.relative_to(ROOT)): str(target.relative_to(ROOT)),
        '-DLISP65_C2_PRODUCT_BUILD_ID=' + before['product_build_id_hex'] + 'UL':
        '-DLISP65_C2_PRODUCT_BUILD_ID=' + after['product_build_id_hex'] + 'UL',
        '-DLISP65_C2_PRODUCT_SHELF_BYTES=' + str(before['artifacts']['shelf']['bytes']) + 'UL':
        '-DLISP65_C2_PRODUCT_SHELF_BYTES=' + str(after['artifacts']['shelf']['bytes']) + 'UL'}
    assert len(commands) == 75
    assert all(any(key in command for command in commands) for key in replacements), 'derived input not consumed'
    updated = [[replacements.get(a, a) for a in c] for c in commands]
    # Materialize a candidate include world, retaining the frozen baseline.
    # All copies are enumerated; quoted includes and forced includes therefore
    # resolve to the same explicitly derived header values.
    candidate_prefix=HERE/'candidate-inputs'
    generated=[];header_changes=[]
    old_size=load(BUILD/'plane/baseline/stdlib-p0.manifest.json')['code_bytes']
    new_size=load(BUILD/'plane/candidate/stdlib-p0.manifest.json')['code_bytes']
    old_code=plane['before_geometry']['code_bytes'];new_code=plane['after_geometry']['code_bytes']
    assert 0 < new_size-old_size <= 256 and new_code-old_code==new_size-old_size
    for row in ready['native']:
        path=ROOT/row['restored']['path']
        raw=checked(row['restored']);newraw=raw
        if path.name=='stdlib-p0.h' or (path.name=='c2_lite_static_plane.h' and f'STATIC_CODE_BYTES {old_code}UL'.encode() in raw):
            if path.name=='stdlib-p0.h':
                def tokens(text):return re.sub(r'/\* suite: .*? \*/','',text)
                before_header=(BUILD/'plane/baseline/stdlib-p0.h').read_text()
                after_header=(BUILD/'plane/candidate/stdlib-p0.h').read_text()
                assert tokens(raw.decode())==tokens(before_header), 'frozen stdlib header not reproduced'
                ma,mb=[load(BUILD/'plane'/s/'stdlib-p0.manifest.json') for s in ('baseline','candidate')]
                projection=before_header
                counts=[('BLOB_BYTES',old_size,new_size)]
                counts += [(macro,len(ma[key]),len(mb[key])) for macro,key in
                           [('LITERAL_INDEX_COUNT','literal_index'),('LITERAL_NODE_COUNT','literal_nodes'),('LITERAL_PATCH_COUNT','literal_patches')]]
                for macro,x,y in counts:
                    old=f'#define LISP65_BYTECODE_STDLIB_{macro} {x}u'
                    new=f'#define LISP65_BYTECODE_STDLIB_{macro} {y}u'
                    assert projection.count(old)==1
                    projection=projection.replace(old,new)
                    newraw=newraw.replace(old.encode(),new.encode())
                assert tokens(projection)==tokens(after_header), 'unclassified stdlib header change'
                header_changes.append(dict(source=row['restored'],counts=counts))
                dest=candidate_prefix/path.relative_to(HERE/'native-inputs')
                once(dest,newraw);generated.append(bind(dest));continue
            else:
                old=f'#define LISP65_C2_LITE_STATIC_CODE_BYTES {old_code}UL'
                new=f'#define LISP65_C2_LITE_STATIC_CODE_BYTES {new_code}UL'
            assert raw.count(old.encode())==1, ('derived header seam',path)
            newraw=raw.replace(old.encode(),new.encode())
            header_changes.append(dict(source=row['restored'],before=old,after=new))
        if path.name.endswith('.compiler-input-assert.h'):
            old=f'LISP65_C2_LITE_STATIC_CODE_BYTES != {old_code}UL'
            new=f'LISP65_C2_LITE_STATIC_CODE_BYTES != {new_code}UL'
            assert raw.count(old.encode())==1, 'compiler input assertion drift'
            newraw=raw.replace(old.encode(),new.encode())
            header_changes.append(dict(source=row['restored'],before=old,after=new))
        dest=candidate_prefix/path.relative_to(HERE/'native-inputs')
        once(dest,newraw);generated.append(bind(dest))
    assert {'stdlib-p0.h','c2_lite_static_plane.h'} <= {Path(r['source']['path']).name for r in header_changes}
    oldprefix=str((HERE/'native-inputs').relative_to(ROOT))+'/'
    newprefix=str(candidate_prefix.relative_to(ROOT))+'/'
    updated=[[a.replace(oldprefix,newprefix) for a in c] for c in updated]
    save(HERE/'derived-inputs.json',dict(replacements=replacements,crc_tables=changes,
        generated=bind(target),all_generated=generated,before=bind(source),stdlib_header_changed=True,
        header_changes=header_changes,code_bytes_before=old_code,code_bytes_after=new_code,
        stdlib_bytes_before=old_size,stdlib_bytes_after=new_size))
    save(HERE/'command-proof.json',dict(commands=updated,authority=ready['authority'],
        allowed_substitutions=replacements,header_changes=header_changes,
        include_root_rebase=dict(before=oldprefix,after=newprefix),frozen=ready['commands']))
    return updated


def include_closure(commands, ready):
    allowed = {str((ROOT / r['restored']['path']).resolve()): r['restored'] for r in ready['native']}
    generated = load(HERE / 'derived-inputs.json')['generated']
    allowed[str((ROOT / generated['path']).resolve())] = generated
    for row in load(HERE / 'derived-inputs.json')['all_generated']:
        allowed[str((ROOT / row['path']).resolve())] = row
    # Toolchain includes are explicit public replay bindings, consumed in place.
    for r in ready['native']:
        if r['source']['path'].startswith('tools/llvm-mos/'):
            allowed[str((ROOT / r['source']['path']).resolve())] = r['source']
    rows = []
    for i, command in enumerate(commands[:73]):
        source = command[command.index('-c')+1]
        if source.endswith('.s'):
            dirs = [ROOT] + [ROOT / command[j+1] for j, a in enumerate(command) if a == '-I']
            pending, deps = [ROOT / source], set()
            while pending:
                path = pending.pop().resolve()
                if str(path) in deps:
                    continue
                deps.add(str(path))
                for name in re.findall(r'^\s*\.include\s+"([^"]+)"', path.read_text(), re.M):
                    found = next((d / name for d in dirs if (d / name).is_file()), None)
                    assert found is not None, name
                    pending.append(found)
        else:
            c = list(command)
            at = c.index('-o')
            del c[at:at+2]
            c.remove('-c')
            raw = run(c + ['-E', '-M', '-MT', 'input'], HERE / 'include-logs' / f'{i:03d}.log')
            deps = {str((ROOT / p).resolve()) for p in shlex.split(raw.decode().replace('\\\n', ' ').split(':', 1)[1])}
        for path in deps:
            assert path in allowed, ('unbound dependency', path)
            checked(allowed[path])
        rows.append(dict(source=source, dependencies=[allowed[p] for p in sorted(deps)]))
    save(HERE / 'include-closure.json', dict(status='PASS', translation_units=73, rows=rows))


def price():
    verify_ready(acceptance=True)
    seeded = load(BUILD / 'seed.json')
    assert seeded['commands_consumed'] == 75 and seeded['product_link_attempts'] == 1
    for row in seeded['native'].values():
        checked(row)
    price_path = accepted_price_path()
    assert not price_path.exists(), 'price receipt already exists'
    from elf_truth import ElfTruth
    paths = [FINAL / 'wplto/resident-island-seed.prg.elf', BUILD / 'wplto/resident-island-seed.prg.elf']
    truths = [ElfTruth.read(p, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj', include_section_data=True) for p in paths]
    a, b = truths
    def sizes(t):
        return {'.text': t.section('.text').bytes, '.rodata': t.section('.rodata').bytes,
                'BSS': sum(s.bytes for s in t.sections if s.section_type == 'SHT_NOBITS' and 'SHF_ALLOC' in s.flags),
                'CRT_zero_bytes': t.symbol('__bss_end').value - t.symbol('__bss_start').value}
    old, new = map(sizes, truths)
    delta = {k: new[k] - v for k, v in old.items()}
    sites = []
    for x in a.symbols:
        if not x.bytes or x.symbol_type not in ('Function', 'Object'):
            continue
        ys = [y for y in b.symbols_by_name.get(x.name, []) if y.section == x.section and y.symbol_type == x.symbol_type]
        if len(ys) != 1:
            continue
        y = ys[0]
        if x.bytes != y.bytes:
            sites.append(dict(name=x.name, section=x.section, before=x.bytes, after=y.bytes, delta=y.bytes-x.bytes))
    sections = [dict(name=s.name, before=a.section(s.name).bytes, after=s.bytes, delta=s.bytes-a.section(s.name).bytes)
                for s in b.sections if 'SHF_ALLOC' in s.flags and s.name in a.sections_by_name and s.bytes != a.section(s.name).bytes]
    plane = load(HERE / 'plane-price.json')
    for row in plane['artifacts']:
        checked(row)
    assert plane['status'] == 'PASS' and plane['total_growth'] <= PLANE_BOUND
    proof = native_price_proof(paths, truths, delta, sites, sections)
    result = dict(status='PASS',
        ELF=[bind(p) for p in paths], before=old, after=new, delta=delta, bound=0,
        proven_drift=proof, supersedes=bind(HERE / 'price.json'),
        plane=plane['plane_deltas'], plane_total=plane['total_growth'], plane_bound=PLANE_BOUND,
        section_deltas=sections, per_site_bytes=sites,
        free_after=dict(text=0xb3b0-b.section('.text').address-b.section('.text').bytes,
                        rodata=0xb98c-b.section('.rodata').address-b.section('.rodata').bytes,
                        high_bss=0xc000-b.symbol('__bss_end').value))
    save(price_path, result)
    return result


def plane_budget(plane):
    assert plane['bound']==PLANE_BOUND and plane['total_growth']==sum(plane['delta'].values())
    assert plane['total_growth']<=PLANE_BOUND, 'preflight plane growth exceeds +%d; no Seed attempt claimed'%PLANE_BOUND


def seed():
    ready = verify_ready()
    preflight=json.loads(checked(ready['preflight_plane']))
    plane_budget(preflight['current']['plane'])
    assert not BUILD.exists(), 'Seed already claimed; no implicit retry'
    BUILD.mkdir()
    save(BUILD / 'attempt.json', dict(authority=AUTH, seed=1, final=0, product_link_attempts=0,
                                     command_probe=bind(HERE / 'command-ready.json')))
    state = dict(status='STARTED', authority=AUTH, seed=1, final=0, product_link_attempts=0)
    try:
        plane = emit_planes(ready)
        commands = derived_commands(ready, plane)
        include_closure(commands, ready)
        for i, command in enumerate(commands):
            if i == 74:
                state['product_link_attempts'] = 1
                save(BUILD / 'product-link-claim.json', state)
            output = ROOT / command[command.index('-o')+1]
            output.parent.mkdir(parents=True, exist_ok=True)
            run(command, BUILD / f'command-{i:03d}.log')
            state['commands_consumed'] = i+1
            print(f'completed frozen command {i+1}/75', flush=True)
        state['native'] = {role: bind(BUILD / 'wplto' / Path(row['path']).name) for role, row in ready['base_native'].items()}
        state['status'] = 'LINKED: run price, inventory, media in order'
    except BaseException as error:
        state.update(status='HALT', error=str(error))
        raise
    finally:
        save(BUILD / 'seed.json', state)
    return state



def classify_bytes(before, after, domains):
    """Exact expected byte pairs, never blanket changed-section exemptions."""
    rows, unknown = [], []
    for i in range(max(len(before), len(after))):
        a = before[i] if i < len(before) else None
        b = after[i] if i < len(after) else None
        if a == b:
            continue
        expected = domains.get(i)
        owner = expected[2] if expected and expected[:2] == (a, b) else 'UNCLASSIFIED'
        rows.append(dict(offset=i, before=a, after=b, owner=owner))
        if owner == 'UNCLASSIFIED':
            unknown.append(i)
    return dict(rows=rows, changed_bytes=len(rows), unclassified_bytes=len(unknown))


# Closed Backspace Final, never an older predecessor baseline.
BASE_ELF_SHA = 'd23af87de3b2d432bd43fdd34322de7b3d96cf64764b3f68a5a0e49b47596f88'


# Exact site, not a tolerance for arbitrary native shrinkage.
MAIN_DRIFT = dict(name='main', section='.text', before=622, after=620, delta=-2)


def project_main_drift(raw, a, b):
    """Project the proven register reuse and all its ELF consequences.

    Only shelf-size bytes differ semantically. X retains 84 through the
    Y stores, eliminating LDX #84. The common suffix restores identical
    A/X/Y/flags before c2_decode_from. See build/walks-r4/drift-report.md.
    No candidate byte is used to construct the expected ELF.
    """
    from dataclasses import replace
    assert sha(raw) == BASE_ELF_SHA, 'drift proof baseline binding'
    assert (a.symbol('main').value, a.symbol('main').bytes) == (0xa53d, 622)
    assert (b.symbol('main').value, b.symbol('main').bytes) == (0xa53d, 620)
    assert len(a.sections) == len(b.sections), 'unproved owner capacity'
    for x, y in zip(a.sections, b.sections, strict=True):
        assert y == (replace(x, bytes=x.bytes-2) if x.name == '.text' else x), 'unallowed section geometry'
    # The removed load occupies a6af..a6b0. All subsequent .text addresses
    # move by -2; this map applies only to the .text owner, never by VMA alone.
    def address(section, value):
        if section == '.text' and value >= 0xa6af:
            assert value >= 0xa6b1, 'reference into deleted instruction'
            return value-2
        return value
    syms = [replace(x, value=address(x.section, x.value),
                    bytes=620 if x.name == 'main' else x.bytes) for x in a.symbols]
    assert b.symbols == syms, 'unallowed symbol drift'
    start = a.section('.text').address
    payloads = {s.name: bytearray(a.section_bytes(s.name)) for s in a.sections
                if s.section_type != 'SHT_NOBITS'}
    old_block = bytes.fromhex('a2b08e84c0a2838e85c0a2018e86c09c87c0a2308e8cc0a2848e8dc0')
    new_block = bytes.fromhex('a2578e84c0a2848e85c0a0018c86c09c87c0a0308c8cc08e8dc0')
    assert bytes(payloads['.llvm_sympart']) == b'contingent\0' + struct.pack('<I', a.symbol('memcpy').value)
    payloads['.llvm_sympart'][11:] = struct.pack('<I', b.symbol('memcpy').value)
    text = payloads['.text']
    assert text[0xa698-start:0xa6b4-start] == old_block
    text[0xa698-start:0xa6b4-start] = new_block
    # Relocation operands are rewritten from the original symbol/addend,
    # including references from other owners to the moved .text suffix.
    relocs = []
    moved_operands = 0
    for r in a.relocations:
        target = a.symbols[r.target_symbol_index]
        value = target.value+r.addend
        newvalue = address(target.section, value)
        offset = address(r.source_section, r.offset)
        addend = newvalue-syms[r.target_symbol_index].value
        relocs.append(replace(r, offset=offset, addend=addend))
        if newvalue != value:
            kind = r.relocation_type
            assert kind in ('R_MOS_ADDR16', 'R_MOS_ADDR16_LO', 'R_MOS_ADDR16_HI'), kind
            def encode(v):
                return (struct.pack('<H', v) if kind == 'R_MOS_ADDR16' else
                        bytes([(v >> 8 if kind.endswith('_HI') else v) & 255]))
            before, after = encode(value), encode(newvalue)
            oldat = r.offset-a.section(r.source_section).address
            at = offset-a.section(r.source_section).address
            assert a.section_bytes(r.source_section)[oldat:oldat+len(before)] == before
            assert payloads[r.source_section][at:at+len(before)] == before
            payloads[r.source_section][at:at+len(after)] = after
            moved_operands += 1
    assert b.relocations == relocs, 'unallowed relocation drift'
    assert bytes(text) == b.section_bytes('.text'), 'unproven main/text instruction drift'
    # Fixed physical packing: -2 through .comment, +2 zero alignment pad
    # before the unchanged symtab. VMA/LMA and all other sizes stay fixed.
    shoff = struct.unpack_from('<I', raw, 32)[0]
    assert (shoff, struct.unpack_from('<I', raw, 28)[0]) == (653936, 52)
    assert struct.unpack_from('<HHHH', raw, 42) == (32, 109, 40, 222)
    expected = bytearray(raw[:3734] + text + raw[40295:136064] + bytes(2) + raw[136064:])
    assert len(expected) == len(raw)
    def fileoff(index):
        return struct.unpack_from('<I', raw, shoff+index*40+16)[0]
    for s in a.sections:
        at = shoff+s.index*40
        if s.index == 13:
            struct.pack_into('<I', expected, at+20, 36559)
        if s.index == 1 or 14 <= s.index <= 130:
            struct.pack_into('<I', expected, at+16, fileoff(s.index)-2)
        if s.section_type != 'SHT_NOBITS':
            off = struct.unpack_from('<I', expected, at+16)[0]
            expected[off:off+len(payloads[s.name])] = payloads[s.name]
    for i in range(109):
        at = 52+i*32
        if i == 2:
            struct.pack_into('<II', expected, at+16, 36559, 36559)
        if 3 <= i <= 107:
            struct.pack_into('<I', expected, at+4, struct.unpack_from('<I', raw, at+4)[0]-2)
    for x, y in zip(a.symbols, syms, strict=True):
        if x != y:
            struct.pack_into('<II', expected, 136064+x.index*16+4, y.value, y.bytes)
    for s in a.sections:
        if s.section_type == 'SHT_RELA':
            rows = [r for r in relocs if r.relocation_section == s.name]
            assert s.bytes == len(rows)*12
            for i, r in enumerate(rows):
                at = fileoff(s.index)+12*i
                struct.pack_into('<I', expected, at, r.offset)
                struct.pack_into('<I', expected, at+8, r.addend & 0xffffffff)
    return expected, dict(site=MAIN_DRIFT, exact_delta=-2, max_shrink=2,
        shelf_bytes_before=99248, shelf_bytes_after=99415,
        rebased_operands=moved_operands,
        before_main_sha256=sha(a.section_bytes('.text')[0xa53d-start:0xa7ab-start]),
        after_main_sha256=sha(text[0xa53d-start:0xa7a9-start]),
        text_free_before=1212, text_free_after=1214)


def native_price_proof(paths, truths, delta, sites, sections):
    assert delta == {'.text': -2, '.rodata': 0, 'BSS': 0, 'CRT_zero_bytes': 0}, 'unallowed native price'
    assert sites == [MAIN_DRIFT], 'unallowed native site'
    assert sections == [dict(name='.text', before=36561, after=36559, delta=-2)], 'unallowed section price'
    _, proof = project_main_drift(Path(paths[0]).read_bytes(), *truths)
    return proof


HALTED_PRICE_SHA = '1d1985e48c6129aaca9b316e41d9229fc4b278f57ae5322352f5c00b3a4090ed'


def inventory():
    from elf_truth import ElfTruth
    verify_ready(acceptance=True)
    priced = load(accepted_price_path())
    assert priced['status'] == 'PASS'
    assert not (HERE / 'inventory.json').exists(), 'inventory already exists'
    paths = [ROOT / r['path'] for r in priced['ELF']]
    raws = [checked(r) for r in priced['ELF']]
    truths = [ElfTruth.read(p, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj',
                           include_section_data=True) for p in paths]
    result = inventory_analysis(paths, raws, truths)
    result.update(ELFs=priced['ELF'], plane=bind(HERE / 'plane-price.json'),
                  derived=bind(HERE / 'derived-inputs.json'))
    save(HERE / 'inventory.json', result)
    assert result['unclassified_bytes'] == 0, 'unclassified ELF bytes'
    return result


def inventory_analysis(paths, raws, truths, listing_reader=None):
    """Read-only classification core; acceptance receipt is written by inventory."""
    a, b = truths
    drift = a.sections != b.sections
    if drift:
        assert len(a.sections) == len(b.sections), 'unproved owner capacity'
        expected, proof = project_main_drift(raws[0], a, b)
    else:
        assert a.symbols == b.symbols and a.relocations == b.relocations, 'ELF identity drift'
        expected, proof = bytearray(raws[0]), None
    plane = load(HERE / 'plane-price.json')
    for row in plane['artifacts']:
        checked(row)
    derived = load(HERE / 'derived-inputs.json')
    labels = ['proven main codegen / ELF packing metadata' if drift else 'unchanged']*len(expected)
    def add(section, offset, old, new, owner):
        assert len(old) == len(new)
        for truth, payload in zip(truths, (old, new)):
            assert truth.section_bytes(section)[offset:offset+len(payload)] == payload
        shoff = struct.unpack_from('<I', raws[0], 32)[0]
        shsize = struct.unpack_from('<H', raws[0], 46)[0]
        fileoff = struct.unpack_from('<I', expected, shoff+a.section(section).index*shsize+16)[0]
        assert expected[fileoff+offset:fileoff+offset+len(old)] == old
        expected[fileoff+offset:fileoff+offset+len(new)] = new
        labels[fileoff+offset:fileoff+offset+len(new)] = [owner]*len(new)
    for row in derived['crc_tables']:
        symbol = a.symbol('c2_phase02a_' + row['table'] + '_crc16')
        add(symbol.section, symbol.value-a.section(symbol.section).address,
            struct.pack('<6H', *row['before']), struct.pack('<6H', *row['after']),
            'derived ' + row['table'] + ' directory CRC16 array')
    pairs = []
    for key in ('before_product', 'after_product'):
        product = plane[key]
        pairs.append((int(product['product_build_id_hex'], 16), product['artifacts']['shelf']['bytes'],
                      derived['code_bytes_before' if key=='before_product' else 'code_bytes_after']))
    # Decode immediate instruction boundaries in the known constant consumers.
    # Main and its relocation/packing consequences are proved separately;
    # other constant consumers retain their instruction boundaries.
    consumers = {
        'c2_stream_phase_00': 0, 'c2_stream_phase_00b': 0,
        'c2_stream_phase_01': 0, 'c2_append_envelope_phase': 0,
        'c2_session_emit_final_crc_phase': 0, 'c2_stream_shelf_read': 1, 'c2_product_boot': 1,
        'main': 1,  # c2_product_boot is inlined by the frozen Final LTO
        'c2_stream_phase_02b': 2, 'c2_stream_phase_03b': 2,

    }
    for name, kind in consumers.items():
        if name not in a.symbols_by_name or (drift and name == 'main'):
            continue
        symbol = a.symbol(name)
        command = [str(ROOT / 'tools/llvm-mos/bin/llvm-objdump'), '-d',
                   '--section=' + symbol.section, '--start-address=' + str(symbol.value),
                   '--stop-address=' + str(symbol.value+symbol.bytes), str(paths[0])]
        listing = (listing_reader(command, name) if listing_reader else
                   run(command, HERE / 'inventory-logs' / (name + '.log')).decode())
        # Unsigned offset > limit can be lowered as offset >= limit+1.
        adjustments = (0, 1) if name == 'c2_stream_shelf_read' else (0,)
        allowed = {(x, y) for adjustment in adjustments
                   for x, y in zip(struct.pack('<I', pairs[0][kind]+adjustment),
                                   struct.pack('<I', pairs[1][kind]+adjustment)) if x != y}
        for line in listing.splitlines():
            match = re.match(r'\s*([0-9a-f]+):\s+([0-9a-f]{2})\s+([0-9a-f]{2})\s+(?:lda|ldx|ldy|cmp|cpx|cpy|eor|ora|and|adc|sbc)\s+#', line)
            if not match:
                continue
            offset = int(match[1], 16)-a.section(symbol.section).address
            old = a.section_bytes(symbol.section)[offset:offset+2]
            new = b.section_bytes(symbol.section)[offset:offset+2]
            assert old == bytes.fromhex(match[2]+match[3])
            if old[0] == new[0] and (old[1], new[1]) in allowed:
                add(symbol.section, offset+1, old[1:], new[1:], 'derived immediate: '+name)
    domains = {i: (old, new, labels[i]) for i, (old, new) in enumerate(zip(raws[0], expected))
               if old != new}
    result = classify_bytes(*raws, domains)
    result.update(status='PASS' if result['unclassified_bytes'] == 0 else 'HALT: UNCLASSIFIED',
                  geometry_proof=proof, expected_elf_sha256=sha(expected))
    return result


def rebind_family(C, fam, value, regions, a, b, elf):
    """Comfort lineage: rebind every payload, record, directory and header CRC."""
    BANK = C.BANK
    for row in value['slices']:
        old, new = a.section_bytes(row['section']), b.section_bytes(row['section'])
        off, rid = row['file_offset'], row['region_id']
        assert len(old) == row['file_size']
        assert len(old)==len(new), 'unproved slice growth: require derived-immediate proof and owner capacity'
        assert regions[rid][off:off+len(old)] == old
        regions[rid][off:off+len(new)] = new
        row.update(sha256=sha(new), crc16=BANK.crc16_ccitt_false(new))
        at = 32+32*row['id']
        struct.pack_into('<H', regions[0], at+20, row['crc16'])
        regions[0][at+22:at+24] = bytes(2)
        row['record_crc16'] = BANK.crc16_ccitt_false(regions[0][at:at+32])
        struct.pack_into('<H', regions[0], at+22, row['record_crc16'])
    over = regions[1]
    crc = BANK.crc16_ccitt_false(over)
    struct.pack_into('<I', regions[0], 28, len(over) | ((crc if over else 0) << 16))
    BANK._refresh_catalog_crcs(regions[0])
    value['overflow_storage'].update(crc16=crc, sha256=sha(over))
    value['storage'].update(crc16=BANK.crc16_ccitt_false(regions[0]), sha256=sha(regions[0]))
    value['catalog'].update(directory_crc16=int.from_bytes(regions[0][24:26], 'little'),
                            header_crc16=int.from_bytes(regions[0][26:28], 'little'))
    if fam == 'session':
        value['external_storage'].update(crc16=BANK.crc16_ccitt_false(regions[2]), sha256=sha(regions[2]))
    value['elf'] = dict(bind(elf), file=str(elf))
    return C.validate_family(fam, value, regions, a, b)


def replace_file(image, name, payload, domains):
    """Classify exact D81 transaction bytes, including allocation and directory."""
    import d81_persistence_fault as D
    if D.visible_files(image)[name.upper().encode()] == payload:
        return image
    slot, = [s for s in D.directory_slots(image) if s.record[2] and D.entry_name(s.record) == name.upper().encode()]
    chain = list(D.file_chain(image, slot.record))
    count = (len(payload)+253)//254
    assert count and count <= 0xffff
    state = bytearray(image)
    freed = chain[count:]
    chain = chain[:count]
    for track in list(range(1, 40))+list(range(41, 81)):
        for sector in range(40):
            if len(chain) < count and D.sector_is_free(state, track, sector):
                chain.append((track, sector))
                D.set_sector_free(state, track, sector, False)
    assert len(chain) == count, 'D81 full'
    for track, sector in freed:
        D.set_sector_free(state, track, sector, True)
    for index, (track, sector) in enumerate(chain):
        at = D.sector_offset(track, sector)
        state[at:at+256] = D.chain_sector(payload, tuple(chain), index)
    at = D.sector_offset(slot.track, slot.sector)+slot.index*32
    state[at+3:at+5] = bytes(chain[0])
    struct.pack_into('<H', state, at+30, count)
    # Compute expected edits from this deterministic allocation plan. The
    # ledger is later compared to the actual persisted image, byte for byte.
    data_offsets = {D.sector_offset(t, sec)+i for t, sec in chain for i in range(256)}
    for i, (old, new) in enumerate(zip(image, state)):
        if old != new:
            kind = 'file-chain' if i in data_offsets else 'directory' if at <= i < at+32 else 'BAM'
            original = domains[i][0] if i in domains else old
            domains[i] = (original, new, name + ': ' + kind)
    state = bytes(state)
    D.validate_bam(state)
    assert D.visible_files(state)[name.upper().encode()] == payload
    return state


def pack_media(C, med, artifacts, before_raw, packages, build_id):
    D, L = C.L.D81, C.L
    before = D.visible_files(before_raw)
    expected = {name: (artifacts / name.decode().lower()).read_bytes() for name in before}
    raw, domains = before_raw, {}
    for name, payload in expected.items():
        if name != b'L65INDEX':
            raw = replace_file(raw, name.decode(), payload, domains)
    # Package locators are final before the index is encoded.
    medium = med / 'locator-image.d81'
    once(medium, raw)
    locators = L.L65I.d81_locators(medium)
    rows, payloads = [], {}
    for row in packages:
        name = row['name']
        entry, payload = L.F.measured_row(name, name, row['shelf'], ROOT / row['manifest']['path'],
            tuple(row['dependencies']), *locators[name], product_build_id=build_id)
        assert payload == expected[name.upper().encode()]
        rows.append(entry); payloads[name] = payload
    index = L.L65I.encode_index(rows)
    expected[b'L65INDEX'] = index
    raw = replace_file(raw, 'l65index', index, domains)
    final = med / 'walks.d81'
    once(final, raw)
    D.validate_bam(raw)
    raw = final.read_bytes()
    actual = D.visible_files(raw)
    assert actual == expected, 'every file must read back exactly'
    assert L.L65I.decode_index(actual[b'L65INDEX'], payloads, artifact_build_id=build_id) == rows
    mutations = L.L65I.mutation_gate(index, payloads, artifact_build_id=build_id)
    diff = classify_bytes(before_raw, raw, domains)
    assert diff['unclassified_bytes'] == 0
    save(med / 'd81-byte-diff.json', diff)
    return dict(status='PASS', medium=bind(final), base_sha256=sha(before_raw),
        every_file_read_back=True, files={n.decode(): dict(bytes=len(v), sha256=sha(v)) for n, v in actual.items()},
        unclassified_bytes=0, diff=bind(med / 'd81-byte-diff.json'), mutations=mutations,
        product_links=0, emulator_runs=0, device_contacts=0)


def media_plane_control(ready, before):
    """Compare emission with frozen emission, and delivery with delivery."""
    import c2_lite_media_product as M
    sources = {name: PLANE/name for name in ('CODE.BIN','C2D.BIN','SHELF.BIN')}
    closure = {str((ROOT / r['source']['path']).resolve()): r for r in ready['closure']}
    proof = {}
    for name, source in sources.items():
        row = closure[str(source.resolve())]
        baseline = (BUILD / 'plane/baseline' / name).read_bytes()
        assert baseline == checked(row['source']) == checked(row['restored']), ('pre-media baseline', name)
        delivered = before[name.encode()]
        if name == 'C2D.BIN':
            assert len(baseline) == M.C2D_PREFIX_BYTES
            expected = baseline + bytes(M.C2D_RESET_DOMAIN_BYTES - len(baseline))
            assert delivered == expected, 'complete C2D reset-domain control'
        elif name == 'SHELF.BIN':
            assert delivered == baseline, 'complete shelf control'
        else:
            assert len(delivered) >= len(baseline) and delivered[:len(baseline)] == baseline, 'static code control'
        proof[name] = dict(emitted_bytes=len(baseline), emitted_sha256=sha(baseline),
                           delivered_bytes=len(delivered), delivered_sha256=sha(delivered),
                           suffix_bytes=len(delivered)-len(baseline), frozen=row['restored'])
    return dict(status='PASS', comparison='frozen pre-media emission; exact delivery projection', files=proof)


def project_delivery_code(delivered, baseline, candidate):
    assert delivered[:len(baseline)]==baseline, 'baseline code mismatch'
    assert len(candidate)-len(baseline)<=256, 'static growth bound'
    assert len(candidate)<=60758, 'static code exceeds frozen Bank-2 owner capacity'
    extent=max(len(baseline),len(candidate))
    assert len(delivered)>=extent and not any(delivered[len(baseline):extent]), 'static growth overlaps native owner'
    result=bytearray(delivered)
    result[:extent]=candidate+bytes(extent-len(candidate))
    assert result[extent:]==delivered[extent:]
    return result


def media(output=None):
    import comfort_default_media as C
    ready = verify_ready(acceptance=True)
    inv = load(HERE / 'inventory.json')
    assert inv['status'] == 'PASS' and inv['unclassified_bytes'] == 0
    assert load(accepted_price_path())['status'] == 'PASS'
    for row in load(BUILD / 'seed.json')['native'].values():
        checked(row)
    for row in inv['ELFs']:
        checked(row)
    checked(inv['plane']); checked(inv['derived'])
    for row in load(HERE / 'plane-price.json')['artifacts']:
        checked(row)
    authority_media = ready['media_authority']
    verify_seed_driver(authority_media['builder'], acceptance=True)
    before_raw = checked(authority_media['medium'])
    assert sha(before_raw) == BASE_MEDIA_SHA
    before = C.L.D81.visible_files(before_raw)
    assert {n.decode(): dict(bytes=len(v), sha256=sha(v)) for n, v in before.items()} == authority_media['files']
    control = media_plane_control(ready, before)
    med = output if output is not None else BUILD / 'media'
    med.mkdir(exist_ok=False)
    artifacts = med / 'artifacts'
    artifacts.mkdir()
    save(med / 'plane-control.json', control)
    for name, data in before.items():
        once(artifacts / name.decode().lower(), data)
    elf = ROOT / inv['ELFs'][1]['path']
    a, b = [C.ElfTruth.read(ROOT / r['path'], llvm_readobj=C.READOBJ, include_section_data=True) for r in inv['ELFs']]
    families, manifests = {}, []
    for fam in ('boot', 'session'):
        value = load(FINAL / 'media' / ('runtime-overlays-'+fam+'-final.json'))
        regions = {0: bytearray(before[(fam+'.bin').upper().encode()]),
                   1: bytearray((FINAL / 'media' / value['overflow_storage']['file']).read_bytes())}
        if fam == 'session':
            regions[2] = bytearray(a.section_bytes('.lisp65_rt_card2b_disk'))
        families[fam] = rebind_family(C, fam, value, regions, a, b, elf)
        (artifacts / (fam+'.bin')).write_bytes(regions[0])
        once(med / value['overflow_storage']['file'], regions[1])
        if fam == 'session':
            (artifacts / 'region1.bin').write_bytes(regions[1])
            code = bytearray(before[b'CODE.BIN'])
            assert code[0xee00:0xee00+len(regions[2])] == a.section_bytes('.lisp65_rt_card2b_disk')
            code[0xee00:0xee00+len(regions[2])] = regions[2]
            (artifacts / 'code.bin').write_bytes(code)
        path = med / ('runtime-overlays-'+fam+'-final.json')
        save(path, value); manifests.append(path)
    window = bytearray(before[b'WINDOW.BIN'])
    for section in a.sections:
        if section.name.startswith('.lisp65_c2_kernal_window.') and section.section_type != 'SHT_NOBITS':
            old, new = a.section_bytes(section.name), b.section_bytes(section.name)
            at = section.address-0xe000
            assert 0 <= at and at+len(old) <= len(window) and len(old) == len(new)
            assert window[at:at+len(old)] == old
            window[at:at+len(new)] = new
        elif section.name.startswith('.lisp65_c2_mapped_') and section.section_type != 'SHT_NOBITS':
            assert a.section_bytes(section.name) == b.section_bytes(section.name), section.name
    (artifacts / 'window.bin').write_bytes(window)
    assert a.section_bytes('.lisp65_c2_vectors') == b.section_bytes('.lisp65_c2_vectors')
    code = bytearray((artifacts / 'code.bin').read_bytes())
    baseline_code = (BUILD / 'plane/baseline/CODE.BIN').read_bytes()
    candidate_code = (BUILD / 'plane/candidate/CODE.BIN').read_bytes()
    code = project_delivery_code(code,baseline_code,candidate_code)
    (artifacts / 'code.bin').write_bytes(code)
    for name in ('SHELF.BIN', 'C2D.BIN'):
        candidate = (BUILD / 'plane/candidate' / name).read_bytes()
        if name == 'C2D.BIN':
            assert len(candidate) == C.M.C2D_PREFIX_BYTES
            candidate += bytes(C.M.C2D_RESET_DOMAIN_BYTES - len(candidate))
        (artifacts / name.lower()).write_bytes(candidate)
    table = C.P.verifier_binding_bytes(*manifests)+C.P.family_stage_binding_bytes(*manifests)
    assert len(table) == 40
    once(med / 'runtime-overlay-verifier-bindings.bin', table)
    prg = med / 'lisp65-c2-substitution-linked.prg'
    once(prg, elf.with_suffix('').read_bytes())
    C.FACADE.materialize_facade(prg, elf, med / 'facade-materialization.json')
    unbound = prg.read_bytes()
    once(med / 'lisp65-c2-substitution-unbound.prg', unbound)
    C.PRG.from_elf(elf, unbound)
    raw = bytearray(unbound)
    at = b.section('.lisp65_runtime_overlay_verifier_bindings').address-int.from_bytes(raw[:2], 'little')+2
    raw[at:at+40] = table
    binding = load(FINAL / 'media/kernal-window-publish-last.json')
    crc = C.BANK.crc16_ccitt_false(window)
    binding['single_product_link_window'] = dict(bind(artifacts / 'window.bin'), crc16=f'0x{crc:04x}')
    for row in binding['binding_operands']:
        assert raw[row['file_offset']] == row['compiled_value']
        row['published_value'] = (crc >> 8) & 255 if row['name'].endswith('high') else crc & 255
        raw[row['file_offset']] = row['published_value']
    save(med / 'kernal-window-publish-last.json', binding)
    domain = set(range(at, at+40)) | {r['file_offset'] for r in binding['binding_operands']}
    assert len(raw) == len(unbound) and all(x == y or i in domain for i, (x, y) in enumerate(zip(unbound, raw)))
    save(med / 'total-publish-last-domain.json', dict(status='passed', changes_outside_declared_domains=0,
        declared_domain_bytes=len(domain), bound_product_sha256=sha(raw), unbound_product_sha256=sha(unbound)))
    prg.write_bytes(raw)
    (artifacts / 'lisp65.prg').write_bytes(C.PRG.from_elf(elf, bytes(raw), publication_dir=med))
    C.CAN.ARTIFACTS = artifacts
    _, geometry = C.CAN.build_boot_stage(elf, artifacts / 'profile')
    product = load(HERE / 'plane-price.json')['after_product']
    build_id = int(product['product_build_id_hex'], 16)
    packages = load(FINAL / 'media/runtime-receipt.json')['packages']
    assert len(packages) == 6 and {r['name'] for r in packages} == {r['name'] for r in authority_media['packages']}
    for row in packages:
        checked(row['manifest'])
        _, payload = C.L.F.measured_row(row['name'], row['name'], row['shelf'], ROOT / row['manifest']['path'],
            tuple(row['dependencies']), 1, 1, product_build_id=build_id)
        (artifacts / row['name']).write_bytes(payload)
    save(med / 'runtime-receipt.json', dict(status='PASS', ELF=bind(elf), families=families,
        boot_geometry=geometry, product_build_id=build_id, packages=packages))
    # The inherited cold delivery stager is not another product link.
    C.MED, C.ART, C.OUT, C.ELF = med, artifacts, HERE, elf
    C.run = lambda cmd: run(cmd, med / ('host-'+sha(str(cmd).encode())[:16]+'.log')).decode('latin1')
    C.M.ASM_CONTRACT_INCLUDE = med / 'stager-contract.inc'
    assembly = C.M.STAGER_S.read_text().replace(C.M.ASM_CONTRACT_INCLUDE_TOKEN,
        '.include "' + str(C.M.ASM_CONTRACT_INCLUDE.relative_to(ROOT)) + '"')
    C.M.ASM_CONTRACT_INCLUDE_TOKEN = '.include "' + str(C.M.ASM_CONTRACT_INCLUDE.relative_to(ROOT)) + '"'
    C.M.STAGER_S = med / 'cold-stager-chain.s'
    once(C.M.STAGER_S, assembly)
    C.M.run = lambda cmd, label: run(cmd, med / ('stager-'+sha(label.encode())[:16]+'.log')).decode('latin1')
    C.stager()
    result = pack_media(C, med, artifacts, before_raw, packages, build_id)
    result['plane_control'] = bind(med / 'plane-control.json')
    save(HERE / 'media.json', result)
    return result


def walks_projection_selftest():
    import tempfile
    from unittest.mock import patch
    import runtime_overlay_bank as BANK
    with tempfile.TemporaryDirectory(prefix='walks-producer-selftest-') as tmp:
        root=Path(tmp);here=root/'receipts';build=root/'product'
        with patch.dict(globals(),ROOT=root,HERE=here,BUILD=build), patch.object(subprocess,'run',side_effect=AssertionError('native command forbidden')), patch.object(subprocess,'check_output',side_effect=AssertionError('native command forbidden')):
            native=here/'native-inputs';native.mkdir(parents=True)
            old_code,new_code=49752,49959
            old_size,new_size=19499,19706
            header='#define LISP65_BYTECODE_STDLIB_BLOB_BYTES 19499u\n'+''.join(f'#define LISP65_BYTECODE_STDLIB_{k} 0u\n' for k in ('LITERAL_INDEX_COUNT','LITERAL_NODE_COUNT','LITERAL_PATCH_COUNT'))
            once(native/'stdlib-p0.h',header)
            once(native/'c2_lite_static_plane.h','#define LISP65_C2_LITE_STATIC_CODE_BYTES 49752UL\n')
            once(native/'owner.compiler-input-assert.h','#if LISP65_C2_LITE_STATIC_CODE_BYTES != 49752UL\n#error wrong header\n#endif\n')
            data={}
            for side,size in [('baseline',old_size),('candidate',new_size)]:
                out=build/'plane'/side
                save(out/'stdlib-p0.manifest.json',dict(code_bytes=size,literal_index=[],literal_nodes=[],literal_patches=[]))
                once(out/'stdlib-p0.h',header.replace('19499',str(size)))
                for name in ('SHELF.BIN','C2D.BIN'):
                    raw=bytearray(224)
                    if name=='C2D.BIN':struct.pack_into('<H',raw,28,32)
                    if side=='candidate':raw[40]=1
                    data[side,name]=bytes(raw);once(out/name,raw)
            source=''
            for name,file in [('shelf','SHELF.BIN'),('c2d','C2D.BIN')]:
                raw=data['baseline',file]
                crcs=[BANK.crc16_ccitt_false(raw[32+i*32:32+(i+1)*32]) for i in range(6)]
                source+='c2_phase02a_'+name+'_crc16:\\n'+'\\n'.join(f'.short 0x{x:04x}' for x in crcs)+'\\n'
            once(native/'crc.c',source)
            flags=['cc','-c',str((native/'crc.c').relative_to(root)),'-DLISP65_C2_PRODUCT_BUILD_ID=0x11111111UL','-DLISP65_C2_PRODUCT_SHELF_BYTES=224UL','-include',str((native/'stdlib-p0.h').relative_to(root))]
            commands=[list(flags) for _ in range(75)]
            save(here/'baseline-command-proof.json',dict(commands=commands))
            ready=dict(authority=AUTH,commands=bind(here/'baseline-command-proof.json'),native=[dict(source=bind(p),restored=bind(p)) for p in sorted(native.iterdir())])
            plane=dict(before_product=dict(product_build_id_hex='0x11111111',artifacts=dict(shelf=dict(bytes=224))),after_product=dict(product_build_id_hex='0x22222222',artifacts=dict(shelf=dict(bytes=224))),before_geometry=dict(code_bytes=old_code),after_geometry=dict(code_bytes=new_code))
            projected=derived_commands(ready,plane)
            proof=load(here/'derived-inputs.json')
            assert len(projected)==75 and proof['stdlib_header_changed']
            assert len(proof['header_changes'])==3
            assert all('receipts/native-inputs/' not in a for c in projected for a in c)
            assert (here/'candidate-inputs/stdlib-p0.h').read_text()==header.replace('19499','19706')
            assert (native/'stdlib-p0.h').read_text()==header
            assert '49959UL' in (here/'candidate-inputs/owner.compiler-input-assert.h').read_text()
            assert load(here/'command-proof.json')['commands']==projected
            padded=b'abcdefgh'+bytes(256)+b'NATIVE-SUFFIX'
            assert project_delivery_code(padded,b'abcdefgh',b'x'*264)==b'x'*264+b'NATIVE-SUFFIX'
            try:project_delivery_code(padded,b'abcdefgh',b'x'*265)
            except AssertionError:pass
            else:raise AssertionError('plane +257 mutation survived')
            delivered=b'abcdefghNATIVE-SUFFIX'
            assert project_delivery_code(delivered,b'abcdefgh',b'ab')==b'ab'+bytes(6)+b'NATIVE-SUFFIX'
            for baseline,candidate in [(b'wrong',b'a'),(b'abcdefgh',b'123456789')]:
                try:project_delivery_code(delivered,baseline,candidate)
                except AssertionError:pass
                else:raise AssertionError('wrong baseline/growth survived media projection')
    return ['75-command exact substitution','derived CRC tables','forced stdlib header','static extent and compiler assertions','immutable baseline headers','fixed native media suffix','bad baseline and growth rejected']


def selftest():
    import backspace_seed_producer as predecessor
    from unittest.mock import patch
    import tempfile
    inherited = predecessor.selftest()
    projections = walks_projection_selftest()
    # Card-specific controls use the actual seam/projection code; no subprocess
    # or native operation may escape these pure tests.
    with patch.object(subprocess,'run',side_effect=AssertionError('product command forbidden')), patch.object(subprocess,'check_output',side_effect=AssertionError('product command forbidden')):
        # Pure projection controls exercise the production transformation with
        # synthetic source worlds; no Git, compiler or product command runs.
        shared='\n'.join('(defun '+name+' (x) x)' for name in WALKS.SHARED)
        loop='(defun %read-line-loop (state) (let* ((event (%rl-poll state))) event))'
        before=shared+'\n'+loop
        after=shared.replace('(x) x)','(x) (cdr x))')+'\n'+loop+'\n(defun %rl-poll (state) (let* ((s3 state)) (if (numberp (car state)) (car s3) nil) nil))'
        product=before.replace('(%rl-poll state)','(if (nthcdr 8 state) (%rl-render nil 0 0 0 0 -1) (key-event 1))')
        projected=WALKS.transform_core(product,before,after)
        assert '(progn (if (numberp' in projected
        for bad in (product+product,product.replace('(defun %rl-cut ', '(defun missing ')):
            try:WALKS.transform_core(bad,before,after)
            except ValueError:pass
            else:raise AssertionError('projection mutation survived')
        # Inventory must fail closed on every unknown geometry, even when
        # it resembles the predecessor card's proven one-byte drift.
        from types import SimpleNamespace as NS
        try:inventory_analysis([],[],[NS(sections=[1]),NS(sections=[2,3])])
        except AssertionError as error:assert 'owner capacity' in str(error)
        else:raise AssertionError('unknown codegen geometry survived')
        assert classify_bytes(b'ab',b'ac',{})['unclassified_bytes']==1
        plane_budget(dict(bound=PLANE_BOUND,total_growth=PLANE_BOUND,delta={'CODE.BIN':207,'SHELF.BIN':PLANE_BOUND-207}))
        for growth in (PLANE_BOUND+1,PLANE_BOUND+100):
            try:plane_budget(dict(bound=PLANE_BOUND,total_growth=growth,delta={'CODE.BIN':207,'SHELF.BIN':growth-207}))
            except AssertionError:pass
            else:raise AssertionError('over-budget preflight admitted a Seed')
    return dict(status='PASS',synthetic_only=True,product_commands=0,
        inherited=inherited,projection_controls=projections,walks_controls=['ancestor-bound source projection',
        'duplicate seam rejected','unproved geometry rejected','unclassified byte rejected'],
        bounds=dict(native_text=0,proven_main_delta=-2,native_rodata=0,BSS=0,plane_total=PLANE_BOUND,authored_preflight_bytecode=206,measured_projection=374))


def main():
    global HERE
    assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', nargs='?', choices=['command-probe', 'seed', 'price', 'inventory', 'media'])
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--probe-output', type=Path, help='fresh budget-free probe receipt root; Seed always uses walks-r3/seed')
    parser.add_argument('--media-output', type=Path, help='fresh media directory under build; preserves failed attempts')
    args = parser.parse_args()
    if args.media_output is not None:
        assert args.mode == 'media' and not args.selftest
        args.media_output = args.media_output.resolve()
        assert args.media_output.is_relative_to(ROOT / 'build') and not args.media_output.exists()
    if args.selftest:
        assert args.mode is None and args.probe_output is None
        result = selftest()
    else:
        assert args.mode is not None
        if args.probe_output is not None:
            assert args.mode == 'command-probe', 'custom root is probe-only'
            HERE = args.probe_output.resolve()
            assert HERE.is_relative_to(ROOT / 'build') and not HERE.exists()
        result = {'command-probe': command_probe, 'seed': seed, 'price': price,
                  'inventory': inventory, 'media': lambda: media(args.media_output)}[args.mode]()
    print(json.dumps(result, indent=2))
    if result['status'].startswith('HALT'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
