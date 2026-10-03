#!/usr/bin/env python3
"""Replay the historical chain walker inventory in the pinned 2.5.2 era."""
import runpy
import sys
from pathlib import Path

import evidence_era as E

COMMIT = '49d128599c73a5b6eb6b8595431923cd30b84491'
ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / 'tools/host-lisp/chain_walker_inventory_disk_r7_20260930.py'


def main():
    if sys.argv[1:] != ['check']:
        raise SystemExit('usage: chain_walker_inventory_disk_r7_v253_20260930.py check')
    with E.host_source_world(COMMIT) as reads:
        runpy.run_path(str(TARGET), run_name='__main__')
    if not reads:
        raise E.EraError('historical chain walker check consumed no host sources')


if __name__ == '__main__':
    main()
