"""2.5.3 dated Comfort live-domain successor.

lib/domain-tier1.lisp gained %nth-after-domain-check (nth now validates the
list domain once, then walks), so the live Comfort measurement moved. The
sealed-era claim and the 2026-09-29 live receipt stay immutable; the live
measurement is pinned in its own dated receipt. All inherited gate controls
remain enabled.
"""
import runpy
import comfort_track_gate as H
import o2_lite_consumers_20260929 as S

H.LIVE_RECEIPT = H.RECEIPT.with_name('comfort-track-live-domain-receipt-v253-20260930.json')

if __name__ == "__main__":
    S.controls()
    with S.suites():
        runpy.run_module('comfort_track_strings_20260928', run_name="__main__")
