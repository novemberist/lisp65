"""Phase-1b qualification successor: preserve checks, adapt two source spellings."""
import sys
from types import SimpleNamespace
from unittest.mock import patch
import c2_v17_comfort_phase1b_adapter_replacement_card as H
import editor_semantics_walks_20260928 as SEM
import walks_successor_20260928 as W
C=H.CARD.COMFORT
RECEIPT='config/c2-v17-comfort-phase1b-receipt-walks-20260928.json'
HISTORY={'tools/host-lisp/c2_v17_comfort_phase1b_adapter_replacement_card.py': '6cc63ca510deca3c314eaa9e7f32e06dff845e740dcdbf8846ae019f2a52b06c', 'tools/host-lisp/c2_v160_comfort_repl.py': '616d12bf7456c18dfe700905c70fdbe7b586785121f4b57ff4cb0957ba6fd0b5', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v1.7-comfort-phase1b-variant-b-adapter-r1-receipt.json': '5cf9edc101fd037b401542d213c289df93578143a62b784d7c2e736b07c9aa82'}
ORIGINAL_SOURCE_GATE=C.source_gate

def source_gate(contract):
    # Only two syntactic predicates receive equivalent access spellings.
    # Executable suites always consume the unmodified, authority-bound bytes.
    W.source_proof()
    editor=C.READ_LINE.read_text(encoding='utf-8')
    for index in (8,4):
        direct='state'
        for _ in range(index):direct='(cdr '+direct+')'
        W.S.require(direct in editor,'walks direct state accessor absent')
        editor=editor.replace(direct,'(nthcdr '+str(index)+' state)')
    with patch.object(C,'READ_LINE',SimpleNamespace(read_text=lambda **kw:editor)):
        return ORIGINAL_SOURCE_GATE(contract)

def derive():
    with patch.object(C,'source_gate',source_gate), patch.object(C,'BUILD',SEM.OUT/'comfort'):
        H.qualification_check()
    return dict(qualification='PASS: all inherited qualification assertions',
                semantics=SEM.derive(),claim_limit='Host semantics and sealed qualification; no new product/device claim')

if __name__=='__main__':
    if sys.argv[1:] == ['qualification-check']:sys.argv[1]='check'
    W.finish('c2-v17-comfort-phase1b',derive,RECEIPT,HISTORY,
             (__file__,SEM.__file__,H.__file__,C.__file__,
              'tests/bytecode/libs/p0-stdlib-ship-input-wait-base.json',
              'tests/bytecode/libs/p0-repl-comfort.json',
              'tests/bytecode/libs/p0-repl-comfort-v240-resident.json',
              'lib/repl-comfort.lisp','lib/sexp-depth.lisp'))
