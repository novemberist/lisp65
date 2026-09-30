#!/usr/bin/env python3
"""Write/check immutable r7c Final evidence. No product commands.

Same --source-run, replay and sealed HEAD as Final; default output is under
Final so sealing does not dirty tracked source before check. Commit evidence
only after the matching check succeeds. Target/device/release gates remain open.
"""
import gzip
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
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
sys.path.append(str(ROOT / 'tools/host-lisp'))
import o2_lite_r7_final as F
from o2_lite_r7_final import Driver, BUDGET, FINAL, bindings, require, save, parser, driver_args, policy

LIMIT = 50_000_000
DEFAULT = FINAL + '/seal.json'
FORMAT = 'o2-lite-final-r7c-seal-v1'


class Seal:
    def __init__(self, driver, manifest=DEFAULT):
        self.d = driver
        self.manifest = manifest
        self.copies = str(Path(manifest).with_suffix(''))
        require(manifest == DEFAULT, 'r7c seal has one fixed write-once output')
        require(driver.path(manifest).is_relative_to(driver.path(FINAL)), 'seal must be under Final')
        require(manifest.endswith('.json') and manifest not in (
            FINAL + '/final-invocation.json', FINAL + '/final-identity.json', FINAL + '/media.json'), 'unsafe seal path')

    def evidence(self):
        d = self.d
        a = d.admit(claimed=True)
        inv = FINAL + '/final-invocation.json'
        identity = FINAL + '/final-identity.json'
        require(d.load(inv) == a, 'Final invocation/admission mismatch')
        v = d.load(identity)
        require(v['status'] == 'PASS' and all(v[k] == a[k] for k in ('head', 'sealed_run', 'source', 'budget')),
                'Final status/source/HEAD/budget mismatch')
        require(v['native_commands_consumed'] == 75 and v['product_links_claimed'] == 1 and
                v['media_transactions'] == 1, 'Final command/link/media budget mismatch')
        require(d.load(FINAL + '/product-link-claim.json') == dict(product_links=1, command=a['commands'][74]),
                'product link claim mismatch')
        require(v['artifacts'] == d.identity(a), 'Final identity population/bindings mismatch')
        rb = d.readback(a['media_readback'])
        require(v['media_readback'] == rb, 'Final readback binding mismatch')
        media = d.verify(v['media_execution'])
        require(media['path'] == FINAL + '/media-execution.json', 'wrong media execution receipt')
        helper = d.load(media['path'])
        require(helper['status'] == 'PASS' and helper['product_links'] == 0 and helper['stager_builds'] == 1 and
                helper['functions'] == ['inventory', 'media'] and helper['commands'] and
                all(r['returncode'] == 0 for r in helper['commands']), 'media execution not complete')
        from o2_lite_r7_replay import MediaScope, PRIORITY
        scope = MediaScope(d, a)
        for row in helper['commands']:
            command, kind = scope.authorize(row['command'])
            require(row['command'] == PRIORITY + command and row['kind'] == kind, 'media transcript command drift')
        require(scope.stager_index == 4 and scope.host_runs == 1, 'incomplete media transcript')
        require(helper['producer'] == d.bind('tools/host-lisp/o2_lite_r7_product.py'), 'media producer drift')
        selected = a['input_bindings'] + [a[k] for k in (
            'source', 'source_log', 'source_start', 'source_mounts', 'replay', 'seed_receipt')]
        selected += [p['final'] for p in v['artifacts']] + [rb, media]
        selected += [d.bind(p) for p in F.installed_tools() + [inv, identity, FINAL + '/product-link-claim.json']]
        selected += [d.bind(FINAL + f'/command-{i:03d}.log') for i in range(75)]
        # Bind all Final-native/media receipts and artifacts, not just the top-level JSON.
        for folder in ('native', 'media-r7'):
            selected += [d.bind(str(p.relative_to(d.root))) for p in sorted(d.path(FINAL + '/' + folder).rglob('*'))
                         if p.is_file()]
        for value in (helper, d.load(rb['path'])):
            selected += [d.verify(r) for r in bindings(value)]
        unique = {}
        from o2_lite_r7_replay import verify_any
        for row in selected:
            row = verify_any(row, d.root)
            require(row['path'] not in unique or unique[row['path']] == row, 'conflicting evidence binding')
            unique[row['path']] = row
        return a, v, [unique[p] for p in sorted(unique)]

    def seal(self):
        a, v, rows = self.evidence()
        require(not os.path.lexists(self.d.path(self.manifest)), 'seal exists; immutable')
        self.d.path(self.copies).mkdir()  # Atomic claim; preserve partial copies after failure.
        copies = []
        for row in rows:
            if not row['path'].endswith('.json'):
                continue
            require(not Path(row['path']).is_absolute(), 'external JSON evidence forbidden')
            raw = self.d.path(row['path']).read_bytes()
            zipped = len(raw) > LIMIT
            dest = self.copies + '/' + row['path'] + ('.gz' if zipped else '')
            path = self.d.path(dest)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(gzip.compress(raw, compresslevel=9, mtime=0) if zipped else raw)
            copies.append(dict(source=row, copy=self.d.bind(dest), compression='gzip' if zipped else 'none'))
        require(self.evidence() == (a, v, rows), 'evidence changed during seal')
        save(self.d.path(self.manifest), dict(format=FORMAT, status='PASS', source_head=a['head'],
            source_run=self.d.run, final=v, budget=BUDGET, inputs=rows, receipt_copies=copies,
            target_device_release='PENDING; separate reviewer gates'))
        return self.check()

    def check(self):
        a, v, rows = self.evidence()
        m = self.d.load(self.manifest)
        require(m['format'] == FORMAT and m['status'] == 'PASS', 'seal format/status mismatch')
        require(m['source_head'] == a['head'] and m['source_run'] == self.d.run and m['final'] == v and
                m['budget'] == BUDGET and m['inputs'] == rows, 'seal evidence/source mismatch')
        expected = {r['path']:r for r in rows if r['path'].endswith('.json')}
        require(len(m['receipt_copies']) == len(expected), 'receipt copy population mismatch')
        seen = set()
        for pair in m['receipt_copies']:
            src, dst = pair['source'], pair['copy']
            require(src == expected.get(src['path']) and src['path'] not in seen, 'copy source mismatch')
            seen.add(src['path'])
            zipped = src['bytes'] > LIMIT
            require(pair['compression'] == ('gzip' if zipped else 'none') and
                    dst['path'] == self.copies + '/' + src['path'] + ('.gz' if zipped else ''), 'copy encoding/path mismatch')
            self.d.verify(dst)
            raw = self.d.path(dst['path']).read_bytes()
            require((gzip.decompress(raw) if zipped else raw) == self.d.path(src['path']).read_bytes(), 'receipt copy differs')
        return dict(status='PASS', bindings=len(rows), receipt_copies=len(expected), source_run=self.d.run)


if __name__ == '__main__':
    try:
        policy()
        p = parser(('seal', 'check'))
        p.add_argument('--manifest', default=DEFAULT)
        a = p.parse_args()
        if a.selftest:
            require(a.mode is None and a.replay and not a.source_run, 'selftest requires --replay; no source run')
            result = F.selftest(a.replay)
        else:
            require(Path(__file__).resolve() == ROOT / F.installed_tools()[2], 'execute the committed installed seal tool')
            result = getattr(Seal(driver_args(a), a.manifest), a.mode)()
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, KeyError, AssertionError) as error:
        sys.exit('FAIL: ' + str(error))
