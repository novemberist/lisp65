"""Next Card-5 after the first strings draft; revised Return consumers."""
import copy
import c2_v251_card5_strings_20260928 as H
import strings_successor_r2_20260928 as S
RECEIPT='config/c2-v251-card5-receipt-strings-r2-20260928.json'
HISTORY={'tools/host-lisp/c2_v251_card5_strings_20260928.py': '40c9622a5c6daf79aec965e89d4024e862377754b1b3be80bac82c811374c83c', 'config/c2-v251-card5-receipt-strings-20260928.json': '9d7a0aa5b46cc7422d3e2ffefb2361f17f41d760ced0cdc569c791f878790fe0'}
REPLACEMENTS={'stdlib_artifacts_strings_20260928.py': 'stdlib_artifacts_strings_r2_20260928.py', 'c2_v160_comfort_repl_strings_20260928.py': 'c2_v160_comfort_repl_strings_r2_20260928.py', 'c2_v17_comfort_phase1b_strings_20260928.py': 'c2_v17_comfort_phase1b_strings_r2_20260928.py', 'c2_v17_repl_idle_blink_strings_20260928.py': 'c2_v17_repl_idle_blink_strings_r2_20260928.py', 'c2_v251_public_authority_strings_20260928.py': 'c2_v251_public_authority_strings_r2_20260928.py', 'c2_v16_defstruct_phase_a_walks_20260928.py': 'c2_v16_defstruct_phase_a_strings_r2_20260928.py', 'c2_v160_hybrid_walks_20260928.py': 'c2_v160_hybrid_strings_r2_20260928.py', 'c2_v160_hybrid_capacity_walks_20260928.py': 'c2_v160_hybrid_capacity_strings_r2_20260928.py', 'c2_v251_keymap_receipt_walks_20260928.py': 'c2_v251_keymap_receipt_strings_r2_20260928.py', 'stdlib_artifacts_walks_20260928.py': 'stdlib_artifacts_strings_r2_20260928.py', 'c2_v251_card5_strings_20260928.py': 'c2_v251_card5_strings_r2_20260928.py'}
RECEIPTS=['config/c2-v16-defstruct-phase-a-receipt-strings-r2-20260928.json', 'config/c2-v160-comfort-repl-receipt-strings-r2-20260928.json', 'config/c2-v160-hybrid-capacity-receipt-strings-r2-20260928.json', 'config/c2-v160-hybrid-receipt-strings-r2-20260928.json', 'config/c2-v17-comfort-phase1b-receipt-strings-r2-20260928.json', 'config/c2-v17-repl-idle-blink-receipt-strings-r2-20260928.json', 'config/c2-v251-keymap-receipt-strings-r2-20260928.json', 'config/c2-v251-public-authority-receipt-strings-r2-20260928.json', 'config/strings-stdlib-artifacts-receipt-r2-20260928.json']
H.K.ROUTES=dict(H.K.ROUTES,**{'block-26-build-integrity-check':'c2_v251_card5_strings_r2_20260928.py'})
H.V.CHECK_HOST_ROUTES=copy.deepcopy(H.V.CHECK_HOST_ROUTES)
for targets in H.V.CHECK_HOST_ROUTES.values():
    for target,commands in targets.items():
        for old,new in REPLACEMENTS.items():commands=[c.replace(old,new) for c in commands]
        targets[target]=commands

def derive():
    return dict(inherited=H.derive(),receipts=[S.bind(p) for p in RECEIPTS])
if __name__=='__main__':
    S.finish('c2-v251-card5-r2',derive,RECEIPT,HISTORY,
      (__file__,H.__file__,'mk/gates.mk','mk/workbench.mk',*RECEIPTS,*('tools/host-lisp/'+p for p in REPLACEMENTS.values())))
