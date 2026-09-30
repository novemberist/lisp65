"""Dated O2-lite successor; inherited assertions and controls remain intact."""
import c2_v17_comfort_phase1b_strings_r2_20260928 as H
import o2_lite_consumers_20260929 as S
RECEIPT='config/c2-v17-comfort-phase1b-o2-lite-receipt-20260929.json'
HISTORY={'tools/host-lisp/c2_v17_comfort_phase1b_strings_r2_20260928.py': '113357dec1ddd776a8993e75b3809e8a3a802a8d58321fd7b652dec767f635fa', 'config/c2-v17-comfort-phase1b-receipt-strings-r2-20260928.json': 'd6c536f86f2cf72e854ca24faa61bfa0af3c76fa391dfab55764336af50e4510'}
# Retain every predecessor binding and its mutation controls.
HISTORY = {**H.HISTORY, **HISTORY}
INPUTS = [row['path'] for row in S.json.loads((S.ROOT / H.RECEIPT).read_bytes())['inputs']]
def derive():
    with S.E.host_source_world(S.ERA, extra_paths=('config/comfort-default-plane/libraries/repl-comfort-suite.json',)), S.scratch() as root:
        inherited=H.derive()
    S.continuity(inherited, 'config/c2-v17-comfort-phase1b-receipt-strings-r2-20260928.json')
    return dict(historical_strings=inherited,live_o2_lite=S.live())
if __name__=='__main__':
    S.finish('c2_v17_comfort_phase1b',derive,RECEIPT,HISTORY,(__file__,*INPUTS,H.__file__))
