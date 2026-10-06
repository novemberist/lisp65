#!/usr/bin/env python3
"""Replay the r7 product receipts as disk_r7_product_receipts_v254_20261003.py does, under the historical host pin rule.

Successor of disk_r7_product_receipts_v254_20261003.py (immutable).  The r7 product receipts witness the 2.5.2
product build and bind the host compiler that build executed (/usr/bin/gcc at its Fedora 44 bytes).  Since the
build host moved to Fedora 45 (2026-10-04) that binary no longer exists, so the unchanged replay fails on the host
alone.  Rule (historical_host_pin_20261004): a host tool row of the past release 2.5.2 is accepted when its hash
is the pin in the committed 2.5.2 reproduction policy.  Every other row is checked exactly as before, in the same
eras (era_replay_v254_20261003 around disk_r7_product_receipts_v253_20260930).

modes
  check     the replay under the rule
  selftest  the rule's controls (no replay)
"""
import json
import sys

import historical_host_pin_20261004 as H

RELEASE = '2.5.2'


def world():
    import strings_seed_producer as S
    return H.checked_world(RELEASE, S)


if __name__ == '__main__':
    if sys.argv[1:] == ['selftest']:
        print(json.dumps(H.selftest(), indent=2))
    elif sys.argv[1:] == ['check']:
        import era_replay_v254_20261003 as R
        with world() as seen:
            R.run('disk_r7_product_receipts_v253_20260930.py', [['check']], 'disk_r7_product_receipts_v254_r2_20261004.py')
        print('r7 product receipts: historical host pin rule applied to %d host tool row(s) of release %s'
              % (len(seen), RELEASE))
    else:
        raise SystemExit('usage: disk_r7_product_receipts_v254_r2_20261004.py check | selftest')
