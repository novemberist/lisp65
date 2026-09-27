#!/usr/bin/env python3
"""comfort-library card: the established matched-state GC instrument, rebound.

Pure renaming derivation of the instrument chain the nested-error recovery card
used (build/nested-error-recovery-gc-equal-*-1/driver.py -> ov_crc16 ->
build/index-crc-r1/gc-equal.py -> build/init-repair-r2/gc-equal-state.py ->
block_26_vm_hardening_dwx_prefilter.measure_gc_population).  The same stimuli,
forcing rule (free-list head cleared after alloc's first instruction at the
witnessed input boundary), snapshots and mark counts.

Roles:
  baseline   the accepted 2.4.0 medium (87cb0f6e), same ELF
  candidate  the Comfort medium, Comfort NOT loaded (equal-state control)
  comfort    the Comfort medium with (require "repl-comfort") and (repl) typed
             first; the same 18 burst passes are typed into Comfort's own
             l65> editor, the forced collection fires on the first key of the
             final line, and the final line is "(+ 3 4)" (same 8 events as
             "abcdefg\\n", so the modulo-256 input counter oracle 136 holds);
             the screen oracle is the evaluated 7 under a live l65> prompt.

Usage: comfort_library_gc.py <role> --trial N
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT / 'build/index-crc-r1/gc-equal.py'
raw = source.read_text()

PRELUDE = r'''
def comfort_prelude(m):
    import time as _t
    def rows():
        return G.CYCLES.ROWS.decoded_framebuffer(m.screen()).splitlines()
    def active(r):
        return r[-1].replace('{$A0}', ' ').strip()
    m.type_text('(require "repl-comfort")\n')
    deadline = _t.monotonic() + 240
    while _t.monotonic() < deadline:
        r = rows()
        echo = [i for i, x in enumerate(r) if x == 'LISP65> (REQUIRE "REPL-COMFORT")']
        if active(r) == 'LISP65>' and echo and 'T' in r[echo[-1] + 1:-1]:
            break
        _t.sleep(.2)
    else:
        raise G.PrefilterError('comfort prelude: require did not answer T')
    m.type_text('(repl)\n')
    deadline = _t.monotonic() + 60
    while _t.monotonic() < deadline:
        r = rows()
        if active(r) == 'L65>':
            break
        _t.sleep(.1)
    else:
        raise G.PrefilterError('comfort prelude: l65> prompt did not appear')
    path = OUT / 'comfort-prelude-framebuffer.txt'
    path.write_text(m.screen())
    state['comfort_prelude'] = dict(active='L65>', framebuffer=G.bind(path))
'''

inner = {
    # Comfort mode: prelude instead of the native controller, Comfort's own final line.
    "source=inspect.getsource(G.measure_gc_population)":
        PRELUDE + "source=inspect.getsource(G.measure_gc_population)",
    "changed=source\n":
        "changed=source\n"
        "if a.role=='comfort':\n"
        "    for _old,_new in (('monitor.type_text(CONTROLLER)','comfort_prelude(monitor)'),\n"
        "                      (\"frame=monitor.wait_screen(['\\\\n7\\\\n','\\\\n9\\\\n'])\",\"frame=monitor.wait_screen(['\\\\n7\\\\n','L65>'])\")):\n"
        "        assert changed.count(_old)==1,_old;changed=changed.replace(_old,_new)\n",
    "ns=dict(G.__dict__,boundary=boundary,force=force,state=state,alloc=alloc,snapshot=snapshot,marked=marked)":
        "ns=dict(G.__dict__,boundary=boundary,force=force,state=state,alloc=alloc,snapshot=snapshot,marked=marked)\n"
        "if a.role=='comfort':ns.update(FINAL='(+ 3 4)\\n',comfort_prelude=comfort_prelude)",
    "row.update(authority='9ff48e97',":
        "row.update(card='comfort-library',binding='180cb993',role=a.role,final_line=ns['FINAL'],authority='9ff48e97',",
}
outer = {
    "\"choices=['baseline','no-init','candidate','place','string-extra']\":\"choices=['baseline','candidate']\"":
        "\"choices=['baseline','no-init','candidate','place','string-extra']\":\"choices=['baseline','candidate','comfort']\"",
    "\"f'build/init-repair-gc-equal-{a.role}-descope-{a.trial}'\":\"f'build/index-crc-gc-equal-{a.role}-{a.trial}'\"":
        "\"f'build/init-repair-gc-equal-{a.role}-descope-{a.trial}'\":\"f'build/comfort-library-gc-equal-{a.role}-{a.trial}'\"",
    "\"'retirement-repair-final-library-medium-r2'\":\"'storage-owner-final-medium-r2'\"":
        "\"'retirement-repair-final-library-medium-r2'\":\"'nested-error-recovery-seed-medium-r1'\"",
    "\"'init-repair-seed-medium-r2'\":\"'index-crc-seed-medium-r1'\"":
        "\"'init-repair-seed-medium-r2'\":\"'comfort-library-medium-r2'\"",
    "changes={\n":
        "changes={\n" + "".join(" %r:%r,\n" % (k, v) for k, v in inner.items()),
}
for old, new in outer.items():
    assert raw.count(old) == 1, old
    raw = raw.replace(old, new)
exec(compile(raw, str(source), 'exec'), dict(__name__='__main__', __file__=__file__))
