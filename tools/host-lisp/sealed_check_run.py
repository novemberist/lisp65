"""Run a check with tracked files and receipt-named artifacts kernel-read-only.

Scratch work in build/ and /tmp remains writable. Every existing file named by
a tracked JSON receipt is protected, even if its historical SHA already drifted.
This prevents child compilers/packers bypassing a Python-only write guard.
"""
import argparse
import ctypes
import glob
import hashlib
import json
import os
import shlex
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_BASE = Path('tests/bytecode/dialect-v2/evidence/architecture-blocks')

def evidence_member(path):
    """Only frozen Set B bundle directories admit receipt-only members."""
    try: parts = path.relative_to(ROOT / EVIDENCE_BASE).parts
    except ValueError: return False
    return len(parts) > 1 and parts[0].startswith('set-b-')

def has_symlink(path):
    return any(p.is_symlink() for p in (path, *path.parents))

def binding_rows(value):
    if isinstance(value, dict):
        if isinstance(value.get('path'), str) and 'sha256' in value:
            yield value
        for child in value.values(): yield from binding_rows(child)
    elif isinstance(value, list):
        for child in value: yield from binding_rows(child)

def bindings(value):
    for row in binding_rows(value): yield row['path']

def population():
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    sealed = set()
    tracked = set(names)
    evidence_hashes = {}
    for name in names:
        if not name.endswith('.json'): continue
        try: value = json.loads((ROOT / name).read_text())
        except (OSError, ValueError): continue
        for row in binding_rows(value):
            lexical = Path(os.path.abspath(ROOT / row['path']))
            p = lexical.resolve()
            if p.is_relative_to(ROOT / 'build') and p.is_file(): sealed.add(p)
            if evidence_member(lexical) and str(lexical.relative_to(ROOT)) not in tracked:
                if has_symlink(lexical) or not lexical.is_file():
                    raise ValueError('missing or symlink seal-bound evidence: '+str(lexical))
                evidence_hashes.setdefault(lexical, set()).add(row['sha256'])
    for path, expected in evidence_hashes.items():
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual not in expected:
            raise ValueError('seal-bound evidence hash mismatch: '+str(path))
        sealed.add(path)
    return [n for n in names if n], sorted(sealed)

# Directories under build/ and the evidence tree whose complete recursive
# content is protected (no symlinks, no unprotected file) are mounted
# read-only as one directory instead of file by file: tens of thousands of
# per-file mounts, rebound again by nested bwrap workspaces, exceed
# fs.mount-max (2026-09-27, Set B evidence). Every file is still verified
# individually below; a directory mount additionally forbids new files there.
# Directories inside or above a generated world are never collapsed.
COLLAPSE_BASES = ('build', 'tests/bytecode/dialect-v2/evidence')
# Gate output directories that receive fresh scratch entries during a check
# keep per-file protection (never collapsed, nor any ancestor of them).
WRITABLE_OUTPUT_DIRS = ('build/v2.1/f011-followup-host-preflight',)

def collapse(protected, generated=()):
    pset = {str(p) for p in protected}
    root = str(ROOT)
    worlds = [str(g) for g in generated] + [str(ROOT/w) for w in WRITABLE_OUTPUT_DIRS]
    tops = set()
    for p in pset:
        rel = os.path.relpath(p, root).split(os.sep)
        for base in COLLAPSE_BASES:
            b = base.split('/')
            if rel[:len(b)] == b and len(rel) > len(b) + 1:
                tops.add(os.path.join(root, *rel[:len(b) + 1]))
    full = {}
    for top in sorted(tops):
        if has_symlink(Path(top)): continue
        for dp, dns, fns in os.walk(top, topdown=False):
            ok = bool(fns or dns) and not any(
                dp == w or dp.startswith(w + os.sep) or w.startswith(dp + os.sep) for w in worlds)
            for f in fns:
                q = os.path.join(dp, f)
                if not ok or os.path.islink(q) or q not in pset: ok = False; break
            for n in dns:
                q = os.path.join(dp, n)
                if not ok or os.path.islink(q) or not full.get(q, False): ok = False; break
            full[dp] = ok
    dirs = sorted(d for d, ok in full.items() if ok and not full.get(os.path.dirname(d), False))
    marks = set(dirs)
    covered, individual = [], []
    for p in sorted(pset):
        d = os.path.dirname(p)
        while d.startswith(root + os.sep) and d not in marks: d = os.path.dirname(d)
        (covered if d in marks else individual).append(p)
    return individual, dirs, covered

