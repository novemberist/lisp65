"""Preserve the historical hybrid capacity world; prove the live Backspace seam."""
import evidence_era as E
import c2_v160_input_service_hybrid_capacity_world_attribution as H
import backspace_successor_20260928 as B

RECEIPT='config/c2-v160-hybrid-capacity-receipt-backspace-20260928.json'
HISTORY={'tools/host-lisp/c2_v160_input_service_hybrid_capacity_world_attribution.py': '41ed97dc83e5bc05e37c7e04afe2cdb112c6a0d27613294e89f8de2ffe947d67', 'tests/bytecode/dialect-v2/evidence/architecture-blocks/c2.3-v1.6-input-service-hybrid-capacity-world-attribution-receipt.json': 'c727d6ed16e2ed9c4a64645b6a83c649fedf5651de893b591fc3cf43b4a01430'}

def derive():
    with E.generated_workbench_world('18abc5a3c234501f282655a0a4295228874a2bb5') as reads:
        value=H.derive()
        H.selftest()
        H.receipt_gate(value)
    return dict(historical=value,era_reads=reads,era='18abc5a3c234501f282655a0a4295228874a2bb5')

if __name__=='__main__':
    B.finish('v160-hybrid-capacity',derive,RECEIPT,HISTORY,(__file__,H.__file__))
