#!/usr/bin/env python3
"""comfort-library card: cold-boot state at the first native prompt, both media.

Attributes the plain-prompt GC placement difference: reads gc_runs, freelist,
nsym and npool (ELF symbols of the one 2.4.0 ELF) at the first ready prompt on
the accepted 2.4.0 medium and on the Comfort medium, plus the boot framebuffer.
Memory reads only; no keys typed.

Usage: comfort_library_boot_probe.py <out-name>
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host-lisp'))
import dwx_retroactive_red_replay as R  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402
import comfort_library_rows as ROWS  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument('out')
    a = p.parse_args()
    out = ROOT / 'build' / a.out
    out.mkdir(exist_ok=False)
    for key, path in (('elf', ROWS.ELF), ('xemu', ROWS.XEMU), ('base', ROWS.BASE), ('medium', ROWS.MEDIUM)):
        assert R.bind(path)['sha256'] == ROWS.EXPECT[key], key
    truth = ElfTruth.read(ROWS.ELF, llvm_readobj=ROOT / 'tools/llvm-mos/bin/llvm-readobj')
    args = argparse.Namespace(xemu=ROWS.XEMU, rom=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/MEGA65.ROM')),
                              sd_image=Path(str(Path.home() / '.local/share/xemu-lgb/mega65/mega65.img')), timeout=600)

    class Monitor(R.ProbeMonitor):
        def wait_screen(self, required, timeout=20):
            return super().wait_screen(required, timeout=120)
    R.ProbeMonitor = Monitor
    result = {}
    for role, medium in (('base', ROWS.BASE), ('comfort', ROWS.MEDIUM)):
        run = R.start_run(role, medium, out, args)
        m = run['monitor']
        time.sleep(3)
        m.command('t1')
        screen = m.screen()
        (out / f'{role}-boot.txt').write_text(screen)
        v = {}
        for name in ('gc_runs', 'freelist', 'nsym', 'npool'):
            s = truth.symbol(name)
            v[name] = int.from_bytes(m.memory_range(s.value, s.bytes), 'little')
        v['framebuffer_sha256'] = hashlib.sha256(screen.encode()).hexdigest()
        v['active'] = ROWS.active(screen)
        v['outputs'] = R.finish_run(run, screen)
        v['medium'] = R.bind(medium)
        result[role] = v
        print(role, {k: v[k] for k in ('gc_runs', 'freelist', 'nsym', 'npool', 'active', 'framebuffer_sha256')}, flush=True)
    same = {k: result['base'][k] == result['comfort'][k] for k in ('gc_runs', 'freelist', 'nsym', 'npool', 'framebuffer_sha256', 'active')}
    value = dict(card='comfort-library', binding='180cb993', worlds=result, equal=same,
                 elf=R.bind(ROWS.ELF), xemu=R.bind(ROWS.XEMU), driver=R.bind(Path(__file__)),
                 claim='Emulator memory and framebuffer reads at the first ready prompt; no keys, no device')
    (out / 'receipt.json').write_text(json.dumps(value, indent=1) + '\n')
    print('equal', same)


if __name__ == '__main__':
    main()
