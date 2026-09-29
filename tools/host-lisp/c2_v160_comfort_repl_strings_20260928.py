"""Strings successor; replay predecessor against exact pre-string inputs."""
import os
import subprocess
import sys
import tempfile
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import c2_v160_comfort_repl_walks_20260928 as H
import strings_successor_20260928 as S
RECEIPT='config/c2-v160-comfort-repl-receipt-strings-20260928.json'
HISTORY={'tools/host-lisp/c2_v160_comfort_repl_walks_20260928.py': '0f46ef5b5a770fba158b689b96b1a6a310e6273a3be6748b91c2d8bdcf8a4391', 'config/c2-v160-comfort-repl-receipt-walks-20260928.json': '7ec19fd6cdcaec940aba199c39fc4c788edb679f3bf5b5a52285243111a859ee'}
SUITE = 'tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json'
COMMAND = ['nice', '-n', '18', 'ionice', '-c3', sys.executable, '-B',
           'tools/host-lisp/bytecode_p0_stdlib.py', '--check', SUITE]


def ship_check(predecessor):
    """Regenerate the closure from this world's suites AND Lisp sources."""
    import bytecode_p0_stdlib as P
    import v2_workbench_codemod as C
    with S.predecessor_world() if predecessor else nullcontext():
        with tempfile.TemporaryDirectory(prefix='strings-v160-', dir=S.ROOT/'build') as raw:
            target = Path(raw)
            C.generate(C.DEFAULT_CLOSURE, target)
            original = P._read_suite

            def read_suite(path, seen=None):
                resolved = Path(path).resolve()
                if resolved.is_relative_to(C.DEFAULT_OUTPUT.resolve()):
                    path = str(target / resolved.relative_to(C.DEFAULT_OUTPUT.resolve()))
                return original(path, seen)

            with patch.object(P, '_read_suite', read_suite):
                return P.main(['--check', SUITE])


def run_ship(command, *, predecessor, **kwargs):
    # Adapt only the inherited ship check, not other historical subprocesses.
    S.require(command == COMMAND, 'unexpected predecessor subprocess')
    bootstrap = (
        "import sys; sys.path.insert(0, 'tools/host-lisp'); "
        "import c2_v160_comfort_repl_strings_20260928 as V; "
        f"raise SystemExit(V.ship_check({predecessor!r}))"
    )
    return subprocess.run(COMMAND[:7] + ['-c', bootstrap], **kwargs)


def derive():
    def historical_run(command, **kwargs):
        return run_ship(command, predecessor=True, **kwargs)

    child = SimpleNamespace(run=historical_run, PIPE=subprocess.PIPE,
                            STDOUT=subprocess.STDOUT)
    with S.predecessor_world(), patch.object(H, 'subprocess', child):
        inherited = H.derive()
    current = run_ship(COMMAND, predecessor=False, cwd=S.ROOT,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                       text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    S.require(current.returncode == 0, current.stdout)
    return dict(inherited=inherited, live_strings=S.live(),
                live_suite=current.stdout.strip())
if __name__=='__main__':
    S.finish('c2_v160_comfort_repl',derive,RECEIPT,HISTORY,(__file__,H.__file__,'tests/bytecode/libs/p0-repl-comfort-v250.json'))
