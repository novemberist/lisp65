"""Read-only charged GC replay of the replacement Seed and its predecessor."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT/'build/transient-retirement-r2/gc-charges.py'
raw = source.read_text()
raw = raw.replace('build/transient-retirement-gc-equal-', 'build/definition-set-a-auth-gc-equal-')
raw = raw.replace('build/transient-retirement-gc-charges-', 'build/definition-set-a-auth-gc-charges-')
raw = raw.replace("'resolver-owner-final-medium-r1'", "'transient-retirement-final-medium-r1'")
raw = raw.replace("'transient-retirement-seed-medium-r1'", "'definition-set-a-seed-medium-r2'")
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