def snapshot(names):
    return {n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names if (ROOT/n).is_file()}

def selftest():
    """Mutate a synthetic world; never mount or run a child check."""
    global ROOT
    from contextlib import redirect_stdout
    from io import StringIO
    from unittest.mock import patch
    original = ROOT
    try:
        with tempfile.TemporaryDirectory() as tmp:
            ROOT = Path(tmp)
            bundle = ROOT / EVIDENCE_BASE / 'set-b-test'
            bundle.mkdir(parents=True)
            (bundle.parent/'unprotected-neighbor').write_text('scratch')
            member = bundle/'tracked'
            member.write_text('tracked')
            protected = {member}
            def check(collapsed, generated=()):
                individual, dirs, covered = collapse(protected, generated)
                assert (str(bundle) in dirs) == collapsed
                assert set(individual) | set(covered) == {str(p) for p in protected}
                assert not set(individual) & set(covered)
            check(True)
            extra = bundle/'ignored.log'
            extra.write_text('receipt-only')
            check(False)  # One unprotected file vetoes its ancestors.
            protected.add(extra)
            check(True)  # Tracked or verified receipt-bound growth stays one mount.
            receipt = ROOT/'seal.json'
            receipt.write_text(json.dumps(dict(path=str(extra.relative_to(ROOT)),
                sha256=hashlib.sha256(extra.read_bytes()).hexdigest())))
            with patch.object(subprocess, 'check_output', return_value=b'seal.json\0'):
                assert population()[1] == [extra]
                def rejected():
                    try: population()
                    except ValueError: return
                    raise AssertionError('invalid evidence admitted')
                extra.write_text('mutated')
                rejected()
                extra.unlink()
                rejected()
                extra.symlink_to(member)
                rejected()
                extra.unlink()
                extra.write_text('receipt-only')
            check(False, [bundle/'generated'/'world'])
            check(False, [bundle])
            check(False, [bundle.parent])
            empty = bundle/'empty'
            empty.mkdir()
            check(False)
            empty.rmdir()
            link = bundle/'link'
            link.symlink_to(member)
            protected.add(link)
            check(False)
            protected.remove(link)
            link.unlink()
            link.symlink_to(bundle, target_is_directory=True)
            check(False)
            link.unlink()
            alias = bundle.parent/'set-b-alias'
            alias.symlink_to(bundle, target_is_directory=True)
            assert not collapse([alias/'tracked'])[1]
            top_alias = ROOT/'build/alias'
            top_alias.parent.mkdir()
            top_alias.symlink_to(bundle, target_is_directory=True)
            assert not collapse([top_alias/'tracked'])[1]
            writable = ROOT/WRITABLE_OUTPUT_DIRS[0]
            writable.mkdir(parents=True)
            output = writable/'receipt'
            output.write_text('bound')
            assert collapse([output]) == ([str(output)], [], [])
            world = ROOT/'build/generated/world'
            world.mkdir(parents=True)
            source = world/'input'
            source.write_text('bound')
            assert collapse([source], [world]) == ([str(source)], [], [])
            plan_output = StringIO()
            with patch.object(sys, 'argv', ['sealed_check_run.py', '--plan',
                    '--out', str(ROOT/'must-not-exist'), '--', 'must-not-run']), \
                    patch(__name__+'.population', return_value=([], [member])), \
                    patch.object(subprocess, 'run', side_effect=AssertionError('plan ran a command')), \
                    redirect_stdout(plan_output):
                main()
            assert json.loads(plan_output.getvalue())['protected_files'] == 1
            assert not (ROOT/'must-not-exist').exists()
    finally:
        ROOT = original
    print('sealed-check: SELFTEST PASS (unknown files, growth, generated ancestors, writable outputs, symlinks, empty directories)')

