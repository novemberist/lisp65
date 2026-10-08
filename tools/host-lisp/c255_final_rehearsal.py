#!/usr/bin/env python3
"""2.5.5 Final REHEARSAL: everything the Final and the seal do, except the 75 native commands.

Successor of c254_final_rehearsal.py (derived by build/card-255-final-prep-r1/derive_c255_final_side.py).

NOT a Final, NOT a product, never an admission.  Like the Seed's `rehearse`:

  phase A  preconditions on the real tree (read-only): pins against the Seed, run names, git state,
           runner population == Final-driver population, mount plan, tracked receipt bindings that
           would grow the sealed population when the Final writes its outputs.
  phase B  the REAL admission for the REAL names (c255_final.Driver.admit: pins, replay hash, real
           verify_manifest over every bound input, real `-###` compiler-driver configuration check,
           real 75-command projection to FINAL/wplto) plus per-command preconditions.
  phase C  the REAL Driver.final() lifecycle inside a rehearsal directory, with the Seed ELF/PRG/LTO
           standing in for the output of command 75: claim, invocation receipt, link claim, native
           byte identity, the REAL media re-derivation (c255_replay.rederive -> c255_product
           inventory() + media() under MediaScope), D81 byte identity, persisted readback,
           re-admission, final-identity.json.
  phase D  the REAL seal + check on that rehearsal Final (bound inputs, hash checks, retained receipt
           copies including deterministic gzip above 50 MB) and negative controls on the real copies.

Refused: every compile and link (the 75 frozen commands are never launched; the cold-stager's three
llvm-mos compiles and its link are replaced by the Seed's own stager outputs and only their argv is
checked against the admitted recipe).  Executed for real: read-only ELF tools, the one host `cc`
ABI-constant emitter (host code, not a product input), git read queries, `ps`.

Simulated, and listed in rehearsal.json: the sealed check-source run (no sealed run is started; a
start/receipt/mounts triple is synthesised from the runner's own population()/collapse() code and then
checked by the REAL Driver.source()), a clean committed tree (uncommitted/untracked tool and replay
files are overlaid as if staged), and the Final directory name.
"""
import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.append(str(ROOT / 'tools/host-lisp'))
import c255_final as F
import c255_replay as R
import c255_seal as Z
import c255_final_pins as PINS
import c255_config as CFG
import sealed_check_run as SCR
from c255_final import require, save, encoded

NAME_PREFIX = 'card-255-final-rehearsal-'
# The symbol tool's name comes from the accountable media parser (c2_product_hw_presmoke.NM via
# c255_replay.symbol_tool), as in the replay adapter: this file names no ELF column tool itself.
READ_ONLY_ELF_TOOLS = ('llvm-readobj', 'llvm-objdump', 'llvm-objcopy', R.symbol_tool().name)
MARK = 'REHEARSAL-NOT-A-FINAL'


def blob_oid(raw, length=40):
    algorithm = hashlib.sha1 if length == 40 else hashlib.sha256
    return algorithm(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


class RehearsalDriver(F.Driver):
    """The real Driver; only Git answers about commit state are overlaid, and binds are memoised.

    overlay = files that the reviewer still has to commit (dirty tracked + untracked tool/replay
    files).  They are presented as tracked with their working-tree bytes, i.e. exactly the state the
    official sequence creates by committing them.  Everything else is asked from real Git."""
    def __init__(self, run, replay, sha, sim, alias=None):
        self.sim, self.alias, self.memo = sim, alias, {}
        super().__init__(run, replay, sha)

    def bind(self, name):
        path = self.path(name)
        stat = path.stat()
        key = (str(name), stat.st_mtime_ns, stat.st_size, stat.st_ino)
        if key not in self.memo:
            self.memo[key] = super().bind(name)
        return dict(self.memo[key])

    def load(self, name):
        value = super().load(name)
        if self.alias and name == self.replay:
            require(value['final_dir'] == CFG.FINAL, 'replay names another Final')
            value = {**value, 'final_dir': self.alias}     # simulated: the rehearsal Final directory
        return value

    def git(self, *args):
        sim = self.sim
        if args == ('status', '--porcelain', '--untracked-files=no'):
            return ''                                       # simulated clean tree (sim['dirty_tracked'])
        if args == ('ls-files', '-z'):
            return '\0'.join(sim['names'])
        if args[:2] == ('ls-files', '--error-unmatch'):
            return args[-1] if args[-1] in sim['names_set'] else super().git(*args)
        if args[:1] == ('ls-tree',):
            rows = []
            for row in filter(None, super().git(*args).split('\0')):
                meta, name = row.split('\t', 1)
                if name in sim['overlay']:
                    mode, kind, oid = meta.split()
                    meta = ' '.join((mode, kind, blob_oid(self.path(name).read_bytes(), len(oid))))
                rows.append(meta + '\t' + name)
            length = len(rows[0].split('\t', 1)[0].split()[2])
            present = {row.split('\t', 1)[1] for row in rows}
            for name in sorted(sim['names_set'] - present):
                rows.append('100644 blob ' + blob_oid(self.path(name).read_bytes(), length) + '\t' + name)
            return '\0'.join(rows)
        return super().git(*args)


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}, text=True)


