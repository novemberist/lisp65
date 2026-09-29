"""Q strings provenance successor with all inherited semantic mutations."""
import copy
from unittest.mock import patch
import c2_q_gate as H
import strings_successor_r2_20260928 as S
from strings_scratch_20260928 import scratch, normalized
RECEIPT='config/c2-q-receipt-strings-20260928.json'
HISTORY={'tools/host-lisp/c2_q_gate.py': '7f4e812521b501b63eb7177eae41e0587e58b4e9cbaebdb446207946dc3162a8', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.2-q-renderer-host-successor-receipt.json': '16af5d0def9d363b0f58682f52fcd909d3f6f1586443d31a42346b4512cf7cd7'}
def derive():
    with scratch() as root:
        captured=[];original=H.atomic_json
        def write(path,value):
            if path==H.SUCCESSOR_RECEIPT:captured.append(value)
            else:original(path,value)
        with patch.multiple(H,BUILD=root,BASE_PREFIX=root/'base/stdlib-p0',CANDIDATE_PREFIX=root/'candidate/stdlib-p0',GENERATED_SUITE=root/'equivalence-cases.json',OBSERVATIONS=root/'candidate/observations.json'),patch.object(H,'atomic_json',write):
            S.require(H.main(record_successor=True)==0,'inherited Q gate failed')
        value,=captured
        old=H.load(H.SUCCESSOR_RECEIPT)
        for key in ('source_contract','mutations_rejected','successor_mutations'):
            S.require(value[key]==old[key],'Q semantics drift: '+key)
        for key in ('delta','projected_post_Link80','current_composition'):
            S.require(value['artifacts'][key]==old['artifacts'][key],'Q artifact semantics drift: '+key)
        return normalized(value,root)
if __name__=='__main__':S.finish('c2-q',derive,RECEIPT,HISTORY,(__file__,H.__file__,'tools/host-lisp/strings_scratch_20260928.py'))
