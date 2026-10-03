"""Second dated successor for 2.5.3 IDE source allocation drift.

The 2026-09-30 receipt bound p0-ide-lib.json before the D3 lossless-load
fixtures; the receipt stays immutable and this successor re-pins the measured
world after the D3/D5 disk candidate.
"""
import hashlib
import c2_v126_editor_allocation_strings_r2_20260928 as H
import c2_v126_editor_allocation_o2_lite_20260929 as P
import c2_v126_editor_allocation_o2_lite_20260930 as Q
import o2_lite_consumers_20260929 as S
RECEIPT='config/c2-v126-editor-allocation-o2-lite-receipt-r2-20260930.json'
HISTORY={**Q.HISTORY,
 'tools/host-lisp/c2_v126_editor_allocation_o2_lite_20260930.py': hashlib.sha256((S.ROOT/'tools/host-lisp/c2_v126_editor_allocation_o2_lite_20260930.py').read_bytes()).hexdigest(),
 'config/c2-v126-editor-allocation-o2-lite-receipt-20260930.json': hashlib.sha256((S.ROOT/'config/c2-v126-editor-allocation-o2-lite-receipt-20260930.json').read_bytes()).hexdigest()}
INPUTS=[row['path'] for row in S.json.loads((S.ROOT/Q.RECEIPT).read_bytes())['inputs']]
def derive():
    with S.suites(): return H.derive()
if __name__=='__main__':
    S.finish('c2_v126_editor_allocation',derive,RECEIPT,HISTORY,(__file__,*INPUTS,H.__file__,P.__file__,Q.__file__))
