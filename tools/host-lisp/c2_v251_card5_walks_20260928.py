"""Walks Card-5 on 2.5.1/r6, retaining every inherited era and mutation."""
import copy
import c2_v251_card5 as H
import walks_successor_20260928 as W
H.K.ROUTES=dict(H.K.ROUTES,**{'block-26-build-integrity-check':'c2_v251_card5_walks_20260928.py'})
H.V.CHECK_HOST_ROUTES=copy.deepcopy(H.V.CHECK_HOST_ROUTES)
REPLACEMENTS={
 'c2_v16_defstruct_phase_a.py':'c2_v16_defstruct_phase_a_walks_20260928.py',
 'c2_v251_public_product.py preflight':'c2_v251_public_authority_walks_20260928.py check',
 'c2_v160_comfort_repl.py':'c2_v160_comfort_repl_walks_20260928.py',
 'c2_v251_card5.py':'c2_v251_card5_walks_20260928.py',
 'stdlib_artifacts_backspace_20260928.py':'stdlib_artifacts_walks_20260928.py',
 'c2_v160_hybrid_backspace_20260928.py':'c2_v160_hybrid_walks_20260928.py',
 'c2_v160_hybrid_capacity_backspace_20260928.py':'c2_v160_hybrid_capacity_walks_20260928.py',
 'c2_v251_keymap_receipt.py':'c2_v251_keymap_receipt_walks_20260928.py',
}
for targets in H.V.CHECK_HOST_ROUTES.values():
    for target,commands in targets.items():
        for old,new in REPLACEMENTS.items():commands=[c.replace(old,new) for c in commands]
        targets[target]=commands
H.V.CHECK_HOST_ROUTES['mk/gates.mk'].update({
 'c2-v16-defstruct-phase-a-selftest':['c2_v16_defstruct_phase_a_walks_20260928.py selftest'],
 'c2-v16-defstruct-phase-a-check':['c2_v16_defstruct_phase_a_walks_20260928.py check'],
 'c2-v160-comfort-repl-selftest':['c2_v160_comfort_repl_walks_20260928.py selftest'],
 'c2-v160-comfort-repl-check':['c2_v160_comfort_repl_walks_20260928.py check'],
})
RECEIPTS=['config/c2-v16-defstruct-phase-a-receipt-walks-20260928.json','config/c2-v251-public-authority-receipt-walks-20260928.json','config/c2-v160-comfort-repl-receipt-walks-20260928.json','config/walks-stdlib-artifacts-receipt-20260928.json',
 'config/c2-v160-hybrid-receipt-walks-20260928.json',
 'config/c2-v160-hybrid-capacity-receipt-walks-20260928.json',
 'config/c2-v251-keymap-receipt-walks-20260928.json']
HISTORY={'tools/host-lisp/c2_v251_card5.py': '75f2f2e4168c1713067995ddf2c68207b70e8721b5a784626f4a0b89bad9d64b', 'config/c2-v251-card5-receipt.json': '13d631e83596e841419527ef9d5d3dff4803c541215180d66aaf793a4b93a80a'}
RECEIPT='config/c2-v251-card5-receipt-walks-20260928.json'
def derive():
    return dict(inherited=H.derive(),receipts=[W.S.bind(p) for p in RECEIPTS])
if __name__=='__main__':
    W.finish('c2-v251-card5',derive,RECEIPT,HISTORY,
      (__file__,H.__file__,*RECEIPTS,*('tools/host-lisp/'+p.split()[0] for p in REPLACEMENTS.values())))
