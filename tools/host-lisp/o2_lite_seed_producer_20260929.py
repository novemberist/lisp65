#!/usr/bin/env python3
"""Write-once O2-lite Seed; historical r2 reuse and authorized r3 successor.

Owner authority: post-2.4.0-plan, 2026-09-29. STOP is a separate card.
R3 actions use the frozen STRINGS native recipe with derived plane constants.
No Final or target claims. Historical r2 actions retain their original guards.
"""
import argparse
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
import strings_seed_producer as S
import bytecode_p0_stdlib as P
import c2_full_emission as F
import c2_defstruct_foundations_gate as PK
import c2_require_resolver_gate as L
import d81_persistence_fault as D
from v11_function_metadata_ide_exit_20260928 import idex_projection

ROOT = Path(__file__).resolve().parents[2]
CAND = ROOT / 'build/multiline-lite-r2'
BUILD = ROOT / 'build/o2-lite-product-r2'
PREFLIGHT = ROOT / 'build/o2-lite-emission-preflight-r2'
FINAL = ROOT / 'build/strings-final-r1'
BASE_HEAD = 'b3a4e3311defbfa015cd746da625eaa3164f404b'
BASE_MEDIA_SHA = '9978daa146b89cf71ad1d3f290d80cf74b197911e7854859f9e4aa9bb2fce441'
LIBRARY_BOUND = 3000
PLANE_BOUND = 1845
SHARED_RESIDENT_DELTA = 0
SUITE = ROOT / 'config/comfort-default-plane/libraries/repl-comfort-suite.json'
sha, bind, checked, load = S.sha, S.bind, S.checked, S.load


def once(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data.encode() if isinstance(data, str) else data)


def save(path, value):
    once(path, json.dumps(value, indent=2, sort_keys=True) + '\n')


def library_budget(before, after):
    assert before == 1060, 'wrong baseline'
    assert after <= LIBRARY_BOUND, 'library exceeds 3000'
    assert after == 2905 and after-before == PLANE_BOUND, 'successor geometry drift'


def index_control(before, rows):
    old = L.decode_index(before)
    assert len(old) == len(rows) == 6, 'index population drift'
    for a, b in zip(old, rows):
        allowed = {'artifact_bytes', 'bank2', 'combined_crc32', 'entries',
                   'resolutions', 'roots', 'scratch'} if a['name'] == 'repl-comfort' else set()
        assert a.keys() == b.keys()
        assert all(a[k] == b[k] for k in a if k not in allowed), 'foreign index mutation'
    return L.encode_index(rows)


def price_control(manifest, blob, expected, baseline):
    library_budget(baseline, len(blob))
    assert manifest['code_bytes'] == len(blob)
    assert len(manifest['entries']) == 24, 'missing entry'
    assert max(e['length'] for e in manifest['entries']) <= 255, '256-byte object'
    assert idex_projection(manifest, blob) == expected['content'], 'stale price'
    assert [{k:e[k] for k in ('name','length','lit_count')} for e in manifest['entries']] == expected['entries'], 'entry drift'


def runtime_control(before, after):
    assert before == after, 'shared/native drift'


def resident_suite(out):
    r = P._read_suite(str(ROOT/'tests/bytecode/libs/p0-repl-comfort-v240-resident.json'))
    r['sources'] = ['lib/stdlib-read-line.lisp' if x.endswith('/022-product-editor.lisp') else x for x in r['sources']]
    for name in re.findall(r'\(defun ([^ ]+)', (ROOT/'lib/stdlib-read-line.lisp').read_text()):
        if name not in r['functions']:
            r['functions'].append(name)
    save(out/'resident.json', r)
    return out/'resident.json'


