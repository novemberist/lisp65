"""Second and last Set-A Seed: priced bounded authentication only."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
SOURCE_AUTH = '630a9521'
source = ROOT/'tools/host-lisp/definition_set_a_producer.py'
raw = source.read_text()
for old,new in {
    'build/definition-set-a-r2': 'build/definition-set-a-r3',
    'build/definition-set-a-product-r2-preflight': 'build/definition-set-a-product-r3-preflight',
    'build/definition-set-a-product-r1': 'build/definition-set-a-product-r2',
    "AUTH='c97a8e60'": f"AUTH='{SOURCE_AUTH}'",
    'build/definition-group-capacity-r2/receipt.json': 'build/definition-group-capacity-r3/receipt.json',
}.items():
    assert old in raw,old
    raw=raw.replace(old,new)
needle="for path in ('build/definition-group-route-r3/receipt.json',"
assert raw.count(needle)==1
raw=raw.replace(needle,"for path in ('build/definition-set-a-auth-lifetime-r2/receipt.json',\n                 'build/definition-group-route-r3/receipt.json',")
needle="    checks=[]"
assert raw.count(needle)==1
raw=raw.replace(needle,"""    projection=R.C.load(ROOT/'build/definition-set-a-auth-projection-r1/receipt.json')
    deltas=[change for row in projection['rows'] for change in row.get('changes',[])]
    if any(not d['section'].startswith('.text.') for d in deltas):
        raise ValueError('authentication projection changed a non-text owner')
    if sum(d['delta'] for d in deltas)!=139:
        raise ValueError('authentication price changed before admission')
    for row in projection['inputs']:
        if R.bind(ROOT/row['path'])!=row: raise ValueError('authentication projection drift')
    checks=[R.bind(ROOT/'build/definition-set-a-auth-projection-r1/receipt.json')]""")
# The replacement has exactly the first Seed's Lisp plane. Copy its complete
# configured setup, preserving embedded provenance and bytes, not regenerating
# library/compiler inputs merely because the native control changed.
old_setup=ROOT/'build/definition-set-a-product-r2-preflight/setup-owned'
new_setup=ROOT/'build/definition-set-a-product-r3-preflight/setup-owned'
if not new_setup.exists():
    shutil.copytree(old_setup,new_setup)
exec(compile(raw,str(source),'exec'),globals())
