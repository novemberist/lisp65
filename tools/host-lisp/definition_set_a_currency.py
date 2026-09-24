"""Repeat the established currency workload; not a substitute for package-use gates."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT/'build/minibuffer-round3/five-ide-currency.py'
raw = source.read_text()
for old, new in {
    'build/minibuffer-round3-five-ide-': 'build/definition-set-a-five-ide-',
    'build/minibuffer-seed-medium-round3': 'build/definition-set-a-seed-medium-r1',
    'HERE=Path(__file__).resolve().parent': "HERE=ROOT/'build/definition-set-a-r2'",
}.items():
    assert raw.count(old) == 1
    raw = raw.replace(old, new)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