def main():
    if sys.argv[1:2] == ['--mount-check']:
        value = json.loads(Path(sys.argv[2]).read_text())
        libc = ctypes.CDLL(None, use_errno=True)
        for name in value.get('sealed_dirs', []) + value['sealed']:
            p = os.fsencode(name)
            if libc.mount(p, p, None, 4096, None) != 0:
                raise OSError(ctypes.get_errno(), 'bind sealed artifact', name)
            # Preserve the namespace's locked nosuid/nodev flags. Do not add
            # noexec: some receipts bind executable host probes.
            if libc.mount(None, p, None, 4096 | 32 | 1 | 2 | 4, None) != 0:
                raise OSError(ctypes.get_errno(), 'read-only sealed artifact', name)
        # Test the original holdings before mounting fresh generated worlds.
        for name in value['sealed'] + value.get('covered', []):
            try: fd = os.open(name, os.O_WRONLY)
            except OSError as error:
                if error.errno not in (13, 30): raise
            else:
                os.close(fd)
                raise RuntimeError('original-write control survived: '+name)
        for row in value.get('generated', []):
            if libc.mount(os.fsencode(row['scratch']), os.fsencode(row['logical']),
                          None, 4096, None) != 0:
                raise OSError(ctypes.get_errno(), 'bind isolated generated tree', row)
        # CAP_SYS_ADMIN exists only in this private setup namespace. Remove
        # the bounding/effective/permitted sets before running any check.
        for cap in range(41):
            if libc.prctl(24, cap, 0, 0, 0) != 0:
                raise OSError(ctypes.get_errno(), 'drop capability')
        header = (ctypes.c_uint32 * 2)(0x20080522, 0)
        data = (ctypes.c_uint32 * 6)()
        if libc.capset(ctypes.byref(header), ctypes.byref(data)) != 0:
            raise OSError(ctypes.get_errno(), 'clear capabilities')
        if libc.prctl(38, 1, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), 'no new privileges')
        for name in value['sealed'] + value.get('covered', []):
            if any(Path(name).is_relative_to(row['logical']) for row in value.get('generated', [])):
                continue  # The original passed above; this is a writable copy.
            if not os.statvfs(name).f_flag & os.ST_RDONLY:
                raise RuntimeError('sealed mount not read-only: ' + name)
            try: fd = os.open(name, os.O_WRONLY)
            except OSError as error:
                if error.errno not in (13, 30): raise
            else:
                os.close(fd)
                raise RuntimeError('sealed artifact remained writable: ' + name)
        print('sealed-check: all artifact write-open controls rejected; capabilities dropped', flush=True)
        os.execvp(value['command'][0], value['command'])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--plan', action='store_true', help='print mount split without creating outputs or executing a check')
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--generated-tree', action='append', default=[])
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return
    worlds = [(ROOT/name).resolve() for name in args.generated_tree]
    for logical in worlds:
        if logical != ROOT/'build/bytecode/dialect-v2':
            raise ValueError('unregistered generated world: '+str(logical))
    if args.plan:
        names, sealed = population()
        protected = set(sealed) | {(ROOT/n).resolve() for n in names if (ROOT/n).is_file()}
        individual, dirs, covered = collapse(protected, worlds)
        print(json.dumps(dict(tracked=len(names), receipt_named=len(sealed),
            protected_files=len(protected), individual=len(individual), directories=len(dirs),
            files_under_directories=len(covered), total_mounts=len(individual)+len(dirs),
            generated_trees=[str(p) for p in worlds],
            set_b=dict(individual=sum(evidence_member(Path(p)) or
                Path(p).parent == ROOT/EVIDENCE_BASE and Path(p).name.startswith('set-b-')
                for p in individual),
                directories=sum(evidence_member(Path(d)/'_') for d in dirs),
                files_under_directories=sum(evidence_member(Path(p)) for p in covered))), indent=2))
        return
    args.out = (args.out or ROOT/'build/sealed-check-runs'/str(time.time_ns())).resolve()
    command = args.command
    if command[:1] == ['--']: command = command[1:]
    if not command: parser.error('check command required')
    args.out.mkdir(parents=True, exist_ok=False)
    names, sealed = population()
    before = snapshot(names)
    sealed_names = [str(p.relative_to(ROOT)) for p in sealed]
    sealed_before = snapshot(sealed_names)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
    (args.out/'start.json').write_text(json.dumps(dict(head=head, tracked=before,
        sealed_paths=sealed_names, sealed_sha256=sealed_before), indent=2)+'\n')
    # Workspace probes legitimately create temporary files at the repository
    # root and in .git. Protect existing tracked files individually rather than
    # treating every future temporary path as a sealed artifact.
    protected = sorted(set(sealed) | {(ROOT/n).resolve() for n in names if (ROOT/n).is_file()})
    options = ['--die-with-parent', '--cap-add', 'CAP_SYS_ADMIN', '--cap-add', 'CAP_SETPCAP', '--ro-bind', '/', '/', '--dev-bind', '/dev', '/dev',
               '--proc', '/proc', '--bind', str(ROOT), str(ROOT),
               '--bind', '/tmp', '/tmp', '--chdir', str(ROOT),
               '--setenv', 'PYTHONDONTWRITEBYTECODE', '1',
               '--setenv', 'LISP65_SEALED_CHECK', '1']
    generated = []
    for i, name in enumerate(args.generated_tree):
        logical = (ROOT/name).resolve()
        if logical != ROOT/'build/bytecode/dialect-v2':
            raise ValueError('unregistered generated world: '+str(logical))
        scratch = args.out/('generated-'+str(i))
        shutil.copytree(logical, scratch, symlinks=True)
        generated.append(dict(logical=str(logical), scratch=str(scratch)))
    # Host-root ownership is unmapped in this private user namespace. Preserve
    # the exact SSH client configuration bytes, but bind same-user read-only
    # copies so OpenSSH can apply its normal owner/mode validation.
    ssh_inputs = []
    pending = [Path('/etc/ssh/ssh_config')]
    seen = set()
    while pending:
        source = pending.pop()
        if source in seen: continue
        seen.add(source)
        if not source.is_file(): continue
        destination = args.out/'ssh'/source.relative_to('/')
        destination.parent.mkdir(parents=True, exist_ok=True)
        raw = source.read_bytes()
        for line in raw.decode().splitlines():
            fields = shlex.split(line, comments=True)
            if fields and fields[0].lower() == 'include':
                for pattern in fields[1:]:
                    pattern = str(Path('/etc/ssh')/pattern) if not pattern.startswith('/') else pattern
                    pending.extend(Path(p) for p in sorted(glob.glob(pattern)))
        destination.write_bytes(raw)
        destination.chmod(0o600)
        assert destination.read_bytes() == raw
        options += ['--ro-bind', str(destination), str(source.resolve())]
        ssh_inputs.append(dict(path=str(source), sha256=hashlib.sha256(raw).hexdigest()))
    (args.out/'ssh-inputs.json').write_text(json.dumps(ssh_inputs, indent=2)+'\n')
    for key, dirname in [('XDG_DATA_HOME', 'xdg-data'), ('XDG_CONFIG_HOME', 'xdg-config'),
                         ('XDG_RUNTIME_DIR', 'xdg-run')]:
        path = args.out/dirname
        path.mkdir(mode=0o700)
        options += ['--setenv', key, str(path)]
    config = args.out/'mounts.json'
    individual, sealed_dirs, covered = collapse(protected, [row['logical'] for row in generated])
    config.write_text(json.dumps(dict(sealed=[str(p) for p in individual], command=command,
                                     sealed_dirs=[str(d) for d in sealed_dirs],
                                     covered=[str(p) for p in covered], generated=generated)))
    start = time.monotonic()
    with (args.out/'check-source.log').open('w') as log:
        result = subprocess.run(['bwrap', *options, '--', sys.executable, '-B', str(Path(__file__).resolve()),
                                 '--mount-check', str(config)],
                                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    after = snapshot(names)
    sealed_after = snapshot(sealed_names)
    endhead = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
    changed = sorted(n for n in before.keys() | after.keys() if before.get(n) != after.get(n))
    changed_sealed = sorted(n for n in sealed_before.keys() | sealed_after.keys()
                            if sealed_before.get(n) != sealed_after.get(n))
    log = args.out/'check-source.log'
    receipt = dict(target=' '.join(command), exit_code=result.returncode,
        seconds=time.monotonic()-start, head_before=head, head_after=endhead,
        protected_files=len(before), sealed_artifacts_read_only=len(sealed),
        changed_files=changed, log=dict(path=str(log.relative_to(ROOT)),
        sha256=hashlib.sha256(log.read_bytes()).hexdigest()))
    receipt['isolated_generated_trees'] = generated
    receipt['read_only_mounts'] = dict(individual=len(individual), directories=len(sealed_dirs),
                                       files_under_directories=len(covered))
    receipt['changed_sealed_artifacts'] = changed_sealed
    receipt['changed_protected_files'] = len(set(changed) | set(changed_sealed))
    (args.out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt), flush=True)
    if changed or changed_sealed or head != endhead: raise SystemExit('write-neutrality violated')
    raise SystemExit(result.returncode)

if __name__ == '__main__': main()
