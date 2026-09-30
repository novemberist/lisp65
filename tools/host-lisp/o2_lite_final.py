#!/usr/bin/env python3
"""O2-lite write-once Final. Reviewed replay manifest required; never infer r3 authority.

See docs/planning/o2-lite-final-runbook.md for the manifest contract. Probe reads
only. Selftest is synthetic and forbids subprocesses. Final replays the frozen
native and media commands, never invokes Seed, and retains failed attempts.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
ROOT = Path(__file__).resolve().parents[2]
PRIORITY = ['nice', '-n', '18', 'ionice', '-c3']
BUDGET = dict(seed_rebuilds=0, final=1, link=1)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def save(path, value):
    with path.open('xb') as stream:
        stream.write(encoded(value))


def bindings(value):
    if isinstance(value, dict):
        if {'path', 'sha256'} <= value.keys():
            yield value
        else:
            for child in value.values():
                yield from bindings(child)
    elif isinstance(value, list):
        for child in value:
            yield from bindings(child)


class Driver:
    def __init__(self, seed, sealed_run, replay, replay_sha256, out, root=ROOT):
        self.root = Path(root).resolve()
        self.seed, self.run, self.replay, self.out = map(str, (seed, sealed_run, replay, out))
        self.replay_sha256 = replay_sha256
        for name in (self.seed, self.run, self.replay, self.out):
            self.path(name)
        require(len({self.seed, self.run, self.out}) == 3, 'directories overlap')
        for a in (self.seed, self.run, self.out):
            for b in (self.seed, self.run, self.out):
                require(a == b or not self.path(a).is_relative_to(self.path(b)), 'directories overlap')

    def path(self, name):
        p = Path(name)
        require(not p.is_absolute() and '..' not in p.parts and str(p) not in ('', '.'), 'unsafe path')
        result = self.root / p
        require(result.resolve().is_relative_to(self.root), 'path escapes root')
        return result

    def load(self, name):
        return json.loads(self.path(name).read_text())

    def bind(self, name):
        raw = self.path(name).read_bytes()
        return dict(path=str(name), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

    def verify(self, row):
        actual = self.bind(row['path'])
        require(actual['sha256'] == row['sha256'] and actual['bytes'] == row.get('bytes', actual['bytes']),
                'binding drift: ' + row['path'])
        return actual

    def git(self, *args):
        return subprocess.check_output(PRIORITY + ['git', *args], cwd=self.root,
                                      env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}, text=True).strip()

    def source(self):
        # One selected run is supplied once, shared by admission, replay and seal.
        head = self.git('rev-parse', 'HEAD')
        require(not self.git('status', '--porcelain', '--untracked-files=no'), 'tracked tree dirty')
        path = self.run + '/receipt.json'
        receipt = self.load(path)
        require(receipt['target'] == 'make -k check-source' and receipt['exit_code'] == 0, 'source not green')
        require(receipt['head_before'] == receipt['head_after'] == head, 'sealed HEAD mismatch')
        require(receipt['changed_protected_files'] == 0 and receipt['changed_files'] == [] and
                receipt['changed_sealed_artifacts'] == [], 'protected changes')
        log = self.verify(receipt['log'])
        require(Path(log['path']).parent == Path(self.run), 'wrong selected source run/log')
        return dict(head=head, sealed_run=self.run, source=self.bind(path), source_log=log)

    def rebase(self, commands, prefixes, paths=False, allowed_seed=None):
        require(commands and len(set(prefixes.values())) == len(prefixes), 'missing/ambiguous replay commands')
        for old, new in prefixes.items():
            require(self.path(old).is_relative_to(self.path(allowed_seed or self.seed)), 'Seed output outside Seed')
            require(self.path(new).is_relative_to(self.path(self.out)), 'output outside Final')
        keys = list(prefixes)
        require(all(a == b or not Path(a).is_relative_to(b) for a in keys for b in keys), 'nested output prefixes')
        def change(arg, mapping):
            for flag in ("-Wl,--lto-obj-path=", "-Wl,-Map="):
                if arg.startswith(flag):
                    return flag + change(arg[len(flag):], mapping)
            matches = [k for k in mapping if arg == k or arg.startswith(k + '/')]
            require(len(matches) <= 1, 'ambiguous output reference')
            return mapping[matches[0]] + arg[len(matches[0]):] if matches else arg
        result = []
        for command in commands:
            require(isinstance(command, list) and command and all(isinstance(x, str) and x for x in command), 'invalid argv')
            new = [change(a, prefixes) for a in command]
            require([change(a, {v:k for k,v in prefixes.items()}) for a in new] == command, 'non-reversible replay')
            require(not any(k in arg for k in prefixes for arg in new), 'unhandled embedded output reference')
            require(paths or new[0] == command[0], 'tool rebased')
            result.append(new)
        return result

    def admit(self, claimed=False):
        source = self.source()  # validate the selected run at start
        require(claimed or not os.path.lexists(self.path(self.out)), 'Final directory exists; no retry')
        manifest_binding = self.verify(dict(path=self.replay, sha256=self.replay_sha256))
        # The replay recipe must itself have been committed before check-source.
        require(self.git('ls-files', '--error-unmatch', '--', self.replay) == self.replay, 'replay manifest not tracked')
        m = self.load(self.replay)
        require(m['format'] in ('o2-lite-replay-v1', 'o2-lite-replay-r6') and m['seed_dir'] == self.seed, 'wrong Seed/layout contract')
        require(m['closure_complete'] is True, 'unreviewed consumed-input closure')
        r6 = m['format'] == 'o2-lite-replay-r6'
        if r6:
            require(self.seed == 'build/o2-lite-product-r6' and self.out == 'build/o2-lite-final-r1', 'r6 layout mismatch')
            require(m['artifacts']['D81']['sha256'] == 'b1921228ba1166f283793ae21f51891e6cb48729a8f5d1b5c0d09cdc6e902aef' and
                    m['artifacts']['ELF']['sha256'] == 'a82d603a03f52a14e6b55bd4d8e35ad5b848b2a540f99f4a529ccddb15c70084', 'r6 identity mismatch')
        seed = self.verify(m['seed_receipt'])
        require(seed['path'] == self.seed + '/seed.json' and self.load(seed['path'])['status'] == 'PASS', 'Seed not PASS')
        rows = {r['path']:r for r in m['inputs']}
        require(len(rows) == len(m['inputs']), 'duplicate input')
        require(rows.get(seed['path']) == seed, 'Seed receipt unbound')
        consumed = set(m['consumed_inputs'])
        require(consumed and consumed <= rows.keys(), 'unbound consumed input')
        require({'lib/stdlib-read-line.lisp', 'lib/repl-comfort-v250.lisp'} <= consumed and
                any(p.startswith('lib/lite') for p in consumed), 'resident/library closure missing')
        deltas = {r['path']:r for r in m['non_product_deltas']}
        require(len(deltas) == len(m['non_product_deltas']), 'duplicate delta')
        require(deltas.keys() <= rows.keys() and not consumed.intersection(deltas), 'consumed/unbound delta forbidden')
        proofs = []
        for path, delta in deltas.items():
            require(not path.startswith(('lib/', 'src/', 'config/')), 'product delta forbidden')
            old = self.verify(delta['historical_copy'])
            require(old['sha256'] == rows[path]['sha256'] and old['bytes'] == rows[path]['bytes'], 'historical delta mismatch')
            require(delta['current']['path'] == path, 'delta path mismatch')
            proofs += [old, self.verify(delta['proof'])]
            proof = self.load(delta['proof']['path'])
            require(proof['status'] == 'PASS' and proof['path'] == path and
                    proof['consumed_inputs'] == m['consumed_inputs'] and
                    proof['commands_sha256'] == hashlib.sha256(encoded(m['commands'])).hexdigest() and
                    proof['media_commands_sha256'] == hashlib.sha256(encoded(m['media_commands'])).hexdigest(),
                    'delta consumption proof mismatch')
        actual = [self.verify(deltas[p]['current'] if p in deltas else row) for p,row in sorted(rows.items())]
        # Every receipt reference must be accounted for, including recursive receipts.
        pending = [seed] + [r for r in m['receipts']]
        seen = set()
        while pending:
            row = pending.pop()
            if row['path'] in seen:
                continue
            seen.add(row['path'])
            self.verify(row)
            for ref in bindings(self.load(row['path'])):
                name = ref['path']
                if r6 and Path(name).is_absolute():
                    require(Path(name).is_relative_to(self.root), 'external receipt path')
                    name = str(Path(name).relative_to(self.root))
                normalized = ({k:ref[k] for k in ('bytes','sha256')} | {'path':name}) if r6 else {**ref, 'path':name}
                if r6 and rows.get(name) != normalized:
                    historical = m['historical_references'].get(name+'@'+ref['sha256'])
                    require(historical and historical['sha256'] == ref['sha256'] and
                            historical['bytes'] == ref['bytes'], 'historical reference missing: '+name)
                    self.verify(historical)
                    proofs.append(historical)
                    if historical['path'].endswith('.json'): pending.append(historical)
                else:
                    require(rows.get(name) == normalized, 'receipt closure missing/conflicting: ' + name)
                    if name.endswith('.json') and name not in deltas:
                        pending.append(normalized)
        commands = m['commands']
        if r6:
            authority = self.verify(m['native_authority'])
            require(authority['path'] == 'build/o2-lite-r4-slots-preflight/native/command-proof.json', 'wrong native authority')
            inherited = self.load(authority['path'])['commands']
            projected = self.rebase(inherited, {'build/o2-lite-product-r4/wplto':self.out+'/wplto'}, allowed_seed='build/o2-lite-product-r4')
            projected = [[x.replace(self.out+'/wplto', self.seed+'/wplto') for x in c] for c in projected]
            require(commands == projected, 'r4-to-r6 command projection drift')
        require(len(commands) == 75 and all('-c' in c for c in commands[:73]) and
                Path(commands[73][0]).name == 'llvm-link' and '-c' not in commands[74], 'native command shape mismatch')
        require(m['commands_receipt']['path'] in rows, 'command proof unbound')
        require(self.load(m['commands_receipt']['path'])['commands'] == commands, 'frozen command drift')
        require(rows[m['commands_receipt']['path']] == m['commands_receipt'], 'command receipt conflict')
        media_proof = m['media_commands_receipt']
        require(rows.get(media_proof['path']) == media_proof, 'media command proof unbound')
        require(self.load(media_proof['path'])['commands'] == m['media_commands'], 'frozen media command drift')
        require(all(not any(self.path(p).is_relative_to(self.path(prefix)) for prefix in m['output_prefixes'])
                    for p in consumed), 'consumed input inside rebased output tree')
        native = self.rebase(commands, m['output_prefixes'])
        media = self.rebase(m['media_commands'], m['output_prefixes'])
        for command in native:
            require(command.count('-o') == 1, 'missing/duplicate output')
            require(self.path(command[command.index('-o')+1]).is_relative_to(self.path(self.out)), 'output outside Final')
        tools = {}
        for tool in m['tools']:
            path = Path(tool['path'])
            require(path.is_absolute(), 'tool path must be absolute')
            raw = path.read_bytes()
            require(hashlib.sha256(raw).hexdigest() == tool['sha256'] and len(raw) == tool['bytes'], 'tool drift')
            tools[str(path)] = tool
        for c in commands + m['media_commands']:
            require(c[0] in tools, 'executable not pinned')
        require(set(m['artifacts']) == {'ELF', 'PRG', 'LTO', 'D81'}, 'artifact population mismatch')
        pairs = []
        for role, row in sorted(m['artifacts'].items()):
            self.verify(row)
            require(rows.get(row['path']) == row, 'artifact unbound')
            dest = self.rebase([[row['path']]], m['output_prefixes'], paths=True)[0][0]
            require(dest != row['path'] and self.path(dest).is_relative_to(self.path(self.out)), 'artifact destination invalid')
            pairs.append(dict(role=role, seed=row, destination=dest))
        require(len({p['destination'] for p in pairs}) == 4, 'artifact destination collision')
        for row in m['gates']:
            require(rows.get(row['path']) == row, 'gate unbound')
            require(self.load(row['path'])['status'] == 'PASS', 'Seed gate not PASS')
        require(m['gates'], 'Seed gates missing')
        require(r6 or m['media_readback'].startswith(self.seed + '/'), 'readback outside Seed')
        readback = self.load(m['media_readback'])
        require(m['media_readback'] in rows and readback['status'] == 'PASS' and
                readback['every_file_read_back'] is True and readback['unclassified_bytes'] == 0 and
                readback['medium'] == m['artifacts']['D81'], 'Seed media not accepted')
        final_readback = m['final_media_readback'] if r6 else self.rebase([[m['media_readback']]], m['output_prefixes'], paths=True)[0][0]
        require(final_readback != m['media_readback'] and self.path(final_readback).is_relative_to(self.path(self.out)), 'readback not projected')
        return dict(status='PASS', **source, replay=manifest_binding, seed_receipt=seed,
                    input_bindings=actual, tools=list(tools.values()), delta_proofs=proofs, commands=native, media_commands=media,
                    pairs=pairs, budget=BUDGET, media_readback=final_readback)

    def probe(self):
        a = self.admit()
        return dict(status='PASS', head=a['head'], sealed_run=self.run, commands=len(a['commands']),
                    budget=dict(seed_rebuilds=0, final=0, link=0))

    def final(self):
        # Do not contend with the Seed job or its oracle, even at low priority.
        processes = subprocess.check_output(['ps', '-eo', 'pid,args'], text=True)
        require(not any(('o2_lite_seed_producer' in line or 'oracle.py' in line) and
                        int(line.split(None, 1)[0]) != os.getpid() for line in processes.splitlines()[1:]),
                'Seed/oracle active; Final refused')
        a = self.admit()
        out = self.path(self.out)
        out.mkdir()  # atomic attempt claim; never remove on failure
        result = dict(status='FAIL', **{k:a[k] for k in ('head','sealed_run','source','budget')}, artifacts=[])
        try:
            save(out / 'final-invocation.json', a)
            for i, command in enumerate(a['commands'] + a['media_commands']):
                if '-o' in command:
                    self.path(command[command.index('-o')+1]).parent.mkdir(parents=True, exist_ok=True)
                with (out / f'command-{i:03d}.log').open('xb') as log:
                    r = subprocess.run(PRIORITY + command, cwd=self.root, stdout=log, stderr=subprocess.STDOUT)
                require(r.returncode == 0, f'command {i} failed; no retry')
                result['commands_consumed'] = i + 1
            for pair in a['pairs']:
                final = self.bind(pair['destination'])
                require(self.path(final['path']).read_bytes() == self.path(pair['seed']['path']).read_bytes(), 'Final byte identity mismatch')
                result['artifacts'].append(dict(role=pair['role'], seed=pair['seed'], final=final, byteidentical=True))
            rb = self.load(a['media_readback'])
            require(rb['status'] == 'PASS' and rb['every_file_read_back'] is True and rb['unclassified_bytes'] == 0 and
                    rb['medium'] == next(p['final'] for p in result['artifacts'] if p['role'] == 'D81'), 'Final media readback failed')
            result['media_readback'] = self.bind(a['media_readback'])
            require(self.admit(claimed=True) == a, 'admission changed during Final')
            result['status'] = 'PASS'
        except BaseException as error:
            result['error'] = str(error)
            raise
        finally:
            save(out / 'final-identity.json', result)
        return result


def selftest():
    from unittest.mock import patch
    with tempfile.TemporaryDirectory(prefix='o2-final-') as temp, \
         patch.object(subprocess, 'run', side_effect=AssertionError('offline only')), \
         patch.object(subprocess, 'check_output', side_effect=AssertionError('offline only')):
        d = Driver('build/seed', 'build/source', 'recipe.json', '0'*64, 'build/final', temp)
        d.git = lambda *args: 'a'*40 if args == ('rev-parse','HEAD') else ''
        run = d.path(d.run); run.mkdir(parents=True)
        (run/'check-source.log').write_text('synthetic\n')
        receipt = dict(target='make -k check-source',exit_code=0,head_before='a'*40,head_after='a'*40,
                       changed_files=[],changed_sealed_artifacts=[],changed_protected_files=0,log=d.bind(d.run+'/check-source.log'))
        def put(value): (run/'receipt.json').write_bytes(encoded(value))
        put(receipt); d.source()
        passed = ['green selected source']
        def reject(name, fn):
            try: fn()
            except (ValueError, FileNotFoundError): passed.append(name)
            else: raise AssertionError('negative survived: '+name)
        for name, changes in [('red',dict(exit_code=1)),('HEAD',dict(head_after='b'*40)),
                              ('protected',dict(changed_protected_files=1)),('wrong run',dict(log={**receipt['log'],'path':'build/else/log'}))]:
            put({**receipt,**changes}); reject(name,d.source)
        put(receipt)
        prefixes = {'build/seed/wplto':'build/final/wplto'}
        command = [['/tool','-c','lib/input','-o','build/seed/wplto/a.o']]
        assert d.rebase(command,prefixes) == [['/tool','-c','lib/input','-o','build/final/wplto/a.o']]
        passed.append('only output references rebased')
        flags = [["/tool", "-Wl,--lto-obj-path=build/seed/wplto/p.lto.o", "-Wl,-Map=build/seed/wplto/p.map"]]
        assert d.rebase(flags,prefixes)[0][1:] == ["-Wl,--lto-obj-path=build/final/wplto/p.lto.o", "-Wl,-Map=build/final/wplto/p.map"]
        passed.append('embedded map and LTO output paths')
        reject('unknown embedded output', lambda:d.rebase([["/tool","--unknown=build/seed/wplto/x"]],prefixes))
        reject('escaping output',lambda:d.rebase(command,{'build/seed/wplto':'../escape'}))
        reject('nested prefixes',lambda:d.rebase(command,{**prefixes,'build/seed/wplto/x':'build/final/x'}))
        reject('path traversal',lambda:d.path('../escape'))
        reject('unpinned recipe',d.admit)
        def write(name, value):
            path = d.path(name); path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value if isinstance(value, bytes) else encoded(value))
            return d.bind(name)
        tool = write('llvm-link', b'synthetic executable, never run')
        absolute_tool = {**tool, 'path':str(d.path('llvm-link'))}
        exe = absolute_tool['path']
        inputs = [write(p,b'source') for p in ('lib/stdlib-read-line.lisp','lib/repl-comfort-v250.lisp','lib/lite.lisp')]
        commands = [[exe,'-c','lib/stdlib-read-line.lisp','-o',f'build/seed/wplto/{i}.o'] for i in range(73)]
        commands += [[exe,'build/seed/wplto/0.o','-o','build/seed/wplto/all.bc'],
                     [exe,'build/seed/wplto/all.bc','-o','build/seed/wplto/product.prg']]
        cp = write('build/seed/commands.json',dict(commands=commands)); inputs.append(cp)
        arts = {role:write('build/seed/'+name,b'artifact') for role,name in
                [('ELF','wplto/product.elf'),('PRG','wplto/product.prg'),('LTO','wplto/product.lto.o'),('D81','media/product.d81')]}
        inputs += list(arts.values())
        rb = write('build/seed/media/readback.json',dict(status='PASS',every_file_read_back=True,unclassified_bytes=0,medium=arts['D81']))
        inputs.append(rb)
        seed = write('build/seed/seed.json',dict(status='PASS',receipts=[rb])); inputs.append(seed)
        mp = write('build/seed/media-commands.json',dict(commands=[[exe,'build/seed/media']]))
        inputs.append(mp)
        m = dict(format='o2-lite-replay-v1',seed_dir=d.seed,closure_complete=True,seed_receipt=seed,
                 inputs=inputs,consumed_inputs=[r['path'] for r in inputs[:3]],non_product_deltas=[],
                 receipts=[rb],commands=commands,commands_receipt=cp,tools=[absolute_tool],
                 media_commands=[[exe,'build/seed/media']],media_commands_receipt=mp,output_prefixes={**prefixes,'build/seed/media':'build/final/media'},
                 artifacts=arts,gates=[rb],media_readback=rb['path'])
        d.git = lambda *args: ('a'*40 if args == ('rev-parse','HEAD') else d.replay if args[0] == 'ls-files' else '')
        def install(value):
            write(d.replay,value); d.replay_sha256 = d.bind(d.replay)['sha256']
        install(m); admitted = d.admit(); assert len(admitted['pairs']) == 4
        passed.append('full synthetic resident/library admission')
        # Exercise write-once replay, media handoff and real seal validation
        # using a fake executor. No native executable or subprocess is started.
        import shutil
        from types import SimpleNamespace
        calls = []
        def fake_run(command, **kwargs):
            calls.append(command)
            if len(calls) == 75:
                for pair in admitted['pairs']:
                    if pair['role'] != 'D81':
                        write(pair['destination'],d.path(pair['seed']['path']).read_bytes())
            if len(calls) == 76:
                medium = next(pair for pair in admitted['pairs'] if pair['role'] == 'D81')
                final_medium = write(medium['destination'],d.path(medium['seed']['path']).read_bytes())
                write(admitted['media_readback'],dict(status='PASS',every_file_read_back=True,
                                                     unclassified_bytes=0,medium=final_medium))
            return SimpleNamespace(returncode=0)
        with patch.object(subprocess,'check_output',return_value='PID COMMAND\n'), \
             patch.object(subprocess,'run',side_effect=fake_run):
            identity = d.final()
        assert identity['status'] == 'PASS' and identity['commands_consumed'] == 76
        assert calls == [PRIORITY+c for c in admitted['commands']+admitted['media_commands']]
        assert d.verify(rb) == rb
        passed.append('synthetic Final replay and private media identity')
        for name in ('tools/host-lisp/o2_lite_final.py','tools/host-lisp/o2_lite_seal.py','docs/planning/o2-lite-final-runbook.md'):
            write(name,b'synthetic fixture')
        from o2_lite_seal import Seal
        seal = Seal(d,'build/evidence/seal.json'); seal.seal(); seal.check()
        passed.append('full Final-to-seal integration')
        ident_path = d.out+'/final-identity.json'
        bad = copy.deepcopy(identity); bad['artifacts'].pop(); write(ident_path,bad)
        reject('seal incomplete artifact population',seal.check)
        write(ident_path,identity)
        final_elf = next(p['final']['path'] for p in identity['artifacts'] if p['role'] == 'ELF')
        write(final_elf,b'wrong'); reject('seal Final artifact drift',seal.check)
        shutil.rmtree(d.path(d.out))  # private synthetic tree only
        with patch.object(subprocess,'check_output',return_value='PID COMMAND\n'), \
             patch.object(subprocess,'run',return_value=SimpleNamespace(returncode=1)):
            reject('failed replay retained',d.final)
        assert d.load(ident_path)['status'] == 'FAIL'
        reject('failed replay cannot retry',d.admit)
        shutil.rmtree(d.path(d.out))  # reset synthetic fixture for mutations
        for name, mutate in [
            ('command flag drift',lambda x:x['commands'][0].append('-DWRONG')),
            ('missing artifact',lambda x:x['artifacts'].pop('ELF')),
            ('missing resident',lambda x:x['consumed_inputs'].remove('lib/stdlib-read-line.lisp')),
            ('unbound closure',lambda x:x['inputs'].remove(seed)),
            ('media command drift',lambda x:x['media_commands'][0].append('--wrong')),
            ('bad readback destination',lambda x:x.update(media_readback='elsewhere.json')),
            ('consumed delta',lambda x:x['non_product_deltas'].append(dict(path='lib/stdlib-read-line.lisp'))),
        ]:
            bad = copy.deepcopy(m); mutate(bad); install(bad); reject(name,d.admit)
        install(m)
        d.path(inputs[0]['path']).write_bytes(b'drift'); reject('input drift',d.admit)
        d.path(inputs[0]['path']).write_bytes(b'source')
        # An exact, non-consumed successor requires both old bytes and bound audit.
        old = write('tests/old.json',{})
        m['inputs'].append(old)
        historical = write('build/seed/old-copy.json',{})
        current = write('tests/old.json',dict(successor=True))
        proof = write('build/seed/delta-proof.json',dict(status='PASS',path=old['path'],consumed_inputs=m['consumed_inputs'],
                      commands_sha256=hashlib.sha256(encoded(m['commands'])).hexdigest(),
                      media_commands_sha256=hashlib.sha256(encoded(m['media_commands'])).hexdigest()))
        m['non_product_deltas']=[dict(path=old['path'],historical_copy=historical,current=current,proof=proof)]
        install(m); d.admit(); passed.append('proven non-consumed delta')
        d.path(historical['path']).write_bytes(b'wrong'); reject('historical delta drift',d.admit)
        d.path(historical['path']).write_bytes(encoded({}))
        d.path(proof['path']).write_bytes(encoded(dict(status='FAIL'))); reject('delta proof drift',d.admit)
        d.path(d.out).mkdir(); reject('write-once attempt',d.admit)
        return dict(status='PASS',tests=passed,product_commands=0,final_links=0,git_commands=0)


def parser(modes=('probe','final')):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', nargs='?', choices=modes)
    p.add_argument('--seed-dir', default='build/o2-lite-product-r6')
    p.add_argument('--source-run', '--sealed-run', dest='sealed_run')
    p.add_argument('--replay')
    p.add_argument('--replay-sha256')
    p.add_argument('--out', default='build/o2-lite-final-r1')
    p.add_argument('--selftest', action='store_true')
    return p


if __name__ == '__main__':
    try:
        require(__debug__, 'assertions required')
        a = parser().parse_args()
        if a.selftest:
            require(a.mode is None, 'standalone selftest required'); result = selftest()
        else:
            require(a.mode and a.sealed_run and a.replay and a.replay_sha256, 'mode, sealed run and pinned replay required')
            result = getattr(Driver(a.seed_dir,a.sealed_run,a.replay,a.replay_sha256,a.out),a.mode)()
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, KeyError, AssertionError, subprocess.CalledProcessError) as error:
        sys.exit('FAIL: '+str(error))
