"""O2-lite successor for the previously masked v1.6 live ship-input lane."""
import subprocess
from unittest.mock import patch
import c2_v160_comfort_repl_strings_r2_20260928 as H
import o2_lite_consumers_20260929 as S
from strings_generated_r11_20260929 import current_generated
RECEIPT='config/c2-v160-comfort-repl-o2-lite-receipt-20260929.json'
HISTORY={'tools/host-lisp/c2_v160_comfort_repl_strings_r2_20260928.py': 'a45a4365e63fedafebb8ba7cc4c115097d939dcd7e69858a5a0aa35f36983f7f', 'config/c2-v160-comfort-repl-receipt-strings-r2-20260928.json': '182c2ec1638cb5a39ff6557c3672af8d31fed350defb9f229dc4df3aff454e3d'}
# Retain every predecessor binding and its mutation controls.
HISTORY = {**H.HISTORY, **HISTORY}
INPUTS = [row['path'] for row in S.json.loads((S.ROOT / H.RECEIPT).read_bytes())['inputs']]
EXTRAS=('config/comfort-default-plane/libraries/repl-comfort-suite.json',)

def era_ship(command, *, predecessor, **kwargs):
    S.S.require(command==H.COMMAND,'unexpected historical ship command')
    bootstrap=("import sys; sys.path.insert(0, 'tools/host-lisp')\n"
               "import evidence_era as E\n"
               "import c2_v160_comfort_repl_strings_r2_20260928 as H\n"
               f"with E.host_source_world({S.ERA!r}, extra_paths={EXTRAS!r}):\n"
               f"    raise SystemExit(H.ship_check({predecessor!r}))\n")
    return subprocess.run(H.COMMAND[:7]+['-c',bootstrap],**kwargs)

def derive():
    with S.E.host_source_world(S.ERA,extra_paths=EXTRAS), S.scratch(), patch.object(H,'run_ship',era_ship):
        inherited=H.derive()
    S.continuity(inherited,'config/c2-v160-comfort-repl-receipt-strings-r2-20260928.json')
    import bytecode_p0_stdlib as P
    path=S.SUITES[H.SUITE]
    with S.scratch() as root, current_generated(root), S.suites():
        result=P.check_suite(path,P._read_suite(str(S.ROOT/path)))
    S.S.require(result['cases']==258,'ship-input regression population drift')
    # Match the predecessor CLI's complete measurement fields; VM objects are not receipt data.
    metrics={key:result[key] for key in ('functions','cases','objects','code_bytes','directory_bytes','steps')}
    return dict(historical_strings=inherited,live_ship_suite=path,live_ship=metrics,live_o2_lite=S.live())

if __name__=='__main__':
    S.finish('c2-v160-comfort-repl',derive,RECEIPT,HISTORY,(__file__,*INPUTS,H.__file__,'tools/host-lisp/strings_generated_r11_20260929.py'))
