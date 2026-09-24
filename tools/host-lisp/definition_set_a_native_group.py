"""Native Seed smoke: actual prompt grouping and use, never RAM-patched code."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT/'build/library-delivery-r8/load-five.py'
raw = source.read_text()
for old, new in {
    'build/library-delivery-final-five-load-r6-': 'build/definition-set-a-native-group-',
    'build/library-delivery-final-medium-r6': 'build/definition-set-a-seed-medium-r1',
    'timeout=90)': 'timeout=180)',
}.items():
    assert old in raw
    raw = raw.replace(old, new)
start = raw.index('    forms=')
end = raw.index('    for name,form,value in forms:', start)
forms = [
    ('defstruct-package', '(require "defstruct")', 'T'),
    ('group-one', '(defstruct groupa a b c d e)', 'T'),
    ('group-one-use', '(groupa-a (make-groupa 42 2 3 4 5))', '42'),
    ('group-two', '(defstruct groupb a b c d e)', 'T'),
    ('group-two-use', '(groupb-e (make-groupb 1 2 3 4 42))', '42'),
    ('recovery-control', '(+ 4 5)', '9'),
]
raw = raw[:start]+'    forms='+repr(forms)+'\n'+raw[end:]
needle = "        assert okay, 'native load failed: '+name"
assert raw.count(needle) == 1
raw = raw.replace(needle, needle+'''
        if name in ('group-one','group-two'):
            prior=rows[-2]['values']
            assert row['values']['images']['used']-prior['images']['used']==1, 'group was not one image'
            assert row['values']['entries']['used']-prior['entries']['used']==18, 'group entry population'
''')
raw = raw.replace('Fresh result after each require and stopped live counters; no device or wall-clock claim',
                  'Unmodified Seed medium: two prompt defstruct groups, one image and 18 entries each, accessors 42; not capacity/rollback or full qualification')
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
