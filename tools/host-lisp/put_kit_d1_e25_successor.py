"""Dated provenance successor; no change to D1/E25 facts or site grammar."""
from pathlib import Path
import sys
import c2_v20_map_tuple_d1_e25_rebind_20260922 as D

ROOT=D.ROOT
HISTORICAL={
    'tools/host-lisp/c2_v20_map_tuple_d1_e25_rebind_20260922.py':
        '5bf64b0456db0f2558ec02876cef11f62c2eaf77d85bebb50ed1e0b382744fb2',
    'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v2.0-map-tuple-d1-e25-rebind-2026-09-22.json':
        '733c7fd9fff2e06bc36885384b9aff0b0b5f5191a09f247a09e25bb092a84e0b',
}

def verify_history(rows):
    D.require({r['path']:r['sha256'] for r in rows}==HISTORICAL,
              'Put-Kit predecessor bytes changed')

base_derive=D.derive
D.DRIVER=Path(__file__).resolve()
D.RECEIPT=D.ARCH/'c2.3-v2.0-map-tuple-d1-e25-put-kit-2026-09-22.json'

def derive():
    rows=[D.bind(ROOT/path) for path in HISTORICAL]
    verify_history(rows)
    for index in range(len(rows)):
        bad=[dict(row) for row in rows]
        bad[index]['sha256']='0'*64
        try: verify_history(bad)
        except D.RebindError: pass
        else: raise AssertionError('historical rewrite mutation survived')
    value=base_derive()
    value['put_kit_successor']=dict(source_authority='3bd13625',
        historical_inputs=rows, historical_rewrite_mutations=2,
        scope='Only live runtime provenance; decoder-site grammar, facts and seven mutations unchanged.')
    return value

D.derive=derive

if __name__=='__main__':
    raise SystemExit(D.main())
