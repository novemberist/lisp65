"""Dated successor for 2.5.3 IDE source allocation drift."""
import hashlib
import c2_v126_editor_allocation_strings_r2_20260928 as H
import c2_v126_editor_allocation_o2_lite_20260929 as P
import o2_lite_consumers_20260929 as S
RECEIPT='config/c2-v126-editor-allocation-o2-lite-receipt-20260930.json'
HISTORY={**P.HISTORY,
 'tools/host-lisp/c2_v126_editor_allocation_o2_lite_20260929.py': hashlib.sha256((S.ROOT/'tools/host-lisp/c2_v126_editor_allocation_o2_lite_20260929.py').read_bytes()).hexdigest(),
 'config/c2-v126-editor-allocation-o2-lite-receipt-20260929.json': hashlib.sha256((S.ROOT/'config/c2-v126-editor-allocation-o2-lite-receipt-20260929.json').read_bytes()).hexdigest()}
INPUTS=[row['path'] for row in S.json.loads((S.ROOT/P.RECEIPT).read_bytes())['inputs']]
def derive():
    with S.suites(): return H.derive()
if __name__=='__main__':
    S.finish('c2_v126_editor_allocation',derive,RECEIPT,HISTORY,(__file__,*INPUTS,H.__file__,P.__file__))
