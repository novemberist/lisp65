"""Comfort default dated D1/E25 provenance successor; inherited semantics unchanged."""
from pathlib import Path
import card_l_d1_e25_20260925 as K

D = K.D
ROOT = D.ROOT
HISTORICAL = dict(K.HISTORICAL)
HISTORICAL.update({'tools/host-lisp/card_l_d1_e25_20260925.py': '8fd9e6acca886b68e68dc03d4da5b01f7426397f1337c456a3452076e5027e59', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v2.0-map-tuple-d1-e25-card-l-2026-09-25.json': '32d705ae6b6d94ed530f139ccf02f6e5ac857f69a457fa73cfd2925273234030'})


def verify_history(rows):
    D.require({r['path']: r['sha256'] for r in rows} == HISTORICAL,
              'Card L predecessor bytes changed')


repair_derive = K.derive
D.DRIVER = Path(__file__).resolve()
D.RECEIPT = D.ARCH/'c2.3-v2.0-map-tuple-d1-e25-comfort-default-2026-09-27.json'


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
    value['comfort_default_successor'] = dict(
        source_authority='49b11a79', historical_inputs=rows,
        historical_rewrite_mutations=len(rows),
        scope='Live runtime provenance at Comfort default HEAD (including frozen Set B); '
              'decoder-site grammar, facts and seven mutations unchanged.')
    return value


D.derive = derive

if __name__ == '__main__':
    raise SystemExit(D.main())
