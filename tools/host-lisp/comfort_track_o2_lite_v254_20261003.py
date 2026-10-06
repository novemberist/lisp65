"""2.5.4 dated Comfort live-domain successor.

The 2.5.4 cards change the Comfort plane (lib/lite-hot.lisp HIST1: LF ends a
comment in %sexp-step; lib/repl-comfort-v250.lisp RP1 result guard) and the
live domain (lib/domain-tier1.lisp mapcan), so the bound live world moves.  The sealed-era claim, the
2026-09-29 live receipt and the 2.5.3 dated live receipt stay immutable; the
live measurement is pinned in its own dated receipt.  The historical world
and every inherited gate control are unchanged; the O2-lite source pin is the
2.5.4 live pin (o2_lite_consumers_v254_20261003).  Measured: the Comfort
steps and per-function counts equal the 2.5.3 live receipt; the only moved
fact is the bound live domain (lib/domain-tier1.lisp, 2.5.4 mapcan), which
check asserts exactly.
"""
import json
import runpy
import sys

import comfort_track_gate as H
import o2_lite_consumers_v254_20261003 as V

PREDECESSOR = H.RECEIPT.with_name('comfort-track-live-domain-receipt-v253-20260930.json')
H.LIVE_RECEIPT = H.RECEIPT.with_name('comfort-track-live-domain-receipt-v254-20261003.json')


def delta_control():
    old, new = (json.loads(p.read_text(encoding='utf-8')) for p in (PREDECESSOR, H.LIVE_RECEIPT))
    moved = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
    H.require(moved == ['live_domain'] and new['live_domain'] == H.bind(H.ROOT / 'lib/domain-tier1.lisp'),
              'Comfort v254 live successor moved beyond the live domain: ' + ', '.join(moved))


if __name__ == "__main__":
    V.route_children()
    S = V.install()
    try:
        with S.suites():
            runpy.run_module('comfort_track_strings_20260928', run_name="__main__")
    except SystemExit as stop:
        if stop.code not in (0, None):
            raise
    if sys.argv[1:] in (['check'], []):
        delta_control()
        print('comfort-track v254: live successor delta = live domain only')
