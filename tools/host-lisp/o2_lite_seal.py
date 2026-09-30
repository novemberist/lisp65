#!/usr/bin/env python3
"""Write/check immutable O2-lite Final evidence; no product commands.

The default Seed is r6, selected by the shared parser.
Uses the same --source-run (legacy alias --sealed-run) and replay contract as o2_lite_final.py. There is no
embedded SOURCE_RUN. JSON copies above 50,000,000 bytes use deterministic gzip.
A Final seal closes build identity only; target/device/release remain later gates.
"""
import gzip
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
from o2_lite_final import Driver, BUDGET, encoded, require, save, parser

LIMIT = 50_000_000
DEFAULT = 'tests/bytecode/dialect-v2/evidence/architecture-blocks/o2-lite-final-20260929.json'


class Seal:
    def __init__(self, driver, manifest=DEFAULT):
        self.d = driver
        self.manifest = manifest
        self.copies = str(Path(manifest).with_suffix(''))
        driver.path(manifest)

    def evidence(self):
        d = self.d
        a = d.admit(claimed=True)
        inv = d.out + '/final-invocation.json'
        identity = d.out + '/final-identity.json'
        require(d.load(inv) == a, 'Final invocation/admission mismatch')
        v = d.load(identity)
        require(v['status'] == 'PASS' and all(v[k] == a[k] for k in ('head','sealed_run','source','budget')),
                'Final status/source/HEAD/budget mismatch')
        require(v['commands_consumed'] == len(a['commands']) + len(a['media_commands']), 'command count mismatch')
        require(len(v['artifacts']) == 4 and {r['role'] for r in v['artifacts']} == {'ELF','PRG','LTO','D81'},
                'Final population mismatch')
        expected = {r['role']:r for r in a['pairs']}
        selected = a['input_bindings'] + a['delta_proofs'] + [a[k] for k in ('source','source_log','replay','seed_receipt')]
        for pair in v['artifacts']:
            want = expected[pair['role']]
            require(pair['seed'] == want['seed'] and pair['final']['path'] == want['destination'] and
                    pair['byteidentical'] is True, 'Final pair mismatch')
            old, new = d.verify(pair['seed']), d.verify(pair['final'])
            require(old['sha256'] == new['sha256'] and old['bytes'] == new['bytes'], 'Final identity drift')
            selected += [old,new]
        rb = d.verify(v['media_readback'])
        require(rb['path'] == a['media_readback'], 'readback path mismatch')
        readback = d.load(rb['path'])
        require(readback['status'] == 'PASS' and readback['every_file_read_back'] is True and
                readback['unclassified_bytes'] == 0 and
                readback['medium'] == next(r['final'] for r in v['artifacts'] if r['role'] == 'D81'), 'readback not PASS')
        from o2_lite_final import bindings
        selected += [d.verify(r) for r in bindings(readback)] + [rb]
        paths = [inv,identity,'tools/host-lisp/o2_lite_final.py','tools/host-lisp/o2_lite_seal.py',
                 'docs/planning/o2-lite-final-runbook.md']
        paths += [d.out + f'/command-{i:03d}.log' for i in range(v['commands_consumed'])]
        selected += [d.bind(p) for p in paths]
        unique = {}
        for row in selected:
            row = d.verify(row)
            require(row['path'] not in unique or unique[row['path']] == row, 'conflicting binding')
            unique[row['path']] = row
        return a, v, [unique[p] for p in sorted(unique)]

    def copy(self, rows):
        copies = []
        for row in rows:
            if not row['path'].endswith('.json'):
                continue
            self.d.verify(row)
            raw = self.d.path(row['path']).read_bytes()
            zipped = len(raw) > LIMIT
            dest = self.copies + '/' + row['path'] + ('.gz' if zipped else '')
            path = self.d.path(dest); path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as stream:
                stream.write(gzip.compress(raw,compresslevel=9,mtime=0) if zipped else raw)
            copies.append(dict(source=row,copy=self.d.bind(dest),compression='gzip' if zipped else 'none'))
        return copies

    def seal(self):
        a,v,rows = self.evidence()
        require(not os.path.lexists(self.d.path(self.manifest)), 'seal exists; immutable')
        self.d.path(self.copies).mkdir(parents=True)  # atomic claim, retained on failure
        copies = self.copy(rows)
        # Recheck after copying; changing live evidence must not be sealed.
        require(self.evidence() == (a,v,rows), 'evidence changed during seal')
        save(self.d.path(self.manifest),dict(format='o2-lite-final-seal-v1',status='PASS',
             source_head=a['head'],sealed_run=self.d.run,final=v,budget=BUDGET,inputs=rows,receipt_copies=copies,
             target_device_release='PENDING; separate reviewer gates'))
        return self.check()

    def check(self):
        a,v,rows = self.evidence()
        m = self.d.load(self.manifest)
        require(m['format'] == 'o2-lite-final-seal-v1' and m['status'] == 'PASS', 'seal format/status mismatch')
        require(m['source_head'] == a['head'] and m['sealed_run'] == self.d.run and m['final'] == v and
                m['budget'] == BUDGET and m['inputs'] == rows, 'seal evidence/source mismatch')
        expected = {r['path']:r for r in rows if r['path'].endswith('.json')}
        require(len(m['receipt_copies']) == len(expected), 'receipt copy population mismatch')
        seen = set()
        for pair in m['receipt_copies']:
            src = pair['source']; dst = pair['copy']
            require(src == expected.get(src['path']) and src['path'] not in seen, 'copy source mismatch')
            seen.add(src['path'])
            zipped = src['bytes'] > LIMIT
            require(pair['compression'] == ('gzip' if zipped else 'none') and
                    dst['path'] == self.copies + '/' + src['path'] + ('.gz' if zipped else ''), 'copy encoding/path mismatch')
            self.d.verify(dst)
            raw = self.d.path(dst['path']).read_bytes()
            require((gzip.decompress(raw) if zipped else raw) == self.d.path(src['path']).read_bytes(), 'receipt copy differs')
        return dict(status='PASS',bindings=len(rows),receipt_copies=len(expected),sealed_run=self.d.run)


