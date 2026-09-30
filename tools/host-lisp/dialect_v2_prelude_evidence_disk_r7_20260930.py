"""Dated System/Runtime evidence, preserving the complete differential oracle."""
import sys
import dialect_v2_prelude_evidence as H
import disk_r7_consumers_20260930 as S
CONFIG = H.FAMILY_CONFIGS['system-runtime']
CONFIG['verdicts'] = H.ROOT / 'build/bytecode/dialect-v2/system-runtime-disk-r7-20260930'
CONFIG['evidence'] = H.ROOT / 'build/bytecode/dialect-v2/system-runtime-evidence-disk-r7-20260930'
RECEIPT = 'config/dialect-v2-system-runtime-disk-r7-receipt-20260930.json'
HISTORY = {'tests/bytecode/dialect-v2/evidence/system-runtime/differential-receipt.json': '070aa672c28103045cadf226265294d2d75ff0d3c6055d1550dc9fe3916c3397', 'tests/bytecode/dialect-v2/evidence/system-runtime/dialect-v2-inventory.json': '11e0205abe024344df8b44fd6c5294d7853ab98ecff38d3e78fb916a2e58f862', 'tests/bytecode/dialect-v2/evidence/system-runtime/dialect-v2-manifest.json': 'aae15e2bb7f3a238d22c5355e781d58b29221a438bcbaec1c6b54e574647de97'}

def finish():
    S.S.history(HISTORY)
    rows=[S.S.bind(p) for p in sorted(CONFIG['evidence'].iterdir()) if p.is_file()]
    value=dict(format='lisp65-system-runtime-disk-r7-evidence-v1', date='2026-09-30', status='PASS',
        predecessor=HISTORY, evidence=rows, source=S.S.bind(S.SOURCE),
        inputs=[S.S.bind(p) for p in (__file__, H.__file__, S.__file__, H.DEFAULT_CONTRACT,
             CONFIG['fixture'], 'tools/host-lisp/dialect_v2_system_runtime_disk_r7_20260930.py',
             'mk/disk-r7-consumers.mk')])
    raw=S.S.canonical(value);path=S.ROOT/RECEIPT
    if 'generate' in sys.argv and not path.exists():
        with path.open('xb') as stream: stream.write(raw)
    else: S.require(path.read_bytes()==raw, 'system-runtime evidence receipt drift')

if __name__ == '__main__':
    S.require(sys.argv[1:3] == ['--family', 'system-runtime'], 'r7 evidence family drift')
    S.source_controls()
    original = H.tempfile.TemporaryDirectory
    write = H.write_evidence
    def temporary(*args, **kwargs):
        if kwargs.get('dir') == H.ROOT: kwargs['dir'] = H.ROOT/'build'
        return original(*args, **kwargs)
    def write_once(rendered, output):
        if output == CONFIG['evidence'] and output.exists():
            H.check_evidence(rendered, output)
        else:
            write(rendered, output)
    with S.patch.object(H.tempfile, 'TemporaryDirectory', temporary), S.patch.object(H, 'write_evidence', write_once):
        code = H.main(sys.argv[1:])
    if code == 0 and 'selftest' not in sys.argv: finish()
    raise SystemExit(code)
