"""Dated O2-lite successor; inherited assertions and controls remain intact."""
import c2_v126_editor_allocation_strings_r2_20260928 as H
import o2_lite_consumers_20260929 as S
RECEIPT='config/c2-v126-editor-allocation-o2-lite-receipt-20260929.json'
HISTORY={'tools/host-lisp/c2_v126_editor_allocation_strings_r2_20260928.py': 'a2533be80bf0707c335683e39833955352f17db6ad53a84b397efc298dd18d0e', 'config/c2-v126-editor-allocation-receipt-strings-r2-20260928.json': '5f979eec60634f183f22b9ccee511d2d8db67372a33372748e594651d8393bd3'}
# Retain every predecessor binding and its mutation controls.
HISTORY = {**H.HISTORY, **HISTORY}
INPUTS = [row['path'] for row in S.json.loads((S.ROOT / H.RECEIPT).read_bytes())['inputs']]
def derive():
    with S.suites():current=H.derive()
    return S.continuity(current, 'config/c2-v126-editor-allocation-receipt-strings-r2-20260928.json')
if __name__=='__main__':
    S.finish('c2_v126_editor_allocation',derive,RECEIPT,HISTORY,(__file__,*INPUTS,H.__file__))