def overlay_state(replay):
    """What the reviewer still has to commit, taken from real Git."""
    tracked = [n for n in git('ls-files', '-z').split('\0') if n]
    dirty = [line for line in git('status', '--porcelain', '--untracked-files=no').splitlines() if line]
    require(all(line[:2] in (' M', 'M ', 'MM', 'A ', 'AM') for line in dirty), 'unsupported dirty state: ' + repr(dirty))
    dirty_names = [line[3:] for line in dirty]
    wanted = F.installed_tools() + F.support_tools() + [replay, 'tools/host-lisp/' + Path(__file__).name]
    # A committed replay directory carries its historical snapshots too.
    wanted += [str(p.relative_to(ROOT)) for p in sorted((ROOT / replay).parent.rglob('*')) if p.is_file()]
    # Every untracked file below tools/host-lisp is a replay input and must be committed with it.
    untracked_tools = [n for n in git('ls-files', '-o', '--exclude-standard', '-z', '--', 'tools/host-lisp').split('\0') if n]
    untracked = sorted(set(n for n in wanted + untracked_tools if n not in set(tracked)))
    names = sorted(set(tracked) | set(untracked))
    return dict(names=names, names_set=set(names), overlay=set(dirty_names) | set(untracked),
                dirty_tracked=dirty_names, untracked_presented_as_tracked=untracked,
                head=git('rev-parse', 'HEAD').strip())


