#!/usr/bin/env python3
"""2.5.3 successor of the Workbench private-inline composition probe (m65d lane).

D2/D4 reshaped lib/m65-disk.lisp (offset helpers now use ash, / and logand;
%m65d-remount-finish left the private-inline population, 14 -> 13). Against the
v253-20260930 receipt the m65d rejection distribution moves from
rel8 14 / code-object 1 / recursive 1 / passed 0 / already-private 1 to
rel8 12 / code-object 2 / recursive 1 / passed 1 / already-private 1:
  %m65d-mask          rel8        -> passed       (now a one-line ash/mod helper)
  %m65d-entry-valid-p rel8        -> code-object  (target %m65d-dir-entries, 375 B)
  %m65d-set, %m65d-bitmap-off, %m65d-bit-free-p stay rel8 (other target function).
This successor pins that expectation, asserts the delta candidate by candidate
against the retained v253-20260930 receipt, and asserts the IDEX lane equal to
it. %m65d-mask is eligible but deliberately not applied (audit only, the
product suites are unchanged). The predecessor tool and receipts stay immutable.
"""
import json
import sys

import workbench_private_inline_probe as P

PREVIOUS = P.ROOT / (
    "tests/bytecode/dialect-v2/evidence/capability-carrier/"
    "workbench-private-inline-composition-probe-v253-20260930.json"
)
M65D_EXPECTED = {"rel8": 12, "code-object": 2, "recursive": 1, "unexpected": 0,
                 "passed": 1, "already-private": 1}
M65D_ELIGIBLE = ["%m65d-mask"]
OUTCOME_DELTA = {"%m65d-mask": ("rel8", "passed"),
                 "%m65d-entry-valid-p": ("rel8", "code-object")}
REL8_TARGET_MOVED = ("%m65d-set", "%m65d-bitmap-off", "%m65d-bit-free-p")
EXISTING_PRIVATE = (14, 13)
_render = P.render


def _rows(suite):
    return {row["candidate"]: row for row in suite["results"]}


def render():
    actual = _render()
    previous = json.loads(PREVIOUS.read_text(encoding="utf-8"))
    old = {row["id"]: row for row in previous["suites"]}
    new = {row["id"]: row for row in actual["suites"]}
    if set(old) != set(new) or old["idex"] != new["idex"]:
        raise P.ProbeError("IDEX lane is not equal to the v253-20260930 receipt")
    before, after = old["m65d"], new["m65d"]
    if (before["existing_private_inline_functions"], after["existing_private_inline_functions"]) != EXISTING_PRIVATE:
        raise P.ProbeError("m65d private-inline population delta drift")
    if before["suite_sha256"] == after["suite_sha256"]:
        raise P.ProbeError("m65d suite did not move")
    if [r["candidate"] for r in before["results"]] != [r["candidate"] for r in after["results"]]:
        raise P.ProbeError("m65d candidate list moved")
    old_rows, new_rows = _rows(before), _rows(after)
    for name, old_row in old_rows.items():
        new_row = new_rows[name]
        if name in OUTCOME_DELTA:
            if (old_row["outcome"], new_row["outcome"]) != OUTCOME_DELTA[name]:
                raise P.ProbeError("outcome delta drift: %s" % name)
        elif name in REL8_TARGET_MOVED:
            if old_row["outcome"] != "rel8" or new_row["outcome"] != "rel8":
                raise P.ProbeError("rel8 lane drift: %s" % name)
        elif old_row != new_row:
            raise P.ProbeError("unexpected change of candidate %s" % name)
    if after["eligible_but_not_applied"] != M65D_ELIGIBLE:
        raise P.ProbeError("m65d eligible set drift")
    return actual


P.SUITES["m65d"]["expected"] = dict(M65D_EXPECTED)
P.SUITES["m65d"]["eligible_but_not_applied"] = list(M65D_ELIGIBLE)
P.render = render


def selftest():
    if M65D_EXPECTED["passed"] != len(M65D_ELIGIBLE) or sum(M65D_EXPECTED.values()) != 17:
        raise P.ProbeError("successor expectation is inconsistent")
    if set(OUTCOME_DELTA) & set(REL8_TARGET_MOVED):
        raise P.ProbeError("delta inventory overlap")
    for name in (*OUTCOME_DELTA, *REL8_TARGET_MOVED):
        if name not in P.SUITES["m65d"]["candidates"]:
            raise P.ProbeError("delta names a non-candidate: %s" % name)
    if P.SUITES["idex"]["eligible_but_not_applied"]:
        raise P.ProbeError("IDEX deferred eligible candidate drift")
    print("workbench-private-inline-probe-v253-20261002: SELFTEST PASS expected-passed=%s" % ",".join(M65D_ELIGIBLE))


if __name__ == "__main__":
    if sys.argv[1:] == ["selftest"]:
        try:
            selftest()
        except P.ProbeError as exc:
            print("workbench-private-inline-probe-v253-20261002: FAIL: %s" % exc, file=sys.stderr)
            sys.exit(1)
        sys.exit(0)
    sys.exit(P.main())
