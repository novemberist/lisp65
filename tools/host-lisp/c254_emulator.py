#!/usr/bin/env python3
"""Run the reviewer instruments with the pinned 2.5.4 Seed medium, in memory.

Successor of c253_emulator.py.  The world is the Seed named by c254_final_pins.SEED_NAME (the receipt
directory of the continued Seed, build/card-254-product-<attempt>: medium media-254/c254.d81 and wplto/resident-island-seed.prg.elf, both
bound by the pinned sha256; the Final must be byte-identical to it).  While the pins are placeholders every
emulator mode refuses before any emulator starts (fail closed).  Nothing is built.

Modes
  rows       Comfort rows (comfort_default_rows.main, medium role 'lite')
  backspace  Backspace rows (backspace_rows.main)
  lanes      typing-cost lane (comfort_default_lanes.main)
  return     Return timing probe
  gcstress   c254_gc_stress forced-collection scenario (--scenario S --out build/DIR)
  new        the 2.5.4 rows and the 2.5.3 regression rows (c254_rows.py):
             new <out-dir-under-build> --session all | repl,lib1,oom-rp1,e3,seam,disk-h,d703,reg-repl,reg-disk,reg-ide,reg-oom
             The e3 group and the seam group are separate sessions = separate boots.
  control    the same driver on the 2.5.3 Seed r8 (c254_config.BASE, hash-checked): negative control for the
             E3 / HIST1 / closure rows and the timing reference for the save rows.  Never a product verdict.
             control <out-dir-under-build> --session e3,repl,reg-disk [--groups ...]
  plan       no emulator, no pins needed: print the session/row plan (c254_rows.plan)
  Use e.g.  c254_emulator.py rows card-254-rows-r1/comfort --medium lite
            c254_emulator.py new card-254-rows-r1/new --session all
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def _root():
    for p in Path(__file__).resolve().parents:
        if (p / '.git').exists():
            return p
    raise RuntimeError('repository root not found')


ROOT = _root()
sys.path.insert(0, str(ROOT / 'tools/host-lisp'))
import c254_config as CFG  # noqa: E402
import c254_final_pins as PINS  # noqa: E402  (no side effects; the pins name the Seed)
SEED = PINS.SEED_NAME
MEDIUM_PATH = ROOT / SEED / PINS.ARTIFACT_PATH['D81']
MEDIUM_SHA = PINS.ARTIFACT_SHA['D81']
ELF_PATH = ROOT / SEED / PINS.ARTIFACT_PATH['ELF']
ELF_SHA = PINS.ARTIFACT_SHA['ELF']
EMULATOR_MODES = ('rows', 'backspace', 'lanes', 'return', 'gcstress', 'new', 'control')


def bind(path):
    path = Path(path)
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def world(role='lite'):
    """(medium, medium sha256, ELF, ELF sha256); fails before any emulator starts."""
    if role == 'control-253r8':
        medium = ROOT / CFG.BASE / CFG.BASE_MEDIA_DIR / CFG.BASE_MEDIA_NAME
        elf = ROOT / CFG.BASE / PINS.ARTIFACT_PATH['ELF']
        if bind(medium)['sha256'] != CFG.BASE_MEDIUM_SHA or bind(elf)['sha256'] != CFG.BASE_ELF_SHA:
            raise ValueError('2.5.3 Seed r8 control world drift')
        return medium, CFG.BASE_MEDIUM_SHA, elf, CFG.BASE_ELF_SHA
    if role != 'lite':
        raise ValueError('only the pinned Seed world and the 2.5.3 control world are bound')
    if not (MEDIUM_SHA and ELF_SHA):
        raise ValueError('c254_final_pins.py names no Seed medium/ELF yet (PLACEHOLDER-AFTER-SEED)')
    found = PINS.problems(ROOT)
    if found:
        raise ValueError('Final pins do not match the Seed: ' + '; '.join(found))
    complete = json.loads((ROOT / SEED / 'complete.json').read_text())
    if complete['medium']['sha256'] != MEDIUM_SHA or complete['ELF']['sha256'] != ELF_SHA:
        raise ValueError('complete.json does not bind the pinned Seed medium/ELF')
    if bind(MEDIUM_PATH)['sha256'] != MEDIUM_SHA or bind(ELF_PATH)['sha256'] != ELF_SHA:
        raise ValueError('pinned Seed artifact drift')
    return MEDIUM_PATH, MEDIUM_SHA, ELF_PATH, ELF_SHA


def idle():
    """House rule: an emulator session never overlaps a sealed run, a producer, the Final or another emulator
    of this checkout.  Read-only process listing; nothing is signalled."""
    text = subprocess.check_output(['ps', '-eo', 'pid,args'], text=True)
    needles = ('sealed_check_run.py', 'make -k check-source', 'make -k check-host', 'c254_seed_producer.py',
               'c254_seed_continue_r1b.py', 'c254_final.py',
               'c254_seal.py', 'c254_replay.py', 'c254_final_rehearsal.py', 'c254_emulator.py', 'c254_gc_stress.py',
               'c253_emulator.py', 'c253_seed_producer.py')
    for line in text.splitlines()[1:]:
        fields = line.strip().split(None, 1)
        if len(fields) != 2 or int(fields[0]) in (os.getpid(), os.getppid()):
            continue
        program = Path(fields[1].split()[0]).name
        if program.startswith(('python', 'make', 'gmake')) and any(n in fields[1] for n in needles):
            raise ValueError('another producer / sealed run / emulator session is active; refused: ' + fields[1][:120])
        if program.startswith('xmega65') and str(ROOT) in fields[1]:
            raise ValueError('an emulator of this checkout is already running; refused (one Xemu at a time)')


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    args = sys.argv[2:]
    if mode == 'plan':
        import c254_rows as X
        print(json.dumps(X.plan(), indent=1))
        return
    if mode not in EMULATOR_MODES:
        raise ValueError('expected one of: plan, ' + ', '.join(EMULATOR_MODES))
    label = 'control-253r8' if mode == 'control' else 'lite'
    medium, medium_sha, elf, elf_sha = world(label)  # fail before starting any emulator
    idle()
    seed = CFG.BASE if mode == 'control' else SEED
    # c254_rows installs the patient monitor transport in memory; the legacy instruments below use the same
    # Monitor class, so they get it too (their files are not edited; see the transport note in c254_rows.py)
    import c254_rows as X
    header = dict(seed=seed, medium=bind(medium), ELF=bind(elf), instrument=mode, transport=X.TRANSPORT)
    if mode in ('new', 'control'):
        X.WORLD.update(label='seed' if mode == 'new' else label, medium=medium, medium_sha=medium_sha, elf=elf, elf_sha=elf_sha)
        print(json.dumps(header, indent=2), flush=True)
        sys.exit(X.main(['run', *args]))
    import comfort_default_rows as D
    import backspace_rows as B
    D.WORLD['lite'] = (medium, medium_sha, elf)
    D.ELF_SHA[elf] = elf_sha
    B.WORLD['lite'] = D.WORLD['lite'][:2]
    if mode == 'rows':
        fn = D.main
    elif mode == 'backspace':
        fn = B.main
    elif mode == 'lanes':
        import comfort_default_lanes as LN
        fn = LN.main
    elif mode == 'return':
        source = ROOT / 'build/lite-throughput-probe-r1/probe4.py'
        scope = dict(__name__='o2_final_return', __file__=str(source))
        exec(compile(source.read_text(), str(source), 'exec'), scope)
        scope['WORLD']['lite'] = D.WORLD['lite'][:2]
        scope['WORLD']['strings'] = D.WORLD['strings'][:2]
        fn = scope['main']
    else:   # gcstress: forced-collection sweep (c254_gc_stress.run_case) on the pinned Seed world
        import argparse
        import c254_gc_stress as G
        G.world = lambda role: (medium, elf)
        ap = argparse.ArgumentParser()
        ap.add_argument('--scenario', required=True, choices=list(G.scenarios()))
        ap.add_argument('--out', required=True, help='directory below build/, must not exist')
        a = ap.parse_args(args)
        target = (ROOT / a.out).resolve()
        assert target.is_relative_to(ROOT / 'build')
        print(json.dumps(header, indent=2), flush=True)
        res = G.run_case('lite', a.scenario, target)
        print(json.dumps({k: v for k, v in res.items() if k not in ('collections', 'events')}, indent=1)[:4000])
        return
    sys.argv = [sys.argv[0], *args]
    print(json.dumps(header, indent=2), flush=True)
    fn()


if __name__ == '__main__':
    try:
        main()
    except ValueError as error:
        sys.exit('REFUSED: ' + str(error))
