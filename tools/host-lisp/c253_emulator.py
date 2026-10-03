#!/usr/bin/env python3
"""Run existing reviewer instruments with the pinned 2.5.3 Seed medium, in memory.

Successor of o2_lite_emulator.py.  The world is the Seed named by c253_final_pins.py
(r8: build/card-253-product-r8 once the pins are set; the Final is byte-identical to it):
medium c253.d81 and resident-island-seed.prg.elf, both bound by the pinned sha256.
Nothing is built.  r7 world (retained): abc9bb49... / 47519653....

Modes
  rows       Comfort rows (comfort_default_rows.main, medium role 'lite')
  backspace  Backspace rows (backspace_rows.main)
  lanes      typing-cost lane (comfort_default_lanes.main)
  return     Return timing probe
  gcstress   c253_gc_stress forced-collection scenario (--scenario S --out build/DIR)
  new        the new 2.5.3 rows (c253_rows.main), sessions: repl | disk | ide | oom
             (r8: + F2 form / nesting ladder rows in repl, OOM recovery rows in oom and disk C-100x40)
  Use e.g.  c253_emulator.py rows card-253-rows-r7/comfort --medium lite
            c253_emulator.py new card-253-rows-r7/new
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host-lisp'))
import c253_final_pins as PINS  # noqa: E402  (no side effects; the pins name the Seed)
SEED = PINS.SEED_NAME
MEDIUM_PATH = ROOT / SEED / PINS.ARTIFACT_PATH['D81']
MEDIUM_SHA = PINS.ARTIFACT_SHA['D81']
ELF_PATH = ROOT / SEED / PINS.ARTIFACT_PATH['ELF']
ELF_SHA = PINS.ARTIFACT_SHA['ELF']


def bind(path):
    path = Path(path)
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def world(role='lite'):
    if role != 'lite':
        raise ValueError('only the pinned Seed world is bound')
    if not (MEDIUM_SHA and ELF_SHA):
        raise ValueError('c253_final_pins.py names no Seed medium/ELF yet ([SET-AFTER-SEED])')
    complete = json.loads((ROOT / SEED / 'complete.json').read_text())
    if complete['medium']['sha256'] != MEDIUM_SHA or complete['ELF']['sha256'] != ELF_SHA:
        raise ValueError('complete.json does not bind the pinned Seed medium/ELF')
    if bind(MEDIUM_PATH)['sha256'] != MEDIUM_SHA or bind(ELF_PATH)['sha256'] != ELF_SHA:
        raise ValueError('pinned Seed artifact drift')
    return MEDIUM_PATH, ELF_PATH


def main():
    medium, elf = world('lite')  # fail before starting any emulator
    import comfort_default_rows as D
    import backspace_rows as B
    D.WORLD['lite'] = (medium, MEDIUM_SHA, elf)
    D.ELF_SHA[elf] = ELF_SHA
    B.WORLD['lite'] = D.WORLD['lite'][:2]
    mode = sys.argv[1]
    args = sys.argv[2:]
    if mode == 'rows':
        fn = D.main
    elif mode == 'backspace':
        fn = B.main
    elif mode == 'lanes':
        import comfort_default_lanes as L
        fn = L.main
    elif mode == 'return':
        source = ROOT / 'build/lite-throughput-probe-r1/probe4.py'
        scope = dict(__name__='o2_final_return', __file__=str(source))
        exec(compile(source.read_text(), str(source), 'exec'), scope)
        scope['WORLD']['lite'] = D.WORLD['lite'][:2]
        scope['WORLD']['strings'] = D.WORLD['strings'][:2]
        fn = scope['main']
    elif mode == 'gcstress':
        # forced-collection sweep (c253_gc_stress.run_case) on the Seed r7 world
        import argparse
        import c253_gc_stress as G
        G.world = lambda role: (medium, elf)
        ap = argparse.ArgumentParser()
        ap.add_argument('--scenario', required=True, choices=list(G.scenarios()))
        ap.add_argument('--out', required=True, help='directory below build/, must not exist')
        a = ap.parse_args(args)
        target = (ROOT / a.out).resolve()
        assert target.is_relative_to(ROOT / 'build')
        print(json.dumps(dict(seed=SEED, medium=bind(medium), ELF=bind(elf), instrument=mode), indent=2), flush=True)
        res = G.run_case('lite', a.scenario, target)
        print(json.dumps({k: v for k, v in res.items() if k not in ('collections', 'events')}, indent=1)[:4000])
        return
    elif mode == 'new':
        import c253_rows as X
        X.WORLD.update(medium=medium, medium_sha=MEDIUM_SHA, elf=elf, elf_sha=ELF_SHA)
        fn = X.main
    else:
        raise ValueError('expected rows, backspace, lanes, return or new')
    sys.argv = [sys.argv[0], *args]
    print(json.dumps(dict(seed=SEED, medium=bind(medium), ELF=bind(elf), instrument=mode), indent=2), flush=True)
    fn()


if __name__ == '__main__':
    main()
