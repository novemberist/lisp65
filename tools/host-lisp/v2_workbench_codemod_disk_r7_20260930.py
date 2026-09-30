"""Dated input closure, retaining the established generated artifact interface."""
import sys
from pathlib import Path
from unittest.mock import patch
import v2_workbench_codemod as C

CLOSURE = C.ROOT / 'config/v2-workbench-artifact-closure-disk-r7-20260930.json'
SUITE = 'p0-m65d-lib-disk-r7-20260930.json'


def generate(closure=CLOSURE, output=None):
    original = C._suite_output
    def suite_output(root, source):
        # The closure pins the dated input; the generated interface is consumed
        # by IDE resident_suites and existing composition tools.
        if Path(source).name == SUITE:
            return root / 'suites/p0-m65d-lib.json'
        return original(root, source)
    with patch.object(C, '_suite_output', suite_output):
        return C.generate(closure, output or C.DEFAULT_OUTPUT)


if __name__ == '__main__':
    import v11_c1_lease_codemod as L
    def run_base(selftest):
        if selftest:
            C.selftest()
        else:
            generate()
    with patch.object(L, 'run_base', run_base):
        raise SystemExit(L.main())
