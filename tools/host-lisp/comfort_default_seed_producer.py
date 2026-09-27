#!/usr/bin/env python3
"""Comfort Seed: nested_error_recovery_producer's admission/write-once pattern.

Replay its Final's recorded canonical constructor (73 TUs, llvm-link, product
link), rather than recapturing the now unrelated HEAD constructor. All consumed
inputs are restored by hash; only the committed Comfort repl.c is substituted.
command-probe is budget-free; seed requires both non-LTO pre-probes and consumes
one attempt before executing any product command. No implicit retry or Final.
"""
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
AUTH = '1447e988'
DIFF_BASE = '90b5f9f2'
HERE = ROOT/'build/comfort-default-r2/seed'
BUILD = ROOT/'build/comfort-default-product-r2'
FINAL = ROOT/'build/nested-error-recovery-final-r1'
TRANSCRIPT = FINAL/'final-command-includes-retained-callable-repair-r2.json'
BASE_SHA = '66165507a8e5ad1d857afdd967f9056be2ce7bbccc332d5328e981398078b47b'
REPL = 'build/nested-error-recovery-product-r1/wplto/generated-product-sources/repl.c'
SOURCE = ROOT/'config/comfort-default-native/sources/repl.c'
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bind(p):
    p = Path(p)
    b = p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)), bytes=len(b), sha256=sha(b))


def once(p, data):
    if isinstance(data, str):
        data = data.encode()
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        assert p.read_bytes() == data, str(p)
    else:
        p.write_bytes(data)


def save(p, value):
    once(p, json.dumps(value, indent=2)+'\n')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, env=ENV)


def command_probe():
    subprocess.run(['git', 'merge-base', '--is-ancestor', AUTH, 'HEAD'], cwd=ROOT, env=ENV, check=True)
    assert git('diff', '--name-only', AUTH, 'HEAD').decode().split() in ([], ['tools/host-lisp/comfort_default_seed_producer.py'])
    assert not git('status', '--porcelain', '--untracked-files=no').strip()
    assert json.loads((FINAL/'final-invocation.json').read_text())['authority'] == DIFF_BASE
    assert bind(FINAL/'wplto/lisp65-c2-substitution-linked.prg.elf')['sha256'] == BASE_SHA
    assert SOURCE.read_bytes() == git('show', AUTH+':'+str(SOURCE.relative_to(ROOT)))
    transcript = json.loads(TRANSCRIPT.read_text())
    baseline = json.loads((ROOT/'build/comfort-default-r1/baseline-authority.json').read_text())
    assert baseline['command_receipt'] == bind(TRANSCRIPT)
    assert {r['consumed']['path']:r['consumed'] for r in baseline['rows']} == {r['path']:r for r in transcript['authority']}
    snapshot = HERE/'inputs'
    rows = []
    for r in baseline['rows']:
        origin = r['exact_origin']
        if origin.startswith('git:'):
            _, rev, path = origin.split(':', 2)
            data = git('show', rev+':'+path)
        else:
            data = (ROOT/origin).read_bytes()
        assert len(data) == r['consumed']['bytes'] and sha(data) == r['consumed']['sha256'], origin
        target = snapshot/r['consumed']['path']
        once(target, data)
        rows.append(dict(consumed=r['consumed'], restored=bind(target)))
    original = (snapshot/REPL).read_text()
    patch = ''.join(difflib.unified_diff(original.splitlines(True), SOURCE.read_text().splitlines(True), fromfile=REPL, tofile=str(SOURCE.relative_to(ROOT))))
    assert 'lisp65_comfort_state' in patch and 'evaluate_line' in patch
    # Replacement authority: lookup-free (Seed 1 paid +302 for sym_lookup de-inlining).
    assert not any('sym_lookup' in l for l in patch.splitlines() if l.startswith('+'))
    once(HERE/'resident-hook.patch', patch)
    # Linker files come from the committed, hash-bound Final projection.
    manifest = json.loads((ROOT/'config/comfort-default-native/manifest.json').read_text())
    # The baseline keeps the Final's linker files; the Seed's full-map-linker
    # directory differs only by the owned high-BSS byte in c.ld.
    linker = HERE/'linker-comfort'
    changed_linker = []
    for r in manifest['linker']:
        p = ROOT/r['path']
        assert bind(p) == r
        rel = p.relative_to(ROOT/'config/comfort-default-native/linker')
        old = FINAL/'wplto'/rel
        once(snapshot/old.relative_to(ROOT), old.read_bytes())
        once(linker/rel, p.read_bytes())
        if p.read_bytes() != old.read_bytes():
            changed_linker.append(str(rel))
            ldiff = list(difflib.unified_diff(old.read_text().splitlines(True), p.read_text().splitlines(True), fromfile=str(old.relative_to(ROOT)), tofile=r['path']))
            assert [l[1:].strip() for l in ldiff if l.startswith('-') and not l.startswith('---')] == ['__bss_end = .;']
            assert 'lisp65_comfort_state' in ''.join(ldiff)
            once(HERE/'linker-owner.patch', ''.join(ldiff))
    assert changed_linker == ['full-map-linker/c.ld'], changed_linker
    for r in json.loads((ROOT/'config/comfort-default-native/include-closure.json').read_text())['rows']:
        assert sha((ROOT/r['successor']).read_bytes()) == r['sha256'] == r['consumed']['sha256']
    once(HERE/'repl.c', SOURCE.read_bytes())
    oldout = str(FINAL.relative_to(ROOT)/'wplto')
    newout = str(BUILD.relative_to(ROOT)/'wplto')
    prefix = str(snapshot.relative_to(ROOT))+'/'
    def rebase(arg):
        # Inputs retain their original relative directory structure. Output
        # objects and final artifacts have their own product directory.
        if arg.startswith(oldout+'/.canonical-objects-'):
            return arg.replace(oldout, newout, 1)
        if arg.startswith('-Wl,--lto-obj-path=') or arg.startswith('-Wl,-Map='):
            return arg.replace(oldout+'/lisp65-c2-substitution-linked', newout+'/resident-island-seed')
        if arg == oldout+'/lisp65-c2-substitution-linked.prg':
            return newout+'/resident-island-seed.prg'
        for token in ('build/', 'src'):
            if arg.startswith(token):
                return prefix+arg
            if arg.startswith('-Wl,-L,'+token) or arg.startswith('-Wl,-T,'+token):
                a, b, p = arg.split(',', 2)
                return a+','+b+','+prefix+p
        return arg
    baseline_commands = [[rebase(a) for a in c] for c in transcript['commands']]
    old_l = '-Wl,-L,'+prefix+oldout+'/full-map-linker'
    new_l = '-Wl,-L,'+str((linker/'full-map-linker').relative_to(ROOT))
    commands = [[str((HERE/'repl.c').relative_to(ROOT)) if a == prefix+REPL else new_l if a == old_l else a for a in c] for c in baseline_commands]
    assert len(commands) == 75
    changes = [(i,a,b) for i,(ca,cb) in enumerate(zip(baseline_commands,commands)) for a,b in zip(ca,cb) if a!=b]
    assert [c[0] for c in changes]==[18,74] and changes[1][1]==old_l, changes
    assert not any('SET_B' in a or 'BANK5_LATE' in a for c in commands for a in c)
    for label, cmds in [('baseline-command-proof',baseline_commands),('command-proof',commands)]:
        save(HERE/(label+'.json'), dict(status='COMMAND PROBE ONLY',commands=cmds,authority=[x['restored'] for x in rows],predecessor=bind(TRANSCRIPT)))
    save(HERE/'command-ready.json',dict(status='PASS',authority=AUTH,diff_base=DIFF_BASE,
         predecessor=bind(TRANSCRIPT),source=bind(SOURCE),driver=bind(Path(__file__).resolve()),
         patch=bind(HERE/'resident-hook.patch'),linker_patch=bind(HERE/'linker-owner.patch'),changed_translation_units=['repl.c'],changed_linker=changed_linker,
         closure=rows,command_proof=bind(HERE/'command-proof.json'),
         baseline_proof=bind(HERE/'baseline-command-proof.json'),seed=0,final=0,product_link=0))