def emit(out):
    out.mkdir()
    rp = resident_suite(out)
    prices = load(CAND/'price.json')
    prices['candidate'] = load(PREFLIGHT/'price.json')
    baseline = load(CAND/'price/baseline/suite.json')
    old = subprocess.check_output(S.PRIORITY + ['git','show',BASE_HEAD+':lib/repl-comfort-v250.lisp'], cwd=ROOT, env=S.ENV)
    once(out/'baseline.lisp', old)
    baseline['sources'] = [str(out/'baseline.lisp') if x == 'lib/repl-comfort-v250.lisp' else x for x in baseline['sources']]
    current = P._read_suite(str(SUITE))
    for side, suite in [('baseline', baseline), ('candidate', current)]:
        dest = out/side
        dest.mkdir()
        suite['resident_suite'] = str(rp)
        suite['cases'] = [dict(name='emission-only', expr='nil', expect='nil')]
        save(dest/'suite.json', suite)
        P.emit_artifacts(str(dest/'suite.json'), suite, str(dest/'repl-comfort'), base_addr=0, artifact_role='disk-lib')
        m = load(dest/'repl-comfort.manifest.json')
        b = (dest/'repl-comfort.blob.bin').read_bytes()
        reference = CAND/'price'/side if side == 'baseline' else PREFLIGHT
        assert b == (reference/'repl-comfort.blob.bin').read_bytes(), 'candidate byte drift'
        assert idex_projection(m,b) == prices[side]['content']
        if side == 'baseline':
            frozen = ROOT/'build/strings-r7/seed/plane/candidate/repl-comfort'
            assert idex_projection(load(frozen.with_suffix('.manifest.json')), frozen.with_suffix('.blob.bin').read_bytes()) == prices[side]['content']
        else:
            price_control(m,b,prices[side],prices['baseline']['code_bytes'])
    manifests = load(ROOT/'build/strings-r7/seed/plane-price.json')['after_product']['manifests']
    known = {e['name'] for row in manifests for e in load(ROOT/row['path'])['entries']}
    known.update(e['name'] for e in m['entries'])
    text = (dest/'repl-comfort.disasm.txt').read_text()
    refs = set()
    for entry, section in zip(m['entries'],re.split(r'^\[\d+\] .*$',text,flags=re.M)[1:]):
        refs.update(entry['literals'][int(i)]['symbol'] for i in re.findall(r'\b(?:CALL|TAILCALL) lit=(\d+)',section))
    assert not refs-known, refs-known
    return dict(status='PASS', baseline=1060, library=2905, bound=LIBRARY_BOUND,
                delta=PLANE_BOUND, shared_resident_delta=0, native_delta=0,
                call_targets=sorted(refs), product_manifests=manifests,
                artifacts=[bind(p) for p in sorted(out.rglob('*')) if p.is_file()])


def pack(before_raw, payload, row, build_id, out):
    before = D.visible_files(before_raw)
    domains = {}
    provisional = S.replace_file(before_raw, 'repl-comfort', payload, domains)
    rows = L.decode_index(before[b'L65INDEX'])
    rows = [row if x['name']=='repl-comfort' else x for x in rows]
    index = index_control(before[b'L65INDEX'], rows)
    raw = S.replace_file(provisional, 'l65index', index, domains)
    expected = {**before, b'REPL-COMFORT':payload, b'L65INDEX':index}
    S.media_like_for_like(before, expected)
    D.validate_bam(raw)
    assert D.visible_files(raw) == expected
    packages = {r['name']:expected[r['name'].upper().encode()] for r in rows}
    assert L.decode_index(index, packages, artifact_build_id=build_id) == rows
    once(out/'o2lite.d81', raw)
    readback = (out/'o2lite.d81').read_bytes()
    assert readback == raw and D.visible_files(readback) == expected
    assert L.decode_index(D.visible_files(readback)[b'L65INDEX'], packages, artifact_build_id=build_id) == rows
    diff = S.classify_bytes(before_raw, readback, domains)
    assert diff['unclassified_bytes'] == 0
    save(out/'d81-byte-diff.json',diff)
    return dict(status='PASS', medium=bind(out/'o2lite.d81'), every_file_read_back=True,
                index_rows=rows, mutations=L.mutation_gate(index,packages,artifact_build_id=build_id),
                files={n.decode():dict(bytes=len(v),sha256=sha(v),unchanged=v==before[n]) for n,v in expected.items()},
                changed_bytes=diff['changed_bytes'], unclassified_bytes=0)


