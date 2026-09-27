#!/usr/bin/env python3
"""Comfort default authority/object preparation only; no Seed/Final/link entry.

Follows nested_error_recovery_producer's explicit authority, predecessor,
composition and command-receipt pattern. This Step-1 successor deliberately
does not import or execute its Seed constructor. Run with
PYTHONDONTWRITEBYTECODE=1 python3 tools/host-lisp/comfort_default_producer.py objects
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'build/comfort-default-r1'
NATIVE = ROOT / 'config/comfort-default-native'
PLANE = ROOT / 'config/comfort-default-plane'
AUTH_PENDING = 'a56ca2f8edd77bc620e0ebe269dff3be1012bda9'
DIFF_BASE = AUTH_PENDING
FINAL = ROOT / 'build/nested-error-recovery-final-r1'
ELF_SHA = '66165507a8e5ad1d857afdd967f9056be2ce7bbccc332d5328e981398078b47b'
COMMANDS = FINAL / 'final-command-includes-retained-callable-repair-r2.json'


def bind(path):
    path = Path(path)
    data = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def run(argv):
    result = subprocess.run([str(x) for x in argv], cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(result.stdout)
    return result.stdout


def main():
    if sys.argv[1:] != ['objects']:
        raise SystemExit('objects only; product build commands intentionally unavailable')
    assert bind(FINAL / 'wplto/lisp65-c2-substitution-linked.prg.elf')['sha256'] == ELF_SHA
    assert run(['git', 'rev-parse', 'HEAD']).strip() == DIFF_BASE
    objects = HERE / 'objects'
    objects.mkdir(parents=True, exist_ok=True)
    receipt = json.loads(COMMANDS.read_text())
    command = next(c for c in receipt['commands'] if '-c' in c and
                   c[c.index('-c') + 1].endswith('/repl.c'))
    # Positive allowlist: the successor uses exactly the recorded definitions.
    assert not any(x.startswith('-flto') for x in command)
    baseline = ROOT / command[command.index('-c') + 1]
    expected = next(r for r in receipt['authority'] if r['path'] == str(baseline.relative_to(ROOT)))
    assert bind(baseline) == expected
    closure = json.loads((NATIVE / 'include-closure.json').read_text())
    for row in closure['rows']:
        assert bind(ROOT / row['successor'])['sha256'] == row['sha256']
    flags, i = [], 1
    while i < command.index('-c'):
        arg = command[i]
        if arg == '-include':
            flags += [arg, str(NATIVE / 'includes' / Path(command[i + 1]).name)]
            i += 2
        elif arg == '-I':
            i += 2
        else:
            flags.append(arg)
            i += 1
    # The MOS driver defaults to bitcode even without an explicit -flto.
    # Step 1 authorizes non-LTO TU objects, not a final link.
    flags += ['-fno-lto', '-I', str(NATIVE / 'includes')]
    baseline_copy = objects / 'repl-baseline.c'
    baseline_copy.write_bytes(baseline.read_bytes())
    rows = []
    for name, source in [('baseline', baseline_copy), ('candidate', NATIVE / 'sources/repl.c')]:
        target = objects / ('repl-' + name + '.o')
        argv = [command[0], *flags, '-c', str(source), '-o', str(target)]
        log = run(argv)
        (objects / ('repl-' + name + '.compile.log')).write_text(log)
        size = run([ROOT / 'tools/llvm-mos/bin/llvm-size', '-A', target])
        (objects / ('repl-' + name + '.size.txt')).write_text(size)
        symbols = run([ROOT / 'tools/llvm-mos/bin/llvm-nm', '-S', '--size-sort', target])
        (objects / ('repl-' + name + '.symbols.txt')).write_text(symbols)
        for suffix, options in [('disasm', ['-dr']), ('sections', ['-h', '-s'])]:
            (objects / ('repl-' + name + '.' + suffix + '.txt')).write_text(
                '\n'.join(line.rstrip() for line in run([ROOT / 'tools/llvm-mos/bin/llvm-objdump', *options, target]).splitlines()) + '\n')
        rows.append(dict(name=name, source=bind(source), object=bind(target), command=argv))
    argv = [sys.executable, 'tools/host-lisp/bytecode_p0_stdlib.py',
            '--emit-artifacts', str(objects / 'repl-comfort'), '--artifact-role', 'disk-lib',
            '--base-addr', '0x000000', str(PLANE / 'libraries/repl-comfort-suite.json')]
    log = run(argv)
    (objects / 'library-emission.log').write_text(log)
    write(HERE / 'object-projection.json', dict(
        status='OBJECT PROJECTION ONLY; NOT NATIVE ACCEPTANCE', AUTH_PENDING=AUTH_PENDING,
        DIFF_BASE=DIFF_BASE, predecessor=bind(COMMANDS),
        recorded_command_index=receipt['commands'].index(command),
        recorded_command=command,
        projection_rule='Exact Final -Oz/defines and hash-identical includes; add -fno-lto for TU machine objects; no link',
        compiles=rows,
        library_command=argv, product_links=0, seed=0, final=0))
    print('Object compiles and library emission complete; no product link.')


if __name__ == '__main__':
    main()
