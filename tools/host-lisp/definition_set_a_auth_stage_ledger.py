"""Replay replacement Seed with the sealed, disjoint stage observer."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
assert sys.argv[1] == 'seed'
source = ROOT/'tools/host-lisp/definition_set_a_stage_ledger.py'
raw = source.read_text()
needle = "exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))"
assert raw.count(needle) == 2
# The first occurrence belongs to the stage adapter's injection machinery;
# transform the emitter adapter after that machinery has composed it.
pos = raw.rfind(needle)
patch = "raw = raw.replace('build/definition-set-a-seed-medium-r1', 'build/definition-set-a-seed-medium-r2')\n"
patch += "raw = raw.replace('stages-{world}-{{slots}}-r2', 'auth-stages-{world}-{{slots}}-r1')\n"
raw = raw[:pos]+patch+raw[pos:]
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
