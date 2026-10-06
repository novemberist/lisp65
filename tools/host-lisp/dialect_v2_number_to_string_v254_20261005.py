#!/usr/bin/env python3
"""2.5.4 host successor of the v2 number->string four-engine pin (build host moved to Fedora 45).

The pinned receipt binds the live equivalence host binary by hash.  That binary is a local make product; after
the build host moved from Fedora 44 to Fedora 45 (2026-10-04) it had to be rebuilt with the installed compiler
(gcc 16.2.1), so its hash moved (335e11a9... -> 2d465206...) although no source, flag or input changed.  The five
bound input files, the case, the four engine observations and the verdict are unchanged.

This successor renders the verdict exactly like its predecessors and asserts the whole delta twice: against the
retained four-engine-v240-verdict.json and against the 2.5.3 receipt four-engine-v253-20261002-verdict.json only
binary.sha256 may differ.  A different observation, expected value, case, input binding or result is a real
finding, not a host effect, and fails.  The predecessor tools and receipts stay immutable; the pinned receipt is
the dated v254 one, recorded on the Fedora 45 host.

commands
  generate  exclusive creation of the v254 receipt (refuses an existing file)
  check     render, both delta assertions, inherited mutation controls, exact comparison with the v254 receipt
  selftest  negative controls of the delta rule on the committed receipts (no binary is run)
"""
import json
import sys

import dialect_v2_number_to_string as N

HOST = "Fedora 45, gcc 16.2.1 (the 2.5.3 receipt was recorded on Fedora 44)"
V240 = N.DEFAULT_RECEIPT
V253 = N.ROOT / (
    "tests/bytecode/dialect-v2/evidence/capability-carrier/"
    "number-to-string-prototype/four-engine-v253-20261002-verdict.json"
)
V254 = N.ROOT / (
    "tests/bytecode/dialect-v2/evidence/capability-carrier/"
    "number-to-string-prototype/four-engine-v254-20261005-verdict.json"
)
_render = N.render


def only_binary_hash_differs(actual, previous, label):
    previous = json.loads(json.dumps(previous))
    delta = json.loads(json.dumps(actual))
    if delta["binary"]["path"] != previous["binary"]["path"]:
        raise N.NumberToStringError("equivalence binary path moved")
    delta["binary"]["sha256"] = previous["binary"]["sha256"]
    if delta != previous:
        raise N.NumberToStringError("delta against the %s verdict is more than the binary hash" % label)


def render(binary, fixture):
    actual = _render(binary, fixture)
    only_binary_hash_differs(actual, N._load(V240), "v240")
    only_binary_hash_differs(actual, N._load(V253), "v253")
    return actual


def selftest():
    base = N._load(V253)
    only_binary_hash_differs(base, N._load(V240), "v240")
    moved = json.loads(json.dumps(base))
    moved["binary"]["sha256"] = "0" * 64
    only_binary_hash_differs(moved, base, "v253")
    mutations = (
        ("observation", lambda v: v["observations"].update({"lisp-lcc": '"-16383"'})),
        ("expected", lambda v: v.update(expected='"-16383"')),
        ("result", lambda v: v.update(result="failed")),
        ("case", lambda v: v.update(case="number-to-string-other")),
        ("input binding", lambda v: v["inputs"][0].update(sha256="1" * 64)),
        ("input population", lambda v: v["inputs"].pop()),
        ("binary path", lambda v: v["binary"].update(path="build/other/equivalence-check")),
        ("engine population", lambda v: v["observations"].pop("native-c-treewalk")),
    )
    rejected = []
    for label, mutate in mutations:
        trial = json.loads(json.dumps(moved))
        mutate(trial)
        try:
            only_binary_hash_differs(trial, base, "v253")
        except N.NumberToStringError:
            rejected.append(label)
        else:
            raise AssertionError("number->string host successor control survived: " + label)
    print("dialect-v2-number-to-string-v254: SELFTEST PASS controls=%d host=%s" % (len(rejected), HOST))
    return 0


N.render = render
N.DEFAULT_RECEIPT = V254

if __name__ == "__main__":
    if sys.argv[1:] == ["selftest"]:
        sys.exit(selftest())
    if sys.argv[1:2] == ["generate"] and V254.exists():
        print("dialect-v2-number-to-string: FAIL: the v254 receipt exists; a further change needs a dated successor")
        sys.exit(1)
    sys.exit(N.main())
