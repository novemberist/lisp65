"""Dated provenance successor (2026-09-23): nested-error recovery runtime change.

The nested-error recovery card (binding 44c021ee, source authority 90b5f9f2,
reviewer decision eaf59c62) changes c2_abort_empty_journal_derived in
src/c2_product_runtime.c.  D1/E25 binds the full runtime by SHA; its
decoder-site grammar, facts and seven mutations are unchanged.  This wrapper
keeps the retained-callable repair successor (and through it the Put-Kit
successor and the 2026-09-22 rebind) as the derivation, binds the repair
wrapper and its receipt by SHA, rejects mutations of each, and writes a new
dated receipt.  No historical receipt is rewritten.
"""
from pathlib import Path
import retained_callable_repair_d1_e25_successor as K

D = K.D
ROOT = D.ROOT
HISTORICAL = dict(K.HISTORICAL)
HISTORICAL.update({
    'tools/host-lisp/retained_callable_repair_d1_e25_successor.py':
        '805038f08d92254360e71cb771403777b130538bac7e6394fc865e0d7987c7ee',
    'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v2.0-map-tuple-d1-e25-retained-callable-repair-2026-09-23.json':
        '27c62ece4c76282a62a627e4bc7df30d2cda9f8f0c77a8982ff88558ea167178',
})


def verify_history(rows):
    D.require({r['path']: r['sha256'] for r in rows} == HISTORICAL,
              'nested-error recovery predecessor bytes changed')


repair_derive = K.derive
D.DRIVER = Path(__file__).resolve()
D.RECEIPT = D.ARCH/'c2.3-v2.0-map-tuple-d1-e25-nested-error-recovery-2026-09-23.json'


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
    value = repair_derive()
    value['nested_error_recovery_successor'] = dict(
        source_authority='90b5f9f2', binding='44c021ee', decision='eaf59c62', historical_inputs=rows,
        historical_rewrite_mutations=len(rows),
        scope='Only live runtime provenance (c2_abort_empty_journal_derived, c-alpha); '
              'decoder-site grammar, facts and seven mutations unchanged.')
    return value


D.derive = derive

if __name__ == '__main__':
    raise SystemExit(D.main())
