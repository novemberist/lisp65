"""Dated provenance successor (2026-09-23): runtime member 2 of the retained-callable repair.

The retained-callable repair (binding d3d5044b, source authority e0be22c1)
adds four byte copies to c2_append_rollback_prepare_phase in
src/c2_product_runtime.c.  D1/E25 binds the full runtime by SHA; its
decoder-site grammar, facts and seven mutations are unchanged.  This wrapper
keeps the Put-Kit successor (and through it the 2026-09-22 rebind) as the
derivation, binds both historical tools and receipts by SHA, rejects
mutations of each, and writes a new dated receipt.  No historical receipt
is rewritten.
"""
from pathlib import Path
import put_kit_d1_e25_successor as K

D = K.D
ROOT = D.ROOT
HISTORICAL = dict(K.HISTORICAL)
HISTORICAL.update({
    'tools/host-lisp/put_kit_d1_e25_successor.py':
        '17e503e410349729656bd0e0529b7d50b27be5052d9d4adb4d283288dd29ca5d',
    'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v2.0-map-tuple-d1-e25-put-kit-2026-09-22.json':
        'd37239650a67714bb7a98ca208f9c4f7751a713fe190fd2a6ec9f74e984774b6',
})


def verify_history(rows):
    D.require({r['path']: r['sha256'] for r in rows} == HISTORICAL,
              'retained-callable repair predecessor bytes changed')


put_kit_derive = K.derive
D.DRIVER = Path(__file__).resolve()
D.RECEIPT = D.ARCH/'c2.3-v2.0-map-tuple-d1-e25-retained-callable-repair-2026-09-23.json'


def derive():
    rows = [D.bind(ROOT/path) for path in HISTORICAL]
    verify_history(rows)
    for index in range(len(rows)):
        bad = [dict(row) for row in rows]
        bad[index]['sha256'] = '0'*64
        try:
            verify_history(bad)
        except D.RebindError:
            pass
        else:
            raise AssertionError('historical rewrite mutation survived')
    value = put_kit_derive()
    value['retained_callable_repair_successor'] = dict(
        source_authority='e0be22c1', binding='d3d5044b', historical_inputs=rows,
        historical_rewrite_mutations=len(rows),
        scope='Only live runtime provenance (member 2: c2_append_rollback_prepare_phase span copy); '
              'decoder-site grammar, facts and seven mutations unchanged.')
    return value


D.derive = derive

if __name__ == '__main__':
    raise SystemExit(D.main())