def selftest():
    rejected = []
    def reject(name, fn):
        try:
            fn()
        except (AssertionError, ValueError, L.GateError, FileExistsError):
            rejected.append(name)
        else:
            raise AssertionError('negative survived: '+name)
    m = load(PREFLIGHT/'repl-comfort.manifest.json')
    b = (PREFLIGHT/'repl-comfort.blob.bin').read_bytes()
    p = load(PREFLIGHT/'price.json')
    price_control(m,b,p,1060)
    reject('3001 B',lambda:library_budget(1060,3001))
    reject('wrong baseline',lambda:library_budget(1059,2905))
    bad=copy.deepcopy(m);bad['entries'][0]['length']=256
    reject('256-B object',lambda:price_control(bad,b,p,1060))
    bad=copy.deepcopy(m);bad['entries'].pop()
    reject('missing entry',lambda:price_control(bad,b,p,1060))
    bad=copy.deepcopy(p);bad['content']['normalized_blob_sha256']='0'*64
    reject('stale price',lambda:price_control(m,b,bad,1060))
    reject('shared drift',lambda:runtime_control(b'CODE',b'code'))
    reject('native drift',lambda:runtime_control(b'ELF',b'elf'))
    original=(FINAL/'media/strings.d81').read_bytes()
    before=D.visible_files(original);rows=L.decode_index(before[b'L65INDEX'])
    bad=copy.deepcopy(rows);bad[0]['roots']+=1
    reject('foreign row mutation',lambda:index_control(before[b'L65INDEX'],bad))
    reject('foreign file mutation',lambda:S.media_like_for_like(before,{**before,b'BOOT.ID':b'wrong'}))
    provisional=S.replace_file(original,'repl-comfort',bytes(5106),{})
    reject('stale index / partial construction',lambda:D.visible_files(provisional))
    full=bytearray(original)
    for t in range(1,81):
        for s in range(40):
            D.set_sector_free(full,t,s,False)
    reject('insufficient space',lambda:S.replace_file(bytes(full),'repl-comfort',bytes(5106),{}))
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'receipt';once(path,b'one')
        reject('write-once / partial retry',lambda:once(path,b'two'))
    assert S.classify_bytes(b'a',b'b',{})['unclassified_bytes']==1
    return dict(status='PASS',negative_controls=rejected,product_links=0)


def symbol_capacity(commands, manifest):
    import mvp_vm_stdlib_boot_budget as B
    names = set()
    inputs = []
    for command in commands:
        if '-c' in command and command[command.index('-c')+1].endswith('.c'):
            path = ROOT/command[command.index('-c')+1]
            active = set(B.d_flags(' '.join(command))) | {'__MEGA65__'}
            native, _, _ = B.native_symbols_from_sources([path], active)
            names.update(native); inputs.append(bind(path))
    paths = [ROOT/r['path'] for r in load(ROOT/'build/strings-r7/seed/plane-price.json')['after_product']['manifests']]
    paths += [ROOT/r['manifest']['path'] for r in load(FINAL/'media/runtime-receipt.json')['packages']]
    paths.append(manifest)
    for path in paths:
        entries, literals = B.manifest_symbols(load(path))
        names.update(entries | literals); inputs.append(bind(path))
    used = dict(symbols=len(names), namepool=B.namepool_bytes(names))
    limits = dict(symbols=1008, namepool=16351)
    assert limits['symbols']-used['symbols'] >= 32
    assert limits['namepool']-used['namepool'] >= 384
    return dict(status='PASS', scope='static native + resident + all six packages; target session floor remains a reviewer gate',
                used=used, limits=limits, names=sorted(names), inputs=inputs)


