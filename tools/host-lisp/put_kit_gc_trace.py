"""Same zero-cycle PC snapshots around the matched-GC protocol."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT / 'tools/host-lisp/boot_only_carrier_gc_trace.py'
raw = source.read_text()
raw = raw.replace('build/boot-only-carrier-r1/', 'build/put-kit-r4/')
raw = raw.replace('build/boot-only-carrier-gc-pc-', 'build/put-kit-gc-pc-')
raw = raw.replace('boot_only_carrier_qualification.py', 'put_kit_qualification.py')
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
