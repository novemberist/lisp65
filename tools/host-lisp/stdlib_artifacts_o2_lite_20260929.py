"""Dated O2-lite successor; inherited assertions and controls remain intact."""
import stdlib_artifacts_strings_r3_20260928 as H
import o2_lite_consumers_20260929 as S
RECEIPT='config/stdlib-artifacts-o2-lite-receipt-20260929.json'
HISTORY={'tools/host-lisp/stdlib_artifacts_strings_r3_20260928.py': 'dd465b283eca121d91bb7d0ed454a64e2072d246ba1630691646e77be57525e5', 'config/strings-stdlib-artifacts-receipt-r3-20260928.json': 'cc8244469612ab5cbc0eaa90a1b50f4da3069243aaad27d4d40b79b4e34d3da5'}
# Retain every predecessor binding and its mutation controls.
HISTORY = {**H.HISTORY, **HISTORY}
INPUTS = [row['path'] for row in S.json.loads((S.ROOT / H.RECEIPT).read_bytes())['inputs']]
def derive():
    with S.E.host_source_world(S.ERA, extra_paths=('config/comfort-default-plane/libraries/repl-comfort-suite.json',)), S.scratch() as root:
        inherited=H.derive()
    S.continuity(inherited, 'config/strings-stdlib-artifacts-receipt-r3-20260928.json')
    return dict(historical_strings=inherited,live_o2_lite=S.live())
if __name__=='__main__':
    S.finish('stdlib_artifacts',derive,RECEIPT,HISTORY,(__file__,*INPUTS,H.__file__))
