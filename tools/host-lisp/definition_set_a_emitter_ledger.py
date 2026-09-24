"""Replay unchanged worlds, attributing transport spans to emitter slices."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
world = sys.argv.pop(1)
assert world in ('before', 'seed')
source = ROOT/'build/definition-ledger-r1/full-r2.py'
raw = source.read_text()
replacements = {
    "f'build/definition-ledger-full-{slots}-r2'":
        f"f'build/definition-set-a-emitter-{world}-{{slots}}-r2'",
    "('APPEND_PHASE_PC','c2_overlay_call')":
        "('APPEND_PHASE_PC','c2_facade_target_c2e_overlay')",
    'build/definition-ledger-r1/observer/build/bin/xmega65.native':
        'build/definition-set-a-emitter-observer-r1/build/bin/xmega65.native',
}
if world == 'seed':
    replacements.update({
        'build/append-name-trace-inspect-r1/receipt.json': 'build/definition-set-a-seed-medium-r1/packed-receipt.json',
        'build/transient-retirement-final-medium-r1/': 'build/definition-set-a-seed-medium-r1/',
        'range(3 + 3*slots)': 'range(1)',
        'i == 2+3*slots': 'i == 0',
        "assert m.memory_range(append, 2) == bytes.fromhex('8609')":
            "assert truth.symbol('c2_ready').value < 256\n    assert m.memory_range(append, 2) == bytes([0xa4, truth.symbol('c2_ready').value])",
    })
for old, new in replacements.items():
    assert raw.count(old) == 1, old
    raw = raw.replace(old, new)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