def run_logged(command, log):
    with log.open('w') as f:
        result = subprocess.run(command,cwd=ROOT,env=ENV,stdout=f,stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'HALT command exit {result.returncode}; see {log}')


def preprobes():
    command_probe()
    tool = str(ROOT/'tools/host-lisp/boot_name_index_link_preprobe.py')
    run_logged([sys.executable,tool,'--proof',str(HERE/'command-proof.json'),'--baseline',str(HERE/'baseline-command-proof.json'),'--out',str(HERE/'link-preprobe')],HERE/'link-preprobe.log')
    link = HERE/'link-preprobe/receipt.json'
    assert json.loads(link.read_text())['status']=='PASS'
    run_logged([sys.executable,tool,'--e000-objects',str(HERE/'link-preprobe/main/objects'),'--e000-baseline-objects',str(HERE/'link-preprobe/baseline/objects'),'--out',str(HERE/'e000-preprobe')],HERE/'e000-preprobe.log')
    e000 = HERE/'e000-preprobe/e000-low-edges-receipt.json'
    assert json.loads(e000.read_text())['status']=='PASS'
    evidence=[bind(p) for p in [HERE/'command-ready.json',HERE/'command-proof.json',link,e000,SOURCE,Path(__file__).resolve()]]
    save(HERE/'preflight-admission.json',dict(status='PASS',authority=AUTH,evidence=evidence))


def seed():
    a=json.loads((HERE/'preflight-admission.json').read_text())
    assert a['status']=='PASS' and a['authority']==AUTH
    for row in a['evidence']:
        assert bind(ROOT/row['path'])==row,row['path']
    ready=json.loads((HERE/'command-ready.json').read_text())
    for row in ready['closure']:
        assert bind(ROOT/row['restored']['path'])==row['restored']
    assert not BUILD.exists(), 'Seed output already exists; no implicit retry'
    BUILD.mkdir()
    save(BUILD/'attempt.json',dict(authority=AUTH,seed=1,final=0,product_link_attempts=1))
    commands=json.loads((HERE/'command-proof.json').read_text())['commands']
    for i,c in enumerate(commands):
        if '-o' in c:
            (ROOT/c[c.index('-o')+1]).parent.mkdir(parents=True,exist_ok=True)
        run_logged(c,BUILD/f'command-{i:02d}.log')
    save(BUILD/'seed.json',dict(status='LINKED; PRICE AND INVENTORY PENDING',authority=AUTH,diff_base=DIFF_BASE,
        ELF=bind(BUILD/'wplto/resident-island-seed.prg.elf'),commands_consumed=len(commands)))


if __name__=='__main__':
    assert os.environ.get('PYTHONDONTWRITEBYTECODE')=='1'
    assert len(sys.argv)==2 and sys.argv[1] in ('command-probe','preprobes','seed')
    {'command-probe':command_probe,'preprobes':preprobes,'seed':seed}[sys.argv[1]]()
