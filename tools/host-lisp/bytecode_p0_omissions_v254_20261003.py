"""2.5.4 dated omission-contract audit: superseded Werkbank suites are skipped.

The audit globs every suite.  2.5.4 adds one IDE defun to lib/ide-ui.lisp
(ide-bind-key; the E3 publication and the key-seam dispatch are written in
place in their single callers and add no defun).
Reviewer decision O3: the frozen tests/bytecode/stdlib/p0-stdlib-werkbank-subset.json
and the dated p0-stdlib-werkbank-subset-v253-20261002.json stay byte-identical
(both are bound by committed receipts); the dated
p0-stdlib-werkbank-subset-v254-20261003.json supersedes them and is audited.
Both superseded suites are already excluded from bytecode-p0-stdlib-check.

Controls: each skipped suite exists and fails the audit with exactly the
one new IDE name undeclared (nothing else); the v254 successor suite is
part of the audited population and passes.  All other suites are audited
unchanged; inherited selftest, scratch generated closure and the O2-lite
suite routing (2.5.4 live pin) are kept.
"""
import glob
import os

import bytecode_p0_stdlib as P
import o2_lite_consumers_v254_20261003 as V
from strings_scratch_20260928 import scratch, generated

SUPERSEDED = ('tests/bytecode/stdlib/p0-stdlib-werkbank-subset.json',
              'tests/bytecode/stdlib/p0-stdlib-werkbank-subset-v253-20261002.json')
SUCCESSOR = 'tests/bytecode/stdlib/p0-stdlib-werkbank-subset-v254-20261003.json'
NEW_NAMES = 'ide-bind-key'


def superseded_controls():
    for rel in SUPERSEDED:
        path = os.path.join(P._repo_root(), rel)
        try:
            P._validate_suite_omissions(P._read_suite(path))
        except P.StdlibCheckError as exc:
            message = str(exc)
            if not message.endswith('undeclared allow_omitted_defuns: ' + NEW_NAMES):
                raise P.StdlibCheckError('superseded suite fails for another reason: ' + message)
        else:
            raise P.StdlibCheckError('superseded suite unexpectedly passes the audit: ' + rel)


def audit():
    original = glob.glob
    skipped = {os.path.join(P._repo_root(), rel) for rel in SUPERSEDED}
    seen = []
    def filtered(pattern, *args, **kwargs):
        rows = original(pattern, *args, **kwargs)
        seen.extend(rows)
        return [p for p in rows if p not in skipped]
    glob.glob = filtered
    try:
        P._omission_contract_audit()
    finally:
        glob.glob = original
    if not skipped <= set(seen) or os.path.join(P._repo_root(), SUCCESSOR) not in seen:
        raise P.StdlibCheckError('omission audit population does not contain the superseded and successor suites')
    print('bytecode-p0-omission-contract v254: skipped superseded=%d successor audited' % len(SUPERSEDED))


if __name__ == '__main__':
    V.route_children()
    S = V.install()
    with S.suites():
        P._omission_contract_selftest()
        with scratch() as root, generated(root):
            superseded_controls()
            audit()
