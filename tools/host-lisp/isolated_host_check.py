"""Run a host oracle in an isolated, same-logical-path scratch world.

Only enumerated generated output trees are writable copies. Repository
sources and historical receipts stay read-only. Logical paths are unchanged,
so existing artifact/content oracles are not normalized to make them pass.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
WORKSPACES = {
    'random': ['build/post-promotion/phase-v/random-base/gate'],
    'banner-media': ['build/c2.3/v2.0-block3-banner-repair-device-media'],
    'codemod': ['build/bytecode/dialect-v2'],
    'banner': ['build/bytecode/dialect-v2',
               'build/c2.3/v2.0-block3-banner-only-repair-preflight-check',
               'build/c2.3/v2.0-block3-banner-only-repair-preflight-check-historical-ide-codemod'],
    'q': ['build/post-promotion/v124/q/host-first'],
    'time': ['build/post-promotion/v124/time/host-first'],
    'm65-hw': ['build/post-promotion/v14/m65-hw/host-first'],
    'option-a': ['build/post-promotion/require-resolver/l65i-v1',
                 'build/post-promotion/workbench-era/require-v1-host-probe',
                 'build/post-promotion/require-option-A-fresh-fixtures',
                 'build/c2-lite/product-shaped-v6-probe'],
    'storage': ['build/storage-owner-preflight-check'],
    'resolver': ['build/resolver-owner-check', 'build/transient-retirement-guard-check'],
    'index-crc': ['build/index-crc-check'],
    'overlay-transaction': ['build/overlay-transaction-check'],
    # Ship Builder regenerates the shared stager include (bound by sealed
    # media-builder receipts) and writes its fleet/repro trees.
    'ship-builder': ['build/generated', 'build/ship-builder-check'],
}


def inside(command):
    guard = ROOT/'mk/gates.mk'
    before = guard.read_bytes()
    try:
        fd = os.open(guard, os.O_WRONLY)
    except OSError as error:
        import errno
        if error.errno not in (errno.EROFS, errno.EACCES):
            raise
    else:
        os.close(fd)
        raise RuntimeError('original-write mutation survived')
    if guard.read_bytes() != before:
        raise RuntimeError('write probe changed protected source')
    print('isolated host oracle: rejected-original-write=1', flush=True)
    return subprocess.call(command, cwd=ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', choices=WORKSPACES)
    parser.add_argument('--inside', action='store_true')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == '--': command = command[1:]
    if not command: parser.error('missing oracle command')
    if args.inside: return inside(command)
    if not args.workspace: parser.error('missing workspace')
    # A containing oracle already owns its complete generated population.
    inherited = json.loads(os.environ.get('LISP65_ISOLATED_HOST_ROOTS', '[]'))
    requested = WORKSPACES[args.workspace]
    if inherited and all(any(p == old or p.startswith(old+'/') for old in inherited) for p in requested):
        return inside(command)
    base = Path(os.environ.get('LISP65_CHECK_SCRATCH_ROOT', str(ROOT/'build/isolated-host-checks')))
    base.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=args.workspace+'-', dir=base))
    output = ROOT/'build/check-result-successors'
    output.mkdir(parents=True, exist_ok=True)
    roots = requested + ['build/check-result-successors']
    mounts = []
    for i, relative in enumerate(roots):
        source = ROOT/relative
        source.mkdir(parents=True, exist_ok=True)
        target = work/str(i)
        if relative == 'build/check-result-successors': target.mkdir()
        else: shutil.copytree(source, target, symlinks=True)
        mounts += ['--bind', str(target), str(source)]
    invocation = ['bwrap', '--die-with-parent', '--unshare-user', '--ro-bind', '/', '/',
        '--dev-bind', '/dev', '/dev', '--proc', '/proc', '--bind', '/tmp', '/tmp',
        '--bind', str(work), str(work), *mounts, '--chdir', str(ROOT),
        '--setenv', 'PYTHONDONTWRITEBYTECODE', '1', '--setenv', 'LISP65_ISOLATED_HOST_ROOTS',
        json.dumps(roots), '--setenv', 'LISP65_CHECK_SCRATCH_ROOT', str(work),
        '--', sys.executable, '-B', str(Path(__file__).resolve()),
        '--inside', '--', *command]
    result = subprocess.call(invocation, cwd=ROOT)
    (work/'execution.json').write_text(json.dumps(dict(command=command,
        writable_copies=roots, exit_code=result, historical_receipts_rewritten=0,
        boundary='Fresh host oracle, same logical paths; no historical reproduction claim'), indent=2)+'\n')
    print('isolated host workspace: '+str(work), flush=True)
    return result


if __name__ == '__main__':
    raise SystemExit(main())
