"""Card L dated provenance successor. Mutation matrix: inherited seven sealed
mutations and five decoder-form cases, plus one SHA corruption per historical
input (eight). No decoder grammar or semantic claims change. Card L authority
50ffcc9c adds LISP65_CARD_L_STAGE in c2_product_boot; the original decoder-form
cause remains 227e59e9. Predecessor tools and receipts remain immutable.
"""
from pathlib import Path
import nested_error_recovery_d1_e25_successor as K

D = K.D
ROOT = D.ROOT
HISTORICAL = dict(K.HISTORICAL)
HISTORICAL.update({'tools/host-lisp/nested_error_recovery_d1_e25_successor.py': 'ba064880c4a1ac4b3f5204d9c8f218deb812558031a86907da52d312568adcfc', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v2.0-map-tuple-d1-e25-nested-error-recovery-2026-09-23.json': '5a7f17eea34e13efa385c8c6d52bb285daeee5bd365cbb5beeef7a13b2e793a1'})


def verify_history(rows):
    D.require({r['path']: r['sha256'] for r in rows} == HISTORICAL,
              'Card L predecessor bytes changed')


repair_derive = K.derive
D.DRIVER = Path(__file__).resolve()
D.RECEIPT = D.ARCH/'c2.3-v2.0-map-tuple-d1-e25-card-l-2026-09-25.json'


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
    value['card_l_successor'] = dict(
        source_authority='50ffcc9c', historical_inputs=rows,
        historical_rewrite_mutations=len(rows),
        scope='Only live runtime provenance (LISP65_CARD_L_STAGE in c2_product_boot); '
              'decoder-site grammar, facts and seven mutations unchanged.')
    return value


D.derive = derive

if __name__ == '__main__':
    raise SystemExit(D.main())
