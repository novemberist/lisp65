#!/usr/bin/env python3
"""Replay the sealed prelude-control evidence in the pinned 2.5.2 source era.

The committed evidence (inventory, profile container, manifests, verdicts) was
generated when lib/lcc.lisp had the bytes of 2.5.2. The 2.5.3 candidate changed
lib/lcc.lisp on purpose (multi-pair setq, arity refusal, nth tails), which moves
only the inventory's lib/lcc.lisp source binding. Historical evidence is not
regenerated in place (Card 4 and the G5 closure bind its bytes); it is checked
against the Lisp sources of the commit that sealed it. Living LCC content is
verified by the LCC, Card 4 and suite gates.
"""
import sys

import dialect_v2_prelude_evidence as T
import evidence_era as E

COMMIT = '49d128599c73a5b6eb6b8595431923cd30b84491'


def main(argv):
    with E.host_source_world(COMMIT) as reads:
        status = T.main(argv)
    if status == 0 and not reads:
        raise E.EraError('historical prelude evidence consumed no host sources')
    return status


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
