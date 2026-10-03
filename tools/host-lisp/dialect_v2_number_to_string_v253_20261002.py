#!/usr/bin/env python3
"""2.5.3 successor of the v2 number->string four-engine pin.

The 2.5.3 candidate changed src/eval.c (and with it the live equivalence host
binary); the five bound input files, the case, the four engine observations and
the verdict are unchanged. This successor renders the verdict exactly like the
predecessor and additionally asserts the whole delta against the retained
four-engine-v240-verdict.json: only binary.sha256 may differ. The predecessor
tool and receipt stay immutable; the pinned receipt is the dated v253 one.
"""
import json
import sys

import dialect_v2_number_to_string as N

V240 = N.DEFAULT_RECEIPT
V253 = N.ROOT / (
    "tests/bytecode/dialect-v2/evidence/capability-carrier/"
    "number-to-string-prototype/four-engine-v253-20261002-verdict.json"
)
_render = N.render


def render(binary, fixture):
    actual = _render(binary, fixture)
    previous = json.loads(json.dumps(N._load(V240)))
    delta = json.loads(json.dumps(actual))
    if delta["binary"]["path"] != previous["binary"]["path"]:
        raise N.NumberToStringError("equivalence binary path moved")
    delta["binary"]["sha256"] = previous["binary"]["sha256"]
    if delta != previous:
        raise N.NumberToStringError("delta against the v240 verdict is more than the binary hash")
    return actual


N.render = render
N.DEFAULT_RECEIPT = V253

if __name__ == "__main__":
    sys.exit(N.main())