def selftest():
    import subprocess
    with tempfile.TemporaryDirectory(prefix='o2-seal-') as temp, \
         patch.object(subprocess,'run',side_effect=AssertionError('offline only')), \
         patch.object(subprocess,'check_output',side_effect=AssertionError('offline only')):
        d = Driver('seed','source','replay.json','0'*64,'final',temp)
        for path,raw in [('small.json',b'{}'),('large.json',b' ' * 200 + b'{}')]:
            d.path(path).write_bytes(raw)
        rows = [d.bind('small.json'),d.bind('large.json')]
        s = Seal(d,'evidence/seal.json')
        a,v = dict(head='a'*40),dict(status='PASS')
        # Only evidence admission is substituted here; Final tests it separately.
        s.evidence = lambda: (a,v,[d.verify(r) for r in rows])
        passed = []
        def reject(name,fn):
            try: fn()
            except (ValueError,FileExistsError): passed.append(name)
            else: raise AssertionError('negative survived: '+name)
        with patch.dict(globals(),LIMIT=100):
            s.seal(); s.check(); passed.append('seal/check, plain and deterministic gzip copies')
            reject('immutable seal',s.seal)
            original = d.path(s.manifest).read_bytes()
            for label, mutate in [('missing copy',lambda x:x['receipt_copies'].pop()),
                                  ('wrong run',lambda x:x.update(sealed_run='wrong')),
                                  ('wrong HEAD',lambda x:x.update(source_head='b'*40)),
                                  ('duplicate copy',lambda x:x['receipt_copies'].__setitem__(1,x['receipt_copies'][0]))]:
                m = json.loads(original); mutate(m); d.path(s.manifest).write_bytes(encoded(m))
                reject(label,s.check); d.path(s.manifest).write_bytes(original)
            cp = d.load(s.manifest)['receipt_copies'][1]['copy']['path']
            d.path(cp).write_bytes(b'corrupt'); reject('copy drift',s.check)
            d.path('small.json').write_bytes(b'wrong'); reject('source drift',s.check)
        return dict(status='PASS',tests=passed,product_commands=0,git_commands=0,
                    gzip_test='synthetic threshold 100 bytes; production threshold 50,000,000 bytes')


if __name__ == '__main__':
    try:
        require(__debug__, 'assertions required')
        p = parser(('seal','check'))
        p.add_argument('--manifest',default=DEFAULT)
        a = p.parse_args()
        if a.selftest:
            require(a.mode is None,'standalone selftest required'); result=selftest()
        else:
            require(a.mode and a.sealed_run and a.replay and a.replay_sha256,'mode, sealed run and pinned replay required')
            result=getattr(Seal(Driver(a.seed_dir,a.sealed_run,a.replay,a.replay_sha256,a.out),a.manifest),a.mode)()
        print(json.dumps(result,indent=2))
    except (ValueError,OSError,KeyError,AssertionError) as error:
        sys.exit('FAIL: '+str(error))