def host():
    """Replay candidate oracles without writing any candidate/sealed evidence."""
    import runpy
    sys.path.insert(0, str(CAND))
    import oracle as O
    from cases import cases, lanes
    out = BUILD/'host'
    out.mkdir()  # write-once run, including partial construction
    O.OUT = out
    O.save = lambda name,value: save(out/name,value)
    def suites(candidate=True):
        suite = P._read_suite(str(ROOT/'tests/bytecode/libs/p0-repl-comfort-v250.json'))
        if not candidate:
            old = load(BUILD/'emission/baseline/suite.json')
            old['cases'] = suite['cases']
            suite = old
        suite['resident_suite'] = str(BUILD/'emission/resident.json')
        assert not any('/multiline-lite-r2/src/' in x for x in suite['sources'])
        return suite
    O.suites = suites
    suite=suites();suite['cases']=[x for x in suite['cases'] if x['name'].startswith('comfort-string-')]+cases()+lanes()
    results=O.run(suite)
    baseline=suites(False);baseline['cases']=lanes()+[x for x in cases() if x['name'] in ('native-entry-unchanged','history-unchanged','history-down-empty')]
    paired=O.run(baseline)
    assert len(results)==31 and len(paired)==7
    save(out/'oracle.json',dict(results=results,baseline=paired))
    # Preserve historical tools; execute bound copies at the native ring capacity.
    for script in ('memory_audit.py','worst.py','publication.py'):
        once(out/script, (CAND/script).read_text().replace('batch_cap=8', 'batch_cap=107'))
    sys.path.insert(0, str(out))
    for script in ('memory_audit.py','worst.py','publication.py'):
        runpy.run_path(str(out/script),run_name='__main__')
    import o2_lite_batch_r2 as batches
    batches.run(O, suites, out, save)
    save(out/'receipt.json',dict(status='PASS',applied_sources=load(BUILD/'source.json'),
        oracle=31,baseline=7,admission=14,publication=2,batch_caps=[1,107,None],
        batch_tool=bind(ROOT/'tools/host-lisp/o2_lite_batch_r2.py'),
        tools=[bind(CAND/n) for n in ('oracle.py','cases.py','admission.py','memory_audit.py','worst.py','publication.py')],
        outputs=[bind(p) for p in sorted(out.glob('*.json'))]))
    return dict(status='PASS',receipt=bind(out/'receipt.json'))


