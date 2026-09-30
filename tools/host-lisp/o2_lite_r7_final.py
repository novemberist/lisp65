#!/usr/bin/env python3
"""Write-once r7c Final: 73 compiles, one bitcode merge, ONE product link.

Frozen Seed native inputs retain their original paths. Only wplto outputs are
rebased. Inventory and media are freshly derived by the unchanged r7 producer;
its seed(), prepare_native(), preflight() and finish() are never called.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
# -B alone still reads timestamp-valid caches. Isolate before project imports.
import tempfile as _cache_tempfile
_BYTECODE_CACHE = _cache_tempfile.TemporaryDirectory(prefix='o2-r7-pycache-')
sys.pycache_prefix = _BYTECODE_CACHE.name

def _reject_bytecode(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        name = os.fsdecode(args[0])
        mode, flags = args[1:3]
        writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))
        if name.endswith('.pyc') and not writing and os.path.isfile(name):
            raise ValueError('unbound bytecode cache read forbidden: ' + name)
sys.addaudithook(lambda event, args: _reject_bytecode(event, args))
ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / 'tools/host-lisp'))
from o2_lite_final import Driver as OldDriver, bindings, encoded, require, save

PRIORITY = ['nice', '-n', '18', 'ionice', '-c3']
SEED = 'build/o2-lite-product-r7c'
FINAL = 'build/o2-lite-final-r7c'
PREP = 'build/final-r7c-prep'
FORMAT = 'o2-lite-replay-r7c-v1'
BUDGET = dict(seed_rebuilds=0, final=1, link=1)
TOOL_NAMES = ('o2_lite_r7_final.py', 'o2_lite_r7_replay.py', 'o2_lite_r7_seal.py')
RECIPE_SHA = '2817a10b5d62745ae7168f99c05470fa485dde9f92581a6a48ccbd3c0443e770'
SEED_SHA = '531d96254b28257d48e008725c9d6c5eac742c0dc823d6f3b5d720d61ab4fd16'
ARTIFACTS = {
    'ELF': ('wplto/resident-island-seed.prg.elf', '4edcc037a3fd729cc124ae40d8c85349889ba17941e3468f1ffe8c2de2aa4abd'),
    'PRG': ('wplto/resident-island-seed.prg', 'f74ca2df859d0f521f3926a6e9306f0cb9d53e7fe686c35899239eaca3281972'),
    'LTO': ('wplto/resident-island-seed.prg.lto.o', 'af01c0a83d94429fcc747534cfcd76ad920a050a52d72cba3b07430966c1cf2a'),
    'D81': ('media-r7/o2lite.d81', 'ae4e2931bb79bc6d963a2334d67e0777e924c9b34db42ef16567f472c87a300d'),
}


def installed_tools():
    return ['tools/host-lisp/' + n for n in TOOL_NAMES]


def policy():
    require(__debug__ and os.environ.get('PYTHONDONTWRITEBYTECODE') == '1',
            'assertions and PYTHONDONTWRITEBYTECODE=1 required')
    require(Path.cwd().resolve() == ROOT, 'run from repository root')


class Driver(OldDriver):
    def __init__(self, source_run, replay, replay_sha256, root=ROOT):
        super().__init__(SEED, source_run, replay, replay_sha256, FINAL, root)
        for name in (self.run, self.replay):
            require(self.path(name).is_relative_to(self.root / 'build'), 'run/replay must be under build/')
        require(not self.path(self.replay).is_relative_to(self.path(self.out)), 'replay inside Final')
        require(not self.path(self.replay).is_relative_to(self.path(self.run)), 'replay inside source run')
        require(not self.path(self.run).is_relative_to(self.root / PREP), 'source run inside preparation tree')

    def path(self, name):
        p = super().path(name)
        # No alias for a write-once name, including dangling symlinks.
        require(str(Path(name)) == str(name), 'noncanonical path')
        require(not any(q.is_symlink() for q in (p, *p.parents) if q.is_relative_to(self.root)),
                'symlink path forbidden: ' + str(name))
        return p

    def git(self, *args):
        return subprocess.check_output(PRIORITY + ['git', *args], cwd=self.root,
            env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}, text=True).strip()

    def source_population(self):
        """Recompute the runner's receipt-named population, without running it."""
        from sealed_check_run import binding_rows, EVIDENCE_BASE
        names = set(filter(None, self.git('ls-files', '-z').split('\0')))
        sealed = set()
        for name in sorted(names):
            if not name.endswith('.json'):
                continue
            try:
                value = self.load(name)
            except (OSError, ValueError):
                continue
            for row in binding_rows(value):
                lexical = Path(os.path.abspath(self.root / row['path']))
                resolved = lexical.resolve()
                if resolved.is_relative_to(self.root / 'build') and resolved.is_file():
                    sealed.add(str(resolved.relative_to(self.root)))
                evidence = self.root / EVIDENCE_BASE
                if lexical.is_relative_to(evidence):
                    parts = lexical.relative_to(evidence).parts
                    if len(parts) > 1 and parts[0].startswith('set-b-'):
                        relative = str(lexical.relative_to(self.root))
                        if relative not in names:
                            require(self.path(relative).is_file(), 'missing protected evidence: ' + relative)
                            sealed.add(relative)
        return names, sealed

    def committed_blobs(self, head):
        # Check bytes against HEAD too: git status can hide assume-unchanged files.
        rows = self.git('ls-tree', '-rz', '--full-tree', head).split('\0')
        result = {}
        for row in filter(None, rows):
            meta, name = row.split('\t', 1)
            mode, kind, oid = meta.split()
            require(kind == 'blob' and mode in ('100644', '100755'), 'unsupported tracked entry: ' + name)
            result[name] = oid
        return result

    def source(self):
        a = super().source()
        receipt = self.load(self.run + '/receipt.json')
        # Parent directory is independently checked by the inherited guard.
        require(Path(receipt['log']['path']).name == 'check-source.log',
                'wrong selected source log')
        start = self.load(self.run + '/start.json')
        mounts = self.load(self.run + '/mounts.json')
        require(start['head'] == a['head'] and mounts['command'] == ['make', '-k', 'check-source'],
                'source start/mount command mismatch')
        require(receipt['protected_files'] == len(start['tracked']) > 0 and
                receipt['sealed_artifacts_read_only'] == len(start['sealed_paths']) > 0,
                'source protection population missing')
        require(receipt['read_only_mounts']['individual'] + receipt['read_only_mounts']['directories'] > 0,
                'source read-only mounts missing')
        names, sealed = self.source_population()
        committed = self.committed_blobs(a['head'])
        require(set(start['tracked']) == names == set(committed), 'source tracked population mismatch')
        require(len(start['sealed_paths']) == len(set(start['sealed_paths'])) and
                set(start['sealed_paths']) == set(start['sealed_sha256']) == sealed,
                'source sealed population mismatch')
        special = set(installed_tools() + [self.replay, 'tools/host-lisp/o2_lite_r7_product.py'])
        require(special <= names, 'source tooling/recipe population missing')
        for name in sorted(names):
            raw = self.path(name).read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            message = ('source run did not protect current tooling/recipe: ' if name in special
                       else 'source tracked start hash mismatch: ') + name
            require(start['tracked'][name] == sha, message)
            oid = committed[name]
            algorithm = hashlib.sha1 if len(oid) == 40 else hashlib.sha256
            require(algorithm(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == oid,
                    'source bytes differ from sealed commit: ' + name)
        for name in sorted(sealed):
            require(start['sealed_sha256'][name] == self.bind(name)['sha256'],
                    'source sealed start hash mismatch: ' + name)
        a.update(source_start=self.bind(self.run + '/start.json'),
                 source_mounts=self.bind(self.run + '/mounts.json'))
        return a

    def check_driver_configuration(self, manifest):
        from o2_lite_r7_replay import driver_configuration
        require(driver_configuration(self) == manifest['driver_configuration'],
                'compiler default configuration selection drift')

    def admit(self, claimed=False):
        from o2_lite_r7_replay import verify_manifest
        require(Path(__file__).resolve() == self.path(installed_tools()[0]), 'execute the committed installed Final tool')
        source = self.source()
        require(claimed or not os.path.lexists(self.path(self.out)), 'Final directory exists; no retry')
        replay = self.verify(dict(path=self.replay, sha256=self.replay_sha256))
        for name in installed_tools() + [self.replay]:
            require(self.git('ls-files', '--error-unmatch', '--', name) == name,
                    'untracked tooling/recipe: ' + name)
        m = self.load(self.replay)
        rows = verify_manifest(self, m)
        self.check_driver_configuration(m)
        native = self.rebase(m['commands'], {SEED + '/wplto': FINAL + '/wplto'})
        outputs = [c[c.index('-o')+1] for c in native]
        require(len(set(outputs)) == 75 and all(self.path(p).is_relative_to(self.path(FINAL + '/wplto'))
                                               for p in outputs), 'native output collision/escape')
        pairs = [dict(role=role, seed=m['artifacts'][role], destination=FINAL + '/' + ARTIFACTS[role][0])
                 for role in sorted(ARTIFACTS)]
        return dict(status='PASS', **source, replay=replay, seed_receipt=m['seed_receipt'],
                    input_bindings=rows, tools=m['tools'], delta_proofs=[], commands=native,
                    # Media is an in-process imported transaction, never another Seed CLI.
                    media_adapter='o2_lite_r7_replay.rederive', pairs=pairs, budget=BUDGET,
                    media_readback=FINAL + '/media.json', closure_roots=m['closure_roots'])

    def probe(self):
        a = self.admit()
        return dict(status='PASS', head=a['head'], source_run=self.run,
                    native_commands=len(a['commands']), budget=dict(seed_rebuilds=0, final=0, link=0))

    def idle(self):
        # Refuse overlapping producers/checks; no interference with an active sealed run.
        text = subprocess.check_output(PRIORITY + ['ps', '-eo', 'pid,args'], text=True)
        needles = ('o2_lite_r7_product.py seed', 'o2_lite_seed_producer', 'oracle.py',
                   'sealed_check_run.py --', 'make -k check-source')
        for line in text.splitlines()[1:]:
            fields = line.strip().split(None, 1)
            if len(fields) == 2 and int(fields[0]) != os.getpid():
                program = Path(fields[1].split()[0]).name
                if program.startswith(('python', 'make', 'gmake')):
                    require(not any(n in fields[1] for n in needles), 'producer/source/oracle active; Final refused')

    def execute(self, command, log):
        from o2_lite_r7_replay import execution_env
        with log.open('xb') as stream:
            r = subprocess.run(PRIORITY + command, cwd=self.root, stdout=stream, stderr=subprocess.STDOUT,
                env=execution_env(self))
        require(r.returncode == 0, 'native command failed; no retry: ' + str(log))

    def media(self, admission):
        from o2_lite_r7_replay import rederive
        return rederive(self, admission)

    def identity(self, admission):
        rows = []
        for pair in admission['pairs']:
            final = self.bind(pair['destination'])
            require(self.path(final['path']).read_bytes() == self.path(pair['seed']['path']).read_bytes(),
                    'Final byte identity mismatch: ' + pair['role'])
            rows.append(dict(**pair, final=final, byteidentical=True))
        return rows

    def readback(self, name):
        from o2_lite_r7_replay import verify_readback
        row = self.bind(name)
        verify_readback(self, self.load(name), self.bind(FINAL + '/media-r7/o2lite.d81'))
        return row

    def final(self):
        self.idle()
        a = self.admit()
        out = self.path(self.out)
        out.mkdir()  # Atomic claim before any command; retain every failed attempt.
        result = dict(status='FAIL', **{k:a[k] for k in ('head', 'sealed_run', 'source', 'budget')},
                      artifacts=[], native_commands_consumed=0, product_links_claimed=0, media_transactions=0)
        from o2_lite_r7_replay import WriteScope
        with WriteScope(out):
            try:
                save(out / 'final-invocation.json', a)
                (out / 'tmp').mkdir()
                for i, command in enumerate(a['commands']):
                    self.path(command[command.index('-o')+1]).parent.mkdir(parents=True, exist_ok=True)
                    if i == 74:
                        save(out / 'product-link-claim.json', dict(product_links=1, command=command))
                        result['product_links_claimed'] = 1
                    self.execute(command, out / f'command-{i:03d}.log')
                    result['native_commands_consumed'] = i + 1
                # Reject native drift before deriving even the first media byte.
                native = {**a, 'pairs':[p for p in a['pairs'] if p['role'] != 'D81']}
                self.identity(native)
                helper = self.media(a)
                result['media_transactions'] = 1
                result['media_execution'] = self.bind(self.out + '/media-execution.json')
                require(helper['product_links'] == 0 and helper['stager_builds'] == 1, 'media link budget')
                result['artifacts'] = self.identity(a)
                result['media_readback'] = self.readback(a['media_readback'])
                require(self.admit(claimed=True) == a, 'admission changed during Final')
                result['status'] = 'PASS'
            except BaseException as error:
                result['error'] = repr(error)
                raise
            finally:
                save(out / 'final-identity.json', result)
        return result


def parser(modes=('probe', 'final')):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', nargs='?', choices=modes)
    p.add_argument('--source-run', help='ONE reviewer-selected sealed check-source directory; no default')
    p.add_argument('--replay', help='committed r7c replay JSON')
    p.add_argument('--replay-sha256', help='reviewed replay SHA256')
    p.add_argument('--selftest', action='store_true')
    return p


def driver_args(a):
    require(a.mode and a.source_run and a.replay and a.replay_sha256, 'mode, --source-run and pinned replay required')
    return Driver(a.source_run, a.replay, a.replay_sha256)


def selftest(replay):
    """Offline admission + real recipe validation + synthetic lifecycle/negative controls."""
    from o2_lite_r7_replay import offline_selftest
    return offline_selftest(replay)


if __name__ == '__main__':
    try:
        policy()
        a = parser().parse_args()
        if a.selftest:
            require(a.mode is None and not a.source_run and a.replay, 'selftest requires --replay; no source run')
            result = selftest(a.replay)
        else:
            result = getattr(driver_args(a), a.mode)()
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, KeyError, AssertionError, subprocess.CalledProcessError) as error:
        sys.exit('FAIL: ' + str(error))
