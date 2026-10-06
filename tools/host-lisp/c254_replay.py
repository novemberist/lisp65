#!/usr/bin/env python3
"""Prepare 2.5.4 replay closure; imported media adapter; offline selftest.

prepare only reads source/product artifacts and writes a new preparation
subdirectory. --preview binds build/ candidates and is inadmissible to Final.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
# -B alone still reads timestamp-valid caches. Isolate before project imports.
import tempfile as _cache_tempfile
_BYTECODE_CACHE = _cache_tempfile.TemporaryDirectory(prefix='c254-pycache-')
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
sys.path.append(str(ROOT / 'tools/host-lisp'))
import c254_final as F
from c254_final import (SEED, LINK_SEED, FINAL, PREP, FORMAT, ARTIFACTS, RECIPE_SHA,
    SEED_SHA, PRIORITY, Driver, bindings, encoded, require, save)
import c2_product_hw_presmoke as HW
import c254_config as CFG
import c254_final_pins as PINS
MEDIA = F.MEDIA
PRODUCT = 'tools/host-lisp/' + CFG.PRODUCT_TOOL

# 2.5.4: the predecessor's selftest (BASE/negative-controls.json provenance) and the 2.5.2 worlds that
# were CFG.BASE / CFG.BASE_PREFLIGHT in the 2.5.3 replay (22 MB + 2.5 MB; bound again, conservatively).
BASE_SELFTEST = 'build/card-253-selftest-r8'
LEGACY_WORLDS = ('build/o2-lite-product-r7c', 'build/o2-lite-r7-preflight-d')
CONTINUE_SELFTEST = 'build/card-254-seed-continue-r1b/selftest-' + PINS.SEED_CONTINUE_TOOL_SHA[:12]
# Conservative current read closure, separate from exact historical provenance.
# No generated/mutable build world is scanned wholesale.
CLOSURE_ROOTS = [
    'tools/host-lisp', 'lib', 'src', 'config', 'scripts',
    'tools/llvm-mos/lib', 'tools/llvm-mos/mos-platform',
    # C254-CHECK: every frozen world that c254_product.py still reads.  CFG.BASE / CFG.BASE_PREFLIGHT are now
    # the 2.5.3 Seed r8 and its preflight; BASE_SELFTEST / LEGACY_WORLDS keep the worlds the 2.5.3 receipts
    # and the four frozen package manifests still name (superset of the 2.5.3 replay roots; all immutable).
    # CFG.E3 = the exhaustive product-world E3 sweep the Seed binds (attempt.json `e3`, source.json `e3`).
    # SEED = receipts + carried artifacts (r1b); LINK_SEED = the halted link attempt whose compiled inputs and
    # logs the recipe names (r1); CONTINUE_SELFTEST = the receipt both continuation records bind (NOT the whole
    # continuation work directory: it holds scratch).
    SEED, LINK_SEED, CONTINUE_SELFTEST, CFG.PREFLIGHT, CFG.SELFTEST, CFG.E3, CFG.BASE, CFG.BASE_PREFLIGHT, BASE_SELFTEST,
    *LEGACY_WORLDS,
    'build/o2-lite-r7-selftest-c',
    'build/o2-lite-r4-slots-preflight', 'build/o2-lite-product-r4',
    'build/o2-lite-product-r5', 'build/o2-lite-product-r6',
    'build/strings-final-r1', 'build/strings-r7/seed',
    'build/nested-error-recovery-seed-medium-r1/packed',
]
REFERENCE_ROOTS = [SEED + '/' + n for n in (
    'seed.json', 'complete.json', 'media.json', 'native/command-proof.json',
    'native/command-ready.json', 'native/derived-inputs.json', 'native/include-closure.json',
    'native/plane-price.json', 'continuation.json', 'attempt.json', 'linked.json')] + [
    LINK_SEED + '/' + n for n in ('attempt.json', 'product-link-claim.json', 'linked.json', 'halt.json')] + [
    CFG.PREFLIGHT + '/receipt.json', CFG.E3 + '/receipt.json']
EXTRA_INPUTS = ['build/o2-lite-device-r1/tools/l252.py', 'build/lite-throughput-probe-r1/probe4.py']

# Receipt provenance must not freeze outputs rebuilt by check-source. These
# exact-byte alternatives are historical evidence, not native input rebasing.
# The producer independently pins the host helper's digest when loading it.
PROVENANCE_COPIES = {
    'build/c2-lite/product-shaped-v6-probe/c2d-v6-entry-emitter-host.so':
        'config/c2-v200-public-plane/static-plane/v6-semantics/c2d-v6-entry-emitter-host.so',
    'build/bytecode/dialect-v2/libs/buffer.ext.bin':
        'build/library-delivery-r1/raw/buffer.ext.bin',
}


def symbol_tool(root=ROOT):
    """Use the accountable media symbol parser's executable identity.

    Canonical media calls HW.symbols; this adapter only authorizes its argv.
    """
    return root / HW.NM.relative_to(HW.ROOT)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def normalize(name, root=ROOT):
    path = Path(name)
    if path.is_absolute() and path.is_relative_to(root):
        return str(path.relative_to(root))
    return str(path)


def bind_any(name, root=ROOT):
    path = root / name
    raw = path.read_bytes()
    return dict(path=str(name), bytes=len(raw), sha256=digest(raw))


def verify_any(row, root=ROOT):
    actual = bind_any(row['path'], root)
    require(actual['sha256'] == row['sha256'] and actual['bytes'] == row.get('bytes', actual['bytes']),
            'binding drift: ' + row['path'])
    return actual


CONFIG_ENTRY = 'tools/llvm-mos/bin/mos-mega65.cfg'


def compiler_configs(root=ROOT):
    """Conservatively bind all SDK defaults and every recursive response file."""
    directory = root / 'tools/llvm-mos/bin'
    pending = list(sorted(directory.glob('*.cfg')))
    seen = set()
    while pending:
        path = pending.pop()
        require(path.is_relative_to(root) and not any(p.is_symlink() for p in (path, *path.parents)),
                'compiler configuration escapes checkout or uses symlink')
        name = str(path.relative_to(root))
        if name in seen:
            continue
        seen.add(name)
        for token in shlex.split(path.read_text(), comments=True):
            if token.startswith('@'):
                child = token[1:].replace('<CFGDIR>', str(path.parent))
                child = Path(os.path.abspath(path.parent / child))
                require(child.is_file(), 'missing compiler configuration include: ' + str(child))
                pending.append(child)
    require(CONFIG_ENTRY in seen, 'missing mega65 driver configuration')
    return sorted(seen)


def driver_configuration(d):
    """Driver-only dry run: reject additional/higher-priority default configs.

    Use the native/media environment; -### never compiles or links. Binding the
    SDK cfg population separately detects additions even if selection is stable.
    """
    compiler = str(d.root / 'tools/llvm-mos/bin/mos-mega65-clang')
    command = [compiler, '-###', '-x', 'c', '-c', '/dev/null', '-o',
               str(d.path(FINAL + '/tmp/config-never-created.o'))]
    result = subprocess.run(PRIORITY + command, cwd=d.root, env=execution_env(d),
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0, 'compiler configuration dry run failed')
    selected = [normalize(line.split(': ', 1)[1], d.root)
                for line in result.stderr.splitlines() if line.startswith('Configuration file: ')]
    require(selected == [CONFIG_ENTRY], 'unexpected compiler default configuration selection')
    return dict(selected=selected, search_policy='same sanitized native/media environment; SDK defaults only')


def tree_files(root=ROOT):
    result = []
    for name in CLOSURE_ROOTS:
        folder = root / name
        require(folder.is_dir(), 'missing closure root: ' + name)
        result += [str(p.relative_to(root)) for p in sorted(folder.rglob('*'))
                   if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
    return sorted(set(result + compiler_configs(root)))


def tools():
    names = {str(Path(sys.executable).resolve()), '/usr/bin/cc', '/usr/bin/setarch', '/usr/bin/llvm-link',
             '/usr/bin/nice', '/usr/bin/ionice'}
    names.update(str(ROOT / 'tools/llvm-mos/bin' / n) for n in (
        'mos-mega65-clang', 'mos-clang', 'clang', 'ld.lld', 'llvm-readobj', 'llvm-objdump', 'llvm-objcopy'))
    names.add(str(symbol_tool()))
    return [bind_any(n) for n in sorted(names)]


def historical_copy(ref, rows, dest):
    """Never re-pin an old reference to current bytes. Retain an exact copy."""
    for row in rows.values():
        if row['sha256'] == ref['sha256'] and row['bytes'] == ref.get('bytes', row['bytes']):
            return row
    name = normalize(ref['path'])
    require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'unsafe historical source')
    env = {**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}
    revisions = subprocess.check_output(PRIORITY + ['git', 'log', '--all', '--format=%H', '--', name],
                                       cwd=ROOT, env=env, text=True).splitlines()
    for rev in revisions:
        r = subprocess.run(PRIORITY + ['git', 'show', rev + ':' + name], cwd=ROOT, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if r.returncode == 0 and digest(r.stdout) == ref['sha256']:
            require(len(r.stdout) == ref.get('bytes', len(r.stdout)), 'historical size mismatch')
            path = dest / 'historical' / (ref['sha256'] + '-' + Path(name).name)
            path.parent.mkdir(exist_ok=True)
            if not path.exists():
                with path.open('xb') as stream:
                    stream.write(r.stdout)
            row = bind_any(str(path.relative_to(ROOT)))
            rows[row['path']] = row
            return row
    raise ValueError('no byte-exact historical snapshot: ' + name + '@' + ref['sha256'])


def receipt_closure(rows, historical, *, dest=None, root=ROOT):
    """Resolve every recursively referenced receipt, including historical copies.

    Historical bytes prove provenance only. Live consumed inputs are separately
    pinned and checked by the producer and the frozen include closure.
    """
    pending = list(REFERENCE_ROOTS)
    seen, used = set(), set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        if dest is not None and name not in rows:
            rows[name] = bind_any(name, root)
        require(name in rows, 'unbound receipt: ' + name)
        value = json.loads((root / name).read_text())
        for ref in bindings(value):
            path = normalize(ref['path'], root)
            key = path + '@' + ref['sha256']
            if path in PROVENANCE_COPIES:
                replacement = PROVENANCE_COPIES[path]
                if dest is not None:
                    rows[replacement] = bind_any(replacement, root)
                    historical[key] = rows[replacement]
                resolved = historical.get(key)
                require(resolved is not None and resolved['path'] == replacement and
                        resolved['sha256'] == ref['sha256'] and
                        resolved['bytes'] == ref.get('bytes', resolved['bytes']) and
                        rows.get(replacement) == resolved,
                        'mutable provenance copy mismatch: ' + path)
                used.add(key)
                continue
            actual = rows.get(path)
            if dest is not None and actual is None and (root / path).is_file():
                actual = bind_any(path, root)
                rows[path] = actual
            if actual and actual['sha256'] == ref['sha256'] and actual['bytes'] == ref.get('bytes', actual['bytes']):
                resolved = actual
            else:
                if dest is not None and key not in historical:
                    historical[key] = historical_copy(ref, rows, dest)
                require(key in historical, 'unresolved historical receipt reference: ' + key)
                resolved = historical[key]
                require(resolved['sha256'] == ref['sha256'] and
                        resolved['bytes'] == ref.get('bytes', resolved['bytes']) and
                        rows.get(resolved['path']) == resolved, 'historical resolution mismatch')
                used.add(key)
            if resolved['path'].endswith('.json'):
                pending.append(resolved['path'])
    require(set(historical) == used, 'unused historical overrides')
    return sorted(seen)


def index_delta(before_rows, after_rows):
    """Pure: names whose L65INDEX row differs; the row population and order must not change."""
    names = [row['name'] for row in after_rows]
    require([row['name'] for row in before_rows] == names and len(set(names)) == len(names),
            'L65INDEX row population/order changed')
    return sorted(new['name'] for old, new in zip(before_rows, after_rows) if old != new)


def verify_readback(d, receipt, medium):
    import c2_require_resolver_gate as L
    import d81_persistence_fault as D
    # 2.5.4: the CFG.PACKAGES_REEMIT rows of L65INDEX change, so the index is exact only without re-emission.
    reemit = sorted(CFG.PACKAGES_REEMIT)
    require(receipt['status'] == 'PASS' and receipt['every_file_read_back'] is True and
            receipt['index_exact'] is (not reemit) and receipt['INIT_exact'] is True and
            receipt['unclassified_bytes'] == 0 and receipt['medium'] == medium, 'media receipt not accepted')
    raw = d.path(medium['path']).read_bytes()
    D.validate_bam(raw)
    files = D.visible_files(raw)
    require(len(raw) == 819200 and len(files) == 20, 'D81 geometry/population mismatch')
    measured = {n.decode():dict(bytes=len(v), sha256=digest(v)) for n,v in files.items()}
    require(receipt['files'] == measured, 'persisted all-file media readback mismatch')
    occupied = set()
    for slot in D.directory_slots(raw):
        if not slot.record[2]:
            continue
        chain = D.file_chain(raw, slot.record)
        require(not occupied.intersection(chain), 'crosslinked media chain')
        occupied.update(chain)
        require(all(not D.sector_is_free(raw, *ts) for ts in chain), 'unallocated media chain')
        require(D.read_record_payload(raw, slot.record) == files[D.entry_name(slot.record)], 'chain readback mismatch')
    # Independent index readback (replaces "index must remain exact"): the persisted index decodes against the
    # persisted package payloads under the persisted static build id, equals the receipt rows, and differs from
    # the predecessor medium's index in exactly the re-emitted rows.  The changed-file set is recomputed too.
    def normal(value):
        return json.loads(json.dumps(value))
    build_id = struct.unpack_from('<I', files[b'SHELF.BIN'], 22)[0]
    require(struct.unpack_from('<I', files[b'C2D.BIN'], 44)[0] == build_id, 'static build id differs between SHELF and C2D')
    payloads = {row['name']: files[row['name'].upper().encode()] for row in receipt['index_rows']}
    rows = normal(L.decode_index(files[b'L65INDEX'], payloads, artifact_build_id=build_id))
    require(rows == receipt['index_rows'], 'persisted L65INDEX differs from the media receipt rows')
    before = D.visible_files(d.path(d.verify(receipt['predecessor_medium'])['path']).read_bytes())
    require(set(before) == set(files) and before[b'INIT.L65'] == files[b'INIT.L65'], 'media population or INIT drift')
    changed = index_delta(normal(L.decode_index(before[b'L65INDEX'])), rows)
    require(changed == reemit and (before[b'L65INDEX'] == files[b'L65INDEX']) is (not reemit),
            'L65INDEX delta is not exactly the re-emitted packages: ' + repr(changed))
    require(sorted(receipt['changed_files']) == sorted(n.decode() for n in files if files[n] != before[n]) and
            all(name.upper() in receipt['changed_files'] for name in reemit) and
            ('L65INDEX' in receipt['changed_files']) is bool(reemit), 'changed-file set differs from the persisted media')
    for row in bindings(receipt):
        d.verify(row)


# ---------------------------------------------------------------- 2.5.4 native identity (no source seam)
# src/ is unchanged since the 2.5.3 authority, so 2.5.4 has NO native source seam.  The only reasons a compiled
# input may differ from the 2.5.3 Seed r8 materialised input are these generated-constant seams.
NATIVE_SEAM_KINDS = frozenset(('CRC16 table', 'resident stdlib counts', 'static code size', 'compiler assertion'))
NATIVE_SOURCES_NOTE = 'identical to 2.5.3 Seed r8'
NATIVE_CONSTANT_FLAGS = ('-DLISP65_C2_PRODUCT_BUILD_ID=', '-DLISP65_C2_PRODUCT_SHELF_BYTES=')
# sha256 of CFG.BASE/native/command-proof.json = c253_final_pins.RECIPE_SHA (the sealed 2.5.3 recipe).
BASE_RECIPE_SHA = '339523296f0a7a683b70adb07529ef449ff1f1b8bf012467aacfc22f4a37d8a4'


def native_identity(ready, derived, proof, base_ready, base_commands, seed=LINK_SEED, base=CFG.BASE,
                    kinds=NATIVE_SEAM_KINDS):
    """Pure.  The 2.5.4 native inputs and recipe ARE the 2.5.3 Seed r8 ones, except declared constant seams.

    ready/derived/proof = SEED/native/{command-ready,derived-inputs,command-proof}.json (byte-identical copies
    of the link attempt's receipts: every path inside them is in LINK_SEED coordinates, hence seed=LINK_SEED);
    base_ready/base_commands = the same receipts of CFG.BASE (2.5.3 Seed r8).  Binds:
      * no eval_c / repl_c (or any other source) seam row; the Seed states `native_sources`;
      * every consumed native input row names, as its source, exactly one row that 2.5.3 Seed r8 consumed
        (same path, bytes, sha256), the population is the same, and its restored path is the rebased path;
      * restored bytes == source bytes unless the file is a declared seam whose kinds are all generated constants;
      * the 75 commands equal the 2.5.3 commands after undoing the Seed prefix and the two -D constants."""
    require('eval_c' not in derived and 'repl_c' not in derived and derived.get('native_sources') == NATIVE_SOURCES_NOTE,
            'native source seam declared or native_sources note missing; 2.5.4 has no native source seam')
    seams = {}
    for change in derived['header_changes']:
        found = {seam['kind'] for seam in change['seams']}
        require(found and found <= kinds, 'unreviewed native seam kind: ' + repr(sorted(found)))
        require(change['after']['path'] not in seams, 'duplicate native seam row: ' + change['after']['path'])
        seams[change['after']['path']] = change
    require(proof['source_changes'] == derived['header_changes'], 'recipe proof and derivation name different seams')
    prefixes = {base + suffix: seed + suffix for suffix in ('/native/candidate-inputs', '/native/derived', '')}
    require(proof['path_replacements'] == prefixes, 'native path rebasing is not the Seed prefix alone')
    # Toolchain rows legitimately repeat (the same in-place file listed by several roles); a repeated path
    # must be the identical binding on both sides.
    base_rows = {}
    for row in base_ready['native']:
        require(base_rows.setdefault(row['restored']['path'], row['restored']) == row['restored'],
                'conflicting 2.5.3 native input rows: ' + row['restored']['path'])
    seen, changed = {}, []
    for row in ready['native']:
        source, restored = row['source'], row['restored']
        require(base_rows.get(source['path']) == source, 'native input is not a 2.5.3 Seed r8 input: ' + source['path'])
        require(seen.setdefault(source['path'], restored) == restored, 'conflicting native input rows: ' + source['path'])
        require(restored['path'] == source['path'].replace(base, seed),
                'native input is not at the rebased 2.5.3 path: ' + restored['path'])
        if (restored['sha256'], restored['bytes']) != (source['sha256'], source['bytes']):
            change = seams.get(restored['path'])
            require(change is not None and change['before'] == source and change['after'] == restored,
                    'compiled input differs from 2.5.3 Seed r8 outside a generated-constant seam: ' + restored['path'])
            changed.append(restored['path'])
    require(set(seen) == set(base_rows), 'native input population differs from 2.5.3 Seed r8')
    require(set(seams) <= {row['restored']['path'] for row in ready['native']}, 'seam names an unconsumed file')
    substitutions = derived['replacements']
    require(proof['allowed_substitutions'] == substitutions and
            sorted(key.split('=')[0] + '=' for key in substitutions) == sorted(NATIVE_CONSTANT_FLAGS) and
            all(old.split('=')[0] == new.split('=')[0] for old, new in substitutions.items()),
            'native constant substitutions are not exactly build id and shelf bytes')
    inverse = {new: old for old, new in substitutions.items()}
    require(len(inverse) == len(substitutions), 'ambiguous native constant substitution')
    undone = [[inverse.get(arg, arg).replace(seed, base) for arg in command] for command in proof['commands']]
    require(undone == base_commands, 'native recipe differs from 2.5.3 Seed r8 beyond Seed prefix and the two constants')
    return dict(native_inputs=len(seen), seam_files=len(seams), changed_files=sorted(set(changed)),
                seam_kinds=sorted({seam['kind'] for change in seams.values() for seam in change['seams']}),
                substitutions=substitutions, commands=len(undone))


# ---------------------------------------------------------------- 2.5.4 package re-emission inputs
# CFG.PACKAGES_REEMIT packages are emitted from LIVE sources by the Seed preflight (not by the Final: the Final
# consumes <PREFLIGHT>/packages/ as bound input).  lib/ and config/ are closure roots already; these rows are
# named explicitly so that a moved/renamed emission input fails `prepare` (free) instead of going unbound.
REEMIT_INPUTS = [
    'lib/comfort-state-address.lisp', 'lib/lite-hot.lisp', 'lib/repl-comfort-v250.lisp', 'lib/lite.lisp',   # repl-comfort
    'lib/defstruct.lisp',                                                                                  # defstruct
    'config/comfort-default-plane/libraries/repl-comfort-suite.json',
    'config/c2-v240-public-plane/libraries/defstruct-suite.json',
    # frozen Comfort resident (r4-era symbol population the Comfort loader is emitted against)
    'config/c2-v253-r2-public-plane/comfort-reemission/build/o2-lite-r4-slots-preflight/planes/resident.json',
    # DEFSTRUCT is emitted against the PRODUCT resident of its side (c254_config.PRODUCT_RESIDENT): the 2.5.3 r8
    # projected resident (BASE_PREFLIGHT, closure root) and the 2.5.4 projected resident (PREFLIGHT, closure root).
    # The live tests/bytecode/libs/p0-stdlib-require-resolver.json chain is NOT an input (its sources are
    # gate-rebuilt build/bytecode files).
] if CFG.PACKAGES_REEMIT else []
PACKAGE_KEYS = ('manifest', 'baseline', 'candidate', 'code', 'metadata')


def continuation_identity(seed, record, rows, pins=None):
    """Pure.  The Seed is the pinned official continuation of the halted link attempt.

    seed = SEED/seed.json, record = SEED/continuation.json, rows = the replay inputs by path.  Binds: the Seed
    receipt's `continues` names the link attempt, its pinned halt / claim / linked records, the pinned
    continuation record and tool; every one of them is a replay input with those bytes; the record is PASS,
    not dry, without a compile or link of its own."""
    pins = PINS if pins is None else pins
    told = seed.get('continues') or {}
    require(told.get('attempt') == LINK_SEED and told.get('dry') is False and told.get('product_links_here') == 0,
            'Seed receipt does not continue the pinned link attempt')
    want = dict(halt=(LINK_SEED + '/halt.json', pins.R1_HALT_SHA), linked=(LINK_SEED + '/linked.json', pins.R1_LINKED_SHA),
                product_link_claim=(LINK_SEED + '/product-link-claim.json', pins.R1_CLAIM_SHA),
                record=(SEED + '/continuation.json', pins.SEED_CONTINUATION_SHA),
                tool=('tools/host-lisp/' + pins.SEED_CONTINUE_TOOL, pins.SEED_CONTINUE_TOOL_SHA))
    for key, (path, sha) in want.items():
        row = told.get(key) or {}
        require(row.get('path') == path and row.get('sha256') == sha, 'Seed receipt `continues` names another ' + key)
        bound = rows.get(path) or {}
        require(bound.get('sha256') == sha, 'continuation record is not a bound replay input: ' + path)
    require(record.get('status') == 'PASS' and record.get('dry') is False and record.get('product_links_here') == 0 and
            record.get('product_compiles') == 0 and record.get('product_links_of_the_attempt') == 1 and
            (record.get('tool') or {}).get('sha256') == pins.SEED_CONTINUE_TOOL_SHA and
            record.get('wrapped') == ['c254_product.data_attribution'], 'continuation record is not the pinned official continuation')
    return dict(continues=LINK_SEED, record=want['record'][0], tool=want['tool'][0])


def e3_identity(attempt, source, receipt, e3_attempt, rows, pin=None, tool_pins=None,
                seed=SEED, e3=CFG.E3, preflight=CFG.PREFLIGHT):
    """Pure.  The Seed was admitted with the exhaustive product-world E3 sweep that is bound here.

    attempt/source = SEED/attempt.json, SEED/source.json; receipt/e3_attempt = <E3>/receipt.json, attempt.json;
    rows = the replay inputs by path.  Binds: the Seed names exactly <E3>/receipt.json (attempt and source
    agree), the reduced stage is <PREFLIGHT>/e3/receipt.json, both are replay inputs with those bytes, the
    sweep is PASS/exhaustive, and it ran with the four tools of the Seed attempt (= the pinned ones)."""
    pin = PINS.E3_RECEIPT_SHA if pin is None else pin
    tool_pins = PINS.SEED_TOOL_SHA if tool_pins is None else tool_pins
    name, reduced = e3 + '/receipt.json', preflight + '/e3/receipt.json'
    bound = attempt.get('e3') or {}
    require(bound.get('path') == name and bound.get('sha256') == pin, 'Seed attempt binds another E3 receipt')
    stages = source.get('e3') or {}
    require(stages.get('exhaustive') == bound, 'Seed source record and attempt name different E3 receipts')
    require((stages.get('reduced') or {}).get('path') == reduced, 'reduced E3 stage is not the preflight stage')
    for row in (bound, stages['reduced']):
        require(rows.get(row['path']) == row, 'E3 receipt is not a bound replay input: ' + row['path'])
    require(receipt.get('status') == 'PASS' and receipt.get('mode') == 'exhaustive', 'E3 receipt is not a PASS exhaustive sweep')
    tools = attempt.get('tools') or {}
    require(set(tools) == set(tool_pins) == {'config', 'producer', 'product', 'e3'}, 'Seed tool identity is not the four-member identity')
    require(all(tools[k]['sha256'] == tool_pins[k] for k in tool_pins), 'Seed attempt binds another tool identity')
    require(receipt.get('tools') == tools and e3_attempt.get('tools') == tools, 'E3 sweep ran with other tool bytes than the Seed')
    return dict(e3=bound, reduced=stages['reduced'], tools=sorted(tools))


def e3_identity_selftest():
    """Synthetic negatives for e3_identity (no file is read)."""
    import copy
    tool = {k: dict(path='tools/host-lisp/' + k, sha256=(c * 64)) for k, c in zip(('config', 'producer', 'product', 'e3'), 'abcd')}
    pins = {k: v['sha256'] for k, v in tool.items()}
    big = dict(path='E/receipt.json', bytes=3, sha256='1' * 64)
    small = dict(path='P/e3/receipt.json', bytes=2, sha256='2' * 64)
    good = dict(attempt=dict(tools=tool, e3=big), source=dict(e3=dict(exhaustive=big, reduced=small)),
                receipt=dict(status='PASS', mode='exhaustive', tools=tool), e3_attempt=dict(tools=tool),
                rows={big['path']: big, small['path']: small})
    call = lambda g: e3_identity(g['attempt'], g['source'], g['receipt'], g['e3_attempt'], g['rows'],
                                 pin='1' * 64, tool_pins=pins, seed='S', e3='E', preflight='P')
    require(call(good)['tools'] == ['config', 'e3', 'producer', 'product'], 'E3 identity positive control')
    cases = (('E3 receipt pin drift', lambda g: g['attempt']['e3'].update(sha256='9' * 64)),
             ('source names another E3 receipt', lambda g: g['source']['e3'].update(exhaustive=dict(big, sha256='8' * 64))),
             ('reduced E3 sweep offered as the exhaustive one', lambda g: g['receipt'].update(mode='reduced')),
             ('E3 receipt not a replay input', lambda g: g['rows'].pop(big['path'])),
             ('three-member tool identity', lambda g: g['attempt']['tools'].pop('e3')),
             ('E3 swept with another harness', lambda g: g['receipt'].update(tools=dict(tool, e3=dict(tool['e3'], sha256='7' * 64)))),
             ('Seed tool differs from the pin', lambda g: g['attempt']['tools']['config'].update(sha256='6' * 64)))
    passed = []
    for label, mutate in cases:
        bad = copy.deepcopy(good)
        mutate(bad)
        try:
            call(bad)
        except (ValueError, KeyError):
            passed.append(label)
        else:
            raise AssertionError('negative survived: ' + label)
    return passed


def package_inputs(root=ROOT):
    """Every package file the Final media transaction consumes, from the Seed preflight receipt.

    Re-emitted packages must be Seed preflight outputs below <PREFLIGHT>/packages/; the others must be the
    exact frozen manifests of the 2.5.3 Seed r8 record (no silent third mode)."""
    receipt = json.loads((root / CFG.PREFLIGHT / 'receipt.json').read_text())
    frozen = {row['name']: row['manifest'] for row in
              json.loads((root / CFG.BASE_PREFLIGHT / 'receipt.json').read_text())['packages']}
    names = [row['name'] for row in receipt['packages']]
    reemit = set(CFG.PACKAGES_REEMIT)
    require(names == list(frozen) and reemit <= set(names), 'package population differs from 2.5.3 Seed r8')
    result = []
    for row in receipt['packages']:
        manifest = normalize(row['manifest']['path'], root)
        inside = Path(manifest).is_relative_to(CFG.PREFLIGHT + '/packages')
        if row['name'] in reemit:
            require(inside, 're-emitted package manifest is not a Seed preflight output: ' + row['name'])
        else:
            require(not inside and row['manifest'] == frozen[row['name']], 'frozen package manifest drift: ' + row['name'])
        for key in PACKAGE_KEYS:
            path = normalize(row[key]['path'], root)
            require(key == 'manifest' or Path(path).is_relative_to(CFG.PREFLIGHT + '/packages'),
                    'package payload outside the Seed preflight: ' + path)
            result.append(path)
    return sorted(set(result))


def verify_native(d, m):
    proof = d.verify(m['native_authority'])
    require(proof['path'] == SEED + '/native/command-proof.json' and proof['sha256'] == RECIPE_SHA,
            'wrong 2.5.4 native authority')
    commands = d.load(proof['path'])['commands']
    compiler = str(d.root / 'tools/llvm-mos/bin/mos-mega65-clang')
    require(all(c[0] == compiler for c in commands[:73]) and commands[74][3] == compiler,
            'recipe belongs to another checkout/toolchain')
    require(m['commands'] == commands, 'frozen native recipe drift')
    require(len(commands) == 75 and all(c.count('-o') == 1 for c in commands) and
            all('-c' in c and Path(c[0]).name == 'mos-mega65-clang' for c in commands[:73]) and
            Path(commands[73][0]).name == 'llvm-link' and commands[74][:3] == ['/usr/bin/setarch', 'x86_64', '-R'] and
            '-c' not in commands[74] and '-Wl,--emit-relocs' in commands[74], 'native recipe shape/link budget')
    ready = d.load(SEED + '/native/command-ready.json')
    derived = d.load(SEED + '/native/derived-inputs.json')
    includes = d.load(SEED + '/native/include-closure.json')
    require(includes['status'] == 'PASS' and includes['translation_units'] == 73, 'include closure not PASS')
    rows = {r['path']:r for r in m['inputs'] + m['tools']}
    live = [r['restored'] for r in ready['native']] + ready['toolchain'] + derived['all_generated'] + [derived['generated']]
    live += list(bindings(includes))
    for row in live:
        row = {**row, 'path':normalize(row['path'])}
        actual = verify_any(row, d.root)
        require(rows.get(actual['path']) == actual, 'consumed native input unbound: ' + actual['path'])
    # 2.5.4: NO native source seam.  Constants come from the Seed preflight; inputs and recipe are the 2.5.3
    # Seed r8 ones except the generated-constant seams (native_identity above).
    base_proof = d.verify(dict(path=CFG.BASE + '/native/command-proof.json', sha256=BASE_RECIPE_SHA))
    base_ready = CFG.BASE + '/native/command-ready.json'
    constants = CFG.PREFLIGHT + '/constants.json'
    for name in (base_proof['path'], base_ready, constants):
        require(name in rows, 'native identity authority unbound: ' + name)
    constants = d.load(constants)
    require(derived['code_bytes_before'] == CFG.BASE_STATIC_CODE_BYTES and
            derived['code_bytes_after'] == constants['LISP65_C2_LITE_STATIC_CODE_BYTES'] and
            derived['crc_tables'] == constants['crc_tables'] and derived['replacements'] == {
                NATIVE_CONSTANT_FLAGS[0] + CFG.BASE_PRODUCT_BUILD_ID + 'UL':
                    NATIVE_CONSTANT_FLAGS[0] + constants['LISP65_C2_PRODUCT_BUILD_ID'] + 'UL',
                NATIVE_CONSTANT_FLAGS[1] + str(CFG.BASE_SHELF_BYTES) + 'UL':
                    NATIVE_CONSTANT_FLAGS[1] + str(constants['LISP65_C2_PRODUCT_SHELF_BYTES']) + 'UL'},
            'wrong full-plane constants/closure')
    return native_identity(ready, derived, d.load(proof['path']), d.load(base_ready), d.load(base_proof['path'])['commands'])


def verify_manifest(d, m):
    require(m['format'] == FORMAT and m['seed_dir'] == SEED and m.get('link_seed_dir') == LINK_SEED and m['final_dir'] == FINAL and
            m['closure_complete'] is True and m['budget'] == F.BUDGET and
            m['media_adapter'] == 'c254_replay.rederive', 'wrong replay/layout/budget')
    require(m['installed_tools'] == F.installed_tools() and m['preview'] is False, 'candidate preview is not release authority')
    require(m['closure_roots'] == CLOSURE_ROOTS and m['reference_roots'] == REFERENCE_ROOTS,
            'closure policy changed')
    require(m['compiler_configs'] == compiler_configs(d.root), 'compiler configuration population changed')
    rows = {r['path']:r for r in m['inputs']}
    require(not rows.keys() & PROVENANCE_COPIES.keys(), 'mutable gate output bound as input')
    # 2.5.4: the generated Workbench tree is rebuilt by check-source (isolated by the sealed
    # runner) and by every gate; nothing under it may be a recipe input (Final r2 lesson).
    require(not any(Path(p).is_relative_to('build/bytecode') for p in rows),
            'mutable generated tree build/bytecode bound as input')
    require(len(rows) == len(m['inputs']), 'duplicate input')
    require(set(tree_files(d.root)) <= rows.keys(), 'closure population dropped/added file')
    require(set(F.installed_tools() + F.support_tools() + EXTRA_INPUTS + REFERENCE_ROOTS) <= rows.keys(),
            'required input missing')
    # 2.5.4: live emission inputs and every consumed package file (re-emitted ones below PREFLIGHT/packages).
    require(set(REEMIT_INPUTS + package_inputs(d.root)) <= rows.keys(), 'package re-emission input missing')
    require(all(not Path(p).is_relative_to(FINAL) and not Path(p).is_relative_to(d.run) for p in rows),
            'Final/source-run cannot be recipe inputs')
    for row in m['inputs']:
        verify_any(row, d.root)
    require(receipt_closure(rows, m['historical_references'], root=d.root) == m['receipt_population'],
            'receipt closure population mismatch')
    require(m['seed_receipt'] == rows[SEED + '/seed.json'] and m['seed_receipt']['sha256'] == SEED_SHA,
            'wrong Seed receipt')
    seed = d.load(SEED + '/seed.json')
    require(seed['status'] == 'PASS' and seed['product_links'] == 1 and seed['seed'] == 1 and seed['final'] == 0,
            'wrong Seed state')
    e3_identity(d.load(SEED + '/attempt.json'), d.load(SEED + '/source.json'), d.load(CFG.E3 + '/receipt.json'),
                d.load(CFG.E3 + '/attempt.json'), rows)
    continuation_identity(seed, d.load(SEED + '/continuation.json'), rows)
    require(set(m['artifacts']) == set(ARTIFACTS), 'artifact roles mismatch')
    for role,(suffix, sha) in ARTIFACTS.items():
        row = m['artifacts'][role]
        require(row['path'] == SEED + '/' + suffix and row['sha256'] == sha and rows.get(row['path']) == row,
                '2.5.4 artifact identity mismatch: ' + role)
    require(m['tools'] == tools(), 'executable/toolchain drift')
    verify_native(d, m)
    # This is read-only validation, not preflight generation or Seed execution.
    import c254_product as P
    P.verify_preflight()
    verify_readback(d, d.load(SEED + '/media.json'), m['artifacts']['D81'])
    return [rows[p] for p in sorted(rows)]


def prepare(out, preview=False):
    require(preview or Path(__file__).resolve() == ROOT / F.installed_tools()[1],
            'prepare release replay with the installed tool; candidates require --preview')
    dest = ROOT / out
    require(Path(out).is_relative_to(PREP) and str(Path(out)) != PREP and '..' not in Path(out).parts,
            'preparation must be a fresh child of ' + PREP)
    require(not any(p.is_symlink() for p in (dest, *dest.parents)), 'preparation symlink')
    (ROOT / PREP).mkdir(exist_ok=True)  # 2.5.4: the preparation parent is new; children stay write-once.
    dest.mkdir()  # Preserve incomplete preparation attempts, too.
    import c254_product as P
    P.verify_preflight()
    names = tree_files() + EXTRA_INPUTS + REEMIT_INPUTS + package_inputs()
    installed = [PREP + '/' + n for n in F.TOOL_NAMES] if preview else F.installed_tools()
    names += installed
    rows = {n:bind_any(n) for n in sorted(set(names))}
    historical = {}
    receipts = receipt_closure(rows, historical, dest=dest)
    m = dict(format=FORMAT, preview=preview, seed_dir=SEED, link_seed_dir=LINK_SEED, final_dir=FINAL, budget=F.BUDGET,
        installed_tools=installed, closure_complete=True, closure_roots=CLOSURE_ROOTS,
        compiler_configs=compiler_configs(),
        reference_roots=REFERENCE_ROOTS, receipt_population=receipts,
        seed_receipt=rows[SEED + '/seed.json'], native_authority=rows[SEED + '/native/command-proof.json'],
        inputs=[rows[p] for p in sorted(rows)], historical_references=historical, tools=tools(),
        commands=json.loads((ROOT / SEED / 'native/command-proof.json').read_text())['commands'],
        artifacts={role:rows[SEED + '/' + suffix] for role,(suffix,_) in ARTIFACTS.items()},
        media_adapter='c254_replay.rederive',
        audit='Frozen 2.5.4 Seed native inputs (= 2.5.3 Seed r8 inputs outside generated-constant seams); only wplto output '
              'references rebase. Imported c254 inventory/media; no Seed call, no package re-emission (preflight outputs are bound inputs). '
              'Historical references resolve to exact snapshots and do not authorize changes to live consumed inputs.')
    # Validate even previews against the complete production admission contract,
    # changing only their installation marker within this local check.
    from unittest.mock import patch
    d = Driver('build/offline-source-placeholder', out + '/replay.json', '0'*64)
    m['driver_configuration'] = driver_configuration(d)
    checked = {**m, 'preview':False}
    with patch.object(F, 'installed_tools', return_value=installed):
        verify_manifest(d, checked)
    save(dest / 'replay.json', m)
    return dict(status='PASS', replay=bind_any(out + '/replay.json'), preview=preview,
                inputs=len(rows), recursive_receipts=len(receipts), historical_copies=len(historical),
                product_commands=0, source_admission='NOT RUN; reviewer sealed run required')


def mutation_paths(event, args):
    """Resolve audited mutations, including dir_fd operations used by rmtree."""
    values = []
    if event == 'open':
        path, mode, flags = args
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            values = [(path, -1)]
    elif event in ('os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.utime', 'os.truncate'):
        fd = (args[1] if event in ('os.remove', 'os.rmdir') else
              args[2] if event in ('os.mkdir', 'os.chmod') else
              args[3] if event == 'os.utime' and len(args) > 3 else -1)
        values = [(args[0], fd)]
    elif event in ('os.rename', 'os.link'):
        values = [(args[0], args[2]), (args[1], args[3])]
    elif event == 'os.symlink':
        raise ValueError('symlink creation forbidden')
    for name, fd in values:
        if isinstance(name, int):
            yield Path('/proc/self/fd/' + str(name)).resolve()
        elif isinstance(name, (str, bytes)):
            p = Path(os.fsdecode(name))
            if not p.is_absolute() and isinstance(fd, int) and fd >= 0:
                p = Path('/proc/self/fd/' + str(fd)).resolve() / p
            yield p.resolve()


class WriteScope:
    """Python write/network guard; child processes separately use pinned argv."""
    def __init__(self, out):
        self.out = out.resolve()
        self.active = False

    def audit(self, event, args):
        if not self.active:
            return
        require(not event.startswith('socket.') and event not in ('os.system', 'os.exec'),
                'forbidden network/direct process operation: ' + event)
        for path in mutation_paths(event, args):
            require(path.is_relative_to(self.out), 'write outside attempt: ' + str(path))
            require(not (path == self.out and event in ('os.rmdir', 'os.rename', 'os.remove')),
                    'attempt directory is irrevocable')
            anchors = ('final-invocation.json', 'product-link-claim.json', 'final-identity.json', 'media-execution.json')
            require(not (path.parent == self.out and path.name in anchors and path.exists()),
                    'attempt receipt is write-once: ' + str(path))

    def __enter__(self):
        self.active = True
        sys.addaudithook(self.audit)
        return self

    def __exit__(self, *error):
        self.active = False


def execution_env(d):
    # No ambient include/library/compiler override can alter the frozen recipe.
    return dict(PATH='/usr/bin:/bin', LANG='C', LC_ALL='C', PYTHONDONTWRITEBYTECODE='1',
                GIT_OPTIONAL_LOCKS='0', TMPDIR=str(d.path(FINAL + '/tmp')))


def stager_commands(d):
    med = FINAL + '/' + MEDIA
    stage = med + '/stager'
    compiler = str(d.root / 'tools/llvm-mos/bin/mos-mega65-clang')
    build_id = d.load(SEED + '/' + MEDIA + '/descriptor-stager-receipt.json')['build_id']
    return [
        [compiler, '-std=c99', '-Oz', '-Wall', '-Wextra', '-Werror', '-DLISP65_C2_LITE_MEDIA_STAGER',
         '-DLISP65_STARTUP_REQUIRE_EXPERIENCE', '-Iscripts', '-include', str(d.root / stage / 'delivery-roles.h'),
         f'-DR3_EXPECTED_PRODUCT_BUILD_ID=0x{build_id:08x}UL', '-c', stage + '/delivery-stager-main.c',
         '-o', stage + '/autoboot-main.o'],
        [compiler, '-Qunused-arguments', '-c', med + '/cold-stager-chain.s', '-o', stage + '/autoboot-chain.o'],
        [compiler, '-Qunused-arguments', '-c', 'scripts/r3-rom-write-enable.s', '-o', stage + '/autoboot-rom-write-enable.o'],
        ['/usr/bin/setarch', os.uname().machine, '-R', compiler, '-Oz', '-Wl,-Map,' + stage + '/autoboot.c65.map',
         stage + '/autoboot-main.o', stage + '/autoboot-chain.o', stage + '/autoboot-rom-write-enable.o',
         '-o', med + '/artifacts/autoboot.c65'],
    ]


class MediaScope(WriteScope):
    """Restrict inherited subprocesses to read-only ELF tools and one cold stager.

    All Python reads inside the repository must be pinned inputs or this Final's
    outputs. No generic compiler/linker/Seed command is admitted in this phase.
    """
    def __init__(self, d, admission):
        super().__init__(d.path(FINAL))
        self.d = d
        self.allowed_reads = {(d.root / r['path']).resolve() for r in admission['input_bindings'] + admission['tools']}
        self.reads, self.commands = set(), []
        self.stager = stager_commands(d)
        self.stager_index = 0
        self.host_binary = None
        self.host_runs = 0
        self.launch = None

    def audit(self, event, args):
        if not self.active:
            return
        # Popen may internally use posix_spawn after its audited launch.
        if event == 'os.posix_spawn':
            require(self.launch is not None and list(map(str, args[1])) == self.launch,
                    'unreviewed direct media process')
            return
        super().audit(event, args)
        if event == 'subprocess.Popen':
            require(self.launch is not None and list(map(str, args[1])) == self.launch,
                    'unreviewed media subprocess')
        if event == 'open' and isinstance(args[0], (str, bytes)) and not list(mutation_paths(event, args)):
            p = Path(os.fsdecode(args[0])).resolve()
            if p.is_relative_to(self.d.root) and not p.is_relative_to(self.out) and p.is_file():
                require(p in self.allowed_reads, 'unbound media read: ' + str(p))
                self.reads.add(str(p.relative_to(self.d.root)))

    def classify(self, command):
        if self.stager_index < 4 and command == self.stager[self.stager_index]:
            self.stager_index += 1
            return 'cold-stager'
        readobj = str(self.d.root / 'tools/llvm-mos/bin/llvm-readobj')
        objdump = str(self.d.root / 'tools/llvm-mos/bin/llvm-objdump')
        if command[0] == readobj:
            require(command[1:-1] in (
                ['--program-headers', '--elf-output-style=JSON'],
                ['--elf-output-style=JSON', '--sections', '--symbols', '--relocations'],
                ['--elf-output-style=JSON', '--sections', '--symbols', '--relocations', '--section-data']),
                'unexpected readobj arguments')
            require((self.d.root / command[-1]).resolve() in self.allowed_reads or
                    (self.d.root / command[-1]).resolve().is_relative_to(self.out), 'unbound readobj ELF')
            return 'ELF-read-only'
        if command[0] == str(symbol_tool(self.d.root)):
            require(len(command) == 3 and command[1] == '--defined-only' and
                    (self.d.root / command[2]).resolve().is_relative_to(self.out), 'unexpected nm arguments')
            return 'ELF-read-only'
        if command[0] == str(self.d.root / 'tools/llvm-mos/bin/llvm-objcopy'):
            require(len(command) == 5 and command[1] == '--dump-section' and '=' in command[2],
                    'unexpected objcopy arguments')
            section, target = command[2].split('=', 1)
            require(section in ('.lisp65_boot_bank3_stage', '.lisp65_workbench_overlay') and
                    all((self.d.root / p).resolve().is_relative_to(self.out / MEDIA / 'artifacts')
                        for p in (target, command[3], command[4])), 'objcopy extraction outside media')
            return 'ELF-extraction'
        if command[0] == objdump:
            require(len(command) == 6 and command[1] == '-d' and command[2].startswith('--section=') and
                    command[3].startswith('--start-address=') and command[4].startswith('--stop-address=') and
                    ((self.d.root / command[-1]).resolve() in self.allowed_reads or
                     (self.d.root / command[-1]).resolve().is_relative_to(self.out)),
                    'unexpected objdump arguments')   # 2.5.4 inventory lists the Final's own ELF too
            return 'ELF-read-only'
        if self.host_binary is not None and command == [self.host_binary] and self.host_runs == 0:
            self.host_runs += 1
            return 'host-ABI-emitter'
        raise ValueError('forbidden media command: ' + repr(command))

    def authorize(self, command):
        command = list(map(str, command))
        if command[:len(PRIORITY)] == PRIORITY:
            command = command[len(PRIORITY):]
        # Host contract emitter is the one reviewed non-product host compiler.
        if command and command[0] in ('cc', '/usr/bin/cc'):
            import asm_c_constant_contract as A
            generator = str(self.d.root / A.load_contract()['generator'])
            require(len(command) == 11 and command[1:10] == [
                '-std=c99', '-Wall', '-Wextra', '-Werror', '-Isrc', '-Iscripts',
                '-DLISP65_C2_LITE_MEDIA_STAGER', generator, '-o'] and self.host_binary is None,
                'unexpected host ABI compiler')
            target = Path(command[-1]).resolve()
            require(target.parent.parent == self.out / 'tmp' and target.parent.name.startswith('lisp65-asm-contract-') and
                    target.name == 'emit', 'host emitter outside Final tmp')
            self.host_binary = str(target)
            command[0] = '/usr/bin/cc'
            kind = 'host-ABI-compile'
        else:
            kind = self.classify(command)
        return command, kind

    def run(self, raw_run, command, *args, **kwargs):
        command, kind = self.authorize(command)
        require(not kwargs.get('shell', False), 'shell command forbidden')
        kwargs['cwd'] = self.d.root
        kwargs['env'] = execution_env(self.d)
        launched = PRIORITY + command
        self.launch = launched
        row = dict(kind=kind, command=launched, returncode=None)
        self.commands.append(row)
        try:
            result = raw_run(launched, *args, **kwargs)
            row['returncode'] = result.returncode
            require(result.returncode == 0, 'media helper failed; no retry')
            return result
        finally:
            self.launch = None


def rederive(d, admission):
    """Re-enter only the unchanged producer's inventory and media functions."""
    import c254_product as P
    import c254_seed_continue_r1b as R1B
    import comfort_default_media as C
    from unittest.mock import patch
    out = d.path(FINAL)
    here = out / 'native'
    here.mkdir()
    # These receipts describe consumed immutable Seed input files. Keeping their
    # bindings in Seed coordinates is intentional; input paths were not rebased.
    for name in ('derived-inputs.json', 'plane-price.json'):
        with (here / name).open('xb') as stream:
            stream.write(d.path(SEED + '/native/' + name).read_bytes())
    scope = MediaScope(d, admission)
    raw_run = subprocess.run
    result = dict(status='FAIL', product_links=0, stager_builds=0,
                  producer=d.bind(PRODUCT),
                  functions=['inventory', 'media'], commands=[], read_bindings=[],
                  # The Final ELF must be byte-identical to the Seed ELF, so it carries the same reviewed swap:
                  # inventory() runs inside the continuation tool's class (pinned to both ELF sha256), as the Seed did.
                  wrapped=['c254_product.data_attribution'], wrapper=d.bind('tools/host-lisp/' + PINS.SEED_CONTINUE_TOOL),
                  reviewed_pair=None)
    # Producer helpers deliberately mutate module globals. This is one CLI
    # attempt, but restore all overridden roots and environment even on failure.
    with patch.object(P, 'BUILD', out), patch.object(P, 'HERE', here), \
         patch.object(P.S, 'HERE', here), patch.object(P.S, 'PRIORITY', PRIORITY), \
         patch.object(P.S, 'ENV', execution_env(d)), \
         patch.object(tempfile, 'tempdir', str(out / 'tmp')), \
         patch.object(subprocess, 'run', side_effect=lambda *a, **kw:scope.run(raw_run, *a, **kw)), scope:
        try:
            with R1B.reviewed_pair_class() as pair:
                P.inventory()
            result['reviewed_pair'] = dict(applied=pair['applied'])
            P.media()
            require(scope.stager_index == 4 and scope.host_runs == 1, 'incomplete media/stager recipe')
            stager = d.load(FINAL + '/' + MEDIA + '/descriptor-stager-receipt.json')
            require(stager['status'] == 'PASS' and stager['product_links'] == 0 and stager['stager_builds'] == 1,
                    'stager receipt budget mismatch')
            result.update(status='PASS', stager_builds=1)
        finally:
            result['commands'] = scope.commands
            result['read_bindings'] = [d.bind(p) for p in sorted(scope.reads)]
            save(out / 'media-execution.json', result)
    return result


def offline_selftest(replay):
    from types import SimpleNamespace
    from unittest.mock import patch
    import c254_seal as Z
    import c254_product as P
    passed = []

    def reject(label, fn, expected=None):
        try:
            fn()
        except (ValueError, OSError, KeyError, AssertionError) as error:
            if expected is not None:
                require(type(error) is ValueError and str(error).startswith(expected),
                        'negative reached wrong guard: ' + label + ': ' + repr(error))
            passed.append(label)
        else:
            raise AssertionError('negative survived: ' + label)

    passed.extend(e3_identity_selftest())
    # No subprocess, network, compiler, link, media CLI or Git invocation can
    # occur in this selftest. Actual 2.5.4 bytes/closure are still read and checked.
    with patch.object(subprocess, 'Popen', side_effect=AssertionError('offline: subprocess forbidden')), \
         patch.object(P, 'seed', side_effect=AssertionError('Seed forbidden')), \
         patch.object(P, 'prepare_native', side_effect=AssertionError('native preparation forbidden')):
        d = Driver('build/offline-source-never-admitted', replay, '0'*64)
        d.replay_sha256 = d.bind(replay)['sha256']
        manifest = d.load(replay)
        require(type(manifest['preview']) is bool, 'invalid replay installation marker')
        input_map = {r['path']:r for r in manifest['inputs']}
        for module, name in zip((F, sys.modules[__name__], Z), manifest['installed_tools'], strict=True):
            require(digest(Path(module.__file__).read_bytes()) == input_map[name]['sha256'],
                    'selftest code differs from replay tooling: ' + name)
        checked = {**manifest, 'preview':False}
        d.check_driver_configuration = lambda m:None  # No subprocess in offline admission.
        d.source = lambda:dict(head='SYNTHETIC; NOT A SEALED HEAD', sealed_run=d.run,
                              source={}, source_log={}, source_start={}, source_mounts={})
        d.git = lambda *args:args[-1] if args[0] == 'ls-files' else ''
        original_load = d.load
        d.load = lambda name:checked if name == replay else original_load(name)
        with patch.object(F, 'installed_tools', return_value=manifest['installed_tools']), \
             patch.object(F, '__file__', str(ROOT / manifest['installed_tools'][0])):
            admission = d.admit()
            require(len(admission['commands']) == 75 and len(admission['pairs']) == 4, 'real admission shape')
            passed.append('actual 2.5.4 closure, 75-command projection and persisted 20-file D81 readback')
            for label, mutate in (
                ('r6 replay rejected', lambda m:m.update(format='o2-lite-replay-r6')),
                ('preview cannot be Final authority', lambda m:m.update(preview=True)),
                ('second product link budget rejected', lambda m:m.update(budget=dict(F.BUDGET, link=2))),
                ('duplicate input rejected', lambda m:m['inputs'].append(m['inputs'][0])),
                ('omitted input rejected', lambda m:m['inputs'].pop(0)),
                ('native recipe mutation rejected', lambda m:m['commands'][74].append('-DUNREVIEWED')),
                ('r6 native authority rejected', lambda m:m['native_authority'].update(sha256='0'*64)),
                ('wrong D81 identity rejected', lambda m:m['artifacts']['D81'].update(sha256='0'*64)),
                ('missing historical resolution rejected', lambda m:m['historical_references'].pop(next(iter(m['historical_references'])))),
                ('tool drift rejected', lambda m:m['tools'][0].update(sha256='0'*64)),
                ('live input drift rejected', lambda m:m['inputs'][0].update(sha256='0'*64)),
                ('mutable gate output input rejected', lambda m:m['inputs'].append(
                    dict(path=next(iter(PROVENANCE_COPIES)), bytes=0, sha256='0'*64))),
            ):
                bad = copy.deepcopy(checked)
                mutate(bad)
                reject(label, lambda:verify_manifest(d, bad))
            for path in PROVENANCE_COPIES:
                key = next(k for k in checked['historical_references'] if k.startswith(path + '@'))
                bad = copy.deepcopy(checked)
                bad['historical_references'][key]['sha256'] = '0'*64
                reject('provenance copy drift rejected: ' + path,
                       lambda:verify_manifest(d, bad), 'mutable provenance copy mismatch:')
        with patch.object(F, 'installed_tools', return_value=manifest['installed_tools']):
            original_read = Path.read_bytes
            for config in ('tools/llvm-mos/bin/mos-mega65.cfg', 'tools/llvm-mos/bin/mos-commodore.cfg',
                           'tools/llvm-mos/bin/mos-common.cfg'):
                def drift(path):
                    raw = original_read(path)
                    return raw + b'\n# configuration drift\n' if path == ROOT / config else raw
                with patch.object(Path, 'read_bytes', drift):
                    reject('compiler configuration drift rejected: ' + config,
                           lambda:verify_manifest(d, checked), 'binding drift: ' + config)
            bad = copy.deepcopy(checked)
            bad['compiler_configs'].pop()
            reject('compiler configuration population rejected', lambda:verify_manifest(d, bad),
                   'compiler configuration population changed')
        # Exercise selection validation with driver-only output, never a process.
        selected = 'Configuration file: ' + str(ROOT / CONFIG_ENTRY) + '\n'
        with patch.object(subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='', stderr=selected)):
            Driver.check_driver_configuration(d, checked)
            bad = {**checked, 'driver_configuration':{}}
            reject('compiler selection receipt drift rejected', lambda:Driver.check_driver_configuration(d, bad),
                   'compiler default configuration selection drift')
        with patch.object(subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='',
                              stderr='Configuration file: /unbound/mos-mega65.cfg\n')):
            reject('higher priority compiler config rejected', lambda:driver_configuration(d),
                   'unexpected compiler default configuration selection')
        reject('preview rejected without test override', lambda:verify_manifest(d, {**manifest, 'preview':True}))
        for suffix in ('.elf', '', '.lto.o'):
            seedpath = SEED + '/wplto/resident-island-seed.prg' + suffix
            dest = FINAL + '/wplto/resident-island-seed.prg' + suffix
            require(any(p['seed']['path'] == seedpath and p['destination'] == dest for p in admission['pairs']),
                    'native mapping missing')
        for before, after in zip(manifest['commands'], admission['commands'], strict=True):
            # No Seed/native input path, flag or executable changes.
            require([x.replace(FINAL + '/wplto', LINK_SEED + '/wplto') for x in after] == before, 'projection not reversible')
        passed.append('only native wplto paths rebased; Seed/native input paths retained')
        reject('unknown embedded output reference rejected', lambda:d.rebase(
            [['/tool', '--unknown=' + LINK_SEED + '/wplto/x']], {LINK_SEED + '/wplto':FINAL + '/wplto'}, allowed_seed=LINK_SEED))
        reject('traversal rejected', lambda:d.path('../outside'))
        reject('overlapping source/Final rejected', lambda:Driver(FINAL + '/source', replay, '0'*64))

        with tempfile.TemporaryDirectory(prefix='selftest-', dir=ROOT / PREP) as scratch:
            root = Path(scratch)
            t = Driver('build/source', 'build/replay.json', '0'*64, root=root)
            def put(name, value):
                path = t.path(name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(encoded(value))
            names = F.installed_tools() + F.support_tools() + [
                'build/replay.json', 'Makefile', 'src/vm.c', 'protection.json']
            for name in names:
                put(name, dict(synthetic=True))
            put('build/protected-native.h', dict(synthetic='protected'))
            put('protection.json', t.bind('build/protected-native.h'))
            run = t.path(t.run)
            run.mkdir(parents=True)
            (run / 'check-source.log').write_bytes(b'synthetic source run\n')
            tracked = {n:t.bind(n)['sha256'] for n in names}
            committed = {}
            for n in names:
                raw = t.path(n).read_bytes()
                committed[n] = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            source = dict(target='make -k check-source', exit_code=0, head_before='a'*40, head_after='a'*40,
                changed_protected_files=0, changed_files=[], changed_sealed_artifacts=[], log=t.bind(t.run + '/check-source.log'),
                protected_files=len(tracked), sealed_artifacts_read_only=1,
                read_only_mounts=dict(individual=1, directories=1))
            sealed = {'build/protected-native.h':t.bind('build/protected-native.h')['sha256']}
            start = dict(head='a'*40, tracked=tracked, sealed_paths=list(sealed), sealed_sha256=sealed)
            mounts = dict(command=['make', '-k', 'check-source'])
            put(t.run + '/receipt.json', source)
            put(t.run + '/start.json', start)
            put(t.run + '/mounts.json', mounts)
            def fixture_git(*args):
                if args == ('rev-parse', 'HEAD'):
                    return 'a'*40
                if args == ('ls-files', '-z'):
                    return '\0'.join(names) + '\0'
                if args[:1] == ('ls-tree',):
                    return ''.join('100644 blob ' + oid + '\t' + n + '\0' for n, oid in committed.items())
                if args[:1] == ('status',):
                    return ''
                raise AssertionError('unexpected fixture git: ' + repr(args))
            t.git = fixture_git
            t.source()
            passed.append('selected sealed source receipt/start/log/full population and commit contract')
            for label, changes in (
                ('red source rejected', dict(exit_code=2)),
                ('wrong source HEAD rejected', dict(head_after='b'*40)),
                ('protected change rejected', dict(changed_protected_files=1)),
                ('changed sealed artifact rejected', dict(changed_sealed_artifacts=['drift'])),
                ('wrong source target rejected', dict(target='make check-host')),
                ('missing read-only mounts rejected', dict(read_only_mounts=dict(individual=0, directories=0))),
            ):
                put(t.run + '/receipt.json', {**source, **changes})
                reject(label, t.source)
            # Correct bytes/hash: these reach the independent parent/name guards.
            for name, expected in (
                ('build/other/check-source.log', 'wrong selected source run/log'),
                (t.run + '/wrong-name.log', 'wrong selected source log'),
            ):
                t.path(name).parent.mkdir(parents=True, exist_ok=True)
                t.path(name).write_bytes((run / 'check-source.log').read_bytes())
                put(t.run + '/receipt.json', {**source, 'log':t.bind(name)})
                reject('foreign source log rejected: ' + name, t.source, expected)
            put(t.run + '/receipt.json', source)
            # Preserve populations and every other field; mutate only the start hash.
            for name in F.installed_tools() + F.support_tools() + [t.replay, 'Makefile', 'src/vm.c']:
                bad = copy.deepcopy(start)
                bad['tracked'][name] = '0'*64
                put(t.run + '/start.json', bad)
                expected = ('source run did not protect current tooling/recipe: ' if name not in ('Makefile', 'src/vm.c')
                            else 'source tracked start hash mismatch: ') + name
                reject('source start drift rejected: ' + name, t.source, expected)
            bad = copy.deepcopy(start)
            bad['sealed_sha256']['build/protected-native.h'] = '0'*64
            put(t.run + '/start.json', bad)
            reject('sealed native start drift rejected', t.source, 'source sealed start hash mismatch:')
            put(t.run + '/start.json', start)
            # Drift after startup, with unchanged HEAD; status cannot hide it.
            name = F.installed_tools()[0]
            raw = t.path(name).read_bytes()
            t.path(name).write_bytes(raw + b' ')
            reject('tool drift after startup rejected', t.source, 'source run did not protect current tooling/recipe:')
            t.path(name).write_bytes(raw)
            # Dirty start/current bytes agree but do not match the sealed commit.
            raw = t.path('Makefile').read_bytes()
            t.path('Makefile').write_bytes(raw + b' ')
            bad = copy.deepcopy(start)
            bad['tracked']['Makefile'] = t.bind('Makefile')['sha256']
            put(t.run + '/start.json', bad)
            reject('dirty start matching current rejected', t.source, 'source bytes differ from sealed commit: Makefile')
            t.path('Makefile').write_bytes(raw)
            put(t.run + '/start.json', start)
            for field, expected in (('tracked', 'source tracked population mismatch'),
                                    ('sealed', 'source sealed population mismatch')):
                bad = copy.deepcopy(start)
                rc = copy.deepcopy(source)
                if field == 'tracked':
                    bad['tracked'].pop('Makefile')
                    rc['protected_files'] -= 1
                else:
                    bad['sealed_paths'] = ['build/another.h']
                    bad['sealed_sha256'] = {'build/another.h':'0'*64}
                put(t.run + '/start.json', bad)
                put(t.run + '/receipt.json', rc)
                reject('source population substitution rejected: ' + field, t.source, expected)
            put(t.run + '/start.json', start)
            put(t.run + '/receipt.json', source)
            with patch.object(t, 'git', side_effect=lambda *a:'a'*40 if a == ('rev-parse', 'HEAD') else ' M tracked'):
                reject('dirty tracked tree rejected', t.source)
            original = (run / 'check-source.log').read_bytes()
            (run / 'check-source.log').write_bytes(b'drift')
            reject('source log drift rejected', t.source)
            (run / 'check-source.log').write_bytes(original)
            symlink = root / 'build/alias'
            symlink.symlink_to(run)
            reject('symlink source alias rejected', lambda:t.path('build/alias/receipt.json'))
            symlink.unlink()

            # Timestamp-valid sibling cache holds different same-size source.
            import importlib.util
            import marshal
            import struct
            cache_source = root / 'cache-fixture.py'
            old, current = b'value = "earlier"\n', b'value = "current"\n'
            cache_source.write_bytes(current)
            stamp = cache_source.stat()
            with patch.object(sys, 'pycache_prefix', None):
                cache_path = Path(importlib.util.cache_from_source(str(cache_source)))
            cache_path.parent.mkdir()
            cache_path.write_bytes(importlib.util.MAGIC_NUMBER +
                struct.pack('<III', 0, int(stamp.st_mtime), len(old)) +
                marshal.dumps(compile(old, str(cache_source), 'exec')))
            spec = importlib.util.spec_from_file_location('r7_cache_fixture', cache_source)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            require(module.value == 'current' and sys.dont_write_bytecode and
                    sys.pycache_prefix and not list(Path(sys.pycache_prefix).rglob('*.pyc')),
                    'unbound bytecode executed or cache namespace not empty')
            passed.append('timestamp-valid foreign cache ignored; current source executed')
            reject('explicit bytecode cache read rejected', cache_path.read_bytes,
                   'unbound bytecode cache read forbidden:')

            # Real write guard events, including descriptor-relative mutations.
            boundary = t.path(FINAL)
            boundary.mkdir()
            with WriteScope(boundary):
                (boundary / 'allowed').write_bytes(b'x')
                reject('write outside attempt rejected', lambda:(root / 'escape').write_bytes(b'x'))
                reject('rename outside attempt rejected', lambda:(boundary / 'allowed').rename(root / 'escape'))
                reject('symlink creation rejected', lambda:(boundary / 'alias').symlink_to(root))
                save(boundary / 'final-invocation.json', dict(synthetic=True))
                reject('attempt receipt overwrite rejected', lambda:(boundary / 'final-invocation.json').write_bytes(b'x'))
                reject('attempt receipt deletion rejected', lambda:(boundary / 'final-invocation.json').unlink())
                reject('attempt root deletion rejected', lambda:os.rmdir(boundary))
                fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    reject('dir_fd escape rejected', lambda:os.mkdir('escape', dir_fd=fd))
                finally:
                    os.close(fd)
            shutil.rmtree(boundary)

            # Actual final() lifecycle, with an explicitly synthetic executor.
            # It still claims atomically, writes/retains failures, counts commands,
            # checks exact bytes and re-admits after the media transaction.
            seed_rows = {}
            for role,(suffix,_) in ARTIFACTS.items():
                path = t.path(SEED + '/' + suffix)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(('synthetic-' + role).encode())
                seed_rows[role] = t.bind(SEED + '/' + suffix)
            put(SEED + '/' + MEDIA + '/descriptor-stager-receipt.json', dict(build_id=4094160407))
            a = dict(admission)
            a.update(head='a'*40, sealed_run=t.run, source=t.bind(t.run + '/receipt.json'),
                source_log=t.bind(t.run + '/check-source.log'), source_start=t.bind(t.run + '/start.json'),
                source_mounts=t.bind(t.run + '/mounts.json'), input_bindings=[], tools=[],
                replay=t.bind('build/replay.json'), seed_receipt=seed_rows['ELF'],
                pairs=[dict(role=role, seed=seed_rows[role], destination=FINAL + '/' + ARTIFACTS[role][0]) for role in sorted(ARTIFACTS)])
            calls, media_calls = [], []
            def admit(claimed=False):
                require(claimed or not os.path.lexists(boundary), 'Final directory exists; no retry')
                return copy.deepcopy(a)
            def execute(command, log):
                i = len(calls)
                calls.append(command)
                log.write_bytes(b'synthetic command; not executed\n')
                if i == 74:
                    require((boundary / 'product-link-claim.json').is_file(), 'link launched without claim')
                    for role in ('ELF', 'PRG', 'LTO'):
                        p = t.path(FINAL + '/' + ARTIFACTS[role][0])
                        p.write_bytes(t.path(seed_rows[role]['path']).read_bytes())
            def fake_media(admitted):
                media_calls.append('media')
                p = t.path(FINAL + '/' + ARTIFACTS['D81'][0])
                p.parent.mkdir()
                p.write_bytes(t.path(seed_rows['D81']['path']).read_bytes())
                put(FINAL + '/media.json', dict(status='SYNTHETIC'))
                import asm_c_constant_contract as A
                generator = str(t.root / A.load_contract()['generator'])
                emit = str(boundary / 'tmp/lisp65-asm-contract-synthetic/emit')
                transcript = []
                ms = MediaScope(t, a)
                commands = [['/usr/bin/cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-Isrc', '-Iscripts',
                             '-DLISP65_C2_LITE_MEDIA_STAGER', generator, '-o', emit], [emit]] + ms.stager
                for c in commands:
                    c, kind = ms.authorize(c)
                    transcript.append(dict(kind=kind, command=PRIORITY+c, returncode=0))
                result = dict(product_links=0, stager_builds=1, status='PASS', commands=transcript,
                              producer=t.bind(PRODUCT),
                              functions=['inventory', 'media'], read_bindings=[])
                put(FINAL + '/media-execution.json', result)
                return result
            t.admit, t.execute, t.media, t.idle = admit, execute, fake_media, lambda:None
            t.readback = lambda name:t.bind(name)  # Actual D81 readback tested above.
            result = t.final()
            require(result['status'] == 'PASS' and len(calls) == 75 and media_calls == ['media'] and
                    result['native_commands_consumed'] == 75 and result['product_links_claimed'] == 1,
                    'synthetic Final lifecycle failed')
            passed.append('synthetic Final: one attempt, 75 commands, one claimed product link, one media transaction')
            reject('successful Final retry rejected', t.final)
            for role in ARTIFACTS:
                p = t.path(FINAL + '/' + ARTIFACTS[role][0]); raw = p.read_bytes()
                p.write_bytes(raw + b'drift')
                reject('Final byte mismatch rejected: ' + role, lambda:t.identity(a))
                p.write_bytes(raw)
            # A fresh private synthetic root represents a separately named test,
            # never removal/retry of the real build/o2-lite-final-r7c attempt.
            for label, fail_at in [('compile failure', 0), ('product link failure', 74)]:
                child = root / label.replace(' ', '-')
                child.mkdir()
                fail = Driver('build/source', 'build/replay.json', '0'*64, root=child)
                (child / 'build').mkdir()
                fail.idle = lambda:None
                fail.admit = lambda claimed=False: copy.deepcopy(a) if claimed or not fail.path(FINAL).exists() else (_ for _ in ()).throw(ValueError('no retry'))
                count = []
                def error_execute(command, log):
                    count.append(command)
                    log.write_bytes(b'synthetic failure test\n')
                    require(len(count)-1 != fail_at, 'injected native failure')
                fail.execute = error_execute
                fail.media = lambda _: (_ for _ in ()).throw(AssertionError('media after native failure'))
                reject(label + ' retained', fail.final)
                failure = fail.load(FINAL + '/final-identity.json')
                require(failure['status'] == 'FAIL' and failure['native_commands_consumed'] == fail_at and
                        failure['product_links_claimed'] == (1 if fail_at == 74 else 0), 'failure claim accounting')
                reject(label + ' retry rejected', fail.final)

            # Exercise the real seal evidence verifier against the synthetic Final.
            evidence_seal = Z.Seal(t)
            evidence_seal.evidence()
            passed.append('seal evidence verifier accepts complete synthetic Final transcript')
            identity_path = t.path(FINAL + '/final-identity.json')
            original_identity = identity_path.read_bytes()
            for label, changes in (
                ('seal rejects unconsumed native command', dict(native_commands_consumed=74)),
                ('seal rejects second product link claim', dict(product_links_claimed=2)),
                ('seal rejects missing media transaction', dict(media_transactions=0)),
                ('seal rejects changed source selection', dict(sealed_run='build/wrong')),
            ):
                identity_path.write_bytes(encoded({**result, **changes}))
                reject(label, evidence_seal.evidence)
                identity_path.write_bytes(original_identity)
            helper_path = t.path(FINAL + '/media-execution.json')
            original_helper = helper_path.read_bytes()
            helper = json.loads(original_helper)
            helper['commands'][-1]['command'].append('-DUNREVIEWED')
            helper_path.write_bytes(encoded(helper))
            identity_path.write_bytes(encoded({**result, 'media_execution':t.bind(FINAL + '/media-execution.json')}))
            reject('seal rejects changed media subprocess transcript', evidence_seal.evidence)
            helper_path.write_bytes(original_helper)
            identity_path.write_bytes(original_identity)

            # Immutable seal/copy mechanism, with admission substituted only here.
            small, large = 'small.json', 'large.json'
            put(small, {})
            put(large, dict(data='x'*200))
            rows = [t.bind(small), t.bind(large)]
            seal = Z.Seal(t)
            seal.evidence = lambda:(a, result, [t.verify(r) for r in rows])
            with patch.object(Z, 'LIMIT', 100):
                seal.seal(); seal.check()
                passed.append('seal/check with plain and deterministic gzip receipt copies')
                reject('immutable seal retry rejected', seal.seal)
                original = t.path(seal.manifest).read_bytes()
                for label, mutate in (
                    ('wrong seal source run rejected', lambda m:m.update(source_run='wrong')),
                    ('wrong seal HEAD rejected', lambda m:m.update(source_head='b'*40)),
                    ('missing receipt copy rejected', lambda m:m['receipt_copies'].pop()),
                    ('duplicate receipt copy rejected', lambda m:m['receipt_copies'].__setitem__(1, m['receipt_copies'][0])),
                ):
                    bad = json.loads(original); mutate(bad)
                    t.path(seal.manifest).write_bytes(encoded(bad))
                    reject(label, seal.check)
                    t.path(seal.manifest).write_bytes(original)
                cp = t.load(seal.manifest)['receipt_copies'][0]['copy']['path']
                t.path(cp).write_bytes(b'corrupt')
                reject('seal copy drift rejected', seal.check)

        # 2.5.4 pure controls on the REAL Seed receipts: native identity with the 2.5.3 Seed r8, index delta rule.
        base_ready = d.load(CFG.BASE + '/native/command-ready.json')
        base_commands = d.load(CFG.BASE + '/native/command-proof.json')['commands']
        real = [d.load(SEED + '/native/' + n) for n in ('command-ready.json', 'derived-inputs.json', 'command-proof.json')]
        census = native_identity(*real, base_ready, base_commands)
        passed.append('native inputs and recipe identical to 2.5.3 Seed r8 outside %d generated-constant seam files'
                      % census['seam_files'])

        def untouched(ready):
            return next(row for row in ready['native'] if row['restored']['path'] != row['source']['path'] and
                        row['restored']['sha256'] == row['source']['sha256'])
        for label, mutate, expected in (
            ('native source seam rejected', lambda r, v, p: v.update(repl_c={}), 'native source seam declared'),
            ('missing native_sources note rejected', lambda r, v, p: v.pop('native_sources'), 'native source seam declared'),
            ('unreviewed seam kind rejected', lambda r, v, p: (v['header_changes'][0]['seams'][0].update(kind='eval.c authority swap'),
                p.update(source_changes=v['header_changes'])), 'unreviewed native seam kind'),
            ('undeclared compiled input change rejected', lambda r, v, p: untouched(r)['restored'].update(sha256='0'*64),
                'compiled input differs from 2.5.3 Seed r8'),
            ('foreign native input rejected', lambda r, v, p: untouched(r)['source'].update(sha256='0'*64),
                'native input is not a 2.5.3 Seed r8 input'),
            ('dropped native input rejected', lambda r, v, p: r['native'].remove(untouched(r)), 'native input population differs'),
            ('extra compiler flag rejected', lambda r, v, p: p['commands'][0].insert(1, '-DUNREVIEWED'), 'native recipe differs'),
            ('third constant substitution rejected', lambda r, v, p: (v['replacements'].update({'-DX=1': '-DX=2'}),
                p.update(allowed_substitutions=v['replacements'])), 'native constant substitutions'),
        ):
            bad = copy.deepcopy(real)
            mutate(*bad)
            reject(label, lambda: native_identity(*bad, base_ready, base_commands), expected)
        index = [dict(name='a', bank2=1), dict(name='b', bank2=2)]
        require(index_delta(index, index) == [] and index_delta(index, [index[0], dict(name='b', bank2=3)]) == ['b'],
                'index delta rule')
        reject('index row population change rejected', lambda: index_delta(index, index[:1]), 'L65INDEX row population')
        reject('index row order change rejected', lambda: index_delta(index, index[::-1]), 'L65INDEX row population')
        require(set(package_inputs(d.root)) <= {r['path'] for r in admission['input_bindings']}, 'package inputs unbound')
        passed.append('re-emitted package manifests are Seed preflight outputs; frozen ones equal the 2.5.3 record')
        # Pure producer negative controls, with no native/media entry point.
        reject('unclassified media mutation rejected', lambda:P.classified(b'a', b'b', {}))
        reject('wrong static delivery baseline rejected', lambda:P.project_delivery_code(b'wrong', b'base', b'newbase'))
        scope = MediaScope(d, admission)
        command = [str(symbol_tool(d.root)), '--defined-only', str(d.path(FINAL + '/media.elf'))]
        require(scope.classify(command) == 'ELF-read-only', 'accountable symbol parser command rejected')
        passed.append('accountable symbol parser command classified without parsing')
        reject('symbol parser extra arguments rejected', lambda:scope.classify(command + ['--extra']),
               'unexpected nm arguments')
        reject('symbol parser input outside Final rejected',
               lambda:scope.classify(command[:2] + [str(d.path(SEED + '/media.elf'))]),
               'unexpected nm arguments')
        scope.active = True  # Call the audit boundary directly, without executing a process.
        reject('unbound repository read rejected', lambda:scope.audit('open', (str(ROOT / '.git/HEAD'), 'r', 0)))
        reject('network audit event rejected', lambda:scope.audit('socket.connect', (None, 'invalid')))
        reject('direct subprocess audit event rejected', lambda:scope.audit('subprocess.Popen', ('/bin/false', ['/bin/false'], None, None)))
        reject('direct posix_spawn rejected', lambda:scope.audit('os.posix_spawn', ('/bin/false', ['/bin/false'], {})))
        scope.active = False
        for label, command in (
            ('second product link forbidden in media', admission['commands'][74]),
            ('Seed CLI forbidden in media', ['python3', 'tools/host-lisp/' + CFG.PRODUCER_TOOL, 'seed']),
            ('make forbidden in media', ['make', '-k', 'check-source']),
            ('network command forbidden in media', ['curl', 'https://invalid.example']),
            ('out-of-order cold stager command rejected', scope.stager[3]),
        ):
            reject(label, lambda:scope.authorize(command))
        for c in scope.stager:
            scope.authorize(c)
        reject('second cold stager link rejected', lambda:scope.authorize(scope.stager[3]))
    return dict(status='PASS', tests=passed, tests_passed=len(passed),
        actual_input_bindings=len(admission['input_bindings']), native_recipe_commands=75,
        product_commands=0, product_links=0, subprocesses=0, git_commands=0,
        source_admission='MOCKED; installation identity, lifecycle/native execution and seal admission are synthetic; no sealed run accepted',
        replay=d.bind(replay))


def main():
    F.policy()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('prepare', 'selftest'))
    p.add_argument('--out', help='fresh child of ' + CFG.PREP + '/')
    p.add_argument('--preview', action='store_true', help='bind uninstalled candidates; cannot authorize Final')
    p.add_argument('--replay', help='reviewed replay or candidate preview for offline selftest')
    a = p.parse_args()
    if a.mode == 'prepare':
        require(a.out and not a.replay, 'prepare requires --out')
        result = prepare(a.out, a.preview)
    else:
        require(a.replay and not a.out and not a.preview, 'selftest requires --replay')
        result = offline_selftest(a.replay)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, AssertionError, subprocess.CalledProcessError) as error:
        sys.exit('FAIL: ' + str(error))
