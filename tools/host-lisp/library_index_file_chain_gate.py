#!/usr/bin/env python3
"""Execute the live L65I parser across a data-track sector boundary.

The fixture is encoded from five symbolic rows, not inherited packed bytes.
The old directory guard and missing fuel check are exercised mutations.
This gate does not replace native all-five publication/capacity witnesses.
"""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host-lisp'))
import bytecode_p0_stdlib as P
import c2_require_resolver_gate as G


def run():
    suite_path = ROOT / 'tests/bytecode/libs/p0-stdlib-require-resolver.json'
    suite = P._read_suite(str(suite_path))
    assert '%disk-file-link-valid-p' in suite['functions']
    suite['cases'] = [dict(name='index-entry', expr='(%l65i-parse)', expect='nil')]
    heap, _, _, _, _, _, directory, _, _, _ = P._compile_suite(suite)
    abi, ledger = P._suite_abi(suite)
    names = ('buffer', 'place', 'string-extra', 'inspect', 'defstruct')
    records = [dict(name=n, track=18, sector=i, combined_crc32=i+1,
        dependencies=[], execution_source=2, artifact_bytes=512, bank2=16,
        images=1, entries=1, resolutions=1, roots=1, scratch=8)
        for i, n in enumerate(names)]
    index = G.encode_index(records)
    assert len(index) == G.HEADER_BYTES + len(records)*G.ROW_BYTES > 254
    G.decode_index(index)
    directory_sector = bytearray(256)
    directory_sector[1] = 255
    directory_sector[2:5] = bytes([0x82, 18, 34])
    directory_sector[5:21] = b'l65index' + bytes([0xa0])*8
    sectors = {(40, 3): bytes(directory_sector),
        (18, 34): bytes([18, 35]) + index[:254],
        (18, 35): (bytes([0, len(index[254:])+1]) + index[254:]).ljust(256, b'\0')}

    class VM(P.B.P0VM):
        def _disk_read_sector_impl(self, track, sector):
            self.reads.append((track, sector))
            self.disk_buf = list(sectors[(track, sector)])
            return True

    source = ROOT / 'lib/stdlib-require.lisp'
    def world(mutation=None):
        h, d = heap.clone(), dict(directory)
        if mutation:
            text = source.read_text()
            old, new = {
                'directory': ('(if (%disk-file-link-valid-p', '(if (%disk-directory-link-valid-p'),
                'fuel': ("(> (symbol-value '*l65i-fuel*) 0)", 't')}[mutation]
            assert text.count(old) == 1
            text = text.replace(old, new)
            for form in P.C.parse_all(text):
                if form[0] != 'defun' or form[1] not in ('%l65i-next-byte', '%l65i-open-sector'):
                    continue
                name, code, helpers = P.C.compile_top_form_with_helpers(
                    form, h, strict_arity=True, abi_profile=abi)
                d[h.intern(name)] = code
                for name, code in helpers:
                    d[h.intern(name)] = code
        v = VM(heap=h, directory=d, abi_profile=abi, abi_ledger=ledger, max_steps=10000000)
        v.reads = []
        return h, d, v

    rows = []
    for mutation in (None, 'directory'):
        h, d, v = world(mutation)
        value = v.run(d[h.intern('%l65i-parse')], [])
        assert (value != P.B.NIL) == (mutation is None)
        if mutation is None:
            assert all(n in h.obj_to_text(value) for n in names)
            assert v.reads == [(40, 3), (18, 34), (18, 35)]
        rows.append(dict(case=mutation or 'two-sector-track18', result=h.obj_to_text(value), reads=v.reads))
    for mutation in (None, 'fuel'):
        h, d, v = world(mutation)
        h.set_symbol_value(h.intern('*l65i-fuel*'), P.B.mkfix(0))
        value = v.run(d[h.intern('%l65i-open-sector')], [P.B.mkfix(18), P.B.mkfix(34)])
        assert (value != P.B.NIL) == (mutation == 'fuel')
        assert bool(v.reads) == (mutation == 'fuel')
        rows.append(dict(case=mutation or 'fuel-exhausted', result=h.obj_to_text(value), reads=v.reads))
    h, d, v = world()
    for track, sector in ((1, 0), (80, 39), (0, 0), (81, 0), (1, 40), (-1, 0), (1, -1), (18, 34)):
        value = v.run(d[h.intern('%disk-file-link-valid-p')],
                     [P.B.mkfix(n) for n in (18, 34, track, sector)])
        expected = 1 <= track <= 80 and 0 <= sector < 40 and (track, sector) != (18, 34)
        assert (value != P.B.NIL) == expected
        rows.append(dict(case='data-link-boundary', track=track, sector=sector, accepted=expected))
    bind = lambda p: dict(path=p.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    return dict(status='PASS', rows=rows, inputs=[bind(source), bind(suite_path), bind(Path(__file__))],
        index_bytes=len(index), mutations_rejected=['directory-guard-on-file', 'fuel-check-removed'],
        claim='Live-source host parser and data-link boundaries; native loading and stopped user reserve remain separate gates.')


if __name__ == '__main__':
    result = run()
    out = ROOT / 'build/library-index-file-chain-gate/receipt.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + '\n')
    print('library-index-file-chain: PASS cases=%d mutations=%d' %
          (len(result['rows']), len(result['mutations_rejected'])))
