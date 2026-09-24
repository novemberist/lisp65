"""Isolated pricing of bounded emitter authentication over the first Seed."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT/'tools/host-lisp/definition_set_a_projection.py'
raw = source.read_text()
for old, new in {
    "BASE_COMMIT = '91cbb479'": "BASE_COMMIT = '20e4aa49'",
    'build/transient-retirement-final-medium-r1/materialized/generated-product-sources':
        'build/definition-set-a-seed-medium-r1/materialized/generated-product-sources',
}.items():
    assert raw.count(old) == 1
    raw = raw.replace(old,new)
exec(compile(raw,str(source),'exec'),dict(__name__='__main__',__file__=__file__))