def simulated_run(d, sim, run_dir):
    """Synthesise the sealed-run triple with the runner's OWN population/collapse code (no bwrap,
    no make), so that the real Driver.source() has real populations and hashes to check."""
    listing = ('\0'.join(sim['names']) + '\0').encode()
    with patch.object(SCR.subprocess, 'check_output', return_value=listing):
        names, sealed = SCR.population()
    require(names == sim['names'], 'runner population differs from the overlay')
    before = SCR.snapshot(names)
    sealed_names = [str(p.relative_to(ROOT)) for p in sealed]
    sealed_before = {n: d.bind(n)['sha256'] for n in sealed_names}
    world = (ROOT / 'build/bytecode/dialect-v2').resolve()
    protected = sorted(set(sealed) | {(ROOT / n).resolve() for n in names if (ROOT / n).is_file()})
    individual, sealed_dirs, covered = SCR.collapse(protected, [str(world)])
    run_dir.mkdir()
    (run_dir / 'start.json').write_text(json.dumps(dict(head=sim['head'], tracked=before,
        sealed_paths=sealed_names, sealed_sha256=sealed_before), indent=2) + '\n')
    (run_dir / 'mounts.json').write_text(json.dumps(dict(sealed=individual, command=['make', '-k', 'check-source'],
        sealed_dirs=sealed_dirs, covered=covered, generated=[dict(logical=str(world), scratch='SIMULATED')])))
    log = run_dir / 'check-source.log'
    log.write_text('SIMULATED sealed run for the Final rehearsal; make -k check-source was NOT executed.\n')
    receipt = dict(target='make -k check-source', exit_code=0, seconds=0.0, head_before=sim['head'], head_after=sim['head'],
        protected_files=len(before), sealed_artifacts_read_only=len(sealed), changed_files=[],
        log=dict(path=str(log.relative_to(ROOT)), sha256=hashlib.sha256(log.read_bytes()).hexdigest()),
        isolated_generated_trees=[dict(logical=str(world), scratch='SIMULATED')],
        read_only_mounts=dict(individual=len(individual), directories=len(sealed_dirs), files_under_directories=len(covered)),
        changed_sealed_artifacts=[], changed_protected_files=0, SIMULATED=MARK)
    (run_dir / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return dict(protected_files=len(before), sealed_artifacts=len(sealed), sealed_bytes=sum(p.stat().st_size for p in sealed),
                mounts=receipt['read_only_mounts'], total_mounts=len(individual) + len(sealed_dirs),
                mount_max=int(Path('/proc/sys/fs/mount-max').read_text()))


def binding_hazards(names):
    """Tracked receipts whose binding rows name paths that the Final / the sealed run will create:
    such a path joins the sealed population between the sealed start and the Final's second
    admission, which would fail AFTER the product link."""
    hazards, absent = [], set()
    for name in names:
        if not name.endswith('.json'):
            continue
        try:
            value = json.loads((ROOT / name).read_text())
        except (OSError, ValueError):
            continue
        for row in SCR.binding_rows(value):
            lexical = Path(os.path.abspath(ROOT / row['path']))
            if not lexical.is_relative_to(ROOT / 'build'):
                continue
            relative = str(lexical.relative_to(ROOT))
            if any(Path(relative).is_relative_to(x) for x in (CFG.FINAL, CFG.SOURCE_RUN)):
                hazards.append(dict(receipt=name, path=relative))
            elif not lexical.is_file():
                absent.add(relative)
    return hazards, sorted(absent)


def command_preconditions(d, commands, final):
    """What the Final loop relies on, without creating anything (mirrors c255_product.rehearse)."""
    produced, rows, absent_dirs = set(), [], set()
    seed_inputs = set()
    for i, command in enumerate(commands):
        output = command[command.index('-o') + 1]
        require(Path(output).is_relative_to(final + '/wplto') and output not in produced and
                not d.path(output).exists(), f'command {i}: output collision/escape')
        tool = Path(command[0])
        require(tool.is_absolute() and tool.is_file() and os.access(tool, os.X_OK), f'command {i}: executable')
        inputs = []
        if '-c' in command:
            source = command[command.index('-c') + 1]
            require(d.path(source).is_file(), f'command {i}: compile source missing')
            inputs.append(source)
        else:
            for arg in command[1:]:
                if arg.endswith(('.o', '.bc')) and not arg.startswith('-') and arg != output:
                    require(arg in produced, f'command {i}: link input not produced by this Final: ' + arg)
                    inputs.append(arg)
        for j, arg in enumerate(command):
            if arg in ('-include', '-T') and j + 1 < len(command):
                require(d.path(command[j + 1]).exists(), f'command {i}: include/script missing')
                inputs.append(command[j + 1])
            if arg == '-I' and j + 1 < len(command) and not d.path(command[j + 1]).exists():
                absent_dirs.add(command[j + 1])           # legal empty search directory, as in the Seed
            for flag in ('-Wl,-T,', '-Wl,-L,'):
                if arg.startswith(flag):
                    require(d.path(arg[len(flag):]).exists(), f'command {i}: linker path missing')
                    inputs.append(arg[len(flag):])
        require(not any(Path(x).is_relative_to(final) for x in inputs if x not in produced), f'command {i}: input inside Final')
        seed_inputs.update(x for x in inputs if x not in produced)
        produced.add(output)
        rows.append(dict(index=i, output=output, inputs=len(inputs)))
    require(len(rows) == CFG.NATIVE_COMMANDS and '-Wl,--emit-relocs' in commands[74], 'recipe shape')
    return dict(commands=len(rows), outputs=len(produced), distinct_external_inputs=len(seed_inputs),
                absent_include_dirs=sorted(absent_dirs),
                artifacts_produced_by_link={role: any(c[c.index('-o') + 1] == final + '/' + F.ARTIFACTS[role][0] or
                    ('-Wl,--lto-obj-path=' + final + '/' + F.ARTIFACTS[role][0]) in c for c in commands)
                    for role in ('PRG', 'LTO')})


def rehearse(replay, out_name, pinned_sha=None, bind_cache=None):
    F.policy()
    out = ROOT / out_name
    require(Path(out_name).parent == Path('build') and Path(out_name).name.startswith(NAME_PREFIX),
            'rehearsal output must be build/' + NAME_PREFIX + '<tag>')
    require(not os.path.lexists(out), 'rehearsal directory is write-once')
    started = time.time()
    result = dict(status='FAIL', kind=MARK, product_compiles=0, product_links=0, native_commands_executed=0)
    out.mkdir()
    (out / 'NOT-A-FINAL.txt').write_text('Rehearsal of the 2.5.5 Final and seal.  No product compile or link ran.\n'
        'final/wplto holds COPIES of the Seed ' + CFG.ATTEMPT + ' ELF/PRG/LTO; final/' + CFG.MEDIA_DIR + ' is re-derived from them; '
        'source-run/ is a SIMULATED sealed run.  Nothing here is a deliverable or an admission.\n')
    try:
        # ---------------------------------------------------------------- phase A
        pins = PINS.check()
        require(pins['status'] == 'PASS', 'pins: ' + '; '.join(pins['problems']))
        require(not os.path.lexists(ROOT / CFG.FINAL), 'the real Final directory already exists')
        # Two Seed directories: receipts/artifacts (F.SEED, r1b) and the link attempt (F.LINK_SEED = CFG.SEED, r1).
        require(F.SEED == PINS.SEED_NAME and F.LINK_SEED == CFG.SEED == PINS.SEED_LINK_NAME and F.FINAL == CFG.FINAL,
                'run names drift')
        replay_sha = hashlib.sha256((ROOT / replay).read_bytes()).hexdigest()
        require(pinned_sha in (None, replay_sha), 'replay differs from --replay-sha256')
        sim = overlay_state(replay)
        fin, run = out_name + '/final', out_name + '/source-run'
        d = RehearsalDriver(run, replay, replay_sha, sim)
        if bind_cache and Path(bind_cache).is_file():
            # Rehearsal-only time saver: binds of earlier rehearsals, valid only for an identical
            # (path, mtime_ns, size, inode); the real Final re-hashes everything at every admission.
            d.memo = {tuple(k): v for k, v in json.loads(Path(bind_cache).read_text())}
            result['bind_cache_entries_loaded'] = len(d.memo)
        idle = 'idle'
        try:
            d.idle()
        except ValueError as error:
            idle = 'REFUSED (the real Final would stop here): ' + str(error)
        hazards, absent = binding_hazards(sim['names'])
        require(not hazards, 'tracked receipt binds a Final/source-run output: ' + repr(hazards[:3]))
        names, sealed = d.source_population()
        listing = ('\0'.join(sim['names']) + '\0').encode()
        with patch.object(SCR.subprocess, 'check_output', return_value=listing):
            runner_names, runner_sealed = SCR.population()
        require(names == set(runner_names) and sealed == {str(p.relative_to(ROOT)) for p in runner_sealed},
                'Final driver and sealed runner disagree on the protected population')
        source = simulated_run(d, sim, ROOT / run)
        if bind_cache:
            Path(bind_cache).write_text(json.dumps([[list(k), v] for k, v in d.memo.items()]))
        require(source['total_mounts'] * 2 < source['mount_max'], 'mount plan too close to fs.mount-max')
        result['preconditions'] = dict(pins=pins, head=sim['head'], idle=idle,
            replay=dict(path=replay, sha256=replay_sha, tracked=replay not in sim['untracked_presented_as_tracked']),
            names=dict(SEED=F.SEED, LINK_SEED=F.LINK_SEED, FINAL=CFG.FINAL, SOURCE_RUN=CFG.SOURCE_RUN, PREP=CFG.PREP,
                       final_absent=True, source_run_absent=not os.path.lexists(ROOT / CFG.SOURCE_RUN)),
            population=dict(tracked=len(names), sealed=len(sealed), runner_equal=True),
            simulated_sealed_run=source, bound_but_absent_build_paths=len(absent),
            receipts_binding_final_outputs=0)
        result['simulated'] = dict(
            sealed_run='no sealed run executed; start/receipt/mounts synthesised from sealed_check_run.population()/collapse() '
                       'and accepted by the real Driver.source()',
            clean_tree=dict(dirty_tracked=sim['dirty_tracked'], untracked_presented_as_tracked=sim['untracked_presented_as_tracked']),
            final_directory=fin + ' instead of ' + CFG.FINAL,
            native_commands='75 frozen commands NOT launched; Seed ELF/PRG/LTO copied at command 75',
            cold_stager='3 compiles + 1 stager link NOT launched; argv checked against the admitted recipe, Seed stager outputs copied')
        print('phase A PASS (preconditions, populations, simulated sealed run)', flush=True)

        # ---------------------------------------------------------------- phase B
        real = d.admit()
        require(real['status'] == 'PASS' and len(real['commands']) == 75 and len(real['pairs']) == 4, 'real-name admission')
        require(all(p['destination'].startswith(CFG.FINAL + '/') for p in real['pairs']) and
                real['media_readback'] == CFG.FINAL + '/media.json', 'real-name projection')
        result['admission_real_names'] = dict(status='PASS', input_bindings=len(real['input_bindings']), tools=len(real['tools']),
            commands=command_preconditions(d, real['commands'], CFG.FINAL),
            pairs=[dict(role=p['role'], destination=p['destination']) for p in real['pairs']],
            driver_configuration='real -### dry run accepted')
        require(not os.path.lexists(ROOT / CFG.FINAL), 'admission created the real Final directory')
        print('phase B PASS (real admission for the real names; 75 commands projected, 0 executed)', flush=True)

        # ---------------------------------------------------------------- phase C
        seed = ROOT / F.SEED
        standin = {role: (seed / F.ARTIFACTS[role][0]).read_bytes() for role in ('ELF', 'PRG', 'LTO')}
        standin_map = (seed / 'wplto/resident-island-seed.prg.map').read_bytes()
        media_seed = seed / CFG.MEDIA_DIR
        stager_files = {str(p.relative_to(seed)): p.read_bytes() for p in sorted(media_seed.rglob('*')) if p.is_file() and (
            p.parent.name == 'stager' or p.name.startswith('autoboot.c65'))}
        executed, observed = [], []
        original_run = subprocess.run

        with patch.object(F, 'FINAL', fin), patch.object(R, 'FINAL', fin), patch.object(Z, 'FINAL', fin), \
             patch.object(Z, 'DEFAULT', fin + '/seal.json'):
            t = RehearsalDriver(run, replay, replay_sha, sim, alias=fin)
            t.memo = d.memo
            final_root = t.path(fin)
            frozen = json.loads((ROOT / replay).read_text())['commands']

            def execute(command, log):
                index = len(executed)
                expected = [x.replace(CFG.SEED + '/wplto', fin + '/wplto') for x in frozen[index]]
                require(command == expected, f'command {index} differs from the frozen recipe projection')
                with log.open('xb') as stream:
                    stream.write(b'REHEARSAL: frozen native command NOT executed\n')
                if index == 74:
                    require((final_root / 'product-link-claim.json').is_file(), 'link reached without its claim')
                    for role in ('ELF', 'PRG', 'LTO'):
                        with t.path(fin + '/' + F.ARTIFACTS[role][0]).open('xb') as stream:
                            stream.write(standin[role])
                    with t.path(fin + '/wplto/resident-island-seed.prg.map').open('xb') as stream:
                        stream.write(standin_map)
                executed.append(command)

            def media_run(command, *args, **kwargs):
                command = list(map(str, command))
                require(command[:len(F.PRIORITY)] == F.PRIORITY, 'priority prefix absent')
                raw = command[len(F.PRIORITY):]
                exe = Path(raw[0]).name
                if exe in READ_ONLY_ELF_TOOLS:
                    observed.append(dict(mode='actual-ELF-extraction' if exe == 'llvm-objcopy' else 'actual-read-only', command=command))
                    return original_run(command, *args, **kwargs)
                if raw[0] == '/usr/bin/cc' or (len(raw) == 1 and Path(raw[0]).name == 'emit' and
                                                 Path(raw[0]).is_relative_to(final_root / 'tmp')):
                    observed.append(dict(mode='actual-host-ABI-emitter (host cc, not a product input)', command=command))
                    return original_run(command, *args, **kwargs)
                if exe in ('mos-mega65-clang', 'setarch'):
                    target = ROOT / raw[raw.index('-o') + 1]
                    suffix = str(target.relative_to(final_root))
                    require(suffix in stager_files, 'not a cold-stager output: ' + suffix)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(stager_files[suffix])
                    if exe == 'setarch':
                        Path(str(target) + '.elf').write_bytes(stager_files[suffix + '.elf'])
                        maparg = next(x for x in raw if x.startswith('-Wl,-Map,'))
                        targetmap = ROOT / maparg.removeprefix('-Wl,-Map,')
                        targetmap.write_bytes(stager_files[str(targetmap.relative_to(final_root))])
                    observed.append(dict(mode='MOCKED-cold-stager-NOT-EXECUTED', command=command))
                    return subprocess.CompletedProcess(command, 0, stdout='' if kwargs.get('text') else b'')
                raise AssertionError('rehearsal refuses process: ' + repr(command)[:300])

            def media(admission):
                with patch.object(subprocess, 'run', side_effect=media_run):
                    return R.rederive(t, admission)

            t.execute, t.media, t.idle = execute, media, lambda: None
            identity = t.final()
            require(identity['status'] == 'PASS' and len(executed) == 75 and identity['native_commands_consumed'] == 75 and
                    identity['product_links_claimed'] == 1 and identity['media_transactions'] == 1, 'rehearsal Final lifecycle')
            require(all(row['byteidentical'] and row['final']['sha256'] == F.ARTIFACTS[row['role']][1]
                        for row in identity['artifacts']) and len(identity['artifacts']) == 4, 'artifact identity')
            helper = t.load(fin + '/media-execution.json')
            kinds = {}
            for row in helper['commands']:
                kinds[row['kind']] = kinds.get(row['kind'], 0) + 1
            require(kinds.get('cold-stager') == 4 and kinds.get('host-ABI-compile') == 1 and kinds.get('host-ABI-emitter') == 1,
                    'media transcript shape: ' + repr(kinds))
            mocked = [r for r in observed if r['mode'].startswith('MOCKED')]
            require(len(mocked) == 4 and len(observed) == len(helper['commands']), 'observed process population')
            # Receipt population of the rehearsal Final versus the Seed (same producer code path).
            def population(base, folders):
                # Log names carry a digest of their (path-bearing) command line.
                return {str(p.relative_to(base)) for folder in folders for p in sorted((base / folder).rglob('*'))
                        if p.is_file() and p.suffix != '.log'}
            seed_media = population(seed, [CFG.MEDIA_DIR])
            final_media = population(final_root, [CFG.MEDIA_DIR])
            require(seed_media == final_media, 'media file population differs from the Seed: ' +
                    repr(sorted(seed_media ^ final_media))[:400])
            differing = sorted(n for n in seed_media if (seed / n).read_bytes() != (final_root / n).read_bytes())
            # Receipts name their own directory; the stager assembly includes its contract by path.
            require(all(n.endswith('.json') or n == CFG.MEDIA_DIR + '/cold-stager-chain.s' for n in differing),
                    'payload bytes differ from the Seed: ' + repr(differing))
            # 2.5.5: no fixed artifact count; every visible D81 file of the Seed receipt has its artifact payload.
            seed_receipt = json.loads((seed / 'media.json').read_text())
            artifact_names = {Path(n).name for n in seed_media if '/artifacts/' in n}
            require(len(seed_receipt['files']) == 20 and {name.lower() for name in seed_receipt['files']} <= artifact_names and
                    not any('/artifacts/' in n for n in differing), 'media artifact payloads differ from the Seed')
            inv_seed, inv_final = [json.loads((x / 'native/inventory.json').read_text()) for x in (seed, final_root)]
            require({k: v for k, v in inv_seed.items() if k not in ('ELFs', 'plane', 'derived', 'section_inventory')} ==
                    {k: v for k, v in inv_final.items() if k not in ('ELFs', 'plane', 'derived', 'section_inventory')},
                    'native attribution differs from the Seed')
            # 2.5.5: the config states the native expectation (.text cap 0, no changed function).
            require(0 <= inv_final['price']['text_delta'] <= CFG.NATIVE_TEXT_CAP and
                    sorted(c['name'] for c in inv_final['text']['changed']) == sorted(CFG.NATIVE_TEXT_EXPECTED_CHANGED),
                    'native attribution differs from the configured 2.5.5 expectation')
            final_receipt = t.load(fin + '/media.json')
            reemit = sorted(CFG.PACKAGES_REEMIT)
            # 2.5.5: the residue-zeroing step ran in the Final's media replay too and gave the Seed's medium.
            zero_seed, zero_final = [json.loads((x / CFG.MEDIA_DIR / 'residue-zeroing.json').read_text()) for x in (seed, final_root)]
            require(zero_final == zero_seed and zero_final['residue_bytes'] == 0 and final_receipt['residue_bytes'] == 0 and
                    zero_final['zeroing']['zeroed_medium_sha256'] == F.ARTIFACTS['D81'][1], 'residue zeroing differs from the Seed')
            require(helper.get('reviewed_pair') == dict(applied=1), 'inventory did not run inside the reviewed pair class')
            require(final_receipt['changed_files'] == seed_receipt['changed_files'] and
                    final_receipt['index_rows'] == seed_receipt['index_rows'] and
                    final_receipt['index_exact'] is (not reemit) and
                    ('L65INDEX' in final_receipt['changed_files']) is bool(reemit) and
                    all(name.upper() in final_receipt['changed_files'] for name in reemit),
                    'package re-emission population differs from the Seed')
            result['final_rehearsal'] = dict(status='PASS', directory=fin, native_commands_projected=75,
                media_commands=kinds, media_processes=dict(real=len(observed) - len(mocked), mocked=len(mocked)),
                media_reads=len(helper['read_bindings']),
                artifacts=[dict(role=r['role'], sha256=r['final']['sha256'], byteidentical=True) for r in identity['artifacts']],
                media_files=len(final_media), media_receipts_differing_by_path_only=differing,
                media_changed_files=final_receipt['changed_files'], packages_reemitted=reemit,
                residue=dict(bytes=0, zeroed=zero_final['zeroing']['bytes_in_ranges'], cleared=zero_final['zeroing']['nonzero_bytes_cleared'],
                             unzeroed_medium_sha256=zero_final['zeroing']['unzeroed_medium_sha256']),
                reviewed_pair=helper['reviewed_pair'],
                inventory=dict(text_delta=inv_final['price']['text_delta'], changed=[c['name'] for c in inv_final['text']['changed']]),
                identity=t.bind(fin + '/final-identity.json'))
            print('phase C PASS (Final lifecycle, media re-derivation, byte identity, readback)', flush=True)

            # ------------------------------------------------------------ phase D
            seal = Z.Seal(t, fin + '/seal.json')
            sealed_result = seal.seal()                      # real admission three times (evidence x2, check)
            manifest = t.load(seal.manifest)
            zipped = [c for c in manifest['receipt_copies'] if c['compression'] == 'gzip']
            require(zipped and all(c['source']['bytes'] > Z.LIMIT for c in zipped) and
                    all(c['source']['bytes'] <= Z.LIMIT for c in manifest['receipt_copies'] if c['compression'] == 'none'),
                    'gzip rule not exercised by real receipts')
            for pair in zipped[:1]:
                raw = t.path(pair['source']['path']).read_bytes()
                require(gzip.compress(raw, compresslevel=9, mtime=0) == t.path(pair['copy']['path']).read_bytes(),
                        'gzip copy is not deterministic')
            rejected = []

            def reject(label, fn, expected):
                try:
                    fn()
                except ValueError as error:
                    require(str(error).startswith(expected), 'negative reached wrong guard: ' + label + ': ' + str(error))
                    rejected.append(label)
                else:
                    raise AssertionError('negative survived: ' + label)

            def tampered(name, mutate, label, fn, expected):
                path = t.path(name)
                original = path.read_bytes()
                stat = path.stat()
                path.write_bytes(mutate(original))
                try:
                    reject(label, fn, expected)
                finally:
                    path.write_bytes(original)
                    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
                    for key in [k for k in t.memo if k[0] == name]:
                        del t.memo[key]

            # Controls only: reuse the admission just accepted instead of re-hashing ~11,000 inputs per control.
            admitted = t.admit(claimed=True)
            real_admit = t.admit
            t.admit = lambda claimed=False: copy.deepcopy(admitted)
            reject('second seal refused', seal.seal, 'seal exists; immutable')
            tampered(zipped[0]['copy']['path'], lambda raw: raw[:-9] + bytes([raw[-9] ^ 1]) + raw[-8:],
                     'gzip receipt copy drift', seal.check, 'binding drift: ')
            plain = next(c for c in manifest['receipt_copies'] if c['compression'] == 'none' and c['source']['path'].startswith(F.SEED + '/'))
            tampered(plain['copy']['path'], lambda raw: raw + b' ', 'plain receipt copy drift', seal.check, 'binding drift: ')
            tampered(fin + '/' + F.ARTIFACTS['D81'][0], lambda raw: raw[:-1] + bytes([raw[-1] ^ 1]),
                     'Final medium drift after seal', seal.check, 'Final byte identity mismatch')
            tampered(fin + '/command-074.log', lambda raw: raw + b'x', 'native log drift after seal', seal.check,
                     'seal evidence/source mismatch')
            tampered(fin + '/media-execution.json', lambda raw: raw.replace(b'"cold-stager"', b'"cold-stagex"', 1),
                     'media transcript drift after seal', seal.check, 'binding drift: ')
            t.admit = real_admit
            final_check = seal.check()                       # real admission again
            require(final_check == sealed_result, 'seal check not stable after the negative controls')
            copies_bytes = sum(p.stat().st_size for p in t.path(seal.copies).rglob('*') if p.is_file())
            result['seal_rehearsal'] = dict(sealed_result, seal=t.bind(seal.manifest),
                gzip_copies=[dict(source=c['source']['path'], bytes=c['source']['bytes'], copy_bytes=c['copy']['bytes']) for c in zipped],
                copies_bytes=copies_bytes, negative_controls=rejected)
            print('phase D PASS (seal, check, gzip copies, negative controls)', flush=True)

        require(not os.path.lexists(ROOT / CFG.FINAL) and not os.path.lexists(ROOT / CFG.SOURCE_RUN),
                'rehearsal touched a real write-once name')
        result.update(status='PASS', seconds=round(time.time() - started, 1), not_exercised=[
            'the 75 frozen native commands (73 compiles, llvm-link, ONE product link) and their determinism',
            'the cold-stager compiles/link and their byte identity with the Seed stager under the sanitised environment',
            'bwrap/kernel read-only mounts and `make -k check-source` of the sealed run',
            'Git as the source of the committed state (overlay used for uncommitted/untracked files)'])
        return result
    except BaseException as error:
        result['error'] = repr(error)
        raise
    finally:
        result.setdefault('seconds', round(time.time() - started, 1))
        (out / 'rehearsal.json').write_bytes(encoded(result))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--replay', required=True, help='prepared replay (tracked or not)')
    p.add_argument('--replay-sha256', help='optional pin, as on the Final command line')
    p.add_argument('--out', required=True, help='fresh build/' + NAME_PREFIX + '<tag>')
    p.add_argument('--bind-cache', help='optional file outside the repository inputs: reuse binds of unchanged files')
    a = p.parse_args()
    result = rehearse(a.replay, a.out, a.replay_sha256, a.bind_cache)
    print(json.dumps({k: v for k, v in result.items() if k not in ('preconditions',)}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, AssertionError, subprocess.CalledProcessError) as error:
        sys.exit('FAIL: ' + str(error))
