"""Gate 4: the retained-callable repair gate rows (lambda, wipe, sweep, sweep54) on the Seed.

Rebinds tools/host-lisp/retained_callable_repair_r2_gates.py with exact,
counted seams (instrument, output prefix, receipt identity) and writes the
rebound driver once to build/nested-error-recovery-r1/regression-gates.py,
which each run executes and binds.  The cumulative sweep keeps N = 1, 2, 16;
the over-cap 54 after them is gate 2's cumulative row of this card
(nested_error_recovery_gates.py cumulative), where the repair card's world
had no prompt.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'tools/host-lisp/retained_callable_repair_r2_gates.py'
TARGET = ROOT/'build/nested-error-recovery-r1/regression-gates.py'
raw = SOURCE.read_text()
for old, new in [
    ("INSTRUMENT = ROOT/'build/retained-callable-repair-r2-instrument-r1/instrument.json'",
     "INSTRUMENT = ROOT/'build/nested-error-recovery-instrument-r1/instrument.json'"),
    ("    out = ROOT / f'build/retained-callable-repair-r2-gates-{options.mode}-{options.world}-{options.attempt}' \\\n"
     "        if options.world == 'baseline' else ROOT / f'build/retained-callable-repair-r2-gates-{options.mode}-{options.attempt}'",
     "    out = ROOT / f'build/nested-error-recovery-reg-{options.mode}-{options.world}-{options.attempt}' \\\n"
     "        if options.world == 'baseline' else ROOT / f'build/nested-error-recovery-reg-{options.mode}-{options.attempt}'"),
    ("            for count in (1, 2, 16, 54):\n                name = f'capn{count}'",
     "            for count in (1, 2, 16):\n                name = f'capn{count}'"),
    ("            binding='d3d5044b', rebinding='2026-09-23 member 1 withdrawn', authority='dafc1f47', mode=options.mode, plan=plan, world=world,",
     "            binding='44c021ee', gate='4 (repair-card regression rows)', authority='90b5f9f2', mode=options.mode, plan=plan, world=world,"),
]:
    assert raw.count(old) == 1, old[:70]
    raw = raw.replace(old, new)
if TARGET.exists():
    assert TARGET.read_text() == raw, 'rebound driver drift'
else:
    TARGET.write_text(raw)
sys.argv[0] = str(TARGET)
exec(compile(raw, str(TARGET), 'exec'), dict(__name__='__main__', __file__=str(TARGET)))