def seed():
    assert not BUILD.exists(), 'Seed already claimed; preserve failed attempts'
    BUILD.mkdir()
    save(BUILD/'attempt.json',dict(status='STARTED',head=S.git('rev-parse','HEAD'),
        authority=bind(ROOT/'docs/planning/post-2.4.0-plan.md'), plan=bind(CAND/'seed-plan.md'),
        producer=bind(Path(__file__)), final=bind(FINAL/'final-identity.json'),
        committed_source_admission='OPEN; working-tree content bound',product_links=0))
    try:
        # Candidate bindings protect both reviewed artifacts and shared sources.
        bindings=load(CAND/'bindings.json')
        for path,row in bindings.items():
            if path.startswith('build/multiline-lite-r2/') or path in ('lib/stdlib-read-line.lisp','lib/sexp-depth.lisp'):
                checked(dict(path=path,**row))
        for name in ('repl-comfort-v250.lisp','lite.lisp','sexp-depth.lisp'):
            assert (ROOT/'lib'/name).read_bytes()==(CAND/'src'/name).read_bytes()
        save(BUILD/'source.json',dict(inputs=[bind(ROOT/'lib'/n) for n in ('repl-comfort-v250.lisp','lite-hot.lisp','lite.lisp','sexp-depth.lisp','stdlib-read-line.lisp')]+[bind(SUITE)],candidate=bind(CAND/'bindings.json'), r2_reference=bind(PREFLIGHT/'price.json'), batch_sources=[bind(ROOT/n) for n in ('src/vm.c','src/optional/c2_kernal_input_consumer.s','src/optional/c2_kernal_input_capture.s','src/c2_kernal_window_equates.inc')]))
        identity=load(FINAL/'final-identity.json')
        runtime=[]
        for item in identity['artifacts']:
            raw=checked(item['final']);runtime_control(checked(item['seed']),raw)
            dest=BUILD/'wplto'/Path(item['final']['path']).name
            once(dest,raw);runtime.append(dict(baseline=item['final'],successor=bind(dest),byteidentical=True))
        before_raw=checked(identity['media'][0]['final'])
        assert sha(before_raw)==BASE_MEDIA_SHA
        # Frozen compiler flags prove the buffer primitive arms are delivered.
        commands=load(ROOT/'build/strings-r7/seed/command-proof.json')['commands']
        vm=[c for c in commands if '-c' in c and c[c.index('-c')+1].endswith('/vm.c')]
        assert len(vm)==1 and '-DLISP65_FIRST_CLASS_BUFFER' in vm[0]
        assert not any('LISP65_BUFFER_NO_PRIMS' in a for a in vm[0])
        save(BUILD/'runtime-identity.json',dict(status='PASS',artifacts=runtime,
            buffer_primitives=[63,64,65],commands=bind(ROOT/'build/strings-r7/seed/command-proof.json'),
            native_text_rodata_bss_identical=True,static_code_shelf_c2d_identical=True))
        save(BUILD/'negative-controls.json',selftest())
        price=emit(BUILD/'emission');save(BUILD/'price.json',price)
        manifest=BUILD/'emission/candidate/repl-comfort.manifest.json'
        before=D.visible_files(before_raw);rows=L.decode_index(before[b'L65INDEX'])
        old=next(r for r in rows if r['name']=='repl-comfort')
        build_id=int(load(ROOT/'build/strings-r7/seed/plane-price.json')['after_product']['product_build_id_hex'],16)
        row,payload=PK.measured_row('repl-comfort','repl-comfort','repl',manifest,(),old['track'],old['sector'],product_build_id=build_id)
        assert {k:row[k] for k in ('artifact_bytes','bank2','entries','resolutions','roots','scratch')} == dict(artifact_bytes=5197,bank2=2905,entries=24,resolutions=155,roots=35,scratch=192)
        image=F.emit_image('repl-comfort','repl',manifest)
        assert len(image.metadata)==2228
        once(BUILD/'emission/candidate/repl-comfort.c2i',image.metadata)
        once(BUILD/'emission/candidate/repl-comfort.l65s',payload)
        allrows=[row if r['name']=='repl-comfort' else r for r in rows]
        cap={k:base+sum(r[field] for r in allrows) for k,field,base in [('code','bank2',50007),('entries','entries',785),('resolutions','resolutions',3082),('roots','roots',378),('images','images',6)]}
        limits=dict(code=60758,entries=2048,resolutions=4096,roots=1536,images=64)
        assert all(cap[k]<=limits[k] for k in cap)
        scratch = sum(r['scratch'] for r in allrows)
        assert scratch <= 50752-33840
        save(BUILD/'capacity.json',dict(status='PASS',used=cap,limits=limits,entry_scratch_sum=scratch,entry_scratch_limit=50752-33840,symbols=symbol_capacity(commands,manifest),geometry=bind(CAND/'geometry.json')))
        med=BUILD/'media-r2';med.mkdir()
        media=pack(before_raw,payload,row,build_id,med)
        save(BUILD/'media.json',media)
        save(BUILD/'inventory.json',dict(status='PASS',runtime_changed_bytes=0,shared_changed_bytes=0,
            d81_changed_bytes=media['changed_bytes'],unclassified_bytes=0,diff=bind(med/'d81-byte-diff.json')))
        save(BUILD/'seed.json',dict(status='PASS',seed=1,final=0,product_links=0,
            medium=media['medium'],receipts=[bind(BUILD/n) for n in ('attempt.json','source.json','runtime-identity.json','negative-controls.json','price.json','capacity.json','media.json','inventory.json')]))
        return media['medium']
    except BaseException as error:
        save(BUILD/'halt.json',dict(status='HALT',error=repr(error)))
        raise


if __name__=='__main__':
    assert os.environ.get('PYTHONDONTWRITEBYTECODE')=='1'
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['selftest','seed','host',
        'r3-prepare','r3-selftest','r3-seed','r3-inventory','r3-media','r3-finish'])
    action=parser.parse_args().action
    if action.startswith('r3-'):
        import o2_lite_r3_product as r3
        result=getattr(r3,action[3:])()
    else:
        result=globals()[action]()
    print(json.dumps(result,indent=2))
