"""Exercise public compile/save/load and later anonymous helpers on the Seed.

Only a disposable data disk is writable. No runtime RAM patches.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
source = ROOT/'build/definition-pricing-r4/native-helper-witness.py'
raw = source.read_text()
start = raw.index("    price=json.loads")
end = raw.index("    m.command('t0')", start)
raw = raw[:start] + raw[end:]
replacements = {
    "variant=sys.argv[1];assert variant in ('before','after')": "variant='after'",
    "('build/definition-helper-native-'+variant+'-r1')": "'build/definition-set-a-prerequisites-r1'",
    'build/append-name-trace-inspect-r1/receipt.json': 'build/definition-set-a-seed-medium-r1/packed-receipt.json',
    "fixture=json.loads((ROOT/'build/definition-pricing-r3/fixture.json').read_text())":
        "fixture=dict(medium=base['medium'])\nbase['binary']=R.bind(ROOT/'build/append-name-pricing-r1/observer/build/bin/xmega65.native')",
    "forms=[('(load-lib \"bridge\")','T'),": "forms=[",
    "claim='NATIVE RAM PROJECTION ONLY'": "claim='Unmodified Set-A Seed: compile-string, persisted C2I readback, later anonymous helper'",
}
for old, new in replacements.items():
    assert raw.count(old) == 1, old
    raw = raw.replace(old, new)
assert "def put(" not in raw and "m.command(f's " not in raw
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
