"""Set B fifth-Seed d1_e25 successor; historical derivation and mutations retained.
Prepared before the attempt; execution and receipt closure remain gates.
"""
from pathlib import Path
import card_l_d1_e25_20260925 as K

D = K.D
ROOT = D.ROOT
HISTORICAL = dict(K.HISTORICAL)
HISTORICAL.update({'tools/host-lisp/nested_error_recovery_d1_e25_successor.py': 'ba064880c4a1ac4b3f5204d9c8f218deb812558031a86907da52d312568adcfc', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v2.0-map-tuple-d1-e25-nested-error-recovery-2026-09-23.json': '5a7f17eea34e13efa385c8c6d52bb285daeee5bd365cbb5beeef7a13b2e793a1'})


def verify_history(rows):
    D.require({r['path']: r['sha256'] for r in rows} == HISTORICAL,
              'Card L predecessor bytes changed')


HISTORICAL.update({'tools/host-lisp/card_l_d1_e25_20260925.py': '8fd9e6acca886b68e68dc03d4da5b01f7426397f1337c456a3452076e5027e59', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v2.0-map-tuple-d1-e25-card-l-2026-09-25.json': '32d705ae6b6d94ed530f139ccf02f6e5ac857f69a457fa73cfd2925273234030'})
repair_derive = K.derive
D.DRIVER = Path(__file__).resolve()
D.RECEIPT = D.ARCH/'c2.3-v2.0-map-tuple-d1-e25-set-b-2026-09-26.json'


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
    value['set_b_successor'] = dict(
        source_authority='fifth-Seed authority in set_b_fifth_seed_20260926.py', historical_inputs=rows,
        historical_rewrite_mutations=len(rows),
        scope='Only live runtime provenance (Set B retirement and resident transaction owner); '
              'decoder-site grammar, facts and seven mutations unchanged.')
    return value


D.derive = derive

if __name__ == '__main__':
    raise SystemExit(D.main())
