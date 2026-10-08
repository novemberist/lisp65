#!/usr/bin/env python3
"""Run the reviewer instruments with the pinned 2.5.5 Seed medium, in memory.

Successor of c254_emulator.py (imported, never edited).  The world is the Seed build/card-255-product-r1b
(medium media-255/c255.d81, ELF wplto/resident-island-seed.prg.elf, both bound by sha256 and by the Seed's
complete.json).  The control world is the 2.5.4 Final build/card-254-final-r1 (final-identity.json).
Nothing is built.

Modes
  new        the 2.5.5 rows and the unchanged 2.5.4 / 2.5.3 rows (c255_rows.py):
             new <out-dir-under-build> --session all | l2,typing,repl,lib1,oom-rp1,e3,seam,disk-h,d703,
                                                       reg-repl,reg-disk,reg-ide,reg-oom,reg-oom-b [--rows ...] [--groups ...]
  control    the same driver on the 2.5.4 Final: reference for a row that differs.  Never a product verdict.
  rows       Comfort rows (comfort_default_rows.main, medium role 'lite')
  backspace  Backspace rows (backspace_rows.main)
  lanes      typing-cost lane (comfort_default_lanes.main)
  plan       no emulator: print the session / row plan (c255_rows.plan)
  Use e.g.  c255_emulator.py new card-255-rows-r1/l2 --session l2
            c255_emulator.py rows card-255-rows-r1/comfort --medium lite
"""
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
import c254_emulator as E4  # noqa: E402  (history: read, never edited; its world() is NOT used)
EMULATOR_MODES = ('rows', 'backspace', 'lanes', 'new', 'control')
NEEDLES = ('sealed_check_run.py', 'make -k check-source', 'make -k check-host', 'c255_seed_producer.py', 'c255_seed_continue_r1b.py',
           'c255_product.py', 'c255_emulator.py', 'c255_gc_session', 'c254_gc_session', 'c254_gc_stress.py', 'c254_emulator.py',
           'c254_seed_producer.py', 'c254_final.py', 'c254_seal.py', 'c254_replay.py', 'c253_emulator.py')


def world(role='seed'):
    """(medium, medium sha256, ELF, ELF sha256); fails before any emulator starts."""
    import c255_rows as X
    if role == 'control-254':
        w = X.CONTROL
        identity = {r['role']: r['final'] for r in json.loads((ROOT / w['name'] / 'final-identity.json').read_text())['artifacts']}
        if identity['D81']['sha256'] != w['medium_sha'] or identity['ELF']['sha256'] != w['elf_sha'] or \
                identity['D81']['path'] != w['medium'] or identity['ELF']['path'] != w['elf']:
            raise ValueError('final-identity.json does not bind the 2.5.4 Final control world')
    elif role == 'seed':
        w = X.SEED
        complete = json.loads((ROOT / w['name'] / 'complete.json').read_text())
        if complete['medium']['sha256'] != w['medium_sha'] or complete['ELF']['sha256'] != w['elf_sha']:
            raise ValueError('complete.json does not bind the pinned 2.5.5 Seed medium/ELF')
    else:
        raise ValueError('only the pinned 2.5.5 Seed world and the 2.5.4 Final control world are bound')
    medium, elf = ROOT / w['medium'], ROOT / w['elf']
    if E4.bind(medium)['sha256'] != w['medium_sha'] or E4.bind(elf)['sha256'] != w['elf_sha']:
        raise ValueError('pinned artifact drift: ' + w['name'])
    return medium, w['medium_sha'], elf, w['elf_sha']


def idle():
    """House rule: an emulator session never overlaps a sealed run, a producer, a GC session or another emulator
    of this checkout.  Read-only process listing; nothing is signalled."""
    text = subprocess.check_output(['ps', '-eo', 'pid,args'], text=True)
    for line in text.splitlines()[1:]:
        fields = line.strip().split(None, 1)
        if len(fields) != 2 or int(fields[0]) in (os.getpid(), os.getppid()):
            continue
        program = Path(fields[1].split()[0]).name
        if program.startswith(('python', 'make', 'gmake')) and any(n in fields[1] for n in NEEDLES):
            raise ValueError('another producer / sealed run / emulator session is active; refused: ' + fields[1][:120])
        if program.startswith('xmega65') and str(ROOT) in fields[1]:
            raise ValueError('an emulator of this checkout is already running; refused (one Xemu at a time)')


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    args = sys.argv[2:]
    import c255_rows as X
    if mode == 'plan':
        print(json.dumps(X.plan(), indent=1))
        return
    if mode not in EMULATOR_MODES:
        raise ValueError('expected one of: plan, ' + ', '.join(EMULATOR_MODES))
    label = 'control-254' if mode == 'control' else 'seed'
    medium, medium_sha, elf, elf_sha = world(label)  # fail before starting any emulator
    idle()
    X4 = X.X4
    header = dict(seed=X.CONTROL['name'] if mode == 'control' else X.SEED['name'], medium=E4.bind(medium), ELF=E4.bind(elf),
                  instrument=mode, transport=X4.TRANSPORT)
    if mode in ('new', 'control'):
        X4.WORLD.update(label=label, medium=medium, medium_sha=medium_sha, elf=elf, elf_sha=elf_sha)
        print(json.dumps(header, indent=2), flush=True)
        sys.exit(X.main(['run', *args]))
    # legacy instruments: same Monitor class, so they get the patient transport of c254_rows (files not edited)
    import comfort_default_rows as D
    import backspace_rows as B
    D.WORLD['lite'] = (medium, medium_sha, elf)
    D.ELF_SHA[elf] = elf_sha
    B.WORLD['lite'] = D.WORLD['lite'][:2]
    if mode == 'rows':
        fn = D.main
    elif mode == 'backspace':
        fn = B.main
    else:
        import comfort_default_lanes as LN
        fn = LN.main
    sys.argv = [sys.argv[0], *args]
    print(json.dumps(header, indent=2), flush=True)
    fn()


if __name__ == '__main__':
    try:
        main()
    except ValueError as error:
        sys.exit('REFUSED: ' + str(error))
