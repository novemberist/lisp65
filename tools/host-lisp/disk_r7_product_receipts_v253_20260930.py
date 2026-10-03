#!/usr/bin/env python3
"""Replay the r7 product receipts in the pinned 2.5.2 source era.

The r7 product receipts witness the 2.5.2 Seed/Final product build and bind the
Lisp sources and helper tool identities as that build consumed them. The 2.5.3
candidate changes some of them on purpose (lib/domain-tier1.lisp, IDE and LCC
libraries, tools/host-lisp/editor_product_list_domain.py). The receipts and the
consumer stay immutable; this wrapper runs the consumer with the host Lisp
sources, suites and the one bound helper tool read from the commit that sealed
the product. Media, plane and byte-ledger assertions remain live.
"""
import sys

import disk_r7_product_receipts_20260930 as P
import evidence_era as E

COMMIT = '49d128599c73a5b6eb6b8595431923cd30b84491'
# Bound (not executed) tool identities recorded by the 2.5.2 product build.
EXTRA = ['tools/host-lisp/editor_product_list_domain.py']


def era():
    return E.host_source_world(COMMIT, EXTRA)


def main():
    with era() as reads:
        P.main()
    if not reads:
        raise E.EraError('historical product receipts consumed no host sources')


if __name__ == '__main__':
    main()
